import json
import os
from pathlib import Path
import pytest
import app
from kds.adapters.akkaya_demo import build_demo
from kds.adapters.project_science import build_bundle
from kds.application.optimization import configuration
from kds.science.execution import execute, stable

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT/'tests/fixtures/scientific_baseline'
pytestmark = pytest.mark.scientific_regression


def assert_result(actual, expected, path='result'):
    if isinstance(expected,dict):
        assert actual.keys()==expected.keys(), path
        for key in expected:
            assert_result(actual[key], expected[key], path+'.'+key)
    elif isinstance(expected,list):
        assert len(actual)==len(expected), path
        for i,(a,e) in enumerate(zip(actual,expected)):
            assert_result(a,e,f'{path}[{i}]')
    elif isinstance(expected,float):
        assert actual==pytest.approx(expected,rel=1e-10,abs=1e-7), path
    else:
        assert actual==expected, path


@pytest.fixture(scope='module')
def document():
    return build_demo(app.DATA_DIR)


@pytest.mark.parametrize('scenario', ['S1','S2'])
@pytest.mark.parametrize('algorithm', ['GA','ACO','ABC'])
@pytest.mark.parametrize('index', [0,1,2] if os.environ.get('KDS_EXTENDED')=='1' else [0])
def test_project_seeded_reference(document, scenario, algorithm, index):
    case=json.loads((BASELINE/f'{scenario.lower()}_{algorithm.lower()}.json').read_text(encoding='utf8'))[index]
    metadata=json.loads((BASELINE/'baseline_metadata.json').read_text(encoding='utf8'))
    keys={'GA':['popSize','generations','cxRate','mutRate'], 'ACO':['ants','iterations','rho','q'],
          'ABC':['foodSources','cycles','limit']}[algorithm]
    payload=dict(scenario=scenario, algorithm=algorithm, seed=case['seed'], objective='water_saving',
                 water_budget_ratio=1., selected_ids=case['selected_ids'],
                 config={k:metadata['configuration'][k] for k in keys})
    bundle=build_bundle(document,configuration(payload,document))
    assert len(bundle.candidates)==6859
    assert sum(c.quota_compatible for c in bundle.candidates)==3673
    result=execute(bundle)
    assert_result(result,case['result'])


def test_legacy_seeded_reference(document):
    from tools.freeze_scientific_baseline import execute as reference
    case=json.loads((BASELINE/'s2_ga.json').read_text(encoding='utf8'))[0]
    assert_result(stable(reference('S2','GA',case['seed'],case['selected_ids'])),case['result'])


def test_reference_preparation_preserves_serving_process_state(document):
    import pickle
    import random
    import numpy as np
    before=pickle.dumps(app._cache)
    rng=random.getstate();numpy_state=pickle.dumps(np.random.get_state())
    build_bundle(document,configuration(dict(scenario='S1',algorithm='GA',seed=123,objective='water_saving',
        water_budget_ratio=1.,config=dict(popSize=12,generations=10,cxRate=.7,mutRate=.08)),document))
    assert pickle.dumps(app._cache)==before
    assert random.getstate()==rng and pickle.dumps(np.random.get_state())==numpy_state
