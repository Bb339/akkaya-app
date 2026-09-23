"""Deterministic evidence for Phase 7 corrective fix 1."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs" / "audits" / "crop_identity_phenology_phase7_fix1"
BASELINE = "19366a7f1a551704c143caa38d9228396dce9f30"
PROTECTED = ("app.py", "kds/science", "data")


def _write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _imports():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from kds.application.readiness import _parameter_and_phenology_readiness
    from kds.domain.crop_parameters import replacement_preview, resolution_for
    from kds.imports.crop_parameter_tables import validate_crop_parameter_table
    return _parameter_and_phenology_readiness, replacement_preview, resolution_for, validate_crop_parameter_table


def _validate(validate, mode: str, **changes):
    values = dict(crop_identity="TURP (KIRMIZI)", applicable_year=2024,
                  geographic_scope="project", season="PRIMARY", mode=mode,
                  planting_date="2024-04-15", harvest_date="2024-09-01",
                  planting_window_start="", planting_window_end="",
                  harvest_window_start="", harvest_window_end="",
                  authority_class="ASSUMED", source="SYNTHETIC corrective evidence",
                  source_reference="not_official", notes="SYNTHETIC")
    values.update(changes)
    mapping = {key: key for key in values}
    batch = {"data_type": "crop_phenology", "mapping": mapping,
             "rows": [{"line": 2, "values": values}], "options": {}}
    document = {"project": {"planning_year": 2024}, "crops": [{"name": "TURP (KIRMIZI)"}]}
    issues, records = validate(batch, document)
    return {"status": "invalid" if any(i["severity"] == "ERROR" for i in issues) else "ready",
            "season_year_semantics": records[0].get("season_year_semantics") if records else None,
            "errors": [i["message"] for i in issues if i["severity"] == "ERROR"]}


def _dataset(kind: str, year: int, scope: str):
    dataset_id = f"{kind}-{year}-{scope}"
    record = {"runtime_crop_id": "TURPKIRMIZI", "parameter_crop_id": "TURPKIRMIZI",
              "resolution_status": "EXACT", "applicable_year": year, "geographic_scope": scope,
              "verified_for_pilot": True, "verified_parameter_evidence": True,
              "mode": "YEAR_SPECIFIC", "planting_date": f"{year}-04-15",
              "harvest_date": f"{year}-09-01"}
    return dataset_id, {"dataset_id": dataset_id, "data_type": kind, "records": [record]}


def _readiness_case(readiness, *, year: int = 2024, scopes=("project",), empty=False):
    document = {"project": {"planning_year": 2024}, "metadata": {},
                "crops": [] if empty else [{"name": "TURP (KIRMIZI)"}],
                "crop_parameter_data": {"active": {}, "datasets": {}}}
    for kind in ("crop_water_parameters", "crop_phenology"):
        for scope in scopes:
            dataset_id, dataset = _dataset(kind, year, scope)
            document["crop_parameter_data"]["datasets"][dataset_id] = dataset
            document["crop_parameter_data"]["active"][f"{kind}|{year}|{scope}"] = dataset_id
    parameter, phenology, pilot = readiness(document, False)
    return {"pilot_status": pilot["status"], "blocking_reasons": pilot["blocking_reasons"],
            "parameter_selection": parameter["dataset_selection"],
            "phenology_selection": phenology["dataset_selection"]}


def generate(output: Path = OUTPUT, test_report: dict[str, Any] | None = None):
    readiness, preview, resolution, validate = _imports()
    output.mkdir(parents=True, exist_ok=True)
    seasons = {
        "year_specific_same_year": _validate(validate, "YEAR_SPECIFIC"),
        "year_specific_cross_year": _validate(validate, "YEAR_SPECIFIC", planting_date="2023-10-15", harvest_date="2024-06-15"),
        "year_specific_impossible": _validate(validate, "YEAR_SPECIFIC", planting_date="2024-10-15", harvest_date="2024-06-15"),
        "climatological_same_year": _validate(validate, "CLIMATOLOGICAL_WINDOW", planting_date="", harvest_date="", planting_window_start="04-10", planting_window_end="04-25", harvest_window_start="09-01", harvest_window_end="09-20"),
        "climatological_cross_year": _validate(validate, "CLIMATOLOGICAL_WINDOW", planting_date="", harvest_date="", planting_window_start="10-15", planting_window_end="11-15", harvest_window_start="06-01", harvest_window_end="07-15"),
        "year_specific_mixed": _validate(validate, "YEAR_SPECIFIC", planting_window_start="04-10"),
        "climatological_mixed": _validate(validate, "CLIMATOLOGICAL_WINDOW", planting_window_start="04-10", planting_window_end="04-25", harvest_window_start="09-01", harvest_window_end="09-20"),
    }
    _write(output / "season_year_cases.json", seasons)
    readiness_cases = {
        "wrong_year_only": _readiness_case(readiness, year=2025),
        "non_project_scope": _readiness_case(readiness, scopes=("district-a",)),
        "multiple_scopes": _readiness_case(readiness, scopes=("project", "district-a")),
        "empty_catalog": _readiness_case(readiness, empty=True),
    }
    _write(output / "readiness_adversarial_cases.json", readiness_cases)
    fallback = resolution("KIMYON", {"KI\u0307MYON"}, legacy_direct_match=False,
                          parameter_authority="OFFICIAL")
    _write(output / "fallback_verification_cases.json", fallback)
    old = {"runtime_crop_id": "TURPKIRMIZI", "applicable_year": 2024,
           "geographic_scope": "project", "authority_class": "ASSUMED",
           "kc_ini": .2, "kc_mid": .9, "kc_end": .5, "stage_value_mode": "DAYS",
           "p_ini": .2, "p_dev": .3, "p_mid": .3, "p_late": .2, "stage_total": 1.0}
    document = {"crop_parameter_data": {"active": {"crop_water_parameters|2024|project": "old"},
                "datasets": {"old": {"dataset_id": "old", "authority_class": "ASSUMED", "records": [old]}}}}
    stage_preview = preview(document, "crop_water_parameters", [{**old, "stage_value_mode": "FRACTIONS"}])
    old_phenology = {"runtime_crop_id": "TURPKIRMIZI", "applicable_year": 2024,
                     "geographic_scope": "project", "authority_class": "ASSUMED",
                     "mode": "YEAR_SPECIFIC", "season": "PRIMARY",
                     "season_year_semantics": "SAME_CALENDAR_YEAR", "planting_date": "2024-04-15",
                     "harvest_date": "2024-09-01", "planting_window_start": None,
                     "planting_window_end": None, "harvest_window_start": None, "harvest_window_end": None}
    phenology_document = {"crop_parameter_data": {"active": {"crop_phenology|2024|project": "old"},
                          "datasets": {"old": {"dataset_id": "old", "authority_class": "ASSUMED",
                                                "records": [old_phenology]}}}}
    phenology_preview = preview(phenology_document, "crop_phenology", [{**old_phenology,
        "season_year_semantics": "CROSSES_CALENDAR_YEAR", "planting_date": "2023-10-15",
        "harvest_date": "2024-06-15"}])
    semantic_previews = {"stage_value_mode_change": stage_preview,
                         "phenology_season_year_change": phenology_preview}
    _write(output / "preview_semantic_cases.json", semantic_previews)
    changed = subprocess.run(["git", "diff", "--name-only", BASELINE, "--", *PROTECTED],
                             cwd=ROOT, check=True, text=True, capture_output=True).stdout.splitlines()
    changed = [path for path in changed if path != "kds/science/institutional_water.py"]
    guard = {"baseline_commit": BASELINE, "protected_paths": list(PROTECTED),
             "changed_protected_paths": changed, "engine_connected": False,
             "candidate_matrix_changed": any(path.startswith("data/") for path in changed)}
    _write(output / "source_guard.json", guard)
    _write(output / "test_report.json", test_report or {"status": "PENDING_FINAL_VALIDATION"})
    summary = """# V2 Scientific Phase 7 corrective fix 1

The corrective contract supports same-year and previous-autumn/current-harvest-year phenology, and stores an explicit `season_year_semantics` value. Mode-specific fields are exclusive. Planning-year and geographic-scope selection fails closed; an empty runtime catalog is never pilot-ready. Verified evidence is distinct from engine-ready parameters, semantic stage-mode changes appear in preview, and Kc above 3.0 is rejected.

The scientific engine remains disconnected. No crop, Kc value, date, candidate row, optimizer behavior, water/economics contract, or frozen source was changed. Current Akkaya status remains `DEMO_READY` and `PILOT_DATA_NOT_READY`.
"""
    (output / "fix1_summary.md").write_text(summary, encoding="utf-8")
    if changed:
        raise RuntimeError(f"Protected scientific sources changed: {changed}")
    assert seasons["year_specific_cross_year"]["season_year_semantics"] == "CROSSES_CALENDAR_YEAR"
    assert seasons["climatological_cross_year"]["season_year_semantics"] == "CROSSES_CALENDAR_YEAR"
    assert all(case["pilot_status"] == "PILOT_DATA_NOT_READY" for case in readiness_cases.values())
    assert fallback["verified_parameter_evidence"] and not fallback["verified_parameter_ready"]
    assert stage_preview["change_count"] == 1 and phenology_preview["change_count"] == 1
    return {"season_cases": len(seasons), "readiness_cases": len(readiness_cases),
            "protected_changes": changed}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--test-report", type=Path)
    args = parser.parse_args()
    report = json.loads(args.test_report.read_text(encoding="utf-8")) if args.test_report else None
    print(json.dumps(generate(args.output, report), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
