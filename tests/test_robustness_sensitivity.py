"""Evidence-contract tests for the preregistered robustness experiment."""
import json
import math
import csv
from pathlib import Path

import pandas as pd

from kds.science.contract import FrozenValue
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
    for path in (OUT / "active_run_records").glob("*.json"):
        value = json.loads(path.read_text(encoding="utf-8"))
        assert path.stem == value["run_id"]
        assert value["scenario_hash"]
        assert value["input_overlay_hash"]
        assert value["population"] == rs.POPULATION
        assert value["analysis_units"] == rs.ANALYSIS_UNITS
        assert value["area_da"] == rs.AREA_DA
        assert value["planning_year"] == rs.PLANNING_YEAR
        assert len(value["analysis_unit_ids"]) == rs.ANALYSIS_UNITS
        assert value["classification"] in {"SAFE WITH LIMITATION", "DIAGNOSTIC ONLY"}
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


def _record(scenario, feasible, annual=True, monthly="ok"):
    return {
        "definition": {"scenario": scenario},
        "metrics": {
            "feasible": feasible,
            "annual_budget_feasible": annual,
            "monthly_delivery_status": monthly,
        },
    }


def test_s2_infeasible_is_diagnostic_even_when_annual_budget_is_feasible():
    assert rs.classify_record(_record("S2", False, False, "violation")) == "DIAGNOSTIC ONLY"
    assert rs.classify_record(_record("S2", False, True, "violation")) == "DIAGNOSTIC ONLY"


def test_s1_feasible_remains_safe_with_limitation():
    assert rs.classify_record(_record("S1", True)) == "SAFE WITH LIMITATION"


def test_uniform_overlay_scales_all_connected_profit_sources_without_mutation():
    resources = {
        "candidate_options": FrozenValue.of(pd.DataFrame([{"profit_tl_da": 10., "profit_tl_total": 20., "yield_ton_da": 3.}])),
        "regional_candidate_options": FrozenValue.of(pd.DataFrame([{"profit_tl_da": 11., "profit_tl_total": 22.}])),
        "environment": FrozenValue.of({"s1": pd.DataFrame([{"profit_tl": 12., "price": 4., "yield": 5.}]),
                                        "s2": pd.DataFrame([{"profit_tl": 13.}])}),
        "crop_catalog": FrozenValue.of({"A": {"profitPerDa": 14., "price": 6., "yield": 7.}}),
        "fallback_crop_parameters": FrozenValue.of({"A": {"profit_per_da": 15., "water_per_da": 8.}}),
        "crop_table": FrozenValue.of(pd.DataFrame([{"net_kar_tl_da": 16., "yield_ton_da": 9.}])),
        "units": FrozenValue.of([{"profit_tl": 17., "water_m3": 10.}]),
        "unit_summary": FrozenValue.of(pd.DataFrame([{"current_profit_tl": 18.}])),
    }
    original = {name: value.digest for name, value in resources.items()}
    scaled, changed = rs.apply_uniform_profit_overlay(resources, .8)
    assert scaled["candidate_options"].copy().iloc[0]["profit_tl_da"] == 8.
    assert math.isclose(scaled["environment"].copy()["s1"].iloc[0]["profit_tl"], 9.6)
    assert math.isclose(scaled["crop_catalog"].copy()["A"]["profitPerDa"], 11.2)
    assert scaled["fallback_crop_parameters"].copy()["A"]["profit_per_da"] == 12.
    assert math.isclose(scaled["crop_table"].copy().iloc[0]["net_kar_tl_da"], 12.8)
    assert math.isclose(scaled["units"].copy()[0]["profit_tl"], 13.6)
    assert math.isclose(scaled["unit_summary"].copy().iloc[0]["current_profit_tl"], 14.4)
    assert scaled["environment"].copy()["s1"].iloc[0]["price"] == 4.
    assert scaled["environment"].copy()["s1"].iloc[0]["yield"] == 5.
    assert scaled["crop_catalog"].copy()["A"]["price"] == 6.
    assert scaled["crop_catalog"].copy()["A"]["yield"] == 7.
    assert {name: value.digest for name, value in resources.items()} == original
    assert "crop_catalog.profitPerDa" in changed


def test_candidate_hash_domains_are_explicit_and_unchanged():
    manifest = json.loads((OUT / "experiment_manifest.json").read_text(encoding="utf-8"))
    domains = manifest["candidate_hash_domains"]
    assert domains["candidate_raw_csv_sha256"] == rs.CANDIDATE_RAW_CSV_SHA256
    assert domains["candidate_canonical_resource_sha256"] == rs.CANDIDATE_CANONICAL_RESOURCE_SHA256
    assert domains["candidate_git_blob_id"] == rs.CANDIDATE_GIT_BLOB_ID
    assert domains["candidate_raw_csv_sha256"] != domains["candidate_canonical_resource_sha256"]


def test_corrected_s2_economic_scaling_and_composition_invariance():
    rows = list(csv.DictReader((OUT / "economic_sensitivity.csv").read_text(encoding="utf-8").splitlines()))
    s2 = sorted((r for r in rows if r["scenario"] == "S2"), key=lambda r: float(r["economic_shock"]))
    assert len(s2) == 5
    for row in s2:
        assert abs(float(row["linear_scaling_residual_tl"])) <= float(row["linear_scaling_tolerance_tl"])
        assert row["composition_response"] == "UNIFORM_SHOCK_INVARIANT_OBSERVED"
        assert row["claim_classification"] == "DIAGNOSTIC ONLY"
    for field in ("total_water_m3", "hhi", "crop_areas_da", "crop_shares"):
        assert len({row[field] for row in s2}) == 1
    assert {row["price_status"] for row in s2} == {"PRICE_SENSITIVITY_NOT_EXECUTABLE_ON_FROZEN_ENGINE"}
    assert {row["yield_status"] for row in s2} == {"YIELD_SENSITIVITY_NOT_EXECUTABLE_ON_FROZEN_ENGINE"}


def test_superseded_s2_economic_runs_are_excluded_from_active_publication():
    manifest = json.loads((OUT / "experiment_manifest.json").read_text(encoding="utf-8"))
    assert manifest["original_scientific_runs"] == 54
    assert manifest["corrective_reexecuted_runs"] == 5
    assert manifest["superseded_runs"] == 5
    assert manifest["active_publication_runs"] == 54
    assert set(manifest["superseded_experiment_runs"]).isdisjoint(manifest["active_run_ids"])


def test_corrective_economic_fresh_process_repeat_is_deterministic():
    evidence = json.loads((OUT / "corrective_determinism.json").read_text(encoding="utf-8"))
    assert evidence["timestamp_runtime_excluded"] is True
    assert evidence["same_result"] is True
    assert evidence["original_result_sha256"] == evidence["repeat_result_sha256"]
