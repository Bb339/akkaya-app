"""Validation, preview and persistence for future economic datasets."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import math
import re
from typing import Any

from kds.data.import_models import Issue
from kds.domain.economic_data import (
    CALCULATION_METHODS, COST_CATEGORIES, PROFIT_DEPENDENCY_ROLES,
    VERIFIED_INPUT_AUTHORITIES, EconomicAuthorityClass, active_dataset,
    authority_rank, canonical_crop_scope, canonical_economic_scope,
    canonical_geographic_scope, convert_price, convert_yield, dataset_authority,
    economic_authority, finite, iso_date, normalize_unit, replacement_preview, scope_key, year,
)
from kds.domain.validation import utc_now
from .mapping import key
from .normalization import numeric


STRICT_SOURCE = {
    EconomicAuthorityClass.MEASURED_FARM_RECORD,
    EconomicAuthorityClass.OFFICIAL_STATISTICS,
    EconomicAuthorityClass.OFFICIAL_MARKET_RECORD,
    EconomicAuthorityClass.LOCAL_INSTITUTIONAL_SOURCE,
}


def _text(data: dict[str, Any], name: str) -> str:
    return str(data.get(name) or "").strip()


def _mapped(batch: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    return {field: row["values"].get(column) for field, column in batch["mapping"].items()}


def _number(data: dict[str, Any], name: str, batch: dict[str, Any], *, optional: bool = False) -> float | None:
    return numeric(data.get(name), name, batch["options"], optional)


def _crop(data: dict[str, Any], document: dict[str, Any]) -> str:
    incoming = _text(data, "crop")
    if not incoming:
        raise ValueError("crop is required.")
    catalog: dict[str, list[str]] = {}
    for record in document.get("crops", []):
        catalog.setdefault(key(record["name"]), []).append(record["name"])
    matches = catalog.get(key(incoming), [])
    if len(matches) != 1:
        reason = "ambiguous" if len(matches) > 1 else "unknown"
        raise ValueError(f"crop identity is {reason}; use one exact canonical project catalog identity.")
    return matches[0]


def _common(data: dict[str, Any], document: dict[str, Any], line: int) -> dict[str, Any]:
    planning_year = year(data.get("planning_year"))
    if planning_year != document["project"]["planning_year"]:
        raise ValueError(f"planning_year must match project year {document['project']['planning_year']}.")
    observation_year = year(data.get("observation_year"), "observation_year")
    authority = economic_authority(data.get("authority_class"))
    institution, reference = _text(data, "source_institution"), _text(data, "source_reference")
    source_document = _text(data, "source_document")
    if authority in STRICT_SOURCE and (not institution or not (reference or source_document)):
        raise ValueError("Measured/official/local institutional records require source_institution and source_reference or source_document.")
    currency = _text(data, "currency").upper()
    if currency not in {"TRY", "TL"}:
        raise ValueError("Only TRY is accepted; foreign currency requires a future explicit FX rate/date/source contract.")
    source_words = " ".join((institution, reference, source_document, _text(data, "source_authority"))).lower()
    return {
        "planning_year": planning_year, "observation_year": observation_year,
        "temporal_alignment": "CURRENT" if observation_year == planning_year else "STALE" if observation_year < planning_year else "FUTURE",
        "authority_class": authority.value, "source_institution": institution or None,
        "source_document": source_document or None, "source_reference": reference or None,
        "source_authority": _text(data, "source_authority") or None,
        "source_date": _text(data, "source_date") or None,
        "price_date": _text(data, "price_date") or None,
        "price_period": _text(data, "price_period") or None,
        "price_basis": _text(data, "price_basis") or None,
        "geographic_scope": canonical_geographic_scope(data.get("geographic_scope")),
        "crop_scope": canonical_crop_scope(data.get("crop_scope")),
        "currency": "TRY", "measurement_method": _text(data, "measurement_method") or None,
        "notes": _text(data, "notes") or None, "source_row": line,
        "synthetic": "synthetic" in source_words or "not_official" in source_words,
    }


def _dependencies(data: dict[str, Any]) -> list[str]:
    values = []
    for name in ("dependency_dataset_ids", "yield_dataset_id", "price_dataset_id", "support_dataset_id", "cost_dataset_id"):
        values.extend(v.strip() for v in _text(data, name).split(",") if v.strip())
    return list(dict.fromkeys(values))


def _validate_dependency(dataset: dict[str, Any] | None, dataset_id: str, record: dict[str, Any],
                         *, expected_type: str | None = None, require_verified: bool = False) -> None:
    if dataset is None or not dataset.get("confirmed_at"):
        raise ValueError(f"Dependency {dataset_id} must reference a confirmed project economic dataset.")
    if expected_type and dataset.get("data_type") != expected_type:
        raise ValueError(f"Dependency {dataset_id} must have data_type {expected_type}.")
    if dataset.get("status") != "active":
        raise ValueError(f"Dependency {dataset_id} must be active.")
    if dataset.get("derivation_status") != "CURRENT" or dataset.get("requires_recalculation") is True:
        raise ValueError(f"Dependency {dataset_id} must be current and not require recalculation.")
    rows = dataset.get("records") or []
    if not any(row.get("planning_year") == record["planning_year"] for row in rows):
        raise ValueError(f"Dependency {dataset_id} must match planning year {record['planning_year']}.")
    crop_rows = [row for row in rows if row.get("crop") == record["crop"]]
    if expected_type and not crop_rows:
        raise ValueError(f"Dependency {dataset_id} must contain crop {record['crop']}.")
    relevant = crop_rows or rows
    if expected_type and any(row.get("currency", "TRY") != "TRY" for row in relevant):
        raise ValueError(f"Dependency {dataset_id} must use TRY currency.")
    if expected_type:
        expected_scope = canonical_economic_scope(record)
        if any(canonical_economic_scope(row) != expected_scope for row in relevant):
            raise ValueError(f"Dependency {dataset_id} must use the same geographic and crop scope.")
    if require_verified and economic_authority(dataset.get("authority_class")) not in VERIFIED_INPUT_AUTHORITIES:
        raise ValueError(f"Dependency {dataset_id} authority is not verified input evidence.")


def _profit_dependency_roles(data: dict[str, Any], record: dict[str, Any], document: dict[str, Any],
                             *, include_support: bool) -> dict[str, str]:
    datasets = document.get("economic_data", {}).get("datasets", {})
    generic = [v.strip() for v in _text(data, "dependency_dataset_ids").split(",") if v.strip()]
    roles: dict[str, str] = {}
    required = {k: v for k, v in PROFIT_DEPENDENCY_ROLES.items() if include_support or k != "support_dataset_id"}
    for role, expected_type in required.items():
        explicit = _text(data, role)
        candidates = [explicit] if explicit else [item for item in generic if datasets.get(item, {}).get("data_type") == expected_type]
        if len(candidates) != 1:
            raise ValueError(f"Calculated net profit requires exactly one {role} ({expected_type}).")
        roles[role] = candidates[0]
    permitted = set(roles.values())
    if set(generic) - permitted:
        raise ValueError("Calculated net profit dependency_dataset_ids contains an unexpected or wrongly typed dataset.")
    for role, dataset_id in roles.items():
        _validate_dependency(datasets.get(dataset_id), dataset_id, record,
                             expected_type=required[role], require_verified=True)
    return roles


def _validate_profit_values(roles: dict[str, str], document: dict[str, Any], record: dict[str, Any],
                            gross: float, total_cost: float, support: float | None) -> None:
    datasets = document["economic_data"]["datasets"]
    crop = record["crop"]
    yield_row = next(row for row in datasets[roles["yield_dataset_id"]]["records"] if row.get("crop") == crop)
    price_row = next(row for row in datasets[roles["price_dataset_id"]]["records"] if row.get("crop") == crop)
    cost_rows = [row for row in datasets[roles["cost_dataset_id"]]["records"] if row.get("crop") == crop]
    expected_gross = float(yield_row["yield_ton_da"]) * float(price_row["price_tl_ton"])
    expected_cost = sum(float(row["amount_tl_da"]) for row in cost_rows)
    if not math.isclose(gross, expected_gross, rel_tol=1e-9, abs_tol=1e-6):
        raise ValueError("gross_revenue_per_da must equal the referenced yield × sale price.")
    if not math.isclose(total_cost, expected_cost, rel_tol=1e-9, abs_tol=1e-6):
        raise ValueError("total_cost_per_da must equal the referenced cost components.")
    if "support_dataset_id" in roles:
        support_rows = [row for row in datasets[roles["support_dataset_id"]]["records"] if row.get("crop") == crop]
        expected_support = sum(float(row["amount_tl_da"]) for row in support_rows)
        if support is None or not math.isclose(support, expected_support, rel_tol=1e-9, abs_tol=1e-6):
            raise ValueError("support_payment_per_da must equal the referenced support records, including explicit zero.")


def _validate_general_dependencies(data: dict[str, Any], record: dict[str, Any], document: dict[str, Any]) -> list[str]:
    dependencies = _dependencies(data)
    datasets = document.get("economic_data", {}).get("datasets", {})
    for dataset_id in dependencies:
        _validate_dependency(datasets.get(dataset_id), dataset_id, record)
    return dependencies


def validate_economic_table(batch: dict[str, Any], document: dict[str, Any]):
    records: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    seen: set[Any] = set()
    kind = batch["data_type"]

    def issue(severity: str, code: str, message: str, line: int | None = None):
        issues.append(asdict(Issue(severity, code, message, line)))

    for row in batch["rows"]:
        line, data = row["line"], _mapped(batch, row)
        try:
            common = _common(data, document, line)
            crop = _crop(data, document)
            record: dict[str, Any] = {"crop": crop, **common}
            identity: Any
            if kind == "crop_yield":
                raw = finite(_number(data, "yield_value", batch), "yield_value", positive=True)
                source_unit = normalize_unit(data.get("yield_unit"))
                value, conversion = convert_yield(raw, source_unit)
                record.update(yield_ton_da=value, source_value=raw, source_unit=source_unit,
                              canonical_unit="ton/da", conversion=conversion)
                identity = crop
            elif kind == "crop_sale_price":
                raw = finite(_number(data, "price", batch), "price", positive=True)
                source_unit = normalize_unit(data.get("price_unit"))
                value, conversion = convert_price(raw, source_unit)
                if not record["price_date"] and not record["price_period"]:
                    raise ValueError("price_date or price_period is required.")
                if record["price_date"]:
                    record["price_date"] = iso_date(record["price_date"])
                    price_year = int(record["price_date"][:4])
                    if price_year != record["observation_year"]:
                        raise ValueError("price_date year must equal observation_year.")
                    period_years = {int(value) for value in re.findall(r"(?<!\d)(?:19|20|21)\d{2}(?!\d)", record["price_period"] or "")}
                    if period_years and period_years != {price_year}:
                        raise ValueError("price_period year conflicts with price_date.")
                    record["price_alignment"] = record["temporal_alignment"]
                record.update(price_tl_ton=value, source_value=raw, source_unit=source_unit,
                              canonical_unit="TL/ton", conversion=conversion)
                identity = (crop, record["price_date"], record["price_period"])
            elif kind == "crop_support_payment":
                support_type = _text(data, "support_type")
                if not support_type:
                    raise ValueError("support_type is required; support cannot be embedded in price or profit.")
                if normalize_unit(data.get("unit")) != "TL/da":
                    raise ValueError("Support payment canonical unit is TL/da.")
                record.update(support_type=support_type, amount_tl_da=finite(_number(data, "amount", batch), "amount"),
                              source_unit="TL/da", canonical_unit="TL/da", conversion=None)
                identity = (crop, support_type.casefold())
            elif kind == "crop_cost_components":
                category = _text(data, "cost_category").lower()
                if category not in COST_CATEGORIES:
                    raise ValueError("cost_category is not canonical.")
                if normalize_unit(data.get("unit")) != "TL/da":
                    raise ValueError("Cost component canonical unit is TL/da.")
                amount = finite(_number(data, "amount", batch), "amount")
                if amount < 0:
                    raise ValueError("Cost component amount_tl_da must be nonnegative.")
                record.update(cost_category=category, amount_tl_da=amount,
                              source_unit="TL/da", canonical_unit="TL/da", conversion=None)
                identity = (crop, category)
            elif kind == "crop_net_profit":
                method = _text(data, "calculation_method").upper()
                if method not in CALCULATION_METHODS:
                    raise ValueError("calculation_method is not canonical.")
                direct = _number(data, "net_profit_per_da", batch, optional=True)
                gross = _number(data, "gross_revenue_per_da", batch, optional=True)
                total_cost = _number(data, "total_cost_per_da", batch, optional=True)
                support = _number(data, "support_payment_per_da", batch, optional=True)
                formula = None
                if method == "DIRECT_SOURCE":
                    if direct is None:
                        raise ValueError("DIRECT_SOURCE requires net_profit_per_da.")
                    profit = finite(direct, "net_profit_per_da")
                else:
                    if gross is None or total_cost is None:
                        raise ValueError("Calculated net profit requires gross_revenue_per_da and total_cost_per_da.")
                    if method == "GROSS_MINUS_TOTAL_COST":
                        if support is not None:
                            raise ValueError("GROSS_MINUS_TOTAL_COST must not provide support_payment_per_da.")
                        profit, formula = gross - total_cost, "gross_revenue_per_da - total_cost_per_da"
                    elif method == "GROSS_PLUS_SUPPORT_MINUS_TOTAL_COST":
                        if support is None:
                            raise ValueError("GROSS_PLUS_SUPPORT_MINUS_TOTAL_COST requires explicit support_payment_per_da, including explicit zero.")
                        profit, formula = gross + support - total_cost, "gross_revenue_per_da + support_payment_per_da - total_cost_per_da"
                    else:
                        if direct is None or not _text(data, "calculation_formula"):
                            raise ValueError("OTHER_DOCUMENTED_METHOD requires a value and documented calculation_formula.")
                        profit, formula = direct, _text(data, "calculation_formula")
                roles = {}
                if method in {"GROSS_MINUS_TOTAL_COST", "GROSS_PLUS_SUPPORT_MINUS_TOTAL_COST"}:
                    if economic_authority(record["authority_class"]) is not EconomicAuthorityClass.CALCULATED_FROM_VERIFIED_INPUTS:
                        raise ValueError("Calculated net profit authority_class must be CALCULATED_FROM_VERIFIED_INPUTS.")
                    roles = _profit_dependency_roles(data, record, document,
                                                     include_support=method == "GROSS_PLUS_SUPPORT_MINUS_TOTAL_COST")
                    _validate_profit_values(roles, document, record, float(gross), float(total_cost), support)
                    record["authority_class"] = EconomicAuthorityClass.CALCULATED_FROM_VERIFIED_INPUTS.value
                    dependencies = list(roles.values())
                else:
                    dependencies = _validate_general_dependencies(data, record, document)
                record.update(net_profit_per_da=float(profit), canonical_unit="TL/da", source_unit="TL/da",
                              calculation_method=method, calculation_formula=formula, dependency_dataset_ids=dependencies,
                              gross_revenue_per_da=gross, total_cost_per_da=total_cost,
                              support_payment_per_da=support if method == "GROSS_PLUS_SUPPORT_MINUS_TOTAL_COST" else None,
                              conversion=None)
                record.update(roles)
                identity = crop
            elif kind == "analysis_unit_economics":
                unit_id = _text(data, "analysis_unit_id")
                if unit_id not in {u["external_id"] for u in document.get("analysis_units", [])}:
                    raise ValueError("analysis_unit_id does not exist in this project.")
                values = {name: _number(data, name, batch, optional=True) for name in ("gross_revenue", "total_cost", "net_profit")}
                if all(value is None for value in values.values()):
                    raise ValueError("At least one unit-level economic value is required.")
                record.update(analysis_unit_id=unit_id, gross_revenue_tl=values["gross_revenue"],
                              total_cost_tl=values["total_cost"], net_profit_tl=values["net_profit"],
                              canonical_unit="TL", source_unit="TL",
                              dependency_dataset_ids=_validate_general_dependencies(data, record, document))
                identity = (unit_id, crop)
            else:
                unit_id = _text(data, "analysis_unit_id") or None
                if unit_id and unit_id not in {u["external_id"] for u in document.get("analysis_units", [])}:
                    raise ValueError("analysis_unit_id does not exist in this project.")
                season = _text(data, "season").upper()
                if season not in {"PRIMARY", "SECONDARY"}:
                    raise ValueError("season must be PRIMARY or SECONDARY.")
                values = {name: _number(data, name, batch, optional=True) for name in ("yield_value", "price", "cost", "net_profit")}
                if all(value is None for value in values.values()):
                    raise ValueError("At least one seasonal economic value is required.")
                yield_unit, price_unit = normalize_unit(data.get("yield_unit")), normalize_unit(data.get("price_unit"))
                if normalize_unit(data.get("cost_unit")) != "TL/da" or normalize_unit(data.get("net_profit_unit")) != "TL/da":
                    raise ValueError("Seasonal cost and net-profit units must be TL/da.")
                yield_value, yield_conversion = (convert_yield(finite(values["yield_value"], "yield_value", positive=True), yield_unit)
                                                  if values["yield_value"] is not None else (None, None))
                price_value, price_conversion = (convert_price(finite(values["price"], "price", positive=True), price_unit)
                                                  if values["price"] is not None else (None, None))
                record.update(analysis_unit_id=unit_id, season=season, yield_ton_da=yield_value,
                              price_tl_ton=price_value, cost_tl_da=values["cost"], net_profit_tl_da=values["net_profit"],
                              source_units={"yield": yield_unit, "price": price_unit, "cost": "TL/da", "net_profit": "TL/da"},
                              canonical_units={"yield": "ton/da", "price": "TL/ton", "cost": "TL/da", "net_profit": "TL/da"},
                              conversion={"yield": yield_conversion, "price": price_conversion},
                              dependency_dataset_ids=_validate_general_dependencies(data, record, document),
                              missing_secondary_fallback_prohibited=True)
                identity = (unit_id, crop, season)
            if identity in seen:
                raise ValueError("Duplicate canonical economic record identity in upload.")
            seen.add(identity)
            records.append(record)
        except (TypeError, ValueError) as exc:
            issue("ERROR", "economic_contract", str(exc), line)

    if records:
        try:
            dataset_authority(records)
            scope_key(kind, records)
        except ValueError as exc:
            issue("ERROR", "economic_contract", str(exc))
    if records and not any(i["severity"] == "ERROR" for i in issues):
        if any(r["temporal_alignment"] == "STALE" for r in records):
            issue("WARNING", "stale_observation", "Observation year predates planning year; no automatic year mixing or adjustment occurs.")
        if any(r["temporal_alignment"] == "FUTURE" for r in records):
            issue("WARNING", "future_observation", "Observation year follows planning year; no automatic year mixing or adjustment occurs.")
        issue("INFO", "economic_contract_validated", "Canonical economic records passed validation; activation still requires confirmation.")
    return issues, records


def preview_replacement(document: dict[str, Any], data_type: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    return replacement_preview(document, data_type, records)


def apply_economic_records(document: dict[str, Any], batch: dict[str, Any], records: list[dict[str, Any]], override_reason: str | None):
    economics = document.setdefault("economic_data", {"datasets": {}, "active": {}, "dependencies": {}, "reanalysis": {}})
    datasets, active = economics.setdefault("datasets", {}), economics.setdefault("active", {})
    pointer = scope_key(batch["data_type"], records)
    previous_id = active.get(pointer)
    previous = datasets.get(previous_id) if previous_id else None
    version = 1 + max((int(d.get("version", 0)) for d in datasets.values() if d.get("scope_key") == pointer), default=0)
    dataset_id, confirmed_at = f"economic-{batch['id']}", utc_now()
    stored = deepcopy(records)
    for record in stored:
        record.update(uploaded_filename=batch["filename"], file_hash=batch["file_hash"], import_batch_id=batch["id"])
    dependencies = sorted({dep for record in stored for dep in record.get("dependency_dataset_ids", [])})
    validity = [r.get("price_date") or r.get("price_period") or str(r["observation_year"]) for r in stored]
    dataset = {
        "dataset_id": dataset_id, "data_type": batch["data_type"], "scope_key": pointer,
        "version": version, "status": "active", "authority_class": dataset_authority(stored),
        "valid_from": min(validity), "valid_to": max(validity),
        "uploaded_at": batch["uploaded_at"], "confirmed_at": confirmed_at,
        "supersedes": previous_id, "superseded_by": None, "override_reason": override_reason,
        "dependency_dataset_ids": dependencies,
        "derivation_status": "CURRENT", "requires_recalculation": False,
        "source": {"uploaded_filename": batch["filename"], "file_hash": batch["file_hash"],
                   "import_batch_id": batch["id"], "synthetic": any(r["synthetic"] for r in stored),
                   "institutions": sorted({r["source_institution"] for r in stored if r.get("source_institution")}),
                   "references": sorted({r["source_reference"] for r in stored if r.get("source_reference")}),
                   "documents": sorted({r["source_document"] for r in stored if r.get("source_document")})},
        "records": stored,
    }
    if batch["data_type"] == "crop_cost_components":
        totals = {}
        for record in stored:
            totals[record["crop"]] = totals.get(record["crop"], 0.0) + record["amount_tl_da"]
        dataset["component_totals_tl_da"] = totals
        dataset["missing_cost_categories"] = {
            crop: sorted(COST_CATEGORIES - {r["cost_category"] for r in stored if r["crop"] == crop})
            for crop in totals
        }
    if previous:
        previous.update(status="inactive", superseded_by=dataset_id)
    datasets[dataset_id], active[pointer] = dataset, dataset_id
    economics.setdefault("dependencies", {})[dataset_id] = dependencies
    stale = []
    if previous_id:
        changed = {previous_id}
        progress = True
        while progress:
            progress = False
            for candidate in datasets.values():
                if candidate["dataset_id"] != dataset_id and candidate["status"] == "active" and candidate["dataset_id"] not in stale and changed.intersection(candidate.get("dependency_dataset_ids", [])):
                    candidate.update(derivation_status="STALE", requires_recalculation=True, stale_reason=f"an upstream dependency was superseded by {dataset_id}")
                    stale.append(candidate["dataset_id"])
                    changed.add(candidate["dataset_id"])
                    progress = True
    economics["reanalysis"] = {"requires_reanalysis": previous is not None, "trigger_dataset_id": dataset_id,
                                "superseded_dataset_id": previous_id, "stale_dataset_ids": stale,
                                "affected_scenarios": ["S1", "S2"], "at": confirmed_at,
                                "existing_analysis_run_ids": sorted(document.get("runs", {}))}
    batch.update(activated_dataset_id=dataset_id, data_version=version, replacement_confirmed_at=confirmed_at)
    return dataset
