from __future__ import annotations

import pytest
from playwright.sync_api import expect, sync_playwright

from test_unified_decision_demo import client_for, project_payload
from test_unified_decision_demo_browser import serve


SECTIONS = ("project", "data", "readiness", "analysis", "result", "provenance", "reference")


def assert_project(page, name: str):
    active = page.locator("#projects .project-card.active")
    expect(active).to_have_count(1)
    expect(active).to_have_attribute("aria-label", name)
    expect(page.locator("#detail")).to_be_visible(timeout=15000)
    expect(page.locator("#project-name")).to_have_text(name)


def assert_closed(page):
    expect(page.locator("#projects .project-card.active")).to_have_count(0)
    expect(page.locator("#detail")).to_be_hidden()
    expect(page.locator("#message")).to_be_visible()


@pytest.mark.browser
def test_canonical_navigation_preserves_exact_project_and_browser_history(tmp_path):
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
            reference_requests = []
            page.on("request", lambda request: reference_requests.append(request.url)
                    if "/api/parcels" in request.url else None)
            base = f"http://127.0.0.1:{server.server_port}/projects"

            page.goto(base + "#project=project-a&section=project")
            assert_project(page, first["name"])
            for section in ("data", "readiness", "analysis", "result", "provenance", "reference"):
                page.locator(f'.workflow [data-project-section="{section}"]').click()
                page.wait_for_url(f"**#project=project-a&section={section}")
                assert_project(page, first["name"])

            page.locator(f'#projects .project-card[aria-label="{second["name"]}"]').click()
            page.wait_for_url("**#project=project-b&section=project")
            assert_project(page, second["name"])
            for section in ("data", "readiness", "analysis", "result", "provenance", "reference"):
                page.locator(f'.workflow [data-project-section="{section}"]').click()
                page.wait_for_url(f"**#project=project-b&section={section}")
                assert_project(page, second["name"])

            page.locator('.workflow [data-project-section="data"]').click()
            page.wait_for_url("**#project=project-b&section=data")
            page.locator('.workflow [data-project-section="readiness"]').click()
            page.wait_for_url("**#project=project-b&section=readiness")
            page.go_back()
            page.wait_for_url("**#project=project-b&section=data")
            assert_project(page, second["name"])
            page.go_forward()
            page.wait_for_url("**#project=project-b&section=readiness")
            assert_project(page, second["name"])
            assert not reference_requests
            browser.close()
    finally:
        server.shutdown(); thread.join(timeout=5)


@pytest.mark.browser
@pytest.mark.parametrize("section", SECTIONS)
def test_every_allowed_section_restores_exact_project_after_reload(tmp_path, section):
    application, client, _ = client_for(tmp_path)
    project = project_payload("reload-project")
    assert client.post("/api/v2/projects", json=project).status_code == 201
    server, thread = serve(application)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            url = (f"http://127.0.0.1:{server.server_port}/projects"
                   f"#project=reload-project&section={section}")
            page.goto(url)
            assert_project(page, project["name"])
            assert page.url == url
            page.reload()
            assert_project(page, project["name"])
            assert page.url == url
            browser.close()
    finally:
        server.shutdown(); thread.join(timeout=5)


@pytest.mark.browser
def test_invalid_sections_preserve_project_while_invalid_projects_fail_closed(tmp_path):
    application, client, _ = client_for(tmp_path)
    project = project_payload("exact-project")
    assert client.post("/api/v2/projects", json=project).status_code == 201
    server, thread = serve(application)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            base = f"http://127.0.0.1:{server.server_port}/projects"

            for suffix in (
                "#project=exact-project&section=unknown",
                "#project=exact-project&section=analysis&section=data",
                "#project=exact-project&section=%E0%A4%A",
            ):
                page.goto(base + suffix)
                assert_project(page, project["name"])
                assert page.url.endswith("#project=exact-project&section=project")
                expect(page.locator("#message")).to_be_visible()

            for suffix in (
                "", "#", "#analysis-section", "#project=", "#project=unknown",
                "#project=%E0%A4%A", "#project=exact-project&project=unknown&section=analysis",
            ):
                page.goto(base + suffix)
                assert_closed(page)

            browser.close()
    finally:
        server.shutdown(); thread.join(timeout=5)


@pytest.mark.browser
def test_section_navigation_preserves_loaded_result_context(tmp_path):
    application, client, _ = client_for(tmp_path)
    project = project_payload("result-project")
    assert client.post("/api/v2/projects", json=project).status_code == 201
    server, thread = serve(application)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.goto(f"http://127.0.0.1:{server.server_port}/projects#project=result-project&section=project")
            assert_project(page, project["name"])
            page.evaluate("""
                document.getElementById('result').hidden = false;
                document.getElementById('result-source-label').textContent = 'STORED_RESULT_SENTINEL';
            """)
            page.locator('.workflow [data-project-section="provenance"]').click()
            page.wait_for_url("**#project=result-project&section=provenance")
            page.locator('.workflow [data-project-section="result"]').click()
            page.wait_for_url("**#project=result-project&section=result")
            expect(page.locator("#result")).to_be_visible()
            expect(page.locator("#result-source-label")).to_have_text("STORED_RESULT_SENTINEL")
            assert_project(page, project["name"])
            browser.close()
    finally:
        server.shutdown(); thread.join(timeout=5)


@pytest.mark.browser
def test_project_creation_writes_canonical_project_section_state(tmp_path):
    application, _, _ = client_for(tmp_path)
    server, thread = serve(application)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.goto(f"http://127.0.0.1:{server.server_port}/projects")
            page.locator("#create-project").evaluate("form => form.parentElement.open = true")
            page.locator('#create-project [name="id"]').fill("created-project")
            page.locator('#create-project [name="name"]').fill("CREATED_PROJECT")
            page.locator("#create-project button").click()
            page.wait_for_url("**#project=created-project&section=project")
            assert_project(page, "CREATED_PROJECT")
            browser.close()
    finally:
        server.shutdown(); thread.join(timeout=5)
