"""Validation and versioned persistence for crop parameters and phenology."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from datetime import date, datetime
from typing import Any

from kds.data.import_models import Issue
from kds.domain.crop_parameters import (
    AMBIGUOUS_GRANULARITY_RELATIONS, IDENTITY_RESOLUTION_REVISION,
    REVIEWED_IDENTITY_RELATIONS, RelationStatus, authority, authority_rank,
    dataset_authority, finite_nonnegative, is_verified_authority,
    replacement_preview, scope_key,
)
from kds.domain.validation import utc_now
from .normalization import numeric


def _mapped(batch: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    return {field: row["values"].get(column) for field, column in batch["mapping"].items()}


def _text(data: dict[str, Any], name: str) -> str:
    return str(data.get(name) or "").strip()


def _identity(data: dict[str, Any], document: dict[str, Any]) -> dict[str, Any]:
    import app
    raw = _text(data, "crop_identity")
    parameter_id = app.normalize_crop_key(raw).replace("_", "")
    runtime = {app.canonical_crop_key(c["name"]): c["name"] for c in document.get("crops", [])}
    ambiguous = {r.parameter_crop_id: r for r in AMBIGUOUS_GRANULARITY_RELATIONS if r.runtime_crop_id in runtime}
    if parameter_id in ambiguous:
        raise ValueError("Crop identity has AMBIGUOUS_GRANULARITY; explicit crop-specific evidence is required.")
    relations = {r.parameter_crop_id: r for r in REVIEWED_IDENTITY_RELATIONS if r.status is RelationStatus.REVIEWED and r.runtime_crop_id in runtime}
    if parameter_id in relations:
        relation = relations[parameter_id]
        return {"crop_identity": raw, "runtime_crop_id": relation.runtime_crop_id,
                "parameter_crop_id": parameter_id, "resolution_status": "REVIEWED_ALIAS",
                "resolution_method": relation.relation_type.value,
                "resolution_evidence": relation.evidence,
                "identity_resolution_revision": IDENTITY_RESOLUTION_REVISION}
    canonical = app.canonical_crop_key(raw)
    if canonical not in runtime or parameter_id != canonical:
        raise ValueError("Crop identity is unknown or requires an explicit reviewed mapping.")
    return {"crop_identity": raw, "runtime_crop_id": canonical, "parameter_crop_id": parameter_id,
            "resolution_status": "EXACT", "resolution_method": "exact_parameter_identity",
            "resolution_evidence": "Exact project crop identity.",
            "identity_resolution_revision": IDENTITY_RESOLUTION_REVISION}


def _common(data: dict[str, Any], document: dict[str, Any], batch: dict[str, Any], line: int) -> dict[str, Any]:
    identity = _identity(data, document)
    year_value = numeric(data.get("applicable_year"), "applicable_year", batch["options"])
    if not float(year_value).is_integer() or int(year_value) != int(document["project"]["planning_year"]):
        raise ValueError("applicable_year must equal the project planning year.")
    scope = _text(data, "geographic_scope")
    if not scope:
        raise ValueError("geographic_scope is required.")
    cls = authority(data.get("authority_class"))
    source, reference = _text(data, "source"), _text(data, "source_reference")
    if not source or not reference:
        raise ValueError("source and source_reference are required.")
    synthetic = "synthetic" in f"{source} {reference}".lower() or "not_official" in f"{source} {reference}".lower()
    return {
        **identity, "applicable_year": int(year_value), "geographic_scope": scope,
        "authority_class": cls.value, "source": source, "source_reference": reference,
        "notes": _text(data, "notes") or None, "source_row": line, "synthetic": synthetic,
        "verified_for_pilot": bool(is_verified_authority(cls) and not synthetic), "engine_connected": False,
    }


def _iso_date(value: Any, field: str) -> str:
    text = _text({field: value}, field)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid ISO calendar date.") from exc
    return parsed.isoformat()


def _month_day(value: Any, field: str) -> str:
    text = _text({field: value}, field)
    try:
        datetime.strptime(f"2000-{text}", "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid MM-DD calendar value.") from exc
    return text


def validate_crop_parameter_table(batch: dict[str, Any], document: dict[str, Any]):
    records, issues, seen = [], [], set()
    kind = batch["data_type"]

    def issue(severity: str, code: str, message: str, line: int | None = None):
        issues.append(asdict(Issue(severity, code, message, line)))

    for row in batch["rows"]:
        line, data = row["line"], _mapped(batch, row)
        try:
            record = _common(data, document, batch, line)
            if kind == "crop_water_parameters":
                for field in ("kc_ini", "kc_mid", "kc_end", "p_ini", "p_dev", "p_mid", "p_late"):
                    record[field] = finite_nonnegative(numeric(data.get(field), field, batch["options"]), field)
                mode = _text(data, "stage_value_mode").upper()
                if mode not in {"DAYS", "FRACTIONS"}:
                    raise ValueError("stage_value_mode must be DAYS or FRACTIONS.")
                stages = [record[field] for field in ("p_ini", "p_dev", "p_mid", "p_late")]
                if mode == "FRACTIONS" and abs(sum(stages) - 1.0) > 1e-9:
                    raise ValueError("FRACTIONS stage values must sum to exactly 1.0; values are not normalized silently.")
                if mode == "DAYS" and sum(stages) <= 0:
                    raise ValueError("DAYS stage durations must have a positive total.")
                record["stage_value_mode"] = mode
                record["stage_total"] = sum(stages)
                if max(record["kc_ini"], record["kc_mid"], record["kc_end"]) > 2.0:
                    issue("WARNING", "unusual_kc", "Kc above 2.0 exceeds the repository's documented review threshold; confirmation requires acknowledgment.", line)
            else:
                mode = _text(data, "mode").upper()
                season = _text(data, "season").upper()
                if season not in {"PRIMARY", "SECONDARY", "PERENNIAL"}:
                    raise ValueError("season must be PRIMARY, SECONDARY or PERENNIAL.")
                record.update(mode=mode, season=season, planting_date=None, harvest_date=None,
                              planting_window_start=None, planting_window_end=None,
                              harvest_window_start=None, harvest_window_end=None)
                if mode == "YEAR_SPECIFIC":
                    planting = _iso_date(data.get("planting_date"), "planting_date")
                    harvest = _iso_date(data.get("harvest_date"), "harvest_date")
                    if int(planting[:4]) != record["applicable_year"] or int(harvest[:4]) != record["applicable_year"]:
                        raise ValueError("YEAR_SPECIFIC dates must match applicable_year.")
                    if planting >= harvest:
                        raise ValueError("planting_date must be before harvest_date.")
                    record.update(planting_date=planting, harvest_date=harvest)
                elif mode == "CLIMATOLOGICAL_WINDOW":
                    fields = ("planting_window_start", "planting_window_end", "harvest_window_start", "harvest_window_end")
                    values = {field: _month_day(data.get(field), field) for field in fields}
                    if values["planting_window_start"] > values["planting_window_end"]:
                        raise ValueError("planting window start must not follow its end.")
                    if values["harvest_window_start"] > values["harvest_window_end"]:
                        raise ValueError("harvest window start must not follow its end.")
                    if values["planting_window_end"] >= values["harvest_window_start"]:
                        raise ValueError("planting window must precede harvest window for the declared season.")
                    record.update(values)
                else:
                    raise ValueError("mode must be YEAR_SPECIFIC or CLIMATOLOGICAL_WINDOW.")
            identity = record["runtime_crop_id"]
            if identity in seen:
                raise ValueError("Duplicate runtime crop identity in upload.")
            seen.add(identity)
            records.append(record)
        except (TypeError, ValueError) as exc:
            issue("ERROR", "crop_parameter_contract", str(exc), line)
    if records:
        try:
            dataset_authority(records)
            scope_key(kind, records)
        except ValueError as exc:
            issue("ERROR", "crop_parameter_contract", str(exc))
    if records and not any(item["severity"] == "ERROR" for item in issues):
        if any(not record["verified_for_pilot"] for record in records):
            issue("WARNING", "unverified_authority", "ASSUMED/UNKNOWN records remain unverified for pilot use.")
        issue("INFO", "crop_parameter_contract_validated", "Records passed contract validation; activation still requires confirmation and remains engine-disconnected.")
    return issues, records


def apply_crop_parameter_records(document: dict[str, Any], batch: dict[str, Any], records: list[dict[str, Any]], override_reason: str | None):
    store = document.setdefault("crop_parameter_data", {"datasets": {}, "active": {}, "reanalysis": {}, "identity_resolution_revision": IDENTITY_RESOLUTION_REVISION})
    datasets, active = store.setdefault("datasets", {}), store.setdefault("active", {})
    pointer = scope_key(batch["data_type"], records)
    previous_id = active.get(pointer)
    previous = datasets.get(previous_id) if previous_id else None
    version = 1 + max((int(d.get("version", 0)) for d in datasets.values() if d.get("scope_key") == pointer), default=0)
    dataset_id, confirmed_at = f"crop-parameter-{batch['id']}", utc_now()
    stored = deepcopy(records)
    for record in stored:
        record.update(uploaded_filename=batch["filename"], file_hash=batch["file_hash"], import_batch_id=batch["id"])
    validity = [str(record["applicable_year"]) for record in stored]
    dataset = {
        "dataset_id": dataset_id, "data_type": batch["data_type"], "scope_key": pointer,
        "version": version, "status": "active", "authority_class": dataset_authority(stored),
        "valid_from": min(validity), "valid_to": max(validity),
        "uploaded_at": batch["uploaded_at"], "confirmed_at": confirmed_at,
        "supersedes": previous_id, "superseded_by": None, "override_reason": override_reason,
        "identity_resolution_revision": IDENTITY_RESOLUTION_REVISION,
        "requires_reanalysis": True, "engine_connected": False,
        "source": {"uploaded_filename": batch["filename"], "file_hash": batch["file_hash"],
                   "import_batch_id": batch["id"], "synthetic": any(r["synthetic"] for r in stored),
                   "references": sorted({r["source_reference"] for r in stored}),
                   "sources": sorted({r["source"] for r in stored})},
        "records": stored,
    }
    if previous:
        previous.update(status="inactive", superseded_by=dataset_id)
    datasets[dataset_id], active[pointer] = dataset, dataset_id
    store["reanalysis"] = {"requires_reanalysis": True, "trigger_dataset_id": dataset_id,
                           "superseded_dataset_id": previous_id, "affected_scenarios": ["S1", "S2"],
                           "at": confirmed_at, "automatic_recompute": False,
                           "existing_analysis_run_ids": sorted(document.get("runs", {}))}
    batch.update(activated_dataset_id=dataset_id, data_version=version, replacement_confirmed_at=confirmed_at)
    return dataset
