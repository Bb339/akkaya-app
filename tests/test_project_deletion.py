from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import pytest
from playwright.sync_api import expect, sync_playwright

from test_unified_decision_demo import client_for, project_payload
from test_unified_decision_demo_browser import serve


def create(client, project_id: str, name: str):
    payload = project_payload(project_id)
    payload["name"] = name
    assert client.post("/api/v2/projects", json=payload).status_code == 201


def test_project_delete_endpoint_removes_project(tmp_path):
    application, client, repository = client_for(tmp_path)
    matching = [rule for rule in application.url_map.iter_rules()
                if rule.rule == "/api/v2/projects/<project_id>"]
    assert matching and any("DELETE" in rule.methods for rule in matching)
    create(client, "delete-me", "Delete Me")
    response = client.delete("/api/v2/projects/delete-me")
    assert response.status_code == 200
    assert response.json == {"deleted": True, "project": {"id": "delete-me", "name": "Delete Me"}}
    assert client.get("/api/v2/projects/delete-me").status_code == 404
    assert not (repository.root / "delete-me").exists()


def test_delete_project_removes_project_revisions(tmp_path):
    _, client, repository = client_for(tmp_path)
    create(client, "revision-project", "Revision Project")
    repository.update("revision-project", lambda document: document.update(
        data_revision=7,
        analysis_units=[{"external_id": "GX-001", "geometry": {"type": "Polygon", "coordinates": []}}],
        metadata={"selection_hash": "project-only-hash", "geometry_revision": 7},
    ))
    assert client.delete("/api/v2/projects/revision-project").status_code == 200
    assert not (repository.root / "revision-project").exists()


def test_delete_project_removes_stored_runs(tmp_path):
    _, client, repository = client_for(tmp_path)
    create(client, "run-project", "Run Project")
    repository.update("run-project", lambda document: document.update(
        runs={"run-1": {"id": "run-1", "provenance": {"project_id": "run-project"}}},
        imports={"batch-1": {"id": "batch-1", "project_id": "run-project"}},
    ))
    assert client.delete("/api/v2/projects/run-project").status_code == 200
    assert not (repository.root / "run-project").exists()


def test_delete_project_does_not_affect_other_projects(tmp_path):
    _, client, repository = client_for(tmp_path)
    create(client, "project-a", "Project A")
    create(client, "project-b", "Project B")
    before = repository.get("project-b")
    assert client.delete("/api/v2/projects/project-a").status_code == 200
    assert repository.get("project-b") == before


@pytest.mark.parametrize("project_id", [
    "akkaya-reference-demo", "akkaya-reference-model", "accepted-akkaya-reference-model",
])
def test_builtin_reference_demo_cannot_be_deleted(tmp_path, project_id):
    _, client, _ = client_for(tmp_path)
    response = client.delete(f"/api/v2/projects/{project_id}")
    assert response.status_code == 403
    assert response.json["error"] == "This built-in reference demo cannot be deleted."


def test_reference_demo_classification_remains_deletable(tmp_path):
    _, client, _ = client_for(tmp_path)
    payload = project_payload("v1-reference-demo")
    payload["data_source_notes"] = "reference_demo"
    assert client.post("/api/v2/projects", json=payload).status_code == 201
    assert client.delete("/api/v2/projects/v1-reference-demo").status_code == 200


def test_projects_page_without_hash_is_valid():
    source = Path("kds/ui/static/projects.js").read_text(encoding="utf-8")
    assert "if(!fragment)return {id:null,section:DEFAULT_SECTION,sectionIssue:null,error:null};" in source
    assert "if(requested.id===null){clearProjectContext(container);return;}" in source


def test_projects_page_without_hash_has_no_error_toast():
    source = Path("kds/ui/static/projects.js").read_text(encoding="utf-8")
    assert "if(reason)message(reason,true);else message('');" in source


def test_project_delete_confirmation_ui():
    template = Path("kds/ui/templates/projects.html").read_text(encoding="utf-8")
    assert 'id="delete-project-dialog"' in template
    assert 'id="delete-project-name"' in template
    assert 'id="delete-project-id"' in template
    assert 'id="cancel-project-delete"' in template
    assert 'id="confirm-project-delete"' in template


@pytest.mark.browser
def test_delete_active_project_clears_ui_context(tmp_path):
    application, client, _ = client_for(tmp_path)
    create(client, "project-a", "Project A")
    create(client, "project-b", "Project B")
    server, thread = serve(application)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page_errors = []
            failed_api = []
            delete_requests = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.on("request", lambda request: delete_requests.append(request.url)
                    if request.method == "DELETE" else None)
            page.on("response", lambda response: failed_api.append((response.status, response.url))
                    if "/api/v2/" in response.url and response.status >= 400 else None)
            base = f"http://127.0.0.1:{server.server_port}/projects"

            page.goto(base)
            expect(page.locator("#message")).to_be_hidden()
            expect(page.locator("#hero-project-name")).to_have_text("Proje seçilmedi")

            card_a = page.locator('.project-card[aria-label="Project A"]')
            card_a.click()
            expect(page.locator("#project-name")).to_have_text("Project A", timeout=20000)
            card_a.locator("xpath=..").locator(".project-delete-trigger").click()
            dialog = page.locator("#delete-project-dialog")
            expect(dialog).to_be_visible()
            expect(page.locator("#delete-project-name")).to_have_text("Project A")
            expect(page.locator("#delete-project-id")).to_have_text("project-a")

            page.locator("#cancel-project-delete").click()
            expect(dialog).to_be_hidden()
            expect(card_a).to_have_count(1)
            assert client.get("/api/v2/projects/project-a").status_code == 200

            card_a.locator("xpath=..").locator(".project-delete-trigger").click()
            with page.expect_response(lambda response: response.url.endswith("/api/v2/projects/project-a")
                                      and response.request.method == "DELETE") as deleted:
                page.locator("#confirm-project-delete").click()
            assert deleted.value.status == 200
            assert [urlparse(url).path for url in delete_requests] == [
                "/api/v2/projects/project-a"
            ]
            assert "/projects/project-a" not in [urlparse(url).path for url in delete_requests]
            expect(card_a).to_have_count(0)
            expect(page.locator("#detail")).to_be_hidden()
            expect(page.locator("#result")).to_be_hidden()
            expect(page.locator("#hero-project-name")).to_have_text("Proje seçilmedi")
            expect(page.locator("#message")).to_contain_text("Proje silindi: Project A")
            assert page.url == base

            card_b = page.locator('.project-card[aria-label="Project B"]')
            expect(card_b).to_have_count(1)
            card_b.click()
            expect(page.locator("#project-name")).to_have_text("Project B", timeout=20000)
            page.reload()
            expect(page.locator('.project-card[aria-label="Project A"]')).to_have_count(0)
            expect(page.locator("#project-name")).to_have_text("Project B", timeout=20000)

            failed_api.clear()
            page.goto(base + "#project=project-a&section=data")
            expect(page.locator("#message")).to_contain_text("proje bulunamadı: project-a")
            expect(page.locator("#detail")).to_be_hidden()
            assert not page_errors
            assert not failed_api
            browser.close()
    finally:
        server.shutdown(); thread.join(timeout=5)


@pytest.mark.browser
def test_cancel_delete_keeps_project(tmp_path):
    application, client, _ = client_for(tmp_path)
    create(client, "keep-project", "Keep Project")
    server, thread = serve(application)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{server.server_port}/projects")
            shell = page.locator('.project-card[aria-label="Keep Project"]').locator("xpath=..")
            shell.locator(".project-delete-trigger").click()
            page.locator("#cancel-project-delete").click()
            expect(page.locator('.project-card[aria-label="Keep Project"]')).to_have_count(1)
            assert client.get("/api/v2/projects/keep-project").status_code == 200
            browser.close()
    finally:
        server.shutdown(); thread.join(timeout=5)


def test_deleted_project_hash_fails_cleanly():
    source = Path("kds/ui/static/projects.js").read_text(encoding="utf-8")
    assert "Hash bağlamındaki proje bulunamadı" in source


@pytest.mark.browser
def test_html_method_error_is_sanitized_and_project_remains(tmp_path):
    application, client, _ = client_for(tmp_path)
    create(client, "error-project", "Error Project")
    server, thread = serve(application)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.route("**/api/v2/projects/error-project", lambda route: route.fulfill(
                status=405,
                content_type="text/html",
                body="<!doctype html><title>405 Method Not Allowed</title>",
            ) if route.request.method == "DELETE" else route.continue_())
            page.goto(f"http://127.0.0.1:{server.server_port}/projects")
            shell = page.locator('.project-card[aria-label="Error Project"]').locator("xpath=..")
            shell.locator(".project-delete-trigger").click()
            page.locator("#confirm-project-delete").click()
            expect(page.locator("#message")).to_have_text(
                "Project deletion failed (405 Method Not Allowed)."
            )
            expect(page.locator("#message")).not_to_contain_text("doctype")
            expect(page.locator('.project-card[aria-label="Error Project"]')).to_have_count(1)
            assert client.get("/api/v2/projects/error-project").status_code == 200
            browser.close()
    finally:
        server.shutdown(); thread.join(timeout=5)
