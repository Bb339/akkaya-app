from __future__ import annotations

from pathlib import Path

import pytest
from flask import send_from_directory
from playwright.sync_api import expect, sync_playwright

from test_unified_decision_demo import PACKAGE, client_for
from test_unified_decision_demo_browser import serve


ROOT = Path(__file__).resolve().parents[1]
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
            expect(page.locator("#v1-project-result")).to_be_visible(timeout=240000)
            expect(page.locator("#v1-project-result-summary")).to_contain_text("SYNTHETIC / NOT_OFFICIAL")
            expect(page.locator("#v1-project-crops")).to_contain_text("Ürün kompozisyonu")
            expect(page.locator("#v1-project-monthly")).to_contain_text("Aylık su doğrulaması")
            expect(page.locator("#v1-project-units")).to_contain_text("GX-001")
            expect(page.locator("#v1-project-provenance")).to_contain_text("selection_hash")
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
            expect(page.locator("#v1-project-result")).to_be_visible(timeout=30000)
            expect(page.locator("#v1-project-provenance")).to_contain_text(run_id)
            project_errors = list(errors)
            assert not [error for error in project_errors
                        if "PROJECT_DATA" not in error and "reference endpoint engellendi" not in error]
            page.locator("#v1-reference-provider").click()
            page.wait_for_url(f"http://127.0.0.1:{server.server_port}/")
            expect(page.locator("#v1-provider-name")).to_have_text("AKKAYA REFERENCE")
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
