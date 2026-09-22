"""Pre-pilot freeze evidence must stay reproducible and claim-safe."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path

from tools.scientific_audit.prepilot_freeze import generate


ROOT = Path(__file__).resolve().parents[1]
SCIENTIFIC_SOURCE_COMMIT = "bb0c6ff516a7d995c2894ee66285ebf124ac9340"

REQUIRED = {
    "scientific_prepilot_freeze.md",
    "scientific_lineage.csv",
    "reference_values.json",
    "data_authority_matrix.csv",
    "claim_boundary.md",
    "pilot_readiness_snapshot.json",
    "official_data_gaps.csv",
    "known_backlog.md",
    "reviewer_response_matrix.csv",
    "publication_limitation_matrix.csv",
    "publication_evidence_inventory.csv",
    "reproducibility_manifest.json",
    "source_guard.json",
    "test_report.json",
}


def _digests(folder):
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(folder.iterdir())
    }


def _rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _git(*args):
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, text=True, capture_output=True,
    ).stdout.strip()


def test_freeze_generator_is_byte_deterministic(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    result1 = generate(first)
    result2 = generate(second)
    assert result1 == result2
    assert set(_digests(first)) == set(_digests(second)) == REQUIRED
    assert _digests(first) == _digests(second)
    assert result1["protected_changes"] == []


def test_freeze_reference_readiness_and_engine_boundary(tmp_path):
    output = tmp_path / "evidence"
    generate(output)
    reference = json.loads((output / "reference_values.json").read_text(encoding="utf-8"))
    assert reference["analysis_units"] == 179
    assert reference["area_da"] == 134919.0
    assert reference["current_pattern_calculated_gross_irrigation_demand_m3"] == 100700080.81
    assert reference["current_calculated_profit_tl"] == 1041499119.212
    assert reference["candidate_rows"] == 6859
    assert reference["raw_quota_flagged_rows"] == 3673
    assert reference["crop_parameter_boundary"] == {
        "runtime_catalog": 58,
        "parameter_catalog": 69,
        "canonical_intersection": 47,
        "symmetric_difference": 33,
        "legacy_direct_parameter_lookup": 45,
        "reviewed_parameter_aliases": 9,
        "ambiguous_parameter_identities": 3,
        "missing_parameter_identities": 1,
        "legacy_fallback_inventory": 13,
        "verified_parameter_ready": 0,
        "verified_phenology": 0,
        "phenology_population": 58,
    }
    readiness = json.loads((output / "pilot_readiness_snapshot.json").read_text(encoding="utf-8"))
    assert readiness["demo_status"] == "DEMO_READY"
    assert readiness["pilot_status"] == "PILOT_DATA_NOT_READY"
    assert readiness["engine_connected"] is False
    manifest = json.loads((output / "reproducibility_manifest.json").read_text(encoding="utf-8"))
    assert manifest["scientific_freeze_commit"] == "bb0c6ff516a7d995c2894ee66285ebf124ac9340"
    assert manifest["parent_tag_target"] == manifest["scientific_freeze_commit"]
    assert manifest["robustness_experiments_run"] is False
    assert set(manifest["engine_connection_states"].values()) >= {False}


def test_publication_matrices_preserve_unresolved_claims(tmp_path):
    output = tmp_path / "evidence"
    generate(output)
    reviewers = _rows(output / "reviewer_response_matrix.csv")
    ijer = next(row for row in reviewers if row["reviewer_issue"].startswith("IJER"))
    assert ijer["not_resolved"] == "YES"
    assert "do not invent" in ijer["publication_action"]
    limitations = {row["limitation"]: row for row in _rows(output / "publication_limitation_matrix.csv")}
    assert limitations["field validation"]["what_remains_unresolved"] == "Observed outcome validation"
    assert "field validated" in limitations["field validation"]["unsafe_manuscript_wording"]
    gaps = _rows(output / "official_data_gaps.csv")
    assert len(gaps) == 15
    assert {row["gap"] for row in gaps} >= {
        "official annual allocation", "planting/harvest phenology", "market capacity",
        "farmer preference/behavior", "rotation history",
    }
    claims = (output / "claim_boundary.md").read_text(encoding="utf-8")
    assert "not official allocation" in claims
    assert "not a recommendation" in claims


def test_lineage_and_source_guard_use_git_objects(tmp_path):
    output = tmp_path / "evidence"
    generate(output)
    lineage = _rows(output / "scientific_lineage.csv")
    assert len(lineage) == 11
    assert lineage[-1]["tag_or_reference"] == "v2-crop-identity-phenology-contract-complete"
    assert lineage[-1]["commit"] == "bb0c6ff516a7d995c2894ee66285ebf124ac9340"
    guard = json.loads((output / "source_guard.json").read_text(encoding="utf-8"))
    assert guard["changed_protected_paths"] == []
    assert guard["candidate_matrix_changed"] is False
    assert guard["optimizer_changed"] is False
    assert all(item["identical"] for item in guard["git_objects"].values())


def test_inventory_separates_scientific_source_and_artifact_introduction(tmp_path):
    output = tmp_path / "evidence"
    generate(output)
    rows = _rows(output / "publication_evidence_inventory.csv")
    assert len(rows) == 12
    assert "source_commit" not in rows[0]
    for row in rows:
        assert (ROOT / row["source_file"]).exists()
        assert row["scientific_source_commit"] == SCIENTIFIC_SOURCE_COMMIT
        assert _git("cat-file", "-t", row["scientific_source_commit"]) == "commit"
        additions = _git(
            "log", "--diff-filter=A", "--format=%H", "--", row["source_file"]
        ).splitlines()
        assert additions
        expected_introduction = additions[-1]
        assert row["artifact_introduction_commit"] == expected_introduction
        subprocess.run(
            [
                "git", "cat-file", "-e",
                f"{row['artifact_introduction_commit']}:{row['source_file']}",
            ],
            cwd=ROOT, check=True, capture_output=True,
        )


def test_seeded_fixture_population_matches_manifest_and_inventory(tmp_path):
    fixture_dir = ROOT / "tests" / "fixtures" / "scientific_baseline"
    actual_ids = set()
    actual_seeds = set()
    actual_cases = set()
    for path in sorted(fixture_dir.glob("s[12]_*.json")):
        scenario, algorithm = path.stem.split("_")
        actual_cases.add((scenario.upper(), algorithm.upper()))
        for run in json.loads(path.read_text(encoding="utf-8")):
            actual_ids.update(run["selected_ids"])
            actual_seeds.add(run["seed"])
            assert set(run["selected_ids"]) == {"P1", "P23", "P149"}
    assert actual_ids == {"P1", "P23", "P149"}
    assert len(actual_ids) == 3
    assert actual_seeds == {123, 456, 789}
    assert actual_cases == {
        (scenario, algorithm)
        for scenario in ("S1", "S2")
        for algorithm in ("GA", "ACO", "ABC")
    }

    output = tmp_path / "evidence"
    generate(output)
    manifest = json.loads((output / "reproducibility_manifest.json").read_text(encoding="utf-8"))
    fixture = manifest["algorithm_reproducibility"]["three_unit_regression_fixture"]
    assert fixture["analysis_unit_count"] == 3
    assert fixture["analysis_units"] == ["P1", "P23", "P149"]
    assert fixture["scenarios"] == ["S1", "S2"]
    assert fixture["algorithms"] == ["GA", "ACO", "ABC"]
    assert fixture["seeds"] == [123, 456, 789]
    assert fixture["publication_scope"] == "REPRODUCIBILITY_ONLY"
    assert fixture["basin_level_result"] is False
    assert "full_akkaya" not in manifest["algorithm_reproducibility"]

    inventory = _rows(output / "publication_evidence_inventory.csv")
    row = next(item for item in inventory if item["table_figure_candidate"] == "Seeded algorithm fixtures")
    assert row["population_type"] == "REGRESSION_FIXTURE"
    assert row["analysis_unit_count"] == "3"
    assert row["publication_scope"] == "REPRODUCIBILITY_ONLY"
    assert all(item in row["scenario_population"] for item in ("P1", "P23", "P149"))
    fixture_wording = " ".join(row.values()).lower()
    assert not any(term in fixture_wording for term in ("full", "akkaya", "179-unit", "basin"))


def test_reference_regression_and_generalization_populations_remain_distinct(tmp_path):
    output = tmp_path / "evidence"
    generate(output)
    manifest = json.loads((output / "reproducibility_manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_schema"] == "v2-scientific-prepilot-freeze-v1.1"
    populations = manifest["evidence_populations"]
    assert populations["reference_project"] == {
        "name": "Akkaya",
        "population_type": "REFERENCE_PROJECT",
        "analysis_unit_count": 179,
        "seeded_full_project_fixture": "NOT_AVAILABLE_IN_FROZEN_SCIENTIFIC_BASELINE",
    }
    assert populations["regression_fixture"]["analysis_unit_count"] == 3
    assert populations["regression_fixture"]["publication_scope"] == "REPRODUCIBILITY_ONLY"
    assert populations["regression_fixture"]["turp_42_4_percent_scope"] == "REGRESSION_FIXTURE_ONLY"
    assert populations["synthetic_generalization_project"] == {
        "population_type": "SYNTHETIC_GENERALIZATION_PROJECT",
        "analysis_unit_count": 24,
        "candidate_count": 192,
        "seed": 2468,
        "publication_scope": "SOFTWARE_ARCHITECTURE_ONLY",
        "external_agronomic_field_validation": False,
    }

    inventory = {
        row["table_figure_candidate"]: row
        for row in _rows(output / "publication_evidence_inventory.csv")
    }
    assert inventory["Akkaya reference-value table"]["population_type"] == "REFERENCE_PROJECT"
    assert inventory["Akkaya reference-value table"]["analysis_unit_count"] == "179"
    assert inventory["Generalization acceptance"]["population_type"] == "SYNTHETIC_GENERALIZATION_PROJECT"
    assert inventory["Generalization acceptance"]["analysis_unit_count"] == "24"


def test_turp_claim_boundary_remains_fixture_scoped(tmp_path):
    output = tmp_path / "evidence"
    generate(output)
    claims = (output / "claim_boundary.md").read_text(encoding="utf-8")
    reference = json.loads((output / "reference_values.json").read_text(encoding="utf-8"))
    assert "42.4% Turp value is confined to a small regression fixture" in claims
    assert reference["turp_boundary"]["fixture_scope_note"] == (
        "The frozen 42.4% value belongs to a small regression fixture."
    )
    assert "Turp should be planted on 95433 da." in reference["turp_boundary"]["forbidden_claims"]
