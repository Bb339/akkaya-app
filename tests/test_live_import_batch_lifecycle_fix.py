from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from flask import Flask
from playwright.sync_api import expect, sync_playwright

from kds.api import register_project_api
from kds.data.project_store import FileProjectStore
from test_unified_decision_demo import PRIORITY, project_payload
from test_unified_decision_demo_browser import serve


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "docs" / "unified_v1_project_provider" / "demo_full_visual_package"


def package_files() -> list[Path]:
    return [path for path in sorted(PACKAGE.iterdir())
            if path.suffix.lower() in {".csv", ".xlsx", ".geojson"}]


def new_client(store: Path):
    application = Flask("live-import-request-boundary")
    application.config["TESTING"] = True
    register_project_api(application, FileProjectStore(store))
    return application.test_client()


def test_accepted_21_file_batch_survives_real_request_and_store_boundaries(tmp_path):
    store = tmp_path / "projects"
    project_id = "live-import-boundary"
    other_id = "other-live-project"

    assert new_client(store).post("/api/v2/projects", json=project_payload(project_id)).status_code == 201
    assert new_client(store).post("/api/v2/projects", json=project_payload(other_id)).status_code == 201

    files = [(io.BytesIO(path.read_bytes()), path.name) for path in package_files()]
    uploaded = new_client(store).post(
        f"/api/v2/projects/{project_id}/bulk-imports",
        data={"files": files},
        content_type="multipart/form-data",
    )
    assert uploaded.status_code == 201, uploaded.json
    package = uploaded.json
    assert len(package["items"]) == package["auto_matched"] == 21
    assert package["review_required"] == package["ignored_not_relevant"] == 0
    assert {item["detection"]["state"] for item in package["items"]} == {"AUTO_MATCHED"}

    batch_ids = [item["batch"]["id"] for item in package["items"]]
    state_path = store / project_id / "state.json"
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert set(batch_ids) <= set(persisted["imports"])
    assert persisted["data_revision"] == 0

    first_batch = batch_ids[0]
    wrong_project = new_client(store).post(
        f"/api/v2/projects/{other_id}/imports/{first_batch}/confirm",
        json={"confirm": True, "acknowledge_warnings": True},
    )
    assert wrong_project.status_code == 404
    assert wrong_project.json == {"error": "Import batch not found in this project."}
    unknown = new_client(store).post(
        f"/api/v2/projects/{project_id}/imports/unknown-batch/confirm",
        json={"confirm": True, "acknowledge_warnings": True},
    )
    assert unknown.status_code == 404
    assert unknown.json == {"error": "Import batch not found in this project."}

    ordered = sorted(package["items"], key=lambda row: PRIORITY[row["detection"]["detected_data_type"]])
    for item in ordered:
        batch_id = item["batch"]["id"]
        mapped = new_client(store).post(
            f"/api/v2/projects/{project_id}/imports/{batch_id}/mapping",
            json={"mapping": item["detection"]["mapping"]},
        )
        assert mapped.status_code == 200 and mapped.json["status"] == "ready", mapped.json
        confirmed = new_client(store).post(
            f"/api/v2/projects/{project_id}/imports/{batch_id}/confirm",
            json={"confirm": True, "acknowledge_warnings": True},
        )
        assert confirmed.status_code == 200 and confirmed.json["status"] == "applied", confirmed.json

    repository = FileProjectStore(store)
    document = repository.get(project_id)
    assert document["data_revision"] == 21
    assert len(document["analysis_units"]) == 24
    assert sum(bool(unit.get("geometry")) for unit in document["analysis_units"]) == 24
    assert len(document["crops"]) == 8
    assert len({row["analysis_unit_id"] for row in document["scientific_inputs"]["candidates"]}) == 24

    consumed = new_client(store).post(
        f"/api/v2/projects/{project_id}/imports/{first_batch}/confirm",
        json={"confirm": True, "acknowledge_warnings": True},
    )
    assert consumed.status_code == 200
    assert consumed.json["status"] == "applied"
    assert FileProjectStore(store).get(project_id)["data_revision"] == 21

    context = new_client(store).get(
        f"/api/v2/projects/{project_id}/decision-context?scenario=S1"
    )
    assert context.status_code == 200
    assert context.json["unit_count"] == context.json["candidate_unit_count"] == 24
    assert context.json["geometry"] == {
        "available": 24, "total": 24, "coverage": "FULL", "fabricated": False,
    }

    request = {
        "execution_profile": "VERIFIED_INSTITUTIONAL", "scenario": "S1",
        "algorithm": "GA", "seed": 123, "objective": "water_saving",
        "water_budget_ratio": 1.0,
        "config": {"popSize": 12, "generations": 10, "cxRate": .7, "mutRate": .08},
    }
    preview = new_client(store).post(
        f"/api/v2/projects/{project_id}/analysis-preview", json=request
    )
    assert preview.status_code == 200 and preview.json["ready"] is True
    run = new_client(store).post(
        f"/api/v2/projects/{project_id}/analyses",
        json={**request, **{key: preview.json[key]
                            for key in ("preview_token", "preview_revision", "selection_hash")}},
    )
    assert run.status_code == 201, run.json
    run_id = run.json["id"]
    reloaded = new_client(store).get(f"/api/v2/projects/{project_id}/analyses/{run_id}")
    assert reloaded.status_code == 200
    assert reloaded.json["id"] == run_id
    assert reloaded.json == run.json


@pytest.mark.browser
def test_bulk_preview_is_cleared_when_project_context_changes(tmp_path):
    store = tmp_path / "projects"
    application = Flask("live-import-project-binding")
    application.config["TESTING"] = True
    register_project_api(application, FileProjectStore(store))
    client = application.test_client()
    for project_id, name in (("preview-project-a", "Preview Project A"),
                             ("preview-project-b", "Preview Project B")):
        payload = project_payload(project_id)
        payload["name"] = name
        assert client.post("/api/v2/projects", json=payload).status_code == 201

    server, thread = serve(application)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            requests = []
            page.on("request", lambda request: requests.append((request.method, request.url)))
            page.goto(
                f"http://127.0.0.1:{server.server_port}/projects"
                "#project=preview-project-a&section=data"
            )
            expect(page.locator("#project-name")).to_have_text("Preview Project A", timeout=20000)
            source = PACKAGE / "analysis_units.csv"
            page.locator('#bulk-upload-form input[type="file"]').set_input_files(str(source))
            with page.expect_response(lambda response: response.url.endswith("/bulk-imports")):
                page.locator('#bulk-upload-form button[type="submit"]').click()
            expect(page.locator("#bulk-import-body tr")).to_have_count(1)
            expect(page.locator("#bulk-confirm")).to_be_enabled()

            page.locator('.project-card[aria-label="Preview Project B"]').click()
            expect(page.locator("#project-name")).to_have_text("Preview Project B")
            assert page.url.endswith("#project=preview-project-b&section=project")
            expect(page.locator("#bulk-import-results")).to_be_hidden()
            expect(page.locator("#bulk-import-body tr")).to_have_count(0)
            expect(page.locator("#bulk-confirm")).to_be_disabled()
            assert not any(
                method == "POST" and "/projects/preview-project-b/imports/" in url
                for method, url in requests
            )
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
