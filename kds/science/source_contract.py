"""Portable source-lineage checks; never repairs or substitutes scientific data."""
from __future__ import annotations

import csv
from copy import deepcopy
from hashlib import sha256
import json
import math
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


SEVERITIES = {"ERROR", "WARNING", "INFO"}


class SourceContractError(ValueError):
    """An active source cannot be used under the declared lineage contract."""


def issue(code: str, severity: str, message: str, *, source_id: str | None = None,
          unit_id: str | None = None, field: str | None = None) -> dict[str, Any]:
    level = str(severity or "").upper()
    if level not in SEVERITIES:
        raise ValueError("severity must be ERROR, WARNING or INFO")
    return {
        "code": str(code), "severity": level, "source_id": source_id,
        "unit_id": unit_id, "field": field, "message": str(message),
    }


def parse_localized_number(value: Any) -> float:
    """Parse Turkish-formatted numbers without treating missing values as zero."""
    if isinstance(value, bool) or value is None:
        raise ValueError("numeric value is missing or boolean")
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip().replace("\u00a0", "").replace(" ", "")
        if not text:
            raise ValueError("numeric value is blank")
        if "," in text:
            # Turkish convention: dot groups thousands, comma is decimal.
            text = text.replace(".", "").replace(",", ".")
        elif text.count(".") >= 1:
            parts = text.split(".")
            signless = parts[0].lstrip("+-")
            if signless.isdigit() and len(parts) > 1 and all(p.isdigit() and len(p) == 3 for p in parts[1:]):
                text = "".join(parts)
        try:
            number = float(text)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"not a numeric value: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError("numeric value must be finite")
    return number


def area_to_da(value: Any, unit: str | None) -> float:
    number = parse_localized_number(value)
    normalized = str(unit or "").strip().casefold().replace("²", "2")
    factors = {
        "da": 1.0, "dekar": 1.0, "dönüm": 1.0, "donum": 1.0,
        "ha": 10.0, "hektar": 10.0,
        "m2": 0.001, "m^2": 0.001, "metrekare": 0.001,
    }
    if normalized not in factors:
        raise ValueError("area unit is missing or unsupported")
    return number * factors[normalized]


def _portable_path(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).replace("\\", "/")
    path = PurePosixPath(text)
    if path.is_absolute() or ".." in path.parts or (len(text) > 1 and text[1] == ":"):
        raise ValueError("manifest paths must be project-relative and portable")
    return path.as_posix()


def _manifest(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("sources"), list):
        raise ValueError("source lineage manifest must contain a sources array")
    return value


def _field_specs(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _key_specs(value: Any) -> list[str]:
    return [item.strip() for item in str(value or "").split("+") if item.strip()]


def _matches_header(spec: str, headers: set[str]) -> bool:
    return any(option.strip() in headers for option in spec.split("/") if option.strip())


def _external_evidence(root: Path, source: dict[str, Any]) -> tuple[str, str] | None:
    """Return verified evidence path/hash for an externally held original source."""
    evidence = source.get("verification_evidence") or {}
    try:
        relative = _portable_path(evidence.get("portable_path"))
    except ValueError:
        return None
    expected_evidence_hash = str(evidence.get("sha256") or "").lower()
    expected_source_hash = str(source.get("sha256") or "").lower()
    if not relative or not expected_evidence_hash or not expected_source_hash:
        return None
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    if not path.is_file() or sha256(path.read_bytes()).hexdigest() != expected_evidence_hash:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    match = next((item for item in payload.get("workbooks", [])
                  if item.get("source_id") == source.get("source_id")), None)
    if not match or str(match.get("sha256") or "").lower() != expected_source_hash:
        return None
    if match.get("identity_status") != "MATCHED":
        return None
    return relative, expected_source_hash


def _binding_issues(root: Path, manifest: dict[str, Any], sources: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate declared source columns/keys and the narrow reference target contract."""
    problems: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    target_contracts = {
        str(item.get("dataset")): item for item in manifest.get("target_contracts", [])
        if item.get("dataset")
    }
    for link in manifest.get("lineage", []):
        link_id = str(link.get("lineage_id") or "").strip() or None
        target = link.get("target") or {}
        dataset = str(target.get("dataset") or "").strip()
        target_fields = _field_specs(target.get("field"))
        transformation = str((link.get("transformation") or {}).get("function") or "").strip()
        contract = target_contracts.get(dataset)
        if target_contracts:
            if contract is None:
                problems.append(issue("invalid_target_mapping", "ERROR",
                                      "Target dataset is not declared by the source contract.",
                                      unit_id=link_id, field=dataset or None))
            else:
                allowed = set(_field_specs(contract.get("fields")))
                invalid = [field for field in target_fields if field not in allowed]
                if invalid:
                    problems.append(issue("invalid_target_mapping", "ERROR",
                                          "Target field is not declared by the dataset contract: " + ", ".join(invalid),
                                          unit_id=link_id, field=", ".join(invalid)))
                expected_function = str(contract.get("transformation") or "").strip()
                if expected_function and transformation != expected_function:
                    problems.append(issue("invalid_transformation_mapping", "ERROR",
                                          "Declared transformation does not match the target contract.",
                                          unit_id=link_id, field="transformation.function"))

        base_locator = link.get("source_locator") or {}
        per_source = base_locator.get("by_source") or {}
        for source_id in link.get("source_ids", []):
            source = sources.get(source_id)
            if source is None:
                continue
            locator = per_source.get(source_id, base_locator)
            checked = {"lineage_id": link_id, "source_id": source_id,
                       "target_dataset": dataset, "target_fields": target_fields,
                       "transformation": transformation, "status": "DECLARED"}
            if locator.get("kind") != "csv" or source.get("source_type") != "csv":
                results.append(checked)
                continue
            try:
                relative = _portable_path(source.get("portable_path"))
            except ValueError:
                relative = None
            path = (root / relative).resolve() if relative else None
            if path is None or not path.is_file():
                results.append(checked)
                continue
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                headers = set(next(csv.reader(handle), []))
            missing_columns = [spec for spec in _field_specs(locator.get("columns"))
                               if not _matches_header(spec, headers)]
            for spec in missing_columns:
                problems.append(issue("missing_source_column", "ERROR",
                                      "Declared source column is absent.", source_id=source_id,
                                      unit_id=link_id, field=spec))
            missing_keys = [spec for spec in _key_specs(locator.get("record_key"))
                            if not _matches_header(spec, headers)]
            for spec in missing_keys:
                problems.append(issue("missing_record_key", "ERROR",
                                      "Declared record-key column is absent.", source_id=source_id,
                                      unit_id=link_id, field=spec))
            checked["status"] = "BOUND" if not missing_columns and not missing_keys else "INVALID"
            checked["source_columns"] = sorted(headers)
            results.append(checked)
    return problems, results


def audit_source_manifest(project_root: Path | str, manifest_path: Path | str) -> dict[str, Any]:
    """Verify active source identity without searching for or substituting another file."""
    root = Path(project_root).resolve()
    path = Path(manifest_path)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    manifest = _manifest(path)
    problems: list[dict[str, Any]] = []
    source_results: list[dict[str, Any]] = []
    known_ids: set[str] = set()
    sources_by_id: dict[str, dict[str, Any]] = {}

    for source in manifest["sources"]:
        source_id = str(source.get("source_id") or "").strip()
        if not source_id or source_id in known_ids:
            problems.append(issue("missing_or_conflicting_source_id", "ERROR",
                                  "Source ID is missing or duplicated.", source_id=source_id or None))
            continue
        known_ids.add(source_id)
        sources_by_id[source_id] = source
        required = bool(source.get("required_for_execution", False))
        try:
            relative = _portable_path(source.get("portable_path"))
        except ValueError as exc:
            problems.append(issue("nonportable_source_path", "ERROR", str(exc), source_id=source_id,
                                  field="portable_path"))
            relative = None
        result = {
            "source_id": source_id, "portable_path": relative,
            "required_for_execution": required, "status": "UNTRACED",
            "expected_sha256": source.get("sha256"), "actual_sha256": None,
        }
        if relative is None:
            verified = _external_evidence(root, source)
            if verified is not None:
                evidence_path, verified_hash = verified
                result["status"] = "EXTERNAL_AUDIT_VERIFIED"
                result["actual_sha256"] = verified_hash
                result["verification_evidence"] = evidence_path
            else:
                severity = "ERROR" if required else "WARNING"
                problems.append(issue("missing_source", severity,
                                      "Source file is unavailable; no alternate source was selected.",
                                      source_id=source_id, field="portable_path"))
                result["status"] = "MISSING"
        else:
            candidate = (root / relative).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                problems.append(issue("nonportable_source_path", "ERROR",
                                      "Resolved source path escapes the project root.", source_id=source_id,
                                      field="portable_path"))
                result["status"] = "INVALID_PATH"
            else:
                if not candidate.is_file():
                    severity = "ERROR" if required else "WARNING"
                    problems.append(issue("missing_source", severity,
                                          "Declared source file does not exist; no fallback was attempted.",
                                          source_id=source_id, field="portable_path"))
                    result["status"] = "MISSING"
                else:
                    actual = sha256(candidate.read_bytes()).hexdigest()
                    result["actual_sha256"] = actual
                    expected = str(source.get("sha256") or "").lower()
                    if not expected:
                        problems.append(issue("missing_source_hash", "WARNING",
                                              "Source exists but no expected hash is declared.",
                                              source_id=source_id, field="sha256"))
                        result["status"] = "PRESENT_UNHASHED"
                    elif actual != expected:
                        severity = "ERROR" if required else "WARNING"
                        problems.append(issue("source_hash_mismatch", severity,
                                              "Source hash differs from the manifest; no fallback was attempted.",
                                              source_id=source_id, field="sha256"))
                        result["status"] = "HASH_MISMATCH"
                    else:
                        result["status"] = "HASH_MATCH"
        source_results.append(result)

    for link in manifest.get("lineage", []):
        link_id = str(link.get("lineage_id") or "").strip() or None
        for source_id in link.get("source_ids", []):
            if source_id not in known_ids:
                problems.append(issue("unknown_lineage_source", "ERROR",
                                      "Lineage refers to an undeclared source.", source_id=source_id,
                                      unit_id=link_id))
        locator = link.get("source_locator") or {}
        if locator.get("kind") == "excel" and not locator.get("range"):
            for source_id in link.get("source_ids") or [None]:
                problems.append(issue("untraced_source_location", "WARNING",
                                      "Excel sheet/cell range is not known; the field is not cell-level traceable.",
                                      source_id=source_id, unit_id=link_id,
                                      field=(link.get("target") or {}).get("field")))
        if bool(link.get("unit_required", False)) and (not link.get("source_unit") or not link.get("target_unit")):
            problems.append(issue("missing_unit", "WARNING", "Source or target unit is not declared.",
                                  source_id=(link.get("source_ids") or [None])[0], unit_id=link_id,
                                  field=(link.get("target") or {}).get("field")))
        if bool(link.get("period_required", False)) and not link.get("data_period"):
            problems.append(issue("missing_year", "WARNING", "Data year/period is unknown and was not inferred.",
                                  source_id=(link.get("source_ids") or [None])[0], unit_id=link_id))
        nature = str(link.get("data_nature") or "").upper()
        validation = str(link.get("validation_status") or "").upper()
        if nature == "FORMULA_DERIVED" and validation in {"MEASURED", "FIELD_VERIFIED"}:
            problems.append(issue("derived_value_labeled_measured", "ERROR",
                                  "A formula-derived value cannot be labelled as an independent measurement.",
                                  source_id=(link.get("source_ids") or [None])[0], unit_id=link_id,
                                  field=(link.get("target") or {}).get("field")))

    binding_problems, binding_results = _binding_issues(root, manifest, sources_by_id)
    problems.extend(binding_problems)

    status = ("NOT_READY" if any(x["severity"] == "ERROR" for x in problems) else
              "READY_WITH_WARNINGS" if any(x["severity"] == "WARNING" for x in problems) else "READY")
    return {
        "schema_version": manifest.get("schema_version"),
        "manifest_path": path.relative_to(root).as_posix(),
        "manifest_sha256": sha256(path.read_bytes()).hexdigest(),
        "status": status, "issues": problems, "sources": source_results,
        "bindings": binding_results,
        # Hash/lineage checks never confer institutional or field authority.
        "pilot_validation_status": "NOT_EVALUATED",
        "institutional_validation_status": "NOT_EVALUATED",
    }


def audit_reference_runtime_bindings(project_root: Path | str, manifest_path: Path | str) -> dict[str, Any]:
    """Compare declared reference CSV fields with the values returned by the real loaders."""
    root = Path(project_root).resolve()
    manifest_file = Path(manifest_path)
    if not manifest_file.is_absolute():
        manifest_file = root / manifest_file
    manifest = _manifest(manifest_file)
    source_audit = audit_source_manifest(root, manifest_file)
    problems = [item for item in source_audit["issues"] if item.get("severity") == "ERROR"]
    import app

    summary_source = next(item for item in manifest["sources"]
                          if item.get("source_id") == "active:parcel-summary")
    summary_rows = read_csv_records(root / _portable_path(summary_source["portable_path"]))
    loaded_units = app.load_parcels()
    source_units = {str(row["parsel_id"]): row for row in summary_rows}
    target_units = {str(row["id"]): row for row in loaded_units}
    if set(source_units) != set(target_units):
        problems.append(issue("runtime_binding_mismatch", "ERROR",
                              "Unit keys returned by app.load_parcels differ from the declared source.",
                              source_id="active:parcel-summary", field="parsel_id -> id"))
    for unit_id in sorted(set(source_units) & set(target_units)):
        source = source_units[unit_id]
        target = target_units[unit_id]
        expected = {
            "area_da": float(source["alan_da"]), "village": source["koy"],
            "current_crop": source["crop"], "water_m3": float(source["mevcut_su_m3"]),
            "profit_tl": float(source["mevcut_kar_tl"]),
        }
        if any(target.get(field) != value for field, value in expected.items()):
            problems.append(issue("runtime_binding_mismatch", "ERROR",
                                  "app.load_parcels changed a declared source value.",
                                  source_id="active:parcel-summary", unit_id=unit_id,
                                  field="alan_da/koy/crop/mevcut_su_m3/mevcut_kar_tl"))

    candidate_source = next(item for item in manifest["sources"]
                            if item.get("source_id") == "active:candidate-matrix")
    candidate_rows = read_csv_records(root / _portable_path(candidate_source["portable_path"]))
    loaded_candidates = app.load_matrix_candidates().to_dict("records")
    key = lambda row: (str(row["parcel_id"]), str(row["candidate_crop"]))
    source_candidates = {key(row): row for row in candidate_rows}
    target_candidates = {key(row): row for row in loaded_candidates}
    if len(source_candidates) != len(candidate_rows) or set(source_candidates) != set(target_candidates):
        problems.append(issue("runtime_binding_mismatch", "ERROR",
                              "Candidate keys returned by app.load_matrix_candidates differ from the declared source.",
                              source_id="active:candidate-matrix", field="parcel_id + candidate_crop"))
    numeric_fields = ("water_m3_da", "net_water_m3_da", "area_da", "yield_ton_da",
                      "production_ton", "profit_tl_da", "profit_tl_total")
    for candidate_key in sorted(set(source_candidates) & set(target_candidates)):
        source = source_candidates[candidate_key]
        target = target_candidates[candidate_key]
        if any(float(target[field]) != float(source[field]) for field in numeric_fields):
            problems.append(issue("runtime_binding_mismatch", "ERROR",
                                  "app.load_matrix_candidates changed a declared numeric source value.",
                                  source_id="active:candidate-matrix",
                                  unit_id=" + ".join(candidate_key), field=", ".join(numeric_fields)))
    status = "NOT_READY" if problems else "READY"
    return {
        "status": status, "issues": problems,
        "unit_binding": {"source_rows": len(summary_rows), "loaded_rows": len(loaded_units),
                         "matched_keys": len(set(source_units) & set(target_units))},
        "candidate_binding": {"source_rows": len(candidate_rows), "loaded_rows": len(loaded_candidates),
                              "matched_keys": len(set(source_candidates) & set(target_candidates))},
        "pilot_validation_status": "NOT_EVALUATED",
        "institutional_validation_status": "NOT_EVALUATED",
    }


def raise_for_source_errors(audit: dict[str, Any]) -> None:
    errors = [item for item in audit.get("issues", []) if item.get("severity") == "ERROR"]
    if errors:
        codes = ", ".join(sorted({str(item.get("code")) for item in errors}))
        raise SourceContractError("Active source contract failed: " + codes)


def audit_tabular_records(records: Iterable[dict[str, Any]], contract: dict[str, Any]) -> dict[str, Any]:
    """Validate identity, units, values and reproducible row/unit/area totals."""
    rows = [dict(row) for row in records]
    source_id = str(contract.get("source_id") or "tabular-source")
    id_field = str(contract.get("id_field") or "id")
    area_field = str(contract.get("area_field") or "area")
    area_unit = contract.get("area_unit")
    production_field = contract.get("production_field")
    settlement_field = contract.get("settlement_field")
    year_field = contract.get("year_field")
    problems: list[dict[str, Any]] = []
    used: list[tuple[dict[str, Any], str, float]] = []
    excluded: list[dict[str, Any]] = []
    seen: dict[str, dict[str, Any]] = {}

    if not area_unit:
        problems.append(issue("missing_unit", "ERROR", "Area unit is not declared.",
                              source_id=source_id, field=area_field))
    for index, row in enumerate(rows, start=1):
        if not any(str(value or "").strip() for value in row.values()):
            excluded.append({"row": index, "reason": "blank_row"})
            continue
        unit_id = str(row.get(id_field) or "").strip()
        if unit_id.casefold() in {"toplam", "total", "genel toplam"}:
            excluded.append({"row": index, "reason": "total_row", "unit_id": unit_id})
            continue
        if not unit_id:
            problems.append(issue("missing_unit_id", "ERROR", "Analysis-unit ID is missing.",
                                  source_id=source_id, unit_id=f"row:{index}", field=id_field))
            excluded.append({"row": index, "reason": "missing_unit_id"})
            continue
        try:
            area = area_to_da(row.get(area_field), area_unit)
        except ValueError as exc:
            problems.append(issue("invalid_numeric_value", "ERROR", str(exc), source_id=source_id,
                                  unit_id=unit_id, field=area_field))
            continue
        if area < 0:
            problems.append(issue("negative_area", "ERROR", "Area cannot be negative.", source_id=source_id,
                                  unit_id=unit_id, field=area_field))
        if unit_id in seen:
            code = "conflicting_unit_id" if seen[unit_id] != row else "duplicate_unit_id"
            problems.append(issue(code, "ERROR", "Analysis-unit ID is duplicated.", source_id=source_id,
                                  unit_id=unit_id, field=id_field))
        else:
            seen[unit_id] = row
        if production_field:
            raw_production = row.get(production_field)
            try:
                production = parse_localized_number(raw_production)
            except ValueError as exc:
                problems.append(issue("invalid_numeric_value", "ERROR", str(exc), source_id=source_id,
                                      unit_id=unit_id, field=str(production_field)))
            else:
                if production < 0:
                    problems.append(issue("negative_production", "ERROR", "Production cannot be negative.",
                                          source_id=source_id, unit_id=unit_id,
                                          field=str(production_field)))
                if area == 0 and production > 0:
                    problems.append(issue("zero_area_positive_production", "ERROR",
                                          "Positive production with zero area remains unresolved.",
                                          source_id=source_id, unit_id=unit_id,
                                          field=str(production_field)))
        for numeric in contract.get("numeric_fields", []):
            field = str(numeric.get("field") or "")
            try:
                number = parse_localized_number(row.get(field))
            except ValueError as exc:
                problems.append(issue("invalid_numeric_value", "ERROR", str(exc), source_id=source_id,
                                      unit_id=unit_id, field=field))
                continue
            if number < 0 and not bool(numeric.get("negative_allowed", False)):
                problems.append(issue("negative_value", "ERROR", "Negative value is not allowed for this field.",
                                      source_id=source_id, unit_id=unit_id, field=field))
        used.append((row, unit_id, area))

    if year_field:
        year_rows = [row for row in rows
                     if str(row.get(id_field) or "").strip().casefold() not in {"toplam", "total", "genel toplam"}
                     and any(str(value or "").strip() for value in row.values())]
        years = {str(row.get(year_field) or "").strip() for row in year_rows}
        if "" in years:
            problems.append(issue("missing_year", "WARNING", "At least one data year is missing; none was inferred.",
                                  source_id=source_id, field=str(year_field)))
            years.discard("")
        if len(years) > 1 and not contract.get("mixed_years_explained"):
            problems.append(issue("mixed_years", "WARNING", "Multiple years are mixed without an explanation.",
                                  source_id=source_id, field=str(year_field)))

    subtotals: dict[str, dict[str, Any]] = {}
    if settlement_field:
        for row, unit_id, area in used:
            settlement = str(row.get(settlement_field) or "").strip() or "UNSPECIFIED"
            item = subtotals.setdefault(settlement, {"row_count": 0, "unit_ids": set(), "total_area_da": 0.0})
            item["row_count"] += 1
            item["unit_ids"].add(unit_id)
            item["total_area_da"] += area
    rendered_subtotals = {
        key: {"row_count": value["row_count"], "unique_unit_count": len(value["unit_ids"]),
              "total_area_da": value["total_area_da"]}
        for key, value in sorted(subtotals.items())
    }
    total_area = sum(area for _, _, area in used)
    expected = contract.get("expected") or {}
    actuals = {"used_row_count": len(used), "unique_unit_count": len(seen), "total_area_da": total_area}
    for key, actual in actuals.items():
        if expected.get(key) is None:
            continue
        tolerance = float(contract.get("area_tolerance_da", 0.0)) if key == "total_area_da" else 0.0
        if abs(float(actual) - float(expected[key])) > tolerance:
            problems.append(issue("source_used_total_mismatch", "ERROR",
                                  f"Expected {key}={expected[key]!r}, found {actual!r}.",
                                  source_id=source_id, field=key))

    return {
        "source_id": source_id, "source_row_count": len(rows),
        "used_row_count": len(used), "excluded_row_count": len(excluded),
        "excluded_records": excluded, "unique_unit_count": len(seen),
        "total_area_da": total_area, "settlement_subtotals": rendered_subtotals,
        "issues": problems,
    }


def audit_project_document_sources(document: dict[str, Any]) -> dict[str, Any]:
    """Read-only audit for legacy/current project records; never backfills provenance."""
    before = deepcopy(document)
    problems: list[dict[str, Any]] = []
    project_id = str((document.get("project") or {}).get("id") or "") or None
    year = (document.get("project") or {}).get("planning_year")
    if year in (None, ""):
        problems.append(issue("missing_year", "WARNING", "Project planning year is missing and was not inferred.",
                              source_id="project-document", unit_id=project_id, field="planning_year"))
    applied = [batch for batch in (document.get("imports") or {}).values()
               if batch.get("status") == "applied" or any(h.get("status") == "applied" for h in batch.get("history", []))]
    if not applied:
        problems.append(issue("untraced_source_location", "WARNING",
                              "No applied import provenance is available; legacy values remain readable but unverified.",
                              source_id="project-document", unit_id=project_id))
    for batch in applied:
        if not batch.get("file_hash"):
            problems.append(issue("missing_source_hash", "WARNING", "Applied import has no file hash.",
                                  source_id=str(batch.get("id") or "project-import"), unit_id=project_id,
                                  field="file_hash"))
    if document != before:
        raise AssertionError("source audit mutated the project document")
    return {
        "status": "READY_WITH_WARNINGS" if problems else "READY",
        "issues": problems, "pilot_validation_status": "NOT_EVALUATED",
        "institutional_validation_status": "NOT_EVALUATED",
    }


def read_csv_records(path: Path | str) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def audit_reference_analysis_units(project_root: Path | str, manifest_path: Path | str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    manifest_file = Path(manifest_path)
    if not manifest_file.is_absolute():
        manifest_file = root / manifest_file
    manifest = _manifest(manifest_file)
    dataset = next(item for item in manifest.get("datasets", []) if item.get("dataset_id") == "reference-analysis-units")
    source = next(item for item in manifest["sources"] if item.get("source_id") == dataset.get("source_id"))
    path = root / _portable_path(source.get("portable_path"))
    table = audit_tabular_records(read_csv_records(path), dataset["validation_contract"])
    source_audit = audit_source_manifest(root, manifest_file)
    all_issues = list(source_audit["issues"]) + list(table["issues"])
    status = ("NOT_READY" if any(x["severity"] == "ERROR" for x in all_issues) else
              "READY_WITH_WARNINGS" if any(x["severity"] == "WARNING" for x in all_issues) else "READY")
    return {
        "status": status, "manifest": source_audit, "analysis_units": table,
        "issues": all_issues, "pilot_validation_status": "NOT_EVALUATED",
        "institutional_validation_status": "NOT_EVALUATED",
    }
