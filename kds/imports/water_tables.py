"""Validation and persistence for versioned project water datasets."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from typing import Any

from kds.data.import_models import Issue
from kds.domain.validation import utc_now
from kds.domain.water_data import (
    AuthorityClass, authority, calendar_month, convert_volume, dataset_authority,
    finite, normalize_unit, planning_year, replacement_preview,
)
from .normalization import numeric


OFFICIAL_OR_MEASURED = {AuthorityClass.MEASURED, AuthorityClass.OFFICIAL_ALLOCATION, AuthorityClass.OFFICIAL_HISTORICAL}
CAPACITY_BASES = {"measured_delivery", "design_capacity", "operational_limit", "official_allocation", "derived_proxy"}


def _text(data: dict[str, Any], name: str) -> str:
    return str(data.get(name) or "").strip()


def _common(data: dict[str, Any], batch: dict[str, Any], line: int) -> dict[str, Any]:
    cls = authority(data.get("authority_class"))
    institution = _text(data, "source_institution")
    reference = _text(data, "source_reference")
    document = _text(data, "source_document")
    if cls in OFFICIAL_OR_MEASURED and (not institution or not (reference or document)):
        raise ValueError("MEASURED/OFFICIAL records require source_institution and source_reference or source_document.")
    synthetic = "synthetic" in " ".join([
        institution, reference, document, _text(data, "source_authority")
    ]).lower()
    return {
        "authority_class": cls.value,
        "source_authority": _text(data, "source_authority") or None,
        "source_institution": institution or None,
        "source_reference": reference or None,
        "source_document": document or None,
        "source_date": _text(data, "source_date") or None,
        "data_period": _text(data, "data_period") or None,
        "measurement_method": _text(data, "measurement_method") or None,
        "notes": _text(data, "notes") or None,
        "geographic_scope": _text(data, "geographic_scope") or None,
        "source_row": line,
        "synthetic": synthetic,
    }


def _mapped(batch: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    return {field: row["values"].get(column) for field, column in batch["mapping"].items()}


def _volume(data: dict[str, Any], value_field: str, source_field: str, target_field: str | None,
            canonical: str, batch: dict[str, Any], *, allow_zero: bool) -> tuple[float, dict[str, Any] | None]:
    value = numeric(data.get(value_field), value_field, batch["options"])
    value = finite(value, value_field, allow_zero=allow_zero)
    source = normalize_unit(data.get(source_field))
    target = canonical if target_field is None else normalize_unit(data.get(target_field))
    if target != canonical:
        raise ValueError(f"{target_field} must be {canonical}.")
    conversion_context = data
    if source == "m3/s":
        conversion_context = dict(data)
        for field in ("operating_hours_per_day", "operating_days_in_month"):
            conversion_context[field] = numeric(data.get(field), field, batch["options"])
    return convert_volume(value, source, target, conversion_context)


def validate_water_table(batch: dict[str, Any], document: dict[str, Any]):
    records: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    seen: set[Any] = set()
    kind = batch["data_type"]
    project_year = document["project"]["planning_year"]

    def issue(severity: str, code: str, message: str, line: int | None = None):
        issues.append(asdict(Issue(severity, code, message, line)))

    for row in batch["rows"]:
        line = row["line"]
        data = _mapped(batch, row)
        try:
            year_value = planning_year(data.get("planning_year"))
            if year_value != project_year:
                raise ValueError(f"planning_year must match project year {project_year}.")
            common = _common(data, batch, line)
            record: dict[str, Any] = {"planning_year": year_value, **common}

            if kind == "annual_water_supply":
                amount, conversion = _volume(data, "amount", "unit", None, "m3/year", batch, allow_zero=False)
                record.update(amount_m3=amount, source_unit=normalize_unit(data["unit"]), canonical_unit="m3/year", conversion=conversion)
                identity = year_value
            elif kind == "monthly_water_supply":
                month = calendar_month(data.get("month"))
                if int(month[:4]) not in {year_value - 1, year_value}:
                    raise ValueError("monthly supply month must be in the planning year or immediately preceding year.")
                amount, conversion = _volume(data, "amount", "unit", None, "m3/month", batch, allow_zero=True)
                record.update(month=month, amount_m3=amount, source_unit=normalize_unit(data["unit"]), canonical_unit="m3/month", conversion=conversion)
                identity = month
            elif kind == "delivery_capacity":
                month = calendar_month(data.get("month"))
                if int(month[:4]) not in {year_value - 1, year_value}:
                    raise ValueError("delivery month must be in the planning year or immediately preceding year.")
                capacity, conversion = _volume(data, "capacity", "source_unit", "canonical_unit", "m3/month", batch, allow_zero=True)
                basis = _text(data, "capacity_basis").lower()
                if basis not in CAPACITY_BASES:
                    raise ValueError("capacity_basis is not canonical.")
                record.update(month=month, capacity_m3=capacity, source_unit=normalize_unit(data["source_unit"]),
                              canonical_unit="m3/month", capacity_basis=basis, conversion=conversion)
                identity = month
            elif kind == "environmental_release":
                form = _text(data, "release_form").lower()
                month = calendar_month(data["month"]) if data.get("month") not in (None, "") else None
                if month and int(month[:4]) != year_value:
                    raise ValueError("month year must match planning_year.")
                if form == "ratio":
                    if normalize_unit(data["source_unit"]) != "ratio" or normalize_unit(data["canonical_unit"]) != "ratio":
                        raise ValueError("Ratio environmental release requires ratio units.")
                    value = finite(numeric(data.get("value"), "value", batch["options"]), "ratio", positive=True)
                    if value > 1:
                        raise ValueError("Environmental release ratio must be <= 1.")
                    record.update(month=month, release_form=form, ratio=value, source_unit="ratio", canonical_unit="ratio", conversion=None)
                elif form == "monthly_release":
                    if not month:
                        raise ValueError("Monthly physical release requires month.")
                    value, conversion = _volume(data, "value", "source_unit", "canonical_unit", "m3/month", batch, allow_zero=True)
                    record.update(month=month, release_form=form, release_m3=value,
                                  source_unit=normalize_unit(data["source_unit"]), canonical_unit="m3/month", conversion=conversion)
                else:
                    raise ValueError("release_form must be ratio or monthly_release.")
                identity = (form, month)
            elif kind == "conveyance_efficiency":
                value = finite(numeric(data.get("efficiency"), "efficiency", batch["options"]), "efficiency", positive=True)
                if value > 1:
                    raise ValueError("efficiency must be <= 1.")
                period = _text(data, "period")
                scope = _text(data, "scope")
                if not period or not scope:
                    raise ValueError("period and scope are required.")
                record.update(period=period, efficiency=value, scope=scope, canonical_unit="ratio")
                identity = (period, scope)
            else:
                crop = _text(data, "crop")
                unit_id = _text(data, "analysis_unit_id") or None
                month = calendar_month(data["month"]) if data.get("month") not in (None, "") else None
                if month and int(month[:4]) != year_value:
                    raise ValueError("month year must match planning_year.")
                if not crop:
                    raise ValueError("crop is required.")
                if unit_id and unit_id not in {u["external_id"] for u in document.get("analysis_units", [])}:
                    raise ValueError("analysis_unit_id does not exist in this project.")
                value, conversion = _volume(data, "value", "source_unit", "canonical_unit", "m3/da", batch, allow_zero=False)
                method, confidence = _text(data, "method"), _text(data, "confidence")
                if not method or not confidence:
                    raise ValueError("method and confidence are required.")
                record.update(crop=crop, analysis_unit_id=unit_id, month=month,
                              granularity="analysis_unit" if unit_id else "crop",
                              gross_irrigation_m3_da=value, source_unit=normalize_unit(data["source_unit"]),
                              canonical_unit="m3/da", confidence=confidence, method=method, conversion=conversion)
                identity = (crop.casefold(), unit_id, month)

            if identity in seen:
                raise ValueError("Duplicate canonical record identity in upload.")
            seen.add(identity)
            records.append(record)
        except (TypeError, ValueError) as exc:
            issue("ERROR", "water_contract", str(exc), line)

    if records:
        try:
            dataset_authority(records)
            if kind in {"monthly_water_supply", "delivery_capacity"}:
                months = {r["month"] for r in records}
                expected = {f"{project_year}-{month:02d}" for month in range(1, 13)}
                if not expected <= months:
                    raise ValueError("A monthly series must contain all 12 unique planning-year months; preceding-year season months may be added.")
            if kind == "annual_water_supply" and len(records) != 1:
                raise ValueError("Annual water supply must contain exactly one project-year record.")
            if kind == "environmental_release":
                forms = {r["release_form"] for r in records}
                if len(forms) != 1:
                    raise ValueError("Ratio and physical environmental release forms cannot be mixed.")
                if "monthly_release" in forms:
                    expected = {f"{project_year}-{month:02d}" for month in range(1, 13)}
                    if {r["month"] for r in records} != expected:
                        raise ValueError("Monthly environmental release must contain exactly 12 unique months.")
                elif len(records) not in {1, 12}:
                    raise ValueError("Environmental ratio must be annual or a complete 12-month series.")
        except ValueError as exc:
            issue("ERROR", "water_contract", str(exc))

    if records and not issues:
        if any(not r.get("source_institution") for r in records):
            issue("WARNING", "missing_source_institution", "Source institution is absent; authority remains explicit but provenance is incomplete.")
        else:
            issue("INFO", "water_contract_validated", "Canonical water records passed validation; activation still requires confirmation.")
    return issues, records


def preview_replacement(document: dict[str, Any], data_type: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    return replacement_preview(document, data_type, records)


def apply_water_records(document: dict[str, Any], batch: dict[str, Any], records: list[dict[str, Any]], override_reason: str | None):
    water = document.setdefault("water_data", {"datasets": {}, "active": {}})
    datasets, active = water.setdefault("datasets", {}), water.setdefault("active", {})
    previous_id = active.get(batch["data_type"])
    previous = datasets.get(previous_id) if previous_id else None
    version = 1 + max((int(d.get("version", 0)) for d in datasets.values() if d.get("data_type") == batch["data_type"]), default=0)
    dataset_id = f"water-{batch['id']}"
    confirmed_at = utc_now()
    stored_records = deepcopy(records)
    for record in stored_records:
        record["uploaded_filename"] = batch["filename"]
        record["file_hash"] = batch["file_hash"]
        record["import_batch_id"] = batch["id"]
    dataset = {
        "dataset_id": dataset_id,
        "data_type": batch["data_type"],
        "version": version,
        "status": "active",
        "authority_class": dataset_authority(stored_records),
        "valid_from": min((r.get("month") or str(r["planning_year"]) for r in stored_records), default=None),
        "valid_to": max((r.get("month") or str(r["planning_year"]) for r in stored_records), default=None),
        "uploaded_at": batch["uploaded_at"],
        "confirmed_at": confirmed_at,
        "supersedes": previous_id,
        "superseded_by": None,
        "source": {
            "uploaded_filename": batch["filename"], "file_hash": batch["file_hash"],
            "import_batch_id": batch["id"], "synthetic": any(r["synthetic"] for r in stored_records),
            "institutions": sorted({r["source_institution"] for r in stored_records if r.get("source_institution")}),
            "references": sorted({r["source_reference"] for r in stored_records if r.get("source_reference")}),
            "documents": sorted({r["source_document"] for r in stored_records if r.get("source_document")}),
        },
        "override_reason": override_reason,
        "records": stored_records,
    }
    if previous:
        previous["status"] = "inactive"
        previous["superseded_by"] = dataset_id
    datasets[dataset_id] = dataset
    active[batch["data_type"]] = dataset_id
    batch["activated_dataset_id"] = dataset_id
    batch["data_version"] = version
    batch["replacement_confirmed_at"] = confirmed_at
    return dataset
