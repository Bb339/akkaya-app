"""The complete synthetic CSV/XLSX/GeoJSON workflow in real Chromium."""
import os,json,threading
from pathlib import Path
import pytest
from flask import Flask
from playwright.sync_api import sync_playwright,expect
from werkzeug.serving import make_server
from kds.api import register_project_api
from kds.data.project_store import FileProjectStore
from general_project_support import FIXTURE

@pytest.mark.browser
def test_general_import_analysis_history_in_browser(tmp_path):
    repository=FileProjectStore(tmp_path/'store');application=Flask('general-browser');register_project_api(application,repository)
    server=make_server('127.0.0.1',0,application,threaded=True)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True)
            page=browser.new_page(viewport=dict(width=1440,height=1000));errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{server.server_port}/projects')
            page.get_by_text('Yeni proje oluştur',exact=True).click()
            form=page.locator('#create-project')
            for key,value in dict(id='general-browser',name='Independent synthetic project',planning_year='2025',province_or_region='Synthetic Region').items():form.locator(f'[name={key}]').fill(value)
            form.locator('[name=data_source_notes]').select_option('synthetic_test_fixture')
            with page.expect_response(lambda r:r.url.endswith('/overview')):
                form.get_by_role('button').click()
            expect(page.locator('#synthetic-watermark')).to_be_visible()
            expect(page.locator('#readiness')).to_contain_text('NOT_READY')
            for kind,filename in [('crops','crops.xlsx'),('analysis_units','analysis_units.csv'),('economics','economics.csv'),('water_budget','water_budget.csv'),('candidates','candidates.csv'),('scientific_inputs','scientific_s1.csv'),('scientific_inputs','scientific_s2.csv'),('geometries','geometry_partial.geojson')]:
                page.locator('#upload-form select').select_option(kind)
                page.locator('#upload-form input[type=file]').set_input_files(str(FIXTURE/filename))
                with page.expect_response(lambda r:r.url.endswith('/overview')):
                    with page.expect_response(lambda r:r.url.endswith('/imports') and r.request.method=='POST'):
                        page.locator('#upload-form button').click()
                expect(page.locator('#data-status')).to_contain_text('Uploaded')
                with page.expect_response(lambda r:r.url.endswith('/mapping')):page.locator('#map-import').click()
                expect(page.locator('#preview')).to_contain_text('"status": "ready"')
                page.locator('#acknowledge').check()
                with page.expect_response(lambda r:r.url.endswith('/confirm')):page.locator('#confirm-import').click()
                expect(page.locator('#message')).to_have_text('Aktarım onaylandı.')
                if filename=='scientific_s1.csv':
                    expect(page.locator('#readiness')).to_contain_text('S1: READY_WITH_WARNINGS')
                    expect(page.locator('#readiness')).to_contain_text('S2: NOT_READY')
            expect(page.locator('#readiness')).to_contain_text('S2: READY_WITH_WARNINGS')
            expect(page.locator('#facts')).to_contain_text('24/24')
            page.locator('#run-button').click()
            expect(page.locator('#result')).to_be_visible(timeout=180000)
            expect(page.locator('#result-source-label')).to_contain_text('Sentetik test verisi')
            expect(page.locator('#result-facts')).to_contain_text('scenario')
            expect(page.locator('#result-facts')).to_contain_text('Motor bu metrik için değer üretmedi')
            expect(page.locator('#history button')).to_have_count(1)
            run=next(iter(repository.get('general-browser')['runs']))
            page.reload();page.get_by_role('button',name='Independent synthetic project',exact=True).click()
            expect(page.locator('#history button')).to_have_count(1)
            page.locator('#history button').click()
            expect(page.locator('#provenance')).to_contain_text(run)
            expect(page.locator('#plan')).to_contain_text('GX-')
            assert not errors
            folder=os.environ.get('KDS_GENERAL_BROWSER_SCREENSHOT')
            if folder:
                out=Path(folder);out.mkdir(parents=True,exist_ok=True)
                page.locator('#result').scroll_into_view_if_needed();page.screenshot(path=str(out/'general-project-result.png'))
                page.locator('#history-section').scroll_into_view_if_needed();page.screenshot(path=str(out/'general-project-history.png'))
            browser.close()
    finally:server.shutdown();thread.join(5)
