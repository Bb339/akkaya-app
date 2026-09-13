"""Synthetic projects verify isolation; their values are not agronomic references."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict
import json
import random
from pathlib import Path
import pytest
from flask import Flask
from kds.api import register_project_api
from kds.application.project_service import project_document
from kds.domain.project import Project
from kds.domain.water_budget import WaterBudget
from kds.domain.crop import Crop
from kds.domain.analysis_unit import AnalysisUnit
from kds.domain.economics import Economics
from kds.data.project_store import FileProjectStore
from kds.application.readiness import readiness
from kds.application.optimization import OptimizationApplicationService, configuration
from kds.adapters.project_science import build_bundle, data_hash
from kds.science.providers import ProjectDataProvider, using_provider
from kds.science.contract import FrozenValue
from kds.science.execution import execute


def example(project_id='sample-a', multiplier=1):
    project=Project(project_id,'Synthetic test',2025,10000,'m3')
    d=project_document(project,WaterBudget(project_id,10000,'m3','measured',source='synthetic test'))
    for i in (1,2):
        d['analysis_units'].append(asdict(AnalysisUnit(f'unit-{i}',project_id,f'P{i}',10,'ARPA',
            geometry={'type':'Point','coordinates':[34,38]})))
    for name in ('ARPA','NOHUT'):
        d['crops'].append(asdict(Crop(name.lower(),project_id,name,kc_initial=.4,kc_mid=1.,kc_end=.5,
            stage_initial_days=20,stage_development_days=30,stage_mid_days=40,stage_late_days=20)))
        d['economics'].append(asdict(Economics(project_id,name,2025,1.,1200.*multiplier,'TRY','synthetic test')))
    candidates=[dict(analysis_unit_id=u['external_id'],crop=c,water_requirement_m3_da=100. if c=='ARPA' else 150.,
                     profit_per_da=1200.*multiplier if c=='ARPA' else 1500.*multiplier,yield_ton_da=1.,
                     allowed=True,rotation_status='explicit-test-approval',suitability=1.)
                for u in d['analysis_units'] for c in ('ARPA','NOHUT')]
    d['scientific_inputs']=dict(candidates=candidates,
        unit_parameters={u['external_id']:dict(current_water_m3=1000.,current_profit=12000.*multiplier,soil_class='II',parcel_type='field') for u in d['analysis_units']},
        irrigation={c:dict(default='drip',recommended='drip',efficiency=.83) for c in ('ARPA','NOHUT')})
    return d


def request_body(scenario='S1'):
    return dict(scenario=scenario,algorithm='GA',seed=123,objective='water_saving',water_budget_ratio=1.,
                config=dict(popSize=8,generations=4,cxRate=.7,mutRate=.08))


def with_seasons(d):
    names=[c['name'] for c in d['crops']]; ids=[u['external_id'] for u in d['analysis_units']]
    year=d['project']['planning_year']; months=[f'{year}-{i:02}-01' for i in range(1,13)]
    e=d['scientific_inputs']; e['crop_families']={'ARPA':'poaceae','NOHUT':'fabaceae'}
    e['rotation_rules']=[dict(type='hard',from_family='*',to_family='same_family',penalty_weight=1.)]
    e['seasonal_resources']=dict(
        s1=[dict(parcel_id=uid,crop='NOHUT',year=year-1) for uid in ids],
        s2=[dict(parcel_id=uid,crop=c,year=year,season=s,area_da=10.,water_m3_calib_gross=1000.,profit_tl=12000.,
                 planting_date=f'{year}-03-01' if s=='primary' else f'{year}-08-01',
                 harvest_date=f'{year}-06-30' if s=='primary' else f'{year}-10-31',
                 yield_ton=10.,price_tl_ton=1500.,variable_cost_tl=3000.,irrig_efficiency=.83)
            for uid in ids for c in names for s in ('primary','secondary')],
        parcels=[dict(parcel_id=uid,district='test',land_capability_class='II') for uid in ids],
        reservoir=[dict(month=m,irrigation_m3_baseline=10000./12) for m in months],
        delivery=[dict(month=m,max_delivery_m3_assumed=10000.) for m in months],
        crop_params=[dict(crop=c,kc_ini=.4,kc_mid=1.,kc_end=.5) for c in names],
        monthly_climate=[dict(parcel_id=uid,month=m,et0_mm=100.,precip_mm=20.) for uid in ids for m in months],
        water_quality=[dict(month=m,ec_dS_m_assumed=.5) for m in months],
        soil_params=[dict(land_capability_class='II',source='test')],
        crop_suitability=[dict(crop=c,land_capability_class='II',suitability_score=1.) for c in names],
        irrigation_methods=[dict(method='drip',typical_total_efficiency=.83)])
    return d


@pytest.fixture
def repository(tmp_path):
    repo=FileProjectStore(tmp_path/'projects'); repo.create(example()); return repo


@pytest.fixture
def client(repository):
    app=Flask('analysis-tests'); app.config['TESTING']=True
    register_project_api(app,repository)
    return app.test_client()


def test_readiness_ready_and_distinct_seasons():
    report=readiness(example())
    assert report['scenarios']['S1']['status']=='READY'
    assert report['scenarios']['S2']['status']=='NOT_READY'
    assert readiness(with_seasons(example()))['scenarios']['S2']['status']=='READY'


def test_warning_is_not_a_missing_data_substitute():
    d=example();d['water_budget']['kind']='calculated_reference';d['analysis_units'][0]['geometry']=None
    assert readiness(d)['scenarios']['S1']['status']=='READY_WITH_WARNINGS'
    d['scientific_inputs']['candidates'].pop(0)
    assert readiness(d)['scenarios']['S1']['status']=='NOT_READY'


@pytest.mark.parametrize('section', ['analysis_units','crops','economics'])
def test_missing_data_prevents_execution(section,repository):
    repository.update('sample-a',lambda d:d.__setitem__(section,[]))
    service=OptimizationApplicationService(repository,lambda b:pytest.fail('Engine must not run'))
    with pytest.raises(ValueError,match='NOT_READY'):
        service.run('sample-a',request_body())
    assert not repository.get('sample-a').get('runs')


@pytest.mark.parametrize('field', ['current_water_m3','current_profit','soil_class'])
def test_missing_baseline_cannot_reach_area_multipliers(field):
    d=example();d['scientific_inputs']['unit_parameters']['P1'].pop(field)
    assert readiness(d)['scenarios']['S1']['status']=='NOT_READY'


def test_immutable_bundle_and_separate_execution_views():
    d=example();bundle=build_bundle(d,configuration(request_body(),d))
    with pytest.raises(FrozenInstanceError):bundle.project_id='other'
    provider=ProjectDataProvider(bundle)
    first=provider.read('units',None);first[0]['area_da']=999
    assert ProjectDataProvider(bundle).read('units',None)[0]['area_da']==10
    assert dict(bundle.resources)['units'].copy()[0]['area_da']==10
    with pytest.raises(ValueError,match='Missing scientific resource'):
        provider.read('not-present',lambda:pytest.fail('No legacy fallback'))
    assert not any(isinstance(v,Path) for v in vars(bundle).values())


def test_data_hash_and_configuration_include_scientific_changes():
    a=example();b=example('sample-b');assert data_hash(a)!=data_hash(b)
    previous=data_hash(a);a['runs']={'run-x':{'status':'running'}};assert data_hash(a)==previous
    a['scientific_inputs']['candidates'][0]['profit_per_da']+=1;assert data_hash(a)!=previous


def test_run_failure_is_persisted(repository):
    def fail(bundle):raise RuntimeError('explicit execution failure')
    service=OptimizationApplicationService(repository,fail)
    run=service.run('sample-a',request_body())
    assert run['status']=='failed' and run['result'] is None
    assert service.get('sample-a',run['id'])['error']=='explicit execution failure'


@pytest.mark.parametrize('changes',[{'seed':True},{'seed':-1},{'algorithm':'AUTO'},{'scenario':'S3'},
                                   {'objective':'invented'},{'config':{}},{'water_budget_ratio':0},
                                   {'selected_ids':['foreign-unit']}])
def test_invalid_configuration(changes):
    with pytest.raises(ValueError):configuration({**request_body(),**changes},example())


def test_minimum_page_contract(client):
    response=client.get('/projects');assert response.status_code==200
    for token in ('create-project','readiness','analysis-form','result','upload-form'):
        assert token.encode() in response.data
    for name in ('projects.js','api.js','imports.js','analysis.js','projects.css'):
        assert client.get('/projects/assets/'+name).status_code==200


def test_api_readiness_budget_and_bad_inputs(client):
    assert client.get('/api/v2/projects/sample-a/readiness').json['scenarios']['S1']['status']=='READY'
    assert client.post('/api/v2/projects/sample-a/analyses',json={}).status_code==400
    assert client.post('/api/v2/projects/sample-a/scientific-inputs',json={'candidates':[{'crop':[]}]}).status_code==400
    response=client.post('/api/v2/projects/sample-a/water-budget',json=dict(amount=11000,unit='m3',kind='measured',source='test'))
    assert response.status_code==200 and response.json['water_budget']['amount']==11000


def test_api_run_storage_and_cross_project_retrieval(client,repository):
    response=client.post('/api/v2/projects/sample-a/analyses',json=request_body())
    assert response.status_code==201, response.json
    run=response.json;assert run['result']['total_profit_tl']>0
    assert client.get('/api/v2/projects/sample-a/analyses/'+run['id']).json==run
    repository.create(example('sample-b'))
    assert client.get('/api/v2/projects/sample-b/analyses/'+run['id']).status_code==404


def test_explicit_generic_s2_uses_only_uploaded_crops():
    d=with_seasons(example());bundle=build_bundle(d,configuration(request_body('S2'),d))
    import app
    with using_provider(ProjectDataProvider(bundle)):
        crops,*_=app.build_candidate_matrix_two_season(app.load_parcels(),2025,'s2')
    assert set(crops)=={'NADAS','ARPA','NOHUT'}
    result=execute(bundle)
    assert result['algorithm']=='GA' and result['status']=='OK'


def test_sequential_projects_and_parent_rng_are_isolated():
    state=random.getstate()
    a,b=example(),example('sample-b',2)
    ba=build_bundle(a,configuration(request_body(),a));bb=build_bundle(b,configuration(request_body(),b))
    first=execute(ba);second=execute(bb);again=execute(ba)
    assert first==again and first['total_profit_tl']!=second['total_profit_tl']
    assert random.getstate()==state


def test_concurrent_project_processes_match_sequential():
    from concurrent.futures import ThreadPoolExecutor
    a,b=example(),example('sample-b',2)
    bundles=[build_bundle(d,configuration(request_body(),d)) for d in (a,b)]
    with ThreadPoolExecutor(2) as pool:
        results=list(pool.map(execute,bundles))
    assert results[0]==execute(bundles[0])
    assert results[1]==execute(bundles[1])


def test_sparse_candidates_are_not_regionally_fabricated():
    import app
    d=example();d['scientific_inputs']['candidates']=[r for r in d['scientific_inputs']['candidates'] if (r['analysis_unit_id'],r['crop'])!=('P1','NOHUT')]
    assert readiness(d)['scenarios']['S1']['status']=='READY'
    bundle=build_bundle(d,configuration(request_body(),d))
    with using_provider(ProjectDataProvider(bundle)):
        problem=app._matrix_build_problem(app.load_parcels(),'water_saving',1.,2025)
    p=next(p for p in problem['parcels'] if p['id']=='P1')
    assert all(o['name']=='ARPA' for o in p['options'])


def test_disallowed_candidate_is_not_an_engine_option():
    d=example();d['scientific_inputs']['candidates'][1]['allowed']=False
    bundle=build_bundle(d,configuration(request_body(),d))
    provider=ProjectDataProvider(bundle)
    rows=provider.read('candidate_options',None).to_dict('records')
    assert not any(r['parcel_id']=='P1' and r['candidate_crop']=='NOHUT' for r in rows)
    assert len(bundle.candidates)==4


def test_reference_readiness_resolves_source_whitespace_without_editing_catalog():
    import app
    from kds.adapters.akkaya_demo import build_demo
    document=build_demo(app.DATA_DIR)
    before=deepcopy(document['crops'])
    report=readiness(document)
    assert all(r['status']=='READY_WITH_WARNINGS' for r in report['scenarios'].values())
    assert len(document['crops'])==58 and document['crops']==before
