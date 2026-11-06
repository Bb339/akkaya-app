from __future__ import annotations

import subprocess

import pytest
from playwright.sync_api import expect, sync_playwright

from test_unified_decision_demo import (
    analysis_payload, bulk_upload, client_for, confirm_bulk, project_payload,
)
from test_unified_decision_demo_browser import serve


@pytest.mark.browser
def test_provider_drawer_is_click_only_overlay_and_resets_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("KDS_PROJECT_STORE", str(tmp_path / "projects"))
    monkeypatch.setenv("KDS_DEPLOYMENT_MODE", "local-development")
    import app as thesis
    server, thread = serve(thesis.app)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1920, "height": 944})
            page.set_default_timeout(60000)
            page.route("https://**", lambda route: route.abort())
            page.goto(f"http://127.0.0.1:{server.server_port}/", wait_until="domcontentloaded")
            page.wait_for_function("window.__V1_PROJECT_PROVIDER__?.provider === 'AKKAYA_REFERENCE'")
            page.locator('[data-demo-user="kurum.nigde"]').click()
            page.locator("#loginForm").evaluate("form => form.requestSubmit()")
            expect(page.locator("#panel")).to_be_visible(timeout=15000)

            shell = page.locator("#v1-provider-shell")
            scrim = page.locator("#v1-provider-scrim")
            toggle = page.locator("#v1-provider-toggle")
            close = page.locator("#v1-provider-close")

            def rect(selector):
                return page.locator(selector).evaluate(
                    "node => { const r=node.getBoundingClientRect(); "
                    "return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right}; }"
                )

            def assert_closed(width):
                expect(shell).to_be_hidden()
                expect(shell).to_have_attribute("aria-hidden", "true")
                expect(shell).to_have_attribute("inert", "")
                expect(scrim).to_be_hidden()
                expect(toggle).to_have_attribute("aria-expanded", "false")
                assert page.evaluate("!document.body.classList.contains('v1-provider-drawer-open')")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                assert rect("#panel")["width"] <= width

            close_methods = ("button", "escape", "outside", "button")
            for (width, height), close_method in zip(
                ((1920, 944), (1536, 864), (1366, 768), (390, 844)), close_methods
            ):
                page.set_viewport_size({"width": width, "height": height})
                assert_closed(width)
                before = rect("#panel")

                toggle.hover()
                page.wait_for_timeout(100)
                assert_closed(width)

                toggle.click()
                expect(shell).to_be_visible()
                expect(shell).to_have_attribute("aria-hidden", "false")
                expect(toggle).to_have_attribute("aria-expanded", "true")
                expect(scrim).to_be_visible()
                after = rect("#panel")
                drawer = rect("#v1-provider-shell")
                assert abs(after["x"] - before["x"]) < 1
                assert abs(after["width"] - before["width"]) < 1
                assert drawer["x"] >= 0 and drawer["right"] <= width + 1
                assert drawer["width"] <= width
                expect(close).to_be_visible()

                if close_method == "button":
                    close.click()
                elif close_method == "escape":
                    page.keyboard.press("Escape")
                else:
                    scrim.click(position={"x": 8, "y": 8})
                assert_closed(width)
                closed = rect("#panel")
                assert abs(closed["x"] - before["x"]) < 1
                assert abs(closed["width"] - before["width"]) < 1

            page.evaluate("localStorage.setItem('v1-provider-drawer-open', 'true')")
            toggle.click()
            expect(shell).to_be_visible()
            page.reload(wait_until="domcontentloaded")
            page.wait_for_function("window.__V1_PROJECT_PROVIDER__?.provider === 'AKKAYA_REFERENCE'")
            assert_closed(390)
            page.evaluate("document.documentElement.style.zoom='125%'")
            assert_closed(390)
            browser.close()
    finally:
        server.shutdown(); thread.join(timeout=5)


@pytest.mark.browser
def test_v1_reference_boundary_is_visible_without_mutating_frozen_index(tmp_path, monkeypatch):
    current_object_before = subprocess.check_output(["git", "hash-object", "index.html"], text=True).strip()

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
            expect(banner.locator("summary")).to_have_text("Referans veri")
            assert banner.evaluate("node => node.open") is False
            banner.locator("summary").click()
            expect(banner).to_contain_text(
                "Referans/model verileriyle çalışır. Resmî su tahsisi veya saha doğrulaması yerine geçmez."
            )
            desktop_rect = banner.locator("span").bounding_box()
            assert desktop_rect and desktop_rect["x"] >= 0
            assert desktop_rect["x"] + desktop_rect["width"] <= 1366
            assert desktop_rect["y"] + desktop_rect["height"] <= 900
            page.set_viewport_size({"width": 390, "height": 844})
            narrow_rect = banner.locator("span").bounding_box()
            assert narrow_rect and narrow_rect["x"] >= 16
            assert narrow_rect["x"] + narrow_rect["width"] <= 374
            assert narrow_rect["y"] >= 0 and narrow_rect["y"] + narrow_rect["height"] <= 844
            banner.locator("summary").press("Enter")
            assert banner.evaluate("node => node.open") is False
            page.set_viewport_size({"width": 1366, "height": 900})
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
    current_object_after = subprocess.check_output(["git", "hash-object", "index.html"], text=True).strip()
    assert current_object_after == current_object_before


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
            page.set_default_timeout(240000)
            page.add_init_script(LEAFLET)
            page.route("https://**", lambda route: route.abort())
            decision = (f"http://127.0.0.1:{server.server_port}/"
                        f"?provider=PROJECT_DATA&project_id=unified-demo&run_id={run['id']}")
            page.goto(decision)
            page.wait_for_function("window.__V1_PROJECT_PROVIDER__?.context?.run?.id")
            expect(page.locator('input[name="scenario"][value="su_tasarruf"]')).to_be_checked()
            expect(page.locator("#v1-provider-name")).to_contain_text(project_name)
            expect(page.locator("#metricsTitle")).to_contain_text("Analiz Birimi Karar Özeti")
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
            expect(page.locator("#v1-provider-name")).to_contain_text(project_name)
            expect(page.locator("#metricsTitle")).to_contain_text("Analiz Birimi Karar Özeti")
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

