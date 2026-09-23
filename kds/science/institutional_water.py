"""Project-agnostic verified water demand and feasibility consumers.

This module consumes only values supplied through the project provider boundary.
It does not read reference files and does not alter optimizer selection math.
"""
from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta
import math
from typing import Any


def _dates(record: dict[str, Any], planning_year: int) -> tuple[date, date]:
    if record["mode"] == "YEAR_SPECIFIC":
        return date.fromisoformat(record["planting_date"]), date.fromisoformat(record["harvest_date"])
    planting_month, planting_day = map(int, record["planting_window_start"].split("-"))
    harvest_month, harvest_day = map(int, record["harvest_window_start"].split("-"))
    planting_year = planning_year - 1 if record.get("season_year_semantics") == "CROSSES_CALENDAR_YEAR" else planning_year
    return date(planting_year, planting_month, planting_day), date(planning_year, harvest_month, harvest_day)


def _kc(day_index: int, total_days: int, parameter: dict[str, Any]) -> float:
    stages = [float(parameter[name]) for name in ("p_ini", "p_dev", "p_mid", "p_late")]
    if parameter["stage_value_mode"] == "DAYS":
        weights = stages
    else:
        weights = [value * total_days for value in stages]
    scale = total_days / max(sum(weights), 1.0)
    ini, dev, mid, late = [value * scale for value in weights]
    if day_index < ini:
        return float(parameter["kc_ini"])
    if day_index < ini + dev:
        progress = (day_index - ini) / max(dev, 1.0)
        return float(parameter["kc_ini"]) + progress * (float(parameter["kc_mid"]) - float(parameter["kc_ini"]))
    if day_index < ini + dev + mid:
        return float(parameter["kc_mid"])
    progress = min(1.0, (day_index - ini - dev - mid) / max(late, 1.0))
    return float(parameter["kc_mid"]) + progress * (float(parameter["kc_end"]) - float(parameter["kc_mid"]))


def monthly_gross_demand_m3_da(parameter: dict[str, Any], phenology: dict[str, Any],
                                climate: list[dict[str, Any]], efficiency: float,
                                planning_year: int) -> dict[str, float]:
    """Calculate daily FAO56-style ETc-minus-effective-rain demand by month."""
    if not 0 < efficiency <= 1:
        raise ValueError("Verified conveyance efficiency must be in (0, 1].")
    start, end = _dates(phenology, planning_year)
    if end < start:
        raise ValueError("Verified phenology harvest must not precede planting.")
    by_month = {int(str(row["month"])[5:7]): row for row in climate}
    if set(by_month) != set(range(1, 13)):
        raise ValueError("Verified crop-water execution requires 12 project climate months per analysis unit.")
    total_days = (end - start).days + 1
    demand: dict[str, float] = defaultdict(float)
    current = start
    while current <= end:
        row = by_month[current.month]  # planning-year monthly normals also support cross-year seasons
        days_in_month = monthrange(current.year, current.month)[1]
        etc = float(row["et0_mm"]) * _kc((current - start).days, total_days, parameter) / days_in_month
        effective_rain = float(row["precip_mm"]) * 0.80 / days_in_month
        demand[f"{planning_year}-{current.month:02d}"] += max(0.0, etc - effective_rain) / efficiency
        current += timedelta(days=1)
    return {month: float(value) for month, value in sorted(demand.items())}


def select_perennial_requirement(records: list[dict[str, Any]], crop: str,
                                  analysis_unit_id: str | None) -> dict[str, Any] | None:
    matching = [row for row in records if row["crop"].casefold() == crop.casefold()
                and row.get("analysis_unit_id") in {None, analysis_unit_id}]
    exact = [row for row in matching if analysis_unit_id and row.get("analysis_unit_id") == analysis_unit_id]
    defaults = [row for row in matching if row.get("analysis_unit_id") is None]
    chosen = exact if exact else defaults
    if len(chosen) > 1:
        raise ValueError(f"Duplicate perennial requirement at the same specificity for {analysis_unit_id or '*'} / {crop}.")
    return chosen[0] if chosen else None


def validate_verified_result(result: dict[str, Any], scenario: str,
                             profiles: dict[tuple[str, str, str], dict[str, float]],
                             annual_supply_m3: float, monthly_supply_m3: dict[str, float],
                             monthly_delivery_m3: dict[str, float], release: dict[str, Any]) -> dict[str, Any]:
    ratios = release.get("values", {}) if release.get("form") == "ratio" else {}
    physical = release.get("values", {}) if release.get("form") == "monthly_release" else {}

    def usable(month: str, supply: float) -> float:
        if ratios:
            ratio = float(ratios.get(month, ratios.get(str(month)[:4], next(iter(ratios.values())))))
            return max(0.0, supply * (1.0 - ratio))
        return max(0.0, supply - float(physical.get(month, 0.0)))

    monthly_demand = {month: 0.0 for month in sorted(monthly_supply_m3)}
    unit_results = []
    for row in result.get("details", []):
        unit_id = str(row.get("parcelId") or row.get("analysis_unit_id") or "")
        area = float(row.get("area_da", 0.0) or 0.0)
        chosen = []
        if scenario == "S1":
            crop = row.get("chosenCrop") or row.get("crop")
            if crop:
                chosen.append((str(crop), "PRIMARY"))
        else:
            for key, season in (("primary", "PRIMARY"), ("secondary", "SECONDARY")):
                value = row.get(key)
                if value and value.get("crop") and str(value["crop"]).upper() not in {"NADAS", "FALLOW"}:
                    chosen.append((str(value["crop"]), season))
        unit_monthly = {month: 0.0 for month in monthly_demand}
        for crop, season in chosen:
            profile = profiles.get((unit_id, crop, season))
            if profile is None:
                raise ValueError(f"Missing verified monthly demand profile for {unit_id}/{crop}/{season}.")
            for month, value in profile.items():
                if month in monthly_demand:
                    unit_monthly[month] += float(value) * area
                    monthly_demand[month] += float(value) * area
        unit_results.append({"analysis_unit_id": unit_id, "area_da": area,
                             "selected_crops": [{"crop": crop, "season": season} for crop, season in chosen],
                             "monthly_water_demand_m3": unit_monthly,
                             "total_water_m3": math.fsum(unit_monthly.values())})
    usable_monthly = {month: usable(month, float(value)) for month, value in monthly_supply_m3.items()}
    supply_violations = [month for month in monthly_demand if monthly_demand[month] > usable_monthly[month] + 1e-6]
    delivery_violations = [month for month in monthly_demand if monthly_demand[month] > float(monthly_delivery_m3[month]) + 1e-6]
    annual_usable = math.fsum(usable_monthly.values())
    if release.get("form") == "ratio" and len(ratios) == 1:
        annual_usable = annual_supply_m3 * (1.0 - float(next(iter(ratios.values()))))
    elif release.get("form") == "monthly_release":
        annual_usable = max(0.0, annual_supply_m3 - math.fsum(float(v) for v in physical.values()))
    annual_demand = math.fsum(monthly_demand.values())
    annual = {"status": "PASS" if annual_demand <= annual_usable + 1e-6 else "FAIL",
              "demand_m3": annual_demand, "usable_supply_m3": annual_usable,
              "unit": "m3/year", "environmental_release_applied_once": True}
    supply = {"status": "PASS" if not supply_violations else "FAIL", "unit": "m3/month",
              "demand_m3": monthly_demand, "usable_supply_m3": usable_monthly,
              "violating_months": supply_violations}
    delivery = {"status": "PASS" if not delivery_violations else "FAIL", "unit": "m3/month",
                "demand_m3": monthly_demand, "capacity_m3": monthly_delivery_m3,
                "violating_months": delivery_violations}
    return {"annual_budget_validation": annual, "monthly_supply_validation": supply,
            "monthly_delivery_validation": delivery,
            "overall_feasible": bool(result.get("feasible", False) and not supply_violations
                                     and not delivery_violations and annual["status"] == "PASS"),
            "unit_results": unit_results}
