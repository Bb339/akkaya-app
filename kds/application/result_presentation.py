"""Presentation-only composition for stored analysis results.

Scientific result objects remain unchanged in the project store.  This module
joins their authoritative pieces with project display metadata by canonical
analysis-unit identity and returns a disposable API view.
"""
from copy import deepcopy
import json


def _identity(row, keys):
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _index(rows, keys, source):
    indexed = {}
    for row in rows or []:
        if not isinstance(row, dict):
            raise ValueError(f"{source} contains a non-object unit record.")
        unit_id = _identity(row, keys)
        if unit_id is None:
            raise ValueError(f"{source} contains a unit without a canonical identity.")
        previous = indexed.get(unit_id)
        if previous is not None:
            left = json.dumps(previous, sort_keys=True, ensure_ascii=False, default=str)
            right = json.dumps(row, sort_keys=True, ensure_ascii=False, default=str)
            if left != right:
                raise ValueError(f"Duplicate conflicting unit identity {unit_id!r} in {source}.")
            continue
        indexed[unit_id] = row
    return indexed


def _selected_crops(detail, scenario):
    if not detail:
        return []
    if scenario == "S1":
        crop = detail.get("chosenCrop") or detail.get("crop")
        return [{"crop": str(crop), "season": "PRIMARY"}] if crop else []
    selected = []
    for key, season in (("primary", "PRIMARY"), ("secondary", "SECONDARY")):
        value = detail.get(key)
        if isinstance(value, dict) and value.get("crop"):
            selected.append({"crop": str(value["crop"]), "season": season})
    return selected


def _profit(detail, scenario):
    if not detail:
        return None
    for key in ("total_profit_tl", "profit_tl"):
        if detail.get(key) is not None:
            return detail[key]
    if scenario == "S2":
        values = [detail.get(key, {}).get("profit_tl") for key in ("primary", "secondary")
                  if isinstance(detail.get(key), dict)]
        supplied = [value for value in values if value is not None]
        return sum(float(value) for value in supplied) if supplied else None
    return None


def _warnings(*rows):
    values = []
    for row in rows:
        if not row:
            continue
        supplied = row.get("warnings", row.get("warning", []))
        supplied = supplied if isinstance(supplied, list) else [supplied]
        for value in supplied:
            if value not in (None, "") and str(value) not in values:
                values.append(str(value))
    return values


def presentation_units(run, document):
    """Return a deterministic, ID-based unit presentation view.

    ``unit_results`` remains the water authority, ``details`` remains the
    optimizer-plan/profit source, and project analysis units remain the source
    for geometry and current-crop metadata.
    """
    result = run.get("result") or {}
    scenario = run.get("scenario") or result.get("scenario")
    water = _index(result.get("unit_results", []), ("analysis_unit_id", "parcelId"), "unit_results")
    plan = _index(result.get("details", []), ("analysis_unit_id", "parcelId"), "result.details")
    project = _index(document.get("analysis_units", []), ("external_id", "analysis_unit_id", "parcelId"),
                     "project.analysis_units")
    # Project metadata enriches result units; it must never create a result row
    # for a unit that the stored scientific/optimizer result did not contain.
    identities = sorted(set(water) | set(plan))
    units = []
    verified = run.get("execution_profile") == "VERIFIED_INSTITUTIONAL"
    for unit_id in identities:
        water_row, detail, metadata = water.get(unit_id), plan.get(unit_id), project.get(unit_id)
        selected = deepcopy((water_row or {}).get("selected_crops")) or _selected_crops(detail, scenario)
        status = next((row.get(key) for row in (water_row, detail, metadata) if row
                       for key in ("status", "assignment_status", "validation_status")
                       if row.get(key) not in (None, "")), None)
        area = next((row.get("area_da") for row in (water_row, detail, metadata)
                     if row and row.get("area_da") is not None), None)
        water_value = (water_row or {}).get("total_water_m3")
        if water_value is None and detail:
            water_value = detail.get("total_water_m3", detail.get("water_m3"))
        unit = {
            "analysis_unit_id": unit_id,
            "area_da": area,
            "current_crop": (metadata or {}).get("current_crop"),
            "selected_crops": selected,
            "authoritative_unit_water_m3": water_value,
            "unit_water_authority": ("VERIFIED_UNIT_PROFILE" if verified and water_row
                                     else "OPTIMIZER_RESULT" if water_value is not None else None),
            "unit_profit_tl": _profit(detail, scenario),
            "latitude": (metadata or {}).get("latitude"),
            "longitude": (metadata or {}).get("longitude"),
            "geometry": deepcopy((metadata or {}).get("geometry")),
            "warnings": _warnings(water_row, detail, metadata),
            "status": status,
            "scenario": scenario,
            "scenario_selection": {key: deepcopy(detail[key]) for key in ("chosenCrop", "primary", "secondary")
                                   if detail and detail.get(key) is not None},
            "presentation_sources": {
                "water": "result.unit_results" if water_row else "result.details" if water_value is not None else None,
                "plan_profit": "result.details" if detail else None,
                "current_crop_geometry": "project.analysis_units" if metadata else None,
            },
        }
        missing = []
        if unit["current_crop"] in (None, ""):
            missing.append("current_crop")
        if unit["unit_profit_tl"] is None:
            missing.append("unit_profit_tl")
        if not ((unit["latitude"] is not None and unit["longitude"] is not None) or unit["geometry"]):
            missing.append("geometry")
        if not unit["warnings"] and unit["status"] is None:
            missing.append("warnings_or_status")
        unit["missing_presentation_metadata"] = missing
        units.append(unit)
    return units


def present_run_for_ui(run, document):
    """Return an enriched copy without mutating scientific/stored results."""
    presented = deepcopy(run)
    result = presented.get("result")
    if isinstance(result, dict):
        result["presentation_units"] = presentation_units(presented, document)
    current_revision = document.get("data_revision")
    snapshot = (presented.get("provenance") or {}).get("input_snapshot") or {}
    run_revision = snapshot.get("preview_revision")
    if run_revision is None and isinstance(result, dict):
        run_revision = (result.get("result_provenance") or {}).get("preview_revision")
    older = (isinstance(current_revision, int) and isinstance(run_revision, int)
             and run_revision < current_revision)
    state = document.get("analysis_state") or {}
    presented["presentation_context"] = {
        "requires_reanalysis": bool(state.get("requires_reanalysis", False)),
        "pinned_to_older_input_snapshot": older,
        "current_project_revision": current_revision,
        "run_project_revision": run_revision,
        "revision_relationship": ("RUN_OLDER_THAN_PROJECT" if older else
                                  "SAME_REVISION" if run_revision == current_revision else
                                  "REVISION_UNAVAILABLE"),
        "latest_run_id": state.get("latest_run_id"),
    }
    return presented
