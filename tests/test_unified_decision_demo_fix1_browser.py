from __future__ import annotations

import subprocess

import pytest
from playwright.sync_api import expect, sync_playwright

from test_unified_decision_demo import (
    analysis_payload, bulk_upload, client_for, confirm_bulk, project_payload,
)
from test_unified_decision_demo_browser import serve


BASELINE = "a6d36d099544776d0610b3c868a3675b12da5b0e"


@pytest.mark.browser
def test_v1_reference_boundary_is_visible_without_mutating_frozen_index(tmp_path, monkeypatch):
    baseline_object = subprocess.check_output(
        ["git", "rev-parse", f"{BASELINE}:index.html"], text=True).strip()
    current_object = subprocess.check_output(["git", "hash-object", "index.html"], text=True).strip()
    assert current_object == baseline_object

    monkeypatch.setenv("KDS_PROJECT_STORE", str(tmp_path / "projects"))
    monkeypatch.setenv("KDS_DEPLOYMENT_MODE", "local-development")
    import app as thesis
    server, thread = serve(thesis.app)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.route("https://**", lambda route: route.abort())
            page.goto(f"http://127.0.0.1:{server.server_port}/", wait_until="domcontentloaded")
            demo_user = page.locator('[data-demo-user="kurum.nigde"]')
            expect(demo_user).to_be_visible(timeout=60000)
            demo_user.click()
            page.locator("#loginForm").evaluate("form => form.requestSubmit()")
            expect(page.locator("#panel")).to_be_visible(timeout=15000)
            banner = page.locator("[data-reference-mode-banner]")
            expect(banner).to_be_visible()
            expect(banner).to_contain_text("AKKAYA REFERENCE")
            expect(banner).to_contain_text("REFERENCE MODEL / DEMO DATA")
            expect(banner).to_contain_text("NOT OFFICIAL / NOT FIELD VALIDATED")
            expect(banner).to_contain_text("Bakanlık onaylı öneri değildir")
            count = page.evaluate("fetch('/api/parcels').then(r => r.json()).then(v => v.parcels.length)")
            assert count == 179
            link = page.locator("[data-project-workspace-link]")
            expect(link).to_be_visible()
            link.click()
            page.wait_for_url("**/projects")
            expect(page.locator("#global-mode-badge")).to_contain_text("REFERENCE MODEL")
            assert not errors
            browser.close()
    finally:
        server.shutdown(); thread.join(timeout=5)


@pytest.mark.browser
def test_native_v1_exact_project_run_and_workspace_return(tmp_path):
    application, client, _ = client_for(tmp_path)
    project_name = project_payload()["name"]
    from test_unified_v1_project_provider_browser import LEAFLET, _serve_v1
    _serve_v1(application)
    assert client.post("/api/v2/projects", json=project_payload()).status_code == 201
    items = bulk_upload(client)
    confirm_bulk(client, items)
    payload = analysis_payload()
    preview = client.post("/api/v2/projects/unified-demo/analysis-preview", json=payload).json
    run_payload = {**payload, **{key: preview[key]
                                for key in ("preview_token", "preview_revision", "selection_hash")}}
    run = client.post("/api/v2/projects/unified-demo/analyses", json=run_payload).json
    server, thread = serve(application)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.add_init_script(LEAFLET)
            page.route("https://**", lambda route: route.abort())
            decision = (f"http://127.0.0.1:{server.server_port}/"
                        f"?provider=PROJECT_DATA&project_id=unified-demo&run_id={run['id']}")
            page.goto(decision)
            page.wait_for_function("window.__V1_PROJECT_PROVIDER__?.context?.run?.id")
            expect(page.locator("#metricsTitle")).to_contain_text(project_name)
            expect(page.locator("#v1-provider-authority")).to_have_text("SYNTHETIC / NOT_OFFICIAL")
            expect(page.locator("#buildMetaBox")).to_contain_text(run["id"])
            assert page.evaluate("document.querySelector('#v1-native-project-results') === null")
            page.goto(f"http://127.0.0.1:{server.server_port}/projects#project=unified-demo&section=result")
            expect(page.locator(f'#projects .project-card[aria-label="{project_name}"]')).to_have_class(
                "project-card active")
            expect(page.locator("#detail")).to_be_visible()
            expect(page.locator("#project-name")).to_have_text(project_name)
            expect(page.locator("#hero-project-meta")).to_contain_text("2025")
            expect(page.locator("#synthetic-watermark")).to_be_visible()
            page.locator("#history button", has_text=run["id"]).click()
            reopen = page.locator("#open-decision-screen")
            expect(reopen).to_be_visible(timeout=15000)
            assert f"run_id={run['id']}" in reopen.get_attribute("href")
            reopen.click()
            page.wait_for_url(f"**run_id={run['id']}**")
            page.wait_for_function("window.__V1_PROJECT_PROVIDER__?.context?.run?.id")
            expect(page.locator("#metricsTitle")).to_contain_text(project_name)
            expect(page.locator("#buildMetaBox")).to_contain_text(run["id"])
            browser.close()
    finally:
        server.shutdown(); thread.join(timeout=5)


@pytest.mark.browser
def test_missing_hash_project_fails_closed_with_explicit_message(tmp_path):
    application, client, _ = client_for(tmp_path)
    assert client.post("/api/v2/projects", json=project_payload("existing-project")).status_code == 201
    server, thread = serve(application)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.goto(f"http://127.0.0.1:{server.server_port}/projects#project=existing-project")
            expect(page.locator("#projects .project-card.active")).to_have_count(1)
            expect(page.locator("#detail")).to_be_visible()
            page.evaluate("location.hash = 'project=missing-project'")
            expect(page.locator("#message")).to_contain_text("Hash bağlamındaki proje bulunamadı: missing-project")
            expect(page.locator("#detail")).to_be_hidden()
            expect(page.locator("#projects .project-card.active")).to_have_count(0)
            browser.close()
    finally:
        server.shutdown(); thread.join(timeout=5)

