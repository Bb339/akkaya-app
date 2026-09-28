from __future__ import annotations

import pytest
from playwright.sync_api import expect, sync_playwright

from test_unified_decision_demo import client_for, project_payload
from test_unified_decision_demo_browser import serve


def assert_closed(page):
    expect(page.locator("#projects .project-card.active")).to_have_count(0)
    expect(page.locator("#detail")).to_be_hidden()
    expect(page.locator("#result")).to_be_hidden()
    expect(page.locator("#analysis-preview-card")).to_be_hidden()
    expect(page.locator("#stale-preview-alert")).to_be_hidden()
    expect(page.locator("#message")).to_be_visible()
    assert page.locator("#message").inner_text().strip()


def assert_open(page, project_id: str, name: str):
    active = page.locator("#projects .project-card.active")
    expect(active).to_have_count(1)
    expect(active).to_have_attribute("aria-label", name)
    expect(page.locator("#detail")).to_be_visible(timeout=15000)
    expect(page.locator("#project-name")).to_have_text(name)


@pytest.mark.browser
def test_project_hash_is_authoritative_and_all_missing_invalid_states_fail_closed(tmp_path):
    application, client, _ = client_for(tmp_path)
    first = project_payload("project-a")
    second = project_payload("project-b")
    second["name"] = "SECOND_INSTITUTIONAL_PROJECT"
    assert client.post("/api/v2/projects", json=first).status_code == 201
    assert client.post("/api/v2/projects", json=second).status_code == 201

    server, thread = serve(application)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            project_requests = []
            reference_requests = []
            page.on("request", lambda request: (
                project_requests.append(request.url) if "/api/v2/projects/" in request.url else None,
                reference_requests.append(request.url) if "/api/parcels" in request.url else None,
            ))
            base = f"http://127.0.0.1:{server.server_port}/projects"

            for suffix in ("", "#", "#project=", "#foo=bar", "#project=unknown", "#project=%E0%A4%A"):
                page.goto(base + suffix)
                assert_closed(page)
                assert not reference_requests

            page.goto(base + "#project=project-a")
            assert_open(page, "project-a", first["name"])
            assert page.url.endswith("#project=project-a")

            page.evaluate("location.hash = 'project=project-b'")
            assert_open(page, "project-b", second["name"])
            assert page.url.endswith("#project=project-b")

            page.evaluate("""
                document.getElementById('result').hidden = false;
                document.getElementById('analysis-preview-card').hidden = false;
                location.hash = '';
            """)
            expect(page.locator("#message")).to_contain_text("proje bağlamı eksik")
            assert_closed(page)

            page.evaluate("location.hash = 'foo=bar'")
            expect(page.locator("#message")).to_contain_text("project parametresi gerekli")
            assert_closed(page)

            page.evaluate("location.hash = 'project=unknown'")
            expect(page.locator("#message")).to_contain_text("proje bulunamadı: unknown")
            assert_closed(page)

            calls_before_recovery = len(project_requests)
            page.evaluate("location.hash = 'project=project-a'")
            assert_open(page, "project-a", first["name"])
            assert page.url.endswith("#project=project-a")
            assert any("/api/v2/projects/project-a" in url for url in project_requests[calls_before_recovery:])
            assert not reference_requests
            browser.close()
    finally:
        server.shutdown(); thread.join(timeout=5)


@pytest.mark.browser
def test_project_card_click_writes_canonical_hash(tmp_path):
    application, client, _ = client_for(tmp_path)
    project = project_payload("canonical-project")
    assert client.post("/api/v2/projects", json=project).status_code == 201
    server, thread = serve(application)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.goto(f"http://127.0.0.1:{server.server_port}/projects")
            assert_closed(page)
            page.locator(f'#projects .project-card[aria-label="{project["name"]}"]').click()
            assert page.url.endswith("/projects#project=canonical-project&section=project")
            assert_open(page, "canonical-project", project["name"])
            browser.close()
    finally:
        server.shutdown(); thread.join(timeout=5)

