from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from flask import Flask

from kds.api import register_project_api
from kds.data.project_store import FileProjectStore
from kds.imports.detection import detect


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "docs" / "unified_decision_demo" / "demo_upload_package"
PRIORITY = {
    "crops": 10, "analysis_units": 20, "economics": 30, "water_budget": 40,
    "candidates": 50, "scientific_inputs": 60, "annual_water_supply": 70,
    "monthly_water_supply": 71, "delivery_capacity": 72, "environmental_release": 73,
    "conveyance_efficiency": 74, "perennial_irrigation_requirement": 75,
    "crop_yield": 80, "crop_sale_price": 81, "crop_cost_components": 82,
    "crop_net_profit": 83, "seasonal_economics": 84, "crop_water_parameters": 90,
    "crop_phenology": 91, "geometries": 100,
}


def project_payload(project_id="unified-demo"):
    return {
        "id": project_id, "name": "Bakanlık Sentetik Demo Projesi",
        "planning_year": 2025, "annual_water_budget": 0, "water_budget_unit": "m3",
        "province_or_region": "Synthetic Region",
        "data_source_notes": "synthetic not_official institutional integration fixture",
        "description": "SYNTHETIC TEST DATA / NOT OFFICIAL / DEMONSTRATION ONLY",
    }


def package_files():
    return [path for path in sorted(PACKAGE.iterdir()) if path.suffix.lower() in {".csv", ".xlsx", ".geojson"}]


def client_for(tmp_path):
    repository = FileProjectStore(tmp_path / "projects")
    application = Flask("unified-decision-demo")
    application.config["TESTING"] = True
    register_project_api(application, repository)
    return application, application.test_client(), repository


def bulk_upload(client, project_id="unified-demo"):
    files = [(io.BytesIO(path.read_bytes()), path.name) for path in package_files()]
    response = client.post(f"/api/v2/projects/{project_id}/bulk-imports",
                           data={"files": files}, content_type="multipart/form-data")
    assert response.status_code == 201, response.json
    return response.json["items"]


def confirm_bulk(client, items, project_id="unified-demo"):
    for item in sorted(items, key=lambda value: PRIORITY[value["detection"]["detected_data_type"]]):
        batch_id = item["batch"]["id"]
        mapped = client.post(f"/api/v2/projects/{project_id}/imports/{batch_id}/mapping",
                             json={"mapping": item["detection"]["mapping"]})
        assert mapped.status_code == 200 and mapped.json["status"] == "ready", (item, mapped.json)
        confirmed = client.post(f"/api/v2/projects/{project_id}/imports/{batch_id}/confirm",
                                json={"confirm": True, "acknowledge_warnings": True})
        assert confirmed.status_code == 200 and confirmed.json["status"] == "applied", (item, confirmed.json)


def analysis_payload():
    return {"execution_profile": "VERIFIED_INSTITUTIONAL", "scenario": "S1", "algorithm": "GA",
            "seed": 123, "objective": "water_saving", "water_budget_ratio": 1.0,
            "config": {"popSize": 12, "generations": 10, "cxRate": .7, "mutRate": .08}}


def test_demo_package_auto_matches_without_activation(tmp_path):
    _, client, repository = client_for(tmp_path)
    assert client.post("/api/v2/projects", json=project_payload()).status_code == 201
    items = bulk_upload(client)
    assert len(items) == 20
    assert all(item["detection"]["state"] == "AUTO_MATCHED" for item in items)
    assert all(item["batch"] and item["batch"]["id"] for item in items)
    document = repository.get("unified-demo")
    assert document["data_revision"] == 0
    assert document["analysis_units"] == [] and document["water_data"]["active"] == {}


def test_project_classification_is_persisted_from_explicit_data_class_not_project_name(tmp_path):
    _, client, repository = client_for(tmp_path)
    response = client.post("/api/v2/projects", json=project_payload("named-by-user"))
    assert response.status_code == 201
    document = repository.get("named-by-user")
    assert document["project"]["name"] == "Bakanlık Sentetik Demo Projesi"
    assert document["metadata"] == {
        "synthetic_institutional_test": True,
        "not_official": True,
        "display_labels": ["SYNTHETIC", "NOT_OFFICIAL"],
    }
    overview = client.get("/api/v2/projects/named-by-user/overview").json
    assert overview["synthetic"] is True
    assert overview["project_kind"] == "synthetic_test"

    real = project_payload("real-institutional")
    real.update(name="Gerçek Kurumsal Proje", data_source_notes="user_provided")
    assert client.post("/api/v2/projects", json=real).status_code == 201
    assert repository.get("real-institutional")["metadata"] == {}

    arbitrary = project_payload("arbitrary-synthetic")
    arbitrary["data_source_notes"] = "synthetic not_official uploaded by user"
    assert client.post("/api/v2/projects", json=arbitrary).status_code == 201
    assert repository.get("arbitrary-synthetic")["metadata"] == {}


def test_confirmed_package_ready_run_and_decision_bridge(tmp_path):
    _, client, repository = client_for(tmp_path)
    client.post("/api/v2/projects", json=project_payload())
    items = bulk_upload(client)
    confirm_bulk(client, items)
    readiness = client.get("/api/v2/projects/unified-demo/readiness").json
    assert readiness["execution_profiles"]["VERIFIED_INSTITUTIONAL"]["ready"]["S1"] is True
    payload = analysis_payload()
    preview = client.post("/api/v2/projects/unified-demo/analysis-preview", json=payload)
    assert preview.status_code == 200 and preview.json["ready"] is True
    run_payload = {**payload, **{key: preview.json[key]
                                for key in ("preview_token", "preview_revision", "selection_hash")}}
    response = client.post("/api/v2/projects/unified-demo/analyses", json=run_payload)
    assert response.status_code == 201, response.json
    run = response.json
    assert run["execution_profile"] == "VERIFIED_INSTITUTIONAL"
    assert run["result_authority_label"] == "SYNTHETIC / NOT_OFFICIAL"
    assert run["result"]["classification"] == "SYNTHETIC_TEST_OUTPUT"
    assert len(run["result"]["presentation_units"]) == 24
    assert {row["analysis_unit_id"] for row in run["result"]["presentation_units"]} == {
        row["external_id"] for row in repository.get("unified-demo")["analysis_units"]}
    assert not any(row["analysis_unit_id"].startswith("P") for row in run["result"]["presentation_units"])
    page = client.get("/projects/decision")
    assert page.status_code == 200 and b"VERIFIED INSTITUTIONAL" in page.data
    stored = client.get(f"/api/v2/projects/unified-demo/analyses/{run['id']}").json
    assert stored["id"] == run["id"] and stored["result"]["result_provenance"]["selection_hash"]


def test_real_institutional_project_rejects_the_same_synthetic_package(tmp_path):
    _, client, repository = client_for(tmp_path)
    project = project_payload("real-institutional")
    project.update(name="Gerçek Kurumsal Proje", data_source_notes="user_provided")
    assert client.post("/api/v2/projects", json=project).status_code == 201
    items = bulk_upload(client, "real-institutional")
    assert len(items) == 20
    assert all(item["detection"]["state"] == "AUTO_MATCHED" for item in items)
    confirm_bulk(client, items, "real-institutional")

    document = repository.get("real-institutional")
    assert document["metadata"].get("synthetic_institutional_test") is None
    assert document["metadata"].get("not_official") is None
    readiness = client.get("/api/v2/projects/real-institutional/readiness").json
    verified = readiness["execution_profiles"]["VERIFIED_INSTITUTIONAL"]
    assert verified["ready"]["S1"] is False
    assert any(domain["connection_state"] == "INVALID_AUTHORITY"
               for domain in readiness["domains"].values())
    assert any("synthetic" in reason.casefold()
               for reason in verified["blocking_reasons"]["S1"])


def test_detection_negative_states_are_fail_closed(tmp_path):
    project = project_payload()
    ambiguous = detect(b"id,unit_id,settlement,area_da,current_crop\nA,A,X,1,ARPA\n",
                       "analysis_units.csv", project=project)
    assert ambiguous["state"] == "AMBIGUOUS" and ambiguous["ambiguous_mapping"]
    missing = detect(b"external_id,area_da\nA,1\n", "analysis_units.csv", project=project)
    assert missing["state"] == "REVIEW_REQUIRED" and missing["missing_required_fields"]
    wrong_year = detect(
        b"planning_year,amount,unit,geographic_scope,authority_class\n2024,1,m3/year,project,MEASURED\n",
        "annual_water_supply.csv", project=project)
    assert wrong_year["state"] == "REVIEW_REQUIRED"
    assert "wrong_planning_year" in {issue["code"] for issue in wrong_year["issues"]}
    wrong_scope = detect(
        b"planning_year,amount,unit,geographic_scope,authority_class\n2025,1,m3/year,other,MEASURED\n",
        "annual_water_supply.csv", project=project)
    assert wrong_scope["state"] == "REVIEW_REQUIRED"
    assert "wrong_geographic_scope" in {issue["code"] for issue in wrong_scope["issues"]}
    assert detect(b"word", "report.docx", project=project)["state"] == "UNSUPPORTED"
    assert detect(b"not a workbook", "broken.xlsx", project=project)["state"] == "INVALID"


def test_duplicate_incomplete_stale_and_no_preview_fail_closed(tmp_path):
    _, client, repository = client_for(tmp_path)
    client.post("/api/v2/projects", json=project_payload())
    data = (PACKAGE / "analysis_units.csv").read_bytes()
    duplicate = client.post("/api/v2/projects/unified-demo/bulk-imports",
                            data={"files": [(io.BytesIO(data), "analysis_units.csv"),
                                            (io.BytesIO(data), "analysis_units-copy.csv")]},
                            content_type="multipart/form-data")
    assert duplicate.status_code == 201
    assert duplicate.json["items"][1]["detection"]["state"] == "AMBIGUOUS"
    assert repository.get("unified-demo")["data_revision"] == 0
    readiness = client.get("/api/v2/projects/unified-demo/readiness").json
    assert readiness["execution_profiles"]["VERIFIED_INSTITUTIONAL"]["ready"]["S1"] is False
    refused = client.post("/api/v2/projects/unified-demo/analyses", json=analysis_payload())
    assert refused.status_code == 400

    # Use a clean project for the preview-replacement check.
    client.post("/api/v2/projects", json=project_payload("stale-demo"))
    items = bulk_upload(client, "stale-demo")
    confirm_bulk(client, items, "stale-demo")
    preview = client.post("/api/v2/projects/stale-demo/analysis-preview", json=analysis_payload()).json
    replacement = b"amount,unit,kind,source\n120001,m3,scenario,synthetic_test_fixture\n"
    uploaded = client.post("/api/v2/projects/stale-demo/imports",
                           data={"data_type": "water_budget", "file": (io.BytesIO(replacement), "water_budget-v2.csv")},
                           content_type="multipart/form-data").json
    client.post(f"/api/v2/projects/stale-demo/imports/{uploaded['id']}/mapping",
                json={"mapping": uploaded["suggested_mapping"]})
    client.post(f"/api/v2/projects/stale-demo/imports/{uploaded['id']}/confirm",
                json={"confirm": True, "acknowledge_warnings": True})
    stale = {**analysis_payload(), **{key: preview[key]
                                     for key in ("preview_token", "preview_revision", "selection_hash")}}
    response = client.post("/api/v2/projects/stale-demo/analyses", json=stale)
    assert response.status_code == 400 and "STALE_PREVIEW" in response.json["error"]

