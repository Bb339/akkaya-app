"""Pre-pilot freeze evidence must stay reproducible and claim-safe."""
from __future__ import annotations

import csv
import hashlib
import json

from tools.scientific_audit.prepilot_freeze import generate


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
