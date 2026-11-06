"""Package 1 regressions: synthetic inputs, injected failures, temporary stores only."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import subprocess

import pytest
import app
from flask import Flask
from kds.api import register_project_api
from kds.data.project_store import FileProjectStore
from kds.application.optimization import OptimizationApplicationService, configuration
from kds.application.readiness import readiness
from kds.adapters.project_science import build_bundle
from kds.science.providers import ProjectDataProvider, LegacyReferenceProvider, using_provider
from kds.science.execution import execute
from kds.application.result_presentation import present_run_for_ui
from test_analysis_workflow import example, request_body
from test_institutional_demo_phase1 import institutional as _institutional_fixture, execution_payload


@pytest.fixture(scope='module')
def institutional_template(tmp_path_factory):
    _, repo, pid = _institutional_fixture.__wrapped__(tmp_path_factory.mktemp('synthetic-inputs'))
    return repo.get(pid)


@pytest.fixture
def institutional(institutional_template, tmp_path):
    repo = FileProjectStore(tmp_path / 'projects')
    document = deepcopy(institutional_template)
    repo.create(document)
    application = Flask('package1-tests')
    application.config['TESTING'] = True
    register_project_api(application, repo)
    return application.test_client(), repo, document['project']['id']


@pytest.fixture(autouse=True)
def isolated_sources(monkeypatch, tmp_path):
    monkeypatch.setattr(app, 'DATA_DIR', tmp_path / 'no-reference-data')
    monkeypatch.setattr(app, '_cache', {})
    def forbidden(*args):
        pytest.fail('PROJECT_DATA must not consult the reference provider')
    monkeypatch.setattr(LegacyReferenceProvider, 'read', forbidden)


def bundle_for(algorithm='GA'):
    document = example()
    payload = request_body()
    payload['algorithm'] = algorithm
    payload['config'] = {
        'GA': dict(popSize=8, generations=4, cxRate=.7, mutRate=.08),
        'ACO': dict(ants=4, iterations=3, rho=.25, q=1),
        'ABC': dict(foodSources=4, cycles=3, limit=2),
    }[algorithm]
    return build_bundle(document, configuration(payload, document))


def run_in_process(bundle):
    config = bundle.algorithm_configuration.copy()
    with using_provider(ProjectDataProvider(bundle)):
        return app.optimize(config['selected_ids'], config['algorithm'], config['objective'],
                            config['water_budget_ratio'], bundle.planning_year, config['options'])


@pytest.mark.parametrize('failure', ['load', 'build'])
def test_s1_failure_never_switches_engine(monkeypatch, failure, caplog):
    bundle = bundle_for()
    def broken(*args, **kwargs):
        raise RuntimeError('controlled-private-detail')
    if failure == 'load':
        monkeypatch.setattr(app, 'load_matrix_candidates', broken)
    else:
        monkeypatch.setattr(app, '_matrix_build_problem', broken)
    monkeypatch.setattr(app, 'build_candidate_matrix', lambda *a, **k: pytest.fail('legacy engine called'))
    with pytest.raises(app.MatrixOptimizationError) as error:
        run_in_process(bundle)
    assert 'controlled-private-detail' not in str(error.value)
    assert 'S1 matrix execution failed' in caplog.text
    assert 'controlled-private-detail' in caplog.text


@pytest.mark.parametrize('candidate_value', [None, app.pd.DataFrame()])
def test_missing_candidate_data_is_validation_error_without_fallback(monkeypatch, candidate_value):
    bundle = bundle_for()
    monkeypatch.setattr(app, 'load_matrix_candidates', lambda: candidate_value)
    monkeypatch.setattr(app, 'build_candidate_matrix', lambda *a, **k: pytest.fail('legacy engine called'))
    with pytest.raises(app.CandidateDataError) as error:
        run_in_process(bundle)
    assert str(error.value) == app.CandidateDataError.public_message


def test_invalid_candidate_schema_is_not_reported_as_technical_failure(monkeypatch):
    bundle = bundle_for()
    monkeypatch.setattr(app, 'load_matrix_candidates', lambda: app.pd.DataFrame({
        'parcel_id': ['unit-1'], 'candidate_crop': ['ARPA'], 'area_da': [10.],
        'water_m3_da': [100.],
    }))
    monkeypatch.setattr(app, 'build_candidate_matrix', lambda *a, **k: pytest.fail('legacy engine called'))
    with pytest.raises(app.CandidateDataError):
        run_in_process(bundle)


def test_valid_candidates_with_zero_quota_return_explicit_no_feasible(monkeypatch):
    bundle = bundle_for()
    candidates = app.pd.DataFrame([
        {
            'parcel_id': unit_id, 'candidate_crop': crop, 'candidate_crop_id': crop,
            'current_crop': 'ARPA', 'area_da': 10., 'water_m3_da': 100.,
            'profit_tl_da': 1200., 'yield_ton_da': 1., 'current_quota_m3': 0.,
        }
        for unit_id in ('P1', 'P2') for crop in ('ARPA', 'NOHUT')
    ])
    monkeypatch.setattr(app, 'load_matrix_candidates', lambda: candidates.copy())
    monkeypatch.setattr(app, 'build_candidate_matrix', lambda *a, **k: pytest.fail('legacy engine called'))
    result = run_in_process(bundle)
    assert result['status'] == 'OK'
    assert result['solution_status'] == 'no_feasible'
    assert result['recommendation_status'] == 'not_feasible'
    assert result['feasible'] is False and result['selectable'] is False
    assert result['details'] == []
    assert 'uygulanabilir aday çözüm bulunamadı' in result['message']


def test_v1_candidate_validation_and_no_feasible_contract(monkeypatch):
    bundle = bundle_for()
    monkeypatch.setattr(app, '_optimization_repeat_selection', lambda *a, **kw: {'selected_repeat_count': 1})
    monkeypatch.setattr(app, 'build_candidate_matrix', lambda *a, **k: pytest.fail('legacy engine called'))
    with using_provider(ProjectDataProvider(bundle)):
        monkeypatch.setattr(app, 'load_matrix_candidates', lambda: app.pd.DataFrame())
        invalid = app.app.test_client().post('/api/optimize', json={'algorithm': 'GA'})
    assert invalid.status_code == 400
    assert invalid.json['error'] == 'invalid_candidate_data'

    candidates = app.pd.DataFrame([
        {
            'parcel_id': unit_id, 'candidate_crop': 'ARPA', 'candidate_crop_id': 'ARPA',
            'current_crop': 'ARPA', 'area_da': 10., 'water_m3_da': 100.,
            'profit_tl_da': 1200., 'yield_ton_da': 1., 'current_quota_m3': 0.,
        }
        for unit_id in ('P1', 'P2')
    ])
    with using_provider(ProjectDataProvider(bundle)):
        monkeypatch.setattr(app, 'load_matrix_candidates', lambda: candidates.copy())
        config = bundle.algorithm_configuration.copy()
        raw = app.optimize(config['selected_ids'], config['algorithm'], config['objective'],
                           config['water_budget_ratio'], bundle.planning_year, config['options'])
        standardized = app._standardize_optimize_payload(
            raw, config['selected_ids'], config['algorithm'], config['objective'],
            config['water_budget_ratio'], bundle.planning_year, config['options'])
        assert standardized['selected_plan']['status'] == 'no_feasible_plan'
        no_feasible = app.app.test_client().post('/api/optimize', json={'algorithm': 'GA'})
    assert no_feasible.status_code == 200, no_feasible.json
    assert no_feasible.json['status'] == 'OK'
    assert no_feasible.json['solution_status'] == 'no_feasible'
    assert no_feasible.json['selected_plan']['status'] == 'no_feasible_plan'
    assert no_feasible.json['selected_plan']['recommendation_status'] == 'not_feasible'
    assert no_feasible.json['selected_plan']['selectable'] is False


def test_v1_matrix_failure_aborts_repeats(monkeypatch):
    bundle = bundle_for()
    calls = []
    def broken(*args, **kwargs):
        calls.append(1)
        raise RuntimeError('controlled-private-detail')
    monkeypatch.setattr(app, '_matrix_build_problem', broken)
    monkeypatch.setattr(app, 'build_candidate_matrix', lambda *a, **k: pytest.fail('legacy engine called'))
    monkeypatch.setattr(app, '_optimization_repeat_selection', lambda **kw: {'selected_repeat_count': 2})
    with using_provider(ProjectDataProvider(bundle)):
        response = app.app.test_client().post('/api/optimize', json={'algorithm': 'GA'})
    assert response.status_code == 500
    assert response.json['status'] == 'ERROR'
    assert 'controlled-private-detail' not in response.get_data(as_text=True)
    assert len(calls) == 1


@pytest.mark.parametrize('value', [0, -1, 'bad', '', float('nan'), float('inf'), True, [], {}])
def test_v1_invalid_budget_is_not_defaulted(value):
    response = app.app.test_client().post('/api/optimize', json={'waterBudgetRatio': value})
    assert response.status_code == 400
    assert response.json['status'] == 'ERROR'


@pytest.mark.parametrize('endpoint', ['/api/validation_report', '/api/benchmark', '/api/run_count_calibration'])
def test_other_v1_budget_entrypoints_reject_zero(endpoint):
    response = app.app.test_client().post(endpoint, json={'waterBudgetRatio': 0})
    assert response.status_code == 400
    assert response.json['status'] == 'ERROR'


@pytest.mark.parametrize('value', [0, -1, 'bad', float('nan'), float('inf')])
def test_engine_budget_validation(value):
    with pytest.raises(app.BudgetRatioError):
        app.optimize([], 'GA', 'water_saving', value)
    bundle = bundle_for()
    with using_provider(ProjectDataProvider(bundle)), pytest.raises(app.BudgetRatioError):
        app._matrix_build_problem(app.load_parcels(), 'water_saving', value)


@pytest.mark.parametrize('value,expected', [(None, 1.), (.5, .5), ('0.5', .5), (11, 11.)])
def test_v1_budget_default_and_positive_range(value, expected):
    bundle = bundle_for()
    with using_provider(ProjectDataProvider(bundle)):
        problem = app._matrix_build_problem(app.load_parcels(), 'water_saving', value)
    assert problem['ratio'] == expected
    assert problem['budget'] == pytest.approx(10000 * expected)


@pytest.mark.parametrize('value', [None, 0, -1, '0.5', 'bad', float('nan'), float('inf'), 10.01, True])
def test_projects_budget_contract_remains_strict(value):
    with pytest.raises(ValueError):
        configuration({**request_body(), 'water_budget_ratio': value}, example())


def test_projects_budget_required_and_boundaries():
    body = request_body()
    body.pop('water_budget_ratio')
    with pytest.raises(ValueError):
        configuration(body, example())
    for value in (.01, .5, 10):
        assert configuration({**request_body(), 'water_budget_ratio': value}, example())['water_budget_ratio'] == value


def test_aco_earlier_best_keeps_its_metrics(monkeypatch):
    bundle = bundle_for('ACO')
    with using_provider(ProjectDataProvider(bundle)):
        problem = app._matrix_build_problem(app.load_parcels(), 'water_saving', 1., 2025)
        problem['benchmark_fast'] = True
        choices = [[i, j] for i in range(len(problem['parcels'][0]['options']))
                   for j in range(len(problem['parcels'][1]['options']))]
        ranked = sorted(choices, key=lambda sol: app._matrix_eval_solution(problem, sol)[0])
        worst, best = ranked[0], ranked[-1]
        expected_score, expected_metrics = app._matrix_eval_solution(problem, best)
        assert expected_score > app._matrix_eval_solution(problem, worst)[0]
        # First ant finds the best; all later ants (including final iteration) are worse.
        stream = iter(best + worst * 11)
        monkeypatch.setattr(app, '_matrix_random_solution', lambda *a: worst[:])
        monkeypatch.setattr(app.random.Random, 'choices', lambda self, *a, **k: [next(stream)])
        solution, metrics = app._matrix_aco_optimize(problem, seed=123, ants=4, iterations=3)
        assert solution == best
        assert metrics['bestScore'] == expected_score
        for key, value in expected_metrics.items():
            assert metrics[key] == value, key
        payload = app._matrix_solution_to_payload(problem, solution, 'ACO')
        selected = [p['options'][i] for p, i in zip(problem['parcels'], best)]
        assert [row['chosenCrop'] for row in payload['details']] == [o['name'] for o in selected]
        assert payload['total_water_m3'] == pytest.approx(sum(o['totalWater'] for o in selected))
        assert payload['total_profit_tl'] == pytest.approx(sum(o['totalProfit'] for o in selected))
        assert sum(row['area_da'] for row in payload['details']) == pytest.approx(sum(o['area_da'] for o in selected))
        assert payload['feasible'] == (payload['total_water_m3'] <= problem['budget'] + 1e-6)


@pytest.mark.parametrize('algorithm', ['GA', 'ABC', 'ACO'])
def test_normal_s1_preserves_provider_algorithm_and_totals(algorithm):
    result = run_in_process(bundle_for(algorithm))
    assert result['status'] == 'OK'
    assert result['algorithm'] == algorithm
    assert result['meta']['planner_mode'] == 'matrix_category_guarded'
    assert {r['chosenCrop'] for r in result['details']} <= {'ARPA', 'NOHUT'}
    assert result['total_water_m3'] == pytest.approx(sum(r['water_m3'] for r in result['details']))
    assert result['total_profit_tl'] == pytest.approx(sum(r['profit_tl'] for r in result['details']))
    assert sum(r['area_da'] for r in result['details']) == 20


@pytest.mark.parametrize('revision_change,fail', [(False, False), (True, False), (True, True)])
def test_run_revision_is_checked_inside_store_update(institutional, revision_change, fail):
    client, repo, pid = institutional
    payload = execution_payload(client, pid)
    before = repo.get(pid)
    revision = before['data_revision']
    new_state = {'requires_reanalysis': True, 'reason': 'test-new-revision'}
    def executor(bundle):
        if revision_change:
            def change(document):
                document['data_revision'] += 1
                document['analysis_state'] = deepcopy(new_state)
            repo.update(pid, change)
        if fail:
            raise RuntimeError('controlled execution failure')
        return run_in_process(bundle)
    service = OptimizationApplicationService(repo, executor)
    run = service.run(pid, payload)
    stored = repo.get(pid)
    assert run['provenance']['input_snapshot']['project_revision'] == revision
    assert stored['runs'][run['id']] == run
    if revision_change:
        assert stored['data_revision'] == revision + 1
        assert stored['analysis_state'] == new_state
    else:
        assert stored['analysis_state']['requires_reanalysis'] is False
        assert stored['analysis_state']['resolved_data_revision'] == revision
    assert run['status'] == ('failed' if fail else 'completed'), run.get('error')
    if fail:
        assert run['result'] is None
    else:
        assert run['result']['input_provenance']['project_revision'] == revision
        assert service.get(pid, run['id'])['result']['input_provenance']['project_revision'] == revision
        presented = present_run_for_ui(run, stored)
        assert presented['presentation_context']['revision_relationship'] == (
            'RUN_OLDER_THAN_PROJECT' if revision_change else 'SAME_REVISION')


def test_projects_matrix_error_persists_failure_not_success(institutional, monkeypatch):
    client, repo, pid = institutional
    body = execution_payload(client, pid)
    original_state = deepcopy(repo.get(pid).get('analysis_state'))
    def broken(*a, **k):
        raise RuntimeError('controlled-private-detail')
    monkeypatch.setattr(app, '_matrix_build_problem', broken)
    monkeypatch.setattr(app, 'build_candidate_matrix', lambda *a, **k: pytest.fail('legacy engine called'))
    run = OptimizationApplicationService(repo, run_in_process).run(pid, body)
    assert run['status'] == 'failed' and run['result'] is None
    assert 'controlled-private-detail' not in run['error']
    assert run['project_id'] == pid and run['algorithm'] == body['algorithm']
    assert run['provenance']['input_snapshot']['project_revision'] == body['preview_revision']
    assert repo.get(pid).get('analysis_state') == original_state
    assert repo.get(pid)['runs'][run['id']]['status'] == 'failed'


def test_worker_process_matrix_error_does_not_return_traceback():
    bundle = bundle_for()
    broken = replace(bundle, resources=tuple((key, value) for key, value in bundle.resources
                                             if key != 'candidate_options'))
    with pytest.raises(RuntimeError) as error:
        execute(broken)
    assert 'S1 aday verisi' in str(error.value)
    assert 'Traceback' not in str(error.value)
    assert 'candidate_options' not in str(error.value)


def test_normal_s1_process_boundary():
    result = execute(bundle_for())
    assert result['status'] == 'OK' and result['algorithm'] == 'GA'
    assert result['total_profit_tl'] == pytest.approx(sum(row['profit_tl'] for row in result['details']))


def test_finalization_failure_discards_partial_result(institutional, monkeypatch):
    import kds.application.optimization as application
    client, repo, pid = institutional
    body = execution_payload(client, pid)
    def broken(*args, **kwargs):
        raise RuntimeError('controlled finalization failure')
    monkeypatch.setattr(application, 'complete_result_contract', broken)
    run = OptimizationApplicationService(repo, run_in_process).run(pid, body)
    assert run['status'] == 'failed' and run['result'] is None and 'summary' not in run
    assert repo.get(pid)['runs'][run['id']]['result'] is None


def test_engine_error_payload_is_not_a_completed_run(institutional):
    client, repo, pid = institutional
    run = OptimizationApplicationService(repo, lambda bundle: {'status': 'ERROR'}).run(
        pid, execution_payload(client, pid))
    assert run['status'] == 'failed' and run['result'] is None
    assert repo.get(pid)['runs'][run['id']]['status'] == 'failed'


def test_reference_run_revision_display_uses_actual_input_revision():
    run = {'status': 'completed', 'result': None,
           'provenance': {'input_snapshot': {'project_revision': 3, 'preview_revision': None}}}
    document = {'data_revision': 4, 'analysis_state': {'requires_reanalysis': True}}
    result = present_run_for_ui(run, document)
    assert result['presentation_context']['run_project_revision'] == 3
    assert result['presentation_context']['revision_relationship'] == 'RUN_OLDER_THAN_PROJECT'
    assert result['presentation_context']['requires_reanalysis'] is True
    assert 'presentation_context' not in run


def test_scenario_global_pilot_and_preview_remain_distinct(institutional):
    client, repo, pid = institutional
    body = execution_payload(client, pid)
    baseline = readiness(repo.get(pid))
    assert baseline['ready'] is True
    def remove_s2(document):
        document['economic_data']['active'].pop('seasonal_economics|2025|project|catalog')
    repo.update(pid, remove_s2)
    report = client.get(f'/api/v2/projects/{pid}/readiness').json
    assert report['ready'] is False
    assert report['execution_profiles']['VERIFIED_INSTITUTIONAL']['ready'] == {'S1': True, 'S2': False}
    assert report['pilot_readiness']['status'] == 'PILOT_DATA_NOT_READY'
    preview = OptimizationApplicationService(repo).preview(pid, body)
    assert preview['ready'] is True
    repo.update(pid, lambda d: d['economic_data']['active'].pop('crop_net_profit|2025|project|catalog'))
    assert OptimizationApplicationService(repo).preview(pid, body)['ready'] is False


def test_readiness_ui_uses_selected_profile_and_fails_closed():
    # Execute the actual ES module without a browser/server or external resources.
    path = Path(__file__).resolve().parents[1] / 'kds/ui/static/readiness.js'
    source = path.read_text(encoding='utf-8').replace("import {badge,table} from './api.js';", '')
    script = '''
const {scenarioReady}=await import('data:text/javascript;base64,'+Buffer.from(SOURCE).toString('base64'));
const assert=(ok)=>{if(!ok)throw Error('readiness mismatch')};
const report={ready:false,scenarios:{S1:{status:'READY'},S2:{status:'NOT_READY'}},execution_profiles:{REFERENCE_DEMO:{ready:{S1:true,S2:false}}},pilot_readiness:{status:'PILOT_DATA_NOT_READY'}};
assert(scenarioReady(report,'REFERENCE_DEMO','S1'));
report.scenarios.S1.status='READY_WITH_WARNINGS';
assert(scenarioReady(report,'REFERENCE_DEMO','S1'));
assert(!scenarioReady(report,'REFERENCE_DEMO','S2'));
assert(!scenarioReady(null,'REFERENCE_DEMO','S1'));
assert(!scenarioReady(report,'VERIFIED_INSTITUTIONAL','S1'));
report.execution_profiles.REFERENCE_DEMO.ready.S1=false;
assert(!scenarioReady(report,'REFERENCE_DEMO','S1'));
report.execution_profiles.REFERENCE_DEMO.ready.S1=true;
report.scenarios.S1.status='NOT_READY';
assert(!scenarioReady(report,'REFERENCE_DEMO','S1'));
assert(report.ready===false&&report.pilot_readiness.status==='PILOT_DATA_NOT_READY');
'''.replace('SOURCE', json.dumps(source))
    subprocess.run(['node', '--input-type=module', '-e', script], check=True, capture_output=True, text=True)


def test_readiness_browser_binding_without_server():
    from playwright.sync_api import sync_playwright
    root = Path(__file__).resolve().parents[1] / 'kds/ui/static'
    readiness_source = (root / 'readiness.js').read_text(encoding='utf-8')
    analysis_source = (root / 'analysis.js').read_text(encoding='utf-8')
    source = '\n'.join(line for line in (readiness_source + '\n' + analysis_source).splitlines()
                       if not line.startswith(('import ', 'export {'))).replace('export function ', 'function ')
    report = {'ready': False, 'status': 'NOT_READY', 'blocking_reasons': ['S2 data missing'],
              'effective_execution_profile': 'REFERENCE_DEMO',
              'scenarios': {'S1': {'status': 'READY', 'issues': []},
                            'S2': {'status': 'NOT_READY', 'issues': []}},
              'execution_profiles': {'REFERENCE_DEMO': {'ready': {'S1': True, 'S2': False}}},
              'pilot_readiness': {'status': 'PILOT_DATA_NOT_READY'}}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.route('**/*', lambda route: route.abort())
        page.set_content('''<form id="analysis-form"><select name="execution_profile"><option>REFERENCE_DEMO</option></select>
            <select name="scenario"><option>S1</option><option>S2</option></select></form>
            <button id="run-button"></button>''' + ''.join(
            f'<div id="{name}"></div>' for name in ('readiness-verdict', 'blocking-summary', 'readiness',
                'scenario-readiness', 'execution-state', 'global-mode-badge', 'mode-warning')))
        browser_script = (
            "const badge=()=>document.createElement('span'),table=()=>document.createElement('table');\n"
            + source + "\nwindow.setReadiness=setReadiness;")
        page.evaluate('(source)=>eval(source)', browser_script)
        page.evaluate('(report)=>window.setReadiness(report)', report)
        assert page.locator('#run-button').is_enabled()
        assert page.locator('#readiness-verdict').inner_text() == 'NOT_READY'
        assert 'Seçili S1: ÇALIŞTIRILABİLİR' in page.locator('#readiness-scopes').inner_text()
        assert 'PILOT_DATA_NOT_READY' in page.locator('#readiness-scopes').inner_text()
        page.select_option('[name=scenario]', 'S2')
        page.evaluate('(report)=>window.setReadiness(report)', report)
        assert page.locator('#run-button').is_disabled()
        assert 'Seçili S2: ENGELLENDİ' in page.locator('#readiness-scopes').inner_text()
        page.select_option('[name=scenario]', 'S1')
        report['execution_profiles']['REFERENCE_DEMO']['ready']['S1'] = False
        page.evaluate('(report)=>window.setReadiness(report)', report)
        assert page.locator('#run-button').is_disabled()
        page.evaluate('window.setReadiness(null)')
        assert page.locator('#run-button').is_disabled()
        browser.close()
