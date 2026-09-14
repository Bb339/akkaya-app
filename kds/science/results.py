"""V2 result projections; this module contains no optimization math."""
from copy import deepcopy
from math import isclose


RESULT_CONTRACT_VERSION = "scientific-result-v2"
FALLOW = {"NADAS", "FALLOW"}


def _crop_name(value):
    return str(value or "").strip()


def _is_planted(value):
    name = _crop_name(value)
    return bool(name) and name.upper() not in FALLOW


def _metrics(details, total_area, feasible=None):
    water = 0.0
    profit = 0.0
    active_by_unit = {}
    distribution = {}
    seasonal_fallow = 0.0
    for row in details:
        row_area = float(row.get("area_da", 0.0) or 0.0)
        planted_areas = []
        for season in ("primary", "secondary"):
            crop = row.get(season)
            if not crop:
                continue
            area = float(crop.get("area_da", row_area) or 0.0)
            water += float(crop.get("water_m3", 0.0) or 0.0)
            profit += float(crop.get("profit_tl", 0.0) or 0.0)
            name = _crop_name(crop.get("crop"))
            if _is_planted(name):
                planted_areas.append(area)
                distribution[name] = distribution.get(name, 0.0) + area
            else:
                seasonal_fallow += area
        active_by_unit[str(row.get("parcelId"))] = max(planted_areas, default=0.0)
    active = sum(active_by_unit.values())
    return dict(
        total_area_da=float(total_area),
        active_area_da=active,
        fallow_area_da=max(0.0, float(total_area) - active),
        seasonal_fallow_area_da=seasonal_fallow,
        total_water_m3=water,
        total_profit_tl=profit,
        efficiency_tl_per_m3=profit / water if water > 0 else 0.0,
        feasible=feasible,
        crop_distribution_da=distribution,
        distribution_basis="seasonal cropped area; S2 can count land twice",
    )


def _selected_units(config, units):
    selected = set(config.get("selected_ids") or [])
    return [u for u in units if not selected or u["external_id"] in selected]


def _raw_details(result):
    rows = []
    for source in result.get("details", []):
        row = deepcopy(source)
        row_area = float(row.get("area_da", 0.0) or 0.0)
        for season in ("primary", "secondary"):
            crop = row.get(season)
            if crop is not None:
                crop.setdefault("area_da", row_area)
        rows.append(row)
    return rows


def _final_details(result):
    rows = []
    for parcel_result in result.get("parcels", []):
        body = parcel_result.get("result") or {}
        parcel = body.get("parcel") or {}
        recommended = body.get("recommended") or []
        if not recommended:
            raise ValueError(f"Final S2 recommendation is missing for unit {parcel_result.get('id')!r}.")
        parcel_id = str(parcel_result.get("id") or parcel.get("id") or "")
        if not parcel_id:
            raise ValueError("Final S2 recommendation has no analysis unit identifier.")
        row = dict(
            parcelId=parcel_id,
            parcelName=parcel.get("name") or parcel_id,
            area_da=float(parcel.get("area_da", recommended[0].get("area", 0.0)) or 0.0),
            primary=None,
            secondary=None,
        )
        for index, recommendation in enumerate(recommended[:2]):
            name = _crop_name(recommendation.get("name"))
            if not name:
                raise ValueError(f"Final S2 recommendation has no crop for unit {parcel_id!r}.")
            if index == 1 and not _is_planted(name):
                continue
            row["primary" if index == 0 else "secondary"] = dict(
                crop=name,
                area_da=float(recommendation.get("area", row["area_da"]) or 0.0),
                water_m3=float(recommendation.get("waterTotal", recommendation.get("waterTotalM3", recommendation.get("totalWater", 0.0))) or 0.0),
                profit_tl=float(recommendation.get("profitTotal", recommendation.get("estimatedNetProfitTl", recommendation.get("totalProfit", 0.0))) or 0.0),
                season=recommendation.get("season"),
            )
        rows.append(row)
    return rows


def project_result(result, config, units):
    """Build the S2 audit/presentation contract from existing engine stages."""
    projected = deepcopy(result)
    if config.get("scenario") != "S2" or not result:
        return projected
    if result.get("result_contract_version") == RESULT_CONTRACT_VERSION:
        return projected

    selected_units = _selected_units(config, units)
    total_area = sum(float(unit["area_da"]) for unit in selected_units)
    raw_details = _raw_details(result)
    final_details = _final_details(result)
    raw_metrics = _metrics(raw_details, total_area, feasible=None)
    final_metrics = _metrics(final_details, total_area, feasible=result.get("feasible"))
    budget = float(result.get("water_budget_m3", 0.0) or 0.0)
    reported_water = result.get("total_water_m3")
    reported_profit = result.get("total_profit_tl")
    totals_consistent = (
        reported_water is not None and reported_profit is not None
        and isclose(float(reported_water), final_metrics["total_water_m3"], rel_tol=1e-9, abs_tol=1e-6)
        and isclose(float(reported_profit), final_metrics["total_profit_tl"], rel_tol=1e-9, abs_tol=1e-6)
    )
    validation = dict(
        authority="engine post-guard parcel recommendations",
        engine_guard_feasible=result.get("feasible"),
        annual_water_budget_met=(final_metrics["total_water_m3"] <= budget + 1e-6) if budget > 0 else None,
        monthly_delivery_evaluated=(result.get("meta", {}).get("delivery_report") is not None),
        engine_reported_totals_consistent=totals_consistent,
        scope="Existing engine guards only; monthly feasibility is reported only when the engine supplies a delivery report.",
    )
    projected.update(
        result_contract_version=RESULT_CONTRACT_VERSION,
        details=deepcopy(final_details),
        total_water_m3=final_metrics["total_water_m3"],
        total_profit_tl=final_metrics["total_profit_tl"],
        efficiency_tl_per_m3=final_metrics["efficiency_tl_per_m3"],
        feasible=final_metrics["feasible"],
        raw_optimizer_plan=dict(
            contract_stage="raw_optimizer",
            details=deepcopy(raw_details),
            metrics=raw_metrics,
            feasibility_status="not_validated",
            algorithm=result.get("algorithm"),
            objective=result.get("objective"),
            year=result.get("year"),
            selected_parcel_ids=deepcopy(result.get("meta", {}).get("selected_parcel_ids", [])),
            run_params=deepcopy(result.get("meta", {}).get("run_params", {})),
        ),
        validated_final_plan=dict(
            contract_stage="validated_final",
            details=deepcopy(final_details),
            parcels=deepcopy(result.get("parcels", [])),
            metrics=deepcopy(final_metrics),
            validation=validation,
        ),
        final_metrics=deepcopy(final_metrics),
    )
    return projected


def summarize(result, bundle):
    config = bundle.algorithm_configuration.copy()
    units = _selected_units(config, bundle.analysis_units.copy())
    total_area = sum(float(u["area_da"]) for u in units)
    params = result.get("meta", {}).get("run_params", {})
    if config["scenario"] == "S2" and result.get("final_metrics"):
        metrics = result["final_metrics"]
        active = metrics["active_area_da"]
        distribution = deepcopy(metrics["crop_distribution_da"])
    else:
        active = 0.0
        distribution = {}
        for row in result.get("details", []):
            area = float(row.get("area_da", 0.0))
            planted = [row.get("chosenCrop")] if _is_planted(row.get("chosenCrop")) else []
            if planted:
                active += area
            for crop in planted:
                distribution[crop] = distribution.get(crop, 0.0) + area
    return dict(
        total_area_da=total_area,
        active_area_da=active,
        fallow_area_da=max(0.0, total_area - active),
        total_water_m3=result.get("total_water_m3"),
        total_profit_tl=result.get("total_profit_tl"),
        efficiency_tl_per_m3=result.get("efficiency_tl_per_m3"),
        feasible=result.get("feasible"),
        score=params.get("bestScore"),
        score_note="S2 raw engine output does not expose final fitness." if config["scenario"] == "S2" else None,
        crop_distribution_da=distribution,
        distribution_basis="seasonal cropped area; S2 can count land twice",
        plan_difference=result.get("delta"),
        diversity=params.get("diversity"),
        effective_run_parameters=params,
    )


def present_stored_run(run, document):
    """Project legacy stored S2 runs without mutating or migrating the store."""
    presented = deepcopy(run)
    if presented.get("status") != "completed" or not presented.get("result"):
        return presented
    config = presented.get("configuration") or {"scenario": presented.get("scenario"), "selected_ids": []}
    presented["result"] = project_result(presented["result"], config, document.get("analysis_units", []))
    metrics = presented["result"].get("final_metrics")
    if metrics:
        summary = deepcopy(presented.get("summary") or {})
        for key in ("total_area_da", "active_area_da", "fallow_area_da", "total_water_m3", "total_profit_tl", "efficiency_tl_per_m3", "feasible", "crop_distribution_da", "distribution_basis"):
            if key in metrics:
                summary[key] = deepcopy(metrics[key])
        presented["summary"] = summary
    return presented
