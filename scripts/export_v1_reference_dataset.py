"""Export the frozen V1 reference inputs through the public Project Data schemas.

No values are randomized.  Every exported value is read from the same loaders or
source files used by the AKKAYA_REFERENCE provider.  The output remains reference
/ demo material and must never be described as official or field validated.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import sys
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DATA_OUTPUT = ROOT / "data" / "project_packages" / "v1_reference_dataset"
EXPORT_OUTPUT = ROOT / "exports" / "v1_reference_dataset"
ZIP_OUTPUT = ROOT / "exports" / "v1_reference_dataset.zip"
SOURCE = "V1 thesis-model reference/demo source; not official; not field validated"
YEAR = 2024


def _csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty dataset: {path.name}")
    fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _flatten(sections: dict) -> list[dict]:
    rows = []
    for section, records in sections.items():
        iterable = records.items() if isinstance(records, dict) else ((f"row-{i+1}", row) for i, row in enumerate(records))
        for identity, fields in iterable:
            for field, value in fields.items():
                if value is None or (isinstance(value, float) and pd.isna(value)):
                    continue
                kind = "boolean" if type(value) is bool else "integer" if type(value) is int else "number" if isinstance(value, float) else "text"
                rows.append({"section": section, "record_id": str(identity), "field": field,
                             "value_type": kind, "value": value, "source": SOURCE})
    return rows


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite_or_none(value):
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def _crop_param(params: pd.DataFrame, app, name: str) -> dict:
    key = app.normalize_crop_key(name)
    by_key = {app.normalize_crop_key(str(row["crop"])): row for _, row in params.iterrows()}
    if key in by_key:
        return {**by_key[key].to_dict(), "parameter_source": "direct crop_params_assumed row"}
    # These are the exact generic defaults used by app._load_crop_params_map
    # consumers when a runtime crop has no direct row.  Exporting them makes the
    # inherited fallback explicit rather than silently reading legacy state.
    return {"crop": name, "kc_ini": 0.6, "kc_mid": 1.0, "kc_end": 0.8,
            "p_ini": 0.2, "p_dev": 0.3, "p_mid": 0.3, "p_late": 0.2,
            "source_note": "explicit replay of existing V1 generic parameter fallback",
            "parameter_source": "legacy generic fallback"}


def build(destination: Path) -> dict:
    import app

    destination.mkdir(parents=True, exist_ok=True)
    parcels = app.load_parcels()
    catalog = app.load_crop_catalog()
    matrix = app.load_matrix_candidates().copy()
    frames = app.load_enhanced_frames()
    params = frames["crop_params"].copy()
    irrigation = app.load_crop_irrigation_map()

    area = sum(float(row["area_da"]) for row in parcels)
    water = sum(float(row["water_m3"]) for row in parcels)
    profit = sum(float(row["profit_tl"]) for row in parcels)
    expected = {"analysis_units": 179, "total_area_da": 134919.0, "crops": 58,
                "candidates": 6859, "current_water_m3": 100700080.81,
                "current_profit_tl": 1041499119.212}
    actual = {"analysis_units": len(parcels), "total_area_da": area, "crops": len(catalog),
              "candidates": len(matrix), "current_water_m3": water, "current_profit_tl": profit}
    for key, value in expected.items():
        if abs(float(actual[key]) - float(value)) > max(1e-6, abs(float(value)) * 1e-12):
            raise ValueError(f"V1 invariant mismatch for {key}: {actual[key]} != {value}")

    units = [{"external_id": p["id"], "settlement": p.get("village", ""), "area_da": p["area_da"],
              "current_crop": p["current_crop"], "name_or_code": p.get("name") or p["id"],
              "irrigation_method": p.get("irrigation_key", ""), "latitude": p.get("lat"),
              "longitude": p.get("lon"), "notes": SOURCE} for p in parcels]
    _csv(destination / "analysis_units.csv", units)

    crops, economics = [], []
    for item in catalog.values():
        name = item["name"]
        parameter = _crop_param(params, app, name)
        crops.append({"crop_name": name, "crop_group": item.get("category", ""),
                      "perennial": bool(item.get("isPerennial")), "kc_initial": parameter["kc_ini"],
                      "kc_mid": parameter["kc_mid"], "kc_end": parameter["kc_end"],
                      "stage_initial_days": parameter["p_ini"], "stage_development_days": parameter["p_dev"],
                      "stage_mid_days": parameter["p_mid"], "stage_late_days": parameter["p_late"],
                      "source": item.get("sourceNote") or SOURCE, "confidence_level": "reference_assumed", "active": True})
        source_yield = float(item["yieldKgPerDa"])
        economics.append({"crop_name": name, "year": YEAR,
                          "yield_per_da": source_yield / 1000.0 if math.isfinite(source_yield) else None,
                          "net_profit_per_da": item["netProfitTlPerDa"], "currency": "TRY",
                          "source": item.get("economySourceStatus") or SOURCE, "yield_unit": "ton/da"})
    _csv(destination / "crops.csv", crops)
    _csv(destination / "economics.csv", economics)
    _csv(destination / "water_budget.csv", [{"amount": expected["current_water_m3"], "unit": "m3",
                                               "kind": "calculated_reference", "source": "data/water_context.csv"}])

    candidates = []
    for _, row in matrix.iterrows():
        candidate_key = app.normalize_crop_key(str(row["candidate_crop"]))
        if candidate_key not in catalog:
            raise ValueError(f"Candidate crop is absent from the V1 catalog: {row['candidate_crop']}")
        candidates.append({"analysis_unit_id": str(row["parcel_id"]), "crop": catalog[candidate_key]["name"],
                           "water_requirement_m3_da": float(row["water_m3_da"]),
                           "profit_per_da": float(row["profit_tl_da"]), "yield_ton_da": float(row["yield_ton_da"]),
                           "allowed": True, "rotation_status": "V1_REFERENCE_MATRIX",
                           "suitability": 1.0, "risk": 0.0,
                           "source": str(row.get("source_workbook") or "combined_parcel_candidate_matrix_2024.csv")})
    _csv(destination / "candidates.csv", candidates)

    unit_parameters = {p["id"]: {"current_water_m3": float(p["water_m3"]),
                                  "current_profit": float(p["profit_tl"]),
                                  "soil_class": str((p.get("soil") or {}).get("class") or "UNKNOWN"),
                                  "parcel_type": p.get("parcel_type") or "field"} for p in parcels}
    method_eff = {str(row["method"]): float(row["typical_total_efficiency"])
                  for _, row in frames["irrigation_methods"].iterrows()}
    irrigation_rows = {}
    for item in catalog.values():
        info = irrigation.get(item["name"]) or irrigation.get(app.normalize_crop_key(item["name"])) or {}
        default = str(info.get("current") or info.get("recommended") or "sprinkler")
        recommended = str(info.get("recommended") or default)
        irrigation_rows[item["name"]] = {"default": default, "recommended": recommended,
                                          "efficiency": method_eff.get(default, method_eff.get(recommended, 0.637))}
    _csv(destination / "scientific_s1.csv", _flatten({"unit_parameters": unit_parameters, "irrigation": irrigation_rows}))

    seasonal = {}
    for name in ("s1", "s2", "parcels", "reservoir", "delivery", "crop_params", "monthly_climate",
                 "water_quality", "soil_params", "crop_suitability", "irrigation_methods"):
        frame = frames[name]
        seasonal["seasonal_resources." + name] = [{k: v for k, v in row.items() if not pd.isna(v)}
                                                   for row in frame.to_dict("records")]
    seasonal["crop_families"] = {key: {"family": value} for key, value in app.load_crop_family_map().items()}
    seasonal["rotation_rules"] = [{k: v for k, v in row.items() if not pd.isna(v)}
                                    for row in app.load_rotation_rules().to_dict("records")]
    _csv(destination / "scientific_s2.csv", _flatten(seasonal))

    response = app.app.test_client().get("/api/geojson_bundle")
    geometry_payload = response.get_json()
    features = geometry_payload["parcels"]["features"]
    for feature in features:
        props = feature.setdefault("properties", {})
        props["external_id"] = str(props.get("id") or props.get("name"))
        props["source"] = props.get("source_file") or SOURCE
        for alias in ("id", "name", "parcel_id"):
            props.pop(alias, None)
    if len(features) != 178 or "P138" in {f["properties"]["external_id"] for f in features}:
        raise ValueError("Geometry contract changed; expected 178 real features with P138 absent.")
    (destination / "geometries.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, indent=2), encoding="utf-8")

    provenance = {"source_institution": "V1 thesis-model reference sources", "source_reference": "repository source manifest",
                  "geographic_scope": "project", "authority_class": "CALCULATED_REFERENCE"}
    _csv(destination / "annual_water_supply.csv", [{"planning_year": YEAR, "amount": expected["current_water_m3"],
                                                      "unit": "m3/year", **provenance}])
    reservoir = frames["reservoir"].copy(); reservoir["month"] = pd.to_datetime(reservoir["month"])
    reservoir = reservoir[reservoir["month"].dt.year == YEAR]
    monthly = [{"planning_year": YEAR, "month": row["month"].strftime("%Y-%m"),
                "amount": float(row["irrigation_m3_baseline"]), "unit": "m3/month", **provenance}
               for _, row in reservoir.iterrows()]
    _csv(destination / "monthly_water_supply.csv", monthly)
    delivery = frames["delivery"].copy(); delivery["month"] = pd.to_datetime(delivery["month"])
    delivery = delivery[delivery["month"].dt.year == YEAR]
    _csv(destination / "delivery_capacity.csv", [{"planning_year": YEAR, "month": row["month"].strftime("%Y-%m"),
        "capacity": float(row["max_delivery_m3_assumed"]), "source_unit": "m3/month", "canonical_unit": "m3/month",
        "capacity_basis": "DERIVED_PROXY", **provenance} for _, row in delivery.iterrows()])
    _csv(destination / "environmental_release.csv", [{"planning_year": YEAR, "release_form": "ratio", "value": 0.10,
        "source_unit": "ratio", "canonical_unit": "ratio", **provenance}])
    current = matrix[matrix["is_current_crop"] == 1]
    efficiency = float((current["total_efficiency"] * current["area_da"]).sum() / current["area_da"].sum())
    _csv(destination / "conveyance_efficiency.csv", [{"planning_year": YEAR, "period": "annual", "efficiency": efficiency,
        "scope": "project", "authority_class": "CALCULATED_REFERENCE", "source_institution": provenance["source_institution"],
        "source_reference": "area-weighted current-pattern total_efficiency"}])
    perennial = [{"planning_year": YEAR, "crop": item["name"], "value": item["waterPerDa"],
                  "source_unit": "m3/da", "canonical_unit": "m3/da", "geographic_scope": "project",
                  "confidence": "REFERENCE_ASSUMED", "method": "V1 catalog gross requirement",
                  "authority_class": "CALCULATED_REFERENCE", "source_institution": provenance["source_institution"],
                  "source_reference": "data/urun_parametreleri_demo.csv"}
                 for item in catalog.values() if item.get("isPerennial")]
    _csv(destination / "perennial_irrigation_requirement.csv", perennial)

    common = {"planning_year": YEAR, "observation_year": YEAR, "authority_class": "CALCULATED_REFERENCE",
              "source_institution": provenance["source_institution"], "source_reference": "data/urun_parametreleri_demo.csv",
              "currency": "TRY", "geographic_scope": "project", "crop_scope": "catalog"}
    _csv(destination / "crop_yield.csv", [{"crop": i["name"], "yield_value": i["yieldKgPerDa"] / 1000,
        "yield_unit": "ton/da", **common} for i in catalog.values()
        if math.isfinite(float(i["yieldKgPerDa"]))])
    _csv(destination / "crop_sale_price.csv", [{"crop": i["name"], "price": i["priceTlPerKg"] * 1000,
        "price_unit": "TRY/ton", "price_period": "2024 reference", **common} for i in catalog.values()])
    _csv(destination / "crop_cost_components.csv", [{"crop": i["name"], "cost_category": "other",
        "amount": i["costTlPerDa"], "unit": "TRY/da", **common} for i in catalog.values()])
    _csv(destination / "crop_net_profit.csv", [{"crop": i["name"], "net_profit_per_da": i["netProfitTlPerDa"],
        "calculation_method": "DIRECT_SOURCE", "gross_revenue_per_da": _finite_or_none(i["grossRevenueTlPerDa"]),
        "total_cost_per_da": _finite_or_none(i["costTlPerDa"]), "support_payment_per_da": _finite_or_none(i["supportTlPerDa"]),
        "calculation_formula": "direct replay of source catalog net_profit_tl_da", **common} for i in catalog.values()])
    seasonal_economics = []
    for _, row in frames["s2"].iterrows():
        area_da = float(row["area_da"])
        seasonal_economics.append({"analysis_unit_id": row["parcel_id"], "crop": row["crop"], "season": row["season"],
            "yield_value": None, "yield_unit": "ton/da", "price": None, "price_unit": "TRY/ton",
            "cost": None, "cost_unit": "TRY/da", "net_profit": float(row["profit_tl"]) / area_da,
            "net_profit_unit": "TRY/da", **common})
    _csv(destination / "seasonal_economics.csv", seasonal_economics)
    water_parameters = []
    for item in catalog.values():
        p = _crop_param(params, app, item["name"])
        stage_total = sum(float(p[field]) for field in ("p_ini", "p_dev", "p_mid", "p_late"))
        stage_mode = "FRACTIONS" if math.isclose(stage_total, 1.0, rel_tol=0.0, abs_tol=1e-9) else "DAYS"
        water_parameters.append({"crop_identity": item["name"], "applicable_year": YEAR, "geographic_scope": "project",
            "kc_ini": p["kc_ini"], "kc_mid": p["kc_mid"], "kc_end": p["kc_end"], "stage_value_mode": stage_mode,
            "p_ini": p["p_ini"], "p_dev": p["p_dev"], "p_mid": p["p_mid"], "p_late": p["p_late"],
            "authority_class": "ASSUMED", "source": "data/enhanced_dataset/csv/crop_params_assumed.csv",
            "source_reference": str(p.get("source_note") or SOURCE)})
    _csv(destination / "crop_water_parameters.csv", water_parameters)
    calendar = app.load_s1_crop_calendar_rules()
    phenology = [{"crop_identity": i["name"], "applicable_year": YEAR, "geographic_scope": "project",
                  "season": "PRIMARY", "mode": "REFERENCE_RULE", "authority_class": "ASSUMED",
                  "source": "data/s1_crop_calendar_rules.json", "source_reference": SOURCE,
                  "notes": json.dumps(calendar.get(i["name"], {}), ensure_ascii=False)} for i in catalog.values()]
    _csv(destination / "crop_phenology.csv", phenology)

    data_files = sorted(p for p in destination.iterdir() if p.suffix in {".csv", ".geojson"})
    if len(data_files) != 21:
        raise ValueError(f"Expected 21 data files, produced {len(data_files)}")
    manifest = {p.name: {"sha256": _sha(p), "bytes": p.stat().st_size} for p in data_files}
    (destination / "SOURCE_MANIFEST.json").write_text(json.dumps({"classification": "REFERENCE_DEMO",
        "warning": "NOT AN OFFICIAL WATER ALLOCATION OR FIELD VALIDATION", "invariants": actual,
        "source_manifest": json.loads((ROOT / "kds/adapters/reference_manifest.json").read_text(encoding="utf-8"))},
        ensure_ascii=False, indent=2), encoding="utf-8")
    (destination / "DATASET_HASHES.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"invariants": actual, "files": manifest, "geometry_count": len(features), "missing_geometry": ["P138"]}


def main() -> None:
    for target in (DATA_OUTPUT, EXPORT_OUTPUT):
        if target.exists():
            shutil.rmtree(target)
    report = build(DATA_OUTPUT)
    shutil.copytree(DATA_OUTPUT, EXPORT_OUTPUT)
    readme = """# V1 Reference Dataset

**REFERENCE / DEMO DATA — NOT AN OFFICIAL WATER ALLOCATION OR FIELD VALIDATION.**

This deterministic 21-file package reconstructs the inputs used by the V1 thesis-model reference workflow. Create project `v1-reference-demo` (`V1 Reference Dataset`, planning year 2024, data classification `reference_demo`), upload all CSV/GeoJSON data files through Bulk Data Upload, and explicitly confirm them in package order. The resulting active revision is 21.

P138 intentionally has no fabricated geometry. Its scientific inputs remain executable and its map state is explicitly `Geometry not provided`. The Esri/Leaflet basemap is a visualization layer and is not PROJECT_DATA.

After import:

- Projects: `/projects#project=v1-reference-demo&section=readiness`
- V1: `/?provider=PROJECT_DATA&project_id=v1-reference-demo&revision=21&seed=123`
"""
    (EXPORT_OUTPUT / "README.md").write_text(readme, encoding="utf-8")
    from scripts.import_v1_reference_dataset import MemoryProjectRepository, import_package, write_reports
    document, evidence = import_package(MemoryProjectRepository(), EXPORT_OUTPUT)
    write_reports(EXPORT_OUTPUT, document, evidence)
    with zipfile.ZipFile(ZIP_OUTPUT, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(EXPORT_OUTPUT.rglob("*")):
            if path.is_file(): archive.write(path, path.relative_to(EXPORT_OUTPUT.parent))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
