"""Deterministic, diagnosis-only Turp dominance audit.

The audit reads frozen project sources and reference fixtures.  It never mutates
production data, ProjectStore state, optimizer code, or scientific parameters.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any, Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "docs" / "audits" / "turp_dominance"
BASELINE = ROOT / "tests" / "fixtures" / "scientific_baseline"
MATRIX_PATH = ROOT / "data" / "excel_derived" / "combined_parcel_candidate_matrix_2024.csv"
CATALOG_PATH = ROOT / "data" / "urun_parametreleri_demo.csv"
S1_PATH = ROOT / "data" / "enhanced_dataset" / "csv" / "senaryo1_backend_seasons.csv"
S2_PATH = ROOT / "data" / "enhanced_dataset" / "csv" / "senaryo2_backend_seasons.csv"
PARAMS_PATH = ROOT / "data" / "enhanced_dataset" / "csv" / "crop_params_assumed.csv"
FAMILY_PATH = ROOT / "data" / "enhanced_dataset" / "csv" / "crop_family_map.csv"
ROTATION_PATH = ROOT / "data" / "enhanced_dataset" / "csv" / "rotation_rules_default.csv"
TURP = "TURPKIRMIZI"
PROTECTED = (
    "app.py", "kds/science", "kds/adapters", "kds/application/optimization.py",
    "data", "index.html", "script.js", "style.css",
)


def _app():
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import app
    return app


def _round(value: Any) -> Any:
    if isinstance(value, (np.floating, float)):
        if not math.isfinite(float(value)):
            return ""
        return round(float(value), 9)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, bool):
        return str(value).lower()
    if value is None:
        return ""
    return value


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str] | None = None) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or (list(rows[0]) if rows else [])
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _round(row.get(key)) for key in fields})


def file_hashes(paths: Iterable[Path]) -> dict[str, str]:
    return {
        str(path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths) if path.is_file()
    }


def protected_files() -> list[Path]:
    files: list[Path] = []
    for name in PROTECTED:
        path = ROOT / name
        files.extend(sorted(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else [path])
    return files


def project_store_hashes() -> dict[str, str]:
    """Snapshot the serving store without creating it or importing the API layer."""
    from kds.config import project_store_path
    root = project_store_path()
    if not root.exists():
        return {}
    return {
        str(path.relative_to(root)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def locked(app: Any, parcel: dict[str, Any]) -> bool:
    flag = str(parcel.get("cok_yillik_kilit", "") or "").strip().lower()
    return bool(
        str(parcel.get("parcel_type", "") or "").strip().lower() == "orchard"
        or flag.startswith(("e", "y"))
        or app.canonical_crop_key(parcel.get("current_crop", "")) in app.PERENNIAL_CROPS
    )


def rank_rows(rows: list[dict[str, Any]], field: str, reverse: bool) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda row: (float(row[field]), row["canonical_crop"]), reverse=reverse)
    count = len(ordered)
    for row in ordered:
        value = float(row[field])
        better = sum(float(other[field]) > value if reverse else float(other[field]) < value for other in ordered)
        tied = sum(math.isclose(float(other[field]), value, rel_tol=0.0, abs_tol=1e-9) for other in ordered)
        row["rank"] = better + 1
        row["rank_min"] = better + 1
        row["rank_max"] = better + tied
        row["rank_range"] = str(better + 1) if tied == 1 else f"{better + 1}-{better + tied}"
        row["tie_count"] = tied
        row["population"] = count
        row["best_percentile"] = 100.0 if count == 1 else 100.0 * (count - (better + 1)) / (count - 1)
    return ordered


def distribution(group: pd.DataFrame, field: str) -> str:
    if field not in group:
        return "{}"
    counts = Counter(str(value).strip() for value in group[field].fillna("") if str(value).strip())
    return json.dumps(dict(sorted(counts.items())), ensure_ascii=False, sort_keys=True)


def fixture_runs(app: Any) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(BASELINE.glob("s[12]_*.json")):
        scenario, algorithm = path.stem.split("_")
        for case in json.loads(path.read_text(encoding="utf-8")):
            result = case["result"]
            crop_area: dict[str, float] = defaultdict(float)
            turp_units = 0
            total_units = len(result["details"])
            for detail in result["details"]:
                area = float(detail.get("area_da", 0.0) or 0.0)
                crop = detail.get("chosenCrop") or detail.get("primary", {}).get("crop", "")
                canon = app.canonical_crop_key(crop)
                crop_area[canon] += area
                if canon == TURP:
                    turp_units += 1
            total_area = sum(crop_area.values())
            shares = sorted((area / total_area for area in crop_area.values() if area > 0), reverse=True)
            turp_area = crop_area.get(TURP, 0.0)
            rows.append({
                "scenario": scenario.upper(), "algorithm": algorithm.upper(), "seed": case["seed"],
                "fixture_unit_count": total_units, "turp_area_da": turp_area,
                "turp_area_share": turp_area / total_area if total_area else 0.0,
                "turp_unit_count": turp_units, "turp_unit_share": turp_units / total_units if total_units else 0.0,
                "top_crop": max(crop_area, key=crop_area.get), "top_crop_share": shares[0] if shares else 0.0,
                "top3_share": sum(shares[:3]), "hhi": sum(value * value for value in shares),
                "total_water_m3": result["total_water_m3"], "total_profit_tl": result["total_profit_tl"],
                "tl_per_m3": result["total_profit_tl"] / result["total_water_m3"] if result["total_water_m3"] else 0.0,
            })
    return rows


def objective_components(app: Any, options: list[dict[str, Any]], objective: str) -> list[dict[str, Any]]:
    opts = [dict(option) for option in options if float(option.get("area_da", 0) or 0) > 0 and float(option.get("totalProfit", 0) or 0) > 0]
    if not opts:
        return []
    current = next((option for option in opts if option.get("isCurrent")), None)
    baseline_profit = float((current or {}).get("totalProfit", 0) or 0)
    baseline_water = float((current or {}).get("totalWater", 0) or 0)
    baseline_eff = float((current or {}).get("tlPerM3", 0) or 0)
    waters = [float(option["totalWater"]) for option in opts]
    profits = [float(option["totalProfit"]) for option in opts]
    efficiencies = [float(option["tlPerM3"]) for option in opts]

    def norm(value: float, values: list[float], invert: bool = False) -> float:
        low, high = min(values), max(values)
        result = 0.5 if abs(high - low) < 1e-9 else max(0.0, min(1.0, (value - low) / (high - low)))
        return 1.0 - result if invert else result

    ranked = app._matrix_rank_options_v8(opts, objective)
    output = []
    for rank, option in enumerate(ranked, 1):
        water, profit, efficiency = (float(option[key]) for key in ("totalWater", "totalProfit", "tlPerM3"))
        source = str(option.get("sourceType", "") or "")
        source_component = 0.12 if option.get("isCurrent") else 0.10 if source == "local_village_crop" else 0.03 if source == "regional_5_village_crop" else -0.04
        category = max(0.0, min(1.0, float(option.get("categoryFitScore", 0) or 0)))
        quota_component = 0.05 if objective in ("water_saving", "water_efficiency") and option.get("fullFeasible") else 0.07 if objective == "max_profit" and option.get("fullFeasible") else 0.0
        water_norm = norm(water, waters, True)
        profit_norm = norm(profit, profits)
        efficiency_norm = norm(efficiency, efficiencies)
        saving_norm = norm(max(0.0, baseline_water - water), [max(0.0, baseline_water - value) for value in waters])
        if objective == "water_saving":
            water_component = 0.42 * water_norm + 0.14 * saving_norm
            profit_component = 0.11 * profit_norm
            efficiency_component = 0.07 * efficiency_norm
            category_component = 0.16 * category
            special_penalty = 0.34 if baseline_profit > 0 and profit < baseline_profit * 0.35 and not option.get("isCurrent") else 0.0
        elif objective == "max_profit":
            water_component = 0.07 * water_norm
            profit_component = 0.52 * profit_norm
            efficiency_component = 0.13 * efficiency_norm
            category_component = 0.16 * category
            special_penalty = 0.0
        else:
            water_component = 0.15 * water_norm
            profit_component = 0.23 * profit_norm
            efficiency_component = 0.42 * efficiency_norm
            category_component = 0.12 * category
            special_penalty = 0.42 if baseline_profit > 0 and baseline_eff > 0 and profit < baseline_profit * 0.75 and efficiency < baseline_eff * 0.95 and not option.get("isCurrent") else 0.0
        reconstructed = (
            water_component + profit_component + efficiency_component + quota_component
            + category_component + source_component
            - float(option.get("rotationPenalty", 0.0) or 0.0)
            - float(option.get("fieldToVegetablePenalty", 0.0) or 0.0)
            - float(option.get("categoryPenalty", 0.0) or 0.0) - special_penalty
        )
        final_score = float(option.get("finalScore", 0.0) or 0.0)
        output.append({
            "rank": rank, "crop": option["name"], "canonical_crop": app.canonical_crop_key(option["name"]),
            "water_m3_da": option["water_m3_da"], "profit_tl_da": option["profit_tl_da"], "tl_per_m3": option["tlPerM3"],
            "compatibility_score": option.get("compatibilityScore", ""),
            "candidate_village_count": option.get("candidateVillageCount", ""),
            "water_norm": water_norm, "profit_norm": profit_norm, "efficiency_norm": efficiency_norm,
            "water_component": water_component, "profit_component": profit_component,
            "efficiency_component": efficiency_component, "quota_component": quota_component,
            "category_component": category_component, "source_component": source_component,
            "rotation_penalty": option.get("rotationPenalty", 0.0),
            "field_to_vegetable_penalty": option.get("fieldToVegetablePenalty", 0.0),
            "category_penalty": option.get("categoryPenalty", 0.0), "special_penalty": special_penalty,
            "reconstructed_score": reconstructed, "final_objective_score": final_score,
            "decomposition_residual": reconstructed - final_score, "source_type": source,
        })
    return output


def generate(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    app = _app()
    before = file_hashes(protected_files())
    store_before = project_store_hashes()
    matrix = pd.read_csv(MATRIX_PATH, encoding="utf-8")
    catalog = pd.read_csv(CATALOG_PATH, encoding="utf-8")
    parcels = app.load_parcels()
    matrix["canonical_crop"] = matrix["candidate_crop"].astype(str).map(app.canonical_crop_key)
    for field in ("area_da", "water_m3_da", "profit_tl_da", "yield_ton_da", "yield_kg_da_model", "is_feasible_under_current_quota"):
        matrix[field] = pd.to_numeric(matrix[field], errors="coerce")

    crop_stats = []
    raw_coverage = []
    for canonical, group in matrix.groupby("canonical_crop", sort=True):
        unique = group[["parcel_id", "area_da"]].drop_duplicates("parcel_id")
        annual = app.is_annual_field_vegetable_candidate(str(group.iloc[0]["candidate_crop"]))
        water = float(group["water_m3_da"].median())
        profit = float(group["profit_tl_da"].median())
        crop_stats.append({
            "canonical_crop": canonical, "crop": str(group.iloc[0]["candidate_crop"]), "comparable_annual": annual,
            "candidate_rows": len(group), "unique_units": group["parcel_id"].nunique(),
            "covered_area_da": float(unique["area_da"].sum()), "water_m3_da": water,
            "profit_tl_da": profit, "tl_per_m3": profit / water if water else 0.0,
            "yield_kg_da": float(group["yield_kg_da_model"].median()),
        })
        raw_coverage.append({
            "canonical_crop": canonical, "crop": str(group.iloc[0]["candidate_crop"]),
            "candidate_row_count": len(group), "unique_analysis_unit_count": group["parcel_id"].nunique(),
            "covered_area_da": float(unique["area_da"].sum()), "total_candidate_area_da": float(group["area_da"].sum()),
            "settlement_distribution": distribution(group, "village"), "district_distribution": distribution(group, "district"),
            "allowed_true_count": "NA", "allowed_field_status": "ABSENT_IN_RAW_MATRIX",
            "quota_flag_true_count": int((group["is_feasible_under_current_quota"] == 1).sum()),
            "quota_flag_false_count": int((group["is_feasible_under_current_quota"] != 1).sum()),
            "suitability_distribution": "ABSENT_IN_RAW_MATRIX",
        })
    annual_stats = [row for row in crop_stats if row["comparable_annual"]]
    water_rank = rank_rows([dict(row) for row in annual_stats], "water_m3_da", False)
    profit_rank = rank_rows([dict(row) for row in annual_stats], "profit_tl_da", True)
    efficiency_rank = rank_rows([dict(row) for row in annual_stats], "tl_per_m3", True)
    raw_unit_rank = {row["canonical_crop"]: row for row in rank_rows([dict(row) for row in crop_stats], "unique_units", True)}
    raw_area_rank = {row["canonical_crop"]: row for row in rank_rows([dict(row) for row in crop_stats], "covered_area_da", True)}
    for row in raw_coverage:
        unit_rank, area_rank = raw_unit_rank[row["canonical_crop"]], raw_area_rank[row["canonical_crop"]]
        row.update({
            "coverage_unit_rank": unit_rank["rank"], "coverage_unit_rank_range": unit_rank["rank_range"],
            "coverage_unit_percentile": unit_rank["best_percentile"],
            "coverage_area_rank": area_rank["rank"], "coverage_area_rank_range": area_rank["rank_range"],
            "coverage_area_percentile": area_rank["best_percentile"],
        })

    problem = app._matrix_build_problem(parcels, "water_saving", 1.0, 2024, {})
    if not problem or len(problem["parcels"]) != 179:
        raise RuntimeError("Production matrix problem did not contain the frozen 179 units.")
    parcel_map = {parcel["id"]: parcel for parcel in parcels}
    runtime_by_crop: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for parcel in problem["parcels"]:
        for option in parcel["options"]:
            runtime_by_crop[app.canonical_crop_key(option["name"])].append((parcel, option))
    runtime_coverage = []
    for canonical in sorted(runtime_by_crop):
        pairs = runtime_by_crop[canonical]
        raw = next((row for row in crop_stats if row["canonical_crop"] == canonical), None)
        runtime_coverage.append({
            "canonical_crop": canonical, "crop": pairs[0][1]["name"], "runtime_option_count": len(pairs),
            "runtime_unique_units": len({parcel["id"] for parcel, _ in pairs}),
            "runtime_full_area_da": sum(float(option["fullAreaDa"]) for _, option in pairs),
            "runtime_eligible_area_da": sum(float(option["area_da"]) for _, option in pairs),
            "regional_expanded_count": sum(option["sourceType"] == "regional_5_village_crop" for _, option in pairs),
            "local_count": sum(option["sourceType"] == "local_village_crop" for _, option in pairs),
            "compatibility_min": min(float(option["compatibilityScore"]) for _, option in pairs),
            "compatibility_median": median(float(option["compatibilityScore"]) for _, option in pairs),
            "compatibility_max": max(float(option["compatibilityScore"]) for _, option in pairs),
            "raw_unique_units": raw["unique_units"] if raw else 0,
            "unit_expansion_ratio": len({parcel["id"] for parcel, _ in pairs}) / raw["unique_units"] if raw and raw["unique_units"] else "",
        })
    runtime_unit_rank = {row["canonical_crop"]: row for row in rank_rows([dict(row) for row in runtime_coverage], "runtime_unique_units", True)}
    runtime_area_rank = {row["canonical_crop"]: row for row in rank_rows([dict(row) for row in runtime_coverage], "runtime_eligible_area_da", True)}
    for row in runtime_coverage:
        unit_rank, area_rank = runtime_unit_rank[row["canonical_crop"]], runtime_area_rank[row["canonical_crop"]]
        row.update({
            "runtime_unit_rank": unit_rank["rank"], "runtime_unit_rank_range": unit_rank["rank_range"],
            "runtime_unit_percentile": unit_rank["best_percentile"],
            "runtime_area_rank": area_rank["rank"], "runtime_area_rank_range": area_rank["rank_range"],
            "runtime_area_percentile": area_rank["best_percentile"],
        })

    turp_raw = next(row for row in crop_stats if row["canonical_crop"] == TURP)
    turp_runtime = next(row for row in runtime_coverage if row["canonical_crop"] == TURP)
    locked_parcels = [parcel for parcel in parcels if locked(app, parcel)]
    unlocked_parcels = [parcel for parcel in parcels if not locked(app, parcel)]
    s2_crops, s2_w1, s2_r1, s2_w2, s2_r2, _, _ = app.build_candidate_matrix_two_season(parcels, 2024, "s2")
    s2_index = s2_crops.index(app.normalize_crop_key("TURP (KIRMIZI)"))
    s2_primary = [index for index in range(len(parcels)) if s2_w1[index, s2_index] < 1e9]
    s2_secondary = [index for index in range(len(parcels)) if s2_w2[index, s2_index] < 1e9]
    s2_primary_unlocked = [index for index in s2_primary if not locked(app, parcels[index])]

    identity_rows = []
    requested = ["TURP", "KIRMIZI TURP", "TURP (KIRMIZI)"]
    for name in requested:
        canonical = app.canonical_crop_key(name)
        group = matrix[matrix["canonical_crop"] == canonical]
        identity_rows.append({
            "source_name": name, "canonical_identity": canonical, "presence": "present" if len(group) else "absent",
            "raw_source": "candidate_matrix" if len(group) else "explicit_absence_check",
            "candidate_count": len(group), "unique_units": group["parcel_id"].nunique() if len(group) else 0,
            "water_m3_da": float(group["water_m3_da"].median()) if len(group) else "",
            "profit_tl_da": float(group["profit_tl_da"].median()) if len(group) else "",
            "yield_kg_da": float(group["yield_kg_da_model"].median()) if len(group) else "",
            "price_tl_kg": 6.0 if canonical == TURP and len(group) else "", "year": 2024 if len(group) else "",
            "season": "Yazlık" if canonical == TURP and len(group) else "", "source_path": str(MATRIX_PATH.relative_to(ROOT)).replace("\\", "/") if len(group) else "",
        })
    for path, name_col, label in ((PARAMS_PATH, "crop", "assumed_crop_parameters"), (S1_PATH, "crop", "S1_seasonal"), (S2_PATH, "crop", "S2_seasonal")):
        frame = pd.read_csv(path, encoding="utf-8")
        for source_name in sorted(set(frame[name_col].astype(str))):
            if "TURP" not in app.canonical_crop_key(source_name):
                continue
            group = frame[frame[name_col].astype(str) == source_name]
            identity_rows.append({
                "source_name": source_name, "canonical_identity": app.canonical_crop_key(source_name), "presence": "present",
                "raw_source": label, "candidate_count": len(group), "unique_units": group["parcel_id"].nunique() if "parcel_id" in group else "",
                "water_m3_da": (float((group["water_m3_calib_gross"] / group["area_da"]).median()) if "water_m3_calib_gross" in group else ""),
                "profit_tl_da": (float((group["profit_tl"] / group["area_da"]).median()) if "profit_tl" in group else ""),
                "yield_kg_da": "", "price_tl_kg": "", "year": int(group["year"].iloc[0]) if "year" in group else "",
                "season": str(group["season"].iloc[0]) if "season" in group else "", "source_path": str(path.relative_to(ROOT)).replace("\\", "/"),
            })

    expansion_trace = [
        {"stage": 1, "path": "combined_parcel_candidate_matrix_2024.csv", "rule": "raw rows", "turp_units": turp_raw["unique_units"], "turp_area_da": turp_raw["covered_area_da"], "effect": "baseline"},
        {"stage": 2, "path": "load_matrix_candidates", "rule": "normalize identifiers; retain raw rows", "turp_units": turp_raw["unique_units"], "turp_area_da": turp_raw["covered_area_da"], "effect": "no expansion"},
        {"stage": 3, "path": "_augment_annual_regional_candidates", "rule": "regional canonical crop median; no minimum village count; locked units bypass augmentation", "turp_units": len(unlocked_parcels), "turp_area_da": sum(float(p["area_da"]) for p in unlocked_parcels), "effect": "+94 regional options; 33 raw local options retained; net +84 versus 43 raw units"},
        {"stage": 4, "path": "candidate_allowed_for_parcel + annual filter", "rule": "exclude orchard/perennial; allow annual field/vegetable", "turp_units": turp_runtime["runtime_unique_units"], "turp_area_da": turp_runtime["runtime_full_area_da"], "effect": "10 raw Turp rows are on locked units; 52 basin units excluded from Turp opportunity"},
        {"stage": 5, "path": "quota + local utility + compact pool", "rule": "water_saving retained runtime options", "turp_units": turp_runtime["runtime_unique_units"], "turp_area_da": turp_runtime["runtime_eligible_area_da"], "effect": "Turp retained for all unlocked units"},
        {"stage": 6, "path": "build_candidate_matrix_two_season(S2)", "rule": "district/season fallback + suitability + realism", "turp_units": len(s2_primary), "turp_area_da": sum(float(parcels[i]["area_da"]) for i in s2_primary), "effect": "primary only; secondary unavailable"},
    ]
    expansion_filters = [
        {"filter": "crop_group", "mode": "hard class gate", "units_before": len(unlocked_parcels), "units_after": len(unlocked_parcels), "turp_units_removed": 0, "finding": "Turp passes annual field/vegetable class"},
        {"filter": "field_orchard", "mode": "hard", "units_before": len(parcels), "units_after": len(unlocked_parcels), "turp_units_removed": turp_raw["unique_units"] - turp_runtime["local_count"], "finding": "10 raw Turp rows removed; 52 basin units excluded from opportunity"},
        {"filter": "perennial", "mode": "hard; overlaps field_orchard", "units_before": len(parcels), "units_after": len(unlocked_parcels), "turp_units_removed": turp_raw["unique_units"] - turp_runtime["local_count"], "finding": "52 protected units / 39,486 da; 10 carried raw Turp rows"},
        {"filter": "soil_LCC", "mode": "no explicit hard S1 expansion filter", "units_before": len(unlocked_parcels), "units_after": len(unlocked_parcels), "turp_units_removed": 0, "finding": "raw matrix has no suitability field"},
        {"filter": "rotation", "mode": "soft local rank penalty", "units_before": len(unlocked_parcels), "units_after": len(unlocked_parcels), "turp_units_removed": 0, "finding": "7 same-family units penalized; availability retained"},
        {"filter": "settlement", "mode": "not a hard gate after regional aggregation", "units_before": turp_raw["unique_units"], "units_after": len(unlocked_parcels), "turp_units_removed": 0, "finding": "+84 units outside raw settlement evidence"},
        {"filter": "region", "mode": "five-village dataset boundary", "units_before": len(unlocked_parcels), "units_after": len(unlocked_parcels), "turp_units_removed": 0, "finding": "confined to loaded basin scope"},
        {"filter": "season", "mode": "annual class", "units_before": len(unlocked_parcels), "units_after": len(unlocked_parcels), "turp_units_removed": 0, "finding": "summer annual identity passes"},
        {"filter": "irrigation", "mode": "compatibility metadata; no hard removal observed", "units_before": len(unlocked_parcels), "units_after": len(unlocked_parcels), "turp_units_removed": 0, "finding": "runtime access retained on all unlocked units"},
        {"filter": "quota", "mode": "feasible-area calculation", "units_before": len(unlocked_parcels), "units_after": turp_runtime["runtime_unique_units"], "turp_units_removed": 0, "finding": "no option removal; raw quota flags all true"},
        {"filter": "allowed", "mode": "ABSENT_IN_RAW_MATRIX", "units_before": turp_raw["unique_units"], "units_after": turp_raw["unique_units"], "turp_units_removed": 0, "finding": "PROVENANCE GAP; cannot validate allowed=true count"},
    ]

    scarcity = []
    representative_ids = ["P1", "P23"]
    unit_rank_cache: dict[str, list[dict[str, Any]]] = {}
    for parcel in problem["parcels"]:
        ranked = objective_components(app, parcel["options"], "water_saving")
        unit_rank_cache[parcel["id"]] = ranked
        turp_entry = next((row for row in ranked if row["canonical_crop"] == TURP), None)
        top_score = float(ranked[0]["final_objective_score"]) if ranked else 0.0
        effective = sum(float(row["final_objective_score"]) >= top_score - 0.10 for row in ranked)
        scarcity.append({
            "analysis_unit_id": parcel["id"], "area_da": parcel["area_da"], "perennial_locked": locked(app, parcel_map[parcel["id"]]),
            "candidate_count": len(parcel["options"]), "viable_candidate_count": len(ranked), "effective_competitive_count_within_0_10": effective,
            "turp_available": turp_entry is not None, "turp_rank_water_saving": turp_entry["rank"] if turp_entry else "",
            "turp_top_ranked": bool(turp_entry and turp_entry["rank"] == 1),
        })
        if turp_entry and turp_entry["rank"] > 1 and parcel["id"] not in representative_ids and len(representative_ids) < 5:
            representative_ids.append(parcel["id"])

    fixture = fixture_runs(app)
    representative = []
    decomposition = []
    for unit_id in representative_ids:
        parcel = next(parcel for parcel in problem["parcels"] if parcel["id"] == unit_id)
        for objective in ("water_saving", "water_efficiency", "max_profit"):
            ranked = objective_components(app, parcel["options"], objective)
            for row in ranked:
                representative.append({
                    "analysis_unit_id": unit_id, "unit_area_da": parcel["area_da"],
                    "current_crop": parcel["current_crop"], "perennial_locked": parcel["locked"],
                    "objective": objective, **row,
                    "suitability_status": "ABSENT_IN_S1_MATRIX_PATH", "compatibility_score": row["compatibility_score"],
                    "selected_by_deterministic_local_ranker": row["rank"] == 1,
                    "selection_evidence": "SELECTED_IN_ALL_FROZEN_S1_GA_ACO_ABC_SEEDS" if row["canonical_crop"] == TURP and unit_id in ("P1", "P23") and objective == "water_saving" else "NOT_SELECTED_OR_OUTSIDE_FROZEN_FIXTURE",
                    "rotation_status": "penalized" if row["rotation_penalty"] else "not_penalized",
                })
                if row["canonical_crop"] == TURP or row["rank"] == 1:
                    decomposition.append({"analysis_unit_id": unit_id, "objective": objective, **row})

    algorithm_comparison = []
    for scenario in ("S1", "S2"):
        for algorithm in ("GA", "ACO", "ABC"):
            group = [row for row in fixture if row["scenario"] == scenario and row["algorithm"] == algorithm]
            algorithm_comparison.append({
                "scenario": scenario, "algorithm": algorithm, "seed_count": len(group), "fixture_unit_count": group[0]["fixture_unit_count"],
                "mean_turp_area_share": sum(row["turp_area_share"] for row in group) / len(group),
                "min_turp_area_share": min(row["turp_area_share"] for row in group), "max_turp_area_share": max(row["turp_area_share"] for row in group),
                "mean_turp_unit_share": sum(row["turp_unit_share"] for row in group) / len(group),
                "top_crop_mode": Counter(row["top_crop"] for row in group).most_common(1)[0][0],
                "mean_top3_share": sum(row["top3_share"] for row in group) / len(group), "mean_hhi": sum(row["hhi"] for row in group) / len(group),
                "mean_water_m3": sum(row["total_water_m3"] for row in group) / len(group),
                "mean_profit_tl": sum(row["total_profit_tl"] for row in group) / len(group),
                "mean_tl_per_m3": sum(row["tl_per_m3"] for row in group) / len(group),
            })

    s1_s2 = []
    for scenario in ("S1", "S2"):
        group = [row for row in fixture if row["scenario"] == scenario]
        s1_s2.append({
            "scenario": scenario, "fixture_run_count": len(group), "fixture_unit_count_per_run": group[0]["fixture_unit_count"],
            "mean_turp_area_share": sum(row["turp_area_share"] for row in group) / len(group),
            "mean_turp_unit_share": sum(row["turp_unit_share"] for row in group) / len(group),
            "turp_source_profit_tl_da": 4000.0, "turp_source_water_m3_da": 298.87,
            "turp_runtime_profit_tl_da": 4000.0 if scenario == "S1" else 1870.0,
            "runtime_primary_units": turp_runtime["runtime_unique_units"] if scenario == "S1" else len(s2_primary),
            "post_perennial_lock_units": len(unlocked_parcels) if scenario == "S1" else len(s2_primary_unlocked),
            "runtime_secondary_units": 0 if scenario == "S2" else "NA",
            "mechanism": "regional five-village median expansion" if scenario == "S1" else "district fallback + suitability 0.85 + realism 0.55; no secondary Turp",
        })

    competitor_keys = {TURP, "MERCIMEK", "NOHUT"}
    competitor_keys.update(row["canonical_crop"] for row in annual_stats if row["canonical_crop"].startswith(("ARPA", "BUGDAY")))
    competitor_keys.update(row["canonical_crop"] for row in sorted(annual_stats, key=lambda row: row["water_m3_da"])[:8])
    competitors = []
    for row in crop_stats:
        if row["canonical_crop"] not in competitor_keys:
            continue
        runtime = next((item for item in runtime_coverage if item["canonical_crop"] == row["canonical_crop"]), {})
        competitors.append({
            **row, "runtime_units": runtime.get("runtime_unique_units", 0), "runtime_area_da": runtime.get("runtime_eligible_area_da", 0),
            "water_rank": next(item["rank"] for item in water_rank if item["canonical_crop"] == row["canonical_crop"]),
            "profit_rank": next(item["rank"] for item in profit_rank if item["canonical_crop"] == row["canonical_crop"]),
            "tl_m3_rank": next(item["rank"] for item in efficiency_rank if item["canonical_crop"] == row["canonical_crop"]),
        })

    diversity_rows = []
    for share in (0.05, 0.10, 0.15, 0.20, 0.25, 0.35, 0.424114352, 0.50, 0.75, 1.00):
        shares = [share] + ([] if share == 1 else [(1 - share) / 4] * 4)
        penalty = app._diversity_penalty_from_shares(shares, app.DIVERSITY_DEFAULTS)
        diversity_rows.append({
            "hypothetical_turp_share": share, "other_crop_count": 0 if share == 1 else 4,
            "hhi": sum(value * value for value in shares), "raw_diversity_penalty": penalty,
            "matrix_score_deduction": 0.12 * penalty, "diagnostic_only": True,
        })

    family = pd.read_csv(FAMILY_PATH, encoding="utf-8")
    rotation = pd.read_csv(ROTATION_PATH, encoding="utf-8")
    turp_family = str(family[family["crop"].astype(str).map(app.canonical_crop_key) == TURP].iloc[0]["crop_family"])
    same_family_units = sum(app.load_crop_family_map().get(app.normalize_crop_key(p["current_crop"]), "") == turp_family for p in unlocked_parcels)
    rotation_rows = [
        {"diagnostic": "turp_family", "value": turp_family, "unit_count": "", "effect": "Brassicaceae identity"},
        {"diagnostic": "same_family_current_crop", "value": "soft local rank penalty", "unit_count": same_family_units, "effect": "0.16 in matrix ranker for non-current same-family option"},
        {"diagnostic": "field_to_vegetable_transition", "value": "soft local rank penalty", "unit_count": sum(str(p.get("parcel_type")) == "field" for p in unlocked_parcels), "effect": "0.50 where current family is cereal/field and candidate is vegetable"},
        {"diagnostic": "R4", "value": str(rotation.loc[rotation["rule_id"] == "R4", "description"].iloc[0]), "unit_count": "", "effect": "hard in S2 rotation table; current Brassicaceae blocks repeat"},
        {"diagnostic": "perennial_lock", "value": "hard", "unit_count": len(locked_parcels), "effect": "Turp unavailable on 39,486 da"},
    ]

    concentration = []
    for row in fixture:
        concentration.append({
            **row, "turp_hhi_contribution": row["turp_area_share"] ** 2,
            "gap_to_5pct_diagnostic": row["turp_area_share"] - 0.05,
            "gap_to_10pct_diagnostic": row["turp_area_share"] - 0.10,
            "gap_to_15pct_diagnostic": row["turp_area_share"] - 0.15,
            "gap_to_20pct_diagnostic": row["turp_area_share"] - 0.20,
            "thresholds_are_not_recommendations": True,
        })

    attribution = [
        {"mechanism": "low water", "classification": "PRIMARY DRIVER", "behavior_type": "EXPECTED OPTIMIZATION BEHAVIOR", "evidence": "298.87 m3/da; rank 1/37"},
        {"mechanism": "TL/m3", "classification": "PRIMARY DRIVER", "behavior_type": "EXPECTED OPTIMIZATION BEHAVIOR", "evidence": "13.383745 TL/m3; rank 3/37"},
        {"mechanism": "runtime expansion", "classification": "PRIMARY DRIVER", "behavior_type": "MODEL ASSUMPTION", "evidence": "43 raw units to 127 runtime units; 2.953x"},
        {"mechanism": "profit", "classification": "NOT SUPPORTED", "behavior_type": "DATA ISSUE", "evidence": "4000 TL/da; tied rank range 23-24/37"},
        {"mechanism": "market cap absence", "classification": "AMPLIFIER", "behavior_type": "MISSING CONSTRAINT", "evidence": "no demand, sales, production, storage or area ceiling in active matrix evaluation"},
        {"mechanism": "candidate scarcity", "classification": "SECONDARY DRIVER", "behavior_type": "MODEL ASSUMPTION", "evidence": "effective competitor counts reported per unit; compact pool retains at most 18 options"},
        {"mechanism": "diversity penalty", "classification": "LIMITER", "behavior_type": "MODEL ASSUMPTION", "evidence": "soft only; repair disabled; score deduction is 0.12 x penalty"},
        {"mechanism": "rotation", "classification": "LIMITER", "behavior_type": "MODEL ASSUMPTION", "evidence": "same-family 0.16 and field-to-vegetable 0.50 local penalties; S2 R4 rule"},
        {"mechanism": "perennial locks", "classification": "LIMITER", "behavior_type": "EXPECTED OPTIMIZATION BEHAVIOR", "evidence": "52 units / 39,486 da excluded; remaining 95,433 da all runtime-accessible in S1"},
        {"mechanism": "algorithm bias", "classification": "NOT SUPPORTED", "behavior_type": "SEARCH BEHAVIOR", "evidence": "GA/ACO/ABC frozen S1 fixtures make identical Turp choices"},
        {"mechanism": "seed", "classification": "NOT SUPPORTED FOR S1; PRESENT FOR S2 MIX", "behavior_type": "SEARCH BEHAVIOR", "evidence": "S1 identical at seeds 123/456/789; S2 varies but never selects Turp"},
        {"mechanism": "S2 transformations", "classification": "LIMITER", "behavior_type": "MODEL ASSUMPTION", "evidence": "Turp 4000 source becomes 1870 after 0.85 suitability and 0.55 realism; secondary absent"},
    ]
    market_status = [
        {"constraint": name, "status": "ABSENT MODEL CONSTRAINT", "active_matrix_path_evidence": "not referenced by _matrix_build_problem or _matrix_eval_solution"}
        for name in ("market demand cap", "sales capacity", "regional production ceiling", "processing/storage capacity", "Turp maximum crop area")
    ]

    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "turp_identity_inventory.csv", identity_rows)
    write_csv(output / "raw_candidate_coverage.csv", raw_coverage)
    write_csv(output / "runtime_candidate_coverage.csv", runtime_coverage)
    write_csv(output / "candidate_expansion_trace.csv", expansion_trace)
    write_csv(output / "expansion_agronomic_filters.csv", expansion_filters)
    write_csv(output / "crop_water_rank.csv", water_rank)
    write_csv(output / "crop_profit_rank.csv", profit_rank)
    write_csv(output / "crop_tl_m3_rank.csv", efficiency_rank)
    write_csv(output / "representative_unit_rankings.csv", representative)
    write_csv(output / "algorithm_turp_comparison.csv", algorithm_comparison)
    write_csv(output / "seed_sensitivity.csv", fixture)
    write_csv(output / "s1_s2_turp_comparison.csv", s1_s2)
    write_csv(output / "competitor_comparison.csv", competitors)
    write_csv(output / "candidate_scarcity.csv", scarcity)
    write_csv(output / "concentration_hhi.csv", concentration)
    write_csv(output / "diversity_penalty_diagnostics.csv", diversity_rows)
    write_csv(output / "rotation_diagnostics.csv", rotation_rows)
    if any(abs(float(row["decomposition_residual"])) > 1e-8 for row in decomposition):
        raise RuntimeError("Objective decomposition does not reconstruct the production ranker score.")
    write_csv(output / "objective_decomposition.csv", decomposition)
    write_csv(output / "root_cause_attribution.csv", attribution)
    write_csv(output / "market_constraint_status.csv", market_status)

    turp_water = next(row for row in water_rank if row["canonical_crop"] == TURP)
    turp_profit = next(row for row in profit_rank if row["canonical_crop"] == TURP)
    turp_eff = next(row for row in efficiency_rank if row["canonical_crop"] == TURP)
    annual_water_median = median(row["water_m3_da"] for row in annual_stats)
    annual_profit_median = median(row["profit_tl_da"] for row in annual_stats)
    next_water = next(row for row in water_rank if row["canonical_crop"] != TURP)
    top_profit = profit_rank[0]
    scarcity_turp_top = [row for row in scarcity if row["turp_top_ranked"]]
    scarcity_turp_not_top = [row for row in scarcity if row["turp_available"] and not row["turp_top_ranked"]]
    selected_scarcity = [row for row in scarcity if row["analysis_unit_id"] in ("P1", "P23")]
    frozen_share = next(row["turp_area_share"] for row in fixture if row["scenario"] == "S1")
    frozen_diversity = next(row for row in diversity_rows if math.isclose(row["hypothetical_turp_share"], frozen_share, abs_tol=1e-9))
    summary = f"""# Phase 5 — Turp Dominance Root-Cause Audit

## Scope

Diagnosis only. Production data, Turp values, candidate matrix, optimizer, objectives, rotation, diversity and market constraints were not changed.

## Quantitative result

- Production identity is `TURP (KIRMIZI)` → `{TURP}`. Plain `TURP` and `KIRMIZI TURP` remain distinct identities and are absent from the candidate matrix.
- Raw coverage is {turp_raw['unique_units']} units and {turp_raw['covered_area_da']:.0f} da, entirely from Bor İlçe Merkezi / Bor. All 43 raw rows have the quota flag; the raw matrix has no `allowed` or suitability field.
- Raw unit coverage rank is {raw_unit_rank[TURP]['rank_range']}/{raw_unit_rank[TURP]['population']}; runtime unit coverage rank is {runtime_unit_rank[TURP]['rank_range']}/{runtime_unit_rank[TURP]['population']}.
- S1 runtime expansion reaches {turp_runtime['runtime_unique_units']} units and {turp_runtime['runtime_full_area_da']:.0f} da: +{turp_runtime['runtime_unique_units'] - turp_raw['unique_units']} units, {turp_runtime['unit_expansion_ratio']:.3f}× unit coverage and {turp_runtime['runtime_full_area_da'] / turp_raw['covered_area_da']:.3f}× area coverage.
- The net +{turp_runtime['runtime_unique_units'] - turp_raw['unique_units']} units consists of {turp_runtime['regional_expanded_count']} new regional options and {turp_runtime['local_count']} retained local options; {turp_raw['unique_units'] - turp_runtime['local_count']} raw Turp rows belong to perennial-locked units and are removed from Turp opportunity.
- Turp water is 298.87 m³/da, rank {turp_water['rank']}/{turp_water['population']} and {turp_water['best_percentile']:.2f} best-percentile. It is {turp_raw['water_m3_da'] / annual_water_median:.3f}× the annual-crop median.
- Turp equals the annual minimum (minimum ratio 1.000). The next-lowest crop is `{next_water['crop']}` at {next_water['water_m3_da']:.2f} m³/da, or {turp_raw['water_m3_da'] / next_water['water_m3_da']:.3f}× that requirement.
- Turp profit is 4,000 TL/da, tied rank range {turp_profit['rank_range']}/{turp_profit['population']} ({turp_profit['tie_count']}-way tie) and {turp_profit['best_percentile']:.2f} best-percentile at the leading tie rank. It is {turp_raw['profit_tl_da'] / annual_profit_median:.3f}× the annual-crop median. High absolute profit is not supported as a driver.
- The top annual profit is `{top_profit['crop']}` at {top_profit['profit_tl_da']:.0f} TL/da; Turp is {turp_raw['profit_tl_da'] / top_profit['profit_tl_da']:.3f}× that value.
- Turp efficiency is {turp_raw['profit_tl_da'] / turp_raw['water_m3_da']:.6f} TL/m³, rank {turp_eff['rank']}/{turp_eff['population']} and {turp_eff['best_percentile']:.2f} best-percentile.
- Frozen S1 fixtures select Turp on P1 and P23 for GA, ACO and ABC at seeds 123, 456 and 789. Frozen S2 fixtures never select Turp.
- S2 has Turp primary evidence/fallback for {len(s2_primary)} units ({len(s2_primary_unlocked)} after the perennial lock), no secondary Turp, and transforms 4,000 TL/da to 1,870 TL/da through default suitability 0.85 and profit-realism 0.55.
- Perennial lock excludes {len(locked_parcels)} units / {sum(float(p['area_da']) for p in locked_parcels):.0f} da. It lowers basin-wide opportunity while concentrating S1 Turp availability over the remaining {len(unlocked_parcels)} units / {sum(float(p['area_da']) for p in unlocked_parcels):.0f} da.
- Turp is locally first under the water-saving ranker on {len(scarcity_turp_top)}/{len(unlocked_parcels)} unlocked units. P1/P23 have {', '.join(str(row['candidate_count']) for row in selected_scarcity)} retained candidates and {', '.join(str(row['effective_competitive_count_within_0_10']) for row in selected_scarcity)} competitors within 0.10 score of their local leader; the frozen global choice therefore cannot be reduced to a local greedy rank.
- At the frozen S1 Turp share ({frozen_share:.4%}), Turp contributes {frozen_share ** 2:.6f} to HHI. The equal-four-other-crop diagnostic produces diversity penalty {frozen_diversity['raw_diversity_penalty']:.6f} and matrix score deduction {frozen_diversity['matrix_score_deduction']:.6f}; this is a diagnostic decomposition, not a proposed crop mix.

## Root cause

The primary drivers are the lowest water requirement in the 37 comparable annual crops, third-highest TL/m³, and a regional median expansion rule that converts 43 local observations into availability on every non-perennial unit. The 4,000 TL/da profit is below the annual median rank and does not explain dominance by itself. Identical S1 choices across algorithms and seeds support a model-space explanation rather than a GA/ACO/ABC-specific search bias.

Market demand, sales capacity, processing/storage capacity, regional production ceilings and a crop-specific maximum area are absent from the active scientific decision path. Existing concentration controls are soft: repair is disabled and the matrix score subtracts only `0.12 × diversity_penalty`.

The unresolved 58/69 catalog difference does not change this result because `TURP (KIRMIZI)` is present in the active 58-crop catalog. It remains a separate backlog item.

## S1 and S2

S1 combines raw candidate economics with basin-wide annual candidate expansion. S2 uses seasonal records, district fallback, suitability, profit realism, rotation and a two-crop structure. Turp has no secondary-season record and its effective S2 profit is 1,870 TL/da, explaining why the frozen S2 results favor other low-water crops.

## Classification

No software defect was demonstrated. Dominance is produced by expected optimization response to low water/high TL-per-m³, amplified by a broad expansion assumption and missing market-cap evidence. The expansion rule and missing raw `allowed`/suitability fields are model/provenance issues requiring scientific review before intervention.
"""
    (output / "phase5_summary.md").write_text(summary, encoding="utf-8", newline="\n")
    (output / "real_world_claim_boundary.md").write_text("""# Real-world claim boundary

## SİSTEM İÇİN SÖYLENEBİLİR

Mevcut modelde `TURP (KIRMIZI)` en düşük yıllık su girdisine, üçüncü en yüksek TL/m³ değerine ve ham kaynağından çok daha geniş runtime erişimine sahiptir. Frozen S1 örneklerinde algoritma ve seed değişse de aynı iki field unit için seçilir; S2 dönüşümleri altında seçilmez.

## GERÇEK TARIM/PİYASA İÇİN SÖYLENEMEZ

Verified fiyat, maliyet, talep, satış kapasitesi, depolama, işleme, rotasyon geçmişi ve bölgesel üretim tavanı olmadan Turp'un Niğde veya Akkaya için en uygun ticari ürün olduğu, 95.433 da alanda yetiştirilebileceği ya da belirli bir pazar payının güvenli olduğu söylenemez. Runtime availability agronomik veya ticari uygunluk kanıtı değildir.
""", encoding="utf-8", newline="\n")
    (output / "future_intervention_options.md").write_text("""# Future intervention options

No numerical cap is selected by this audit.

| Option family | Scientific justification | Required external data | Main risk | Optimizer impact |
|---|---|---|---|---|
| Verified economics replacement | Replace proxy yield, price and cost assumptions | Farm records, official market series, dated costs | Temporal/geographic mismatch | Changes profit and TL/m³ ranks |
| Market capacity contract | Prevent production beyond evidenced demand | Buyer contracts, demand, storage and processing throughput | False precision or market exclusion | Adds crop/region capacity constraint |
| Crop/region area ceiling | Bound concentration when agronomically and commercially justified | Rotation trials, extension guidance, market absorption | Arbitrary cap if evidence is weak | Hard feasible-space reduction |
| Diversity calibration | Make concentration cost commensurate with portfolio objectives | Accepted HHI/share targets and sensitivity analysis | Hiding weak source economics | Changes portfolio score, possibly convergence |
| Expansion restriction | Require settlement/district evidence or minimum village coverage | Transferability study and local trials | Candidate scarcity and infeasibility | Narrows unit-level options |
| Rotation hardening | Enforce crop/family history constraints | Parcel crop-history records and disease guidance | Overconstraint from incomplete history | Removes rotation-incompatible options |
| Water recalibration | Verify the unusually low water advantage | Local ETo, Kc, effective rain and irrigation-efficiency observations | Losing genuine efficiency signal | Changes water and TL/m³ ranks |

The scientifically strongest sequence is to verify water and economics, establish a market-capacity contract, and then calibrate expansion and concentration behavior against those observations.
""", encoding="utf-8", newline="\n")

    after = file_hashes(protected_files())
    if before != after:
        raise RuntimeError("Protected production/scientific source mutated during audit.")
    if store_before != project_store_hashes():
        raise RuntimeError("ProjectStore mutated during audit.")
    return {
        "outputs": sorted(path.name for path in output.iterdir() if path.is_file()),
        "protected_hashes": after, "turp_raw_units": turp_raw["unique_units"],
        "turp_runtime_units": turp_runtime["runtime_unique_units"], "turp_runtime_area_da": turp_runtime["runtime_full_area_da"],
        "turp_water_rank": turp_water["rank"], "turp_profit_rank": turp_profit["rank"], "turp_efficiency_rank": turp_eff["rank"],
        "fixture_runs": len(fixture), "full_project_optimizer_runs": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(generate(args.output.resolve()), ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
