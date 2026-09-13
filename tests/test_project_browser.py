"""Real Chromium: create, import, preflight, execute and view stored result."""
import os
import json
from pathlib import Path
import threading
from flask import Flask
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright, expect
import pytest
from kds.api import register_project_api
from kds.data.project_store import FileProjectStore
from test_analysis_workflow import example


@pytest.mark.browser
def test_project_workflow_in_chromium(tmp_path):
    repository=FileProjectStore(tmp_path/'projects');repository.create(example())
    app=Flask('browser-tests');register_project_api(app,repository)
    server=make_server('127.0.0.1',0,app,threaded=True)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':1280,'height':900})
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{server.server_port}/projects')
            page.get_by_text('Yeni proje oluştur',exact=True).click()
            form=page.locator('#create-project')
            form.locator('[name=id]').fill('browser-created')
            form.locator('[name=name]').fill('Tarayıcı test projesi')
            form.locator('[name=planning_year]').fill('2025')
            form.locator('[name=annual_water_budget]').fill('10000')
            form.get_by_role('button').click()
            expect(page.locator('#project-name')).to_have_text('Tarayıcı test projesi')
            expect(page.locator('#readiness')).to_contain_text('NOT_READY')
            page.locator('#upload-form input[type=file]').set_input_files(dict(name='units.csv',mimeType='text/csv',
                buffer=b'external_id,settlement,area_da,current_crop\nP1,Test,10,ARPA\nP2,Test,10,ARPA\n'))
            page.locator('#upload-form button').click()
            expect(page.locator('#import-preview')).to_be_visible()
            page.locator('#map-import').click()
            expect(page.locator('#preview')).to_contain_text('"status": "ready"')
            page.locator('#acknowledge').check()
            page.locator('#confirm-import').click()
            expect(page.locator('#message')).to_have_text('Aktarım onaylandı.')
            assert len(repository.get('browser-created')['analysis_units'])==2
            for data_type,content in [
                ('crops','crop_name,kc_initial,kc_mid,kc_end,stage_initial_days,stage_development_days,stage_mid_days,stage_late_days,source,confidence_level\nARPA,0.4,1,0.5,20,30,40,20,synthetic,high\nNOHUT,0.4,1,0.5,20,30,40,20,synthetic,high\n'),
                ('economics','crop_name,year,yield_per_da,net_profit_per_da,currency,source,yield_unit\nARPA,2025,1000,1200,TRY,synthetic,kg/da\nNOHUT,2025,1000,1500,TRY,synthetic,kg/da\n')]:
                page.locator('#upload-form select').select_option(data_type)
                page.locator('#upload-form input[type=file]').set_input_files(dict(name=data_type+'.csv',mimeType='text/csv',buffer=content.encode()))
                with page.expect_response(lambda r:'/imports' in r.url and r.request.method=='POST'):
                    page.locator('#upload-form button').click()
                page.locator('#map-import').click()
                expect(page.locator('#preview')).to_contain_text('"status": "ready"')
                page.locator('#acknowledge').check()
                with page.expect_response(lambda r:r.url.endswith('/confirm')):
                    page.locator('#confirm-import').click()
            page.get_by_text('Su bütçesini tanımla',exact=True).click()
            page.locator('#budget-form [name=amount]').fill('10000')
            page.locator('#budget-form [name=source]').fill('Synthetic browser test')
            with page.expect_response(lambda r:r.url.endswith('/water-budget')):
                page.locator('#budget-form button').click()
            page.get_by_text('Açık bilimsel aday ve sezon girdileri',exact=True).click()
            data=example('browser-created')['scientific_inputs']
            page.locator('#scientific-form input[type=file]').set_input_files(dict(name='scientific.json',mimeType='application/json',buffer=json.dumps(data).encode()))
            page.locator('#scientific-form button').click()
            expect(page.locator('#readiness')).to_contain_text('S1: READY')
            page.locator('#run-button').click()
            expect(page.locator('#result')).to_be_visible(timeout=90000)
            expect(page.locator('#result-facts')).to_contain_text('browser-created')
            expect(page.locator('#provenance')).to_contain_text('cache_key')
            records=repository.get('browser-created')['runs']
            assert len(records)==1 and next(iter(records.values()))['status']=='completed'
            assert not errors
            screenshot=os.environ.get('KDS_BROWSER_SCREENSHOT')
            if screenshot:
                page.locator('#result').scroll_into_view_if_needed()
                page.screenshot(path=str(Path(screenshot).resolve()),full_page=False)
            browser.close()
    finally:
        server.shutdown();thread.join(timeout=5)
