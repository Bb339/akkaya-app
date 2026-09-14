"""Deterministic Phase 3 water reconciliation; never runs or mutates the optimizer."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "audits" / "water_supply_phase3"
YEAR = 2024
ENV_FLOW_RATIO = 0.10
WATER_SAVING_PERENNIAL_MULTIPLIER = 0.72
FULL_S2_GA_SEED123_M3 = 23_933_291.2028


def read_csv(relative: str) -> list[dict[str, str]]:
    with (ROOT / relative).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def crop_key(value: str) -> str:
    text = str(value or "").upper().replace("İ", "I").replace("İ", "I")
    text = unicodedata.normalize("NFKD", text)
    return re.sub(r"[^A-Z0-9]", "", "".join(c for c in text if not unicodedata.combining(c)))


def write_csv(name: str, rows: list[dict], fields: list[str] | None = None) -> None:
    path = OUT / name
    fields = fields or list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(name: str, value: dict) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def concept(name, field, source, column, unit, period, meaning, calculation,
            authority, confidence, s1, s2, notes):
    return dict(canonical_name=name, code_field=field, source_file=source,
                source_column=column, unit=unit, period=period,
                physical_meaning=meaning, calculation=calculation,
                authority=authority, confidence=confidence,
                used_by_S1=s1, used_by_S2=s2, notes=notes)


def build(output_dir: Path | None = None) -> dict:
    global OUT
    if output_dir is not None:
        OUT = Path(output_dir)
    OUT.mkdir(parents=True, exist_ok=True)

    unit_path = ROOT / "data/parsel_su_kar_ozet.csv"
    context_path = ROOT / "data/water_context.csv"
    annual_balance_path = ROOT / "data/akkaya_baraj_su_bilanco_2000_2025.csv"
    reservoir_path = ROOT / "data/enhanced_dataset/csv/akkaya_reservoir_monthly_backend.csv"
    delivery_path = ROOT / "data/enhanced_dataset/csv/delivery_capacity_monthly_assumed.csv"
    season_path = ROOT / "data/enhanced_dataset/csv/senaryo2_backend_seasons.csv"
    candidate_path = ROOT / "data/excel_derived/combined_parcel_candidate_matrix_2024.csv"
    lock_path = ROOT / "tests/fixtures/scientific_fix_phase1/akkaya_locks.json"

    tracked_inputs = [unit_path, context_path, annual_balance_path, reservoir_path, delivery_path,
                      season_path, candidate_path, lock_path]
    source_hashes_before = {str(p.relative_to(ROOT)).replace("\\", "/"): sha256(p) for p in tracked_inputs}

    units = read_csv("data/parsel_su_kar_ozet.csv")
    water_context = read_csv("data/water_context.csv")
    annual_balance = read_csv("data/akkaya_baraj_su_bilanco_2000_2025.csv")
    reservoir = [r for r in read_csv("data/enhanced_dataset/csv/akkaya_reservoir_monthly_backend.csv")
                 if str(r["month"]).startswith(f"{YEAR}-")]
    delivery = [r for r in read_csv("data/enhanced_dataset/csv/delivery_capacity_monthly_assumed.csv")
                if str(r["month"]).startswith(f"{YEAR}-")]
    seasons = [r for r in read_csv("data/enhanced_dataset/csv/senaryo2_backend_seasons.csv")
               if int(r["year"]) == YEAR]
    candidates = read_csv("data/excel_derived/combined_parcel_candidate_matrix_2024.csv")
    expected_locks = json.loads(lock_path.read_text(encoding="utf-8"))["unit_ids"]

    assert len(units) == 179
    assert len(reservoir) == len(delivery) == 12
    unit_by_id = {r["parsel_id"]: r for r in units}
    assert set(expected_locks) <= set(unit_by_id)
    protected = [unit_by_id[pid] for pid in expected_locks]
    flagged = {r["parsel_id"] for r in units if r.get("cok_yillik_kilit") == "Evet"}
    assert flagged == set(expected_locks)

    current_total = math.fsum(float(r["mevcut_su_m3"]) for r in units)
    context_reference = next(float(r["available_water_m3"]) for r in water_context
                             if r["projection_mode"] == "planning_reference_current_crop_pattern")
    assert math.isclose(current_total, context_reference, abs_tol=1e-6)

    reservoir_total = math.fsum(float(r["irrigation_m3_baseline"]) for r in reservoir)
    annual_balance_2024 = next(r for r in annual_balance if int(r["yil"]) == YEAR)
    annual_withdrawal_field = float(annual_balance_2024["cekis_su_hacmi_hm3"])
    assert math.isclose(reservoir_total, annual_withdrawal_field, abs_tol=1e-3)
    engine_budget = reservoir_total * (1.0 - ENV_FLOW_RATIO)
    raw_delivery = math.fsum(float(r["max_delivery_m3_assumed"]) for r in delivery)
    effective_delivery = raw_delivery * (1.0 - ENV_FLOW_RATIO)

    delivery_by_month = {r["month"][:7]: r for r in delivery}
    reservoir_by_month = {r["month"][:7]: r for r in reservoir}
    ratios = []
    for month in sorted(delivery_by_month):
        d = delivery_by_month[month]
        ratios.append(float(d["max_delivery_m3_assumed"]) / float(d["irrigation_m3_baseline"]))
    assert all(math.isclose(ratio, 1.15, rel_tol=0, abs_tol=2e-6) for ratio in ratios)

    primary = {}
    for row in seasons:
        if row["season"] == "primary":
            primary[(row["parcel_id"], crop_key(row["crop"]))] = row
    candidate_by_unit: dict[str, set[str]] = {}
    for row in candidates:
        candidate_by_unit.setdefault(row["parcel_id"], set()).add(crop_key(row["candidate_crop"]))

    protected_rows = []
    for unit in protected:
        pid = unit["parsel_id"]
        row = primary[(pid, crop_key(unit["crop"]))]
        source_area = float(row["area_da"])
        area = float(unit["alan_da"])
        calibrated_intensity = float(row["water_m3_calib_gross"]) / source_area
        engine_locked_water = calibrated_intensity * area * WATER_SAVING_PERENNIAL_MULTIPLIER
        current_crop_key = crop_key(unit["crop"])
        available = current_crop_key in candidate_by_unit.get(pid, set())
        protected_rows.append(dict(
            analysis_unit_id=pid,
            settlement=unit["koy"],
            area_da=area,
            current_crop=unit["crop"],
            perennial_status_source="Phase 1 observed-current lock contract; current_crop plus frozen 52-unit fixture",
            current_water_m3=float(unit["mevcut_su_m3"]),
            current_profit_tl=float(unit["mevcut_kar_tl"]),
            model_water_floor_m3=engine_locked_water,
            floor_method="primary calibrated gross m3/da × full unit area_da × water_saving multiplier 0.72",
            floor_source="senaryo2_backend_seasons.csv primary current-crop row; app.py:_apply_s2_irrigation_adjustments",
            monthly_floor_if_available="",
            candidate_availability="current crop present" if available else "locked current crop absent from raw candidate matrix",
            candidate_row_count=len(candidate_by_unit.get(pid, set())),
            notes="Objective-dependent current-model demand; not orchard survival water and not official demand.",
        ))

    protected_area = math.fsum(float(r["area_da"]) for r in protected_rows)
    protected_current = math.fsum(float(r["current_water_m3"]) for r in protected_rows)
    protected_profit = math.fsum(float(r["current_profit_tl"]) for r in protected_rows)
    protected_floor = math.fsum(float(r["model_water_floor_m3"]) for r in protected_rows)
    assert math.isclose(protected_floor, protected_current * 0.72, abs_tol=1e-6)
    settlement_summary = []
    for settlement in sorted({r["settlement"] for r in protected_rows}):
        group = [r for r in protected_rows if r["settlement"] == settlement]
        settlement_summary.append(dict(
            settlement=settlement,
            protected_units=len(group),
            protected_area_da=math.fsum(r["area_da"] for r in group),
            current_reference_demand_m3=math.fsum(r["current_water_m3"] for r in group),
            model_floor_m3=math.fsum(r["model_water_floor_m3"] for r in group),
        ))
    crop_counts = {
        crop: sum(r["current_crop"] == crop for r in protected_rows)
        for crop in sorted({r["current_crop"] for r in protected_rows}, key=crop_key)
    }

    monthly = []
    for month in sorted(reservoir_by_month):
        r = reservoir_by_month[month]
        d = delivery_by_month[month]
        baseline = float(r["irrigation_m3_baseline"])
        raw_cap = float(d["max_delivery_m3_assumed"])
        effective_cap = raw_cap * (1.0 - ENV_FLOW_RATIO)
        full_demand = FULL_S2_GA_SEED123_M3 * baseline / reservoir_total
        monthly.append(dict(
            month=month,
            reservoir_irrigation_baseline_m3=baseline,
            reservoir_storage_m3=float(r["storage_m3"]),
            raw_delivery_capacity_m3=raw_cap,
            delivery_to_baseline_ratio=raw_cap / baseline,
            environmental_flow_ratio=ENV_FLOW_RATIO,
            effective_delivery_capacity_m3=effective_cap,
            full_s2_plan_demand_proportional_m3=full_demand,
            full_s2_difference_m3=effective_cap-full_demand,
            full_s2_coverage_ratio=effective_cap/full_demand if full_demand else None,
            protected_perennial_demand_m3="",
            protected_perennial_monthly_status="NOT_EVALUATED: active calibrated source has no crop-specific planting/harvest monthly floor",
        ))

    concepts = [
        concept("current_pattern_calculated_gross_irrigation_demand", "water_budget.amount / water_m3", "data/parsel_su_kar_ozet.csv; data/water_context.csv", "mevcut_su_m3; available_water_m3", "m3", "2024 annual", "Calculated gross demand of the current crop pattern", "sum analysis-unit current reference demand", "CALCULATED_REFERENCE", "high for arithmetic; medium for source authority", "yes", "baseline comparison only", "Not measured use, allocation or available supply."),
        concept("project_annual_water_budget", "document.water_budget", "kds/adapters/akkaya_demo.py", "amount/kind", "m3", "annual", "Project reference amount", "copied from current-pattern reference", "CALCULATED_REFERENCE", "high", "yes", "provenance only; S2 engine substitutes reservoir-derived budget", "Overloaded term; not S2 supply."),
        concept("reservoir_irrigation_baseline", "irrigation_m3_baseline", "data/enhanced_dataset/csv/akkaya_reservoir_monthly_backend.csv; data/akkaya_baraj_su_bilanco_2000_2025.csv", "irrigation_m3_baseline; cekis_su_hacmi_hm3", "m3/month; annual field label says hm3", "calendar month / annual", "Monthly model input named irrigation baseline", "12-month sum matches the 2024 annual withdrawal-named field within 0.001 m3", "UNKNOWN", "low", "no", "yes", "No generator or official citation; annual header says hm3 although magnitude behaves as m3. The match establishes lineage, not measurement authority."),
        concept("reservoir_storage", "storage_m3", "data/enhanced_dataset/csv/akkaya_reservoir_monthly_backend.csv", "storage_m3", "m3", "calendar month", "Series labelled reservoir storage", "upstream observation/generator unavailable", "UNKNOWN", "low", "no", "not used by budget function", "Presence in a CSV does not establish measurement authority."),
        concept("official_allocation", "none", "not supplied", "none", "m3", "annual/monthly", "Official irrigation allocation", "none", "UNKNOWN", "none", "no", "no", "Required for real-world feasibility."),
        concept("raw_delivery_capacity", "max_delivery_m3_assumed", "data/enhanced_dataset/csv/delivery_capacity_monthly_assumed.csv", "max_delivery_m3_assumed", "m3/month", "calendar month", "Assumed delivery ceiling", "rounded irrigation baseline × 1.15", "DERIVED_PROXY", "high for formula; low for real capacity", "no", "yes", "Not canal design, SCADA or DSİ evidence."),
        concept("environmental_flow_ratio", "envFlowRatio", "app.py default/options", "0.10", "dimensionless", "run setting", "Share reserved from model supply", "input × (1-ratio)", "ASSUMED", "high for code; none for local authority", "no", "yes", "No supplied thesis or official ecological-release evidence."),
        concept("environmental_flow_adjusted_delivery", "month_caps", "engine derivation", "derived", "m3/month", "calendar month", "Scenario delivery ceiling after reserve", "raw delivery × 0.90", "SCENARIO", "high for arithmetic; low for field authority", "no", "yes", "Diagnostic/model constraint only."),
        concept("quota", "current_quota_m3 / equal_parcel_quota_m3", "candidate matrix; parcel summary", "current_quota_m3; esit_parsel_kota_m3", "m3", "annual/scenario", "Administrative or model comparison quota", "reference allocation rules", "SCENARIO", "medium", "yes", "candidate metadata", "Not official allocation."),
        concept("analysis_unit_current_demand", "water_m3", "data/parsel_su_kar_ozet.csv", "mevcut_su_m3", "m3", "2024 annual", "Unit share of current-pattern calculated gross demand", "source workbook/model reference", "CALCULATED_REFERENCE", "medium", "yes", "baseline comparison", "Not measured withdrawal."),
        concept("candidate_crop_demand", "water_m3_calib_gross", "senaryo1/2 backend season tables and candidate matrix", "water_m3_calib_gross / water_m3_da", "m3 or m3/da", "season/annual", "Candidate crop model demand", "calibrated/proxy crop water × area", "DERIVED_PROXY", "medium-low", "yes", "yes", "Varies by source coverage."),
        concept("optimized_plan_demand", "total_water_m3", "engine result", "total_water_m3", "m3", "annual", "Computed demand of selected scenario plan", "sum area × selected gross water intensity", "SCENARIO", "high for computation", "yes", "yes", "Does not represent observed use."),
        concept("monthly_demand", "delivery_report.demand_m3", "engine result", "demand_m3", "m3/month", "calendar month", "Monthly scenario demand", "calib: annual demand × reservoir profile; FAO: crop monthly matrices", "SCENARIO", "low in active calibrated Akkaya path", "no", "yes", "Calibrated path is proportional, not crop-specific."),
        concept("annual_demand", "total_water_m3", "engine result", "total_water_m3", "m3", "annual", "Scenario plan total", "sum monthly or unit/season totals", "SCENARIO", "high for arithmetic", "yes", "yes", "Input authority remains separate."),
        concept("effective_rainfall_contribution", "peff_m", "app.py FAO calculation", "precip_mm", "mm/month", "calendar month", "Rainfall credited against ETc", "USDA-SCS effective rainfall relation", "DERIVED_PROXY", "medium-low", "no", "FAO mode", "Not used for active calibrated floor."),
        concept("net_irrigation_requirement", "nir_d", "app.py FAO calculation", "derived", "mm", "day aggregated to month", "ETc remaining after effective rainfall", "max(0, ETc-effective rainfall)", "DERIVED_PROXY", "medium-low", "no", "FAO mode", "Requires verified climate and phenology."),
        concept("gross_irrigation_requirement", "gross_d / water_m3_calib_gross", "app.py; seasonal table", "derived / water_m3_calib_gross", "mm=m3/da; m3", "monthly/season", "Demand before field delivery after efficiency allowance", "net requirement / irrigation efficiency", "DERIVED_PROXY", "medium-low", "yes", "yes", "Active floor uses calibrated seasonal gross values, not a verified survival threshold."),
    ]

    trace = [
        dict(step=1, variable="current pattern demand", source="parsel_su_kar_ozet.csv", operation="sum 179 mevcut_su_m3", result_m3=current_total, authority="CALCULATED_REFERENCE", evidence="water_context note and adapter kind"),
        dict(step=2, variable="annual withdrawal-named source field", source="akkaya_baraj_su_bilanco_2000_2025.csv", operation="select 2024 cekis_su_hacmi_hm3", result_m3=annual_withdrawal_field, authority="UNKNOWN", evidence="field label says hm3 but magnitude behaves as m3; no generator or official citation"),
        dict(step=3, variable="reservoir irrigation baseline", source="akkaya_reservoir_monthly_backend.csv", operation="sum 12 rows for 2024; compare annual field", result_m3=reservoir_total, authority="UNKNOWN", evidence="matches annual withdrawal-named field within 0.001 m3; lineage match does not establish measurement authority"),
        dict(step=4, variable="engine annual budget", source="app.py:basin_budget_and_delivery_caps", operation="reservoir baseline × 0.90", result_m3=engine_budget, authority="SCENARIO", evidence="code default envFlowRatio=0.10"),
        dict(step=5, variable="raw delivery capacity", source="delivery_capacity_monthly_assumed.csv", operation="sum rounded monthly baseline × 1.15", result_m3=raw_delivery, authority="DERIVED_PROXY", evidence="all 12 ratios approximately 1.15; source note"),
        dict(step=6, variable="effective delivery capacity", source="app.py:basin_budget_and_delivery_caps", operation="raw delivery × 0.90", result_m3=effective_delivery, authority="SCENARIO", evidence="dimensionless environmental reserve"),
        dict(step=7, variable="protected perennial current reference", source="52 current rows", operation="sum current reference water", result_m3=protected_current, authority="CALCULATED_REFERENCE", evidence="Phase 1 frozen protected set"),
        dict(step=8, variable="protected perennial model floor", source="primary calibrated current-crop rows + app multiplier", operation="sum full-area primary demand × 0.72", result_m3=protected_floor, authority="SCENARIO", evidence="water_saving objective adjustment; not survival water"),
        dict(step=9, variable="full S2 GA seed123 demand", source="Phase 2 frozen fixture/test", operation="sum validated final plan", result_m3=FULL_S2_GA_SEED123_M3, authority="SCENARIO", evidence="deterministic engine output"),
    ]

    annual = dict(
        planning_year=YEAR,
        analysis_units=len(units),
        current_pattern_calculated_gross_demand_m3=current_total,
        water_context_reference_m3=context_reference,
        reservoir_irrigation_baseline_annual_sum_m3=reservoir_total,
        upstream_2024_withdrawal_named_field_m3=annual_withdrawal_field,
        upstream_annual_match_absolute_difference_m3=abs(reservoir_total-annual_withdrawal_field),
        upstream_unit_label_anomaly="column suffix is hm3, while numeric magnitude and downstream use are m3-scale",
        reservoir_baseline_authority="UNKNOWN",
        environmental_flow_ratio=ENV_FLOW_RATIO,
        environmental_flow_authority="ASSUMED",
        engine_annual_budget_m3=engine_budget,
        raw_monthly_delivery_sum_m3=raw_delivery,
        effective_delivery_sum_m3=effective_delivery,
        delivery_authority="DERIVED_PROXY",
        full_s2_ga_seed123_demand_m3=FULL_S2_GA_SEED123_M3,
        official_annual_allocation_m3=None,
        measured_annual_delivery_m3=None,
    )
    floor_summary = dict(
        definition="current-model protected perennial demand floor under S2 water_saving",
        protected_units=len(protected_rows),
        protected_area_da=protected_area,
        protected_perennial_current_reference_demand_m3=protected_current,
        protected_perennial_current_reference_profit_tl=protected_profit,
        protected_perennial_model_floor_m3=protected_floor,
        method="locked current crop primary calibrated gross intensity × full analysis-unit area × 0.72",
        multiplier=WATER_SAVING_PERENNIAL_MULTIPLIER,
        multiplier_meaning="existing water_saving objective irrigation adjustment; model assumption",
        crop_counts=crop_counts,
        by_settlement=settlement_summary,
        survival_water_claim_allowed=False,
        monthly_floor_available=False,
        monthly_floor_reason="Active calibrated S2 rows contain no planting/harvest dates or crop-specific monthly demand; reservoir-profile allocation would be circular and non-phenological.",
    )
    bounds = dict(
        classification="STRUCTURAL INFEASIBILITY UNDER CURRENT MODEL INPUTS",
        real_world_infeasibility_claim=False,
        minimum_annual_budget_to_cover_model_floor_m3=protected_floor,
        current_engine_budget_m3=engine_budget,
        model_floor_minus_engine_budget_m3=protected_floor-engine_budget,
        minimum_factor_relative_to_engine_budget=protected_floor/engine_budget,
        effective_delivery_sum_m3=effective_delivery,
        minimum_factor_relative_to_effective_delivery_sum=protected_floor/effective_delivery,
        reservoir_baseline_sum_m3=reservoir_total,
        minimum_factor_relative_to_reservoir_baseline=protected_floor/reservoir_total,
        annual_necessary_condition_met=protected_floor <= engine_budget,
        monthly_necessary_condition_evaluated=False,
        monthly_reason=floor_summary["monthly_floor_reason"],
        note="Ratios are diagnostic lower bounds, not recommended budgets or supply multipliers.",
    )

    authority_rows = [
        dict(variable="current_pattern_calculated_gross_demand", current_value_source=f"{current_total:.6f} m3; parsel summary", authority_class="CALCULATED_REFERENCE", confidence="medium", production_allowed="comparison only", real_world_claim_allowed="demand estimate only", replacement_required="yes for observed withdrawals", priority="high"),
        dict(variable="reservoir_irrigation_baseline", current_value_source=f"{reservoir_total:.6f} m3/year; monthly CSV matches 2024 cekis_su_hacmi_hm3 field", authority_class="UNKNOWN", confidence="low; lineage match only", production_allowed="model scenario only", real_world_claim_allowed="no", replacement_required="yes", priority="critical"),
        dict(variable="engine_annual_budget", current_value_source=f"{engine_budget:.6f} m3; baseline × 0.90", authority_class="SCENARIO", confidence="high arithmetic/low authority", production_allowed="diagnostic only", real_world_claim_allowed="no", replacement_required="yes", priority="critical"),
        dict(variable="raw_delivery_capacity", current_value_source=f"{raw_delivery:.6f} m3/year; monthly baseline × 1.15", authority_class="DERIVED_PROXY", confidence="high formula/low capacity", production_allowed="diagnostic only", real_world_claim_allowed="no", replacement_required="yes", priority="critical"),
        dict(variable="environmental_flow_ratio", current_value_source="0.10; code default/run option", authority_class="ASSUMED", confidence="low local authority", production_allowed="scenario only", real_world_claim_allowed="no", replacement_required="yes", priority="high"),
        dict(variable="effective_delivery_capacity", current_value_source=f"{effective_delivery:.6f} m3/year; proxy × 0.90", authority_class="SCENARIO", confidence="high arithmetic/low authority", production_allowed="diagnostic only", real_world_claim_allowed="no", replacement_required="yes", priority="critical"),
        dict(variable="protected_perennial_current_reference", current_value_source=f"{protected_current:.6f} m3; 52 current rows", authority_class="CALCULATED_REFERENCE", confidence="medium", production_allowed="comparison only", real_world_claim_allowed="reference demand only", replacement_required="yes for measured use", priority="high"),
        dict(variable="protected_perennial_model_floor", current_value_source=f"{protected_floor:.6f} m3; calibrated rows × 0.72", authority_class="SCENARIO", confidence="high reproduction/low agronomic minimum", production_allowed="model lower-bound diagnostic", real_world_claim_allowed="no survival/field claim", replacement_required="yes", priority="critical"),
        dict(variable="official_allocation", current_value_source="not supplied", authority_class="UNKNOWN", confidence="none", production_allowed="no", real_world_claim_allowed="no", replacement_required="yes", priority="critical"),
    ]

    gaps = [
        ("official annual irrigation allocation", "DSİ / irrigation scheme authority", "m3/year", "Defines authoritative annual supply", "critical"),
        ("official monthly allocation or release schedule", "DSİ / reservoir operator", "m3/month", "Defines monthly available supply", "critical"),
        ("reservoir storage and inflow/outflow observations", "DSİ / reservoir operator", "m3 and m3/month", "Validates water balance and operating year", "high"),
        ("dead storage and operating rule curve", "DSİ design/operation records", "m3; elevation/month", "Separates stored volume from usable irrigation volume", "high"),
        ("environmental release obligation", "official basin/environmental decision", "m3/month or ratio", "Replaces assumed 10 percent reserve", "high"),
        ("canal design and operational conveyance capacity", "DSİ / irrigation association", "m3/s and m3/month", "Replaces 1.15 delivery proxy", "critical"),
        ("monthly delivered-water or SCADA records", "irrigation association / DSİ", "m3/month", "Validates actual delivery capacity and losses", "critical"),
        ("scheme conveyance loss or efficiency", "field test / operator records", "dimensionless", "Links release to farm-gate water", "high"),
        ("crop- and orchard-specific irrigation requirement", "field study / validated CROPWAT inputs", "mm/month and m3/da", "Validates perennial demand and monthly floor", "critical"),
        ("deficit-irrigation response thresholds", "local agronomic trials/literature", "mm or fraction of full requirement", "Required before any survival/minimum claim", "high"),
    ]
    gap_rows = [dict(required_variable=a, current_gap="not supplied with traceable authority", likely_source=b,
                     impact=f"Without it, this cannot be verified: {d}", unit=c, used_for=d, priority=e)
                for a,b,c,d,e in gaps]
    request_rows = [
        dict(required_variable=a, institution_source=b, preferred_granularity="Akkaya scheme; monthly plus annual",
             unit=c, period="minimum last 5 complete irrigation years", minimum_years=5,
             mandatory_or_optional="mandatory" if e == "critical" else "optional but strongly preferred",
             used_for=d, current_proxy=("none" if "official" in a or "dead" in a else "model CSV/default"),
             risk_if_missing="Real-world feasibility and operational capacity cannot be claimed")
        for a,b,c,d,e in gaps
    ]

    write_csv("water_concept_dictionary.csv", concepts)
    write_csv("water_source_trace.csv", trace)
    write_csv("water_authority_matrix.csv", authority_rows)
    write_json("annual_water_reconciliation.json", annual)
    write_csv("monthly_water_reconciliation.csv", monthly)
    write_csv("protected_perennial_units.csv", protected_rows)
    write_json("protected_perennial_demand_summary.json", floor_summary)
    write_json("feasibility_lower_bounds.json", bounds)
    write_csv("official_data_gaps.csv", gap_rows)
    write_csv("official_data_request_specification.csv", request_rows)

    (OUT / "real_world_claim_boundary.md").write_text(f"""# Real-world claim boundary

## Şu an söylenebilir

- Mevcut model girdileri altında protected perennial model floor `{protected_floor:,.3f} m³`, engine annual budget `{engine_budget:,.3f} m³` değerini aşar.
- Bu nedenle perennial kilitler korunurken annual constraint açısından **STRUCTURAL INFEASIBILITY UNDER CURRENT MODEL INPUTS** vardır.
- `100,700,080.81 m³` mevcut ürün deseninin hesaplanmış brüt talep referansıdır.
- Delivery serisi reservoir irrigation baseline değerinin yaklaşık `1.15×` türetilmiş proxy’sidir.

## Şu an söylenemez

- Akkaya sahasının gerçek kullanılabilir suyu kesin olarak `{engine_budget:,.3f} m³`dür.
- DSİ resmî tahsisi veya gerçek kanal kapasitesi mevcut model CSV’leriyle kanıtlanmıştır.
- `{protected_floor:,.3f} m³` ağaçların hayatta kalması için minimum sudur.
- Mevcut saha arzı kesinlikle yetersizdir.
- Aylık perennial kapasite ihlali kanıtlanmıştır; aktif calibrated girdide ürün bazlı aylık perennial talep yoktur.
""", encoding="utf-8")

    (OUT / "phase2_minor_followup_backlog.md").write_text("""# Phase 2 minor follow-up backlog

1. FAO mode’da canonical month-key normalization aylık score penalty’yi etkinleştirerek plan hash’ini değiştirebilir; davranış değişikliği kullanıcı/provenance metninde açıklaştırılmalı.
2. `validated_final_plan`, `feasible=false` iken tam bilimsel onay izlenimi verebilir; terminoloji ayrıca ele alınmalı.
3. UI’da `100.7M m³ calculated_reference` ile S2 engine’in reservoir-derived budget değeri daha açık ayrılmalı.

Bu Phase 3 audit’inde UI veya production kodu değiştirilmedi.
""", encoding="utf-8")

    (OUT / "phase3_summary.md").write_text(f"""# Scientific Phase 3 — verified water supply and protected perennial demand floor

## Sonuç

Mevcut model girdileri altında yapısal infeasibility doğrulandı; real-world infeasibility doğrulanmadı. Kullanılan reservoir ve delivery serilerinin resmî/ölçülmüş arz olduğuna dair kaynak yoktur.

| Kavram | Değer | Authority |
|---|---:|---|
| Current-pattern calculated gross demand | {current_total:,.3f} m³ | CALCULATED_REFERENCE |
| Reservoir irrigation baseline sum | {reservoir_total:,.3f} m³ | UNKNOWN |
| Engine annual budget after 10% reserve | {engine_budget:,.3f} m³ | SCENARIO |
| Raw monthly delivery sum | {raw_delivery:,.3f} m³ | DERIVED_PROXY |
| Effective delivery sum | {effective_delivery:,.3f} m³ | SCENARIO |
| Protected perennial current reference | {protected_current:,.3f} m³ | CALCULATED_REFERENCE |
| Protected perennial current-model floor | {protected_floor:,.3f} m³ | SCENARIO |
| Full S2 GA seed123 plan | {FULL_S2_GA_SEED123_M3:,.3f} m³ | SCENARIO |

## Protected set and floor

- 52 observed-current perennial units, `{protected_area:,.1f} da`.
- Current reference sum: `{protected_current:,.3f} m³`.
- Existing engine water_saving floor: primary calibrated current-crop demand × `0.72` = `{protected_floor:,.3f} m³`.
- This is objective-dependent model demand. It is not observed use, independently validated agronomic minimum, or survival water.
- Active calibrated S2 rows have no planting/harvest dates, so a defensible crop-specific monthly perennial floor cannot be produced.

## Necessary feasibility condition

- Annual model floor minus engine budget: `{protected_floor-engine_budget:,.3f} m³`.
- Minimum diagnostic factor relative to engine budget: `{protected_floor/engine_budget:.6f}`.
- Minimum diagnostic factor relative to effective delivery sum: `{protected_floor/effective_delivery:.6f}`.
- These are lower-bound ratios, not recommended budgets or capacity multipliers.

## Source conclusions

- The 179 analysis-unit current water fields reproduce `100,700,080.81 m³` exactly within floating tolerance.
- The 12 reservoir irrigation-baseline rows reproduce `{reservoir_total:,.3f} m³` and match the 2024 `cekis_su_hacmi_hm3` annual field within `0.001 m³`. The header/unit conflict, absent generator and absent official citation leave authority UNKNOWN; the numerical match only establishes an internal lineage link.
- All 12 delivery ratios are approximately `1.15`; the source note calls the capacity assumed. It is DERIVED_PROXY.
- `envFlowRatio=0.10` is an existing configurable model assumption; no local official ecological-release evidence was supplied.

No optimizer, production source, scientific input, ProjectStore, budget, lock, delivery value or UI code was changed.
""", encoding="utf-8")

    source_hashes_after = {str(p.relative_to(ROOT)).replace("\\", "/"): sha256(p) for p in tracked_inputs}
    assert source_hashes_before == source_hashes_after
    production = [ROOT / "app.py", ROOT / "kds/science/results.py", ROOT / "kds/science/validation.py",
                  ROOT / "kds/application/readiness.py", ROOT / "index.html", ROOT / "script.js", ROOT / "style.css"]
    guard = dict(
        baseline_commit="b2ec7157493943966bee825c14fbc03110e7a204",
        production_sha256={str(p.relative_to(ROOT)).replace("\\", "/"): sha256(p) for p in production},
        input_sha256=source_hashes_after,
        generator="tools/scientific_audit/water_supply_phase3.py",
        optimizer_executed=False,
        project_store_accessed=False,
    )
    write_json("source_and_mutation_guard.json", guard)
    return dict(annual=annual, floor=floor_summary, bounds=bounds,
                protected_rows=protected_rows, monthly=monthly, authority=authority_rows,
                source_hashes=source_hashes_after)


if __name__ == "__main__":
    result = build()
    print(json.dumps({
        "output": str(OUT),
        "current_pattern_m3": result["annual"]["current_pattern_calculated_gross_demand_m3"],
        "protected_units": result["floor"]["protected_units"],
        "protected_area_da": result["floor"]["protected_area_da"],
        "protected_model_floor_m3": result["floor"]["protected_perennial_model_floor_m3"],
        "classification": result["bounds"]["classification"],
    }, ensure_ascii=False, indent=2))
