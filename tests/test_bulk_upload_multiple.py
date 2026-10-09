from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from scripts.import_v1_reference_dataset import project_payload
from test_unified_decision_demo import client_for
from test_unified_decision_demo_browser import serve


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "data" / "project_packages" / "v1_reference_dataset"
DATA_FILES = sorted(
    path for path in PACKAGE.iterdir()
    if path.suffix.lower() in {".csv", ".xlsx", ".xls", ".geojson", ".json"}
    and path.name not in {"SOURCE_MANIFEST.json", "DATASET_HASHES.json"}
)


def test_bulk_input_contract_is_multiple_and_verified_upload_stays_single():
    source = (ROOT / "kds" / "ui" / "templates" / "projects.html").read_text(encoding="utf-8")
    assert 'id="bulk-upload-files" type="file" name="files" multiple required' in source
    assert 'accept=".csv,.xlsx,.xls,.geojson,.json"' in source
    verified = source.split('id="upload-form"', 1)[1].split("</form>", 1)[0]
    assert 'name="file"' in verified and " multiple" not in verified


@pytest.mark.browser
def test_bulk_file_control_accepts_one_and_twenty_one_mixed_files(tmp_path):
    assert len(DATA_FILES) == 21
    assert {path.suffix.lower() for path in DATA_FILES} >= {".csv", ".geojson"}
    application, client, repository = client_for(tmp_path)
    assert client.post("/api/v2/projects", json=project_payload()).status_code == 201
    server, thread = serve(application)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.goto(
                f"http://127.0.0.1:{server.server_port}/projects?lang=en"
                "#project=v1-reference-demo&section=data"
            )
            expect(page.locator("#project-name")).to_have_text("V1 Reference Dataset", timeout=20000)
            control = page.locator("#bulk-upload-files")
            assert control.evaluate("input => input.multiple") is True
            assert control.get_attribute("accept") == ".csv,.xlsx,.xls,.geojson,.json"

            control.set_input_files(str(DATA_FILES[0]))
            assert control.evaluate("input => input.files.length") == 1

            control.set_input_files([str(path) for path in DATA_FILES])
            assert control.evaluate("input => input.files.length") == 21
            expect(page.locator("#bulk-upload-files + .paper-file-control .paper-file-status")).to_have_text(
                "21 files selected"
            )
            selected_extensions = control.evaluate(
                "input => [...input.files].map(file => file.name.split('.').pop().toLowerCase())"
            )
            assert "csv" in selected_extensions and "geojson" in selected_extensions

            with page.expect_response(
                lambda response: response.url.endswith("/bulk-imports"), timeout=180000
            ) as response_info:
                page.locator('#bulk-upload-form button[type="submit"]').click()
            assert response_info.value.status == 201
            expect(page.locator("#bulk-import-body tr")).to_have_count(21, timeout=180000)
            assert page.locator("#bulk-import-body tr", has_text="AUTO_MATCHED").count() == 21
            expect(page.locator("#bulk-confirm")).to_be_enabled()
            assert repository.get("v1-reference-demo")["data_revision"] == 0
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
