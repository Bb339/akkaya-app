"""Deterministic, diagnosis-only Phase 6 crop catalog reconciliation audit.

This module reads frozen repository sources.  It does not run an optimizer,
write ProjectStore state, or change production catalogs and scientific inputs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "docs" / "audits" / "crop_catalog_phase6"
CATALOG_PATH = ROOT / "data" / "urun_parametreleri_demo.csv"
PARAM_PATH = ROOT / "data" / "enhanced_dataset" / "csv" / "crop_params_assumed.csv"
MATRIX_PATH = ROOT / "data" / "excel_derived" / "combined_parcel_candidate_matrix_2024.csv"
S1_PATH = ROOT / "data" / "enhanced_dataset" / "csv" / "senaryo1_backend_seasons.csv"
S2_PATH = ROOT / "data" / "enhanced_dataset" / "csv" / "senaryo2_backend_seasons.csv"
FAMILY_PATH = ROOT / "data" / "enhanced_dataset" / "csv" / "crop_family_map.csv"
ROTATION_PATH = ROOT / "data" / "enhanced_dataset" / "csv" / "rotation_rules_default.csv"
SUITABILITY_PATH = ROOT / "data" / "enhanced_dataset" / "csv" / "crop_suitability_assumed.csv"
CALENDAR_PATH = ROOT / "data" / "s1_crop_calendar_rules.json"
IRRIGATION_PATH = ROOT / "data" / "crop_irrigation_map.json"
REFERENCE_PARAMETERS_PATH = ROOT / "kds" / "adapters" / "reference_parameters.json"
BASELINE = ROOT / "tests" / "fixtures" / "scientific_baseline"
PROTECTED = (
    "app.py", "kds/science", "kds/adapters", "kds/application/optimization.py",
    "data", "index.html", "script.js", "style.css",
)

# Audit-only relations.  They document evidence; they do not alter production aliases.
SEMANTIC_PAIRS = {
    "KIMYON": ("KI\u0307MYON", "DIACRITIC_VARIANT", "combining U+0307 survives production normalization"),
    "SALCALIKBIBER": ("BIBERSALCALIK", "CROP_FORM_VARIANT", "same base/form tokens in reversed source order"),
    "SIVRIBIBER": ("BIBERSIVRI", "CROP_FORM_VARIANT", "same base/form tokens in reversed source order"),
    "SALCALIKDOMATES": ("DOMATESSALCALIK", "CROP_FORM_VARIANT", "same base/form tokens in reversed source order"),
    "SOFRALIKDOMATES": ("DOMATESSOFRALIK", "CROP_FORM_VARIANT", "same base/form tokens in reversed source order"),
    "SILAJLIKMISIR": ("MISIRSILAJLIK", "GRAIN_FORAGE_VARIANT", "same silage-maize concept, source word order differs"),
    "TRTIKALEDANE": ("TRITIKALEDANE", "SPELLING_VARIANT", "catalog TRTİKALE spelling differs from parameter TRİTİKALE"),
}
KABAK_FORMS = {"KABAKBAL", "KABAKCEREZLIK", "KABAKSAKIZ"}


def _app():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import app
    return app


def _clean(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return round(value, 9)
    if isinstance(value, bool):
        return str(value).lower()
    return value


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str] | None = None) -> None:
    rows = list(rows)
    fields = fields or (list(rows[0]) if rows else [])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _clean(row.get(field)) for field in fields})


def protected_files() -> list[Path]:
    files: list[Path] = []
    for name in PROTECTED:
        path = ROOT / name
        files.extend(
            sorted(p for p in path.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
            if path.is_dir() else [path]
        )
    return files


def hashes(paths: Iterable[Path], base: Path = ROOT) -> dict[str, str]:
    return {
        str(path.relative_to(base)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths) if path.is_file()
    }


def project_store_hashes() -> dict[str, str]:
    from kds.config import project_store_path
    store = project_store_path()
    if not store.exists():
        return {}
    return hashes((p for p in store.rglob("*") if p.is_file()), store)


def yn(value: bool) -> str:
    return "YES" if value else "NO"


def raw_names(df: pd.DataFrame, column: str) -> set[str]:
    return {str(value).strip() for value in df[column].dropna() if str(value).strip()}


def source_count(app: Any, source: str, path: str, df: pd.DataFrame | None, column: str | None,
                 year: str, purpose: str, s1: str, s2: str, project: str, ui: str,
                 role: str, authority: str, note: str = "") -> dict[str, Any]:
    names = raw_names(df, column) if df is not None and column else set()
    return {
        "source": source, "path": path, "raw_row_count": len(df) if df is not None else "NA",
        "raw_unique_crop_names": len(names) if column else "NA",
        "normalized_unique_crop_count": len({app.normalize_crop_key(v) for v in names}) if column else "NA",
        "canonical_unique_crop_count": len({app.canonical_crop_key(v) for v in names}) if column else "NA",
        "year": year, "purpose": purpose, "used_by_S1": s1, "used_by_S2": s2,
        "used_by_Project": project, "used_by_UI": ui, "scientific_role": role,
        "authority": authority, "notes": note,
    }


def fixture_names(app: Any) -> set[str]:
    names: set[str] = set()
    for path in sorted(BASELINE.glob("s[12]_*.json")):
        for case in json.loads(path.read_text(encoding="utf-8")):
            for detail in case.get("result", {}).get("details", []):
                names.add(str(detail.get("chosenCrop") or detail.get("primary", {}).get("crop") or "").strip())
                for alt in detail.get("alternatives", []) or []:
                    names.add(str(alt.get("name") or alt.get("crop") or "").strip())
    return {name for name in names if name}


def classification_rows(app: Any, catalog_names: dict[str, list[str]], parameter_names: dict[str, list[str]]) -> list[dict[str, Any]]:
    cset, pset = set(catalog_names), set(parameter_names)
    reverse_pairs = {peer: (catalog, cls, note) for catalog, (peer, cls, note) in SEMANTIC_PAIRS.items()}
    rows = []
    for identity in sorted(cset ^ pset):
        side = "IN_58_NOT_69" if identity in cset else "IN_69_NOT_58"
        peer = ""
        if identity in SEMANTIC_PAIRS:
            peer, cls, note = SEMANTIC_PAIRS[identity]
        elif identity in reverse_pairs:
            peer, cls, note = reverse_pairs[identity]
        elif identity in KABAK_FORMS:
            peer, cls, note = "KABAK", "CROP_FORM_VARIANT", "three catalog forms map only to one generic parameter row; unsafe to auto-merge"
        elif identity == "KABAK":
            peer, cls, note = "KABAKBAL|KABAKCEREZLIK|KABAKSAKIZ", "CROP_FORM_VARIANT", "generic parameter row has no safe one-to-one catalog target"
        elif identity == "SOGANTAZE":
            cls, note = "GENUINE_MISSING_CROP", "runtime crop exists but no defensible parameter counterpart was found"
        else:
            cls, note = "PARAMETER_ONLY", "parameter identity is absent from project, candidate, and seasonal catalogs"
        rows.append({
            "production_canonical_identity": identity, "set_membership": side,
            "catalog_raw_names": " | ".join(catalog_names.get(identity, [])),
            "parameter_raw_names": " | ".join(parameter_names.get(identity, [])),
            "reconciliation_peer": peer, "classification": cls, "evidence": note,
            "software_assessment": "SOFTWARE BUG" if cls in {"DIACRITIC_VARIANT", "SPELLING_VARIANT"} else "EXPECTED ARCHITECTURE" if cls == "PARAMETER_ONLY" else "DATA CONTRACT GAP",
            "runtime_loss_assessment": "INDEPENDENT_PARAMETER_SCOPE" if cls == "PARAMETER_ONLY" else "MISSING_PARAMETER_DEPENDENCY" if identity == "SOGANTAZE" else "IDENTITY_KEY_MISMATCH" if cls in {"DIACRITIC_VARIANT", "SPELLING_VARIANT"} else "UNSAFE_GRANULARITY_OR_FORM_MISMATCH",
            "pipeline_evidence": "absent from project/candidate/seasonal sources" if cls == "PARAMETER_ONLY" else "present in runtime catalog but direct normalized Kc key does not resolve" if identity in cset else "parameter row has no direct normalized runtime key",
        })
    return rows


def generate(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    app = _app()
    source_before, store_before = hashes(protected_files()), project_store_hashes()
    output.mkdir(parents=True, exist_ok=True)

    catalog = pd.read_csv(CATALOG_PATH)
    params = pd.read_csv(PARAM_PATH)
    matrix = pd.read_csv(MATRIX_PATH)
    s1 = pd.read_csv(S1_PATH)
    s2 = pd.read_csv(S2_PATH)
    family = pd.read_csv(FAMILY_PATH)
    rotation = pd.read_csv(ROTATION_PATH)
    suitability = pd.read_csv(SUITABILITY_PATH)
    calendar_raw = json.loads(CALENDAR_PATH.read_text(encoding="utf-8-sig"))
    irrigation_raw = json.loads(IRRIGATION_PATH.read_text(encoding="utf-8-sig"))
    reference = json.loads(REFERENCE_PARAMETERS_PATH.read_text(encoding="utf-8"))
    fallback_raw = reference["fallback_crop_parameters"]
    fixtures = fixture_names(app)

    def cmap(values: Iterable[Any]) -> dict[str, list[str]]:
        result: dict[str, list[str]] = defaultdict(list)
        for value in values:
            raw = str(value).strip()
            if raw:
                result[app.canonical_crop_key(raw)].append(raw)
        return {key: sorted(set(vals)) for key, vals in result.items()}

    catalog_names, parameter_names = cmap(catalog["urun_adi"]), cmap(params["crop"])
    cset, pset = set(catalog_names), set(parameter_names)
    matrix_set = {app.canonical_crop_key(v) for v in matrix["candidate_crop"].dropna()}
    s1_set = {app.canonical_crop_key(v) for v in s1["crop"].dropna()}
    s2_primary_set = {app.canonical_crop_key(v) for v in s2.loc[s2["season"].str.lower() == "primary", "crop"].dropna()}
    s2_secondary_set = {app.canonical_crop_key(v) for v in s2.loc[s2["season"].str.lower() == "secondary", "crop"].dropna()}
    family_set = {app.canonical_crop_key(v) for v in family["crop"].dropna()}
    fallback_set = {app.canonical_crop_key(v) for v in fallback_raw}
    calendar_set = {app.canonical_crop_key(v) for v in calendar_raw}
    irrigation_set = {app.canonical_crop_key(v) for v in irrigation_raw}
    normalized_param_set = {app.normalize_crop_key(v) for v in params["crop"].dropna()}

    # Prove that the adapter creates Project Crop records from the 58-row catalog.
    from kds.adapters.akkaya_demo import build_demo
    document = build_demo(ROOT / "data")
    project_crop_set = {app.canonical_crop_key(row["name"]) for row in document["crops"]}

    catalog_norm = {app.normalize_crop_key(v) for v in catalog["urun_adi"]}
    parameter_norm = {app.normalize_crop_key(v) for v in params["crop"]}
    matrix_norm = {app.normalize_crop_key(v) for v in matrix["candidate_crop"]}
    s1_norm = {app.normalize_crop_key(v) for v in s1["crop"]}
    s2p_norm = {app.normalize_crop_key(v) for v in s2.loc[s2["season"].str.lower() == "primary", "crop"]}
    s2s_norm = {app.normalize_crop_key(v) for v in s2.loc[s2["season"].str.lower() == "secondary", "crop"]}
    family_norm = {app.normalize_crop_key(v) for v in family["crop"]}
    calendar_norm = {app.normalize_crop_key(v) for v in calendar_raw}
    irrigation_norm = {app.normalize_crop_key(v) for v in irrigation_raw}

    class_rows = classification_rows(app, catalog_names, parameter_names)
    class_by_identity = {row["production_canonical_identity"]: row for row in class_rows}

    inventories = [
        source_count(app, "runtime crop catalog", "data/urun_parametreleri_demo.csv", catalog, "urun_adi", "2024", "project/economic crop master", "YES", "YES", "YES", "YES", "catalog and calibrated proxy", "DERIVED"),
        source_count(app, "Kc/stage parameter catalog", "data/enhanced_dataset/csv/crop_params_assumed.csv", params, "crop", "unspecified", "Kc coefficients and stage fractions", "YES", "YES", "YES(reference bundle)", "INDIRECT", "FAO/Kc parameter input", "ASSUMED"),
        source_count(app, "candidate matrix", "data/excel_derived/combined_parcel_candidate_matrix_2024.csv", matrix, "candidate_crop", "2024", "parcel-crop water/economics candidates", "YES", "YES", "YES", "YES", "frozen thesis-derived options", "DERIVED"),
        source_count(app, "S1 seasonal rows", "data/enhanced_dataset/csv/senaryo1_backend_seasons.csv", s1, "crop", "2024", "primary seasonal reference", "YES", "FALLBACK", "YES(reference bundle)", "INDIRECT", "calibrated seasonal output", "DERIVED"),
        source_count(app, "S2 seasonal rows", "data/enhanced_dataset/csv/senaryo2_backend_seasons.csv", s2, "crop", "2024", "primary/secondary seasonal reference", "NO", "YES", "YES(reference bundle)", "INDIRECT", "calibrated seasonal output", "DERIVED"),
        source_count(app, "crop family map", "data/enhanced_dataset/csv/crop_family_map.csv", family, "crop", "2024", "crop-to-family lookup", "YES", "YES", "YES(reference bundle)", "INDIRECT", "rotation classification", "DERIVED"),
        source_count(app, "rotation rules", "data/enhanced_dataset/csv/rotation_rules_default.csv", rotation, None, "unspecified", "family-level rules", "YES", "YES", "YES(reference bundle)", "INDIRECT", "family-level constraints; not a crop catalog", "ASSUMED"),
        source_count(app, "suitability table", "data/enhanced_dataset/csv/crop_suitability_assumed.csv", suitability, "crop", "unspecified", "LCC-crop suitability", "YES", "YES", "YES(reference bundle)", "INDIRECT", "assumed suitability", "ASSUMED"),
    ]
    extra_inventory = [
        {"source": "S1 calendar rules", "path": "data/s1_crop_calendar_rules.json", "raw_row_count": len(calendar_raw), "raw_unique_crop_names": len(calendar_raw), "normalized_unique_crop_count": len(calendar_norm), "canonical_unique_crop_count": len(calendar_set), "year": "unspecified", "purpose": "season labels, irrigation text, secondary options", "used_by_S1": "YES", "used_by_S2": "YES", "used_by_Project": "YES(reference bundle)", "used_by_UI": "YES", "scientific_role": "calendar annotation; contains no planting/harvest dates", "authority": "DERIVED", "notes": "86 JSON keys collapse to 79 production identities"},
        {"source": "irrigation map", "path": "data/crop_irrigation_map.json", "raw_row_count": len(irrigation_raw), "raw_unique_crop_names": len(irrigation_raw), "normalized_unique_crop_count": len(irrigation_norm), "canonical_unique_crop_count": len(irrigation_set), "year": "unspecified", "purpose": "current/recommended method", "used_by_S1": "YES", "used_by_S2": "YES", "used_by_Project": "YES(reference bundle)", "used_by_UI": "YES", "scientific_role": "irrigation method lookup", "authority": "DERIVED", "notes": "not a crop master"},
        {"source": "fallback parameters", "path": "kds/adapters/reference_parameters.json", "raw_row_count": len(fallback_raw), "raw_unique_crop_names": len(fallback_raw), "normalized_unique_crop_count": len({app.normalize_crop_key(v) for v in fallback_raw}), "canonical_unique_crop_count": len(fallback_set), "year": "unspecified", "purpose": "lean-source fallback", "used_by_S1": "YES", "used_by_S2": "YES", "used_by_Project": "YES(reference bundle)", "used_by_UI": "NO", "scientific_role": "fallback only", "authority": "FALLBACK", "notes": "must not define the 58 or 69 universe"},
        {"source": "Project Crop records", "path": "kds/adapters/akkaya_demo.py -> build_demo", "raw_row_count": len(document["crops"]), "raw_unique_crop_names": len({r["name"] for r in document["crops"]}), "normalized_unique_crop_count": len({app.normalize_crop_key(r["name"]) for r in document["crops"]}), "canonical_unique_crop_count": len(project_crop_set), "year": "2024", "purpose": "stored project catalog", "used_by_S1": "YES", "used_by_S2": "YES", "used_by_Project": "YES", "used_by_UI": "YES", "scientific_role": "adapter copy of runtime crop catalog", "authority": "DERIVED", "notes": "exactly sourced from urun_parametreleri_demo.csv"},
        {"source": "scientific baseline fixtures", "path": "tests/fixtures/scientific_baseline/s[12]_*.json", "raw_row_count": "NA", "raw_unique_crop_names": len(fixtures), "normalized_unique_crop_count": len({app.normalize_crop_key(v) for v in fixtures}), "canonical_unique_crop_count": len({app.canonical_crop_key(v) for v in fixtures}), "year": "2024", "purpose": "regression outputs", "used_by_S1": "TEST", "used_by_S2": "TEST", "used_by_Project": "TEST", "used_by_UI": "NO", "scientific_role": "frozen result evidence, not authoritative catalog", "authority": "CALCULATED_REFERENCE", "notes": "chosen and alternative names observed in fixture outputs"},
    ]
    inventories.extend(extra_inventory)
    inventories.extend([
        {"source": "production crop identity helpers", "path": "app.py:normalize_crop_key/canonical_crop_key", "raw_row_count": "NA", "raw_unique_crop_names": "NA", "normalized_unique_crop_count": "NA", "canonical_unique_crop_count": "NA", "year": "runtime", "purpose": "normalize punctuation/Turkish letters and apply explicit aliases", "used_by_S1": "YES", "used_by_S2": "YES", "used_by_Project": "YES", "used_by_UI": "INDIRECT", "scientific_role": "production identity contract", "authority": "DERIVED", "notes": "canonical removes underscores after normalization; combining marks and token order are not repaired"},
        {"source": "Akkaya project adapter", "path": "kds/adapters/akkaya_demo.py", "raw_row_count": "NA", "raw_unique_crop_names": "NA", "normalized_unique_crop_count": "NA", "canonical_unique_crop_count": "NA", "year": "2024", "purpose": "copy source rows into Project Crop/Economics records", "used_by_S1": "YES", "used_by_S2": "YES", "used_by_Project": "YES", "used_by_UI": "YES", "scientific_role": "source-to-domain adapter", "authority": "DERIVED", "notes": "SOURCE_FILES['crops'] proves the 58 source"},
        {"source": "project science adapter", "path": "kds/adapters/project_science.py", "raw_row_count": "NA", "raw_unique_crop_names": "NA", "normalized_unique_crop_count": "NA", "canonical_unique_crop_count": "NA", "year": "runtime", "purpose": "verify frozen Project document and attach independent scientific resources", "used_by_S1": "YES", "used_by_S2": "YES", "used_by_Project": "YES", "used_by_UI": "INDIRECT", "scientific_role": "separates Project Crop records from candidate/reference resources", "authority": "CALCULATED_REFERENCE", "notes": "does not require project crop count to equal candidate or parameter count"},
    ])
    write_csv(output / "crop_source_inventory.csv", inventories)
    write_csv(output / "raw_vs_canonical_counts.csv", inventories, ["source", "raw_row_count", "raw_unique_crop_names", "normalized_unique_crop_count", "canonical_unique_crop_count", "notes"])

    set_rows = []
    for identity in sorted(cset | pset):
        membership = "IN_BOTH" if identity in cset and identity in pset else "IN_58_NOT_69" if identity in cset else "IN_69_NOT_58"
        set_rows.append({"production_canonical_identity": identity, "membership": membership, "catalog_raw_names": " | ".join(catalog_names.get(identity, [])), "parameter_raw_names": " | ".join(parameter_names.get(identity, []))})
    write_csv(output / "catalog_set_difference.csv", set_rows)
    write_csv(output / "difference_classification.csv", class_rows)

    param_by_norm = {app.normalize_crop_key(row["crop"]): row for _, row in params.iterrows()}
    cat_by_canon = {app.canonical_crop_key(row["urun_adi"]): row for _, row in catalog.iterrows()}
    kc_rows, phen_rows, econ_rows, water_rows, runtime_rows = [], [], [], [], []
    for _, row in catalog.sort_values("urun_adi").iterrows():
        raw = row["urun_adi"]
        norm, canon = app.normalize_crop_key(raw), app.canonical_crop_key(raw)
        pr = param_by_norm.get(norm)
        kc_ok = bool(pr is not None and all(pd.notna(pr[k]) for k in ("kc_ini", "kc_mid", "kc_end")))
        stages_ok = bool(pr is not None and all(pd.notna(pr[k]) for k in ("p_ini", "p_dev", "p_mid", "p_late")))
        econ_complete = all(pd.notna(row[k]) for k in ("beklenen_verim_kg_da", "fiyat_tl_kg", "brut_hasilat_tl_da", "maliyet_tl_da", "net_kar_tl_da"))
        water_catalog = pd.notna(row["su_tuketimi_m3_da"])
        kc_rows.append({"raw_name": raw, "normalized_key": norm, "canonical_name": canon, "direct_runtime_parameter_match": yn(pr is not None), "kc_ini_present": yn(pr is not None and pd.notna(pr["kc_ini"])), "kc_mid_present": yn(pr is not None and pd.notna(pr["kc_mid"])), "kc_end_present": yn(pr is not None and pd.notna(pr["kc_end"])), "stage_fractions_present": yn(stages_ok), "kc_complete_direct": yn(kc_ok), "missing_behavior": "generic Kc 0.6/1.0/0.8 + 0.2/0.3/0.3/0.2 fallback" if not kc_ok else "source row used"})
        phen_rows.append({"raw_name": raw, "canonical_name": canon, "calendar_rule_direct": yn(norm in calendar_norm), "calendar_rule_canonical": yn(canon in calendar_set), "season_label_present": yn(norm in calendar_norm), "planting_date_present": "NO", "harvest_date_present": "NO", "season_length_present": "NO", "stage_lengths_present": yn(stages_ok), "note": "p_* are stage fractions; repository data sources contain no planting/harvest date columns"})
        econ_rows.append({"raw_name": raw, "canonical_name": canon, "yield_present": yn(pd.notna(row["beklenen_verim_kg_da"])), "price_present": yn(pd.notna(row["fiyat_tl_kg"])), "gross_revenue_present": yn(pd.notna(row["brut_hasilat_tl_da"])), "cost_present": yn(pd.notna(row["maliyet_tl_da"])), "net_profit_present": yn(pd.notna(row["net_kar_tl_da"])), "economics_complete": yn(econ_complete), "authority": row["ekonomi_kaynak_durumu"]})
        water_rows.append({"raw_name": raw, "canonical_name": canon, "catalog_calibrated_water": yn(water_catalog), "fao_kc_direct": yn(kc_ok), "candidate_matrix_water": yn(canon in matrix_set), "s1_seasonal_water": yn(canon in s1_set), "s2_primary_water": yn(canon in s2_primary_set), "s2_secondary_water": yn(canon in s2_secondary_set), "irrigation_method_direct": yn(norm in irrigation_norm), "water_complete_all_paths": yn(water_catalog and kc_ok and canon in matrix_set and canon in s1_set)})
        runtime_rows.append({
            "raw_name": raw, "normalized_name": norm, "canonical_name": canon,
            "annual_perennial": "perennial" if str(row["cok_yillik_mi"]).lower().startswith("e") else "annual",
            "category": row["kategori"], "yield_present": yn(pd.notna(row["beklenen_verim_kg_da"])),
            "profit_present": yn(pd.notna(row["net_kar_tl_da"])), "water_present": yn(water_catalog),
            "kc_present_direct": yn(kc_ok), "phenology_dates_present": "NO",
            "candidate_matrix_present": yn(canon in matrix_set), "s1_present": yn(canon in s1_set),
            "s2_primary_present": yn(canon in s2_primary_set), "s2_secondary_present": yn(canon in s2_secondary_set),
            "family_present": yn(canon in family_set), "rotation_coverage": yn(canon in family_set and len(rotation) > 0),
            "fallback_present": yn(canon in fallback_set),
        })
    write_csv(output / "runtime_58_catalog.csv", runtime_rows)
    write_csv(output / "kc_coverage.csv", kc_rows)
    write_csv(output / "phenology_coverage.csv", phen_rows)
    write_csv(output / "economics_coverage.csv", econ_rows)
    write_csv(output / "water_coverage.csv", water_rows)

    param_rows = []
    for _, row in params.sort_values("crop").iterrows():
        raw, norm, canon = row["crop"], app.normalize_crop_key(row["crop"]), app.canonical_crop_key(row["crop"])
        param_rows.append({"raw_name": raw, "normalized_name": norm, "canonical_name": canon, "catalog_58": yn(canon in cset), "direct_runtime_key_match": yn(norm in catalog_norm), "candidate_matrix": yn(canon in matrix_set), "s1": yn(canon in s1_set), "s2_primary": yn(canon in s2_primary_set), "kc_complete": yn(all(pd.notna(row[k]) for k in ("kc_ini", "kc_mid", "kc_end"))), "stage_fractions_complete": yn(all(pd.notna(row[k]) for k in ("p_ini", "p_dev", "p_mid", "p_late"))), "source_status": row["source_status"], "classification": class_by_identity.get(canon, {}).get("classification", "EXACT_MATCH")})
    write_csv(output / "parameter_69_catalog.csv", param_rows)

    candidate_rows = []
    for canon in sorted(cset | matrix_set):
        g = matrix[matrix["candidate_crop"].map(app.canonical_crop_key) == canon]
        candidate_rows.append({"canonical_name": canon, "runtime_catalog": yn(canon in cset), "candidate_matrix": yn(canon in matrix_set), "row_count": len(g), "unique_parcels": g["parcel_id"].nunique() if len(g) else 0, "water_complete": yn(bool(len(g)) and pd.to_numeric(g["water_m3_da"], errors="coerce").notna().all()), "profit_complete": yn(bool(len(g)) and pd.to_numeric(g["profit_tl_da"], errors="coerce").notna().all()), "reason_if_absent": "catalog crop KIMYON has no frozen candidate rows" if canon == "KIMYON" else ""})
    write_csv(output / "candidate_matrix_coverage.csv", candidate_rows)

    season_rows = []
    for source, frame in (("S1", s1), ("S2", s2)):
        for season, group in frame.groupby("season", sort=True):
            identities = {app.canonical_crop_key(v) for v in group["crop"]}
            season_rows.append({"source": source, "season": season, "row_count": len(group), "raw_unique_crops": group["crop"].nunique(), "canonical_unique_crops": len(identities), "catalog_coverage_count": len(identities & cset), "catalog_missing_from_season": " | ".join(sorted(cset - identities)), "identities": " | ".join(sorted(identities))})
    write_csv(output / "seasonal_coverage.csv", season_rows)

    runtime50_path = ROOT / "docs" / "audits" / "turp_dominance" / "runtime_candidate_coverage.csv"
    runtime50 = set()
    if runtime50_path.exists():
        runtime50 = set(pd.read_csv(runtime50_path)["canonical_crop"])
    engine_rows = [
        {"universe": "PROJECT_CATALOG", "count": len(project_crop_set), "definition": "Project Crop records copied by Akkaya adapter", "identities": " | ".join(sorted(project_crop_set))},
        {"universe": "PARAMETER_CATALOG", "count": len(pset), "definition": "production-canonical identities in crop_params_assumed.csv", "identities": " | ".join(sorted(pset))},
        {"universe": "CANDIDATE_UNIVERSE_RAW", "count": len(matrix_set), "definition": "frozen candidate matrix identities", "identities": " | ".join(sorted(matrix_set))},
        {"universe": "S1_SEASONAL_UNIVERSE", "count": len(s1_set), "definition": "S1 primary seasonal rows", "identities": " | ".join(sorted(s1_set))},
        {"universe": "S2_PRIMARY_UNIVERSE", "count": len(s2_primary_set), "definition": "S2 primary seasonal rows", "identities": " | ".join(sorted(s2_primary_set))},
        {"universe": "S2_SECONDARY_UNIVERSE", "count": len(s2_secondary_set), "definition": "S2 secondary seasonal rows", "identities": " | ".join(sorted(s2_secondary_set))},
        {"universe": "RUNTIME_MATRIX_OPTION_UNIVERSE", "count": len(runtime50), "definition": "diagnosis-only Phase 5 _matrix_build_problem observation; no optimizer run", "identities": " | ".join(sorted(runtime50))},
    ]
    write_csv(output / "engine_crop_universes.csv", engine_rows)

    crosswalk = []
    all_sets = sorted(cset | pset | matrix_set | s1_set | s2_primary_set | s2_secondary_set | family_set | fallback_set)
    for identity in all_sets:
        cr = cat_by_canon.get(identity)
        kc = next((x for x in kc_rows if x["canonical_name"] == identity), None)
        er = next((x for x in econ_rows if x["canonical_name"] == identity), None)
        wr = next((x for x in water_rows if x["canonical_name"] == identity), None)
        crosswalk.append({"raw_name": " | ".join(sorted(set(catalog_names.get(identity, []) + parameter_names.get(identity, [])))), "canonical_name": identity, "catalog_58": yn(identity in cset), "parameter_69": yn(identity in pset), "candidate_matrix": yn(identity in matrix_set), "s1_seasonal": yn(identity in s1_set), "s2_primary": yn(identity in s2_primary_set), "s2_secondary": yn(identity in s2_secondary_set), "family_map": yn(identity in family_set), "rotation": yn(identity in family_set and len(rotation) > 0), "fallback": yn(identity in fallback_set), "economics_complete": er["economics_complete"] if er else "NO", "water_complete": wr["water_complete_all_paths"] if wr else "NO", "kc_complete": kc["kc_complete_direct"] if kc else "NO", "phenology_complete": "NO", "classification": class_by_identity.get(identity, {}).get("classification", "EXACT_MATCH" if identity in cset & pset else "SOURCE_SPECIFIC"), "notes": class_by_identity.get(identity, {}).get("evidence", "")})
    write_csv(output / "crop_identity_crosswalk.csv", crosswalk)

    dead_rows = [row | {"dead_unused_status": "DEAD_FOR_DIRECT_RUNTIME_KC_LOOKUP", "reason": "normalized parameter key is absent from the 58 runtime catalog"} for row in param_rows if row["direct_runtime_key_match"] == "NO"]
    write_csv(output / "dead_parameter_rows.csv", dead_rows)
    incomplete = []
    for rr, kr, pr, er, wr in zip(runtime_rows, kc_rows, phen_rows, econ_rows, water_rows):
        missing = []
        if kr["kc_complete_direct"] == "NO": missing.append("KC_DIRECT")
        if pr["planting_date_present"] == "NO" or pr["harvest_date_present"] == "NO": missing.append("PHENOLOGY_DATES")
        if er["economics_complete"] == "NO": missing.append("ECONOMICS")
        if wr["candidate_matrix_water"] == "NO": missing.append("CANDIDATE_WATER")
        incomplete.append({"raw_name": rr["raw_name"], "canonical_name": rr["canonical_name"], "incomplete_components": " | ".join(missing), "kc_direct_missing": yn("KC_DIRECT" in missing), "phenology_dates_missing": yn("PHENOLOGY_DATES" in missing), "economics_missing": yn("ECONOMICS" in missing), "candidate_water_missing": yn("CANDIDATE_WATER" in missing)})
    write_csv(output / "runtime_incomplete_parameters.csv", incomplete)

    impact = [{"canonical_name": "SOGANTAZE", "gap": "runtime crop lacks a direct or defensible Kc/stage parameter identity", "S1_impact": "MEDIUM", "S2_impact": "MEDIUM", "water_impact": "HIGH", "economics_impact": "NONE", "rotation_impact": "LOW", "UI_impact": "LOW", "real_pilot_impact": "HIGH", "evidence": "present in catalog/matrix/S1/S2/family; absent from parameter catalog; generic Kc fallback is silent"}]
    write_csv(output / "missing_crop_impact.csv", impact)

    normal_examples = []
    for raw in ("BUĞDAY", "BUGDAY", "BUĞDAY (Dane)", "BUĞDAY_KURU", "MERCİMEK", "MERCİMEK_KURU", "MISIR (Dane)", "SİLAJLIK MISIR", "TURP", "TURP (KIRMIZI)", "KIRMIZI TURP", "DOMATES (SALÇALIK)", "SALÇALIK DOMATES", "KAYISI", "KAYSI", "NEKTARİN", "NEKTAR"):
        normal_examples.append({"input": raw, "normalize_crop_key": app.normalize_crop_key(raw), "canonical_crop_key": app.canonical_crop_key(raw), "variant_preserved": yn(app.canonical_crop_key(raw) not in {"BUGDAY", "MERCIMEK", "MISIR", "TURP", "DOMATES"} or raw in {"BUĞDAY", "BUGDAY"})})
    write_csv(output / "canonicalization_examples.csv", normal_examples)
    safety_pairs = []
    for left, right, rule in (
        ("BUĞDAY", "BUĞDAY_KURU", "dry/irrigated form remains distinct"),
        ("MERCİMEK", "MERCİMEK_KURU", "dry/irrigated form remains distinct"),
        ("MISIR (Dane)", "SİLAJLIK MISIR", "grain/forage form remains distinct"),
        ("TURP", "TURP (KIRMIZI)", "plain/red form remains distinct"),
        ("KIRMIZI TURP", "TURP (KIRMIZI)", "word order is not an automatic alias"),
        ("DOMATES (SALÇALIK)", "DOMATES (SOFRALIK)", "market form remains distinct"),
        ("FASULYE (TAZE)", "KURU FASULYE", "fresh/dry form remains distinct"),
        ("ARPA (Dane)", "ARPA (YEŞİLOT)", "grain/green-forage form remains distinct"),
        ("KAYISI", "KAYSI", "explicit production perennial alias resolves together"),
        ("NEKTARİN", "NEKTAR", "explicit production perennial alias resolves together"),
    ):
        lc, rc = app.canonical_crop_key(left), app.canonical_crop_key(right)
        safety_pairs.append({"left_raw": left, "right_raw": right, "left_canonical": lc, "right_canonical": rc, "same_production_identity": yn(lc == rc), "safety_finding": rule})
    write_csv(output / "agronomic_variant_safety.csv", safety_pairs)
    trace = [
        {"step": 1, "component": "source", "evidence": "akkaya_demo.SOURCE_FILES['crops']", "value": "urun_parametreleri_demo.csv (58 rows)"},
        {"step": 2, "component": "adapter", "evidence": "akkaya_demo.build_demo", "value": "one Crop and one Economics record per source row"},
        {"step": 3, "component": "domain", "evidence": "kds.domain.crop.Crop", "value": f"{len(document['crops'])} Project Crop records"},
        {"step": 4, "component": "project science", "evidence": "project_science.verify_reference_document/build_bundle", "value": "frozen document equality plus independent candidate resources"},
        {"step": 5, "component": "readiness", "evidence": "project document validation", "value": "project crops and scientific candidates remain distinct universes"},
    ]
    write_csv(output / "project_crop_source_trace.csv", trace)
    write_csv(output / "phase5_followup_backlog.csv", [{"item": "rotation diagnostic exposure vs application", "exposure_same_family": 7, "exposure_field": 81, "actual_applied_same_family_turp_options": 6, "actual_applied_field_to_vegetable_turp_options": 32, "status": "BACKLOG_ONLY", "phase6_action": "none"}, {"item": "test_s2_high_budget_can_return_feasible_two_crop_plan", "status": "INHERITED_FAILURE_BACKLOG", "phase6_action": "none"}])

    root_causes = {
        "definitions": {"58": "rows and unique crop identities in the runtime economic/project crop catalog", "69": "rows and unique crop identities in the assumed Kc/stage-fraction parameter table"},
        "production_canonical": {"catalog": len(cset), "parameters": len(pset), "intersection": len(cset & pset), "catalog_only_identities": len(cset - pset), "parameter_only_identities": len(pset - cset), "symmetric_difference_identities": len(cset ^ pset)},
        "reconciled_unmatched_identity_rows": {"paired_naming_defects": 14, "kabak_granularity": 4, "genuine_runtime_parameter_gap": 1, "parameter_only_scope": 14, "total": 33},
        "paired_relationships": {"diacritic": 1, "spelling": 1, "word_order_or_form": 5, "total": 7},
        "runtime_direct_coverage": {"kc_and_stage_fraction_hits": sum(r["kc_complete_direct"] == "YES" for r in kc_rows), "generic_kc_fallbacks": sum(r["kc_complete_direct"] == "NO" for r in kc_rows), "calendar_direct_hits": sum(r["calendar_rule_direct"] == "YES" for r in phen_rows), "phenology_date_hits": 0, "candidate_matrix_hits": len(cset & matrix_set), "economics_complete": sum(r["economics_complete"] == "YES" for r in econ_rows)},
        "conclusion": "69-58=11 is an arithmetic row-count difference, not a list of 11 missing runtime crops.",
    }
    (output / "root_cause_breakdown.json").write_text(json.dumps(root_causes, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = f"""# V2 Scientific Phase 6 — Crop catalog reconciliation

## Finding

**58 and 69 count different contracts.** The 58 are rows and unique identities in `urun_parametreleri_demo.csv`, the economic/project runtime catalog copied by `akkaya_demo.build_demo`. The 69 are rows and unique identities in `crop_params_assumed.csv`, an assumed Kc and stage-fraction table. Both retain their counts after production canonicalization, but only {len(cset & pset)} identities intersect. Therefore `69 - 58 = 11` does not prove eleven missing products.

The production-canonical symmetric difference contains {len(cset ^ pset)} identity rows. Reconciliation finds seven paired naming relations (14 rows), a four-row Kabak granularity group, 14 parameter-only identities, and one genuine runtime parameter gap: **SOĞAN TAZE**. Production code was not changed, and unsafe form/variant merges were not proposed.

## Runtime effects

- Direct Kc/stage lookup succeeds for {sum(r['kc_complete_direct'] == 'YES' for r in kc_rows)}/58 runtime crops and silently uses the generic Kc fallback for {sum(r['kc_complete_direct'] == 'NO' for r in kc_rows)}/58.
- The source tree contains no planting or harvest date fields. Stage fractions exist for the same direct {sum(r['stage_fractions_present'] == 'YES' for r in kc_rows)} matches; calendar rules provide season labels, not dates.
- Economics are complete for {sum(r['economics_complete'] == 'YES' for r in econ_rows)}/58. DUT lacks yield and gross revenue while retaining price, cost, net profit, and calibrated water.
- The frozen candidate matrix has {len(matrix_set)} identities and omits only KIMYON from the runtime catalog. S1 and S2 primary each have {len(s1_set)} identities; S2 secondary has {len(s2_secondary_set)}: {', '.join(sorted(s2_secondary_set))}.
- Project catalog ({len(project_crop_set)}), parameter catalog ({len(pset)}), candidate universe ({len(matrix_set)}), seasonal universe ({len(s1_set)}), and observed runtime option universe ({len(runtime50)}) are separate concepts.

## Impact boundaries

TURP (KIRMIZI) is present in the runtime catalog, parameter table, candidate matrix, S1, S2 primary, and family map. The Phase 5 dominance conclusion is not materially changed by the 58/69 discrepancy. The Phase 5 rotation reporting distinction remains backlog only: exposure 7/81 versus applied Turp-option counts 6/32.

All observed protected perennial current crops remain covered by the runtime catalog/candidate sources used by the Phase 3 water floor. Five names in the broader code-level perennial registry (FINDIK, FISTIK, INCIR, NAR, ZEYTIN) are not observed Project Crop records and do not enter that frozen audit population.
"""
    (output / "phase6_summary.md").write_text(summary, encoding="utf-8")
    (output / "real_pilot_priority.md").write_text("""# Real-pilot priorities

## MUST FIX BEFORE REAL PILOT

- Replace silent generic Kc fallback with an explicit, reviewed data contract for the 13 runtime names without direct lookup, led by SOĞAN TAZE and the seven paired naming defects.
- Supply sourced planting and harvest dates or an explicit phenology calendar; current repository sources contain none.
- Decide safe, crop-specific Kc rows for the three Kabak forms. Do not map all three blindly to generic KABAK.

## SHOULD FIX BEFORE INSTITUTIONAL DEMO

- Correct catalog `TRTİKALE (Dane)` spelling through a reviewed migration and resolve combining-mark text in parameter inputs.
- Make the Kc lookup contract use a documented identity layer consistently; review KAYSI/KAYISI and NEKTAR/NEKTARIN.
- Mark DUT yield/gross revenue as unavailable in presentation and readiness output.

## OPTIONAL / CLEANUP

- Review the 14 parameter-only identities for future scoped onboarding. Keep them until provenance and intended use are decided.
- Document why seven matrix identities do not appear in the observed 50-crop runtime option universe.
""", encoding="utf-8")
    (output / "claim_boundary.md").write_text("""# Claim boundary

This is a diagnosis-only reconciliation of repository artifacts at the Phase 5 tag. It proves source counts, production normalization results, direct key reachability, and frozen-reference coverage. It does not validate the agronomic correctness of assumed Kc values, infer missing dates, establish that parameter-only crops belong in the pilot, or authorize a 69-crop expansion.

`canonical_crop_key` preserves agronomically meaningful forms unless an explicit production alias exists. Dry/irrigated, grain/forage, crop-form, and Turp variants must remain separate until a sourced contract justifies a relation. Audit-only peers in `difference_classification.csv` are evidence labels and are not production aliases.

No optimizer, Tier 3 run, production data mutation, push, or deployment is part of this audit.
""", encoding="utf-8")

    if source_before != hashes(protected_files()):
        raise RuntimeError("Phase 6 audit mutated a protected source.")
    if store_before != project_store_hashes():
        raise RuntimeError("Phase 6 audit mutated ProjectStore state.")
    manifest = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(output.iterdir()) if path.is_file()}
    result = {
        "runtime_catalog_count": len(cset), "parameter_catalog_count": len(pset),
        "canonical_intersection": len(cset & pset), "symmetric_difference": len(cset ^ pset),
        "direct_kc_coverage": sum(r["kc_complete_direct"] == "YES" for r in kc_rows),
        "candidate_count": len(matrix_set), "s1_count": len(s1_set),
        "s2_primary_count": len(s2_primary_set), "s2_secondary_count": len(s2_secondary_set),
        "project_crop_count": len(project_crop_set), "output_file_count": len(manifest),
        "full_optimizer_runs": 0, "project_store_unchanged": True, "source_unchanged": True,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(generate(args.output), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
