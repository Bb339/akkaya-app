from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

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
    assert '<option value="reference_demo">REFERENCE / DEMO DATA</option>' in source
    assert 'Hesaplanmış referans suyu / Başlangıç planlama suyu (m³)' in source
    verified = source.split('id="upload-form"', 1)[1].split("</form>", 1)[0]
    assert 'name="file"' in verified and " multiple" not in verified


@pytest.mark.browser
def test_bulk_file_control_accepts_one_and_twenty_one_mixed_files(tmp_path):
    assert len(DATA_FILES) == 21
    assert {path.suffix.lower() for path in DATA_FILES} >= {".csv", ".geojson"}
    application, _, repository = client_for(tmp_path)
    server, thread = serve(application)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.goto(f"http://127.0.0.1:{server.server_port}/projects?lang=en")
            form = page.locator("#create-project")
            form.evaluate("form => form.closest('details').open = true")
            form.locator('[name="id"]').fill("v1-reference-demo")
            form.locator('[name="name"]').fill("V1 Reference Dataset")
            form.locator('[name="planning_year"]').fill("2024")
            form.locator('[name="annual_water_budget"]').fill("100700080.81")
            form.locator('[name="data_source_notes"]').select_option("reference_demo")
            with page.expect_response(
                lambda response: response.url.endswith("/api/v2/projects")
                and response.request.method == "POST"
            ):
                form.locator("button.button.primary").click()
            expect(page.locator("#project-name")).to_have_text("V1 Reference Dataset", timeout=20000)
            created, readiness, context = page.evaluate("""Promise.all([
                fetch('/api/v2/projects/v1-reference-demo').then(response => response.json()),
                fetch('/api/v2/projects/v1-reference-demo/readiness').then(response => response.json()),
                fetch('/api/v2/projects/v1-reference-demo/decision-context').then(response => response.json())
            ])""")
            assert created["project"]["data_source_notes"] == "reference_demo"
            assert created["metadata"] == {
                "reference_demo": True,
                "not_official": True,
                "display_labels": ["REFERENCE", "DEMO DATA"],
                "classification": "REFERENCE_DEMO",
            }
            assert "REFERENCE_DEMO" in readiness["execution_profiles"]
            assert context["execution_profile"] == "REFERENCE_DEMO"
            expect(page.locator('#analysis-form [name="execution_profile"]')).to_have_value("REFERENCE_DEMO")
            expect(page.locator("#global-mode-badge")).to_have_text("REFERENCE MODEL / DEMO DATA")
            expect(page.locator("#mode-warning")).to_be_visible()
            expect(page.locator("#mode-warning")).to_contain_text(
                "NOT AN OFFICIAL WATER ALLOCATION OR FIELD VALIDATION"
            )
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
