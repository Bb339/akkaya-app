"""Resolve confirmed project datasets once and adapt them to the frozen engine boundary.

This module never reads reference files for VERIFIED_INSTITUTIONAL runs.  It
materializes a copied project document and delegates to the existing
``project_science.build_bundle`` adapter; ``kds.science`` remains unchanged.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from kds.domain.crop_parameters import VERIFIED_AUTHORITIES as CROP_VERIFIED_AUTHORITIES
from kds.domain.economic_data import VERIFIED_INPUT_AUTHORITIES, economic_authority
from kds.domain.water_data import AuthorityClass
from kds.science.institutional_water import monthly_gross_demand_m3_da, select_perennial_requirement


WATER_TYPES = (
    "annual_water_supply", "monthly_water_supply", "delivery_capacity",
    "environmental_release", "conveyance_efficiency",
    "perennial_irrigation_requirement",
)
ECONOMIC_TYPES = (
    "crop_yield", "crop_sale_price", "crop_support_payment",
    "crop_cost_components", "crop_net_profit", "analysis_unit_economics",
    "seasonal_economics",
)
VERIFIED_WATER_AUTHORITIES = {
    AuthorityClass.MEASURED.value,
    AuthorityClass.OFFICIAL_ALLOCATION.value,
    AuthorityClass.OFFICIAL_HISTORICAL.value,
}


@dataclass(frozen=True)
class VerifiedWaterContext:
    planning_year: int
    annual_supply_m3: float
    monthly_supply_m3: dict[str, float]
    monthly_delivery_capacity_m3: dict[str, float]
    environmental_release: dict[str, Any]
    conveyance_efficiency: float
    perennial_requirements: tuple[dict[str, Any], ...]
    datasets: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class VerifiedEconomicContext:
    planning_year: int
    crop_net_profit_tl_da: dict[str, float]
    analysis_unit_profit_tl: dict[str, float]
    seasonal_profit_tl_da: tuple[dict[str, Any], ...]
    datasets: tuple[dict[str, Any], ...]


def _dataset_fact(dataset: dict[str, Any]) -> dict[str, Any]:
    conversions = []
    for record in dataset.get("records", []):
        if record.get("conversion") or record.get("source_unit") != record.get("canonical_unit"):
            conversions.append({
                "source_row": record.get("source_row"),
                "source_unit": record.get("source_unit"),
                "canonical_unit": record.get("canonical_unit"),
                "conversion": deepcopy(record.get("conversion")),
            })
    return {
        "dataset_id": dataset["dataset_id"], "data_type": dataset["data_type"],
        "version": dataset["version"], "authority_class": dataset["authority_class"],
        "confirmed_at": dataset["confirmed_at"], "source": deepcopy(dataset.get("source", {})),
        "scope_key": dataset.get("scope_key"),
        "conversion_provenance": conversions,
    }


def _active_water(document: dict[str, Any], data_type: str) -> dict[str, Any]:
    store = document.get("water_data", {})
    dataset_id = store.get("active", {}).get(data_type)
    dataset = store.get("datasets", {}).get(dataset_id)
    if not dataset:
        raise ValueError(f"VERIFIED_INSTITUTIONAL requires active {data_type}.")
    return dataset


def _active_by_type(document: dict[str, Any], store_name: str, data_type: str) -> list[dict[str, Any]]:
    store = document.get(store_name, {})
    ids = [value for key, value in store.get("active", {}).items() if key.startswith(data_type + "|")]
    return [store.get("datasets", {}).get(value) for value in ids if store.get("datasets", {}).get(value)]


def _validate_dataset(dataset: dict[str, Any], year: int, *, synthetic_allowed: bool,
                      authorities: set[str], required_scope: str = "project") -> None:
    if dataset.get("status") != "active" or not dataset.get("confirmed_at"):
        raise ValueError(f"{dataset.get('data_type')} must be active and confirmed.")
    if dataset.get("authority_class") not in authorities:
        raise ValueError(f"{dataset.get('data_type')} authority is not eligible for verified execution.")
    if dataset.get("derivation_status") == "STALE" or dataset.get("requires_recalculation") is True:
        raise ValueError(f"{dataset.get('data_type')} is stale or requires recalculation.")
    records = dataset.get("records", [])
    if not records:
        raise ValueError(f"{dataset.get('data_type')} has no records.")
    for record in records:
        record_year = record.get("planning_year", record.get("applicable_year"))
        if int(record_year) != year:
            raise ValueError(f"{dataset.get('data_type')} does not match planning year {year}.")
        if record.get("synthetic") and not synthetic_allowed:
            raise ValueError(f"{dataset.get('data_type')} is synthetic and cannot support a real institutional run.")
        if dataset.get("data_type") in ECONOMIC_TYPES and record.get("temporal_alignment") not in {None, "CURRENT"}:
            raise ValueError(f"{dataset.get('data_type')} contains stale or future observations.")
        scope = record.get("geographic_scope") or record.get("scope") or "project"
        if scope != required_scope:
            raise ValueError(f"{dataset.get('data_type')} does not match geographic scope {required_scope}.")


def _synthetic_project(document: dict[str, Any]) -> bool:
    metadata = document.get("metadata", {})
    return bool(metadata.get("synthetic_institutional_test") and metadata.get("not_official"))


def resolve_verified_water(document: dict[str, Any]) -> VerifiedWaterContext:
    year = int(document["project"]["planning_year"])
    synthetic = _synthetic_project(document)
    required_scope = (document.get("project", {}).get("pilot_geographic_scope") or
                      document.get("metadata", {}).get("pilot_geographic_scope") or "project")
    selected = {}
    for data_type in WATER_TYPES:
        dataset = _active_water(document, data_type)
        _validate_dataset(dataset, year, synthetic_allowed=synthetic,
                          authorities=VERIFIED_WATER_AUTHORITIES, required_scope=required_scope)
        selected[data_type] = dataset
    monthly = selected["monthly_water_supply"]["records"]
    delivery = selected["delivery_capacity"]["records"]
    if len(monthly) != 12 or len(delivery) != 12:
        raise ValueError("Verified monthly supply and delivery capacity require 12 months.")
    releases = selected["environmental_release"]["records"]
    efficiencies = selected["conveyance_efficiency"]["records"]
    if len(efficiencies) != 1:
        raise ValueError("Verified execution requires one unambiguous conveyance efficiency record.")
    release = ({"form": "ratio", "values": {r.get("month") or str(year): r["ratio"] for r in releases}}
               if releases[0]["release_form"] == "ratio" else
               {"form": "monthly_release", "values": {r["month"]: r["release_m3"] for r in releases}})
    return VerifiedWaterContext(
        planning_year=year,
        annual_supply_m3=float(selected["annual_water_supply"]["records"][0]["amount_m3"]),
        monthly_supply_m3={r["month"]: float(r["amount_m3"]) for r in monthly},
        monthly_delivery_capacity_m3={r["month"]: float(r["capacity_m3"]) for r in delivery},
        environmental_release=release,
        conveyance_efficiency=float(efficiencies[0]["efficiency"]),
        perennial_requirements=tuple(deepcopy(selected["perennial_irrigation_requirement"]["records"])),
        datasets=tuple(_dataset_fact(selected[k]) for k in WATER_TYPES),
    )


def resolve_verified_economics(document: dict[str, Any], scenario: str) -> VerifiedEconomicContext:
    year = int(document["project"]["planning_year"])
    synthetic = _synthetic_project(document)
    selected: list[dict[str, Any]] = []
    by_type: dict[str, list[dict[str, Any]]] = {}
    authorities = {value.value for value in VERIFIED_INPUT_AUTHORITIES}
    required_scope = (document.get("project", {}).get("pilot_geographic_scope") or
                      document.get("metadata", {}).get("pilot_geographic_scope") or "project")
    active = document.get("economic_data", {}).get("active", {})
    datasets_store = document.get("economic_data", {}).get("datasets", {})
    for data_type in ECONOMIC_TYPES:
        pointer = f"{data_type}|{year}|{required_scope}|catalog"
        dataset_id = active.get(pointer)
        datasets = [datasets_store[dataset_id]] if dataset_id in datasets_store else []
        for dataset in datasets:
            _validate_dataset(dataset, year, synthetic_allowed=synthetic, authorities=authorities,
                              required_scope=required_scope)
        if datasets:
            by_type[data_type] = datasets
            selected.extend(datasets)
    if not by_type.get("crop_net_profit"):
        raise ValueError("VERIFIED_INSTITUTIONAL requires active verified crop_net_profit.")
    if scenario == "S2" and not by_type.get("seasonal_economics"):
        raise ValueError("S2 VERIFIED_INSTITUTIONAL requires active verified seasonal_economics.")
    catalog = {c["name"] for c in document.get("crops", [])}
    profit_rows = [r for d in by_type["crop_net_profit"] for r in d["records"]]
    profits = {r["crop"]: float(r["net_profit_per_da"]) for r in profit_rows}
    if catalog - profits.keys():
        raise ValueError("Verified crop_net_profit coverage is incomplete: " + ", ".join(sorted(catalog - profits.keys())))
    units = {r["analysis_unit_id"]: float(r["net_profit_tl"])
             for d in by_type.get("analysis_unit_economics", []) for r in d["records"]
             if r.get("net_profit_tl") is not None}
    seasonal = tuple(deepcopy(r) for d in by_type.get("seasonal_economics", []) for r in d["records"])
    return VerifiedEconomicContext(year, profits, units, seasonal,
                                   tuple(_dataset_fact(d) for d in selected))


def _resolve_crop_contract(document: dict[str, Any], data_type: str) -> dict[str, Any]:
    from kds.application.readiness import _readiness_dataset_selection
    year = int(document["project"]["planning_year"])
    synthetic = _synthetic_project(document)
    datasets, selection = _readiness_dataset_selection(document, data_type)
    if selection["status"] != "SELECTED" or len(datasets) != 1:
        raise ValueError(f"VERIFIED_INSTITUTIONAL {data_type} selection failed: {selection['status']}.")
    dataset = datasets[0]
    _validate_dataset(dataset, year, synthetic_allowed=synthetic,
                      authorities={value.value for value in CROP_VERIFIED_AUTHORITIES},
                      required_scope=(document.get("project", {}).get("pilot_geographic_scope") or
                                      document.get("metadata", {}).get("pilot_geographic_scope") or "project"))
    records = dataset["records"]
    required = {__import__("app").canonical_crop_key(c["name"]) for c in document.get("crops", [])}
    actual = {r["runtime_crop_id"] for r in records
              if r.get("resolution_status") in {"EXACT", "REVIEWED_ALIAS"}}
    if required != actual:
        raise ValueError(f"Verified {data_type} crop coverage is incomplete or ambiguous.")
    return dataset


def _applied_imports(document: dict[str, Any], data_types: set[str]) -> list[dict[str, Any]]:
    return [{"import_batch_id": b["id"], "data_type": b["data_type"], "file_hash": b["file_hash"],
             "applied_revision": b.get("applied_revision"), "filename": b.get("filename")}
            for b in document.get("imports", {}).values()
            if b.get("status") == "applied" and b.get("data_type") in data_types]


def _candidate_snapshot(document: dict[str, Any], scenario: str) -> dict[str, Any]:
    extra = document.get("scientific_inputs", {})
    if not extra.get("candidates") or not extra.get("unit_parameters"):
        raise ValueError("VERIFIED_INSTITUTIONAL requires confirmed project candidates and current-pattern unit parameters.")
    if scenario == "S2" and not extra.get("seasonal_resources", {}).get("s2"):
        raise ValueError("S2 VERIFIED_INSTITUTIONAL requires project seasonal candidate resources.")
    imports = _applied_imports(document, {"candidates", "scientific_inputs", "analysis_units", "crops"})
    present = {item["data_type"] for item in imports}
    required = {"candidates", "scientific_inputs", "analysis_units", "crops"}
    if not required <= present:
        raise ValueError("Verified candidate/current-pattern inputs require applied import provenance: " +
                         ", ".join(sorted(required - present)))
    candidate_imports = [item for item in imports if item["data_type"] == "candidates"]
    current_imports = [item for item in imports if item["data_type"] == "scientific_inputs"]
    latest_current = max(current_imports, key=lambda item: item.get("applied_revision") or 0)
    current_pattern = {
        "source": "confirmed project scientific_inputs import",
        "import_batch_id": latest_current["import_batch_id"],
        "file_hash": latest_current["file_hash"],
        "applied_revision": latest_current.get("applied_revision"),
        "filename": latest_current.get("filename"),
        "analysis_unit_count": len(extra["unit_parameters"]),
        "planning_year": document["project"]["planning_year"],
        "geographic_scope": (document.get("project", {}).get("pilot_geographic_scope") or
                             document.get("metadata", {}).get("pilot_geographic_scope") or "project"),
    }
    return {"candidate_source": "confirmed project import", "candidate_count": len(extra["candidates"]),
            "analysis_unit_count": len(document.get("analysis_units", [])),
            "imports": candidate_imports, "current_pattern_source": current_pattern}


def verified_execution_plan(document: dict[str, Any], configuration: dict[str, Any]) -> dict[str, Any]:
    water = resolve_verified_water(document)
    economics = resolve_verified_economics(document, configuration["scenario"])
    parameters = _resolve_crop_contract(document, "crop_water_parameters")
    phenology = _resolve_crop_contract(document, "crop_phenology")
    candidates = _candidate_snapshot(document, configuration["scenario"])
    if water.environmental_release["form"] != "ratio":
        raise ValueError("Physical environmental release is contract-valid but NOT_EXECUTABLE_WITH_CURRENT_MODE.")
    if len(set(float(value) for value in water.environmental_release["values"].values())) != 1:
        raise ValueError("Verified execution requires one annual environmental release ratio.")
    climate = document.get("scientific_inputs", {}).get("seasonal_resources", {}).get("monthly_climate", [])
    climate_months: dict[str, set[int]] = {}
    for row in climate:
        climate_months.setdefault(str(row.get("parcel_id")), set()).add(int(str(row.get("month"))[5:7]))
    expected_units = {str(unit["external_id"]) for unit in document.get("analysis_units", [])}
    if set(climate_months) != expected_units or any(months != set(range(1, 13)) for months in climate_months.values()):
        raise ValueError("Verified crop-water execution requires 12 project climate months per analysis unit.")
    if configuration["scenario"] == "S2":
        by_crop = {}
        for record in phenology["records"]:
            by_crop.setdefault(record["runtime_crop_id"], set()).add(record["season"])
        missing = sorted(crop for crop in by_crop if not {"PRIMARY", "SECONDARY"} <= by_crop[crop])
        if missing:
            raise ValueError("S2 verified phenology requires PRIMARY and SECONDARY records for every runtime crop: " + ", ".join(missing))
    synthetic = _synthetic_project(document)
    datasets = [*water.datasets, *economics.datasets, _dataset_fact(parameters), _dataset_fact(phenology)]
    return {
        "execution_profile": "VERIFIED_INSTITUTIONAL", "project_id": document["project"]["id"],
        "planning_year": water.planning_year, "ready": True, "blocking_reasons": [], "warnings": (
            ["SYNTHETIC_INSTITUTIONAL_TEST_PROJECT; NOT_OFFICIAL"] if synthetic else []),
        "datasets": datasets, "candidate_source": {k: v for k, v in candidates.items() if k != "current_pattern_source"},
        "current_pattern_source": candidates["current_pattern_source"], "algorithm": configuration["algorithm"],
        "objective": configuration["objective"], "scenario": configuration["scenario"],
        "synthetic": synthetic, "not_official": synthetic,
    }


def verified_readiness(document: dict[str, Any], scenario: str = "S1") -> dict[str, Any]:
    minimal = {"scenario": scenario, "algorithm": "GA", "objective": "water_saving"}
    try:
        plan = verified_execution_plan(document, minimal)
        datasets = plan["datasets"]
        by_type = {d["data_type"]: d for d in datasets}
        def connected(data_type, consumer, scope="S1_AND_S2"):
            return {"status": "READY", "engine_connected": True, "connection_state": "CONNECTED",
                    "execution_scope": scope, "consumer": consumer, "dataset": by_type[data_type]}
        domains = {
            "annual_water": connected("annual_water_supply", "optimizer annual usable-water budget"),
            "monthly_supply": connected("monthly_water_supply", "verified monthly supply validation"),
            "delivery": connected("delivery_capacity", "verified monthly delivery validation"),
            "environmental_release": connected("environmental_release", "single-deduction usable-water calculation"),
            "conveyance": connected("conveyance_efficiency", "gross crop-water demand calculation"),
            "perennial_requirement": connected("perennial_irrigation_requirement", "S2 perennial exact/default water override", "S2"),
            "economics": {"status": "READY", "engine_connected": True, "connection_state": "CONNECTED",
                          "execution_scope": "S1_AND_S2", "consumer": "candidate/seasonal optimizer profit",
                          "datasets": [d for d in datasets if d["data_type"] in ECONOMIC_TYPES]},
            "crop_parameters": connected("crop_water_parameters", "verified FAO56 project water calculator"),
            "phenology": connected("crop_phenology", "verified monthly crop-water calendar"),
            "candidates": {"status": "READY", "engine_connected": True, "connection_state": "CONNECTED",
                           "execution_scope": "S1_AND_S2", "consumer": "optimizer candidate matrix", **plan["candidate_source"]},
            "current_pattern": {"status": "READY", "engine_connected": True, "connection_state": "CONNECTED",
                                "execution_scope": "S1_AND_S2", "consumer": "unit baseline and perennial locks",
                                **plan["current_pattern_source"]},
        }
        return {"ready": True, "blocking_reasons": [], "warnings": plan["warnings"], "domains": domains}
    except ValueError as exc:
        message = str(exc)
        consumers = {
            "annual_water": ("S1_AND_S2", "optimizer annual usable-water budget"),
            "monthly_supply": ("S1_AND_S2", "verified monthly supply validation"),
            "delivery": ("S1_AND_S2", "verified monthly delivery validation"),
            "environmental_release": ("S1_AND_S2", "single-deduction usable-water calculation"),
            "conveyance": ("S1_AND_S2", "gross crop-water demand calculation"),
            "perennial_requirement": ("S2", "S2 perennial exact/default water override"),
            "economics": ("S1_AND_S2", "candidate/seasonal optimizer profit"),
            "crop_parameters": ("S1_AND_S2", "verified FAO56 project water calculator"),
            "phenology": ("S1_AND_S2", "verified monthly crop-water calendar"),
            "candidates": ("S1_AND_S2", "optimizer candidate matrix"),
            "current_pattern": ("S1_AND_S2", "unit baseline and perennial locks"),
        }
        domains = {name: {"status": "NOT_READY", "engine_connected": True,
                          "connection_state": "CONNECTED", "execution_scope": scope,
                          "consumer": consumer, "blocking_reason": message}
                   for name, (scope, consumer) in consumers.items()}
        if "NOT_EXECUTABLE_WITH_CURRENT_MODE" in message:
            domains["environmental_release"].update(engine_connected=False,
                connection_state="NOT_EXECUTABLE_WITH_CURRENT_MODE")
        return {"ready": False, "blocking_reasons": [message], "warnings": [], "domains": domains}


def _phenology_dates(record: dict[str, Any], year: int) -> tuple[str, str]:
    if record["mode"] == "YEAR_SPECIFIC":
        return record["planting_date"], record["harvest_date"]
    planting = record["planting_window_start"]
    harvest = record["harvest_window_start"]
    planting_year = year - 1 if record.get("season_year_semantics") == "CROSSES_CALENDAR_YEAR" else year
    return f"{planting_year}-{planting}", f"{year}-{harvest}"


def materialize_verified_document(document: dict[str, Any], configuration: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Return a copied engine document, adjusted config, and immutable input plan."""
    plan = verified_execution_plan(document, configuration)
    water = resolve_verified_water(document)
    economics = resolve_verified_economics(document, configuration["scenario"])
    parameters = _resolve_crop_contract(document, "crop_water_parameters")
    phenology = _resolve_crop_contract(document, "crop_phenology")
    if water.environmental_release["form"] != "ratio":
        raise ValueError("Physical environmental release is preserved by contract but is not executable in this phase.")
    ratios = set(float(value) for value in water.environmental_release["values"].values())
    if len(ratios) != 1:
        raise ValueError("Verified execution requires one annual environmental release ratio.")
    release_ratio = next(iter(ratios))
    usable_annual = water.annual_supply_m3 * (1.0 - release_ratio)
    result = deepcopy(document)
    result["water_budget"] = {"project_id": document["project"]["id"], "amount": usable_annual,
                              "unit": "m3", "kind": "verified_institutional",
                              "source": ",".join(d["dataset_id"] for d in water.datasets)}
    by_crop = {r["runtime_crop_id"]: r for r in parameters["records"]}
    import app
    for crop in result["crops"]:
        row = by_crop[app.canonical_crop_key(crop["name"])]
        crop.update(kc_initial=row["kc_ini"], kc_mid=row["kc_mid"], kc_end=row["kc_end"])
        if row["stage_value_mode"] == "DAYS":
            crop.update(stage_initial_days=row["p_ini"], stage_development_days=row["p_dev"],
                        stage_mid_days=row["p_mid"], stage_late_days=row["p_late"])
    profits = economics.crop_net_profit_tl_da
    for row in result.get("economics", []):
        if row.get("crop_name") in profits and row.get("year") == water.planning_year:
            row["net_profit_per_da"] = profits[row["crop_name"]]
    extra = result["scientific_inputs"]
    climate_rows = extra.get("seasonal_resources", {}).get("monthly_climate", [])
    climate_by_unit: dict[str, list[dict[str, Any]]] = {}
    for row in climate_rows:
        climate_by_unit.setdefault(str(row["parcel_id"]), []).append(row)
    if set(climate_by_unit) != {str(u["external_id"]) for u in result["analysis_units"]}:
        raise ValueError("Verified crop-water execution requires project monthly climate for every analysis unit.")
    phenology_rows = {(r["runtime_crop_id"], r["season"]): r for r in phenology["records"]}
    profiles: dict[tuple[str, str, str], dict[str, float]] = {}
    def profile(unit_id: str, crop: str, season: str) -> dict[str, float]:
        key = (unit_id, crop, season)
        if key not in profiles:
            crop_id = app.canonical_crop_key(crop)
            if (crop_id, season) not in phenology_rows:
                raise ValueError(f"Verified phenology is missing {season} for {crop}.")
            profiles[key] = monthly_gross_demand_m3_da(
                by_crop[crop_id], phenology_rows[(crop_id, season)], climate_by_unit[unit_id],
                water.conveyance_efficiency, water.planning_year)
        return profiles[key]
    for candidate in extra["candidates"]:
        candidate["profit_per_da"] = profits[candidate["crop"]]
        monthly_profile = profile(str(candidate["analysis_unit_id"]), candidate["crop"], "PRIMARY")
        candidate["water_requirement_m3_da"] = sum(monthly_profile.values())
    units = {u["external_id"]: u for u in result["analysis_units"]}
    for uid, params in extra["unit_parameters"].items():
        params["current_profit"] = economics.analysis_unit_profit_tl.get(
            uid, profits[units[uid]["current_crop"]] * float(units[uid]["area_da"]))
    for info in extra["irrigation"].values():
        info["efficiency"] = water.conveyance_efficiency
    env = extra.setdefault("seasonal_resources", {})
    env["reservoir"] = [{"month": month + "-01", "irrigation_m3_baseline": value * (1.0 - release_ratio)}
                        for month, value in sorted(water.monthly_supply_m3.items())]
    env["delivery"] = [{"month": month + "-01", "max_delivery_m3_assumed": value}
                       for month, value in sorted(water.monthly_delivery_capacity_m3.items())]
    env["crop_params"] = [{"crop": c["name"], "kc_ini": c["kc_initial"],
                           "kc_mid": c["kc_mid"], "kc_end": c["kc_end"]} for c in result["crops"]]
    seasonal_profit = {(r.get("analysis_unit_id"), r["crop"], r["season"].lower()): r
                       for r in economics.seasonal_profit_tl_da}
    perennial = list(water.perennial_requirements)
    perennial_crops = {c["name"] for c in result["crops"] if c.get("perennial")}
    for row in env.get("s2", []):
        crop_id = app.canonical_crop_key(row["crop"])
        season_key = str(row["season"]).upper()
        planting, harvest = _phenology_dates(phenology_rows[(crop_id, season_key)], water.planning_year)
        row.update(planting_date=planting, harvest_date=harvest,
                   irrigation_efficiency=water.conveyance_efficiency)
        econ = seasonal_profit.get((row.get("parcel_id"), row["crop"], str(row["season"]).lower())) or seasonal_profit.get((None, row["crop"], str(row["season"]).lower()))
        row["profit_tl"] = float((econ or {}).get("net_profit_tl_da", profits[row["crop"]])) * float(row["area_da"])
        monthly_profile = profile(str(row["parcel_id"]), row["crop"], season_key)
        row["water_m3_calib_gross"] = sum(monthly_profile.values()) * float(row["area_da"])
        requirement = (select_perennial_requirement(perennial, row["crop"], row.get("parcel_id"))
                       if row["crop"] in perennial_crops else None)
        if requirement:
            row["water_m3_calib_gross"] = float(requirement["gross_irrigation_m3_da"]) * float(row["area_da"])
            # Preserve the verified temporal shape while honoring the exact annual floor.
            total = sum(monthly_profile.values())
            if total > 0:
                profiles[(str(row["parcel_id"]), row["crop"], season_key)] = {
                    month: value / total * float(requirement["gross_irrigation_m3_da"])
                    for month, value in monthly_profile.items()
                }
    env["verified_monthly_profiles"] = [
        {"analysis_unit_id": unit_id, "crop": crop, "season": season, "month": month,
         "gross_water_m3_da": value}
        for (unit_id, crop, season), values in sorted(profiles.items())
        for month, value in sorted(values.items())
    ]
    adjusted = deepcopy(configuration)
    # Supply values are already net of the verified release; the engine must not deduct it twice.
    adjusted["options"]["envFlowRatio"] = 0.0
    adjusted["options"]["waterModel"] = "verified_fao56_precomputed"
    plan["verified_water_model"] = "FAO56_PROJECT_INPUTS_PRECOMPUTED"
    plan["water_constraints"] = {
        "annual_supply_m3": water.annual_supply_m3,
        "monthly_supply_m3": water.monthly_supply_m3,
        "monthly_delivery_capacity_m3": water.monthly_delivery_capacity_m3,
        "environmental_release": water.environmental_release,
        "conveyance_efficiency": water.conveyance_efficiency,
    }
    return result, adjusted, plan


def build_verified_bundle(document: dict[str, Any], configuration: dict[str, Any]):
    from kds.adapters.project_science import build_bundle
    materialized, adjusted, plan = materialize_verified_document(document, configuration)
    bundle = build_bundle(materialized, adjusted)
    profiles_frame = dict(bundle.resources)["environment"].copy().get("verified_monthly_profiles")
    profiles = {}
    if profiles_frame is not None:
        for _, row in profiles_frame.iterrows():
            profiles.setdefault((str(row["analysis_unit_id"]), str(row["crop"]), str(row["season"])), {})[
                str(row["month"])] = float(row["gross_water_m3_da"])
    execution_context = {"monthly_profiles": profiles, **plan["water_constraints"]}
    return bundle, adjusted, plan, execution_context
