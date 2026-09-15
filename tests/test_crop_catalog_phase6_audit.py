"""Determinism and mutation guards for the Phase 6 diagnosis-only audit."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from tools.scientific_audit.crop_catalog_phase6 import ROOT, generate, protected_files, project_store_hashes


def digests(folder: Path) -> dict[str, str]:
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(folder.iterdir()) if path.is_file()}


def test_crop_catalog_phase6_is_deterministic_and_read_only(tmp_path):
    source_before = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in protected_files()}
    store_before = project_store_hashes()
    first, second = tmp_path / "first", tmp_path / "second"
    result1, result2 = generate(first), generate(second)

    assert result1 == result2
    assert digests(first) == digests(second)
    assert result1 == {
        "runtime_catalog_count": 58, "parameter_catalog_count": 69,
        "canonical_intersection": 47, "symmetric_difference": 33,
        "direct_kc_coverage": 45, "candidate_count": 57,
        "s1_count": 56, "s2_primary_count": 56, "s2_secondary_count": 4,
        "project_crop_count": 58, "output_file_count": 25,
        "full_optimizer_runs": 0, "project_store_unchanged": True, "source_unchanged": True,
    }
    assert len(list(first.iterdir())) >= 20
    breakdown = json.loads((first / "root_cause_breakdown.json").read_text(encoding="utf-8"))
    assert breakdown["reconciled_unmatched_identity_rows"]["total"] == 33
    with (first / "runtime_58_catalog.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 58
    assert [row["canonical_name"] for row in rows if row["candidate_matrix_present"] == "NO"] == ["KIMYON"]
    assert source_before == {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in protected_files()}
    assert store_before == project_store_hashes()
