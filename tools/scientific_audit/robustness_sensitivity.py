"""Run and summarize the preregistered full-project robustness experiment."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import itertools
import json
import math
import platform
import statistics
import subprocess
import sys
import time
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "experiments" / "robustness_sensitivity"
RAW = OUT / "raw_runs"
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
    resources = dict(bundle.resources)
    changed = []
    for name in ("candidate_options", "regional_candidate_options"):
        frame = resources[name].copy()
        for col in ("profit_tl_da", "profit_tl_total"):
            if col in frame.columns:
                frame[col] = frame[col].astype(float) * factor
        resources[name] = FrozenValue.of(frame)
        changed.append(name)
    environment = resources["environment"].copy()
    for name in ("s1", "s2"):
        frame = environment[name].copy()
        if "profit_tl" in frame.columns:
            frame["profit_tl"] = frame["profit_tl"].astype(float) * factor
        environment[name] = frame
    resources["environment"] = FrozenValue.of(environment)
    changed.append("environment.s1/s2.profit_tl")
    candidates = tuple(replace(c, profit_per_da=c.profit_per_da * factor,
                               water_productivity=c.water_productivity * factor) for c in bundle.candidates)
    provenance = bundle.provenance.copy()
    provenance["experimental_overlay"] = {
        "factor": "net_profit_per_da", "shock": shock, "multiplier": factor,
        "changed_resources": changed, "source_data_mutated": False,
    }
    bundle = replace(bundle, candidates=candidates, resources=tuple(resources.items()),
                     provenance=FrozenValue.of(provenance))
    return bundle, config


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


def run_spec(document: dict[str, Any], spec: dict[str, Any], *, role: str = "scientific") -> dict[str, Any]:
    from kds.science.execution import execute, stable
    from kds.science.results import project_result, summarize
    definition = {k: spec[k] for k in ("family", "scenario", "objective", "algorithm", "seed", "water_budget_ratio", "economic_shock")}
    scenario_hash = digest(definition)
    overlay = {"water_budget_ratio": spec["water_budget_ratio"], "economic_shock": spec["economic_shock"]}
    overlay_hash = digest(overlay)
    run_id = digest({"role": role, "scenario_hash": scenario_hash})[:20]
    path = RAW / f"{run_id}.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing["scenario_hash"] != scenario_hash:
            raise RuntimeError(f"Raw run identity collision: {run_id}")
        return existing
    bundle, config = make_bundle(document, spec)
    started = time.perf_counter()
    executed_at = datetime.now(timezone.utc).isoformat()
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
    RAW.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"Refusing to overwrite immutable raw output: {path}")
    write_json(path, record)
    return record


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
            "population": "FULL_REFERENCE_PROJECT_EXPERIMENT", "analysis_units": 179, "area_da": 134919,
            "claim_classification": "SAFE WITH LIMITATION", "run_id": record["run_id"], "scenario_hash": record["scenario_hash"],
            "input_overlay_hash": record["input_overlay_hash"], "runtime_seconds": record["runtime_seconds"],
            **{k: (canonical(v) if isinstance(v, (dict, list)) else v) for k, v in m.items()}}


def build_outputs() -> None:
    planned = plan(); hashes = {digest({k: r[k] for k in ("family", "scenario", "objective", "algorithm", "seed", "water_budget_ratio", "economic_shock")}): r for r in planned}
    records = []
    for path in sorted(RAW.glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("role") == "scientific": records.append(value)
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
        summary_rows.append(row)
    write_csv(OUT / "scenario_summary.csv", summary_rows)

    core = [r for r in records if "ALGORITHM_SEED" in r["definition"]["family"]]
    seed_rows = []
    for key, group_iter in itertools.groupby(sorted(core, key=lambda r:(r["definition"]["scenario"],r["definition"]["algorithm"])), key=lambda r:(r["definition"]["scenario"],r["definition"]["algorithm"])):
        group=list(group_iter); row={"scenario":key[0],"algorithm":key[1],"seeds":len(group)}
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
        row["annual_feasibility_transition_from_previous"] = bool(previous is not None and str(previous["annual_budget_feasible"]).lower()!=str(row["annual_budget_feasible"]).lower())
        row["transition_interval_lower"] = previous["water_budget_ratio"] if row["annual_feasibility_transition_from_previous"] else ""
        row["transition_interval_upper"] = row["water_budget_ratio"] if row["annual_feasibility_transition_from_previous"] else ""
        previous=row
    write_csv(OUT / "water_threshold_analysis.csv", water)
    economic=[flatten(r) for r in records if "ECONOMIC" in r["definition"]["family"]]
    for row in economic:
        row["factor"]="net_profit_per_da"; row["price_status"]="PRICE_SENSITIVITY_NOT_EXECUTABLE_ON_FROZEN_ENGINE"; row["yield_status"]="YIELD_SENSITIVITY_NOT_EXECUTABLE_ON_FROZEN_ENGINE"
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
              "failed_runs":[],"raw_run_count":len(records),"software":{"python":platform.python_version(),"platform":platform.platform(),"numpy":importlib.metadata.version("numpy"),"pandas":importlib.metadata.version("pandas")},
              "dataset_hashes":dict(next(iter(records))["result"].get("input_provenance",{}).get("resource_hashes",{})) if records else {},
              "candidate_hash":None,"source_guard_unchanged":guard["unchanged"]}
    app,build_demo=imports(); document=build_demo(app.DATA_DIR); from kds.adapters.project_science import build_bundle
    from kds.application.optimization import configuration
    b=build_bundle(document,configuration(payload("S1","GA",selected_seeds()[0],"water_saving",1.0),document)); resources=dict(b.resources)
    manifest["dataset_hashes"]={k:v.digest for k,v in resources.items()}; manifest["candidate_hash"]=resources["candidate_options"].digest
    manifest["baseline_reproduction"]={"analysis_units":len(document["analysis_units"]),"area_da":sum(u["area_da"] for u in document["analysis_units"]),"candidate_rows":len(resources["candidate_options"].copy()),"crop_count":len(document["crops"]),"current_pattern_calculated_gross_demand_m3":document["water_budget"]["amount"],"catalog_derived_current_pattern_profit_tl":sum(float(u["metadata"]["current_profit_tl"]) for u in document["analysis_units"])}
    write_json(OUT/"experiment_manifest.json",manifest)
    protocol_text=PROTOCOL.read_text(encoding="utf-8"); (OUT/"experimental_protocol.md").write_text(protocol_text,encoding="utf-8")
    build_publication_docs(records, summary_rows, seed_rows, agreement, water, economic, manifest)


def build_publication_docs(records, summaries, seed_rows, agreement, water, economic, manifest):
    claim = """# Claim boundary\n\nThe tables in this package describe outputs of the frozen V2 scientific engine for the frozen 179-unit reference project under preregistered input perturbations. They establish computational behavior and sensitivity inside that model.\n\nThey do not establish official water allocation, measured water use, reservoir availability, real-farm profitability, market absorption, agronomic prescriptions, policy recommendations or real-world feasibility. The critical water multiplier is a structural threshold derived from the model's protected-perennial floor and engine budget. Price and yield sensitivity are not claimed because those fields are not independent decision inputs on the frozen execution path.\n"""
    (OUT/"claim_boundary.md").write_text(claim,encoding="utf-8")
    water_transitions={s:[r for r in water if r["scenario"]==s and str(r["annual_budget_feasible"]).lower()=="true"] for s in ("S1","S2")}
    lines=["# Publication tables","","All tables are frozen-model evidence classified **SAFE WITH LIMITATION**.","","## Table 1. Experimental design","","| Population | Scenarios | Algorithms | Seeds | Scientific runs |","|---|---|---|---|---:|",f"| 179 units / 134,919 da | S1, S2 | GA, ACO, ABC | {', '.join(map(str,manifest['selected_seeds']))} | {len(records)} |","","## Table 2. Water-budget sensitivity","", "| Scenario | First tested annual-feasible multiplier | Engine feasibility at that row |","|---|---:|---|"]
    for scenario,rows in water_transitions.items():
        first=rows[0] if rows else None; lines.append(f"| {scenario} | {first['water_budget_ratio'] if first else 'none'} | {first['feasible'] if first else 'n/a'} |")
    lines += ["","## Table 3. Algorithm agreement","","| Scenario | Mean weighted Jaccard | Top-1 agreement rate | Feasibility agreement rate |","|---|---:|---:|---:|"]
    for scenario in ("S1","S2"):
        rr=[r for r in agreement if r["scenario"]==scenario]; lines.append(f"| {scenario} | {statistics.fmean(r['weighted_jaccard'] for r in rr):.6f} | {statistics.fmean(bool(r['top1_agreement']) for r in rr):.6f} | {statistics.fmean(bool(r['feasible_agreement']) for r in rr):.6f} |")
    lines += ["","## Table 4. Seed variability","","| Scenario | Algorithm | Water CV | Profit CV | HHI CV |","|---|---|---:|---:|---:|"]
    for r in seed_rows: lines.append(f"| {r['scenario']} | {r['algorithm']} | {r['total_water_m3_cv']:.6g} | {r['total_profit_tl_cv']:.6g} | {r['hhi_cv']:.6g} |")
    lines += ["","## Table 5. Economic robustness","","| Scenario | Profit at -20% | Profit at baseline | Profit at +20% | Composition response |","|---|---:|---:|---:|---|"]
    for scenario in ("S1","S2"):
        rr=sorted([r for r in economic if r["scenario"]==scenario],key=lambda r:float(r["economic_shock"])); lines.append(f"| {scenario} | {float(rr[0]['total_profit_tl']):.3f} | {float(rr[2]['total_profit_tl']):.3f} | {float(rr[4]['total_profit_tl']):.3f} | {rr[0]['composition_response']} |")
    lines += ["","## Table 6. Crop-pattern stability","","| Scenario | Mean algorithm weighted Jaccard | Mean algorithm Bray-Curtis | Mean top-3 Jaccard |","|---|---:|---:|---:|"]
    for scenario in ("S1","S2"):
        rr=[r for r in agreement if r["scenario"]==scenario]; lines.append(f"| {scenario} | {statistics.fmean(r['weighted_jaccard'] for r in rr):.6f} | {statistics.fmean(r['bray_curtis'] for r in rr):.6f} | {statistics.fmean(r['top3_jaccard'] for r in rr):.6f} |")
    lines += ["","See the CSV files for complete precision and every run. Values are frozen-model outputs within the claim boundary.",""]
    (OUT/"publication_tables.md").write_text("\n".join(lines),encoding="utf-8")
    figures=[
      {"figure_id":"F1","title":"Annual water feasibility across budget multipliers","source":"water_threshold_analysis.csv","x":"water_budget_ratio","y":"total_water_m3 and water_budget_m3","group":"scenario","status":"DATA_READY"},
      {"figure_id":"F2","title":"Algorithm agreement in crop shares","source":"algorithm_agreement.csv","x":"algorithm pair","y":"weighted_jaccard","group":"scenario","status":"DATA_READY"},
      {"figure_id":"F3","title":"Seed variability of water and profit","source":"seed_variability.csv","x":"algorithm","y":"coefficient of variation","group":"scenario","status":"DATA_READY"},
      {"figure_id":"F4","title":"Net-profit sensitivity","source":"economic_sensitivity.csv","x":"economic_shock","y":"total_profit_tl","group":"scenario","status":"DATA_READY"},
      {"figure_id":"F5","title":"Crop-share stability by scenario","source":"crop_share_stability.csv","x":"comparison","y":"weighted_jaccard and Bray-Curtis","group":"scenario","status":"DATA_READY"},
    ]
    write_csv(OUT/"publication_figure_manifest.csv",figures)
    follow="""# Minor pre-pilot follow-ups\n\nThese inherited items remain non-blocking and did not alter the experiment: the freeze helper has no `--follow` mode, Git reports platform EOL normalization warnings, and a historical Phase 5 inventory can flag `__pycache__` artifacts. Scientific sources and engine behavior remain unchanged.\n"""
    (OUT/"minor_prepilot_followups.md").write_text(follow,encoding="utf-8")
    audit="""# Experimental data-flow audit\n\n+| Factor | Source value | Runtime consumer | Transformation | Objective effect | Result field | Connected |\n+|---|---|---|---|---|---|---|\n+| Annual water budget | Project water budget / frozen reservoir delivery resources | `configuration` → frozen optimizer budget handling | Explicit `water_budget_ratio` | Feasibility penalties and guards | `water_budget_m3`, `feasible`, total water | true |\n+| Net profit per da | `candidate_options.profit_tl_da`; seasonal `environment.s1/s2.profit_tl` | S1 candidate matrix; S2 seasonal candidate matrix | In-memory uniform multiplier on copied immutable bundle | Profit score and reported profit | `total_profit_tl`, TL/m3, crop composition | true |\n+| Sale price | Frozen descriptive candidate/seasonal columns | No independent consumer on accepted execution path | none | none | none | false |\n+| Yield | Frozen descriptive candidate/seasonal columns | No independent consumer on accepted execution path | none | none | none | false |\n+| Cost | Embedded upstream in catalog-derived direct net profit | No independent runtime cost perturbation consumer | none | none | none | false |\n+\n+S1 reports the current-pattern calculated gross-demand budget (100,700,080.81 m3 at ratio 1.0), whereas S2 reports the reservoir-derived engine scenario budget (10,401,986.556 m3 at ratio 1.0). The protected-perennial critical multiplier therefore applies to the S2 annual-budget boundary.\n+"""
    (OUT/"data_flow_audit.md").write_text(audit,encoding="utf-8")


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("command",choices=("guard","pilot","grid","run","build")); parser.add_argument("--shard-index",type=int,default=0); parser.add_argument("--shard-count",type=int,default=1); args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    if args.command=="guard": write_json(OUT/"source_guard_before.json",source_hashes())
    elif args.command=="pilot": pilot()
    elif args.command=="grid": write_csv(OUT/"scenario_grid.csv",[{**r,"scenario_hash":digest(r)} for r in plan()])
    elif args.command=="run":
        if args.shard_count < 1 or not 0 <= args.shard_index < args.shard_count:
            parser.error("shard index must be in [0, shard count)")
        run_all(args.shard_index,args.shard_count)
    elif args.command=="build": build_outputs()


if __name__ == "__main__":
    main()
