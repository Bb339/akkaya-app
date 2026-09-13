"""Public-import helpers and subprocess guards for synthetic acceptance only."""
import io,json,multiprocessing,traceback
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
from flask import Flask
from kds.api import register_project_api
from kds.data.project_store import FileProjectStore
FIXTURE=Path(__file__).parent/'fixtures/general_project'
ROOT=Path(__file__).resolve().parents[1]


def client_for(path):
    repository=FileProjectStore(path)
    application=Flask('general-acceptance');application.config['TESTING']=True
    register_project_api(application,repository)
    return application.test_client(),repository


def upload(client,pid,kind,filename,content=None):
    content=(FIXTURE/filename).read_bytes() if content is None else content
    root=f'/api/v2/projects/{pid}/imports'
    response=client.post(root,data=dict(data_type=kind,file=(io.BytesIO(content),filename)),content_type='multipart/form-data')
    assert response.status_code==201,response.json
    batch=response.json
    mapped=client.post(root+'/'+batch['id']+'/mapping',json={'mapping':batch['suggested_mapping']})
    assert mapped.status_code==200 and mapped.json['status']=='ready',mapped.json
    before=client.get(root+'/'+batch['id']).json
    assert before['normalized_preview'] and before['status']=='ready'
    result=client.post(root+'/'+batch['id']+'/confirm',json=dict(confirm=True,acknowledge_warnings=True))
    assert result.status_code==200 and result.json['status']=='applied',result.json
    return result.json


def import_project(client,pid='synthetic-general',seasons=True,geometry='partial'):
    project=json.loads((FIXTURE/'project.json').read_text())
    project['id']=pid
    response=client.post('/api/v2/projects',json=project);assert response.status_code==201,response.json
    for kind,filename in [('crops','crops.xlsx'),('analysis_units','analysis_units.csv'),('economics','economics.csv'),('water_budget','water_budget.csv'),('candidates','candidates.csv'),('scientific_inputs','scientific_s1.csv')]:
        upload(client,pid,kind,filename)
    if seasons:upload(client,pid,'scientific_inputs','scientific_s2.csv')
    if geometry:upload(client,pid,'geometries',f'geometry_{geometry}.geojson')
    return pid


def config(scenario='S1',algorithm='GA',seed=2468):
    params={'GA':dict(popSize=12,generations=10,cxRate=.7,mutRate=.08),
            'ACO':dict(ants=10,iterations=10,rho=.25,q=1.),'ABC':dict(foodSources=10,cycles=10,limit=4)}
    return dict(scenario=scenario,algorithm=algorithm,seed=seed,objective='water_saving',water_budget_ratio=1.,config=params[algorithm])


def _guarded_worker(document,payload,sending):
    attempts=[]
    try:
        import builtins,io
        original_open=builtins.open;original_io_open=io.open
        def guarded(original):
            def opening(file,*args,**kwargs):
                if isinstance(file,(str,bytes,Path)) and Path(file).resolve().is_relative_to(ROOT/'data'):
                    attempts.append(str(file));raise AssertionError('Reference data access denied: '+str(file))
                return original(file,*args,**kwargs)
            return opening
        with ExitStack() as stack:
            stack.enter_context(patch('builtins.open',guarded(original_open)))
            stack.enter_context(patch('io.open',guarded(original_io_open)))
            import app
            from kds.science.providers import LegacyReferenceProvider,ProjectDataProvider,using_provider
            from kds.adapters import scientific_reference,akkaya_demo
            def denied(*args,**kwargs):
                attempts.append('legacy-provider-or-adapter');raise AssertionError('Legacy provider/adapter is forbidden')
            for target,name in [(LegacyReferenceProvider,'read'),(scientific_reference,'snapshot'),(scientific_reference,'read_optional'),(akkaya_demo,'build_demo')]:stack.enter_context(patch.object(target,name,denied))
            from kds.application.readiness import readiness
            from kds.application.optimization import configuration
            from kds.adapters.project_science import build_bundle
            from kds.science.execution import stable
            report=readiness(document)
            assert report['scenarios'][payload['scenario']]['status']!='NOT_READY',report
            bundle=build_bundle(document,configuration(payload,document))
            options=bundle.algorithm_configuration.copy()
            with using_provider(ProjectDataProvider(bundle)):
                result=stable(app.optimize([],payload['algorithm'],payload['objective'],1.,year=2025,options=options['options']))
            assert not attempts,attempts
            sending.send(dict(result=result,attempts=attempts,project_id=bundle.project_id,area=sum(u['area_da'] for u in bundle.analysis_units.copy()),candidates=len(bundle.candidates)))
    except Exception:sending.send(dict(error=traceback.format_exc(),attempts=attempts))
    finally:sending.close()


def guarded_execute(document,payload):
    context=multiprocessing.get_context('spawn');receiving,sending=context.Pipe(False)
    process=context.Process(target=_guarded_worker,args=(document,payload,sending));process.start();sending.close()
    try:
        assert receiving.poll(180),'Synthetic acceptance timed out'
        result=receiving.recv();assert 'error' not in result,result
        return result
    finally:
        receiving.close();process.join(2)
        if process.is_alive():process.terminate();process.join(5)
