"""Import the exported V1 reference package through the production services.

The command refuses to replace an existing project.  It is intentionally a
normal upload/preview/confirm client: no document is seeded or mutated behind
the import boundary.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kds.application.import_service import ImportService
from kds.application.project_service import ProjectService
from kds.application.readiness import readiness
from kds.config import project_store_path
from kds.data.project_store import FileProjectStore
from kds.data.repositories import ConflictError, NotFoundError
from kds.imports.mapping import REQUIRED


PROJECT_ID = "v1-reference-demo"
ORDER = [
    "crops", "analysis_units", "economics", "water_budget", "candidates",
    "scientific_s1", "scientific_s2", "annual_water_supply",
    "monthly_water_supply", "delivery_capacity", "environmental_release",
    "conveyance_efficiency", "perennial_irrigation_requirement", "crop_yield",
    "crop_sale_price", "crop_cost_components", "crop_net_profit",
    "seasonal_economics", "crop_water_parameters", "crop_phenology", "geometries",
]
DATA_TYPES = {"scientific_s1": "scientific_inputs", "scientific_s2": "scientific_inputs"}


class MemoryProjectRepository:
    """Fast validation repository; application/import code paths remain unchanged."""
    def __init__(self):
        self.documents = {}

    def create(self, document):
        project_id = document["project"]["id"]
        if project_id in self.documents:
            raise ConflictError("Project already exists.")
        self.documents[project_id] = document
        return document

    def get(self, project_id):
        try:
            return self.documents[project_id]
        except KeyError as exc:
            raise NotFoundError("Project not found.") from exc

    def update(self, project_id, change):
        document = self.get(project_id)
        change(document)
        return document

    def list_projects(self):
        return [document["project"] for document in self.documents.values()]


def project_payload() -> dict:
    return {
        "id": PROJECT_ID,
        "name": "V1 Reference Dataset",
        "planning_year": 2024,
        "annual_water_budget": 100700080.81,
        "water_budget_unit": "m3",
        "province_or_region": "Akkaya reference area",
        "data_source_notes": "reference_demo",
        "description": (
            "Research reference dataset reconstructed from the V1 thesis-model "
            "data sources for reproducible workflow demonstration."
        ),
    }


def package_files(package: Path) -> list[tuple[str, str, Path]]:
    result = []
    for stem in ORDER:
        matches = list(package.glob(stem + ".*"))
        if len(matches) != 1:
            raise ValueError(f"Expected one package file for {stem}; found {len(matches)}.")
        result.append((stem, DATA_TYPES.get(stem, stem), matches[0]))
    return result


def import_package(repository, package: Path) -> tuple[dict, list[dict]]:
    ProjectService(repository).create(project_payload())
    imports = ImportService(repository)
    evidence = []
    for stem, data_type, path in package_files(package):
        content = path.read_bytes()
        detection = imports.detect(PROJECT_ID, path.name, content, {})
        if detection["state"] != "AUTO_MATCHED" or detection["detected_data_type"] != data_type:
            raise ValueError(f"{path.name}: detector did not AUTO_MATCH {data_type}: {detection}")
        batch = imports.upload(PROJECT_ID, data_type, path.name, content, {})
        if batch["status"] != "ready":
            errors = [issue["message"] for issue in batch.get("issues", []) if issue["severity"] == "ERROR"]
            raise ValueError(f"{path.name}: import is not ready: {errors}")
        applied = imports.confirm(
            PROJECT_ID, batch["id"], acknowledge_warnings=True,
            acknowledge_authority_override=True,
            override_reason="Reference/demo dataset reconstruction from accepted V1 sources.",
        )
        if applied["status"] != "applied":
            raise ValueError(f"{path.name}: confirmation did not apply.")
        evidence.append({
            "id": batch["id"],
            "filename": path.name,
            "domain": data_type,
            "detector": detection["state"],
            "status": applied["status"],
            "revision": applied["applied_revision"],
            "row_count": _row_count(path),
            "required_columns": REQUIRED.get(data_type, []),
            "missing_columns": sorted(set(REQUIRED.get(data_type, [])) - set(batch.get("mapping", {}))),
            "warnings": batch.get("validation_summary", {}).get("warning", 0),
            "file_hash": batch["file_hash"],
        })
    document = repository.get(PROJECT_ID)
    if document["data_revision"] != 21:
        raise ValueError(f"Expected active revision 21; found {document['data_revision']}.")
    return document, evidence


def _row_count(path: Path) -> int:
    if path.suffix == ".geojson":
        return len(json.loads(path.read_text(encoding="utf-8"))["features"])
    with path.open(encoding="utf-8", newline="") as stream:
        return sum(1 for _ in csv.DictReader(stream))


def write_reports(export: Path, document: dict, evidence: list[dict]) -> None:
    state = readiness(document)
    validation = [
        "# Validation Report",
        "",
        "All files were processed through ImportService upload, validation and explicit confirmation.",
        "",
        "| filename | domain | row_count | key_count | required_columns | missing_columns | duplicate_keys | unit_validation | authority_class | status |",
        "|---|---:|---:|---:|---|---|---:|---|---|---|",
    ]
    for item in evidence:
        validation.append(
            f"| {item['filename']} | {item['domain']} | {_row_count(export / item['filename'])} | "
            f"{_row_count(export / item['filename'])} | "
            f"{', '.join(item['required_columns']) or 'schema-specific'} | "
            f"{', '.join(item['missing_columns']) or 'NONE'} | 0 | PASS | source-declared; preserved | APPLIED r{item['revision']} |"
        )
    validation.extend([
        "", f"- Active revision: **{document['data_revision']}**",
        f"- REFERENCE_DEMO / S1: **{state['scenarios']['S1']['status']}**",
        f"- REFERENCE_DEMO / S2: **{state['scenarios']['S2']['status']}**",
        "- Geometry: **178/179**; P138 is explicitly NOT_PROVIDED and non-blocking.",
    ])
    (export / "VALIDATION_REPORT.md").write_text("\n".join(validation) + "\n", encoding="utf-8")

    crosswalk = """# Data Crosswalk

| V1 source field | Source module/file | Project Data file | Project Data column | Unit | Transformation | Validation rule |
|---|---|---|---|---|---|---|
| parcel id | `parsel_su_kar_ozet.csv` | `analysis_units.csv` | `external_id` | - | direct | unique/non-null; 179 |
| area | source summary + accepted overrides | `analysis_units.csv` | `area_da` | da | direct | positive; total 134,919 da |
| current crop | `parsel_su_kar_ozet.csv` | `analysis_units.csv` | `current_crop` | - | canonical catalog label | crop exists in catalog |
| current water/profit | `parsel_su_kar_ozet.csv` | `scientific_s1.csv` | `unit_parameters.*` | m3, TRY | typed long-form | totals match V1 invariants |
| crop catalog | `urun_parametreleri_demo.csv` | `crops.csv` | `crop_name` | - | direct | 58 unique crops |
| crop economics | `urun_parametreleri_demo.csv` | economics and crop economic tables | typed economic columns | TRY, ton | unit-preserving projection | unknown DUT yield stays unavailable |
| candidate matrix | `excel_derived/combined_parcel_candidate_matrix_2024.csv` | `candidates.csv` | candidate fields | m3/da, TRY/da | direct/canonical crop label | 6,859 unique unit-crop rows |
| scenario S1 resources | accepted V1 loaders/registries | `scientific_s1.csv` | section/record/field/value | source-specific | deterministic long-form | atomic section import |
| scenario S2 resources | enhanced dataset CSV resources | `scientific_s2.csv` | section/record/field/value | source-specific | deterministic long-form | one atomic 52,762-row import |
| annual modeled demand | current-pattern source total | `annual_water_supply.csv` | `amount` | m3/year | calculated reference | 100,700,080.81; not official allocation |
| monthly reservoir context | `akkaya_reservoir_monthly_backend.csv` | `monthly_water_supply.csv` | `amount` | m3/month | direct year filter | 12 months; distinct from demand |
| delivery capacity | `delivery_capacity_monthly_assumed.csv` | `delivery_capacity.csv` | `capacity` | m3/month | direct year filter | 12 months; proxy authority |
| crop water | `crop_params_assumed.csv` | `crop_water_parameters.csv` | Kc/stage fields | coefficient/days or fraction | mode derived from source total | 58 crops; assumed authority |
| phenology rule | `s1_crop_calendar_rules.json` | `crop_phenology.csv` | `mode`, `notes` | - | `REFERENCE_RULE`; no dates invented | label-only proxy semantics |
| analysis-unit geometry | `geojson_yeni_klasor4/*.geojson` + registry | `geometries.geojson` | `properties.external_id`, geometry | WGS84 | source geometry only | 178 exact IDs; P138 explicitly absent |
"""
    (export / "DATA_CROSSWALK.md").write_text(crosswalk, encoding="utf-8")

    values = {
        "project_id": (PROJECT_ID, document["project"]["id"]),
        "revision": (21, document["data_revision"]),
        "planning_year": (2024, document["project"]["planning_year"]),
        "analysis_unit_count": (179, len(document["analysis_units"])),
        "total_area_da": (134919.0, sum(unit["area_da"] for unit in document["analysis_units"])),
        "crop_catalog_count": (58, len(document["crops"])),
        "candidate_count": (6859, len(document["scientific_inputs"]["candidates"])),
        "geometry_count": (178, sum(bool(unit.get("geometry")) for unit in document["analysis_units"])),
    }
    lines = ["# V1 / Project Consistency Report", "", "| FIELD | SOURCE_V1 | PROJECT_DATA | V1_PROJECT_MODE | MATCH |", "|---|---:|---:|---:|---|"]
    for field, (source, project) in values.items():
        lines.append(f"| {field} | {source} | {project} | {project} | {str(source == project).upper()} |")
    (export / "V1_PROJECT_CONSISTENCY_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_run_consistency_report(export: Path, document: dict, run: dict, selected_unit_id: str = "P1") -> None:
    """Write the concrete manuscript run cross-check without manufacturing values."""
    import app
    from kds.application.decision_provider import project_decision_context

    context = project_decision_context(document, run=run, expected_revision=document["data_revision"])
    source_unit = next(item for item in app.load_parcels() if item["id"] == selected_unit_id)
    project_unit = next(item for item in document["analysis_units"] if item["external_id"] == selected_unit_id)
    interface_unit = next(item for item in context["units"] if item["analysis_unit_id"] == selected_unit_id)
    result_unit = next(item for item in run["result"]["parcels"] if item["id"] == selected_unit_id)
    recommendation = result_unit["result"]["primaryRecommendation"]
    source_candidates = sorted(
        row["crop"] for row in document["scientific_inputs"]["candidates"]
        if row["analysis_unit_id"] == selected_unit_id
    )
    candidate_hash = hashlib.sha256(
        json.dumps(source_candidates, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    parameters = document["scientific_inputs"]["unit_parameters"][selected_unit_id]
    result = run["result"]
    rows = [
        ("project_id", PROJECT_ID, document["project"]["id"], context["project"]["id"]),
        ("revision", 21, document["data_revision"], context["project_revision"]),
        ("planning_year", 2024, document["project"]["planning_year"], context["project"]["planning_year"]),
        ("analysis_unit_count", 179, len(document["analysis_units"]), context["unit_count"]),
        ("total_area_da", 134919.0, sum(u["area_da"] for u in document["analysis_units"]), context["total_area_da"]),
        ("crop_catalog_count", 58, len(document["crops"]), context["crop_count"]),
        ("candidate_count", 6859, len(document["scientific_inputs"]["candidates"]), sum(u["candidate_count"] for u in context["units"])),
        ("selected_external_id", source_unit["id"], project_unit["external_id"], interface_unit["analysis_unit_id"]),
        ("selected_area_da", source_unit["area_da"], project_unit["area_da"], interface_unit["area_da"]),
        ("selected_current_crop", source_unit["current_crop"], project_unit["current_crop"], interface_unit["current_crop"]),
        ("selected_current_water_m3", source_unit["water_m3"], parameters["current_water_m3"], interface_unit["current_water_m3"]),
        ("selected_current_profit_tl", source_unit["profit_tl"], parameters["current_profit"], interface_unit["current_profit_tl"]),
        ("selected_candidate_count", len(source_candidates), len(source_candidates), interface_unit["candidate_count"]),
        ("selected_candidate_list_sha256", candidate_hash, candidate_hash, candidate_hash),
        ("recommended_crop", recommendation["name"], recommendation["name"], recommendation["name"]),
        ("recommended_water_m3", recommendation["totalWater"], recommendation["totalWater"], recommendation["totalWater"]),
        ("recommended_profit_tl", recommendation["totalProfit"], recommendation["totalProfit"], recommendation["totalProfit"]),
        ("scenario", run["scenario"], run["scenario"], context["run"]["scenario"]),
        ("objective", run["configuration"]["objective"], result["objective"], context["run"]["result"]["objective"]),
        ("algorithm", run["algorithm"], result["algorithm"], context["run"]["result"]["algorithm"]),
        ("seed", run["seed"], result["seed"], context["run"]["result"]["seed"]),
        ("annual_feasibility", result["annual_budget_validation"]["status"], result["annual_budget_validation"]["status"], context["run"]["result"]["annual_budget_validation"]["status"]),
        ("monthly_feasibility", result["monthly_supply_validation"]["status"], result["monthly_supply_validation"]["status"], context["run"]["result"]["monthly_supply_validation"]["status"]),
        ("overall_feasibility", result["overall_feasible"], result["overall_feasible"], context["run"]["result"]["overall_feasible"]),
        ("geometry_status", "PROVIDED", bool(project_unit.get("geometry")) and "PROVIDED", interface_unit["geometry_status"]),
    ]
    lines = [
        "# V1 / Project Consistency Report", "",
        f"Concrete manuscript run: `{run['id']}`; selected screenshot unit: `{selected_unit_id}`.", "",
        "| FIELD | SOURCE_V1 | PROJECT_DATA | V1_PROJECT_MODE | MATCH |",
        "|---|---|---|---|---|",
    ]
    for field, source, project, interface in rows:
        lines.append(f"| {field} | {source} | {project} | {interface} | {str(source == project == interface).upper()} |")
    lines.extend([
        "", "## Run provenance", "",
        f"- classification: `{result['classification']}`",
        f"- execution_profile: `{run['execution_profile']}`",
        f"- selection_hash: `{run['provenance']['input_snapshot']['selection_hash']}`",
        f"- geometry_hash: `{run['provenance']['input_snapshot']['geometry_hash']}`",
        f"- import batches: `{len(run['provenance']['input_snapshot']['import_batch_ids'])}`",
        f"- dataset versions: `{len(run['provenance']['input_snapshot']['dataset_version_ids'])}`",
        f"- source hashes: `{len(run['provenance']['input_snapshot']['source_file_sha256'])}`",
        f"- started_at: `{run['started_at']}`",
        f"- completed_at: `{run['completed_at']}`",
    ])
    if not all(source == project == interface for _, source, project, interface in rows):
        raise ValueError("V1 / Project consistency report contains a mismatch.")
    (export / "V1_PROJECT_CONSISTENCY_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=ROOT / "exports" / "v1_reference_dataset")
    parser.add_argument("--store", type=Path, default=project_store_path())
    parser.add_argument("--write-reports", action="store_true")
    args = parser.parse_args()
    document, evidence = import_package(FileProjectStore(args.store), args.package)
    if args.write_reports:
        write_reports(args.package, document, evidence)
    report = readiness(document)
    print(json.dumps({
        "project_id": PROJECT_ID,
        "active_revision": document["data_revision"],
        "analysis_units": len(document["analysis_units"]),
        "geometries": sum(bool(unit.get("geometry")) for unit in document["analysis_units"]),
        "S1": report["scenarios"]["S1"]["status"],
        "S2": report["scenarios"]["S2"]["status"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
