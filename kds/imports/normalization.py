"""Pure row conversion, used both by preview validation and confirmed writes."""
import json
import re
from dataclasses import asdict
from hashlib import sha256
from typing import Any
from kds.domain.analysis_unit import AnalysisUnit
from kds.domain.crop import Crop
from kds.domain.economics import Economics
from kds.domain.validation import ValidationError, number
from .mapping import key


def numeric(value: Any, field: str, options: dict[str, Any], optional: bool = False) -> float | None:
    if value in (None, ""):
        if optional:
            return None
        raise ValidationError(field, "Numeric value is required.")
    if isinstance(value, (int, float)):
        return number(value, field)
    text = str(value).strip()
    separator = options.get("decimal_separator", ".")
    if separator not in {".", ","}:
        raise ValidationError(field, "decimal_separator must be '.' or ','.")
    if separator == ",":
        if "." in text:
            if not re.fullmatch(r"[+-]?\d{1,3}(\.\d{3})+(,\d+)?", text):
                raise ValidationError(field, "Invalid Turkish number grouping.")
            text = text.replace(".", "")
        text = text.replace(",", ".")
    try:
        result = float(text)
    except ValueError as exc:
        raise ValidationError(field, "Malformed number; specify decimal_separator for comma decimals.") from exc
    return number(result, field)


def boolean(value: Any, field: str, default: bool | None = None) -> bool | None:
    if value in (None, ""):
        return default
    normalized = key(str(value))
    if normalized in {"true", "evet", "yes", "1"}:
        return True
    if normalized in {"false", "hayir", "no", "0"}:
        return False
    raise ValidationError(field, "Expected true/false, yes/no or evet/hayır.")


def record_id(project_id: str, external_id: str) -> str:
    return "r-" + sha256(f"{project_id}:{external_id}".encode()).hexdigest()[:24]


def normalize(row: dict[str, Any], mapping: dict[str, str], data_type: str,
              project_id: str, options: dict[str, Any]) -> dict[str, Any]:
    values = row["values"]
    data = {field: values.get(column) for field, column in mapping.items()}
    def text(name: str) -> str:
        value = data.get(name)
        return "" if value is None else str(value).strip()
    def num(name: str, optional: bool = False) -> float | None:
        return numeric(data.get(name), name, options, optional)
    metadata = {"source_row": row["line"], "unmapped": {k: v for k, v in values.items() if k not in mapping.values()}}
    if data_type in {"analysis_units", "geometries"}:
        external = text("external_id")
        geometry = data.get("geometry")
        if isinstance(geometry, str):
            try:
                geometry = json.loads(geometry) if geometry.strip() else None
            except json.JSONDecodeError as exc:
                raise ValidationError("geometry", "Malformed geometry JSON.") from exc
        if data_type == "geometries":
            if not external:
                raise ValidationError("external_id", "External id is required.")
            return {"external_id": external, "geometry": geometry}
        metadata["notes"] = text("notes")
        return asdict(AnalysisUnit(record_id(project_id, external), project_id, external, num("area_da"), text("current_crop"),
                                  text("name_or_code"), text("settlement"), text("irrigation_method"),
                                  num("latitude", True), num("longitude", True), geometry, metadata))
    if data_type == "crops":
        kwargs = {name: num(name, True) for name in ("kc_initial", "kc_mid", "kc_end", "stage_initial_days", "stage_development_days", "stage_mid_days", "stage_late_days")}
        return asdict(Crop(id=record_id(project_id, key(text("crop_name"))), project_id=project_id, name=text("crop_name"),
                          crop_group=text("crop_group"), perennial=boolean(data.get("perennial"), "perennial"),
                          source=text("source"), confidence_level=text("confidence_level"),
                          active=boolean(data.get("active"), "active", True), metadata=metadata,
                          planting_date=text("planting_date") or None, harvest_date=text("harvest_date") or None, **kwargs))
    if data_type == "economics":
        year_value = num("year")
        if isinstance(year_value, float) and not year_value.is_integer():
            raise ValidationError("year", "Year must be an integer.")
        metadata["yield_unit"] = text("yield_unit") or None
        return asdict(Economics(project_id, text("crop_name"), int(year_value), num("yield_per_da"),
                                num("net_profit_per_da"), text("currency") or None, text("source"), metadata))
    raise ValueError("Unsupported import data type.")
