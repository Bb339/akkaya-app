"""Determinism and mutation guards for the diagnosis-only Phase 5 audit."""
from __future__ import annotations

import hashlib
import csv
from pathlib import Path

from tools.scientific_audit.turp_dominance_phase5 import ROOT, generate, protected_files


def digests(folder: Path) -> dict[str, str]:
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(folder.iterdir()) if path.is_file()}


def test_turp_audit_is_deterministic_and_does_not_mutate_sources(tmp_path):
    before = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in protected_files()}
    first, second = tmp_path / "first", tmp_path / "second"
    result1 = generate(first)
    result2 = generate(second)
    assert digests(first) == digests(second)
    assert result1["turp_raw_units"] == 43
    assert result1["turp_runtime_units"] == 127
    assert result1["turp_runtime_area_da"] == 95433.0
    assert (result1["turp_water_rank"], result1["turp_profit_rank"], result1["turp_efficiency_rank"]) == (1, 23, 3)
    with (first / "objective_decomposition.csv").open(encoding="utf-8", newline="") as stream:
        assert max(abs(float(row["decomposition_residual"])) for row in csv.DictReader(stream)) <= 1e-8
    assert result1["fixture_runs"] == 18 and result1["full_project_optimizer_runs"] == 0
    assert result1 == result2
    assert before == {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in protected_files()}
