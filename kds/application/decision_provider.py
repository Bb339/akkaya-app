"""Read-only provider projection for the shared V1 decision workspace.

The projection joins existing project, readiness and stored-run contracts.  It
does not calculate agronomic values and never reads the Akkaya reference
provider.
"""
from copy import deepcopy

from kds.application.project_overview import history, overview
from kds.application.result_presentation import present_run_for_ui


ALGORITHMS = ("GA", "ACO", "ABC")
OBJECTIVES = ("water_saving", "max_profit", "water_efficiency")

DOMAIN_LABELS = {
    "annual_water": "Yıllık su tahsisi",
    "monthly_supply": "Aylık su arzı",
    "delivery": "Aylık teslim kapasitesi",
    "environmental_release": "Çevresel akış",
    "conveyance": "İletim randımanı",
    "perennial_requirement": "Çok yıllık bitki su ihtiyacı",
    "economics": "Ekonomik girdiler",
    "crop_parameters": "Ürün su parametreleri",
    "phenology": "Fenoloji",
    "candidates": "Aday matrisi",
    "current_pattern": "Mevcut ürün deseni",
}


def _identity(row):
    for key in ("external_id", "analysis_unit_id", "parcelId", "id"):
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    raise ValueError("Project analysis unit has no canonical identity.")


def _number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _project_units(document):
    parameters = document.get("scientific_inputs", {}).get("unit_parameters", {})
    seen = set()
    units = []
    for source in document.get("analysis_units", []):
        unit_id = _identity(source)
        if unit_id in seen:
            raise ValueError(f"Duplicate project analysis-unit identity: {unit_id}.")
        seen.add(unit_id)
        current = parameters.get(unit_id, {}) if isinstance(parameters, dict) else {}
        current_water = _number(current.get("current_water_m3", source.get("current_water_m3")))
        current_profit = _number(current.get("current_profit", source.get("current_profit_tl")))
        area = _number(source.get("area_da"))
        units.append({
            "analysis_unit_id": unit_id,
            "area_da": source.get("area_da"),
            "current_crop": source.get("current_crop"),
            "latitude": source.get("latitude"),
            "longitude": source.get("longitude"),
            "geometry": deepcopy(source.get("geometry")),
            "settlement": source.get("settlement") or source.get("village") or source.get("district"),
            "warnings": deepcopy(source.get("warnings") or []),
            "current_water_m3": current_water,
            "current_profit_tl": current_profit,
            "current_efficiency_tl_per_m3": (
                current_profit / current_water if current_water and current_profit is not None else None
            ),
            "current_water_m3_da": current_water / area if area and current_water is not None else None,
            "current_profit_tl_da": current_profit / area if area and current_profit is not None else None,
            "soil_class": current.get("soil_class"),
            "parcel_type": current.get("parcel_type"),
            "current_metrics_source": current.get("source"),
            "source": "project.analysis_units + project.scientific_inputs.unit_parameters",
        })
    return units


def _current_summary(units):
    water = [unit["current_water_m3"] for unit in units if unit["current_water_m3"] is not None]
    profit = [unit["current_profit_tl"] for unit in units if unit["current_profit_tl"] is not None]
    complete = bool(units) and len(water) == len(units) and len(profit) == len(units)
    total_water = sum(water) if len(water) == len(units) else None
    total_profit = sum(profit) if len(profit) == len(units) else None
    return {
        "status": "PROVIDED" if complete else "NOT_PROVIDED",
        "covered_units": min(len(water), len(profit)),
        "total_units": len(units),
        "water_m3": total_water,
        "profit_tl": total_profit,
        "efficiency_tl_per_m3": (
            total_profit / total_water if total_water and total_profit is not None else None
        ),
        "source": "project.scientific_inputs.unit_parameters",
    }


def _geographic_summary(units, project):
    groups = {}
    fallback = project.get("province_or_region") or "Proje kapsamı"
    for unit in units:
        name = unit.get("settlement") or fallback
        group = groups.setdefault(name, {
            "name": name, "unit_count": 0, "area_da": 0.0,
            "current_water_m3": 0.0, "current_profit_tl": 0.0,
            "current_water_complete": True, "current_profit_complete": True,
            "optimized_water_m3": 0.0, "optimized_profit_tl": 0.0,
            "optimized_water_complete": True, "optimized_profit_complete": True,
        })
        group["unit_count"] += 1
        group["area_da"] += _number(unit.get("area_da")) or 0.0
        if unit.get("current_water_m3") is None:
            group["current_water_complete"] = False
        else:
            group["current_water_m3"] += unit["current_water_m3"]
        if unit.get("current_profit_tl") is None:
            group["current_profit_complete"] = False
        else:
            group["current_profit_tl"] += unit["current_profit_tl"]
        result = unit.get("result") or {}
        if result.get("authoritative_unit_water_m3") is None:
            group["optimized_water_complete"] = False
        else:
            group["optimized_water_m3"] += result["authoritative_unit_water_m3"]
        if result.get("unit_profit_tl") is None:
            group["optimized_profit_complete"] = False
        else:
            group["optimized_profit_tl"] += result["unit_profit_tl"]
    for group in groups.values():
        if not group.pop("current_water_complete"):
            group["current_water_m3"] = None
        if not group.pop("current_profit_complete"):
            group["current_profit_tl"] = None
        if not group.pop("optimized_water_complete"):
            group["optimized_water_m3"] = None
        if not group.pop("optimized_profit_complete"):
            group["optimized_profit_tl"] = None
    return {
        "status": "PROVIDED" if groups else "NOT_PROVIDED",
        "level": "settlement_or_project_scope",
        "rows": list(groups.values()),
        "source": "project.analysis_units + project.scientific_inputs.unit_parameters",
    }


def _geometry_kind(unit):
    geometry = unit.get("geometry")
    if isinstance(geometry, dict) and geometry.get("type") in {"Polygon", "MultiPolygon"}:
        return geometry["type"]
    if unit.get("latitude") is not None and unit.get("longitude") is not None:
        return "Point"
    return None


def _requirements(report, scenario):
    verified = report["execution_profiles"]["VERIFIED_INSTITUTIONAL"]
    rows = [
        {
            "key": "analysis_units",
            "label": "Analiz birimleri / parseller",
            "requirement": "REQUIRED",
            "status": "PROVIDED" if report["counts"]["analysis_units"] else "MISSING",
            "technical_status": "READY" if report["counts"]["analysis_units"] else "MISSING_DATASET",
            "explanation_tr": ("Analiz birimleri sağlandı." if report["counts"]["analysis_units"]
                               else "Analizin çalışabilmesi için analiz birimi dosyası eksik."),
        }
    ]
    for key, domain in report.get("domains", {}).items():
        if domain.get("connection_state") == "NOT_REQUIRED_FOR_SCENARIO":
            requirement = "OPTIONAL"
            status = "NOT_APPLICABLE"
        else:
            requirement = "REQUIRED"
            status = "PROVIDED" if domain.get("status") == "READY" else "REVIEW_REQUIRED"
        rows.append({
            "key": key,
            "label": DOMAIN_LABELS.get(key, key.replace("_", " ").title()),
            "requirement": requirement,
            "status": status,
            "technical_status": domain.get("connection_state") or domain.get("status"),
            "explanation_tr": ("Veri doğrulandı ve yürütme sözleşmesine bağlı."
                               if status == "PROVIDED" else
                               "Bu veri seçilen senaryoda zorunlu değil."
                               if status == "NOT_APPLICABLE" else
                               "Veri eksik veya doğrulanamadı; teknik ayrıntıyı inceleyin."),
            "technical_detail": domain.get("blocking_reason"),
        })
    rows.append({
        "key": "geometry", "label": "Harita geometrisi", "requirement": "OPTIONAL",
        "status": "PROVIDED" if report["counts"]["geometry_covered"] else "MISSING",
        "technical_status": "PRESENT" if report["counts"]["geometry_covered"] else "NOT_PROVIDED",
        "explanation_tr": ("Harita geometrisi sağlandı." if report["counts"]["geometry_covered"]
                           else "Harita verisi sağlanmadı; analiz haritasız çalışabilir."),
    })
    return {
        "scenario": scenario,
        "ready": verified["ready"][scenario],
        "blocking_reasons": deepcopy(verified["blocking_reasons"][scenario]),
        "warnings": deepcopy(verified["warnings"]),
        "items": rows,
    }


def project_decision_context(document, run=None, scenario="S1"):
    """Create the backend-authoritative PROJECT_DATA view consumed by V1."""
    if scenario not in {"S1", "S2"}:
        raise ValueError("scenario must be S1 or S2.")
    report = overview(document)
    readiness = report["readiness"]
    units = _project_units(document)
    run_view = present_run_for_ui(run, document) if run is not None else None
    if run_view:
        result_units = {row["analysis_unit_id"]: row
                        for row in run_view.get("result", {}).get("presentation_units", [])}
        units = [{**unit, "result": deepcopy(result_units.get(unit["analysis_unit_id"]))}
                 for unit in units]
    geometry_count = sum(_geometry_kind(unit) is not None for unit in units)
    metadata = document.get("metadata", {})
    synthetic = bool(metadata.get("synthetic_institutional_test") and metadata.get("not_official"))
    verified = readiness["execution_profiles"]["VERIFIED_INSTITUTIONAL"]
    scenarios = {
        name: {
            "ready": verified["ready"][name],
            "blocking_reasons": deepcopy(verified["blocking_reasons"][name]),
        } for name in ("S1", "S2")
    }
    return {
        "provider": "PROJECT_DATA",
        "project": deepcopy(document["project"]),
        "project_revision": document.get("data_revision", 0),
        "authority": ("SYNTHETIC / NOT_OFFICIAL" if synthetic else
                      "VERIFIED INSTITUTIONAL" if verified["ready"][scenario] else
                      "INSTITUTIONAL / NOT VERIFIED"),
        "synthetic": synthetic,
        "execution_profile": "VERIFIED_INSTITUTIONAL",
        "capabilities": {
            "algorithms": list(ALGORITHMS), "objectives": list(OBJECTIVES), "scenarios": scenarios,
        },
        "requirements": _requirements(readiness, scenario),
        "units": units,
        "current_summary": _current_summary(units),
        "geographic_summary": _geographic_summary(units, document["project"]),
        "unit_count": len(units),
        "total_area_da": readiness["counts"]["total_area_da"],
        "crop_count": readiness["counts"]["crops"],
        "candidate_unit_count": report["candidate_units"],
        "geometry": {
            "available": geometry_count,
            "total": len(units),
            "coverage": ("FULL" if units and geometry_count == len(units) else
                         "PARTIAL" if geometry_count else "NONE"),
            "fabricated": False,
        },
        "history": history(document, limit=50),
        "run": run_view,
    }
