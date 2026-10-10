from __future__ import annotations

import io
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from test_unified_decision_demo import PRIORITY, client_for
from test_unified_decision_demo_browser import serve


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "data" / "project_packages" / "v1_reference_dataset"
DATA_FILES = sorted(
    path for path in PACKAGE.iterdir()
    if path.suffix.lower() in {".csv", ".xlsx", ".xls", ".geojson", ".json"}
    and path.name not in {"SOURCE_MANIFEST.json", "DATASET_HASHES.json"}
)
EVIDENCE_FILES = [PACKAGE / "DATASET_HASHES.json", PACKAGE / "SOURCE_MANIFEST.json"]


def project_payload(project_id="v1-reference-demo"):
    return {
        "id": project_id, "name": "V1 Reference Dataset", "planning_year": 2024,
        "annual_water_budget": 100700080.81, "water_budget_unit": "m3",
        "province_or_region": "Akkaya reference area", "data_source_notes": "reference_demo",
    }


def upload(client, project_id="v1-reference-demo", files=DATA_FILES):
    return client.post(
        f"/api/v2/projects/{project_id}/bulk-imports",
        data={"files": [(io.BytesIO(path.read_bytes()), path.name) for path in files]},
        content_type="multipart/form-data",
    )


def apply_package(client, package, project_id="v1-reference-demo"):
    items = sorted(package["items"], key=lambda item: PRIORITY[item["detection"]["detected_data_type"]])
    for item in items:
        batch_id = item["batch"]["id"]
        mapped = client.post(
            f"/api/v2/projects/{project_id}/imports/{batch_id}/mapping",
            json={"mapping": item["detection"]["mapping"]},
        )
        assert mapped.status_code == 200 and mapped.json["status"] == "ready"
        confirmed = client.post(
            f"/api/v2/projects/{project_id}/imports/{batch_id}/confirm",
            json={"confirm": True, "acknowledge_warnings": True},
        )
        assert confirmed.status_code == 200 and confirmed.json["status"] == "applied"


def test_pending_duplicate_reopens_discard_allows_retry_and_applied_is_immutable(tmp_path):
    _, client, repository = client_for(tmp_path)
    assert client.post("/api/v2/projects", json=project_payload()).status_code == 201

    first = upload(client)
    assert first.status_code == 201
    package = first.json
    assert package["file_count"] == package["auto_matched"] == 21
    assert package["unsupported"] == package["review_required"] == 0
    assert package["status"] == "READY" and repository.get("v1-reference-demo")["data_revision"] == 0

    duplicate = upload(client)
    assert duplicate.status_code == 200
    assert duplicate.json["id"] == package["id"]
    assert duplicate.json["duplicate"] is True
    assert duplicate.json["message"] == (
        "An identical validated import already exists. The existing import has been reopened."
    )
    assert len(duplicate.json["items"]) == 21

    discarded = client.delete(
        f"/api/v2/projects/v1-reference-demo/bulk-imports/{package['id']}"
    )
    assert discarded.status_code == 200 and discarded.json["status"] == "DISCARDED"
    assert repository.get("v1-reference-demo")["data_revision"] == 0

    retried = upload(client)
    assert retried.status_code == 201
    assert retried.json["id"] != package["id"]
    assert retried.json["file_count"] == retried.json["auto_matched"] == 21
    apply_package(client, retried.json)
    assert repository.get("v1-reference-demo")["data_revision"] == 21

    applied_duplicate = upload(client)
    assert applied_duplicate.status_code == 200
    assert applied_duplicate.json["id"] == retried.json["id"]
    assert applied_duplicate.json["status"] == "APPLIED"
    assert applied_duplicate.json["applied_revision"] == 21
    assert applied_duplicate.json["message"] == (
        "This dataset package has already been applied to the project."
    )
    refused = client.delete(
        f"/api/v2/projects/v1-reference-demo/bulk-imports/{retried.json['id']}"
    )
    assert refused.status_code == 409


def test_23_file_manifest_does_not_block_the_correct_21_file_manifest(tmp_path):
    _, client, _ = client_for(tmp_path)
    assert client.post("/api/v2/projects", json=project_payload()).status_code == 201
    oversized = upload(client, files=[*DATA_FILES, *EVIDENCE_FILES])
    assert oversized.status_code == 201
    assert oversized.json["file_count"] == 23
    correct = upload(client)
    assert correct.status_code == 200
    assert correct.json["id"] != oversized.json["id"]
    assert correct.json["manifest_hash"] != oversized.json["manifest_hash"]
    assert correct.json["file_count"] == correct.json["auto_matched"] == 21


def test_legacy_pending_file_batches_are_reopened_as_a_bulk_package(tmp_path):
    _, client, repository = client_for(tmp_path)
    assert client.post("/api/v2/projects", json=project_payload()).status_code == 201
    initial = upload(client)
    assert initial.status_code == 201
    legacy_batch_ids = {item["batch"]["id"] for item in initial.json["items"]}
    repository.update("v1-reference-demo", lambda document: document.update(bulk_imports={}))

    reopened = upload(client)
    assert reopened.status_code == 200
    assert reopened.json["duplicate"] is True
    assert reopened.json["status"] == "READY"
    assert reopened.json["message"] == (
        "An identical validated import already exists. The existing import has been reopened."
    )
    assert {item["batch"]["id"] for item in reopened.json["items"]} == legacy_batch_ids
    assert len(repository.get("v1-reference-demo")["imports"]) == 21


@pytest.mark.browser
def test_browser_resumes_discards_reuploads_and_recognizes_applied_package(tmp_path):
    application, client, repository = client_for(tmp_path)
    assert client.post("/api/v2/projects", json=project_payload()).status_code == 201
    server, thread = serve(application)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.goto(
                f"http://127.0.0.1:{server.server_port}/projects?lang=en"
                "#project=v1-reference-demo&section=data"
            )
            control = page.locator("#bulk-upload-files")
            control.set_input_files([str(path) for path in DATA_FILES])

            with page.expect_response(lambda response: response.url.endswith("/bulk-imports")
                                      and response.request.method == "POST", timeout=180000) as first:
                page.locator('#bulk-upload-form button[type="submit"]').click()
            assert first.value.status == 201
            first_id = first.value.json()["id"]
            expect(page.locator("#bulk-import-body tr")).to_have_count(21, timeout=180000)

            with page.expect_response(lambda response: response.url.endswith("/bulk-imports")
                                      and response.request.method == "POST", timeout=180000) as duplicate:
                page.locator('#bulk-upload-form button[type="submit"]').click()
            assert duplicate.value.status == 200 and duplicate.value.json()["id"] == first_id
            expect(page.locator("#bulk-import-note")).to_have_text(
                "An identical validated import already exists. The existing import has been reopened."
            )
            expect(page.locator("#bulk-import-body tr")).to_have_count(21)
            expect(page.locator("#bulk-confirm")).to_be_enabled()
            expect(page.locator("#bulk-resume")).to_be_visible()
            expect(page.locator("#bulk-discard")).to_be_visible()

            with page.expect_response(lambda response: response.request.method == "DELETE"
                                      and f"/bulk-imports/{first_id}" in response.url) as discarded:
                page.locator("#bulk-discard").click()
            assert discarded.value.status == 200
            assert repository.get("v1-reference-demo")["data_revision"] == 0

            control.set_input_files([str(path) for path in DATA_FILES])
            with page.expect_response(lambda response: response.url.endswith("/bulk-imports")
                                      and response.request.method == "POST", timeout=180000) as retry:
                page.locator('#bulk-upload-form button[type="submit"]').click()
            assert retry.value.status == 201 and retry.value.json()["id"] != first_id
            expect(page.locator("#bulk-confirm")).to_be_enabled()

            page.locator("#bulk-confirm").click()
            expect(page.locator("#message")).to_contain_text(
                "Toplu paket açık onayla projeye uygulandı.", timeout=900000
            )
            assert repository.get("v1-reference-demo")["data_revision"] == 21

            with page.expect_response(lambda response: response.url.endswith("/bulk-imports")
                                      and response.request.method == "POST", timeout=180000) as applied:
                page.locator('#bulk-upload-form button[type="submit"]').click()
            assert applied.value.status == 200 and applied.value.json()["status"] == "APPLIED"
            expect(page.locator("#bulk-import-note")).to_have_text(
                "This dataset package has already been applied to the project."
            )
            expect(page.locator("#bulk-confirm")).to_be_disabled()
            expect(page.locator("#imports")).to_contain_text("APPLIED")
            assert not page_errors
            browser.close()
    finally:
        server.shutdown(); thread.join(timeout=5)
