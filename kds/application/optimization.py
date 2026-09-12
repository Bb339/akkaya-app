"""Application orchestration without HTTP/UI or scientific formula duplication."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import uuid4
from kds.adapters.project_science import build_bundle, data_hash
from kds.application.readiness import readiness
from kds.data.repositories import NotFoundError
from kds.science.execution import execute


def now():
    return datetime.now(timezone.utc).isoformat()


def configuration(payload, document):
    required = {'scenario','algorithm','seed','objective','water_budget_ratio','config'}
    if not isinstance(payload,dict) or not required <= payload.keys() or payload.keys() - (required | {'selected_ids'}):
        raise ValueError('Explicit scenario, algorithm, seed, objective, water_budget_ratio and config are required.')
    if payload['scenario'] not in ('S1','S2') or payload['algorithm'] not in ('GA','ACO','ABC'):
        raise ValueError('Use S1/S2 and GA/ACO/ABC.')
    if payload['objective'] not in ('water_saving','water_efficiency','max_profit'):
        raise ValueError('Unknown objective.')
    if type(payload['seed']) is not int or not 0 <= payload['seed'] < 2**32-1:
        raise ValueError('seed must be an integer in [0, 2^32-2].')
    ratio = payload['water_budget_ratio']
    if type(ratio) not in (int,float) or not 0 < ratio <= 10:
        raise ValueError('water_budget_ratio must be in (0, 10].')
    params = payload['config']
    expected = {'GA':{'popSize','generations','cxRate','mutRate'}, 'ACO':{'ants','iterations','rho','q'},
                'ABC':{'foodSources','cycles','limit'}}[payload['algorithm']]
    if not isinstance(params,dict) or set(params)!=expected:
        raise ValueError('Explicit algorithm configuration required: '+', '.join(sorted(expected)))
    for key,value in params.items():
        if key in ('cxRate','mutRate','rho'):
            if type(value) not in (int,float) or not 0 < value <= 1:
                raise ValueError(key+' must be in (0,1].')
        elif key=='q':
            if type(value) not in (int,float) or not 0 < value <= 10:
                raise ValueError('q must be in (0,10].')
        elif type(value) is not int or not 2 <= value <= 200:
            raise ValueError(key+' must be an integer in [2,200].')
    known = {u['external_id'] for u in document['analysis_units']}
    ids = payload.get('selected_ids', [])
    if not isinstance(ids,list) or any(not isinstance(i,str) or i not in known for i in ids) or len(ids)!=len(set(ids)):
        raise ValueError('selected_ids must contain unique project analysis unit identifiers.')
    scenario = payload['scenario']
    options = dict(params, seed=payload['seed'], seasonSource=scenario.lower(),
                   scenarioType='single' if scenario=='S1' else 'double', twoSeason=scenario=='S2',
                   simpleMode=False, envFlowRatio=.10, enforceDeliveryCaps=True,
                   waterModel='calib', riskMode='none', riskLambda=0., riskSamples=120, waterQualityFilter=True)
    return {**payload, 'selected_ids':ids, 'options':options}


class OptimizationApplicationService:
    def __init__(self, repository, executor=execute):
        self.repository, self.executor = repository, executor

    def readiness(self, project_id):
        return readiness(self.repository.get(project_id))

    def get(self, project_id, run_id):
        run = self.repository.get(project_id).get('runs',{}).get(run_id)
        if run is None:
            raise NotFoundError('Analysis run not found in this project.')
        return run

    def run(self, project_id, payload):
        document = self.repository.get(project_id)
        config = configuration(payload, document)
        report = readiness(document)
        state = report['scenarios'][config['scenario']]
        if state['status']=='NOT_READY':
            raise ValueError('NOT_READY: '+'; '.join(i['message'] for i in state['issues'] if i['severity']=='error'))
        bundle = build_bundle(document, config)
        config_hash = sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
        cache_key = sha256(json.dumps([project_id,bundle.data_version,bundle.planning_year,config['scenario'],
                                      config['objective'],config['algorithm'],config_hash]).encode()).hexdigest()
        run_id = 'run-'+uuid4().hex
        provenance = dict(bundle.provenance.copy(), project_id=project_id, data_version=bundle.data_version,
                          planning_year=bundle.planning_year, scenario=config['scenario'],algorithm=config['algorithm'],
                          seed=config['seed'],objective=config['objective'],config_hash=config_hash,
                          cache_key=cache_key,scientific_engine='thesis-engine / provider-boundary-1',
                          weights='Unchanged engine objective formulas', configuration=config)
        record = dict(id=run_id,project_id=project_id,data_version=bundle.data_version,configuration=config,
                      scenario=config['scenario'],algorithm=config['algorithm'],seed=config['seed'],
                      started_at=now(),completed_at=None,status='running',result=None,error=None,
                      provenance=provenance,warnings=[i['message'] for i in state['issues'] if i['severity']=='warning'])
        self.repository.update(project_id, lambda d: d.setdefault('runs',{}).__setitem__(run_id,record))
        try:
            record['result'] = self.executor(bundle)
            record['status'] = 'completed'
        except Exception as exc:
            # Persist failed runs; callers never receive a fabricated successful result.
            record['status']='failed'
            record['error']=str(exc)
        record['completed_at']=now()
        self.repository.update(project_id, lambda d: d['runs'].__setitem__(run_id,record))
        return record
