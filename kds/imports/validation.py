from dataclasses import asdict
import json
from typing import Any
from kds.data.import_models import Issue
from kds.domain.validation import ValidationError
from .mapping import REQUIRED, key
from .normalization import normalize
from .geometry import geometry_error
from kds.domain.water_data import WATER_DATA_TYPES
from kds.domain.economic_data import ECONOMIC_DATA_TYPES


def validate(batch: dict[str, Any], document: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return issues and proposed records without mutating project data."""
    issues, records = [], []
    mapping, data_type = batch["mapping"], batch["data_type"]
    def issue(level: str, code: str, message: str, row: int | None = None, column: str | None = None, value: Any = None) -> None:
        issues.append(asdict(Issue(level, code, message, row, column, value)))
    missing = [field for field in REQUIRED[data_type] if field not in mapping]
    for field in missing:
        issue("ERROR", "missing_column", "Required mapping is missing.", column=field)
    if missing:
        return issues, []
    if data_type in WATER_DATA_TYPES:
        from .water_tables import validate_water_table
        return validate_water_table(batch, document)
    if data_type in ECONOMIC_DATA_TYPES:
        from .economic_tables import validate_economic_table
        return validate_economic_table(batch, document)
    if data_type in {'candidates','scientific_inputs','water_budget'}:
        from .scientific_tables import validate_table
        return validate_table(batch, document)
    if data_type == "analysis_units" and key(mapping["area_da"]) in {"area", "alan"} and batch["options"].get("area_unit") != "da":
        issue("ERROR", "ambiguous_unit", "Confirm area_unit='da'; no implicit hectare conversion.", column="area_da")
    known_crops = {key(c["name"]) for c in document["crops"]}
    known_units = {u["external_id"] for u in document["analysis_units"]}
    seen, geometries = set(), {}
    incoming_ids = {str(row["values"].get(mapping.get("external_id"), "")).strip() for row in batch["rows"]}
    if data_type == "geometries":
        for unit in document["analysis_units"]:
            if unit["external_id"] not in incoming_ids and unit.get("geometry") is not None:
                geometries[json.dumps(unit["geometry"], sort_keys=True)] = unit["external_id"]
    for row in batch["rows"]:
        line = row["line"]
        try:
            record = normalize(row, mapping, data_type, batch["project_id"], batch["options"])
        except ValidationError as exc:
            issue("ERROR", "invalid_value", str(exc), line, exc.field, row["values"].get(mapping.get(exc.field)))
            continue
        if data_type in {"analysis_units", "geometries"}:
            identity = record["external_id"]
        elif data_type == "crops":
            identity = key(record["name"])
        else:
            identity = (key(record["crop_name"]), record["year"])
        if identity in seen:
            issue("ERROR", "duplicate_id", "Duplicate record identity in upload.", line, value=identity)
        seen.add(identity)
        if data_type in {"analysis_units", "geometries"}:
            geometry = record.get("geometry")
            error = geometry_error(geometry)
            if error:
                issue("ERROR", "invalid_geometry", error, line, "geometry")
            elif geometry is None:
                severity = "ERROR" if data_type == "geometries" else "WARNING"
                issue(severity, "missing_geometry", "No geometry supplied.", line, "geometry")
            else:
                signature = json.dumps(geometry, sort_keys=True)
                if signature in geometries:
                    issue("ERROR", "duplicate_geometry", "Identical geometry assigned to multiple units.", line, "geometry")
                geometries[signature] = identity
            if data_type == "geometries" and identity not in known_units:
                issue("ERROR", "unknown_unit", "Feature external_id does not match an active analysis unit.", line, "external_id")
            if data_type == "analysis_units" and key(record["current_crop"]) not in known_crops:
                issue("WARNING", "unknown_crop", "Crop is not in the project catalog.", line, "current_crop")
        if data_type in {"crops", "economics"} and not record["source"]:
            issue("WARNING", "missing_source", "Source was not supplied.", line, "source")
        if data_type == "crops":
            if not record["confidence_level"]:
                issue("WARNING", "missing_confidence", "Confidence was not supplied.", line, "confidence_level")
            for field in ("kc_initial", "kc_mid", "kc_end"):
                if record[field] is None:
                    issue("WARNING", "missing_kc", "Kc is missing; water calculation readiness is not implied.", line, field)
                elif record[field] > 2:
                    issue("WARNING", "unusual_kc", "Kc greater than 2 requires review.", line, field)
        if data_type == "economics":
            if key(record["crop_name"]) not in known_crops:
                issue("WARNING", "unknown_crop", "Crop is not in the project catalog.", line, "crop_name")
            if record["currency"] is None:
                issue("WARNING", "missing_currency", "Currency remains null; TRY is a suggestion only.", line, "currency")
            if not record["metadata"].get("yield_unit"):
                issue("WARNING", "missing_yield_unit", "Yield unit was not supplied; value is not converted.", line, "yield_unit")
        records.append(record)
    if data_type == "crops":
        incoming = {key(r["name"]) for r in records}
        referenced = {key(u["current_crop"]) for u in document["analysis_units"]} | {key(e["crop_name"]) for e in document["economics"]}
        for missing_crop in sorted(referenced - incoming):
            issue("WARNING", "catalog_reference_removed", "Replacement catalog omits a crop referenced by active data.", value=missing_crop)
    if not issues:
        issue("INFO", "validated", "All supplied records passed validation.")
    return issues, records
