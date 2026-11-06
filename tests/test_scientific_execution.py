import json
import os
from copy import deepcopy
from pathlib import Path
import pytest
import app
from kds.adapters.akkaya_demo import build_demo
from kds.adapters.project_science import build_bundle
from kds.application.optimization import configuration
from kds.science.execution import execute, stable
from kds.science.providers import ProjectDataProvider, using_provider

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


def phase1_compatible(result, scenario):
    """Remove only the authorized Phase 2 diagnostic for frozen parity."""
    comparable = deepcopy(result)
    if scenario == 'S2':
        report = comparable['meta']['delivery_report']
        assert report['unit']=='m3/month' and report['period']=='calendar_month'
        assert len(report['months'])==12 and report['status'] in ('pass','violation')
        comparable['meta']['delivery_report']=None
    return comparable


def assert_orchard_full_area_policy(result, historical, bundle):
    """Keep the frozen, area-shrunk result as history and verify the new contract."""
    units = {str(unit['external_id']): unit for unit in bundle.analysis_units.copy()}
    orchard = units['P149']
    physical_area = float(orchard['area_da'])
    current_crop = app.canonical_crop_key(orchard['current_crop'])
    current = next(
        candidate for candidate in bundle.candidates
        if candidate.analysis_unit_id == 'P149'
        and app.canonical_crop_key(candidate.crop) == current_crop
    )
    candidate_row = current.metadata.copy()
    scenario_budget = float(candidate_row['quota_area_fair_per_da_m3'])
    independently_calculated_need = physical_area * float(current.water_requirement_m3_da)
    independently_calculated_gap = max(0.0, independently_calculated_need - scenario_budget)

    # The immutable fixture remains an explicit historical comparator: it used
    # the same orchard crop but silently reduced the planted area to the quota.
    historical_parcel = next(p for p in historical['parcels'] if p['id'] == 'P149')
    historical_crop = historical_parcel['result']['recommended'][0]
    assert app.canonical_crop_key(historical_crop['name']) == current_crop
    assert historical_crop['area_da'] < physical_area
    assert historical_crop['coverage_pct'] < 100.0
    assert historical_crop['totalWater'] == pytest.approx(scenario_budget)

    # The approved policy keeps the installed orchard's identity and physical
    # area, computes its full-area need, and rejects it when the quota is short.
    assert independently_calculated_need == pytest.approx(7760993.46)
    assert scenario_budget == pytest.approx(7124889.536775843)
    assert independently_calculated_gap == pytest.approx(636103.9232241577)
    diagnostic = next(d for d in result['diagnostic_units'] if d['analysis_unit_id'] == 'P149')
    assert diagnostic['physical_area_da'] == pytest.approx(physical_area)
    assert diagnostic['required_full_area_water_m3'] == pytest.approx(independently_calculated_need)
    assert diagnostic['scenario_budget_m3'] == pytest.approx(scenario_budget)
    assert diagnostic['budget_gap_m3'] == pytest.approx(independently_calculated_gap)
    assert diagnostic['orchard_locked'] is True

    assert result['status'] == 'OK'
    assert result['solution_status'] == 'no_feasible'
    assert result['recommendation_status'] == 'not_feasible'
    assert result['feasible'] is False and result['selectable'] is False
    assert result['meta']['no_feasible_parcel_ids'] == ['P149']
    assert result['total_water_m3'] is None
    assert result['total_profit_tl'] is None
    assert result['efficiency_tl_per_m3'] is None
    assert result['area_accounting']['proposed_planted_area_da'] is None
    assert result['water_accounting']['proposed_calculated_need_m3'] is None
    assert result['water_accounting']['calculated_need_reduction_m3'] is None
    assert result['water_accounting']['calculated_need_reduction_pct'] is None

    # Only the orchard is strict in the default partial-planting policy. Field
    # units retain candidates and their former partial-area behaviour.
    config = bundle.algorithm_configuration.copy()
    with using_provider(ProjectDataProvider(bundle)):
        selected = [p for p in app.load_parcels() if str(p.get('id')) in config['selected_ids']]
        problem = app._matrix_build_problem(
            selected, 'S1', 1.0, year=bundle.planning_year, options=config['options'])
    by_id = {parcel['id']: parcel for parcel in problem['parcels']}
    assert problem['area_policy'] == 'partial_planting'
    assert problem['no_feasible_parcel_ids'] == ['P149']
    assert by_id['P149']['strict_physical_area'] is True
    assert by_id['P149']['options'] == []
    for parcel_id in ('P1', 'P23'):
        assert by_id[parcel_id]['strict_physical_area'] is False
        assert by_id[parcel_id]['options']


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
    if scenario == 'S1':
        assert_orchard_full_area_policy(result, case['result'], bundle)
    else:
        assert_result(phase1_compatible(result,scenario),case['result'])


def test_legacy_seeded_reference(document):
    from tools.freeze_scientific_baseline import execute as reference
    case=json.loads((BASELINE/'s2_ga.json').read_text(encoding='utf8'))[0]
    result=stable(reference('S2','GA',case['seed'],case['selected_ids']))
    assert_result(phase1_compatible(result,'S2'),case['result'])


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
