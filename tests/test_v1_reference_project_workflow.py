"""V1 reference data replay through the real versioned import boundary."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from kds.adapters.project_science import data_hash
from kds.application.decision_provider import project_decision_context
from kds.application.import_service import ImportService
from kds.application.optimization import OptimizationApplicationService
from kds.application.readiness import readiness
from kds.data.repositories import ConflictError, NotFoundError
from scripts.export_v1_reference_dataset import build
from scripts.import_v1_reference_dataset import PROJECT_ID, import_package


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "data" / "project_packages" / "v1_reference_dataset"


class MemoryProjectRepository:
    def __init__(self):
        self.documents = {}

    def create(self, document):
        project_id = document["project"]["id"]
        if project_id in self.documents:
            raise ConflictError("Project already exists.")
        self.documents[project_id] = document
        return document

    def get(self, project_id):
        if project_id not in self.documents:
            raise NotFoundError("Project not found.")
        return self.documents[project_id]

    def update(self, project_id, change):
        document = self.get(project_id)
        change(document)
        return document

    def list_projects(self):
        return [document["project"] for document in self.documents.values()]


@pytest.fixture(scope="module")
def imported_reference():
    repository = MemoryProjectRepository()
    document, evidence = import_package(repository, PACKAGE)
    return repository, document, evidence


def test_v1_reference_export_counts(tmp_path):
    report = build(tmp_path / "package")
    assert report["invariants"] == {
        "analysis_units": 179,
        "total_area_da": 134919.0,
        "crops": 58,
        "candidates": 6859,
        "current_water_m3": pytest.approx(100700080.81),
        "current_profit_tl": pytest.approx(1041499119.212),
    }
    assert len(report["files"]) == 21
    assert report["geometry_count"] == 178 and report["missing_geometry"] == ["P138"]


def test_v1_reference_package_imports(imported_reference):
    _, document, evidence = imported_reference
    assert len(evidence) == 21
    assert all(item["detector"] == "AUTO_MATCHED" and item["status"] == "applied" for item in evidence)
    assert [item["revision"] for item in evidence] == list(range(1, 22))
    assert document["data_revision"] == 21


def test_all_required_reference_domains_ready(imported_reference):
    report = readiness(imported_reference[1])
    assert report["scenarios"]["S1"]["status"] == "READY_WITH_WARNINGS"
    assert report["scenarios"]["S2"]["status"] == "READY_WITH_WARNINGS"
    assert not [item for scenario in report["scenarios"].values() for item in scenario["issues"] if item["severity"] == "error"]


def test_reference_profile_is_backend_declared(imported_reference):
    context = project_decision_context(imported_reference[1], expected_revision=21)
    assert context["execution_profile"] == "REFERENCE_DEMO"
    assert context["authority"] == "REFERENCE / DEMO DATA"
    assert context["project"]["data_source_notes"] == "reference_demo"


def test_v1_project_data_uses_active_revision(imported_reference):
    context = project_decision_context(imported_reference[1], expected_revision=21)
    assert context["provider"] == "PROJECT_DATA" and context["project_revision"] == 21
    with pytest.raises(ValueError, match="active project revision"):
        project_decision_context(imported_reference[1], expected_revision=20)


def test_v1_project_data_has_no_legacy_fallback():
    source = (ROOT / "kds" / "ui" / "static" / "v1-provider.js").read_text(encoding="utf-8")
    assert 'fetch("/api/parcels")' not in source
    assert 'fetch("/api/optimize")' not in source
    assert "initReferenceProvider" not in source[source.index("async function initProject"):]


def test_project_and_v1_analysis_unit_counts_match(imported_reference):
    document = imported_reference[1]
    assert project_decision_context(document)["unit_count"] == len(document["analysis_units"]) == 179


def test_project_and_v1_total_area_match(imported_reference):
    document = imported_reference[1]
    assert project_decision_context(document)["total_area_da"] == pytest.approx(134919.0)


def test_project_and_v1_crop_catalog_match(imported_reference):
    document = imported_reference[1]
    assert project_decision_context(document)["crop_count"] == len(document["crops"]) == 58


def test_project_and_v1_candidate_count_match(imported_reference):
    document = imported_reference[1]
    assert len(document["scientific_inputs"]["candidates"]) == 6859


def test_selected_unit_current_values_match(imported_reference):
    document = imported_reference[1]
    project = next(unit for unit in document["analysis_units"] if unit["external_id"] == "P1")
    interface = next(unit for unit in project_decision_context(document)["units"] if unit["analysis_unit_id"] == "P1")
    parameters = document["scientific_inputs"]["unit_parameters"]["P1"]
    assert (interface["area_da"], interface["current_crop"]) == (project["area_da"], project["current_crop"])
    assert interface["current_water_m3"] == parameters["current_water_m3"]
    assert interface["current_profit_tl"] == parameters["current_profit"]


def test_project_and_v1_candidate_values_match(imported_reference):
    document = imported_reference[1]
    expected = [row for row in document["scientific_inputs"]["candidates"] if row["analysis_unit_id"] == "P1"]
    unit = next(row for row in project_decision_context(document)["units"] if row["analysis_unit_id"] == "P1")
    assert unit["candidate_count"] == len(expected)
    assert unit["candidate_crops"] == sorted({row["crop"] for row in expected})
    assert unit["candidate_options"] == sorted(expected, key=lambda row: row["crop"])


def _payload(scenario="S1", algorithm="GA", seed=123, objective="water_saving"):
    configs = {
        "GA": {"popSize": 12, "generations": 10, "cxRate": .7, "mutRate": .08},
        "ACO": {"ants": 12, "iterations": 10, "rho": .2, "q": 1.0},
        "ABC": {"foodSources": 12, "cycles": 10, "limit": 5},
    }
    return {"execution_profile": "REFERENCE_DEMO", "scenario": scenario, "algorithm": algorithm,
            "seed": seed, "objective": objective, "water_budget_ratio": 1.0,
            "config": configs[algorithm]}


@pytest.fixture(scope="module")
def ga_seed_123(imported_reference):
    repository = imported_reference[0]
    run = OptimizationApplicationService(repository).run(PROJECT_ID, _payload())
    assert run["status"] == "completed", run.get("error")
    return repository, run


def test_project_and_v1_optimization_result_match(ga_seed_123):
    repository, run = ga_seed_123
    context = project_decision_context(repository.get(PROJECT_ID), run=run, expected_revision=21)
    assert context["run"]["id"] == run["id"]
    assert context["run"]["result"]["algorithm"] == "GA"
    assert context["run"]["result"]["seed"] == 123


def test_project_and_v1_run_provenance_match(ga_seed_123):
    _, run = ga_seed_123
    snapshot = run["provenance"]["input_snapshot"]
    assert snapshot["project_id"] == PROJECT_ID and snapshot["project_revision"] == 21
    assert snapshot["algorithm"] == "GA" and snapshot["scenario"] == "S1" and snapshot["seed"] == 123
    assert snapshot["selection_hash"] and snapshot["geometry_hash"]
    assert snapshot["started_at"] and snapshot["completed_at"]


def test_reference_run_has_dataset_hashes(ga_seed_123):
    snapshot = ga_seed_123[1]["provenance"]["input_snapshot"]
    assert len(snapshot["import_batch_ids"]) == 21
    assert len(snapshot["source_file_names"]) == 21
    assert len(snapshot["source_file_sha256"]) == 21
    assert snapshot["dataset_version_ids"]
    assert snapshot["input_datasets"]


def test_missing_project_data_fails_closed():
    repository = MemoryProjectRepository()
    with pytest.raises(NotFoundError):
        repository.get("missing-project")


def test_project_geometry_count_is_178(imported_reference):
    document = imported_reference[1]
    assert sum(bool(unit.get("geometry")) for unit in document["analysis_units"]) == 178
    assert project_decision_context(document)["geometry"] == {
        "available": 178, "total": 179, "coverage": "PARTIAL", "fabricated": False,
    }


def test_geometry_external_ids_match_analysis_units(imported_reference):
    document = imported_reference[1]
    geometry_ids = {unit["external_id"] for unit in document["analysis_units"] if unit.get("geometry")}
    unit_ids = {unit["external_id"] for unit in document["analysis_units"]}
    assert geometry_ids == unit_ids - {"P138"}


def test_v1_project_mode_uses_project_geometry(imported_reference):
    document = imported_reference[1]
    stored = next(unit for unit in document["analysis_units"] if unit["external_id"] == "P1")
    shown = next(unit for unit in project_decision_context(document)["units"] if unit["analysis_unit_id"] == "P1")
    assert shown["geometry"] == stored["geometry"] and shown["geometry_status"] == "PROVIDED"


def test_v1_does_not_use_legacy_geometry_fallback(imported_reference):
    p138 = next(unit for unit in project_decision_context(imported_reference[1])["units"] if unit["analysis_unit_id"] == "P138")
    assert p138["geometry"] is None and p138["geometry_status"] == "NOT_PROVIDED"
    assert p138["latitude"] is None and p138["longitude"] is None


def test_selected_unit_geometry_matches_project_revision(imported_reference):
    document = imported_reference[1]
    before = data_hash(document)
    changed = deepcopy(document)
    unit = next(unit for unit in changed["analysis_units"] if unit["external_id"] == "P1")
    unit["geometry"] = deepcopy(unit["geometry"])
    unit["geometry"]["coordinates"][0][0][0] += 0.000001
    changed["data_revision"] += 1
    assert data_hash(changed) != before


def test_missing_p138_geometry_is_explicit_and_non_blocking(imported_reference):
    report = readiness(imported_reference[1])
    assert all(report["scenarios"][name]["status"] != "NOT_READY" for name in ("S1", "S2"))
    geometry = [issue for issue in report["scenarios"]["S1"]["issues"] if issue["code"] == "geometry"]
    assert len(geometry) == 1 and geometry[0]["severity"] == "warning" and "178/179" in geometry[0]["message"]


def test_s2_large_import_is_atomic(imported_reference):
    _, document, evidence = imported_reference
    s2 = next(item for item in evidence if item["filename"] == "scientific_s2.csv")
    assert s2["row_count"] > 20_000 and s2["revision"] == 7
    assert document["imports"][s2["id"]]["status"] == "applied"


@pytest.mark.parametrize("scenario", ["S1", "S2"])
@pytest.mark.parametrize("algorithm", ["GA", "ACO", "ABC"])
def test_reference_optimizer_regression_seed_42(imported_reference, scenario, algorithm):
    run = OptimizationApplicationService(imported_reference[0]).run(PROJECT_ID, _payload(scenario, algorithm, 42))
    assert run["status"] == "completed", run.get("error")
    assert run["result"]["execution_profile"] == "REFERENCE_DEMO"
    assert run["result"]["classification"] == "REFERENCE_MODEL_OUTPUT"
