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


def _project_units(document):
    seen = set()
    units = []
    for source in document.get("analysis_units", []):
        unit_id = _identity(source)
        if unit_id in seen:
            raise ValueError(f"Duplicate project analysis-unit identity: {unit_id}.")
        seen.add(unit_id)
        units.append({
            "analysis_unit_id": unit_id,
            "area_da": source.get("area_da"),
            "current_crop": source.get("current_crop"),
            "latitude": source.get("latitude"),
            "longitude": source.get("longitude"),
            "geometry": deepcopy(source.get("geometry")),
            "settlement": source.get("settlement") or source.get("village") or source.get("district"),
            "warnings": deepcopy(source.get("warnings") or []),
            "source": "project.analysis_units",
        })
    return units


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
