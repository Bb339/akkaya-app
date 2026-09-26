from __future__ import annotations

import threading
from pathlib import Path

import pytest
from flask import Flask
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from kds.api import register_project_api
from kds.data.project_store import FileProjectStore


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "docs" / "unified_decision_demo" / "demo_upload_package"

LEAFLET_STUB = """
Object.defineProperty(window, 'L', {configurable: true, writable: true, value: {
  map(root) { return {_root:root,setView(){return this},fitBounds(){return this},remove(){root.replaceChildren()}} },
  tileLayer(){return {addTo(){return this}}},
  marker(coords){let handlers={};return {addTo(map){const el=document.createElement('button');el.type='button';el.className='leaflet-marker-icon';map._root.append(el);this._icon=el;return this},bindTooltip(){return this},on(name,fn){handlers[name]=fn;this._icon.onclick=()=>handlers.click?.();return this},getLatLng(){return coords}}},
  featureGroup(layers){return {getLayers(){return layers},getBounds(){return {pad(){return this}}}}},
  geoJSON(){throw new Error('Demo uses accepted coordinate markers, not a hidden geometry fallback')}
}});
"""


def serve(application):
    server = make_server("127.0.0.1", 0, application, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


@pytest.mark.browser
def test_akkaya_reference_thesis_screen_remains_operational_in_chromium():
    import app as thesis
    server, thread = serve(thesis.app)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.route("https://**", lambda route: route.abort())
            page.goto(f"http://127.0.0.1:{server.server_port}/", wait_until="domcontentloaded")
            expect(page).to_have_title("Tarımsal Karar Destek Sistemi")
            expect(page.locator("#panel")).to_be_attached()
            expect(page.locator('[data-project-workspace-link]')).to_have_text("Projeler / Kurumsal veri")
            count = page.evaluate("fetch('/api/parcels').then(r => r.json()).then(v => v.parcels.length)")
            assert count == 179
            status = page.evaluate("fetch('/api/meta').then(r => r.json()).then(v => v.status)")
            assert status
            browser.close()
    finally:
        server.shutdown(); thread.join(timeout=5)


@pytest.mark.browser
def test_missing_project_run_fails_closed_without_reference_requests(tmp_path):
    repository = FileProjectStore(tmp_path / "projects")
    application = Flask("unified-demo-fallback-guard")
    application.config["TESTING"] = True
    register_project_api(application, repository)
    server, thread = serve(application)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            requested = []
            page.on("request", lambda request: requested.append(request.url))
            page.route("https://**", lambda route: route.abort())
            page.goto(
                f"http://127.0.0.1:{server.server_port}/projects/decision"
                "?project_id=missing&run_id=missing&execution_profile=VERIFIED_INSTITUTIONAL"
            )
            expect(page.locator("#decision-title")).to_have_text("Karar ekranı açılamadı")
            expect(page.locator("#decision-subtitle")).to_contain_text("fallback uygulanmadı")
            assert not any("/api/parcels" in url or "/api/optimize" in url for url in requested)
            browser.close()
    finally:
        server.shutdown(); thread.join(timeout=5)


@pytest.mark.browser
def test_fresh_bulk_import_run_and_decision_bridge_in_chromium(tmp_path):
    repository = FileProjectStore(tmp_path / "projects")
    application = Flask("unified-demo-browser")
    application.config["TESTING"] = True
    register_project_api(application, repository)
    server, thread = serve(application)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.add_init_script(LEAFLET_STUB)
            page.route("https://**", lambda route: route.abort())
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{server.server_port}/projects")
            page.locator("details.form-drawer").first.locator("summary").click()
            form = page.locator("#create-project")
            form.locator('[name="id"]').fill("browser-unified-demo")
            form.locator('[name="name"]').fill("SYNTHETIC_INSTITUTIONAL_TEST_PROJECT")
            form.locator('[name="planning_year"]').fill("2025")
            form.locator('[name="province_or_region"]').fill("Synthetic Region")
            form.locator('[name="data_source_notes"]').select_option("synthetic not_official institutional integration fixture")
            with page.expect_response(lambda response: response.url.endswith("/api/v2/projects") and response.request.method == "POST"):
                form.locator('button').click()
            expect(page.locator("#synthetic-watermark")).to_be_visible()

            files = [str(path) for path in sorted(PACKAGE.iterdir())
                     if path.suffix.lower() in {".csv", ".xlsx", ".geojson"}]
            page.locator('#bulk-upload-form input[type="file"]').set_input_files(files)
            with page.expect_response(lambda response: response.url.endswith("/bulk-imports"), timeout=120000):
                page.locator('#bulk-upload-form button[type="submit"]').click()
            expect(page.locator("#bulk-import-body tr")).to_have_count(20)
            expect(page.locator("#bulk-import-body")).to_contain_text("AUTO_MATCHED")
            expect(page.locator("#bulk-confirm")).to_be_enabled()
            page.locator("#bulk-confirm").click()
            expect(page.locator("#message")).to_contain_text("Toplu paket açık onayla", timeout=180000)
            expect(page.locator("#readiness-verdict")).to_contain_text("VERIFIED READY")

            page.locator('#analysis-form [name="execution_profile"]').select_option("VERIFIED_INSTITUTIONAL")
            page.locator('#analysis-form [name="scenario"]').select_option("S1")
            page.locator('#analysis-form [name="algorithm"]').select_option("GA")
            page.locator('#analysis-form [name="objective"]').select_option("water_saving")
            page.locator('#analysis-form [name="seed"]').fill("123")
            with page.expect_response(lambda response: response.url.endswith("/analysis-preview"), timeout=120000):
                page.locator("#preview-analysis").click()
            expect(page.locator("#preview-ready-badge")).to_have_class("state-chip ready")
            expect(page.locator("#run-button")).to_be_enabled()
            with page.expect_response(lambda response: response.url.endswith("/analyses") and response.request.method == "POST", timeout=240000):
                page.locator("#run-button").click()
            expect(page.locator("#open-decision-screen")).to_be_visible()
            expect(page.locator("#result-source-label")).to_contain_text("SYNTHETIC / NOT OFFICIAL")
            page.locator("#open-decision-screen").click()
            page.wait_for_url("**/projects/decision?**")
            expect(page.locator(".mode-badge.verified")).to_have_text("VERIFIED INSTITUTIONAL")
            expect(page.locator("#decision-authority")).to_be_visible()
            expect(page.locator("#decision-title")).to_have_text("SYNTHETIC_INSTITUTIONAL_TEST_PROJECT")
            expect(page.locator("#result-source-label")).to_contain_text("SYNTHETIC / NOT OFFICIAL")
            expect(page.locator("#provenance-summary")).to_contain_text("Selection hash")
            expect(page.locator("#provenance-summary")).to_contain_text("Engine commit")
            expect(page.locator("#unit-list button")).to_have_count(24)
            expect(page.locator(".leaflet-marker-icon")).to_have_count(2)
            assert "AKKAYA" not in page.locator("#result-facts").inner_text()
            assert not errors
            browser.close()
    finally:
        server.shutdown(); thread.join(timeout=5)

