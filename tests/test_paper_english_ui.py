from __future__ import annotations

from flask import send_from_directory
import pytest
from playwright.sync_api import expect, sync_playwright

from test_unified_decision_demo import analysis_payload, client_for, project_payload
from test_unified_decision_demo_browser import serve
from test_unified_v1_project_provider_browser import _serve_v1
from test_v1_native_project_integration_fix2 import _confirm, _upload


ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]


def _prepare_run(client, repository):
    project_id = 'paper-english-parity'
    payload = project_payload(project_id)
    payload['name'] = 'English Paper UI Parity Project'
    assert client.post('/api/v2/projects', json=payload).status_code == 201
    package = _upload(client, project_id)
    assert package['auto_matched'] == len(package['items']) == 21
    _confirm(client, project_id, package['items'])
    request = analysis_payload()
    preview = client.post(f'/api/v2/projects/{project_id}/analysis-preview', json=request)
    assert preview.status_code == 200 and preview.json['ready'] is True
    response = client.post(f'/api/v2/projects/{project_id}/analyses', json={
        **request,
        **{key: preview.json[key] for key in ('preview_token', 'preview_revision', 'selection_hash')},
    })
    assert response.status_code == 201, response.json
    document = repository.get(project_id)
    assert document['data_revision'] == 21
    assert len(document['analysis_units']) == 24
    assert sum(bool(unit.get('geometry')) for unit in document['analysis_units']) == 24
    assert len(document['crops']) == 8
    assert len({row['analysis_unit_id'] for row in document['scientific_inputs']['candidates']}) == 24
    return project_id, response.json


@pytest.mark.browser
def test_english_paper_ui_preserves_project_run_and_selected_unit_parity(tmp_path):
    application, client, repository = client_for(tmp_path)

    @application.get('/data/<path:filename>')
    def v1_reference_data(filename):
        return send_from_directory(ROOT / 'data', filename)

    _serve_v1(application)
    project_id, run = _prepare_run(client, repository)
    server, thread = serve(application)
    requests, page_errors = [], []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1366, 'height': 900})
            page.on('request', lambda request: requests.append(request.url))
            page.on('pageerror', lambda error: page_errors.append(str(error)))
            page.goto(
                f'http://127.0.0.1:{server.server_port}/?provider=PROJECT_DATA'
                f'&project_id={project_id}&run_id={run["id"]}'
            )
            page.wait_for_function(
                'runId => window.__V1_PROJECT_PROVIDER__?.context?.run?.id === runId',
                arg=run['id'],
            )
            page.evaluate(
                "setAuthenticatedUser(getAuthUserByUsername('kurum.nigde'), {focus:false})"
            )
            page.locator('#parcelSelect').select_option('KDS-009')
            page.wait_for_function(
                "document.querySelector('#metricsTitle')?.textContent.includes('KDS-009')"
            )
            page.evaluate("""() => {
              map.invalidateSize();
              const layers=Object.values(map._layers||{}).filter(
                layer => layer.__providerUnit && typeof layer.getBounds === 'function'
              );
              const bounds=L.featureGroup(layers).getBounds();
              if(bounds?.isValid?.())map.fitBounds(bounds.pad(.15),{animate:false});
            }""")
            page.evaluate("window.__V1_PROJECT_PROVIDER__.openUnitPopup('KDS-009')")
            popup = page.locator('.leaflet-popup-content', has_text='KDS-009')
            expect(popup).to_be_visible()
            page.wait_for_function("""() => {
              const popup=document.querySelector('.leaflet-popup');
              const map=document.querySelector('#map');
              if(!popup||!map)return false;
              const p=popup.getBoundingClientRect(), m=map.getBoundingClientRect();
              return p.left>=m.left && p.right<=m.right && p.top>=m.top && p.bottom<=m.bottom;
            }""")
            assert page.locator('.parcel-badge > .dot + .pid + .hint').count() == 24
            assert page.evaluate("""() => Array.from(
              document.querySelectorAll('#analysisTables .tab')
            ).filter(node => node.offsetParent !== null).length""") == 7
            assert page.locator('.tab[data-tab="drought"]').count() == 0

            before = page.evaluate("""() => ({
              project:window.__V1_PROJECT_PROVIDER__.context.project.id,
              run:window.__V1_PROJECT_PROVIDER__.context.run.id,
              revision:window.__V1_PROJECT_PROVIDER__.context.project_revision,
              selected:window.__V1_PROJECT_PROVIDER__.selectedUnit,
              units:window.__V1_PROJECT_PROVIDER__.context.units.map(x=>x.analysis_unit_id),
              geometry:document.querySelectorAll('.leaflet-overlay-pane path.leaflet-interactive').length,
              result:JSON.stringify(window.__V1_PROJECT_PROVIDER__.context.run.result)
            })""")
            api_requests_before = [url for url in requests if '/api/v2/' in url]
            page.locator('[data-paper-lang="en"]').click()
            expect(page.locator('html')).to_have_attribute('lang', 'en')
            expect(page.locator('#metricsTitle')).to_have_text(
                'Analysis Unit Decision Summary (KDS-009)'
            )
            expect(page.locator('.map-card .card-title')).to_have_text('Analysis Unit Map')
            expect(page.locator('#waterRiskSection')).to_contain_text('NOT PROVIDED')
            expect(page.locator('#parcelSummaryTitle')).to_contain_text('KDS-009')
            expect(page.locator('#tblCurrent')).to_contain_text('Current')
            expect(page.locator('#tblRecommended')).to_contain_text('Recommended')
            assert [url for url in requests if '/api/v2/' in url] == api_requests_before
            after = page.evaluate("""() => ({
              project:window.__V1_PROJECT_PROVIDER__.context.project.id,
              run:window.__V1_PROJECT_PROVIDER__.context.run.id,
              revision:window.__V1_PROJECT_PROVIDER__.context.project_revision,
              selected:window.__V1_PROJECT_PROVIDER__.selectedUnit,
              units:window.__V1_PROJECT_PROVIDER__.context.units.map(x=>x.analysis_unit_id),
              geometry:document.querySelectorAll('.leaflet-overlay-pane path.leaflet-interactive').length,
              result:JSON.stringify(window.__V1_PROJECT_PROVIDER__.context.run.result)
            })""")
            assert after == before
            assert before == {
                **before,
                'project': project_id,
                'run': run['id'],
                'revision': 21,
                'selected': 'KDS-009',
                'geometry': 24,
            }

            page.locator('[data-paper-lang="tr"]').click()
            expect(page.locator('#metricsTitle')).to_have_text(
                'Analiz Birimi Karar Özeti (KDS-009)'
            )
            page.locator('[data-paper-lang="en"]').click()
            page.goto(f'http://127.0.0.1:{server.server_port}/projects#project={project_id}&section=result')
            expect(page.locator('html')).to_have_attribute('lang', 'en')
            expect(page.locator('h1')).to_have_text('Institutional Agricultural Decision Workflow')
            expect(page.locator('#project-status-badges')).to_contain_text('Revision 21')
            page.goto(
                f'http://127.0.0.1:{server.server_port}/projects/decision'
                f'?project_id={project_id}&run_id={run["id"]}'
                '&execution_profile=VERIFIED_INSTITUTIONAL'
            )
            expect(page.locator('html')).to_have_attribute('lang', 'en')
            expect(page.locator('#decision-title')).to_contain_text('English Paper UI Parity Project')
            expect(page.locator('#result')).to_contain_text('Verified Water Results')
            assert not page_errors
            reference_tokens = (
                '/api/parcels', '/api/optimize', '/api/meta', '/api/geojson_files',
                '/api/geojson_bundle', '/api/water_allocation_logic', '/data/',
            )
            assert not [url for url in requests if any(token in url for token in reference_tokens)]
            stored = client.get(f'/api/v2/projects/{project_id}/analyses/{run["id"]}').json
            assert stored == run
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
