"""Independent 24-unit project, always created using the public import API."""
from copy import deepcopy
import json
import pytest
from general_project_support import FIXTURE,client_for,import_project,upload,config,guarded_execute
from kds.application.readiness import readiness
from kds.application.optimization import OptimizationApplicationService

@pytest.fixture(scope='module')
def imported(tmp_path_factory):
    client,repo=client_for(tmp_path_factory.mktemp('general-public')/'projects')
    pid=import_project(client)
    return client,repo,pid


def test_public_pipeline_and_synthetic_sources(imported):
    client,repo,pid=imported;d=repo.get(pid)
    assert len(d['analysis_units'])==24 and len(d['crops'])==8
    assert len({u['settlement'] for u in d['analysis_units']})==3
    assert all(u['external_id'].startswith('GX-') for u in d['analysis_units'])
    assert all(c['id'].startswith('r-') and c['project_id']==pid for c in d['crops'])
    assert {b['status'] for b in d['imports'].values()}=={'applied'}
    assert len(d['imports'])==8
    for b in d['imports'].values():
        states={h['status'] for h in b['history']}
        assert {'uploaded','parsed','ready','confirmed','applied'}<=states
    assert d['water_budget']['source']=='synthetic_test_fixture'
    assert all(c['source']=='synthetic_test_fixture' for c in d['crops']+d['economics']+d['scientific_inputs']['candidates'])
    assert all(u['metadata']['unmapped']['source']=='synthetic_test_fixture' for u in d['analysis_units'])
    assert not d['metadata'].get('source_version')
    assert any(c['perennial'] for c in d['crops']) and any(not c['perennial'] for c in d['crops'])


def test_readiness_geometry_and_season_distinction(imported):
    _,repo,pid=imported;d=repo.get(pid)
    assert all(s['status']=='READY_WITH_WARNINGS' for s in readiness(d)['scenarios'].values())
    for u in d['analysis_units']:u['geometry']={'type':'Point','coordinates':[28,39]}
    assert all(s['status']=='READY' for s in readiness(d)['scenarios'].values())
    d['scientific_inputs'].pop('seasonal_resources');d['scientific_inputs'].pop('rotation_rules')
    assert readiness(d)['scenarios']['S1']['status']=='READY'
    assert readiness(d)['scenarios']['S2']['status']=='NOT_READY'


@pytest.mark.parametrize('missing',['economics','kc','budget','candidates','water','scientific_inputs','rotation','seasons'])
def test_missing_science_blocks_without_legacy(imported,missing):
    _,repo,pid=imported;d=repo.get(pid)
    if missing=='economics':d['economics']=[]
    elif missing=='kc':d['crops'][0]['kc_mid']=None
    elif missing=='budget':d['water_budget']['amount']=0
    elif missing=='candidates':d['scientific_inputs']['candidates']=[]
    elif missing=='water':d['scientific_inputs']['candidates'][0].pop('water_requirement_m3_da')
    elif missing=='scientific_inputs':d['scientific_inputs']={}
    elif missing=='rotation':d['scientific_inputs'].pop('rotation_rules')
    else:d['scientific_inputs'].pop('seasonal_resources')
    class Snapshot:
        def get(self,key):return d
    service=OptimizationApplicationService(Snapshot(),lambda bundle:pytest.fail('NOT_READY reached execution'))
    with pytest.raises(ValueError,match='NOT_READY'):service.run(pid,config('S2' if missing in ('rotation','seasons') else 'S1'))


@pytest.mark.general_execution
@pytest.mark.parametrize('scenario',['S1','S2'])
@pytest.mark.parametrize('algorithm',['GA','ACO','ABC'])
def test_general_execution_no_reference_and_repeatable(imported,scenario,algorithm):
    _,repo,pid=imported;d=repo.get(pid)
    first=guarded_execute(d,config(scenario,algorithm));second=guarded_execute(d,config(scenario,algorithm))
    assert first==second
    assert first['attempts']==[] and first['candidates']==192 and first['area']==sum(u['area_da'] for u in d['analysis_units'])
    result=first['result'];assert result['details'] and isinstance(result['feasible'],bool)
    for row in result['details']:assert row['parcelId'].startswith('GX-')
    forbidden={'akkaya','niğde','bor','sazlıca','bahçeli','kemerhisar','kaynarca','combined_parcel_candidate_matrix_2024.csv'}
    def walk(value):
        if isinstance(value,dict):
            for v in value.values():walk(v)
        elif isinstance(value,list):
            for v in value:walk(v)
        elif isinstance(value,str):assert value.casefold() not in forbidden
    walk(result)
    assert len(d['analysis_units'])!=179 and first['area']!=134919 and d['water_budget']['amount']!=100700080.81
    import os
    from pathlib import Path
    folder=os.environ.get('KDS_GENERAL_ACCEPTANCE_OUTPUT')
    if folder:
        out=Path(folder);out.mkdir(parents=True,exist_ok=True)
        (out/f'general-{scenario}-{algorithm}.json').write_text(json.dumps(dict(scenario=scenario,algorithm=algorithm,seed=2468,units=24,candidates=192,
            source='synthetic_test_fixture',reproducible=True,reference_access_attempts=first['attempts'],feasible=result['feasible'],
            water=result['total_water_m3'],profit=result['total_profit_tl']),indent=2),encoding='utf8')


def test_negative_economics_preserved_public_import(tmp_path):
    client,repo=client_for(tmp_path/'projects');pid=import_project(client,seasons=False,geometry=None)
    upload(client,pid,'economics','economics_negative.csv')
    assert min(e['net_profit_per_da'] for e in repo.get(pid)['economics'])==-50.


def test_history_and_budget_provenance(imported):
    client,repo,pid=imported;root=f'/api/v2/projects/{pid}'
    response=client.post(root+'/analyses',json=config());assert response.status_code==201,response.json
    run=response.json;assert run['provenance']['water_budget']['kind']=='scenario'
    assert run['provenance']['data_source_notes']=='synthetic_test_fixture'
    listed=client.get(root+'/analyses?limit=1').json
    assert listed['items'][0]['id']==run['id'] and 'result' not in listed['items'][0]
    assert client.get(root+'/analyses/'+run['id']).json==run
    changed=client.post(root+'/water-budget',json=dict(amount=120000,unit='m3',kind='measured',source='synthetic_test_fixture'))
    assert changed.status_code==200
    assert client.get(root+'/analyses/'+run['id']).json['provenance']['water_budget']['kind']=='scenario'
    client.post(root+'/water-budget',json=dict(amount=120000,unit='m3',kind='scenario',source='synthetic_test_fixture'))
    assert client.get(root+'/analyses?limit=0').status_code==400
    assert client.get('/api/v2/projects/unknown/analyses/'+run['id']).status_code==404
    overview=client.get(root+'/overview').json
    assert overview['synthetic'] and overview['last_run']['id']==run['id'] and overview['last_import_at']
    assert overview['candidate_units']==24 and overview['import_status']['geometries']=='Warning'

@pytest.mark.general_execution
def test_reference_and_general_sequential_and_concurrent(imported):
    from concurrent.futures import ThreadPoolExecutor
    from kds.adapters.akkaya_demo import build_demo
    from kds.adapters.project_science import build_bundle
    from kds.application.optimization import configuration
    from kds.science.execution import execute
    import app
    _,repo,pid=imported;general=repo.get(pid);reference=build_demo(app.DATA_DIR)
    ref_options=config();ref_options['selected_ids']=['P1','P23','P149']
    bundles=[build_bundle(d,configuration(c,d)) for d,c in [(reference,ref_options),(general,config())]]
    sequential=[execute(bundle) for bundle in bundles]
    with ThreadPoolExecutor(2) as pool:concurrent=list(pool.map(execute,bundles))
    assert concurrent==sequential
    assert all(r['parcelId'].startswith('GX-') for r in concurrent[1]['details'])
    assert not any(r['parcelId'].startswith('GX-') for r in concurrent[0]['details'])


def test_invalid_scientific_import_is_atomic(imported):
    import io
    client,repo,pid=imported;before=repo.get(pid);url=f'/api/v2/projects/{pid}/imports'
    content=b'section,record_id,field,value_type,value,source\nunit_parameters,GX-001,current_water_m3,number,NaN,synthetic_test_fixture\n'
    response=client.post(url,data=dict(data_type='scientific_inputs',file=(io.BytesIO(content),'invalid-science.csv')),content_type='multipart/form-data')
    assert response.status_code==201 and response.json['status']=='invalid'
    refused=client.post(url+'/'+response.json['id']+'/confirm',json=dict(confirm=True,acknowledge_warnings=True))
    assert refused.status_code==409
    after=repo.get(pid)
    assert before['scientific_inputs']==after['scientific_inputs'] and before['data_revision']==after['data_revision']
    assert client.get(f'/api/v2/projects/{pid}/overview').json['import_status']['scientific_inputs']=='Warning'


def test_uploaded_status_does_not_claim_active_data(tmp_path):
    import io
    client,repo=client_for(tmp_path/'projects')
    project=json.loads((FIXTURE/'project.json').read_text());client.post('/api/v2/projects',json=project)
    root='/api/v2/projects/'+project['id']
    response=client.post(root+'/imports',data=dict(data_type='crops',file=(io.BytesIO((FIXTURE/'crops.xlsx').read_bytes()),'crops.xlsx')),content_type='multipart/form-data')
    assert response.status_code==201
    assert repo.get(project['id'])['crops']==[]
    assert client.get(root+'/overview').json['import_status']['crops']=='Uploaded'


def test_failed_history_preserves_missing_metrics(imported):
    client,repo,pid=imported
    def failure(bundle):raise RuntimeError('intentional synthetic failure')
    failed=OptimizationApplicationService(repo,failure).run(pid,config())
    assert failed['status']=='failed'
    rows=client.get(f'/api/v2/projects/{pid}/analyses').json['items']
    row=next(r for r in rows if r['id']==failed['id'])
    assert all(row[k] is None for k in ('feasible','water','profit','efficiency','score'))
    page=client.get(f'/api/v2/projects/{pid}/analyses?offset=1&limit=1').json
    assert len(page['items'])==1
