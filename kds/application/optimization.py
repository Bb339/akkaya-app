"""Application orchestration without HTTP/UI or scientific formula duplication."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import uuid4
from dataclasses import asdict
from pathlib import Path
import subprocess
from kds.adapters.project_science import build_bundle, data_hash
from kds.application.readiness import readiness
from kds.data.repositories import NotFoundError
from kds.science.execution import execute
from kds.science.results import RESULT_CONTRACT_VERSION, present_stored_run, project_result, summarize
from kds.domain.analysis_run import AnalysisRun
from kds.domain.execution_profile import (
    ExecutionProfile, authority_label, execution_profile, result_classification,
)


def now():
    return datetime.now(timezone.utc).isoformat()


def configuration(payload, document):
    required = {'scenario','algorithm','seed','objective','water_budget_ratio','config'}
    if not isinstance(payload,dict) or not required <= payload.keys() or payload.keys() - (required | {'selected_ids','execution_profile'}):
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
    profile = execution_profile(payload.get('execution_profile', ExecutionProfile.REFERENCE_DEMO.value))
    return {**payload, 'execution_profile': profile.value, 'selected_ids':ids, 'options':options}


def engine_commit():
    root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(['git','rev-parse','HEAD'], cwd=root, text=True,
                               capture_output=True, check=False)
    return completed.stdout.strip() if completed.returncode == 0 else None


class OptimizationApplicationService:
    def __init__(self, repository, executor=execute):
        self.repository, self.executor = repository, executor

    def readiness(self, project_id):
        return readiness(self.repository.get(project_id))

    def get(self, project_id, run_id):
        document = self.repository.get(project_id)
        run = document.get('runs',{}).get(run_id)
        if run is None:
            raise NotFoundError('Analysis run not found in this project.')
        return present_stored_run(run, document)

    def preview(self, project_id, payload):
        document = self.repository.get(project_id)
        config = configuration(payload, document)
        profile = execution_profile(config['execution_profile'])
        report = readiness(document)
        if profile is ExecutionProfile.REFERENCE_DEMO:
            state = report['scenarios'][config['scenario']]
            return {
                'execution_profile': profile.value, 'result_authority_label': authority_label(profile, synthetic=False),
                'project_id': project_id, 'planning_year': document['project']['planning_year'],
                'ready': state['status'] != 'NOT_READY',
                'blocking_reasons': [i['message'] for i in state['issues'] if i['severity']=='error'],
                'warnings': [i['message'] for i in state['issues'] if i['severity']=='warning'],
                'datasets': [], 'candidate_source': {'source': 'accepted reference/project-explicit demo path',
                    'candidate_count': report['scientific_data']['raw_candidate_count'],
                    'analysis_unit_count': report['counts']['analysis_units']},
                'algorithm': config['algorithm'], 'objective': config['objective'], 'scenario': config['scenario'],
            }
        from kds.adapters.institutional import verified_execution_plan
        try:
            plan = verified_execution_plan(document, config)
            plan['result_authority_label'] = authority_label(profile, synthetic=plan['synthetic'])
            return plan
        except ValueError as exc:
            return {
                'execution_profile': profile.value, 'project_id': project_id,
                'planning_year': document['project']['planning_year'], 'ready': False,
                'blocking_reasons': [str(exc)], 'warnings': [], 'datasets': [],
                'algorithm': config['algorithm'], 'objective': config['objective'], 'scenario': config['scenario'],
            }

    def run(self, project_id, payload):
        document = self.repository.get(project_id)
        config = configuration(payload, document)
        profile = execution_profile(config['execution_profile'])
        report = readiness(document)
        state = report['scenarios'][config['scenario']]
        if profile is ExecutionProfile.REFERENCE_DEMO:
            if state['status']=='NOT_READY':
                raise ValueError('NOT_READY: '+'; '.join(i['message'] for i in state['issues'] if i['severity']=='error'))
            bundle = build_bundle(document, config)
            execution_plan = self.preview(project_id, payload)
            effective_config = config
            synthetic = False
        else:
            from kds.adapters.institutional import build_verified_bundle
            bundle, effective_config, execution_plan = build_verified_bundle(document, config)
            synthetic = bool(execution_plan['synthetic'])
        config_hash = sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
        cache_key = sha256(json.dumps([project_id,bundle.data_version,bundle.planning_year,config['scenario'],
                                      config['objective'],config['algorithm'],config_hash]).encode()).hexdigest()
        run_id = 'run-'+uuid4().hex
        input_snapshot = {
            'execution_profile': profile.value, 'planning_year': bundle.planning_year,
            'project_id': project_id, 'input_datasets': deepcopy_json(execution_plan.get('datasets', [])),
            'candidate_source': deepcopy_json(execution_plan.get('candidate_source', {})),
            'engine_commit': engine_commit(), 'algorithm': config['algorithm'], 'seed': config['seed'],
            'objective': config['objective'], 'scenario': config['scenario'],
            'created_at': now(), 'readiness_snapshot': deepcopy_json(execution_plan),
            'result_classification': result_classification(profile, synthetic=synthetic),
        }
        provenance = dict(bundle.provenance.copy(), project_id=project_id, data_version=bundle.data_version,
                          planning_year=bundle.planning_year, scenario=config['scenario'],algorithm=config['algorithm'],
                          seed=config['seed'],objective=config['objective'],config_hash=config_hash,
                          cache_key=cache_key,scientific_engine='thesis-engine / provider-boundary-1',
                          weights='Unchanged engine objective formulas', configuration=effective_config,
                          execution_profile=profile.value,
                          result_authority_label=authority_label(profile, synthetic=synthetic),
                          input_snapshot=input_snapshot)
        record = asdict(AnalysisRun(id=run_id,project_id=project_id,data_version=bundle.data_version,configuration=config,
                      scenario=config['scenario'],algorithm=config['algorithm'],seed=config['seed'],
                      execution_profile=profile.value,
                      result_authority_label=authority_label(profile, synthetic=synthetic),
                      started_at=now(),completed_at=None,status='running',result=None,error=None,
                      provenance=provenance,warnings=[i['message'] for i in state['issues'] if i['severity']=='warning']))
        provenance=record['provenance']
        if config['scenario']=='S2':
            provenance['result_contract_version']=RESULT_CONTRACT_VERSION
        provenance['run_timestamp']=record['started_at']
        provenance['water_budget']=bundle.water_budget.copy()
        provenance['project_name']=document['project']['name']
        provenance['data_source_notes']=document['project'].get('data_source_notes','')
        self.repository.update(project_id, lambda d: d.setdefault('runs',{}).__setitem__(run_id,record))
        try:
            engine_result = self.executor(bundle)
            record['result'] = project_result(engine_result, effective_config, document['analysis_units'])
            record['result'].update(
                execution_profile=profile.value, project_id=project_id, planning_year=bundle.planning_year,
                scenario=config['scenario'], algorithm=config['algorithm'], seed=config['seed'],
                objective=config['objective'], result_authority_label=authority_label(profile, synthetic=synthetic),
                classification=result_classification(profile, synthetic=synthetic),
                input_provenance=deepcopy_json(input_snapshot),
            )
            record['summary'] = summarize(record['result'],bundle)
            provenance['effective_run_parameters']=record['summary']['effective_run_parameters']
            if record['result'].get('feasible') is False:
                record['warnings'].append('Motorun ürettiği plan mevcut bütçe/kısıtlara uygun değil; tamamlanan çalışma uygulanabilir plan anlamına gelmez.')
            effective=record['summary']['effective_run_parameters']
            changed=[k for k,v in config['config'].items() if k in effective and effective[k]!=v]
            if changed:
                record['warnings'].append('Motorun mevcut parametre sınırları uygulandı: '+', '.join(changed)+'. Etkin değerler provenance içinde kayıtlıdır.')
            record['status'] = 'completed'
        except Exception as exc:
            # Persist failed runs; callers never receive a fabricated successful result.
            record['status']='failed'
            record['error']=str(exc)
        record['completed_at']=now()
        def finish(d):
            d['runs'][run_id] = record
            if record['status'] == 'completed':
                d['analysis_state'] = {'requires_reanalysis': False, 'latest_run_id': run_id,
                                       'resolved_data_revision': d['data_revision'],
                                       'resolved_at': record['completed_at']}
        self.repository.update(project_id, finish)
        return record


def deepcopy_json(value):
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
