"""Generate deterministic Phase 7 crop-contract evidence without running science."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "docs" / "audits" / "crop_identity_phenology_phase7"
BASELINE = "38f8c89d4ab14de6868dcd84f017e6e5378353aa"
PROTECTED = ("app.py", "kds/science", "kds/application/optimization.py", "data")


def _imports():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import app
    from kds.adapters.akkaya_demo import build_demo
    from kds.application.readiness import readiness
    from kds.domain.crop_parameters import (
        AMBIGUOUS_GRANULARITY_RELATIONS,
        LEGACY_DIRECT_FALLBACK_CROPS,
        PARAMETER_ONLY_IDENTITIES,
        REVIEWED_IDENTITY_RELATIONS,
        resolution_for,
    )
    return app, build_demo, readiness, REVIEWED_IDENTITY_RELATIONS, AMBIGUOUS_GRANULARITY_RELATIONS, LEGACY_DIRECT_FALLBACK_CROPS, PARAMETER_ONLY_IDENTITIES, resolution_for


def _write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str] | None = None) -> None:
    rows = list(rows)
    fields = fields or (list(rows[0]) if rows else [])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _protected_digest() -> str:
    digest = hashlib.sha256()
    paths: list[Path] = []
    for item in PROTECTED:
        path = ROOT / item
        paths.extend(sorted(p for p in path.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
                     if path.is_dir() else [path])
    for path in sorted(paths):
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def generate(output: Path = DEFAULT_OUTPUT, test_report: dict[str, Any] | None = None) -> dict[str, Any]:
    (app, build_demo, readiness, reviewed, ambiguous_relations, legacy_fallback,
     parameter_only, resolution_for) = _imports()
    output.mkdir(parents=True, exist_ok=True)
    protected_before = _protected_digest()

    document = build_demo(app.DATA_DIR)
    params = app.load_enhanced_frames()["crop_params"]
    parameter_ids = {app.normalize_crop_key(value).replace("_", "") for value in params["crop"]}
    direct_keys = {app.normalize_crop_key(value) for value in params["crop"]}
    runtime_rows = []
    for crop in sorted(document["crops"], key=lambda row: app.canonical_crop_key(row["name"])):
        crop_id = app.canonical_crop_key(crop["name"])
        normalized = app.normalize_crop_key(crop["name"])
        row = resolution_for(crop_id, parameter_ids,
                             legacy_direct_match=normalized in direct_keys,
                             parameter_authority="ASSUMED")
        runtime_rows.append({
            "runtime_crop_name": crop["name"],
            "runtime_crop_id": crop_id,
            "resolution_status": row["resolution_status"],
            "resolved_parameter_identity": row["resolved_parameter_identity"],
            "resolution_method": row["resolution_method"],
            "resolution_evidence": row["resolution_evidence"],
            "parameter_authority": row["parameter_authority"],
            "identity_resolution_reviewed": row["identity_resolution_reviewed"],
            "verified_parameter_ready": row["verified_parameter_ready"],
            "legacy_generic_fallback": row["legacy_generic_fallback"],
            "engine_connected": False,
        })
    _write_csv(output / "runtime_parameter_resolution.csv", runtime_rows)

    relation_rows = [{
        "runtime_crop_id": row.runtime_crop_id,
        "parameter_crop_id": row.parameter_crop_id,
        "relation_type": row.relation_type.value,
        "status": row.status.value,
        "evidence": row.evidence,
        "source": row.source,
        "review_note": row.review_note,
    } for row in reviewed]
    _write_csv(output / "reviewed_identity_relations.csv", relation_rows)

    gaps = [{
        "runtime_crop_id": row["runtime_crop_id"],
        "status": row["resolution_status"],
        "reason": row["resolution_evidence"],
        "required_action": ("crop-form-specific external parameter evidence" if row["resolution_status"] == "AMBIGUOUS"
                            else "defensible external crop parameter record"),
        "verified_for_pilot": False,
    } for row in runtime_rows if row["resolution_status"] in {"AMBIGUOUS", "MISSING"}]
    _write_csv(output / "unresolved_parameter_gaps.csv", gaps)

    phenology_rows = [{
        "runtime_crop_name": crop["name"],
        "runtime_crop_id": app.canonical_crop_key(crop["name"]),
        "planting_source_value": "",
        "harvest_source_value": "",
        "status": "MISSING",
        "verified_for_pilot": False,
        "engine_connected": False,
        "evidence": "Frozen Akkaya runtime/project source data contains no sourced planting or harvest values.",
    } for crop in sorted(document["crops"], key=lambda row: app.canonical_crop_key(row["name"]))]
    _write_csv(output / "phenology_readiness.csv", phenology_rows)

    fallback_rows = []
    by_id = {row["runtime_crop_id"]: row for row in runtime_rows}
    for crop_id in legacy_fallback:
        row = by_id[crop_id]
        fallback_rows.append({
            "runtime_crop_id": crop_id,
            "contract_resolution_status": row["resolution_status"],
            "resolved_parameter_identity": row["resolved_parameter_identity"],
            "legacy_kc_ini": 0.6,
            "legacy_kc_mid": 1.0,
            "legacy_kc_end": 0.8,
            "legacy_stage_values": "0.2|0.3|0.3|0.2",
            "legacy_status": "LEGACY_GENERIC_FALLBACK",
            "verified_parameter_ready": False,
            "engine_connected": False,
        })
    _write_csv(output / "legacy_fallback_inventory.csv", fallback_rows)

    report = readiness(document)
    pilot = {
        "baseline_commit": BASELINE,
        "crop_parameter_readiness": {k: v for k, v in report["crop_parameter_readiness"].items() if k != "resolutions"},
        "phenology_readiness": report["phenology_readiness"],
        "pilot_readiness": report["pilot_readiness"],
        "candidate_coverage_gap": {"runtime_crop_id": "KIMYON", "candidate_rows_added": False},
        "economic_completeness_gap": {"runtime_crop_id": "DUT", "changed": False},
        "parameter_only_identity_count": len(parameter_only),
        "engine_connected": False,
    }
    _write_json(output / "pilot_readiness.json", pilot)

    changed = subprocess.run(
        ["git", "diff", "--name-only", BASELINE, "--", *PROTECTED], cwd=ROOT,
        check=True, text=True, capture_output=True,
    ).stdout.splitlines()
    guard = {
        "baseline_commit": BASELINE,
        "protected_paths": list(PROTECTED),
        "changed_protected_paths": changed,
        "protected_tree_sha256": protected_before,
        "candidate_matrix_changed": any(path.startswith("data/") for path in changed),
        "optimizer_changed": any(path == "kds/application/optimization.py" or path.startswith("kds/science/") for path in changed),
        "legacy_app_changed": "app.py" in changed,
        "engine_connected": False,
    }
    _write_json(output / "source_guard.json", guard)

    counts = {status: sum(row["resolution_status"] == status for row in runtime_rows)
              for status in ("EXACT", "REVIEWED_ALIAS", "AMBIGUOUS", "MISSING")}
    summary = f"""# V2 Scientific Phase 7 — Crop identity and phenology contract

## Resolution result

The frozen 58-crop Akkaya runtime catalog resolves to **{counts['EXACT']} exact**, **{counts['REVIEWED_ALIAS']} reviewed alias**, **{counts['AMBIGUOUS']} ambiguous**, and **{counts['MISSING']} missing** parameter identities. The reviewed layer safely resolves 9 of the 13 historical direct-lookup failures. The three Kabak forms remain ambiguous against generic `KABAK`; `SOGANTAZE` remains missing. None of the 13 crops using the unchanged legacy generic engine fallback is verified for pilot use.

## Phenology and pilot status

The frozen Akkaya runtime/project source data contains no sourced planting or harvest values. Verified phenology coverage is therefore **0/58**, and status is **PILOT_DATA_NOT_READY** while the existing demo remains **DEMO_READY**. Schema support and actual source coverage are reported separately.

## Scientific boundary

The `crop_water_parameters` and `crop_phenology` contracts support validated, versioned, explicitly confirmed project imports. They remain disconnected from the scientific engine (`engine_connected=false`). No Kc value, date, crop, candidate row, optimizer rule, or production source was changed. KIMYON candidate coverage, DUT economic completeness, Phase 5 rotation exposure 7/81 versus applied Turp options 6/32, and the inherited S2 test remain backlog items.
"""
    (output / "phase7_summary.md").write_text(summary, encoding="utf-8")
    _write_json(output / "test_report.json", test_report or {
        "status": "PENDING_FINAL_VALIDATION",
        "note": "Regenerate with final test results before milestone handoff.",
        "tier3_run": False,
        "inherited_s2_test_run": False,
    })

    if _protected_digest() != protected_before:
        raise RuntimeError("Phase 7 evidence generation mutated a protected source.")
    if changed:
        raise RuntimeError(f"Protected scientific sources changed since {BASELINE}: {changed}")
    if counts != {"EXACT": 45, "REVIEWED_ALIAS": 9, "AMBIGUOUS": 3, "MISSING": 1}:
        raise RuntimeError(f"Unexpected Phase 7 resolution counts: {counts}")
    if len(fallback_rows) != 13 or len(gaps) != 4 or len(phenology_rows) != 58:
        raise RuntimeError("Unexpected Phase 7 fallback/gap/phenology evidence counts.")
    return {"resolution_counts": counts, "legacy_fallback_count": len(fallback_rows),
            "phenology_verified_count": 0, "output": str(output)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--test-report", type=Path)
    args = parser.parse_args()
    test_report = json.loads(args.test_report.read_text(encoding="utf-8")) if args.test_report else None
    print(json.dumps(generate(args.output, test_report), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
