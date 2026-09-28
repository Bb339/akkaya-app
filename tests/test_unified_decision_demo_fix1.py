from __future__ import annotations

import io
from pathlib import Path

from kds.imports.detection import detect
from test_unified_decision_demo import client_for, package_files, project_payload


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "docs" / "unified_decision_demo" / "demo_upload_package"


def test_accepted_package_remains_twenty_of_twenty_auto_matched():
    project = project_payload()
    results = [detect(path.read_bytes(), path.name, project=project) for path in package_files()]
    assert len(results) == 20
    assert {result["state"] for result in results} == {"AUTO_MATCHED"}


def test_required_numeric_text_and_malformed_explicit_year_require_review():
    project = project_payload()
    bad_amount = detect(
        b"planning_year,amount,unit,geographic_scope,authority_class\n2025,not-a-number,m3/year,project,MEASURED\n",
        "annual_water_supply.csv", project=project)
    assert bad_amount["state"] == "REVIEW_REQUIRED"
    assert "required_numeric_field_not_parseable" in {issue["code"] for issue in bad_amount["issues"]}

    bad_year = detect(
        b"planning_year,amount,unit,geographic_scope,authority_class\nnot-a-year,60000,m3/year,project,MEASURED\n",
        "annual_water_supply.csv", project=project)
    assert bad_year["state"] == "REVIEW_REQUIRED"
    assert "explicit_year_not_parseable" in {issue["code"] for issue in bad_year["issues"]}


def test_existing_detection_states_remain_fail_closed():
    project = project_payload()
    ambiguous = detect(b"id,unit_id,settlement,area_da,current_crop\nA,A,X,1,ARPA\n",
                       "analysis_units.csv", project=project)
    assert ambiguous["state"] == "AMBIGUOUS"
    missing = detect(b"external_id,area_da\nA,1\n", "analysis_units.csv", project=project)
    assert missing["state"] == "REVIEW_REQUIRED"
    wrong_year = detect(
        b"planning_year,amount,unit,geographic_scope,authority_class\n2024,1,m3/year,project,MEASURED\n",
        "annual_water_supply.csv", project=project)
    assert wrong_year["state"] == "REVIEW_REQUIRED"
    wrong_scope = detect(
        b"planning_year,amount,unit,geographic_scope,authority_class\n2025,1,m3/year,elsewhere,MEASURED\n",
        "annual_water_supply.csv", project=project)
    assert wrong_scope["state"] == "REVIEW_REQUIRED"
    assert detect(b"word", "report.docx", project=project)["state"] == "UNSUPPORTED"
    assert detect(b"not a workbook", "broken.xlsx", project=project)["state"] == "INVALID"


def test_auto_matched_upload_still_does_not_activate_before_confirmation(tmp_path):
    _, client, repository = client_for(tmp_path)
    assert client.post("/api/v2/projects", json=project_payload()).status_code == 201
    content = (PACKAGE / "annual_water_supply.csv").read_bytes()
    response = client.post(
        "/api/v2/projects/unified-demo/bulk-imports",
        data={"files": [(io.BytesIO(content), "annual_water_supply.csv")]},
        content_type="multipart/form-data")
    assert response.status_code == 201
    assert response.json["items"][0]["detection"]["state"] == "AUTO_MATCHED"
    document = repository.get("unified-demo")
    assert document["data_revision"] == 0
    assert document["water_data"]["active"] == {}

