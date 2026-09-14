"""Canonical authority and versioned water-data contracts.

These contracts describe future project inputs. They are deliberately not
consumed by the scientific optimization engine in this milestone.
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime
from enum import Enum
from typing import Any


class AuthorityClass(str, Enum):
    MEASURED = "MEASURED"
    OFFICIAL_ALLOCATION = "OFFICIAL_ALLOCATION"
    OFFICIAL_HISTORICAL = "OFFICIAL_HISTORICAL"
    CALCULATED_REFERENCE = "CALCULATED_REFERENCE"
    DERIVED_PROXY = "DERIVED_PROXY"
    SCENARIO = "SCENARIO"
    ASSUMED = "ASSUMED"
    UNKNOWN = "UNKNOWN"


AUTHORITY_PRECEDENCE = {
    AuthorityClass.MEASURED: 7,
    AuthorityClass.OFFICIAL_ALLOCATION: 6,
    AuthorityClass.OFFICIAL_HISTORICAL: 5,
    AuthorityClass.CALCULATED_REFERENCE: 4,
    AuthorityClass.DERIVED_PROXY: 3,
    AuthorityClass.ASSUMED: 2,
    AuthorityClass.UNKNOWN: 1,
}

WATER_DATA_TYPES = {
    "annual_water_supply",
    "monthly_water_supply",
    "delivery_capacity",
    "environmental_release",
    "conveyance_efficiency",
    "perennial_irrigation_requirement",
}


def authority(value: Any) -> AuthorityClass:
    try:
        return AuthorityClass(str(value or "").strip().upper())
    except ValueError as exc:
        raise ValueError("authority_class must use the canonical AuthorityClass enum.") from exc


def authority_rank(value: Any) -> int | None:
    parsed = authority(value)
    return None if parsed is AuthorityClass.SCENARIO else AUTHORITY_PRECEDENCE[parsed]


def finite(value: Any, field: str, *, positive: bool = False, allow_zero: bool = True) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{field} must be finite.")
    number = float(value)
    if positive and number <= 0:
        raise ValueError(f"{field} must be greater than zero.")
    if not allow_zero and number <= 0:
        raise ValueError(f"{field} must be greater than zero.")
    if allow_zero and number < 0:
        raise ValueError(f"{field} must be zero or greater.")
    return number


def planning_year(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("planning_year must be an integer.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("planning_year must be an integer.") from exc
    if not number.is_integer() or not 1900 <= number <= 2200:
        raise ValueError("planning_year must be an integer between 1900 and 2200.")
    return int(number)


def calendar_month(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m")
    text = str(value or "").strip()
    match = re.fullmatch(r"(\d{4})-(\d{2})(?:-(\d{2}))?", text)
    if not match:
        raise ValueError("month must be YYYY-MM or an ISO date.")
    year_value, month_value = int(match.group(1)), int(match.group(2))
    if not 1900 <= year_value <= 2200 or not 1 <= month_value <= 12:
        raise ValueError("month is outside the supported calendar range.")
    if match.group(3):
        try:
            date(year_value, month_value, int(match.group(3)))
        except ValueError as exc:
            raise ValueError("month contains an invalid ISO date.") from exc
    return f"{year_value:04d}-{month_value:02d}"


def normalize_unit(value: Any) -> str:
    text = str(value or "").strip().lower().replace("³", "3").replace(" ", "")
    aliases = {
        "m3": "m3", "m3/year": "m3/year", "m3/yil": "m3/year",
        "m3/month": "m3/month", "m3/ay": "m3/month", "m3/s": "m3/s",
        "hm3": "hm3", "hm3/year": "hm3/year", "hm3/month": "hm3/month",
        "ratio": "ratio", "fraction": "ratio", "mm": "mm", "m3/da": "m3/da",
    }
    if text not in aliases:
        raise ValueError(f"Unsupported explicit unit: {value!r}.")
    return aliases[text]


def convert_volume(value: float, source_unit: str, canonical_unit: str, record: dict[str, Any]) -> tuple[float, dict[str, Any] | None]:
    source, target = normalize_unit(source_unit), normalize_unit(canonical_unit)
    if source == target:
        return value, None
    if source == "m3" and target in {"m3/year", "m3/month"}:
        return value, dict(source_unit=source, canonical_unit=target, conversion_method="volume unchanged; period supplied by contract")
    if source == "hm3" and target in {"m3/year", "m3/month"}:
        return value * 1_000_000.0, dict(source_unit=source, canonical_unit=target, conversion_method="hm3 × 1,000,000; period supplied by contract")
    if (source, target) in {("hm3", "m3"), ("hm3/year", "m3/year"), ("hm3/month", "m3/month")}:
        return value * 1_000_000.0, dict(source_unit=source, canonical_unit=target, conversion_method="hm3 × 1,000,000")
    if source == "m3/s" and target == "m3/month":
        hours = finite(record.get("operating_hours_per_day"), "operating_hours_per_day", positive=True)
        days = finite(record.get("operating_days_in_month"), "operating_days_in_month", positive=True)
        if hours > 24 or days > 31:
            raise ValueError("m3/s conversion requires operating hours <= 24 and operating days <= 31.")
        return value * 3600.0 * hours * days, dict(
            source_unit=source, canonical_unit=target,
            conversion_method="m3/s × 3600 × operating_hours_per_day × operating_days_in_month",
            operating_hours_per_day=hours, operating_days_in_month=days,
        )
    if source == "mm" and target == "m3/da":
        return value, dict(source_unit=source, canonical_unit=target, conversion_method="1 mm over 1 da = 1 m3/da")
    raise ValueError(f"No authorized conversion contract from {source} to {target}.")


def dataset_authority(records: list[dict[str, Any]]) -> str:
    values = {record["authority_class"] for record in records}
    if len(values) != 1:
        raise ValueError("One imported dataset must have exactly one authority_class.")
    return next(iter(values))


def active_dataset(document: dict[str, Any], data_type: str) -> dict[str, Any] | None:
    water = document.get("water_data", {})
    dataset_id = water.get("active", {}).get(data_type)
    return water.get("datasets", {}).get(dataset_id) if dataset_id else None


def dataset_total(data_type: str, records: list[dict[str, Any]]) -> float | None:
    field = {
        "annual_water_supply": "amount_m3",
        "monthly_water_supply": "amount_m3",
        "delivery_capacity": "capacity_m3",
    }.get(data_type)
    if field:
        return math.fsum(float(record[field]) for record in records)
    if data_type == "environmental_release" and records and records[0]["release_form"] == "monthly_release":
        return math.fsum(float(record["release_m3"]) for record in records)
    return None


def _preview_key(data_type: str, record: dict[str, Any]) -> str:
    if data_type == "annual_water_supply":
        return str(record["planning_year"])
    if data_type in {"monthly_water_supply", "delivery_capacity", "environmental_release"}:
        return str(record.get("month") or record["planning_year"])
    if data_type == "conveyance_efficiency":
        return f"{record['period']}:{record['scope']}"
    return ":".join(str(record.get(field) or "*") for field in ("crop", "analysis_unit_id", "month"))


def _preview_value(data_type: str, record: dict[str, Any]) -> float:
    field = {
        "annual_water_supply": "amount_m3",
        "monthly_water_supply": "amount_m3",
        "delivery_capacity": "capacity_m3",
        "conveyance_efficiency": "efficiency",
        "perennial_irrigation_requirement": "gross_irrigation_m3_da",
    }.get(data_type)
    if data_type == "environmental_release":
        field = "release_m3" if record["release_form"] == "monthly_release" else "ratio"
    return float(record[field])


def replacement_preview(document: dict[str, Any], data_type: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    existing = active_dataset(document, data_type)
    old_records = existing.get("records", []) if existing else []
    new_total, old_total = dataset_total(data_type, records), dataset_total(data_type, old_records)
    difference = new_total - old_total if new_total is not None and old_total is not None else None
    percent = difference / old_total * 100 if difference is not None and old_total else None
    old_authority = existing.get("authority_class") if existing else None
    new_authority = dataset_authority(records)
    old_rank = authority_rank(old_authority) if old_authority else None
    new_rank = authority_rank(new_authority)
    lower = existing is not None and (new_rank is None or (old_rank is not None and new_rank < old_rank))
    old_values = {_preview_key(data_type, record): _preview_value(data_type, record) for record in old_records}
    new_values = {_preview_key(data_type, record): _preview_value(data_type, record) for record in records}
    changed_keys = sorted(key for key in old_values.keys() | new_values.keys() if old_values.get(key) != new_values.get(key))
    changes = [{
        "period_or_scope": key,
        "old_value": old_values.get(key),
        "new_value": new_values.get(key),
        "difference": (new_values[key] - old_values[key]) if key in old_values and key in new_values else None,
    } for key in changed_keys]
    months = [key for key in changed_keys if re.fullmatch(r"\d{4}-\d{2}", key)]
    return {
        "existing_dataset_id": existing.get("dataset_id") if existing else None,
        "old_authority": old_authority,
        "new_authority": new_authority,
        "authority_change": "SCENARIO_SPECIAL" if new_rank is None else "LOWER" if lower else "HIGHER" if old_rank is not None and new_rank > old_rank else "SAME" if existing else "INITIAL",
        "old_annual_total": old_total,
        "new_annual_total": new_total,
        "absolute_difference": difference,
        "percentage_difference": percent,
        "annual_total_unit": "m3/year" if new_total is not None else None,
        "affected_months": months,
        "value_changes": changes[:100],
        "value_change_count": len(changes),
        "value_changes_truncated": len(changes) > 100,
        "affected_scenarios": ["S1", "S2"],
        "requires_reanalysis": existing is not None,
        "will_deactivate_existing": existing is not None,
        "will_deactivate_proxy": bool(existing and old_authority in {"DERIVED_PROXY", "ASSUMED", "UNKNOWN"}),
        "requires_authority_override": lower,
        "same_authority_conflict": bool(existing and old_authority == new_authority),
        "activation_occurs_only_after_confirm": True,
    }


def authority_snapshot(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Expose active authority without changing readiness or engine inputs."""
    budget_kind = str(document.get("water_budget", {}).get("kind") or "unknown").upper()
    budget_authority = budget_kind if budget_kind in {member.value for member in AuthorityClass} else "UNKNOWN"
    extra = document.get("scientific_inputs", {}).get("seasonal_resources", {})
    legacy = {
        "annual_water_supply": budget_authority,
        "monthly_water_supply": "UNKNOWN",
        "delivery_capacity": "DERIVED_PROXY" if extra.get("delivery") else "UNKNOWN",
        "environmental_release": "ASSUMED",
        "conveyance_efficiency": "UNKNOWN",
        "perennial_irrigation_requirement": "SCENARIO" if extra.get("s2") else "UNKNOWN",
    }
    snapshot = {}
    for data_type, fallback in legacy.items():
        dataset = active_dataset(document, data_type)
        snapshot[data_type] = {
            "active_dataset_id": dataset.get("dataset_id") if dataset else None,
            "authority_class": dataset.get("authority_class") if dataset else fallback,
            "data_version": dataset.get("version") if dataset else None,
            "source": dataset.get("source") if dataset else {"legacy_or_default": True},
            "confirmed_at": dataset.get("confirmed_at") if dataset else None,
            "engine_connected": False,
        }
    return snapshot


def resolve_perennial_requirement(records: list[dict[str, Any]], crop: str,
                                   analysis_unit_id: str | None = None,
                                   month: str | None = None) -> dict[str, Any] | None:
    """Resolve without inventing monthly values: unit scope, then crop scope."""
    target_month = calendar_month(month) if month else None
    candidates = [
        record for record in records
        if str(record.get("crop", "")).casefold() == str(crop).casefold()
        and record.get("analysis_unit_id") in {None, analysis_unit_id}
        and record.get("month") in {None, target_month}
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda record: (
        1 if analysis_unit_id and record.get("analysis_unit_id") == analysis_unit_id else 0,
        1 if target_month and record.get("month") == target_month else 0,
    ))
