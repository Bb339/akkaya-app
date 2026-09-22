"""Evidence-contract tests for the preregistered robustness experiment."""
import json
import math
import csv
from pathlib import Path

from tools.scientific_audit import robustness_sensitivity as rs


OUT = Path(__file__).resolve().parents[1] / "docs" / "experiments" / "robustness_sensitivity"


def test_preregistered_grid_is_unique_and_complete():
    rows = rs.plan()
    identities = {
        rs.digest({key: row[key] for key in (
            "scenario", "objective", "algorithm", "seed",
            "water_budget_ratio", "economic_shock",
        )}) for row in rows
    }
    assert len(rows) == len(identities) == 54
    assert rs.selected_seeds() == (101, 211, 307, 401, 503)
    assert len(rs.WATER_LEVELS) == len(set(rs.WATER_LEVELS)) == 8
    assert math.isclose(rs.CRITICAL, rs.PERENNIAL_FLOOR / rs.BASE_BUDGET)


def test_stability_formulas_have_explicit_zero_behavior():
    metrics = rs.crop_metrics({"A": 3, "B": 1})
    assert metrics["crop_count"] == 2
    assert metrics["top1_crop"] == "A"
    assert math.isclose(metrics["hhi"], .625)
    assert rs.distances({}, {}) == {
        "l1_share_distance": 0,
        "bray_curtis": 0.0,
        "weighted_jaccard": 1.0,
    }
    comparison = rs.distances({"A": 1}, {"B": 1})
    assert comparison["l1_share_distance"] == 2
    assert comparison["bray_curtis"] == 1
    assert comparison["weighted_jaccard"] == 0


def test_raw_scientific_runs_are_complete_and_identity_safe():
    records = []
    for path in (OUT / "raw_runs").glob("*.json"):
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("role") == "scientific":
            assert path.stem == value["run_id"]
            assert value["scenario_hash"]
            assert value["input_overlay_hash"]
            records.append(value)
    assert len(records) == 54
    assert len({row["run_id"] for row in records}) == 54
    assert all(row["definition"]["scenario"] in {"S1", "S2"} for row in records)


def test_manifest_population_and_source_guard():
    manifest = json.loads((OUT / "experiment_manifest.json").read_text(encoding="utf-8"))
    guard = json.loads((OUT / "source_guard.json").read_text(encoding="utf-8"))
    assert manifest["baseline_commit"] == rs.BASELINE_COMMIT
    assert manifest["population"] == {
        "label": "FULL_REFERENCE_PROJECT_EXPERIMENT",
        "analysis_units": 179,
        "area_da": 134919,
    }
    assert manifest["raw_run_count"] == 54
    assert guard["unchanged"] is True
    assert guard["before"] == guard["after"]


def test_protocol_copy_and_required_outputs():
    assert (OUT / "experimental_protocol.md").read_text(encoding="utf-8") == rs.PROTOCOL.read_text(encoding="utf-8")
    required = {
        "experiment_manifest.json", "scenario_grid.csv", "run_level_results.csv",
        "scenario_summary.csv", "algorithm_agreement.csv", "seed_variability.csv",
        "crop_share_stability.csv", "water_threshold_analysis.csv",
        "economic_sensitivity.csv", "claim_boundary.md", "publication_tables.md",
        "publication_figure_manifest.csv", "source_guard.json",
    }
    assert required <= {path.name for path in OUT.iterdir()}


def test_same_seed_reproduction_and_overlay_isolation_evidence():
    pilot = json.loads((OUT / "pilot_evidence.json").read_text(encoding="utf-8"))
    manifest = json.loads((OUT / "experiment_manifest.json").read_text(encoding="utf-8"))
    assert pilot["same_seed_deterministic"] is True
    assert pilot["selected_seeds"] == [101, 211, 307, 401, 503]
    assert manifest["candidate_hash"] == manifest["dataset_hashes"]["candidate_options"]
    assert manifest["source_guard_unchanged"] is True


def test_full_population_has_no_fixture_contamination():
    text = (OUT / "run_level_results.csv").read_text(encoding="utf-8")
    rows = list(csv.DictReader(text.splitlines()))
    assert len(rows) == 54
    assert {row["population"] for row in rows} == {"FULL_REFERENCE_PROJECT_EXPERIMENT"}
    assert {int(row["analysis_units"]) for row in rows} == {179}
    assert {float(row["area_da"]) for row in rows} == {134919.0}
    assert "3-unit" not in text and "24-unit" not in text


def test_publication_boundary_rejects_field_and_official_claims():
    text = (OUT / "claim_boundary.md").read_text(encoding="utf-8").lower()
    assert "do not establish official water allocation" in text
    assert "real-farm profitability" in text
    assert "real-world feasibility" in text
