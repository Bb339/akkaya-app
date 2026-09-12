"""Read thesis inputs, preserve provenance; never invoke or alter the scientific engine."""
import csv
from dataclasses import asdict
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from kds.application.project_service import project_document
from kds.data.repositories import ProjectRepository, Document, ConflictError
from kds.domain.analysis_unit import AnalysisUnit
from kds.domain.crop import Crop
from kds.domain.economics import Economics
from kds.domain.project import Project
from kds.domain.water_budget import WaterBudget
from kds.imports.normalization import record_id, boolean

PROJECT_ID = "akkaya-2024-demo"
SOURCE_VERSION = "v1.0.0-thesis-final"
SOURCE_COMMIT = "a49daac1ae6d15d83428565c388bfafb4b6da08a"
SOURCE_FILES = {
    "units": "parsel_su_kar_ozet.csv",
    "crops": "urun_parametreleri_demo.csv",
    "candidates": "excel_derived/combined_parcel_candidate_matrix_2024.csv",
}


def source_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def build_demo(source_dir: Path) -> Document:
    paths = {name: source_dir / filename for name, filename in SOURCE_FILES.items()}
    units, crops, candidates = (source_rows(paths[name]) for name in ("units", "crops", "candidates"))
    refs = {"analysis_unit_count": len(units),
            "total_area_da": str(sum(Decimal(r["alan_da"]) for r in units)),
            "current_water_m3": str(sum(Decimal(r["mevcut_su_m3"]) for r in units)),
            "current_profit_tl": str(sum(Decimal(r["mevcut_kar_tl"]) for r in units)),
            "raw_candidate_rows": len(candidates),
            "raw_water_quota_flagged_rows": sum(int(r["is_feasible_under_current_quota"]) for r in candidates)}
    if (refs["analysis_unit_count"] != 179 or Decimal(refs["total_area_da"]) != Decimal("134919")
            or Decimal(refs["current_water_m3"]) != Decimal("100700080.81")
            or Decimal(refs["current_profit_tl"]) != Decimal("1041499119.212")
            or refs["raw_candidate_rows"] != 6859 or refs["raw_water_quota_flagged_rows"] != 3673):
        raise ValueError("Akkaya source no longer matches the frozen thesis references.")
    project = Project(id=PROJECT_ID, name="Akkaya 2024 Demo", planning_year=2024,
                      annual_water_budget=float(refs["current_water_m3"]), water_budget_unit="m3",
                      country="Türkiye", province_or_region="Niğde", basin_or_irrigation_area="Akkaya",
                      description="Temsilî analiz birimleri kullanan tez referans projesi.", status="active",
                      data_source_notes="Excel/CROPWAT referansları ve proxy/türetilmiş veriler. Su miktarı mevcut desenin hesaplanmış talep referansıdır.")
    budget = WaterBudget(PROJECT_ID, project.annual_water_budget, "m3", "calculated_reference",
                         source=SOURCE_FILES["units"], metadata={"exact_amount": refs["current_water_m3"]})
    document = project_document(project, budget)
    for row in units:
        external_id = row["parsel_id"]
        metadata = {"source_file": SOURCE_FILES["units"], "source_record": row,
                    "current_profit_tl": row["mevcut_kar_tl"], "current_water_m3": row["mevcut_su_m3"],
                    "geometry_notice": "Geometry is not inferred from coordinates; source geometry remains in the legacy dataset."}
        unit = AnalysisUnit(record_id(PROJECT_ID, external_id), PROJECT_ID, external_id,
                            float(row["alan_da"]), row["crop"], external_id, row["koy"],
                            latitude=float(row["lat"]) if row["lat"] else None,
                            longitude=float(row["lon"]) if row["lon"] else None, metadata=metadata)
        document["analysis_units"].append(asdict(unit))
    for row in crops:
        name = row["urun_adi"]
        crop = Crop(record_id(PROJECT_ID, name), PROJECT_ID, name, crop_group=row["kategori"],
                    perennial=boolean(row["cok_yillik_mi"], "perennial"), source=row["kaynak"],
                    confidence_level=row["veri_onceligi"], metadata={"source_file": SOURCE_FILES["crops"], "source_record": row})
        document["crops"].append(asdict(crop))
        economics = Economics(PROJECT_ID, name, 2024, float(row["beklenen_verim_kg_da"]) if row["beklenen_verim_kg_da"] else None,
                              float(row["net_kar_tl_da"]), "TRY", row["ekonomi_kaynak_durumu"],
                              {"yield_unit": "kg/da", "source_file": SOURCE_FILES["crops"],
                               "note": "Catalog rate; do not substitute it for the unit-level thesis baseline profit."})
        document["economics"].append(asdict(economics))
    if len({u["external_id"] for u in document["analysis_units"]}) != len(units):
        raise ValueError("Duplicate source analysis units.")
    document["metadata"] = {"source_version": SOURCE_VERSION, "source_commit": SOURCE_COMMIT,
                            "references": refs, "sources": {name: {"relative_path": SOURCE_FILES[name], "sha256": sha256(path.read_bytes()).hexdigest()} for name, path in paths.items()},
                            "candidate_note": "raw_water_quota_flagged_rows counts raw matrix quota flags, not final suitable candidates."}
    return document


def ensure_demo(repository: ProjectRepository, source_dir: Path) -> Document:
    document = build_demo(source_dir)
    try:
        return repository.create(document)
    except ConflictError:
        existing = repository.get(PROJECT_ID)
        if existing["metadata"].get("sources") != document["metadata"]["sources"]:
            raise ConflictError("Existing demo provenance differs; no data was overwritten.")
        return existing
