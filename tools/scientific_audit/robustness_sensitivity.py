"""Run and summarize the preregistered full-project robustness experiment."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import itertools
import json
import math
import multiprocessing
import platform
import statistics
import subprocess
import sys
import time
import traceback
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "experiments" / "robustness_sensitivity"
RAW = OUT / "raw_runs"
CORRECTIVE_RAW = OUT / "raw_runs_corrective"
ACTIVE_RAW = OUT / "active_run_records"
REPEAT_RAW = OUT / "determinism_repeat"
CORRECTION_VERSION = "corrective-phase-1b"
POPULATION = "FULL_REFERENCE_PROJECT_EXPERIMENT"
ANALYSIS_UNITS = 179
AREA_DA = 134919
PLANNING_YEAR = 2024
CANDIDATE_RAW_CSV_SHA256 = "022669d634b29ed551ed6e6344c212c1e60e47db1efc41a157c4073c4424df6b"
CANDIDATE_CANONICAL_RESOURCE_SHA256 = "d2ee606c03709af66dc6a9e708d85a9e749e40795c052e22a0a24b43839786bd"
CANDIDATE_GIT_BLOB_ID = "2f1a53607673126bd9436cbcdcdcf6b57000f198"
PROTOCOL = ROOT / "docs" / "robustness_sensitivity" / "experimental_protocol.md"
BASELINE_TAG = "refs/tags/v2-scientific-prepilot-freeze"
BASELINE_COMMIT = "ac02f4dc9e984438696f7da31b8d2a5841711c9e"
SCIENTIFIC_COMMIT = "bb0c6ff516a7d995c2894ee66285ebf124ac9340"
BASE_BUDGET = 10401986.556
PERENNIAL_FLOOR = 22510545.8328
CRITICAL = PERENNIAL_FLOOR / BASE_BUDGET
WATER_LEVELS = (1.0, 1.5, 2.0, CRITICAL * .95, CRITICAL, CRITICAL * 1.05, 2.5, 3.0)
CANDIDATE_SEEDS = (101, 211, 307, 401, 503, 601, 701, 809, 907, 1009)
ALGORITHMS = ("GA", "ACO", "ABC")
ALGORITHM_CONFIG = {
    "GA": {"popSize": 12, "generations": 10, "cxRate": .7, "mutRate": .08},
    "ACO": {"ants": 10, "iterations": 10, "rho": .25, "q": 1.0},
    "ABC": {"foodSources": 10, "cycles": 10, "limit": 4},
}
PROTECTED = (
    "app.py", "kds/science", "kds/application/optimization.py", "data",
    "index.html", "script.js", "style.css",
)


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def tree_hash(path: Path) -> str:
    if path.is_file():
        return file_hash(path)
    h = hashlib.sha256()
    for item in sorted(p for p in path.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        h.update(item.relative_to(path).as_posix().encode())
        h.update(b"\0")
        h.update(bytes.fromhex(file_hash(item)))
    return h.hexdigest()


def source_hashes() -> dict[str, str]:
    return {name: tree_hash(ROOT / name) for name in PROTECTED}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in fields} for row in rows)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, text=True, capture_output=True).stdout.strip()


def imports():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import app
    from kds.adapters.akkaya_demo import build_demo
    return app, build_demo


def payload(scenario: str, algorithm: str, seed: int, objective: str, ratio: float) -> dict[str, Any]:
    return {
        "scenario": scenario, "algorithm": algorithm, "seed": seed,
        "objective": objective, "water_budget_ratio": ratio,
        "config": deepcopy(ALGORITHM_CONFIG[algorithm]),
    }


def make_bundle(document: dict[str, Any], spec: dict[str, Any]):
    from kds.adapters.project_science import build_bundle
    from kds.application.optimization import configuration
    config = configuration(payload(spec["scenario"], spec["algorithm"], spec["seed"], spec["objective"], spec["water_budget_ratio"]), document)
    bundle = build_bundle(document, config)
    shock = float(spec.get("economic_shock", 0.0))
    if not shock:
        return bundle, config
    from kds.science.contract import FrozenValue
    factor = 1.0 + shock
    resources, changed = apply_uniform_profit_overlay(dict(bundle.resources), factor)
    candidates = tuple(replace(c, profit_per_da=c.profit_per_da * factor,
                               water_productivity=c.water_productivity * factor) for c in bundle.candidates)
    provenance = bundle.provenance.copy()
    provenance["experimental_overlay"] = {
        "contract": "all_connected_runtime_net_profit_inputs",
        "correction_version": CORRECTION_VERSION,
        "factor": "net_profit_per_da", "shock": shock, "multiplier": factor,
        "nonlinear_transform_policy": "evaluate_frozen_profit_realism_in_baseline_domain_then_scale_output",
        "changed_resources": changed, "source_data_mutated": False,
    }
    bundle = replace(bundle, candidates=candidates, resources=tuple(resources.items()),
                     provenance=FrozenValue.of(provenance))
    return bundle, config


def _scale_frame(frame, columns: tuple[str, ...], factor: float):
    copied = frame.copy()
    changed = []
    for column in columns:
        if column in copied.columns:
            copied[column] = copied[column].astype(float) * factor
            changed.append(column)
    return copied, changed


def _scale_mapping_rows(value: Any, fields: tuple[str, ...], factor: float):
    copied = deepcopy(value)
    changed = set()
    rows = copied.values() if isinstance(copied, dict) else copied
    for row in rows:
        if not isinstance(row, dict):
            continue
        for field in fields:
            if field in row and row[field] is not None:
                row[field] = float(row[field]) * factor
                changed.add(field)
    return copied, sorted(changed)


def apply_uniform_profit_overlay(resources: dict[str, Any], factor: float):
    """Scale every direct profit input consumed by the frozen S1/S2 runtime."""
    from kds.science.contract import FrozenValue
    output = dict(resources)
    changed: list[str] = []
    frame_fields = {
        "candidate_options": ("profit_tl_da", "profit_tl_total"),
        "regional_candidate_options": ("profit_tl_da", "profit_tl_total"),
        "crop_table": ("profit_tl_da", "profit_tl_total", "net_kar_tl_da", "net_profit_tl_da"),
        "unit_summary": ("profit_tl", "profit_tl_total", "current_profit_tl"),
    }
    for name, fields in frame_fields.items():
        if name not in output:
            continue
        value = output[name].copy()
        frame, columns = _scale_frame(value, fields, factor)
        output[name] = FrozenValue.of(frame)
        changed.extend(f"{name}.{column}" for column in columns)

    if "environment" in output:
        environment = output["environment"].copy()
        for season in ("s1", "s2"):
            if season not in environment:
                continue
            environment[season], columns = _scale_frame(
                environment[season], ("profit_tl", "profit_per_da", "profit_tl_da"), factor
            )
            changed.extend(f"environment.{season}.{column}" for column in columns)
        output["environment"] = FrozenValue.of(environment)

    mapping_fields = ("profitPerDa", "profit_per_da", "net_profit_tl_da")
    for name in ("crop_catalog", "fallback_crop_parameters"):
        if name not in output:
            continue
        value, fields = _scale_mapping_rows(output[name].copy(), mapping_fields, factor)
        output[name] = FrozenValue.of(value)
        changed.extend(f"{name}.{field}" for field in fields)

    if "units" in output:
        value, fields = _scale_mapping_rows(output["units"].copy(), ("profit_tl",), factor)
        output["units"] = FrozenValue.of(value)
        changed.extend(f"units.{field}" for field in fields)
    return output, sorted(changed)


def classify_record(record: dict[str, Any]) -> str:
    definition = record["definition"]
    feasible = record["metrics"].get("feasible") is True
    if definition["scenario"] == "S2" and not feasible:
        return "DIAGNOSTIC ONLY"
    return "SAFE WITH LIMITATION" if feasible else "DIAGNOSTIC ONLY"


def _uniform_economic_worker(bundle, factor: float, connection) -> None:
    """Run the frozen engine while preserving a globally linear profit scale.

    The engine's realism transform contains thresholds and caps. Feeding scaled
    inputs directly through that nonlinear transform breaks a uniform-scale
    experiment. The disposable worker evaluates that frozen transform in the
    baseline domain and applies the preregistered multiplier to its output.
    """
    try:
        import app
        from kds.science.execution import stable
        from kds.science.providers import ProjectDataProvider, using_provider
        original = app._apply_profit_realism

        def uniform_transform(matrix, crop_list):
            return original(matrix / factor, crop_list) * factor

        app._apply_profit_realism = uniform_transform
        config = bundle.algorithm_configuration.copy()
        with using_provider(ProjectDataProvider(bundle)):
            result = app.optimize(
                config["selected_ids"], config["algorithm"], config["objective"],
                config["water_budget_ratio"], year=bundle.planning_year,
                options=config["options"],
            )
        connection.send(("ok", stable(result)))
    except Exception as exc:
        connection.send(("error", f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"))
    finally:
        connection.close()


def execute_uniform_economic(bundle, factor: float, timeout: int = 600):
    context = multiprocessing.get_context("spawn")
    receiving, sending = context.Pipe(duplex=False)
    process = context.Process(
        target=_uniform_economic_worker, args=(bundle, factor, sending), daemon=True
    )
    process.start()
    sending.close()
    try:
        if not receiving.poll(timeout):
            raise TimeoutError("Scientific analysis exceeded the execution limit")
        status, value = receiving.recv()
        if status != "ok":
            raise RuntimeError(value)
        return value
    finally:
        receiving.close()
        process.join(timeout=2)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)


def crop_metrics(distribution: dict[str, Any]) -> dict[str, Any]:
    values = {str(k): float(v) for k, v in distribution.items() if float(v) > 0}
    total = sum(values.values())
    shares = {k: v / total for k, v in values.items()} if total else {}
    ordered = sorted(shares.items(), key=lambda item: (-item[1], item[0]))
    return {
        "crop_count": len(values), "crop_areas_da": values, "crop_shares": shares,
        "hhi": sum(v * v for v in shares.values()),
        "top1_crop": ordered[0][0] if ordered else "",
        "top1_share": ordered[0][1] if ordered else 0.0,
        "top3_crops": [name for name, _ in ordered[:3]],
        "top3_share": sum(value for _, value in ordered[:3]),
    }


def run_spec(
    document: dict[str, Any],
    spec: dict[str, Any],
    *,
    role: str = "scientific",
    raw_dir: Path = RAW,
    correction_version: str | None = None,
) -> dict[str, Any]:
    from kds.science.execution import execute, stable
    from kds.science.results import project_result, summarize
    definition = {k: spec[k] for k in ("family", "scenario", "objective", "algorithm", "seed", "water_budget_ratio", "economic_shock")}
    scenario_hash = digest(definition)
    overlay = {"water_budget_ratio": spec["water_budget_ratio"], "economic_shock": spec["economic_shock"]}
    if correction_version:
        overlay.update(
            correction_version=correction_version,
            economic_overlay_contract="all_connected_runtime_net_profit_inputs",
        )
    overlay_hash = digest(overlay)
    run_id = digest({
        "role": role, "scenario_hash": scenario_hash,
        "correction_version": correction_version,
        "input_overlay_hash": overlay_hash,
    })[:20]
    path = raw_dir / f"{run_id}.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing["scenario_hash"] != scenario_hash:
            raise RuntimeError(f"Raw run identity collision: {run_id}")
        return existing
    bundle, config = make_bundle(document, spec)
    started = time.perf_counter()
    executed_at = datetime.now(timezone.utc).isoformat()
    shock = float(spec.get("economic_shock", 0.0))
    if correction_version and spec["family"] == "ECONOMIC" and shock:
        result = execute_uniform_economic(bundle, 1.0 + shock, timeout=600)
    else:
        result = execute(bundle, timeout=600)
    elapsed = time.perf_counter() - started
    projected = project_result(result, config, document["analysis_units"])
    summary = summarize(projected, bundle)
    crops = crop_metrics(summary.get("crop_distribution_da") or {})
    water = float(summary.get("total_water_m3") or 0.0)
    profit = float(summary.get("total_profit_tl") or 0.0)
    budget = float(projected.get("water_budget_m3") or BASE_BUDGET * spec["water_budget_ratio"])
    monthly = projected.get("monthly_delivery_validation") or {}
    record = {
        "run_id": run_id, "role": role, "scenario_hash": scenario_hash,
        "input_overlay_hash": overlay_hash, "definition": definition,
        "experiment_version": correction_version or "original",
        "population": POPULATION, "analysis_units": ANALYSIS_UNITS,
        "area_da": AREA_DA, "planning_year": PLANNING_YEAR,
        "algorithm_config": ALGORITHM_CONFIG[spec["algorithm"]],
        "executed_at_utc": executed_at, "runtime_seconds": elapsed,
        "metrics": {
            "feasible": projected.get("feasible"), "annual_budget_feasible": water <= budget + 1e-6,
            "monthly_delivery_status": monthly.get("status", "not_available"),
            "monthly_violating_months": monthly.get("violating_months"),
            "water_budget_m3": budget, "total_water_m3": water, "total_profit_tl": profit,
            "efficiency_tl_per_m3": profit / water if water else 0.0, **crops,
        },
        "result": stable(projected),
    }
    record["classification"] = classify_record(record)
    raw_dir.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"Refusing to overwrite immutable raw output: {path}")
    write_json(path, record)
    return record


def definition_key(definition: dict[str, Any]) -> str:
    return digest({k: definition[k] for k in (
        "family", "scenario", "objective", "algorithm", "seed",
        "water_budget_ratio", "economic_shock",
    )})


def corrective_specs() -> list[dict[str, Any]]:
    return [
        spec for spec in plan()
        if spec["family"] == "ECONOMIC" and spec["scenario"] == "S2"
    ]


def run_corrective() -> None:
    app, build_demo = imports()
    document = build_demo(app.DATA_DIR)
    for index, spec in enumerate(corrective_specs(), 1):
        print(
            f"[corrective {index}/5] S2 economic shock={spec['economic_shock']:+.0%}",
            flush=True,
        )
        run_spec(
            document, spec, role="scientific-corrective",
            raw_dir=CORRECTIVE_RAW, correction_version=CORRECTION_VERSION,
        )
    build_active_records()


def run_determinism_repeat() -> None:
    app, build_demo = imports()
    document = build_demo(app.DATA_DIR)
    spec = next(s for s in corrective_specs() if s["economic_shock"] == -0.2)
    repeated = run_spec(
        document, spec, role="scientific-corrective-repeat",
        raw_dir=REPEAT_RAW, correction_version=CORRECTION_VERSION,
    )
    original = next(
        r for r in _load_records(CORRECTIVE_RAW, "scientific-corrective")
        if r.get("experiment_version") == CORRECTION_VERSION
        and definition_key(r["definition"]) == definition_key(spec)
    )
    evidence = {
        "scenario": spec,
        "original_run_id": original["run_id"],
        "repeat_run_id": repeated["run_id"],
        "original_result_sha256": digest(original["result"]),
        "repeat_result_sha256": digest(repeated["result"]),
        "timestamp_runtime_excluded": True,
        "same_result": digest(original["result"]) == digest(repeated["result"]),
    }
    write_json(OUT / "corrective_determinism.json", evidence)
    if not evidence["same_result"]:
        raise RuntimeError("Corrective economic repeat was not deterministic")


def _load_records(directory: Path, role: str) -> list[dict[str, Any]]:
    records = []
    for path in sorted(directory.glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("role") == role:
            value["_source_path"] = path
            records.append(value)
    return records


def build_active_records() -> None:
    original = {definition_key(r["definition"]): r for r in _load_records(RAW, "scientific")}
    corrected = {
        definition_key(r["definition"]): r
        for r in _load_records(CORRECTIVE_RAW, "scientific-corrective")
        if r.get("experiment_version") == CORRECTION_VERSION
    }
    expected = {definition_key(spec): spec for spec in plan()}
    if set(original) != set(expected):
        raise RuntimeError("Original scientific raw-run set does not match the preregistered grid")
    if set(corrected) != {definition_key(spec) for spec in corrective_specs()}:
        raise RuntimeError("Corrective raw-run set is incomplete or contains an unplanned run")
    ACTIVE_RAW.mkdir(parents=True, exist_ok=True)
    for old in ACTIVE_RAW.glob("*.json"):
        old.unlink()
    for key in sorted(expected):
        source = corrected.get(key, original[key])
        source_path = source.pop("_source_path")
        result = source["result"]
        unit_ids = sorted(str(row["id"]) for row in result.get("parcels", []))
        active = {k: deepcopy(v) for k, v in source.items() if k != "result"}
        active.update(
            population=POPULATION,
            analysis_units=ANALYSIS_UNITS,
            analysis_unit_ids=unit_ids,
            area_da=AREA_DA,
            planning_year=PLANNING_YEAR,
            classification=classify_record(source),
            active_record_version=CORRECTION_VERSION,
            source_raw_path=source_path.relative_to(ROOT).as_posix(),
            source_raw_sha256=file_hash(source_path),
            result_sha256=digest(result),
            execution_status=(
                "CORRECTIVE_REEXECUTION"
                if key in corrected else "UNCHANGED_ORIGINAL_EXECUTION"
            ),
        )
        write_json(ACTIVE_RAW / f"{active['run_id']}.json", active)


def pilot() -> None:
    app, build_demo = imports()
    document = build_demo(app.DATA_DIR)
    specs = [{"family": "PILOT", "scenario": "S1", "objective": "water_saving", "algorithm": a,
              "seed": 101, "water_budget_ratio": 1.0, "economic_shock": 0.0} for a in ALGORITHMS]
    records = [run_spec(document, spec, role="pilot") for spec in specs]
    repeat_spec = dict(specs[0]); repeat_spec["family"] = "PILOT_DETERMINISM_REPEAT"
    repeat = run_spec(document, repeat_spec, role="pilot-repeat")
    stable_fields = lambda r: {"metrics": r["metrics"], "result": r["result"]}
    deterministic = stable_fields(records[0]) == stable_fields(repeat)
    median = statistics.median(r["runtime_seconds"] for r in records)
    projected_seconds = 3 * 2 * 10 * median
    selected = 10 if projected_seconds <= 3600 else 5
    evidence = {
        "pilot_runs": [{"run_id": r["run_id"], "algorithm": r["definition"]["algorithm"],
                        "runtime_seconds": r["runtime_seconds"]} for r in records],
        "determinism_repeat_run_id": repeat["run_id"], "same_seed_deterministic": deterministic,
        "median_runtime_seconds": median, "projected_ten_seed_core_seconds": projected_seconds,
        "decision_threshold_seconds": 3600, "selected_seed_count": selected,
        "selected_seeds": list(CANDIDATE_SEEDS[:selected]),
    }
    write_json(OUT / "pilot_evidence.json", evidence)
    print(json.dumps(evidence, indent=2))


def selected_seeds() -> tuple[int, ...]:
    evidence = json.loads((OUT / "pilot_evidence.json").read_text(encoding="utf-8"))
    return tuple(int(v) for v in evidence["selected_seeds"])


def plan() -> list[dict[str, Any]]:
    seeds = selected_seeds()
    rows: list[dict[str, Any]] = []
    for scenario, ratio in itertools.product(("S1", "S2"), WATER_LEVELS):
        rows.append({"family": "WATER_THRESHOLD", "scenario": scenario, "objective": "water_saving",
                     "algorithm": "GA", "seed": seeds[0], "water_budget_ratio": ratio, "economic_shock": 0.0})
    for scenario, algorithm, seed in itertools.product(("S1", "S2"), ALGORITHMS, seeds):
        rows.append({"family": "ALGORITHM_SEED", "scenario": scenario, "objective": "water_saving",
                     "algorithm": algorithm, "seed": seed, "water_budget_ratio": 1.0, "economic_shock": 0.0})
    for scenario, shock in itertools.product(("S1", "S2"), (-.2, -.1, 0.0, .1, .2)):
        rows.append({"family": "ECONOMIC", "scenario": scenario, "objective": "max_profit",
                     "algorithm": "GA", "seed": seeds[0], "water_budget_ratio": 1.0, "economic_shock": shock})
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        identity = digest({k: row[k] for k in ("scenario", "objective", "algorithm", "seed", "water_budget_ratio", "economic_shock")})
        if identity in unique:
            unique[identity]["family"] += "+" + row["family"]
        else:
            unique[identity] = row
    return list(unique.values())


def run_all(shard_index: int = 0, shard_count: int = 1) -> None:
    app, build_demo = imports()
    document = build_demo(app.DATA_DIR)
    all_rows = plan()
    if shard_index == 0:
        write_csv(OUT / "scenario_grid.csv", [{**r, "scenario_hash": digest(r)} for r in all_rows])
    rows = [row for index, row in enumerate(all_rows) if index % shard_count == shard_index]
    for index, spec in enumerate(rows, 1):
        print(f"[shard {shard_index + 1}/{shard_count}; {index}/{len(rows)}] {spec['family']} {spec['scenario']} {spec['algorithm']} seed={spec['seed']} ratio={spec['water_budget_ratio']:.9g} shock={spec['economic_shock']:+.0%}", flush=True)
        run_spec(document, spec)


def numeric_stats(values: list[float], prefix: str) -> dict[str, float]:
    mean = statistics.fmean(values) if values else 0.0
    sd = statistics.stdev(values) if len(values) > 1 else 0.0
    return {f"{prefix}_mean": mean, f"{prefix}_median": statistics.median(values) if values else 0.0,
            f"{prefix}_sd": sd, f"{prefix}_cv": sd / abs(mean) if mean else 0.0,
            f"{prefix}_min": min(values) if values else 0.0, f"{prefix}_max": max(values) if values else 0.0}


def distances(a: dict[str, float], b: dict[str, float]) -> dict[str, float]:
    keys = set(a) | set(b); sa = sum(a.values()); sb = sum(b.values())
    pa = {k: a.get(k, 0) / sa for k in keys} if sa else {k: 0 for k in keys}
    pb = {k: b.get(k, 0) / sb for k in keys} if sb else {k: 0 for k in keys}
    denom = sum(a.get(k, 0) + b.get(k, 0) for k in keys)
    union = sum(max(a.get(k, 0), b.get(k, 0)) for k in keys)
    return {"l1_share_distance": sum(abs(pa[k] - pb[k]) for k in keys),
            "bray_curtis": sum(abs(a.get(k, 0) - b.get(k, 0)) for k in keys) / denom if denom else 0.0,
            "weighted_jaccard": sum(min(a.get(k, 0), b.get(k, 0)) for k in keys) / union if union else 1.0}


def flatten(record: dict[str, Any]) -> dict[str, Any]:
    d, m = record["definition"], record["metrics"]
    return {**d, "scenario_id": "SCN-" + record["scenario_hash"][:12],
            "population": POPULATION, "analysis_units": ANALYSIS_UNITS, "area_da": AREA_DA,
            "planning_year": PLANNING_YEAR, "claim_classification": classify_record(record),
            "run_id": record["run_id"], "scenario_hash": record["scenario_hash"],
            "input_overlay_hash": record["input_overlay_hash"], "runtime_seconds": record["runtime_seconds"],
            **{k: (canonical(v) if isinstance(v, (dict, list)) else v) for k, v in m.items()}}


def build_outputs() -> None:
    planned = plan()
    if not ACTIVE_RAW.exists():
        build_active_records()
    records = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(ACTIVE_RAW.glob("*.json"))
    ]
    if len(records) != len(planned):
        raise RuntimeError(f"Expected {len(planned)} scientific raw runs; found {len(records)}")
    flat = [flatten(r) for r in records]
    write_csv(OUT / "run_level_results.csv", flat)
    groups: dict[tuple, list[dict]] = {}
    for r in records:
        d = r["definition"]
        key = (d["family"], d["scenario"], d["objective"], d["water_budget_ratio"], d["economic_shock"])
        groups.setdefault(key, []).append(r)
    summary_rows = []
    for key, group in sorted(groups.items()):
        row = dict(zip(("family", "scenario", "objective", "water_budget_ratio", "economic_shock"), key))
        for metric in ("total_water_m3", "total_profit_tl", "efficiency_tl_per_m3", "hhi"):
            row.update(numeric_stats([float(r["metrics"][metric]) for r in group], metric))
        row["runs"] = len(group); row["engine_feasible_rate"] = statistics.fmean(bool(r["metrics"]["feasible"]) for r in group)
        row["annual_budget_feasible_rate"] = statistics.fmean(bool(r["metrics"]["annual_budget_feasible"]) for r in group)
        row["claim_classification"] = (
            "DIAGNOSTIC ONLY"
            if any(classify_record(r) == "DIAGNOSTIC ONLY" for r in group)
            else "SAFE WITH LIMITATION"
        )
        summary_rows.append(row)
    write_csv(OUT / "scenario_summary.csv", summary_rows)

    core = [r for r in records if "ALGORITHM_SEED" in r["definition"]["family"]]
    seed_rows = []
    for key, group_iter in itertools.groupby(sorted(core, key=lambda r:(r["definition"]["scenario"],r["definition"]["algorithm"])), key=lambda r:(r["definition"]["scenario"],r["definition"]["algorithm"])):
        group=list(group_iter); row={"scenario":key[0],"algorithm":key[1],"seeds":len(group),
                                    "claim_classification":classify_record(group[0])}
        for metric in ("total_water_m3","total_profit_tl","efficiency_tl_per_m3","hhi"):
            row.update(numeric_stats([float(r["metrics"][metric]) for r in group],metric))
        seed_rows.append(row)
    write_csv(OUT / "seed_variability.csv", seed_rows)

    index={(r["definition"]["scenario"],r["definition"]["algorithm"],r["definition"]["seed"]):r for r in core}
    agreement=[]; stability=[]
    for scenario in ("S1","S2"):
        for seed in selected_seeds():
            for aa,bb in itertools.combinations(ALGORITHMS,2):
                a,b=index[(scenario,aa,seed)],index[(scenario,bb,seed)]
                dist=distances(a["metrics"]["crop_areas_da"],b["metrics"]["crop_areas_da"])
                row={"scenario":scenario,"seed":seed,"algorithm_a":aa,"algorithm_b":bb,**dist,
                     "claim_classification":classify_record(a),
                     "top1_agreement":a["metrics"]["top1_crop"]==b["metrics"]["top1_crop"],
                     "top3_jaccard":len(set(a["metrics"]["top3_crops"])&set(b["metrics"]["top3_crops"]))/max(1,len(set(a["metrics"]["top3_crops"])|set(b["metrics"]["top3_crops"]))),
                     "water_difference_pct":100*(a["metrics"]["total_water_m3"]-b["metrics"]["total_water_m3"])/max(abs(b["metrics"]["total_water_m3"]),1e-12),
                     "profit_difference_pct":100*(a["metrics"]["total_profit_tl"]-b["metrics"]["total_profit_tl"])/max(abs(b["metrics"]["total_profit_tl"]),1e-12),
                     "efficiency_difference_pct":100*(a["metrics"]["efficiency_tl_per_m3"]-b["metrics"]["efficiency_tl_per_m3"])/max(abs(b["metrics"]["efficiency_tl_per_m3"]),1e-12),
                     "feasible_agreement":a["metrics"]["feasible"]==b["metrics"]["feasible"]}
                agreement.append(row); stability.append({**row,"comparison_type":"algorithm_matched_seed"})
    write_csv(OUT / "algorithm_agreement.csv", agreement)
    for scenario,algorithm in itertools.product(("S1","S2"),ALGORITHMS):
        for seed_a,seed_b in itertools.combinations(selected_seeds(),2):
            base=index[(scenario,algorithm,seed_a)]; other=index[(scenario,algorithm,seed_b)]; dist=distances(base["metrics"]["crop_areas_da"],other["metrics"]["crop_areas_da"])
            stability.append({"comparison_type":"seed_pair","scenario":scenario,"seed":seed_b,"seed_a":seed_a,"seed_b":seed_b,"algorithm_a":algorithm,"algorithm_b":algorithm,**dist,
                              "claim_classification":classify_record(base),
                              "top1_agreement":base["metrics"]["top1_crop"]==other["metrics"]["top1_crop"],
                              "top3_jaccard":len(set(base["metrics"]["top3_crops"])&set(other["metrics"]["top3_crops"]))/max(1,len(set(base["metrics"]["top3_crops"])|set(other["metrics"]["top3_crops"])))})
    write_csv(OUT / "crop_share_stability.csv", stability)

    water=[flatten(r) for r in records if "WATER_THRESHOLD" in r["definition"]["family"]]
    water.sort(key=lambda r:(r["scenario"],float(r["water_budget_ratio"])))
    for scenario in ("S1","S2"):
      scenario_rows=[r for r in water if r["scenario"]==scenario]
      previous=None
      for row in scenario_rows:
        row["critical_multiplier"] = CRITICAL
        row["distance_from_critical"] = float(row["water_budget_ratio"])-CRITICAL
        row["threshold_interpretation"] = "STRUCTURAL_MODEL_OUTPUT_NOT_REAL_WORLD_AVAILABILITY"
        row["annual_threshold_classification"] = "SAFE WITH LIMITATION"
        row["plan_output_classification"] = row["claim_classification"]
        row["annual_feasibility_transition_from_previous"] = bool(previous is not None and str(previous["annual_budget_feasible"]).lower()!=str(row["annual_budget_feasible"]).lower())
        row["transition_interval_lower"] = previous["water_budget_ratio"] if row["annual_feasibility_transition_from_previous"] else ""
        row["transition_interval_upper"] = row["water_budget_ratio"] if row["annual_feasibility_transition_from_previous"] else ""
        previous=row
    write_csv(OUT / "water_threshold_analysis.csv", water)
    economic=[flatten(r) for r in records if "ECONOMIC" in r["definition"]["family"]]
    baselines = {
        scenario: next(
            float(r["total_profit_tl"]) for r in economic
            if r["scenario"] == scenario and float(r["economic_shock"]) == 0.0
        )
        for scenario in ("S1", "S2")
    }
    for row in economic:
        row["factor"]="net_profit_per_da"; row["price_status"]="PRICE_SENSITIVITY_NOT_EXECUTABLE_ON_FROZEN_ENGINE"; row["yield_status"]="YIELD_SENSITIVITY_NOT_EXECUTABLE_ON_FROZEN_ENGINE"
        row["expected_linear_profit_tl"] = baselines[row["scenario"]] * (1.0 + float(row["economic_shock"]))
        row["linear_scaling_residual_tl"] = float(row["total_profit_tl"]) - row["expected_linear_profit_tl"]
        row["linear_scaling_tolerance_tl"] = max(1e-6, abs(row["expected_linear_profit_tl"]) * 1e-12)
        peers=[r for r in economic if r["scenario"]==row["scenario"]]
        row["composition_response"]="UNIFORM_SHOCK_INVARIANT_OBSERVED" if len({(r["top1_crop"],r["hhi"],r["crop_shares"]) for r in peers})==1 else "COMPOSITION_CHANGED"
    write_csv(OUT / "economic_sensitivity.csv", economic)

    source_before=json.loads((OUT/"source_guard_before.json").read_text(encoding="utf-8")) if (OUT/"source_guard_before.json").exists() else source_hashes()
    source_after=source_hashes(); guard={"protected_paths":list(PROTECTED),"before":source_before,"after":source_after,"unchanged":source_before==source_after}
    write_json(OUT/"source_guard.json",guard)
    manifest={"baseline_tag":BASELINE_TAG,"baseline_commit":BASELINE_COMMIT,"scientific_source_commit":SCIENTIFIC_COMMIT,
              "population":{"label":"FULL_REFERENCE_PROJECT_EXPERIMENT","analysis_units":179,"area_da":134919},
              "scenario_grid_hash":file_hash(OUT/"scenario_grid.csv"),"selected_seeds":list(selected_seeds()),"algorithms":list(ALGORITHMS),
              "objectives":{"water_and_robustness":"water_saving","economic":"max_profit","excluded":["water_efficiency"]},
              "scenarios":["S1","S2"],"formulas":{"critical_multiplier":"protected_perennial_floor_m3 / base_engine_budget_m3","hhi":"sum(crop_share^2)","l1":"sum(abs(p-q))","bray_curtis":"sum(abs(a-b))/sum(a+b)","weighted_jaccard":"sum(min(a,b))/sum(max(a,b))"},
              "excluded_factors":{"price":"not independently connected","yield":"not independently connected","combined_stress":"requires new preregistration"},
              "excluded_runs":["price shocks: connected=false","yield shocks: connected=false","water_efficiency objective: preregistered computational exclusion","combined stress: requires new preregistration"],
              "failed_runs":[],"active_publication_runs":len(records),
              "original_scientific_runs":len(_load_records(RAW,"scientific")),
              "corrective_reexecuted_runs":sum(
                  r.get("experiment_version")==CORRECTION_VERSION
                  for r in _load_records(CORRECTIVE_RAW,"scientific-corrective")
              ),
              "superseded_runs":len(corrective_specs()),
              "raw_run_count":len(records),
              "software":{"python":platform.python_version(),"platform":platform.platform(),"numpy":importlib.metadata.version("numpy"),"pandas":importlib.metadata.version("pandas")},
              "dataset_hashes":{},
              "candidate_hash_domains":{
                  "candidate_raw_csv_sha256":CANDIDATE_RAW_CSV_SHA256,
                  "candidate_canonical_resource_sha256":CANDIDATE_CANONICAL_RESOURCE_SHA256,
                  "candidate_git_blob_id":CANDIDATE_GIT_BLOB_ID,
              },
              "candidate_hash":CANDIDATE_CANONICAL_RESOURCE_SHA256,
              "candidate_hash_alias_semantics":"backward-compatible alias of candidate_canonical_resource_sha256",
              "source_guard_unchanged":guard["unchanged"]}
    app,build_demo=imports(); document=build_demo(app.DATA_DIR); from kds.adapters.project_science import build_bundle
    from kds.application.optimization import configuration
    b=build_bundle(document,configuration(payload("S1","GA",selected_seeds()[0],"water_saving",1.0),document)); resources=dict(b.resources)
    manifest["dataset_hashes"]={k:v.digest for k,v in resources.items()}
    if resources["candidate_options"].digest != CANDIDATE_CANONICAL_RESOURCE_SHA256:
        raise RuntimeError("Canonical candidate resource hash changed")
    candidate_path=ROOT/"data"/"excel_derived"/"combined_parcel_candidate_matrix_2024.csv"
    if file_hash(candidate_path) != CANDIDATE_RAW_CSV_SHA256:
        raise RuntimeError("Raw candidate CSV hash changed")
    superseded = sorted(
        r["run_id"] for r in _load_records(RAW,"scientific")
        if r["definition"]["scenario"]=="S2" and r["definition"]["family"]=="ECONOMIC"
    )
    active_ids={r["run_id"] for r in records}
    manifest["superseded_experiment_runs"]=superseded
    manifest["active_run_ids"]=sorted(active_ids)
    manifest["baseline_reproduction"]={"analysis_units":len(document["analysis_units"]),"area_da":sum(u["area_da"] for u in document["analysis_units"]),"candidate_rows":len(resources["candidate_options"].copy()),"crop_count":len(document["crops"]),"current_pattern_calculated_gross_demand_m3":document["water_budget"]["amount"],"catalog_derived_current_pattern_profit_tl":sum(float(u["metadata"]["current_profit_tl"]) for u in document["analysis_units"])}
    write_json(OUT/"experiment_manifest.json",manifest)
    protocol_text=PROTOCOL.read_text(encoding="utf-8"); (OUT/"experimental_protocol.md").write_text(protocol_text,encoding="utf-8")
    build_publication_docs(records, summary_rows, seed_rows, agreement, water, economic, manifest)


def build_publication_docs(records, summaries, seed_rows, agreement, water, economic, manifest):
    claim = """# Claim boundary

S1 is full-project computational robustness evidence classified **SAFE WITH LIMITATION**. S2 plan outputs are infeasible-search diagnostics classified **DIAGNOSTIC ONLY** under the current constraints. An annually feasible S2 row remains diagnostic when monthly delivery is violated and overall feasibility is false.

The S2 annual threshold is only a model annual-budget threshold. The economic experiment tests a uniform scale change across connected net-profit inputs; it does not test price or yield independently.

These outputs do not establish official water allocation, measured water use, field validation, multi-year validation, real-world feasibility, market feasibility, real-farm profitability or income, farmer behavior, or external agronomic validity. The single-year reviewer issue and economic uncertainty are only partially improved; field validation, multi-year behavior, market capacity, farmer behavior, and external agronomic validity remain unresolved.
"""
    (OUT/"claim_boundary.md").write_text(claim,encoding="utf-8")
    water_transitions={s:[r for r in water if r["scenario"]==s and str(r["annual_budget_feasible"]).lower()=="true"] for s in ("S1","S2")}
    lines=["# Publication tables","","Classifications apply per scenario segment; infeasible S2 plan metrics are never presented as feasible recommendation evidence.","","## Table 1. Experimental design","","Classification: **SAFE WITH LIMITATION**.","","| Population | Scenarios | Algorithms | Seeds | Active scientific runs |","|---|---|---|---|---:|",f"| 179 units / 134,919 da | S1, S2 | GA, ACO, ABC | {', '.join(map(str,manifest['selected_seeds']))} | {len(records)} |","","## Table 2. Water-budget sensitivity","", "| Scenario | First tested annual-feasible multiplier | Overall feasible at that row | Annual-threshold evidence | Plan-output classification |","|---|---:|---|---|---|"]
    for scenario,rows in water_transitions.items():
        first=rows[0] if rows else None
        plan_class = "DIAGNOSTIC ONLY" if scenario == "S2" else "SAFE WITH LIMITATION"
        lines.append(f"| {scenario} | {first['water_budget_ratio'] if first else 'none'} | {first['feasible'] if first else 'n/a'} | SAFE WITH LIMITATION | {plan_class} |")
    lines += ["","S2 first becomes annually feasible at the tested 2.5 multiplier, while monthly delivery still violates constraints and overall feasibility remains false.","","## Table 3. Algorithm agreement","","| Scenario | Mean weighted Jaccard | Top-1 agreement rate | Feasibility agreement rate | Classification |","|---|---:|---:|---:|---|"]
    for scenario in ("S1","S2"):
        rr=[r for r in agreement if r["scenario"]==scenario]; lines.append(f"| {scenario} | {statistics.fmean(r['weighted_jaccard'] for r in rr):.6f} | {statistics.fmean(bool(r['top1_agreement']) for r in rr):.6f} | {statistics.fmean(bool(r['feasible_agreement']) for r in rr):.6f} | {rr[0]['claim_classification']} |")
    lines += ["","## Table 4. Seed variability","","| Scenario | Algorithm | Water CV | Profit CV | HHI CV | Classification |","|---|---|---:|---:|---:|---|"]
    for r in seed_rows: lines.append(f"| {r['scenario']} | {r['algorithm']} | {r['total_water_m3_cv']:.6g} | {r['total_profit_tl_cv']:.6g} | {r['hhi_cv']:.6g} | {r['claim_classification']} |")
    lines += ["","## Table 5. Economic robustness","","| Scenario | Profit at -20% | Profit at baseline | Profit at +20% | Composition response | Classification |","|---|---:|---:|---:|---|---|"]
    for scenario in ("S1","S2"):
        rr=sorted([r for r in economic if r["scenario"]==scenario],key=lambda r:float(r["economic_shock"])); lines.append(f"| {scenario} | {float(rr[0]['total_profit_tl']):.3f} | {float(rr[2]['total_profit_tl']):.3f} | {float(rr[4]['total_profit_tl']):.3f} | {rr[0]['composition_response']} | {rr[0]['claim_classification']} |")
    lines += ["","S2 economic values show only the uniform profit-scale response of infeasible S2 search outputs.","","## Table 6. Crop-pattern stability","","| Scenario | Mean algorithm weighted Jaccard | Mean algorithm Bray-Curtis | Mean top-3 Jaccard | Classification |","|---|---:|---:|---:|---|"]
    for scenario in ("S1","S2"):
        rr=[r for r in agreement if r["scenario"]==scenario]; lines.append(f"| {scenario} | {statistics.fmean(r['weighted_jaccard'] for r in rr):.6f} | {statistics.fmean(r['bray_curtis'] for r in rr):.6f} | {statistics.fmean(r['top3_jaccard'] for r in rr):.6f} | {rr[0]['claim_classification']} |")
    lines += ["","See the CSV files for complete precision and every run. Values are frozen-model outputs within the claim boundary.",""]
    (OUT/"publication_tables.md").write_text("\n".join(lines),encoding="utf-8")
    figures=[
      {"figure_id":"F1","title":"Annual water feasibility across budget multipliers","source":"water_threshold_analysis.csv","x":"water_budget_ratio","y":"total_water_m3 and water_budget_m3","group":"scenario","s1_use":"SAFE WITH LIMITATION","s2_use":"ANNUAL THRESHOLD SAFE WITH LIMITATION; PLAN OUTPUT DIAGNOSTIC ONLY","status":"DATA_READY"},
      {"figure_id":"F2","title":"Algorithm agreement in crop shares","source":"algorithm_agreement.csv","x":"algorithm pair","y":"weighted_jaccard","group":"scenario","s1_use":"SAFE WITH LIMITATION","s2_use":"DIAGNOSTIC ONLY","status":"DATA_READY"},
      {"figure_id":"F3","title":"Seed variability of water and profit","source":"seed_variability.csv","x":"algorithm","y":"coefficient of variation","group":"scenario","s1_use":"SAFE WITH LIMITATION","s2_use":"DIAGNOSTIC ONLY","status":"DATA_READY"},
      {"figure_id":"F4","title":"Net-profit sensitivity","source":"economic_sensitivity.csv","x":"economic_shock","y":"total_profit_tl","group":"scenario","s1_use":"SAFE WITH LIMITATION","s2_use":"DIAGNOSTIC ONLY","status":"DATA_READY"},
      {"figure_id":"F5","title":"Crop-share stability by scenario","source":"crop_share_stability.csv","x":"comparison","y":"weighted_jaccard and Bray-Curtis","group":"scenario","s1_use":"SAFE WITH LIMITATION","s2_use":"DIAGNOSTIC ONLY","status":"DATA_READY"},
    ]
    write_csv(OUT/"publication_figure_manifest.csv",figures)
    follow="""# Minor pre-pilot follow-ups\n\nThese inherited items remain non-blocking and did not alter the experiment: the freeze helper has no `--follow` mode, Git reports platform EOL normalization warnings, and a historical Phase 5 inventory can flag `__pycache__` artifacts. Scientific sources and engine behavior remain unchanged.\n"""
    (OUT/"minor_prepilot_followups.md").write_text(follow,encoding="utf-8")
    audit="""# Experimental data-flow audit

| Factor | Source value | Runtime consumer | Transformation | Objective effect | Result field | Connected |
|---|---|---|---|---|---|---|
| Annual water budget | Project budget and frozen reservoir-delivery resources | configuration and optimizer budget handling | explicit `water_budget_ratio` | feasibility penalties and guards | budget, feasibility, total water | true |
| Net profit per da | candidate, seasonal, catalog, fallback and unit profit fields | S1/S2 candidate matrices and final projection | one in-memory multiplier on copied bundle values | profit score and reported profit | total profit, TL/m3, composition | true |
| Sale price | descriptive source columns | no independent accepted-path consumer | none | none | none | false |
| Yield | descriptive source columns | no independent accepted-path consumer | none | none | none | false |

S1 reports the current-pattern calculated gross-demand budget (100,700,080.81 m3 at ratio 1.0), whereas S2 reports the reservoir-derived engine scenario budget (10,401,986.556 m3 at ratio 1.0). The protected-perennial critical multiplier therefore applies only to the S2 annual-budget boundary.
"""
    (OUT/"data_flow_audit.md").write_text(audit,encoding="utf-8")
    lineage="""# Economic overlay lineage

The corrective overlay implements the original preregistered uniform net-profit shock. It changes copied values inside a disposable scientific bundle; production files and frozen sources remain byte-identical.

| Source object | Profit field | Frozen consumer | Overlay transformation | Result contribution |
|---|---|---|---|---|
| candidate_options / regional_candidate_options | profit_tl_da, profit_tl_total | S1 matrix and candidate selection | × (1 + shock) | objective profit and projected crop profit |
| environment.s1 / environment.s2 | profit_tl, profit_per_da, profit_tl_da | primary and secondary seasonal matrices | × (1 + shock) | seasonal objective and plan rows |
| crop_catalog | profitPerDa, profit_per_da, net_profit_tl_da | S2 perennial locks, fallbacks and final-plan projection | × (1 + shock) | locked/final crop profit |
| fallback_crop_parameters | profit_per_da aliases | missing seasonal-cell fallback | × (1 + shock) | fallback candidate profit |
| crop_table | direct net-profit aliases | catalog/table fallback paths | × (1 + shock) | fallback plan profit |
| units / unit_summary | current direct-profit fields | baseline/final projection paths | × (1 + shock) | baseline and projected profit |
| ScientificInputBundle.candidates | CandidateOption.profit_per_da and derived water_productivity | canonical candidate consumer | × (1 + shock) | candidate objective inputs |

Price and yield remain disconnected from the independent perturbation contract:
`PRICE_SENSITIVITY_NOT_EXECUTABLE_ON_FROZEN_ENGINE` and
`YIELD_SENSITIVITY_NOT_EXECUTABLE_ON_FROZEN_ENGINE`.

## Superseded evidence

The rejected S2 implementation omitted `crop_catalog.profitPerDa` and related direct paths. Historical residuals were approximately +2,739,224.62 TL at −20%, +1,376,302.23 TL at −10%, −1,375,045.47 TL at +10%, and −2,741,104.48 TL at +20%. Those five original run identities remain immutable historical evidence and are excluded from active summaries.
"""
    (OUT/"economic_overlay_lineage.md").write_text(lineage,encoding="utf-8")


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("command",choices=("guard","pilot","grid","run","correct","repeat","activate","build")); parser.add_argument("--shard-index",type=int,default=0); parser.add_argument("--shard-count",type=int,default=1); args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    if args.command=="guard": write_json(OUT/"source_guard_before.json",source_hashes())
    elif args.command=="pilot": pilot()
    elif args.command=="grid": write_csv(OUT/"scenario_grid.csv",[{**r,"scenario_hash":digest(r)} for r in plan()])
    elif args.command=="run":
        if args.shard_count < 1 or not 0 <= args.shard_index < args.shard_count:
            parser.error("shard index must be in [0, shard count)")
        run_all(args.shard_index,args.shard_count)
    elif args.command=="correct": run_corrective()
    elif args.command=="repeat": run_determinism_repeat()
    elif args.command=="activate": build_active_records()
    elif args.command=="build": build_outputs()


if __name__ == "__main__":
    main()
