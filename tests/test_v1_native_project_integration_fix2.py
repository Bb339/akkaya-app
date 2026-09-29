from __future__ import annotations

import io
from pathlib import Path

import pytest

from kds.imports.detection import detect
from test_unified_decision_demo import PRIORITY, client_for, project_payload


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "docs" / "unified_v1_project_provider" / "demo_full_visual_package"


def _files():
    return [path for path in sorted(PACKAGE.iterdir())
            if path.suffix.lower() in {".csv", ".xlsx", ".geojson"}]


def _upload(client, project_id):
    response = client.post(
        f"/api/v2/projects/{project_id}/bulk-imports",
        data={"files": [(io.BytesIO(path.read_bytes()), path.name) for path in _files()]},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201, response.json
    return response.json


def _confirm(client, project_id, items):
    staged = [item for item in items if item["detection"]["state"] == "AUTO_MATCHED"]
    for item in sorted(staged, key=lambda row: PRIORITY[row["detection"]["detected_data_type"]]):
        batch_id = item["batch"]["id"]
        mapped = client.post(f"/api/v2/projects/{project_id}/imports/{batch_id}/mapping",
                             json={"mapping": item["detection"]["mapping"]})
        assert mapped.status_code == 200 and mapped.json["status"] == "ready", mapped.json
        confirmed = client.post(f"/api/v2/projects/{project_id}/imports/{batch_id}/confirm",
                                json={"confirm": True, "acknowledge_warnings": True})
        assert confirmed.status_code == 200 and confirmed.json["status"] == "applied", confirmed.json


def test_clearly_irrelevant_supported_file_is_ignored_but_ambiguous_data_is_not():
    ignored = detect(b"note,owner\nmeeting agenda,office\n", "meeting_notes.csv")
    assert ignored["state"] == "IGNORED_NOT_RELEVANT"
    assert ignored["detected_data_type"] is None
    assert ignored["issues"] == [{
        "code": "ignored_not_relevant",
        "message": "No reliable supported-domain evidence was found; file was not staged.",
    }]
    ambiguous = detect(b"external_id,area_da,current_crop\nKDS-001,8,ARPA\n", "unknown.csv")
    assert ambiguous["state"] != "IGNORED_NOT_RELEVANT"


def test_full_visual_package_is_21_of_21_and_has_24_native_polygons(tmp_path):
    _, client, repository = client_for(tmp_path)
    payload = project_payload("full-visual-demo")
    payload["name"] = "KDS Full Visual Synthetic Demo"
    assert client.post("/api/v2/projects", json=payload).status_code == 201
    package = _upload(client, "full-visual-demo")
    assert len(package["items"]) == 21
    assert package["auto_matched"] == 21
    assert package["ignored_not_relevant"] == 0
    assert {item["detection"]["state"] for item in package["items"]} == {"AUTO_MATCHED"}
    _confirm(client, "full-visual-demo", package["items"])
    document = repository.get("full-visual-demo")
    assert document["data_revision"] == 21
    assert [row["external_id"] for row in document["analysis_units"]] == [
        f"KDS-{index:03d}" for index in range(1, 25)
    ]
    assert all(row.get("geometry", {}).get("type") == "Polygon"
               for row in document["analysis_units"])
    context = client.get("/api/v2/projects/full-visual-demo/decision-context?scenario=S1").json
    assert context["authority"] == "SYNTHETIC / NOT_OFFICIAL"
    assert context["geometry"] == {"available": 24, "total": 24, "coverage": "FULL", "fabricated": False}
    assert context["unit_count"] == context["candidate_unit_count"] == 24
    assert context["total_area_da"] == 258


def test_full_visual_package_accepts_backend_algorithm_objective_preview_matrix(tmp_path):
    _, client, _ = client_for(tmp_path)
    project_id = "algorithm-objective-matrix"
    payload = project_payload(project_id)
    assert client.post("/api/v2/projects", json=payload).status_code == 201
    package = _upload(client, project_id)
    _confirm(client, project_id, package["items"])
    for algorithm in ("GA", "ACO", "ABC"):
        for objective in ("water_saving", "max_profit", "water_efficiency"):
            configs = {
                "GA": {"popSize": 12, "generations": 10, "cxRate": .7, "mutRate": .08},
                "ACO": {"ants": 10, "iterations": 10, "rho": .25, "q": 1.0},
                "ABC": {"foodSources": 10, "cycles": 10, "limit": 4},
            }
            response = client.post(f"/api/v2/projects/{project_id}/analysis-preview", json={
                "execution_profile": "VERIFIED_INSTITUTIONAL", "scenario": "S1",
                "algorithm": algorithm, "objective": objective, "seed": 123,
                "water_budget_ratio": 1.0,
                "config": configs[algorithm],
            })
            assert response.status_code == 200, (algorithm, objective, response.json)
            assert response.json["ready"] is True
            assert response.json["preview_revision"] == 21

