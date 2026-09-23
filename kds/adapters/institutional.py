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
    scopes = sorted({str(record.get("geographic_scope") or record.get("scope"))
                     for record in dataset.get("records", [])
                     if record.get("geographic_scope") or record.get("scope")})
    return {
        "dataset_id": dataset.get("dataset_id"), "data_type": dataset.get("data_type"),
        "version": dataset.get("version"), "authority_class": dataset.get("authority_class"),
        "confirmed_at": dataset.get("confirmed_at"), "source": deepcopy(dataset.get("source", {})),
        "scope_key": dataset.get("scope_key"),
        "geographic_scope": scopes[0] if len(scopes) == 1 else scopes,
        "conversion_provenance": conversions,
    }


def _active_water(document: dict[str, Any], data_type: str) -> dict[str, Any]:
    store = document.get("water_data", {})
    dataset_id = store.get("active", {}).get(data_type)
    dataset = store.get("datasets", {}).get(dataset_id)
    if not dataset:
        raise ValueError(f"VERIFIED_INSTITUTIONAL requires active {data_type}.")
    return dataset


def _selected_water_dataset(document: dict[str, Any], data_type: str) -> dict[str, Any] | None:
    """Return the pointer-selected resource without asserting that it is valid."""
    store = document.get("water_data", {})
    dataset_id = store.get("active", {}).get(data_type)
    return store.get("datasets", {}).get(dataset_id)


def _selected_economic_datasets(
        document: dict[str, Any], scenario: str,
) -> tuple[list[dict[str, Any]], bool, str | None]:
    """Snapshot active pointers before strict economic validation."""
    store = document.get("economic_data", {})
    active = store.get("active", {})
    datasets_store = store.get("datasets", {})
    selected: list[dict[str, Any]] = []
    selected_types: set[str] = set()
    seen: set[str] = set()
    for data_type in ECONOMIC_TYPES:
        dataset_ids = [dataset_id for key, dataset_id in active.items()
                       if key.startswith(data_type + "|")]
        datasets = [datasets_store[dataset_id] for dataset_id in dataset_ids
                    if dataset_id in datasets_store]
        if datasets:
            selected_types.add(data_type)
        for dataset in datasets:
            identity = str(dataset.get("dataset_id") or id(dataset))
            if identity not in seen:
                selected.append(dataset)
                seen.add(identity)
    required_types = {"crop_net_profit"}
    if scenario == "S2":
        required_types.add("seasonal_economics")
    required_selected = required_types <= selected_types
    if not required_selected:
        return selected, False, "MISSING_DATASET"
    year = int(document["project"]["planning_year"])
    required_scope = (document.get("project", {}).get("pilot_geographic_scope") or
                      document.get("metadata", {}).get("pilot_geographic_scope") or "project")
    for data_type in required_types:
        keys = [key for key, dataset_id in active.items()
                if key.startswith(data_type + "|") and dataset_id in datasets_store]
        if not any(key.startswith(f"{data_type}|{year}|") for key in keys):
            return selected, True, "INVALID_YEAR"
        if f"{data_type}|{year}|{required_scope}|catalog" not in keys:
            return selected, True, "INVALID_SCOPE"
    return selected, True, None


def _selected_crop_contract_datasets(document: dict[str, Any], data_type: str) -> list[dict[str, Any]]:
    """Return resources named by active contract pointers, regardless of validity."""
    store = document.get("crop_parameter_data", {})
    dataset_ids = [dataset_id for key, dataset_id in store.get("active", {}).items()
                   if key.startswith(data_type + "|")]
    return [store["datasets"][dataset_id] for dataset_id in dataset_ids
            if dataset_id in store.get("datasets", {})]


def _invalid_connection_state(reason: str, selected: bool) -> str:
    """Classify a strict resolver error without inventing unsupported precision."""
    if not selected:
        return "MISSING_DATASET"
    normalized = reason.casefold()
    if "stale" in normalized or "requires recalculation" in normalized:
        return "STALE"
    if "geographic scope" in normalized or "configured_scope" in normalized or "scope" in normalized:
        return "INVALID_SCOPE"
    if "planning year" in normalized or "planning_year" in normalized:
        return "INVALID_YEAR"
    if "authority" in normalized or "synthetic" in normalized:
        return "INVALID_AUTHORITY"
    if "ambiguous" in normalized:
        return "AMBIGUOUS_OR_INCOMPLETE"
    if "coverage" in normalized or "no records" in normalized or "all planning-year months" in normalized:
        return "INCOMPLETE_COVERAGE"
    return "INVALID"


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
        scope = record.get("geographic_scope") or record.get("scope")
        if not scope:
            raise ValueError(f"{dataset.get('data_type')} requires explicit geographic scope for verified execution.")
        if scope != required_scope:
            raise ValueError(f"{dataset.get('data_type')} does not match geographic scope {required_scope}.")


def _synthetic_project(document: dict[str, Any]) -> bool:
    metadata = document.get("metadata", {})
    return bool(metadata.get("synthetic_institutional_test") and metadata.get("not_official"))


def resolve_verified_water(document: dict[str, Any], *, require_perennial: bool = True) -> VerifiedWaterContext:
    year = int(document["project"]["planning_year"])
    synthetic = _synthetic_project(document)
    required_scope = (document.get("project", {}).get("pilot_geographic_scope") or
                      document.get("metadata", {}).get("pilot_geographic_scope") or "project")
    selected = {}
    required_water_types = tuple(t for t in WATER_TYPES
                                 if require_perennial or t != "perennial_irrigation_requirement")
    for data_type in required_water_types:
        dataset = _active_water(document, data_type)
        _validate_dataset(dataset, year, synthetic_allowed=synthetic,
                          authorities=VERIFIED_WATER_AUTHORITIES, required_scope=required_scope)
        selected[data_type] = dataset
    monthly = selected["monthly_water_supply"]["records"]
    delivery = selected["delivery_capacity"]["records"]
    if len(monthly) < 12 or len(delivery) < 12:
        raise ValueError("Verified monthly supply and delivery capacity require all planning-year months.")
    if {row["month"] for row in monthly} != {row["month"] for row in delivery}:
        raise ValueError("Verified monthly supply and delivery coverage must use identical YYYY-MM periods.")
    annual_amount = float(selected["annual_water_supply"]["records"][0]["amount_m3"])
    # The annual allocation is a planning-calendar-year quantity. Extra preceding-year
    # rows provide exact coverage for cross-year crop seasons and are reconciled only
    # to their matching monthly validation periods, not to the planning-year annual total.
    monthly_total = sum(float(row["amount_m3"]) for row in monthly
                        if str(row["month"]).startswith(f"{year}-"))
    tolerance = max(1.0, annual_amount * 0.001)
    if abs(monthly_total - annual_amount) > tolerance:
        raise ValueError(
            f"Annual/monthly water supply mismatch: annual={annual_amount}, "
            f"monthly_total={monthly_total}, tolerance={tolerance} m3.")
    releases = selected["environmental_release"]["records"]
    efficiencies = selected["conveyance_efficiency"]["records"]
    if len(efficiencies) != 1:
        raise ValueError("Verified execution requires one unambiguous conveyance efficiency record.")
    release = ({"form": "ratio", "values": {r.get("month") or str(year): r["ratio"] for r in releases}}
               if releases[0]["release_form"] == "ratio" else
               {"form": "monthly_release", "values": {r["month"]: r["release_m3"] for r in releases}})
    return VerifiedWaterContext(
        planning_year=year,
        annual_supply_m3=annual_amount,
        monthly_supply_m3={r["month"]: float(r["amount_m3"]) for r in monthly},
        monthly_delivery_capacity_m3={r["month"]: float(r["capacity_m3"]) for r in delivery},
        environmental_release=release,
        conveyance_efficiency=float(efficiencies[0]["efficiency"]),
        perennial_requirements=tuple(deepcopy(selected.get("perennial_irrigation_requirement", {}).get("records", []))),
        datasets=tuple(_dataset_fact(selected[k]) for k in required_water_types),
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
    water = resolve_verified_water(document, require_perennial=configuration["scenario"] == "S2")
    economics = resolve_verified_economics(document, configuration["scenario"])
    parameters = _resolve_crop_contract(document, "crop_water_parameters")
    phenology = _resolve_crop_contract(document, "crop_phenology")
    candidates = _candidate_snapshot(document, configuration["scenario"])
    if water.environmental_release["form"] != "ratio":
        raise ValueError("Physical environmental release is contract-valid but NOT_EXECUTABLE_WITH_CURRENT_MODE.")
    if len(set(float(value) for value in water.environmental_release["values"].values())) != 1:
        raise ValueError("Verified execution requires one annual environmental release ratio.")
    climate = document.get("scientific_inputs", {}).get("seasonal_resources", {}).get("monthly_climate", [])
    required_scope = (document.get("project", {}).get("pilot_geographic_scope") or
                      document.get("metadata", {}).get("pilot_geographic_scope") or "project")
    climate_periods: dict[str, set[str]] = {}
    modes = {str(row.get("climate_mode") or "") for row in climate}
    if modes not in ({"YEAR_SPECIFIC"}, {"CLIMATOLOGICAL_NORMAL"}):
        raise ValueError("Verified climate requires one explicit YEAR_SPECIFIC or CLIMATOLOGICAL_NORMAL mode.")
    if any(row.get("geographic_scope") != required_scope or not row.get("source") for row in climate):
        raise ValueError("Verified climate source/geographic scope is missing or does not match the project.")
    for row in climate:
        climate_periods.setdefault(str(row.get("parcel_id")), set()).add(str(row.get("month"))[:7])
    expected_units = {str(unit["external_id"]) for unit in document.get("analysis_units", [])}
    if set(climate_periods) != expected_units:
        raise ValueError("Verified crop-water execution requires project climate for every analysis unit.")
    mode = next(iter(modes))
    if mode == "CLIMATOLOGICAL_NORMAL":
        for unit_id, periods in climate_periods.items():
            months = {int(period[5:7]) for period in periods}
            if months != set(range(1, 13)):
                raise ValueError(f"Climatological climate requires months 1..12 for analysis unit {unit_id}.")
    else:
        required_periods: set[str] = set()
        for record in phenology["records"]:
            if configuration["scenario"] == "S1" and record["season"] != "PRIMARY":
                continue
            start_text, end_text = _phenology_dates(record, water.planning_year)
            cursor, end = date.fromisoformat(start_text), date.fromisoformat(end_text)
            while cursor <= end:
                required_periods.add(f"{cursor.year}-{cursor.month:02d}")
                cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
        for unit_id, periods in climate_periods.items():
            missing = sorted(required_periods - periods)
            if missing:
                raise ValueError(f"YEAR_SPECIFIC climate for {unit_id} is missing required calendar months: " + ", ".join(missing))
    climate_imports = _applied_imports(document, {"scientific_inputs"})
    climate_source = {
        "mode": mode, "geographic_scope": required_scope,
        "sources": sorted({str(row["source"]) for row in climate}),
        "coverage": sorted({str(row["month"])[:7] for row in climate}),
        "imports": climate_imports,
    }
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
        "current_pattern_source": candidates["current_pattern_source"], "climate_source": climate_source,
        "environmental_release_form": water.environmental_release["form"],
        "conveyance_efficiency": water.conveyance_efficiency, "geographic_scope": required_scope,
        "algorithm": configuration["algorithm"],
        "objective": configuration["objective"], "scenario": configuration["scenario"],
        "consumer_roles": {
            "annual_water": "OPTIMIZER_INPUT", "monthly_supply": "POST_RUN_VALIDATION",
            "delivery": "POST_RUN_VALIDATION", "environmental_release": "OPTIMIZER_INPUT",
            "conveyance": "OPTIMIZER_INPUT", "economics": "OPTIMIZER_INPUT",
            "crop_parameters": "OPTIMIZER_INPUT", "phenology": "OPTIMIZER_INPUT",
            "perennial_requirement": "OPTIMIZER_INPUT" if configuration["scenario"] == "S2" else "NOT_CONNECTED",
            "approximate_s2_monthly_optimizer": ("OPTIMIZER_CONSTRAINT"
                                                   if configuration["scenario"] == "S2" else "NOT_CONNECTED"),
        },
        "synthetic": synthetic, "not_official": synthetic,
    }


def verified_readiness(document: dict[str, Any], scenario: str = "S1") -> dict[str, Any]:
    minimal = {"scenario": scenario, "algorithm": "GA", "objective": "water_saving"}
    year = int(document["project"]["planning_year"])
    synthetic = _synthetic_project(document)
    required_scope = (document.get("project", {}).get("pilot_geographic_scope") or
                      document.get("metadata", {}).get("pilot_geographic_scope") or "project")
    domains: dict[str, dict[str, Any]] = {}
    blockers: list[str] = []

    def state(*, status="READY", selected=True, valid=True, connected=True, connection="CONNECTED",
              role="OPTIMIZER_INPUT", scope="S1_AND_S2", consumer="", reason=None,
              consumer_available=True, **facts):
        dataset = facts.get("dataset")
        if isinstance(dataset, dict):
            for key in ("dataset_id", "version", "data_type", "authority_class", "confirmed_at",
                        "scope_key", "geographic_scope", "source"):
                facts.setdefault(key, deepcopy(dataset.get(key)))
        return {"status": status, "consumer_available": consumer_available,
                "dataset_selected": selected, "dataset_valid": valid if selected else False,
                "engine_connected": connected, "connection_state": connection,
                "consumer_role": role, "execution_scope": scope, "consumer": consumer,
                "blocking_reason": reason, "blocking_reasons": ([reason] if reason else []), **facts}

    water_specs = {
        "annual_water": ("annual_water_supply", "optimizer annual usable-water budget", "OPTIMIZER_INPUT", "S1_AND_S2"),
        "monthly_supply": ("monthly_water_supply", "exact verified monthly supply validation", "POST_RUN_VALIDATION", "S1_AND_S2"),
        "delivery": ("delivery_capacity", "exact verified monthly delivery validation", "POST_RUN_VALIDATION", "S1_AND_S2"),
        "environmental_release": ("environmental_release", "single-deduction usable-water calculation", "OPTIMIZER_INPUT", "S1_AND_S2"),
        "conveyance": ("conveyance_efficiency", "gross crop-water demand calculation", "OPTIMIZER_INPUT", "S1_AND_S2"),
        "perennial_requirement": ("perennial_irrigation_requirement", "S2 perennial exact/default water override", "OPTIMIZER_INPUT", "S2"),
    }
    for name, (data_type, consumer, role, scope) in water_specs.items():
        required = name != "perennial_requirement" or scenario == "S2"
        dataset = _selected_water_dataset(document, data_type)
        selected = dataset is not None
        dataset_facts = ({"dataset": _dataset_fact(dataset)} if dataset else {})
        try:
            if dataset is None:
                raise ValueError(f"VERIFIED_INSTITUTIONAL requires active {data_type}.")
            _validate_dataset(dataset, year, synthetic_allowed=synthetic,
                              authorities=VERIFIED_WATER_AUTHORITIES, required_scope=required_scope)
            if not required:
                domains[name] = state(status="NOT_REQUIRED_FOR_SCENARIO", selected=True, valid=True, connected=False,
                                      connection="NOT_REQUIRED_FOR_SCENARIO", role="NOT_CONNECTED",
                                      scope=scope, consumer=consumer, **dataset_facts)
            elif name == "environmental_release" and dataset["records"][0]["release_form"] != "ratio":
                reason = "Physical environmental release is contract-valid but NOT_EXECUTABLE_WITH_CURRENT_MODE."
                domains[name] = state(status="NOT_READY", selected=True, valid=True, connected=False,
                                      connection="NOT_EXECUTABLE_WITH_CURRENT_MODE", role=role, scope=scope,
                                      consumer=consumer, reason=reason, **dataset_facts)
                blockers.append(reason)
            else:
                domains[name] = state(role=role, scope=scope, consumer=consumer,
                                      **dataset_facts)
        except ValueError as exc:
            reason = str(exc)
            if not required:
                domains[name] = state(status="NOT_REQUIRED_FOR_SCENARIO", selected=selected, valid=False,
                                      connected=False,
                                      connection="NOT_REQUIRED_FOR_SCENARIO", role="NOT_CONNECTED",
                                      scope=scope, consumer=consumer, reason=reason, **dataset_facts)
            else:
                blockers.append(reason)
                domains[name] = state(status="NOT_READY", selected=selected, valid=False, connected=False,
                                      connection=_invalid_connection_state(reason, selected),
                                      role=role, scope=scope, consumer=consumer, reason=reason, **dataset_facts)

    economics = None
    selected_economics, required_economics_selected, economics_selection_issue = (
        _selected_economic_datasets(document, scenario))
    economics_facts = {"datasets": [_dataset_fact(dataset) for dataset in selected_economics]}
    try:
        economics = resolve_verified_economics(document, scenario)
        domains["economics"] = state(consumer="candidate/seasonal optimizer profit",
                                      datasets=list(economics.datasets))
    except ValueError as exc:
        reason = str(exc); blockers.append(reason)
        domains["economics"] = state(status="NOT_READY", selected=required_economics_selected,
                                      valid=False, connected=False,
                                      connection=(economics_selection_issue or
                                                  _invalid_connection_state(reason, required_economics_selected)),
                                      consumer="candidate/seasonal optimizer profit", reason=reason,
                                      **economics_facts)

    resolved_contracts: dict[str, dict[str, Any]] = {}
    for name, data_type, consumer in (("crop_parameters", "crop_water_parameters", "verified FAO56 project water calculator"),
                                      ("phenology", "crop_phenology", "verified monthly crop-water calendar")):
        selected_contracts = _selected_crop_contract_datasets(document, data_type)
        contract_selected = bool(selected_contracts)
        contract_facts = {"datasets": [_dataset_fact(dataset) for dataset in selected_contracts]}
        if len(selected_contracts) == 1:
            contract_facts["dataset"] = contract_facts["datasets"][0]
        try:
            dataset = _resolve_crop_contract(document, data_type)
            if name == "phenology" and scenario == "S2":
                by_crop: dict[str, set[str]] = {}
                for record in dataset["records"]:
                    by_crop.setdefault(record["runtime_crop_id"], set()).add(record["season"])
                missing = sorted(crop for crop in by_crop if not {"PRIMARY", "SECONDARY"} <= by_crop[crop])
                if missing:
                    raise ValueError("S2 verified phenology requires PRIMARY and SECONDARY records for every runtime crop: " + ", ".join(missing))
            resolved_contracts[name] = dataset
            domains[name] = state(consumer=consumer, dataset=_dataset_fact(dataset))
        except ValueError as exc:
            reason = str(exc); blockers.append(reason)
            domains[name] = state(status="NOT_READY", selected=contract_selected, valid=False,
                                  connected=False, connection=_invalid_connection_state(reason, contract_selected),
                                  consumer=consumer, reason=reason, **contract_facts)

    extra = document.get("scientific_inputs", {})
    applied = _applied_imports(document, {"candidates", "scientific_inputs"})
    candidate_imports = [item for item in applied if item["data_type"] == "candidates"]
    current_imports = [item for item in applied if item["data_type"] == "scientific_inputs"]
    if extra.get("candidates") and candidate_imports:
        domains["candidates"] = state(consumer="optimizer candidate matrix",
            source="confirmed project import", candidate_count=len(extra["candidates"]), imports=candidate_imports)
    else:
        reason = "Verified candidate matrix requires data and applied import provenance."
        blockers.append(reason); domains["candidates"] = state(
            status="NOT_READY", selected=bool(extra.get("candidates")), valid=False, connected=False,
            connection="INVALID_OR_UNAVAILABLE", consumer="optimizer candidate matrix", reason=reason)
    current_valid = bool(extra.get("unit_parameters") and current_imports and
                         (scenario != "S2" or extra.get("seasonal_resources", {}).get("s2")))
    if current_valid:
        latest = max(current_imports, key=lambda item: item.get("applied_revision") or 0)
        domains["current_pattern"] = state(consumer="unit baseline and perennial locks",
            source="confirmed project scientific_inputs import", import_batch_id=latest["import_batch_id"],
            file_hash=latest["file_hash"], applied_revision=latest.get("applied_revision"),
            analysis_unit_count=len(extra["unit_parameters"]))
    else:
        reason = "Verified current pattern requires unit parameters, scenario resources, and applied import provenance."
        blockers.append(reason); domains["current_pattern"] = state(
            status="NOT_READY", selected=bool(extra.get("unit_parameters")), valid=False, connected=False,
            connection="INVALID_OR_UNAVAILABLE", consumer="unit baseline and perennial locks", reason=reason)

    climate_consumer = "verified FAO56 project climate"
    try:
        climate = document.get("scientific_inputs", {}).get("seasonal_resources", {}).get("monthly_climate", [])
        if not climate:
            raise ValueError("VERIFIED_INSTITUTIONAL requires project monthly climate.")
        modes = {str(row.get("climate_mode") or "") for row in climate}
        if modes not in ({"YEAR_SPECIFIC"}, {"CLIMATOLOGICAL_NORMAL"}):
            raise ValueError("Verified climate requires one explicit YEAR_SPECIFIC or CLIMATOLOGICAL_NORMAL mode.")
        if any(row.get("geographic_scope") != required_scope or not row.get("source") for row in climate):
            raise ValueError("Verified climate source/geographic scope is missing or does not match the project.")
        periods: dict[str, set[str]] = {}
        for row in climate:
            periods.setdefault(str(row.get("parcel_id")), set()).add(str(row.get("month"))[:7])
        units = {str(unit["external_id"]) for unit in document.get("analysis_units", [])}
        if set(periods) != units:
            raise ValueError("Verified crop-water execution requires project climate for every analysis unit.")
        mode = next(iter(modes))
        if mode == "CLIMATOLOGICAL_NORMAL":
            if any({int(p[5:7]) for p in values} != set(range(1, 13)) for values in periods.values()):
                raise ValueError("Climatological climate requires months 1..12 for every analysis unit.")
        else:
            phenology = resolved_contracts.get("phenology")
            if phenology is None:
                raise ValueError("YEAR_SPECIFIC climate coverage cannot be connected without valid phenology.")
            required_periods: set[str] = set()
            for record in phenology["records"]:
                if scenario == "S1" and record["season"] != "PRIMARY": continue
                start_text, end_text = _phenology_dates(record, year)
                cursor, end = date.fromisoformat(start_text), date.fromisoformat(end_text)
                while cursor <= end:
                    required_periods.add(f"{cursor.year}-{cursor.month:02d}")
                    cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
            missing = sorted((unit, period) for unit, values in periods.items()
                             for period in required_periods - values)
            if missing:
                raise ValueError("YEAR_SPECIFIC climate is missing required calendar months: " +
                                 ", ".join(f"{unit}/{period}" for unit, period in missing[:12]))
        facts = {"mode": mode, "source": sorted({str(r["source"]) for r in climate}),
                 "geographic_scope": required_scope,
                 "coverage": sorted({str(r["month"])[:7] for r in climate}),
                 "imports": _applied_imports(document, {"scientific_inputs"})}
        domains["climate"] = state(consumer=climate_consumer, **facts)
    except ValueError as exc:
        reason = str(exc); blockers.append(reason)
        selected = bool(document.get("scientific_inputs", {}).get("seasonal_resources", {}).get("monthly_climate"))
        domains["climate"] = state(status="NOT_READY", selected=selected, valid=False, connected=False,
                                    connection=_invalid_connection_state(reason, selected),
                                    consumer=climate_consumer, reason=reason)

    # Cross-domain water reconciliation remains fail-closed without falsifying other domains.
    if all(domains[name]["status"] == "READY" for name in
           ("annual_water", "monthly_supply", "delivery", "environmental_release", "conveyance")):
        try:
            resolve_verified_water(document, require_perennial=scenario == "S2")
        except ValueError as exc:
            reason = str(exc); blockers.append(reason)
            affected = ("annual_water", "monthly_supply") if "Annual/monthly" in reason else ("annual_water",)
            for name in affected:
                domains[name].update(status="NOT_READY", engine_connected=False,
                                     connection_state="INCONSISTENT", blocking_reason=reason,
                                     blocking_reasons=[reason])

    ready = not blockers
    warnings = ["SYNTHETIC_INSTITUTIONAL_TEST_PROJECT; NOT_OFFICIAL"] if synthetic else []
    return {"ready": ready, "blocking_reasons": list(dict.fromkeys(blockers)),
            "warnings": warnings, "domains": domains}


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
    execution_context = {"monthly_profiles": profiles, "planning_year": plan["planning_year"],
                         **plan["water_constraints"]}
    return bundle, adjusted, plan, execution_context
