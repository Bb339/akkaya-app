from __future__ import annotations

from copy import deepcopy

import pytest

from kds.application.decision_provider import project_decision_context
from kds.application.project_service import project_document
from kds.domain.project import Project
from test_unified_decision_demo import (
    analysis_payload, bulk_upload, client_for, confirm_bulk, project_payload,
)


def _document(units):
    project = Project(
        id="provider-geometry", name="Provider geometry fixture", planning_year=2025,
        annual_water_budget=0, water_budget_unit="m3", province_or_region="Synthetic Region",
        data_source_notes="synthetic not_official institutional integration fixture",
    )
    document = project_document(project)
    document["analysis_units"] = units
    return document


def test_project_decision_context_uses_only_project_contracts(tmp_path):
    _, client, repository = client_for(tmp_path)
    payload = project_payload("provider-demo")
    payload["name"] = "Kurumsal Veri Demo Projesi"
    assert client.post("/api/v2/projects", json=payload).status_code == 201
    items = bulk_upload(client, "provider-demo")
    assert len(items) == 20
    assert {item["detection"]["state"] for item in items} == {"AUTO_MATCHED"}
    confirm_bulk(client, items, "provider-demo")
    request = analysis_payload()
    preview = client.post("/api/v2/projects/provider-demo/analysis-preview", json=request).json
    run_body = {**request, **{key: preview[key]
                              for key in ("preview_token", "preview_revision", "selection_hash")}}
    run = client.post("/api/v2/projects/provider-demo/analyses", json=run_body).json

    response = client.get(f"/api/v2/projects/provider-demo/decision-context?run_id={run['id']}&scenario=S1")
    assert response.status_code == 200
    context = response.json
    assert context["provider"] == "PROJECT_DATA"
    assert context["project"]["name"] == "Kurumsal Veri Demo Projesi"
    assert context["project_revision"] == 20
    assert context["authority"] == "SYNTHETIC / NOT_OFFICIAL"
    assert context["unit_count"] == 24
    assert context["total_area_da"] == 258
    assert context["crop_count"] == 8
    assert context["candidate_unit_count"] == 24
    assert [unit["analysis_unit_id"] for unit in context["units"]] == [
        unit["external_id"] for unit in repository.get("provider-demo")["analysis_units"]
    ]
    assert all(not unit["analysis_unit_id"].startswith("P") for unit in context["units"])
    assert context["capabilities"]["algorithms"] == ["GA", "ACO", "ABC"]
    assert context["capabilities"]["objectives"] == ["water_saving", "max_profit", "water_efficiency"]
    assert context["capabilities"]["scenarios"]["S1"]["ready"] is True
    assert context["run"]["id"] == run["id"]
    assert context["run"]["result_authority_label"] == "SYNTHETIC / NOT_OFFICIAL"
    assert context["run"]["result"]["classification"] == "SYNTHETIC_TEST_OUTPUT"
    assert len(context["run"]["result"]["presentation_units"]) == 24
    assert "akkaya" not in str(context).casefold()


def test_context_query_is_strict_and_missing_project_fails_closed(tmp_path):
    _, client, _ = client_for(tmp_path)
    assert client.post("/api/v2/projects", json=project_payload("strict-context")).status_code == 201
    duplicate = client.get("/api/v2/projects/strict-context/decision-context?run_id=a&run_id=b")
    assert duplicate.status_code == 400
    assert "At most one" in duplicate.json["error"]
    unknown = client.get("/api/v2/projects/missing/decision-context")
    assert unknown.status_code == 404


@pytest.mark.parametrize(
    ("units", "coverage", "available"),
    [
        ([{"external_id": "GX-001", "area_da": 1, "current_crop": "ARPA",
           "geometry": {"type": "Polygon", "coordinates": [[[34, 38], [34.1, 38], [34.1, 38.1], [34, 38]]]}}],
         "FULL", 1),
        ([{"external_id": "GX-001", "area_da": 1, "current_crop": "ARPA", "latitude": 38, "longitude": 34},
          {"external_id": "GX-002", "area_da": 2, "current_crop": "NOHUT"}], "PARTIAL", 1),
        ([{"external_id": "GX-001", "area_da": 1, "current_crop": "ARPA"}], "NONE", 0),
    ],
)
def test_geometry_coverage_is_project_only_and_never_fabricated(units, coverage, available):
    context = project_decision_context(_document(units))
    assert context["geometry"] == {
        "available": available, "total": len(units), "coverage": coverage, "fabricated": False,
    }


def test_conflicting_project_unit_identity_fails_closed():
    units = [
        {"external_id": "GX-001", "area_da": 1, "current_crop": "ARPA"},
        {"external_id": "GX-001", "area_da": 2, "current_crop": "NOHUT"},
    ]
    with pytest.raises(ValueError, match="Duplicate project analysis-unit identity"):
        project_decision_context(_document(deepcopy(units)))


def test_project_current_metrics_and_geography_use_backend_project_contract():
    document = _document([
        {"external_id": "GX-001", "area_da": 2, "current_crop": "ARPA",
         "settlement": "Köy A"},
        {"external_id": "GX-002", "area_da": 3, "current_crop": "NOHUT",
         "settlement": "Köy A"},
    ])
    document["scientific_inputs"] = {"unit_parameters": {
        "GX-001": {"current_water_m3": 200, "current_profit": 1000,
                   "soil_class": "II", "parcel_type": "field", "source": "fixture"},
        "GX-002": {"current_water_m3": 450, "current_profit": 2700,
                   "soil_class": "III", "parcel_type": "field", "source": "fixture"},
    }}
    context = project_decision_context(document)
    assert context["units"][0]["current_water_m3_da"] == 100
    assert context["units"][0]["current_profit_tl_da"] == 500
    assert context["units"][0]["current_efficiency_tl_per_m3"] == 5
    assert context["current_summary"] == {
        "status": "PROVIDED", "covered_units": 2, "total_units": 2,
        "water_m3": 650.0, "profit_tl": 3700.0,
        "efficiency_tl_per_m3": 3700 / 650,
        "source": "project.scientific_inputs.unit_parameters",
    }
    assert context["geographic_summary"]["rows"] == [{
        "name": "Köy A", "unit_count": 2, "area_da": 5.0,
        "current_water_m3": 650.0, "current_profit_tl": 3700.0,
        "optimized_water_m3": None, "optimized_profit_tl": None,
    }]


def test_project_current_summary_fails_explicitly_when_values_are_incomplete():
    document = _document([
        {"external_id": "GX-001", "area_da": 2, "current_crop": "ARPA"},
        {"external_id": "GX-002", "area_da": 3, "current_crop": "NOHUT"},
    ])
    document["scientific_inputs"] = {"unit_parameters": {
        "GX-001": {"current_water_m3": 200, "current_profit": 1000},
    }}
    summary = project_decision_context(document)["current_summary"]
    assert summary["status"] == "NOT_PROVIDED"
    assert summary["water_m3"] is None
    assert summary["profit_tl"] is None
