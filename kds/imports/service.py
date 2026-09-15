"""Pure preparation and preview, separate from application persistence."""
from typing import Any
from kds.data.import_models import transition
from .mapping import suggest
from .validation import validate
from kds.domain.water_data import WATER_DATA_TYPES
from kds.domain.economic_data import ECONOMIC_DATA_TYPES
from kds.domain.crop_parameters import CROP_PARAMETER_DATA_TYPES


def refresh(batch: dict[str, Any], document: dict[str, Any]) -> list[dict[str, Any]]:
    issues, records = validate(batch, document)
    batch["issues"] = issues
    batch["validation_summary"] = {level.lower(): sum(i["severity"] == level for i in issues) for level in ("ERROR", "WARNING", "INFO")}
    needs_mapping = any(i["code"] in {"missing_column", "ambiguous_unit"} for i in issues)
    status = "needs_mapping" if needs_mapping else "invalid" if batch["validation_summary"]["error"] else "ready"
    transition(batch, status)
    return records


def preview(batch: dict[str, Any], document: dict[str, Any], limit: int = 20) -> dict[str, Any]:
    result = {k: v for k, v in batch.items() if k != "rows"}
    result["row_count"] = len(batch["rows"])
    result["stale"] = batch["status"] != "applied" and batch["base_revision"] != document["data_revision"]
    result["preview_rows"] = batch["rows"][:limit]
    if batch["detected_columns"]:
        _, records = validate(batch, document)
        result["normalized_preview"] = records[:limit]
    else:
        result["normalized_preview"] = []
    result["suggested_mapping"], result["ambiguous_mapping"] = suggest(batch["detected_columns"], batch["data_type"])
    result["replacement_policy"] = "merge_geometry_by_external_id" if batch["data_type"] == "geometries" else "replace_entire_data_type"
    if batch['data_type']=='scientific_inputs':
        result['replacement_policy']='replace_supplied_scientific_sections; preserve_other_sections'
    if batch['data_type']=='candidates':
        result['replacement_policy']='replace_candidate_options; preserve_other_scientific_sections'
    if batch['data_type'] in WATER_DATA_TYPES and batch["status"] == "ready" and result["normalized_preview"]:
        from .water_tables import preview_replacement
        result["replacement_policy"] = "versioned_active_pointer; retain_history; explicit_confirm"
        result["replacement_preview"] = preview_replacement(document, batch["data_type"], records)
        result["synthetic"] = any(record.get("synthetic") for record in records)
        result["display_label"] = "SYNTHETIC" if result["synthetic"] else None
    if batch['data_type'] in ECONOMIC_DATA_TYPES and batch["status"] == "ready" and result["normalized_preview"]:
        from .economic_tables import preview_replacement
        result["replacement_policy"] = "versioned_scope_pointer; retain_history; explicit_confirm; engine_disconnected"
        result["replacement_preview"] = preview_replacement(document, batch["data_type"], records)
        result["synthetic"] = any(record.get("synthetic") for record in records)
        result["display_label"] = "SYNTHETIC / not_official" if result["synthetic"] else None
    if batch['data_type'] in CROP_PARAMETER_DATA_TYPES and batch["status"] == "ready" and result["normalized_preview"]:
        from kds.domain.crop_parameters import replacement_preview
        result["replacement_policy"] = "versioned_scope_pointer; retain_history; explicit_confirm; engine_disconnected"
        result["replacement_preview"] = replacement_preview(document, batch["data_type"], records)
        result["synthetic"] = any(record.get("synthetic") for record in records)
        result["display_label"] = "SYNTHETIC / not_official" if result["synthetic"] else None
    result["warnings_require_acknowledgment"] = True
    return result
