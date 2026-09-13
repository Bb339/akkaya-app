"""Tier 2 / 3: full reference-project parity, excluded from normal collection."""
import json,multiprocessing,os,time,traceback
from pathlib import Path
import pytest
from kds.science.execution import stable,execute
from kds.adapters.project_science import build_bundle
from kds.application.optimization import configuration
from general_project_support import config
from test_scientific_execution import assert_result
pytestmark=pytest.mark.full_project


def legacy_worker(payload,sending):
    try:
        import app
        sending.send(('ok',stable(app.optimize([],payload['algorithm'],payload['objective'],1.,year=2024,options=payload['options']))))
    except Exception:sending.send(('error',traceback.format_exc()))
    finally:sending.close()


def legacy_execute(payload):
    context=multiprocessing.get_context('spawn');r,s=context.Pipe(False)
    process=context.Process(target=legacy_worker,args=(payload,s));process.start();s.close()
    try:
        assert r.poll(300),'Legacy full-project timeout'
        status,value=r.recv();assert status=='ok',value
        return value
    finally:
        r.close();process.join(2)
        if process.is_alive():process.terminate();process.join(5)


@pytest.mark.parametrize('seed',[123,456,789] if os.environ.get('KDS_NIGHTLY')=='1' else [123])
@pytest.mark.parametrize('scenario',['S1','S2'])
@pytest.mark.parametrize('algorithm',['GA','ACO','ABC'])
def test_full_project_parity(scenario,algorithm,seed):
    import app
    from kds.adapters.akkaya_demo import build_demo
    started=time.perf_counter();d=build_demo(app.DATA_DIR)
    options=configuration(config(scenario,algorithm,seed),d)
    expected=legacy_execute(options)
    actual=execute(build_bundle(d,options))
    assert len(d['analysis_units'])==179
    assert_result(actual,expected)
    output=os.environ.get('KDS_ACCEPTANCE_OUTPUT')
    if output:
        p=Path(output);p.mkdir(parents=True,exist_ok=True)
        (p/f'full-{scenario}-{algorithm}-{seed}.json').write_text(json.dumps(dict(scenario=scenario,algorithm=algorithm,seed=seed,units=179,
            matched=True,elapsed_seconds=time.perf_counter()-started,water=actual['total_water_m3'],profit=actual['total_profit_tl'],
            feasible=actual['feasible'],comparison='all deterministic raw output fields; rel=1e-10 abs=1e-7'),indent=2),encoding='utf8')
