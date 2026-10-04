from __future__ import annotations

from pathlib import Path

import pytest
from flask import send_from_directory
from playwright.sync_api import expect, sync_playwright

from test_unified_decision_demo import PACKAGE, client_for
from test_unified_decision_demo_browser import serve
from kds.application.import_service import ImportService


ROOT = Path(__file__).resolve().parents[1]
FULL_VISUAL_PACKAGE = ROOT / "docs" / "unified_v1_project_provider" / "demo_full_visual_package"
EVIDENCE = ROOT / "docs" / "v1_native_project_integration_fix2"
LEAFLET = """
Object.defineProperty(window,'L',{configurable:true,writable:true,value:{
 map(root){const layers=[];return{_root:root,_layers:layers,setView(){return this},fitBounds(){return this},remove(){root.replaceChildren()},eachLayer(fn){layers.forEach(fn)},invalidateSize(){return this}}},
 tileLayer(){return{addTo(){return this}}},
 marker(coords){const handlers={};return{__coords:coords,addTo(map){map._layers.push(this);const el=document.createElement('button');el.className='leaflet-marker-icon';map._root.append(el);el.onclick=()=>handlers.click?.();this._el=el;return this},on(name,fn){handlers[name]=fn;return this},getLatLng(){return coords}}},
 geoJSON(feature){const handlers={};return{feature,addTo(map){map._layers.push(this);const el=document.createElement('button');el.className='leaflet-interactive';map._root.append(el);el.onclick=()=>handlers.click?.();return this},on(name,fn){handlers[name]=fn;return this},getBounds(){return{pad(){return this}}}}},
 featureGroup(layers){return{getBounds(){return{pad(){return this}}}}}
}});
Object.defineProperty(window,'Chart',{configurable:true,writable:true,value:function(){return{destroy(){},update(){}}}});
"""
FULL_VISUAL_LEAFLET = LEAFLET + """
L.esri={basemapLayer(name){window.__V1_BASEMAP_NAME__=name;return{addTo(){window.__V1_BASEMAP_ADDED__=true;return this}}}};
"""


def _serve_v1(application):
    @application.get("/")
    def root():
        return send_from_directory(ROOT, "index.html")

    @application.get("/<path:filename>")
    def asset(filename):
        if filename not in {"script.js", "style.css", "favicon.ico"}:
            return "missing", 404
        return send_from_directory(ROOT, filename)


@pytest.mark.browser
def test_projects_to_same_v1_workspace_full_project_flow(tmp_path):
    application, _, repository = client_for(tmp_path)
    _serve_v1(application)
    server, thread = serve(application)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.add_init_script(LEAFLET)
            page.route("https://**", lambda route: route.abort())
            requests, errors = [], []
            page.on("request", lambda request: requests.append(request.url))
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{server.server_port}/projects")
            page.locator("details.form-drawer").first.locator("summary").click()
            form = page.locator("#create-project")
            form.locator('[name="id"]').fill("v1-provider-demo")
            form.locator('[name="name"]').fill("Kurumsal Veri Demo Projesi")
            form.locator('[name="planning_year"]').fill("2025")
            form.locator('[name="province_or_region"]').fill("Synthetic Region")
            form.locator('[name="data_source_notes"]').select_option(
                "synthetic not_official institutional integration fixture")
            with page.expect_response(lambda response: response.url.endswith("/api/v2/projects")
                                      and response.request.method == "POST"):
                form.locator("button").click()
            expect(page.locator("#synthetic-watermark")).to_be_visible(timeout=15000)

            files = [str(path) for path in sorted(PACKAGE.iterdir())
                     if path.suffix.lower() in {".csv", ".xlsx", ".geojson"}]
            page.locator('#bulk-upload-form input[type="file"]').set_input_files(files)
            with page.expect_response(lambda response: response.url.endswith("/bulk-imports"), timeout=120000):
                page.locator('#bulk-upload-form button[type="submit"]').click()
            expect(page.locator("#bulk-import-body tr")).to_have_count(20)
            assert page.locator("#bulk-import-body tr", has_text="AUTO_MATCHED").count() == 20
            page.locator("#bulk-confirm").click()
            expect(page.locator("#readiness-verdict")).to_contain_text("VERIFIED READY", timeout=180000)
            page.locator("#open-v1-project").click()
            page.wait_for_url("**/?provider=PROJECT_DATA&project_id=v1-provider-demo")

            # Authentication is outside this provider milestone.  The compact
            # local harness blocks remote decorative assets, so drive the
            # accepted demo-account controls through their DOM handlers.
            page.wait_for_function(
                "typeof window.__V1_PROJECT_PROVIDER__ === 'object' && "
                "typeof setAuthenticatedUser === 'function' && "
                "typeof getAuthUserByUsername === 'function'"
            )
            page.evaluate("setAuthenticatedUser(getAuthUserByUsername('kurum.nigde'), {focus:false})")
            expect(page.locator("#panel")).to_be_visible(timeout=30000)
            expect(page.locator("#v1-provider-name")).to_have_text(
                "PROJECT DATA · Kurumsal Veri Demo Projesi", timeout=30000)
            expect(page.locator("#v1-provider-authority")).to_contain_text("SYNTHETIC / NOT_OFFICIAL")
            expect(page.locator("#parcelSelect option")).to_have_count(24)
            assert page.locator("#parcelSelect option").first.get_attribute("value").startswith("GX-")
            page.locator("#parcelSelect").select_option("GX-001")
            expect(page.locator("#parcelSummaryTitle")).to_contain_text("GX-001")
            page.locator("#parcelSelect").select_option("GX-002")
            expect(page.locator("#parcelSummaryTitle")).to_contain_text("GX-002")
            expect(page.locator("#v1-geometry-status")).to_contain_text("24 birimin 2'sinde")

            page.locator("#algoSelect").select_option("ga")
            page.locator("#seasonSourceSel").select_option("s1")
            page.locator('input[name="scenario"][value="su_tasarruf"]').check()
            page.locator("#v1-provider-seed").fill("123")
            page.locator("#v1-provider-preview").click()
            expect(page.locator("#v1-provider-preview-state")).to_contain_text("PINNED", timeout=120000)
            page.locator("#runOptBtn").click()
            expect(page.locator("#algoStatus")).to_contain_text("Tamamlandı", timeout=240000)
            expect(page.locator("#v1-project-result")).to_be_hidden()
            expect(page.locator("#v1-project-result")).to_have_attribute("aria-hidden", "true")
            assert not page.locator("#v1-project-result").inner_text().strip()
            expect(page.locator("#v1-native-run-summary")).to_contain_text("SYNTHETIC / NOT_OFFICIAL")
            expect(page.locator("#v1-native-water-accounting")).to_contain_text("Optimizer su kullanımı")
            expect(page.locator("#v1-native-water-accounting")).to_contain_text("Doğrulanmış / otoritatif su")
            expect(page.locator("#v1-native-water-accounting")).to_contain_text("değerler farklı olabilir")
            expect(page.locator("#v1-native-annual-budget")).to_contain_text("PASS")
            expect(page.locator("#v1-native-warnings")).to_contain_text("Analiz uyarıları")
            expect(page.locator("#v1-native-warnings")).to_contain_text("SYNTHETIC_INSTITUTIONAL_TEST_PROJECT")
            expect(page.locator("#mWaterCurrent")).to_have_text("Mevcut su değeri sağlanmadı")
            expect(page.locator("#mProfitCurrent")).to_have_text("Mevcut kâr değeri sağlanmadı")
            expect(page.locator("#v1-native-crops")).to_contain_text("Ürün kompozisyonu")
            expect(page.locator("#v1-native-monthly")).to_contain_text("Aylık su doğrulaması")
            expect(page.locator("#v1-native-unit-result")).to_contain_text("GX-002")
            expect(page.locator("#v1-native-provenance")).to_contain_text("selection_hash")
            assert "run_id=" in page.url
            run_id = next(iter(repository.get("v1-provider-demo")["runs"]))
            assert f"run_id={run_id}" in page.url
            assert page.evaluate("window.__V1_PROJECT_PROVIDER__.blockedReferencePaths")
            assert not any("/api/parcels" in url or "/api/optimize" in url for url in requests)

            page.reload()
            page.wait_for_function(
                "typeof window.__V1_PROJECT_PROVIDER__ === 'object' && "
                "typeof setAuthenticatedUser === 'function'"
            )
            page.evaluate("setAuthenticatedUser(getAuthUserByUsername('kurum.nigde'), {focus:false})")
            expect(page.locator("#v1-project-result")).to_be_hidden(timeout=30000)
            expect(page.locator("#tblRecommendedFooter")).to_contain_text("water_saving")
            expect(page.locator("#v1-native-provenance")).to_contain_text(run_id)
            project_errors = list(errors)
            assert not [error for error in project_errors
                        if "PROJECT_DATA" not in error and "reference endpoint engellendi" not in error]

            # A stored result must never survive a project switch.  Create an
            # ordinary second project, switch through the provider selector,
            # then return to A and reopen the exact immutable run explicitly.
            status = page.evaluate("""async () => {
              const response = await fetch('/api/v2/projects', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({
                id:'v1-provider-project-b', name:'Kurumsal Proje B', planning_year:2025,
                annual_water_budget:0, water_budget_unit:'m3', province_or_region:'Niğde',
                data_source_notes:'user_provided'
              })}); return response.status;
            }""")
            assert status == 201
            page.reload()
            page.wait_for_function("typeof window.__V1_PROJECT_PROVIDER__ === 'object'")
            page.evaluate("setAuthenticatedUser(getAuthUserByUsername('kurum.nigde'), {focus:false})")
            page.locator("#v1-project-provider-select").select_option("v1-provider-project-b")
            page.wait_for_url("**/?provider=PROJECT_DATA&project_id=v1-provider-project-b")
            page.wait_for_function("typeof window.__V1_PROJECT_PROVIDER__ === 'object'")
            page.evaluate("setAuthenticatedUser(getAuthUserByUsername('kurum.nigde'), {focus:false})")
            expect(page.locator("#v1-provider-name")).to_have_text("PROJECT DATA · Kurumsal Proje B")
            expect(page.locator("#v1-requirement-list")).to_contain_text("Analiz birimleri gerekli")
            expect(page.locator("#v1-requirement-list")).to_contain_text(
                "Harita geometrisi analiz için zorunlu değildir"
            )
            expect(page.locator("#v1-project-result")).to_be_hidden()
            assert run_id not in page.locator("body").inner_text()
            assert "GX-001" not in page.locator("#parcelSelect").inner_text()
            page.locator("#v1-project-provider-select").select_option("v1-provider-demo")
            page.wait_for_url("**/?provider=PROJECT_DATA&project_id=v1-provider-demo")
            expect(page.locator("#v1-project-result")).to_be_hidden()
            page.goto(f"http://127.0.0.1:{server.server_port}/?provider=PROJECT_DATA&project_id=v1-provider-demo&run_id={run_id}")
            page.wait_for_function("typeof window.__V1_PROJECT_PROVIDER__ === 'object'")
            page.evaluate("setAuthenticatedUser(getAuthUserByUsername('kurum.nigde'), {focus:false})")
            expect(page.locator("#v1-project-result")).to_be_hidden()
            expect(page.locator("#tblRecommendedFooter")).to_contain_text("water_saving")
            expect(page.locator("#v1-native-provenance")).to_contain_text(run_id)
            assert not any("/api/parcels" in url or "/api/optimize" in url for url in requests)
            page.locator("#v1-provider-toggle").click()
            page.locator("#v1-reference-provider").click()
            page.wait_for_url(f"http://127.0.0.1:{server.server_port}/")
            expect(page.locator("#v1-provider-name")).to_have_text("AKKAYA REFERENCE")
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.mark.browser
def test_full_visual_package_native_drawer_satellite_map_and_stored_run(tmp_path):
    assert 'L.esri.basemapLayer("Imagery").addTo(map)' in (ROOT / "script.js").read_text(encoding="utf-8")
    assert "L.map(root)" not in (ROOT / "kds/ui/static/v1-provider.js").read_text(encoding="utf-8")
    application, _, repository = client_for(tmp_path)
    _serve_v1(application)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    server, thread = serve(application)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.add_init_script(FULL_VISUAL_LEAFLET)
            page.route("https://**", lambda route: route.abort())
            requests = []
            page.on("request", lambda request: requests.append(request.url))
            page.goto(f"http://127.0.0.1:{server.server_port}/projects")
            page.locator("details.form-drawer").first.locator("summary").click()
            form = page.locator("#create-project")
            form.locator('[name="id"]').fill("native-full-visual")
            form.locator('[name="name"]').fill("KDS Tam Görsel Sentetik Demo")
            form.locator('[name="planning_year"]').fill("2025")
            form.locator('[name="province_or_region"]').fill("Synthetic Region")
            form.locator('[name="data_source_notes"]').select_option(
                "synthetic not_official institutional integration fixture")
            form.locator("button").click()
            files = [str(path) for path in sorted(FULL_VISUAL_PACKAGE.iterdir())
                     if path.suffix.lower() in {".csv", ".xlsx", ".geojson"}]
            page.locator('#bulk-upload-form input[type="file"]').set_input_files(files)
            page.locator('#bulk-upload-form button[type="submit"]').click()
            expect(page.locator("#bulk-import-body tr")).to_have_count(21, timeout=120000)
            assert page.locator("#bulk-import-body tr", has_text="AUTO_MATCHED").count() == 21
            page.locator("#bulk-confirm").click()
            expect(page.locator("#readiness-verdict")).to_contain_text("VERIFIED READY", timeout=180000)
            page.locator("#open-v1-project").click()
            page.wait_for_function("typeof window.__V1_PROJECT_PROVIDER__ === 'object'")
            page.evaluate("setAuthenticatedUser(getAuthUserByUsername('kurum.nigde'), {focus:false})")
            expect(page.locator("#v1-provider-badge")).to_have_text("PROJECT DATA")
            page.locator("#v1-provider-toggle").click()
            expect(page.locator("#v1-provider-shell")).to_have_attribute("aria-hidden", "false")
            expect(page.locator("#v1-provider-authority")).to_contain_text("SYNTHETIC / NOT_OFFICIAL")
            expect(page.locator("#v1-geometry-status")).to_contain_text("24 birimin tamamında")
            expect(page.locator("#parcelSelect option")).to_have_count(24)
            assert page.locator("#parcelSelect option").first.get_attribute("value") == "KDS-001"
            expect(page.locator(".leaflet-interactive")).to_have_count(24, timeout=30000)
            assert page.evaluate("document.querySelector('#map') === document.getElementById('map')")
            page.locator("#v1-provider-close").click()
            page.locator(".leaflet-interactive").nth(11).dispatch_event("click")
            expect(page.locator("#parcelSelect")).to_have_value("KDS-012")
            page.locator("#parcelSelect").select_option("KDS-005")
            expect(page.locator("#parcelSummaryTitle")).to_contain_text("KDS-005")
            page.locator("#parcelSelect").select_option("KDS-024")
            expect(page.locator("#parcelSummaryTitle")).to_contain_text("KDS-024")
            page.locator("#v1-provider-toggle").click()
            assert page.evaluate("window.__V1_PROJECT_PROVIDER__.context.capabilities.scenarios.S1.ready") is True
            for algorithm in ("aco", "abc", "ga"):
                page.locator("#algoSelect").select_option(algorithm)
                page.locator("#v1-provider-preview").click()
                expect(page.locator("#v1-provider-preview-state")).to_contain_text("PINNED", timeout=120000)
            for objective in ("maks_kar", "su_etkin", "su_tasarruf"):
                page.locator(f'input[name="scenario"][value="{objective}"]').check()
                page.locator("#v1-provider-preview").click()
                expect(page.locator("#v1-provider-preview-state")).to_contain_text("PINNED", timeout=120000)
            page.locator("#algoSelect").select_option("ga")
            page.locator("#seasonSourceSel").select_option("s1")
            page.locator('input[name="scenario"][value="su_tasarruf"]').check()
            page.locator("#v1-provider-seed").fill("123")
            page.locator("#v1-provider-preview").click()
            expect(page.locator("#v1-provider-preview-state")).to_contain_text("PINNED", timeout=120000)
            page.locator("#runOptBtn").click()
            expect(page.locator("#algoStatus")).to_contain_text("Tamamlandı", timeout=240000)
            expect(page.locator("#v1-project-result")).to_be_hidden()
            expect(page.locator("#v1-native-provenance")).to_contain_text("selection_hash")
            expect(page.locator("#activeObjectiveBadge")).to_contain_text("Su tasarrufu")
            run_id = next(iter(repository.get("native-full-visual")["runs"]))
            assert f"run_id={run_id}" in page.url
            assert not any("/api/parcels" in url or "/api/optimize" in url for url in requests)
            page.screenshot(path=str(EVIDENCE / "chromium_1366x900.png"), full_page=True)
            page.set_viewport_size({"width": 1920, "height": 1080})
            page.screenshot(path=str(EVIDENCE / "chromium_1920x1080.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            page.screenshot(path=str(EVIDENCE / "chromium_mobile_390x844.png"), full_page=True)
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.mark.browser
@pytest.mark.parametrize("query", [
    "provider=PROJECT_DATA&project_id=missing",
    "provider=PROJECT_DATA&project_id=%2Fmalformed",
    "provider=PROJECT_DATA&provider=AKKAYA_REFERENCE&project_id=missing",
    "provider=PROJECT_DATA&project_id=one&project_id=two",
    "provider=UNKNOWN",
])
def test_invalid_project_contexts_fail_closed_without_reference_requests(tmp_path, query):
    application, _, _ = client_for(tmp_path)
    _serve_v1(application)
    server, thread = serve(application)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.add_init_script(LEAFLET)
            requests = []
            page.on("request", lambda request: requests.append(request.url))
            page.route("https://**", lambda route: route.abort())
            page.goto(f"http://127.0.0.1:{server.server_port}/?{query}")
            expect(page.locator("#v1-provider-name")).to_contain_text(
                "PROJECT DATA", timeout=30000)
            expect(page.locator("#v1-provider-error")).to_contain_text("Akkaya", timeout=30000)
            assert not any("/api/parcels" in url or "/api/optimize" in url for url in requests)
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.mark.browser
def test_bulk_import_primary_guidance_is_turkish_and_raw_issues_are_secondary(tmp_path):
    application, client, _ = client_for(tmp_path)
    _serve_v1(application)
    assert client.post("/api/v2/projects", json={
        "id": "guidance-project", "name": "Yönlendirme Projesi", "planning_year": 2025,
        "annual_water_budget": 0, "water_budget_unit": "m3", "province_or_region": "Niğde",
        "data_source_notes": "user_provided",
    }).status_code == 201
    irrelevant = tmp_path / "meeting_notes.csv"
    irrelevant.write_text("note,owner\nmeeting agenda,office\n", encoding="utf-8")
    malformed = tmp_path / "analysis_units.csv"
    malformed.write_text(
        "external_id,settlement,area_da,current_crop\nGX-1,X,not-a-number,WHEAT\n",
        encoding="utf-8",
    )
    server, thread = serve(application)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.goto(
                f"http://127.0.0.1:{server.server_port}/projects"
                "#project=guidance-project&section=data"
            )
            page.locator('#bulk-upload-form input[type="file"]').set_input_files(
                [str(irrelevant), str(malformed)]
            )
            with page.expect_response(lambda response: response.url.endswith("/bulk-imports")):
                page.locator('#bulk-upload-form button[type="submit"]').click()
            expect(page.locator("#bulk-import-body tr")).to_have_count(2)
            irrelevant_row = page.locator("#bulk-import-body tr", has_text="meeting_notes.csv")
            irrelevant_row.locator("summary", has_text="Dosya önizlemesi").click()
            expect(irrelevant_row).to_contain_text("Türkçe kullanıcı yönlendirmesi")
            expect(irrelevant_row).to_contain_text("güvenilir yapısal kanıt bulunmadı")
            expect(irrelevant_row).to_contain_text("eksiksiz bir paketin aktivasyonunu engellemez")
            malformed_row = page.locator("#bulk-import-body tr", has_text="analysis_units.csv")
            malformed_row.locator("summary", has_text="Dosya önizlemesi").click()
            expect(malformed_row).to_contain_text("Sayısal olması gereken area_da")
            expect(malformed_row).to_contain_text("not-a-number")
            expect(page.locator("#bulk-confirm")).to_be_disabled()
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.mark.browser
def test_geometry_unit_mismatch_guidance_blocks_bulk_confirmation(tmp_path):
    application, client, repository = client_for(tmp_path)
    _serve_v1(application)
    assert client.post("/api/v2/projects", json={
        "id": "geometry-guidance", "name": "Geometri Projesi", "planning_year": 2025,
        "annual_water_budget": 0, "water_budget_unit": "m3", "province_or_region": "Niğde",
        "data_source_notes": "user_provided",
    }).status_code == 201
    service = ImportService(repository)
    units = service.upload(
        "geometry-guidance", "analysis_units", "analysis_units.csv",
        b"external_id,settlement,area_da,current_crop\nGX-001,X,10,WHEAT\n", {},
    )
    service.confirm("geometry-guidance", units["id"], True)
    geometry = tmp_path / "geometry.geojson"
    geometry.write_text(
        '{"type":"FeatureCollection","features":[{"type":"Feature",'
        '"properties":{"unit_id":"GX-999"},"geometry":{"type":"Point",'
        '"coordinates":[34.5,38.0]}}]}', encoding="utf-8",
    )
    server, thread = serve(application)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.goto(
                f"http://127.0.0.1:{server.server_port}/projects"
                "#project=geometry-guidance&section=data"
            )
            page.locator('#bulk-upload-form input[type="file"]').set_input_files(str(geometry))
            with page.expect_response(lambda response: response.url.endswith("/bulk-imports")):
                page.locator('#bulk-upload-form button[type="submit"]').click()
            row = page.locator("#bulk-import-body tr", has_text="geometry.geojson")
            row.locator("summary", has_text="Dosya önizlemesi").click()
            expect(row).to_contain_text("birim kimliği proje analiz birimleriyle eşleşmiyor")
            expect(row).to_contain_text("Geometri dosyasındaki kimlikleri")
            expect(page.locator("#bulk-confirm")).to_be_disabled()
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
