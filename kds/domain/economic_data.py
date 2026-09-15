"""Canonical, versioned economic-data contracts for future integration.

The active datasets defined here are intentionally disconnected from every
scientific optimizer.  They provide an auditable intake and replacement layer.
"""
from __future__ import annotations

import math
import re
from datetime import date
from enum import Enum
from typing import Any


class EconomicAuthorityClass(str, Enum):
    MEASURED_FARM_RECORD = "MEASURED_FARM_RECORD"
    OFFICIAL_STATISTICS = "OFFICIAL_STATISTICS"
    OFFICIAL_MARKET_RECORD = "OFFICIAL_MARKET_RECORD"
    LOCAL_INSTITUTIONAL_SOURCE = "LOCAL_INSTITUTIONAL_SOURCE"
    DOCUMENTED_COMMERCIAL_SOURCE = "DOCUMENTED_COMMERCIAL_SOURCE"
    CALCULATED_FROM_VERIFIED_INPUTS = "CALCULATED_FROM_VERIFIED_INPUTS"
    CALCULATED_REFERENCE = "CALCULATED_REFERENCE"
    DERIVED_PROXY = "DERIVED_PROXY"
    ASSUMED = "ASSUMED"
    FALLBACK = "FALLBACK"
    UNKNOWN = "UNKNOWN"


AUTHORITY_PRECEDENCE = {
    EconomicAuthorityClass.MEASURED_FARM_RECORD: 11,
    EconomicAuthorityClass.OFFICIAL_MARKET_RECORD: 10,
    EconomicAuthorityClass.LOCAL_INSTITUTIONAL_SOURCE: 9,
    EconomicAuthorityClass.OFFICIAL_STATISTICS: 8,
    EconomicAuthorityClass.DOCUMENTED_COMMERCIAL_SOURCE: 7,
    EconomicAuthorityClass.CALCULATED_FROM_VERIFIED_INPUTS: 6,
    EconomicAuthorityClass.CALCULATED_REFERENCE: 5,
    EconomicAuthorityClass.DERIVED_PROXY: 4,
    EconomicAuthorityClass.ASSUMED: 3,
    EconomicAuthorityClass.FALLBACK: 2,
    EconomicAuthorityClass.UNKNOWN: 1,
}

ECONOMIC_DATA_TYPES = {
    "crop_yield", "crop_sale_price", "crop_support_payment",
    "crop_cost_components", "crop_net_profit", "analysis_unit_economics",
    "seasonal_economics",
}

COST_CATEGORIES = {
    "seed", "fertilizer", "pesticide", "labor", "energy", "irrigation",
    "machinery", "harvest", "transport", "storage", "marketing", "rent", "other",
}

CALCULATION_METHODS = {
    "DIRECT_SOURCE", "GROSS_MINUS_TOTAL_COST",
    "GROSS_PLUS_SUPPORT_MINUS_TOTAL_COST", "OTHER_DOCUMENTED_METHOD",
}

VERIFIED_INPUT_AUTHORITIES = {
    EconomicAuthorityClass.MEASURED_FARM_RECORD,
    EconomicAuthorityClass.OFFICIAL_MARKET_RECORD,
    EconomicAuthorityClass.LOCAL_INSTITUTIONAL_SOURCE,
    EconomicAuthorityClass.OFFICIAL_STATISTICS,
    EconomicAuthorityClass.DOCUMENTED_COMMERCIAL_SOURCE,
    EconomicAuthorityClass.CALCULATED_FROM_VERIFIED_INPUTS,
}

PROFIT_DEPENDENCY_ROLES = {
    "yield_dataset_id": "crop_yield",
    "price_dataset_id": "crop_sale_price",
    "cost_dataset_id": "crop_cost_components",
    "support_dataset_id": "crop_support_payment",
}


def economic_authority(value: Any) -> EconomicAuthorityClass:
    text = str(value or "").strip().upper()
    if text == "SCENARIO":
        raise ValueError("SCENARIO is a modelling context, not an economic authority class.")
    try:
        return EconomicAuthorityClass(text)
    except ValueError as exc:
        raise ValueError("authority_class must use the canonical economic authority enum.") from exc


def authority_rank(value: Any) -> int:
    return AUTHORITY_PRECEDENCE[economic_authority(value)]


def finite(value: Any, field: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{field} must be finite.")
    number = float(value)
    if positive and number <= 0:
        raise ValueError(f"{field} must be greater than zero.")
    return number


def year(value: Any, field: str = "planning_year") -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer.") from exc
    if not number.is_integer() or not 1900 <= number <= 2200:
        raise ValueError(f"{field} must be an integer between 1900 and 2200.")
    return int(number)


def iso_date(value: Any, field: str = "price_date") -> str:
    text = str(value or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        raise ValueError(f"{field} must use ISO YYYY-MM-DD.")
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid ISO calendar date.") from exc
    return text


def normalize_unit(value: Any) -> str:
    text = str(value or "").strip().lower().replace("₺", "tl").replace(" ", "")
    aliases = {
        "kg/da": "kg/da", "ton/da": "ton/da", "t/da": "ton/da",
        "tl/kg": "TL/kg", "try/kg": "TL/kg", "tl/ton": "TL/ton", "try/ton": "TL/ton",
        "tl/da": "TL/da", "try/da": "TL/da", "tl": "TL", "try": "TL",
    }
    if text not in aliases:
        raise ValueError(f"Unsupported explicit economic unit: {value!r}.")
    return aliases[text]


def convert_yield(value: float, source_unit: Any) -> tuple[float, dict[str, Any] | None]:
    source = normalize_unit(source_unit)
    if source == "ton/da":
        return value, None
    if source == "kg/da":
        return value / 1000.0, {"source_unit": source, "canonical_unit": "ton/da", "conversion_method": "kg/da ÷ 1000"}
    raise ValueError("Yield unit must be kg/da or ton/da.")


def convert_price(value: float, source_unit: Any) -> tuple[float, dict[str, Any] | None]:
    source = normalize_unit(source_unit)
    if source == "TL/ton":
        return value, None
    if source == "TL/kg":
        return value * 1000.0, {"source_unit": source, "canonical_unit": "TL/ton", "conversion_method": "TL/kg × 1000"}
    raise ValueError("Sale price unit must be TL/kg or TL/ton; TL/da is never a sale-price unit.")


def dataset_authority(records: list[dict[str, Any]]) -> str:
    values = {r["authority_class"] for r in records}
    if len(values) != 1:
        raise ValueError("One imported economic dataset must have exactly one authority_class.")
    return next(iter(values))


def canonical_geographic_scope(value: Any) -> str:
    """Resolve absent economic geography to the contract's project default."""
    return str(value or "").strip() or "project"


def canonical_crop_scope(value: Any) -> str:
    """Resolve absent economic crop coverage to the contract's catalog default."""
    return str(value or "").strip() or "catalog"


def canonical_economic_scope(record: dict[str, Any]) -> tuple[str, str]:
    return (
        canonical_geographic_scope(record.get("geographic_scope")),
        canonical_crop_scope(record.get("crop_scope")),
    )


def scope_key(data_type: str, records: list[dict[str, Any]]) -> str:
    years = {r["planning_year"] for r in records}
    geographies = {canonical_economic_scope(r)[0] for r in records}
    crops = {canonical_economic_scope(r)[1] for r in records}
    if len(years) != 1 or len(geographies) != 1 or len(crops) != 1:
        raise ValueError("One dataset must use one planning year, geographic_scope and crop_scope.")
    return f"{data_type}|{next(iter(years))}|{next(iter(geographies))}|{next(iter(crops))}"


def active_dataset(document: dict[str, Any], data_type: str, records: list[dict[str, Any]]) -> dict[str, Any] | None:
    economics = document.get("economic_data", {})
    dataset_id = economics.get("active", {}).get(scope_key(data_type, records))
    return economics.get("datasets", {}).get(dataset_id) if dataset_id else None


def specificity(record: dict[str, Any]) -> dict[str, int]:
    return {
        "scope": 2 if record.get("analysis_unit_id") else 1 if record.get("crop") else 0,
        "time": 2 if record.get("price_date") else 1 if record.get("observation_year") else 0,
        "authority": authority_rank(record["authority_class"]),
    }


def _identity(data_type: str, record: dict[str, Any]) -> str:
    fields = {
        "crop_yield": ("crop",), "crop_sale_price": ("crop", "price_date", "price_period"),
        "crop_support_payment": ("crop", "support_type"),
        "crop_cost_components": ("crop", "cost_category"),
        "crop_net_profit": ("crop",),
        "analysis_unit_economics": ("analysis_unit_id", "crop"),
        "seasonal_economics": ("analysis_unit_id", "crop", "season"),
    }[data_type]
    return "|".join(str(record.get(f) or "*") for f in fields)


def _value(data_type: str, record: dict[str, Any]) -> float | None:
    field = {
        "crop_yield": "yield_ton_da", "crop_sale_price": "price_tl_ton",
        "crop_support_payment": "amount_tl_da", "crop_cost_components": "amount_tl_da",
        "crop_net_profit": "net_profit_per_da", "analysis_unit_economics": "net_profit_tl",
        "seasonal_economics": "net_profit_tl_da",
    }[data_type]
    value = record.get(field)
    return float(value) if value is not None else None


def replacement_preview(document: dict[str, Any], data_type: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    existing = active_dataset(document, data_type, records)
    old_records = existing.get("records", []) if existing else []
    old_values = {_identity(data_type, r): _value(data_type, r) for r in old_records}
    new_values = {_identity(data_type, r): _value(data_type, r) for r in records}
    keys = sorted(k for k in old_values.keys() | new_values.keys() if old_values.get(k) != new_values.get(k))
    changes = []
    for key in keys:
        old, new = old_values.get(key), new_values.get(key)
        difference = new - old if old is not None and new is not None else None
        changes.append({"identity": key, "old_value": old, "new_value": new,
                        "absolute_difference": difference,
                        "percentage_difference": difference / old * 100 if difference is not None and old else None})
    old_authority = existing.get("authority_class") if existing else None
    new_authority = dataset_authority(records)
    lower = bool(existing and authority_rank(new_authority) < authority_rank(old_authority))
    affected_crops = sorted({r.get("crop") for r in old_records + records if r.get("crop")})
    affected_units = sorted({r.get("analysis_unit_id") for r in old_records + records if r.get("analysis_unit_id")})
    return {
        "scope_key": scope_key(data_type, records), "existing_dataset_id": existing.get("dataset_id") if existing else None,
        "old_authority": old_authority, "new_authority": new_authority,
        "authority_change": "LOWER" if lower else "HIGHER" if existing and authority_rank(new_authority) > authority_rank(old_authority) else "SAME" if existing else "INITIAL",
        "year": records[0]["planning_year"], "unit": (
            records[0].get("canonical_unit")
            or records[0].get("canonical_units", {}).get("net_profit")
        ),
        "value_changes": changes[:100], "value_change_count": len(changes),
        "affected_crops": affected_crops, "affected_analysis_units": affected_units,
        "affected_scenarios": ["S1", "S2"], "requires_reanalysis": existing is not None,
        "requires_authority_override": lower,
        "same_authority_conflict": bool(existing and old_authority == new_authority),
        "activation_occurs_only_after_confirm": True, "engine_connected": False,
    }


def authority_snapshot(document: dict[str, Any]) -> dict[str, Any]:
    economics = document.get("economic_data", {})
    result = {}
    for key, dataset_id in economics.get("active", {}).items():
        dataset = economics.get("datasets", {}).get(dataset_id, {})
        result[key] = {"active_dataset_id": dataset_id, "authority_class": dataset.get("authority_class"),
                       "data_version": dataset.get("version"), "derivation_status": dataset.get("derivation_status"),
                       "source": dataset.get("source"), "engine_connected": False}
    return result


FUTURE_RESULT_PROVENANCE_FIELDS = (
    "economic_source_type", "economic_dataset_id", "economic_version", "fallback_used",
    "fallback_source", "raw_profit_per_da", "suitability_multiplier",
    "profit_realism_multiplier", "effective_profit_per_da", "transformations",
)


def calculate_profit_from_verified_inputs(yield_dataset: dict[str, Any], price_dataset: dict[str, Any],
                                          cost_dataset: dict[str, Any], support_dataset: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a derived value only from current, active and verified datasets."""
    roles = {
        "yield_dataset_id": (yield_dataset, "crop_yield"),
        "price_dataset_id": (price_dataset, "crop_sale_price"),
        "cost_dataset_id": (cost_dataset, "crop_cost_components"),
    }
    if support_dataset is not None:
        roles["support_dataset_id"] = (support_dataset, "crop_support_payment")
    for role, (source, expected_type) in roles.items():
        if source.get("data_type") != expected_type:
            raise ValueError(f"{role} must reference {expected_type}.")
        if not source.get("confirmed_at") or source.get("status") != "active":
            raise ValueError(f"{role} must reference a confirmed active dataset.")
        if source.get("derivation_status") != "CURRENT" or source.get("requires_recalculation") is True:
            raise ValueError(f"{role} must reference a current dataset that does not require recalculation.")
        if economic_authority(source.get("authority_class")) not in VERIFIED_INPUT_AUTHORITIES:
            raise ValueError(f"{role} authority is not verified input evidence.")
    sources = [source for source, _ in roles.values()]
    records = [source["records"] for source in sources]
    if len(records[0]) != 1 or len(records[1]) != 1 or (support_dataset and len(records[-1]) != 1) or not records[2]:
        raise ValueError("Yield, price and optional support require one record; cost requires at least one component.")
    rows = [records[0][0], records[1][0], *records[2], *([records[3][0]] if support_dataset else [])]
    crop_values = {row["crop"] for row in rows}
    years = {row["planning_year"] for row in rows}
    currencies = {row.get("currency", "TRY") for row in rows}
    if len(crop_values) != 1 or len(years) != 1 or currencies != {"TRY"}:
        raise ValueError("Yield, price, support and cost inputs must share crop, year and TRY currency.")
    scopes = {canonical_economic_scope(row) for row in rows}
    if len(scopes) != 1:
        raise ValueError("Yield, price, support and cost inputs must use the same geographic_scope and crop_scope.")
    geographic_scope, crop_scope = next(iter(scopes))
    yield_row, price_row = records[0][0], records[1][0]
    gross = float(yield_row["yield_ton_da"]) * float(price_row["price_tl_ton"])
    support = float(records[3][0]["amount_tl_da"]) if support_dataset else 0.0
    total_cost = sum(float(r["amount_tl_da"]) for r in cost_dataset["records"])
    method = "GROSS_PLUS_SUPPORT_MINUS_TOTAL_COST" if support_dataset else "GROSS_MINUS_TOTAL_COST"
    result = {
        "crop": yield_row["crop"], "planning_year": yield_row["planning_year"],
        "geographic_scope": geographic_scope, "crop_scope": crop_scope,
        "gross_revenue_per_da": gross, "support_payment_per_da": support,
        "total_cost_per_da": total_cost, "net_profit_per_da": gross + support - total_cost,
        "currency": "TRY", "canonical_unit": "TL/da", "calculation_method": method,
        "calculation_formula": "yield_ton_da × price_tl_ton + support_payment_per_da - total_cost_per_da",
        "dependency_dataset_ids": [source["dataset_id"] for source in sources],
        "authority_class": EconomicAuthorityClass.CALCULATED_FROM_VERIFIED_INPUTS.value,
        "engine_connected": False,
    }
    result.update({role: source["dataset_id"] for role, (source, _) in roles.items()})
    return result
