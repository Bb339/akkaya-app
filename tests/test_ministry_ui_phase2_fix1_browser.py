"""Real Chromium coverage for corrective map, state and result presentation."""
import json
import threading

import pytest
from flask import Flask
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from kds.api import register_project_api
from kds.data.project_store import FileProjectStore
from test_analysis_workflow import example


LEAFLET_STUB = """
Object.defineProperty(window, 'L', {configurable: false, value: {
  map(root) { return {_root:root,lastTarget:null,setView(p,z){this.lastTarget=String(p);return this},fitBounds(b){this.lastTarget='bounds';return this},remove(){root.replaceChildren()}} },
  tileLayer(){return {addTo(){return this}}},
  marker(coords){let handlers={};return {addTo(map){const el=document.createElement('button');el.type='button';el.className='leaflet-marker-icon';el.dataset.coords=coords.join(',');el.onclick=()=>handlers.click?.();map._root.append(el);this._icon=el;return this},bindTooltip(value){this._icon.title=value;return this},on(name,fn){handlers[name]=fn;return this},getLatLng(){return coords}}},
  featureGroup(layers){return {getLayers(){return layers},getBounds(){return {pad(){return this}}}}},
  geoJSON(){throw new Error('Coordinate marker fixture should not call geoJSON')}
}});
"""


def stored_run():
    return {
        "id": "run-map", "project_id": "sample-a", "data_version": "v1",
        "configuration": {"objective": "water_saving", "scenario": "S1", "selected_ids": []},
        "scenario": "S1", "algorithm": "GA", "seed": 7,
        "execution_profile": "VERIFIED_INSTITUTIONAL",
        "result_authority_label": "SYNTHETIC / NOT_OFFICIAL",
        "started_at": "2026-09-25T10:00:00+00:00", "completed_at": "2026-09-25T10:01:00+00:00",
        "status": "completed", "error": None, "warnings": ["Kurumsal kontrol uyarısı"],
        "provenance": {"project_name": "Synthetic test", "data_source_notes": "synthetic_test_fixture",
                       "input_snapshot": {"preview_revision": 0}, "cache_key": "fixture"},
        "summary": {"active_area_da": 20, "fallow_area_da": 0, "score": 1},
        "result": {
            "scenario": "S1", "feasible": True, "overall_feasible": True,
            "classification": "SYNTHETIC_DIAGNOSTIC", "total_profit_tl": 2100,
            "total_water_m3": 90, "authoritative_water_m3": 90, "optimizer_water_m3": 90,
            "verified_profile_water_m3": 90, "planning_year_profile_water_m3": 60,
            "efficiency_tl_per_m3": 10, "efficiency_tl_per_m3_denominator": "AUTHORITATIVE_VERIFIED_FULL_SEASON_WATER",
            "unit_results": [
                {"analysis_unit_id": "P2", "area_da": 10, "selected_crops": [{"crop": "MISIR", "season": "PRIMARY"}], "total_water_m3": 50, "warnings": ["P2 su uyarısı"]},
                {"analysis_unit_id": "P1", "area_da": 10, "selected_crops": [{"crop": "NOHUT", "season": "PRIMARY"}], "total_water_m3": 40, "status": "PASS"},
                {"analysis_unit_id": "P3", "area_da": 5, "selected_crops": [{"crop": "ARPA", "season": "PRIMARY"}], "total_water_m3": 10},
            ],
            "details": [
                {"parcelId": "P1", "area_da": 10, "chosenCrop": "NOHUT", "profit_tl": 900},
                {"parcelId": "P2", "area_da": 10, "chosenCrop": "MISIR", "profit_tl": 1200},
                {"parcelId": "P3", "area_da": 5, "chosenCrop": "ARPA", "profit_tl": 300},
            ],
            "top_crops": [{"crop": "NOHUT", "area_da": 10, "share": .5}],
            "crop_shares": {"NOHUT": .5, "MISIR": .3, "ARPA": .2}, "hhi": .38, "HHI": .38,
            "warnings": [], "annual_budget_validation": {"status": "PASS"},
            "monthly_supply_validation": {"status": "PASS"}, "monthly_delivery_validation": {"status": "PASS"},
            "water_reconciliation": {"status": "PASS"},
            "result_provenance": {"preview_revision": 0, "selection_hash": "sel", "engine_commit": "engine"},
        },
    }


def repository_with_run(tmp_path):
    repo=FileProjectStore(tmp_path/'projects');document=example()
    document['analysis_units'][0].update(latitude=38.1,longitude=34.1,current_crop='ARPA')
    document['analysis_units'][1].update(latitude=38.2,longitude=34.2,current_crop='BUGDAY')
    document['analysis_units'].append({"id":"unit-3","project_id":"sample-a","external_id":"P3","area_da":5,"current_crop":"ARPA","name_or_code":"","settlement":"","irrigation_method":"","latitude":None,"longitude":None,"geometry":None,"metadata":{}})
    document['project']['data_source_notes']='synthetic_test_fixture';document['metadata'].update(synthetic_institutional_test=True,not_official=True)
    document['runs']={'run-map':stored_run()};document['analysis_state']={"requires_reanalysis":True,"latest_run_id":"run-new"};document['data_revision']=2
    repo.create(document);return repo


def serve(repository):
    app=Flask('phase2-fix1-browser');app.config['TESTING']=True;register_project_api(app,repository)
    server=make_server('127.0.0.1',0,app,threaded=True);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    return server,thread


@pytest.mark.browser
def test_verified_map_list_crop_shares_and_reanalysis_in_real_chromium(tmp_path):
    server,thread=serve(repository_with_run(tmp_path))
    try:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True);page=browser.new_page(viewport={"width":1366,"height":1000})
            page.add_init_script(LEAFLET_STUB);page.route('https://unpkg.com/**',lambda route:route.abort())
            errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{server.server_port}/projects');page.locator('#projects .project-card').click()
            page.locator('#history button').first.click()
            expect(page.locator('.leaflet-marker-icon')).to_have_count(2)
            page.locator('.leaflet-marker-icon').nth(1).dispatch_event('click')
            expect(page.locator('#unit-detail')).to_contain_text('P2');expect(page.locator('#unit-detail')).to_contain_text('BUGDAY')
            expect(page.locator('#unit-detail')).to_contain_text('MISIR');expect(page.locator('#unit-detail')).to_contain_text('1.200')
            expect(page.locator('#unit-detail')).to_contain_text('50');expect(page.locator('#unit-detail')).to_contain_text('P2 su uyarısı')
            page.locator('#unit-list button').first.click()
            assert page.locator('.leaflet-marker-icon').first.evaluate("element => element.classList.contains('selected-unit-marker')")
            expect(page.locator('#unit-detail')).to_contain_text('P1')
            page.locator('#unit-list button').nth(2).click()
            expect(page.locator('#unit-detail')).to_contain_text('GEOMETRİ YOK')
            expect(page.locator('#crop-shares')).to_contain_text('MISIR');expect(page.locator('#crop-shares')).to_contain_text('ARPA')
            expect(page.locator('#provenance-summary')).to_contain_text('Yeniden analiz gerekli')
            expect(page.locator('#provenance-summary')).to_contain_text('RUN_OLDER_THAN_PROJECT')
            expect(page.locator('#synthetic-watermark')).to_be_visible();assert not errors
            browser.close()
    finally:
        server.shutdown();thread.join(timeout=5)


def minimal_run(warnings=None):
    value=stored_run();value['id']='run-state';value['warnings']=warnings or [];value['result']['presentation_units']=[]
    return value


@pytest.mark.browser
def test_execution_states_persist_after_async_refresh_and_errors(tmp_path):
    repo=FileProjectStore(tmp_path/'projects');repo.create(example());server,thread=serve(repo)
    try:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True);page=browser.new_page();page.add_init_script(LEAFLET_STUB)
            mode={"value":"complete"}
            def analyses(route):
                if mode['value']=='complete':route.fulfill(status=201,content_type='application/json',body=json.dumps(minimal_run()))
                elif mode['value']=='warnings':route.fulfill(status=201,content_type='application/json',body=json.dumps(minimal_run(['review warning'])))
                elif mode['value']=='stale':route.fulfill(status=409,content_type='application/json',body=json.dumps({"error":"STALE_PREVIEW / REVISION_CONFLICT"}))
                else:route.fulfill(status=500,content_type='application/json',body=json.dumps({"error":"ordinary server failure"}))
            page.route('**/api/v2/projects/sample-a/analyses',analyses)
            page.goto(f'http://127.0.0.1:{server.server_port}/projects');page.locator('#projects .project-card').click()
            expect(page.locator('#execution-state')).to_have_text('READY')
            page.locator('#run-button').click();expect(page.locator('#execution-state')).to_have_text('COMPLETED')
            mode['value']='warnings';page.locator('#run-button').click();expect(page.locator('#execution-state')).to_have_text('COMPLETED WITH WARNINGS')
            page.locator('#preview-analysis').click();expect(page.locator('#execution-state')).to_have_text('READY')
            page.locator('#analysis-form [name=seed]').fill('124');page.locator('#analysis-form [name=seed]').blur()
            expect(page.locator('#execution-state')).to_have_text('STALE PREVIEW')
            page.locator('#preview-analysis').click();expect(page.locator('#execution-state')).to_have_text('READY')
            mode['value']='stale';page.locator('#run-button').click();expect(page.locator('#execution-state')).to_have_text('STALE PREVIEW')
            page.locator('#preview-analysis').click();expect(page.locator('#execution-state')).to_have_text('READY')
            mode['value']='failure';page.locator('#run-button').click();expect(page.locator('#execution-state')).to_have_text('FAILED')
            browser.close()
    finally:
        server.shutdown();thread.join(timeout=5)


@pytest.mark.browser
def test_blocked_state_and_offline_map_fallback_remain_truthful(tmp_path):
    repo=repository_with_run(tmp_path);repo.update('sample-a',lambda doc:doc.__setitem__('analysis_units',[]));server,thread=serve(repo)
    try:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True);page=browser.new_page()
            page.route('https://unpkg.com/**',lambda route:route.abort())
            page.goto(f'http://127.0.0.1:{server.server_port}/projects');page.locator('#projects .project-card').click()
            expect(page.locator('#execution-state')).to_have_text('BLOCKED')
            page.locator('#history button').first.click();expect(page.locator('#institutional-map')).to_contain_text('çevrimdışı')
            expect(page.locator('#unit-list button')).to_have_count(3);page.locator('#unit-list button').nth(1).click();expect(page.locator('#unit-detail')).to_contain_text('P2')
            browser.close()
    finally:
        server.shutdown();thread.join(timeout=5)
