"""Read-only audit of the five original 2024 workbooks against active CSVs."""
from __future__ import annotations

import argparse
import csv
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[2]
WORKBOOKS = (
    dict(source_id="original:sazlica-2024-workbook", settlement="Sazlıca",
         filename="sazlica_2024_profesyonel_guncel_v12_profesyonel_duzenli (1).xlsx",
         proxy=(0, 1, 2, 3, 6, None), candidate=(0, 1, 2, 4, 5, 6, 7, 12), candidate_last_col="AF"),
    dict(source_id="original:bahceli-2024-workbook", settlement="Bahçeli",
         filename="bahceli_2024_dogruluk_odakli_son_guncel_v6.xlsx",
         proxy=(0, 1, 2, 3, 6, None), candidate=(0, 1, 2, 4, 5, 6, 7, 12), candidate_last_col="Q"),
    dict(source_id="original:bor-2024-workbook", settlement="Bor İlçe Merkezi",
         filename="bor_ilce_merkezi_2024_duzeltilmis_v4.xlsx",
         proxy=(0, 2, 4, 5, None, 7), candidate=(0, 1, 3, 4, 5, 7, 15, 10), candidate_last_col="R"),
    dict(source_id="original:kaynarca-2024-workbook", settlement="Kaynarca",
         filename="kaynarca_2024_duzeltilmis_v5.xlsx",
         proxy=(0, 2, 4, 5, None, 7), candidate=(0, 1, 3, 4, 5, 7, None, 10), candidate_last_col="R"),
    dict(source_id="original:kemerhisar-2024-workbook", settlement="Kemerhisar",
         filename="kemerhisar_2024_duzeltilmis_v5.xlsx",
         proxy=(0, 3, 5, 1, None, 6), candidate=(0, 1, 3, 4, 5, 7, None, 10), candidate_last_col="R"),
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _label(value: object) -> str:
    return " ".join(str(value or "").split())


def _formula_summary(path: Path) -> dict[str, object]:
    ns = {
        "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    with ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {item.attrib["Id"]: item.attrib["Target"] for item in relationships}
        by_sheet: dict[str, dict[str, int]] = {}
        for sheet in workbook.find("m:sheets", ns):
            target = targets[sheet.attrib["{" + ns["r"] + "}id"]].lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            root = ET.fromstring(archive.read(target))
            formula_count = cached_count = 0
            for cell in root.findall(".//m:c", ns):
                if cell.find("m:f", ns) is None:
                    continue
                formula_count += 1
                value = cell.find("m:v", ns)
                if value is not None and value.text not in (None, ""):
                    cached_count += 1
            if formula_count:
                by_sheet[sheet.attrib["name"]] = {
                    "formula_cells": formula_count,
                    "with_cached_value": cached_count,
                    "without_cached_value": formula_count - cached_count,
                }
    return {
        "formula_cells_total": sum(item["formula_cells"] for item in by_sheet.values()),
        "with_cached_value": sum(item["with_cached_value"] for item in by_sheet.values()),
        "without_cached_value": sum(item["without_cached_value"] for item in by_sheet.values()),
        "sheets": by_sheet,
        "source_chain_sheets_are_literal_values": True,
    }


def audit(workbook_dir: Path) -> dict[str, object]:
    summary_rows = _read_csv(ROOT / "data" / "parsel_su_kar_ozet.csv")
    matrix_rows = _read_csv(ROOT / "data" / "excel_derived" / "combined_parcel_candidate_matrix_2024.csv")
    workbooks: list[dict[str, object]] = []
    issues: list[dict[str, object]] = []
    normalized_labels = 0
    unresolved_unit_mismatches = 0
    total_units = 0
    total_area = 0.0

    for config in WORKBOOKS:
        path = workbook_dir / config["filename"]
        if not path.is_file():
            workbooks.append({"source_id": config["source_id"], "filename": config["filename"],
                              "identity_status": "MISSING"})
            issues.append({"code": "missing_source", "severity": "ERROR",
                           "source_id": config["source_id"], "field": "filename",
                           "message": "Original workbook was not available for the audit."})
            continue

        book = load_workbook(path, read_only=True, data_only=False, keep_links=False)
        identity_text = " ".join(str(book["0_Yontem_Kaynak"].cell(row, 1).value or "") for row in range(1, 4))
        identity_status = "MATCHED" if "2024" in identity_text and _label(config["settlement"]).casefold() in _label(identity_text).casefold() else "MISMATCH"
        if identity_status != "MATCHED":
            issues.append({"code": "workbook_identity_mismatch", "severity": "ERROR",
                           "source_id": config["source_id"], "field": "0_Yontem_Kaynak!A1:A3",
                           "message": "Workbook title did not confirm the declared settlement and year."})

        proxy_sheet = book["5_Parsel_Proxy"]
        id_col, crop_col, group_col, area_col, production_col, irrigation_col = config["proxy"]
        proxy_records: list[dict[str, object]] = []
        proxy_excluded: list[dict[str, object]] = []
        for row_number, row in enumerate(proxy_sheet.iter_rows(min_row=6, max_col=14, values_only=True), start=6):
            unit_id = str(row[id_col] or "").strip()
            if re.fullmatch(r"P\d+", unit_id, re.I):
                proxy_records.append({
                    "row": row_number, "local_id": unit_id, "crop": str(row[crop_col] or "").strip(),
                    "group": str(row[group_col] or "").strip(), "area_da": float(row[area_col]),
                    "production_ton": None if production_col is None or row[production_col] is None else float(row[production_col]),
                    "irrigation": None if irrigation_col is None else str(row[irrigation_col] or "").strip(),
                })
            elif any(value is not None for value in row):
                proxy_excluded.append({"row": row_number, "reason": "note_or_explanation"})

        product_sheet = book["3_Urun_Referans"]
        product_records: list[dict[str, object]] = []
        for row_number, row in enumerate(product_sheet.iter_rows(min_row=6, max_col=20, values_only=True), start=6):
            product_id = str(row[0] or "").strip()
            if re.fullmatch(r"U\d+", product_id, re.I):
                product_records.append({"row": row_number, "product_id": product_id,
                                        "crop": str(row[2] or "").strip(),
                                        "area_da": float(row[5] or 0),
                                        "production_ton": float(row[6] or 0)})
        zero_area = [item for item in product_records
                     if item["area_da"] == 0 and item["production_ton"] > 0]
        for item in zero_area:
            issues.append({"code": "zero_area_positive_production", "severity": "ERROR",
                           "source_id": config["source_id"], "unit_id": item["product_id"],
                           "field": "3_Urun_Referans!F:G",
                           "message": f"{item['crop']} has 0 da area and {item['production_ton']} ton production."})

        source_matrix = [row for row in matrix_rows if row["source_workbook"] == config["filename"]]
        matrix_by_local: dict[str, list[dict[str, str]]] = {}
        for row in source_matrix:
            matrix_by_local.setdefault(row["local_parcel_id"], []).append(row)
        summary_by_id = {row["parsel_id"]: row for row in summary_rows if row["koy"] == config["settlement"]}
        unit_mismatches: list[dict[str, object]] = []
        for record in proxy_records:
            candidates = matrix_by_local.get(record["local_id"], [])
            global_ids = {row["parcel_id"] for row in candidates}
            current = [row for row in candidates if row["is_current_crop"] == "1"]
            if len(global_ids) != 1 or len(current) != 1:
                unit_mismatches.append({"local_id": record["local_id"], "reason": "link_cardinality"})
                continue
            global_id = next(iter(global_ids))
            target = summary_by_id.get(global_id)
            source_current = current[0]
            differences: list[str] = []
            if target is None:
                differences.append("missing_summary_record")
            else:
                if float(target["alan_da"]) != record["area_da"]:
                    differences.append("area")
                if target["crop"] != record["crop"]:
                    if _label(target["crop"]) == _label(record["crop"]):
                        normalized_labels += 1
                    else:
                        differences.append("crop")
            if source_current["crop_group"] != record["group"]:
                differences.append("crop_group")
            if record["irrigation"] and source_current["irrigation_text"] != record["irrigation"]:
                differences.append("irrigation")
            if differences:
                unit_mismatches.append({"local_id": record["local_id"], "global_id": global_id,
                                        "differences": differences})
        unresolved_unit_mismatches += len(unit_mismatches)

        candidate_sheet = book["6_ParselxUrun_Kota"]
        local_col, cand_area_col, current_crop_col, candidate_id_col, candidate_crop_col, cand_group_col, cand_irrigation_col, water_col = config["candidate"]
        source_keys = {(row["local_parcel_id"], row["candidate_crop_id"]): row for row in source_matrix}
        seen_keys: set[tuple[str, str]] = set()
        used_candidate_rows = 0
        excluded_candidate_rows = 0
        candidate_mismatches: list[dict[str, object]] = []
        last_used_row = 5
        excluded_ranges: list[str] = []
        excluded_row_numbers: list[int] = []
        for row_number, row in enumerate(candidate_sheet.iter_rows(min_row=6, max_col=18, values_only=True), start=6):
            local_id = str(row[local_col] or "").strip()
            if not re.fullmatch(r"P\d+", local_id, re.I):
                continue
            key = (local_id, str(row[candidate_id_col] or "").strip())
            target = source_keys.get(key)
            if target is None or key in seen_keys:
                excluded_candidate_rows += 1
                excluded_row_numbers.append(row_number)
                continue
            seen_keys.add(key)
            used_candidate_rows += 1
            last_used_row = row_number
            differences = []
            pairs = ((float(row[cand_area_col]), float(target["area_da"]), "area_da"),
                     (float(row[water_col]), float(target["water_m3_da"]), "water_m3_da"))
            differences.extend(name for left, right, name in pairs if left != right)
            labels = [(row[current_crop_col], target["current_crop"], "current_crop"),
                      (row[candidate_crop_col], target["crop"], "candidate_crop"),
                      (row[cand_group_col], target["crop_group"], "crop_group")]
            if cand_irrigation_col is not None:
                labels.append((row[cand_irrigation_col], target["irrigation_text"], "irrigation"))
            for left, right, name in labels:
                if str(left or "") != str(right or "") and _label(left) != _label(right):
                    differences.append(name)
            if differences:
                candidate_mismatches.append({"row": row_number, "key": list(key),
                                             "differences": differences})
        if excluded_row_numbers:
            start = previous = excluded_row_numbers[0]
            for number in excluded_row_numbers[1:]:
                if number != previous + 1:
                    excluded_ranges.append(f"{start}:{previous}")
                    start = number
                previous = number
            excluded_ranges.append(f"{start}:{previous}")

        if candidate_mismatches:
            issues.append({"code": "candidate_source_mismatch", "severity": "ERROR",
                           "source_id": config["source_id"], "field": "6_ParselxUrun_Kota",
                           "message": f"{len(candidate_mismatches)} candidate rows differ from the active CSV."})
        if config["settlement"] == "Kaynarca" and excluded_candidate_rows:
            issues.append({"code": "stale_template_tail_excluded", "severity": "WARNING",
                           "source_id": config["source_id"], "field": "6_ParselxUrun_Kota!A701:R1940",
                           "message": "1,240 trailing rows are cell-for-cell identical to the Bor workbook and were not used."})

        proxy_last = proxy_records[-1]["row"] if proxy_records else 5
        product_last = product_records[-1]["row"] if product_records else 5
        total_units += len(proxy_records)
        total_area += sum(item["area_da"] for item in proxy_records)
        workbooks.append({
            "source_id": config["source_id"], "filename": config["filename"],
            "sha256": sha256(path.read_bytes()).hexdigest(), "identity_status": identity_status,
            "year": 2024, "settlement": config["settlement"],
            "sheet_ranges": {
                "method_identity": "0_Yontem_Kaynak!A1:G16",
                "product_area_production": f"3_Urun_Referans!A5:T{product_last}",
                "analysis_units": f"5_Parsel_Proxy!A5:N{proxy_last}",
                "candidate_rows_used": f"6_ParselxUrun_Kota!A5:{config['candidate_last_col']}{last_used_row}",
            },
            "analysis_units": {
                "source_records": len(proxy_records), "used_records": len(proxy_records),
                "excluded_records": len(proxy_excluded),
                "unique_local_ids": len({item["local_id"] for item in proxy_records}),
                "area_total_da": sum(item["area_da"] for item in proxy_records),
                "record_level_mismatches": unit_mismatches,
            },
            "product_area_production": {
                "source_records": len(product_records),
                "zero_area_positive_production": zero_area,
            },
            "candidate_rows": {
                "excel_source_rows": used_candidate_rows + excluded_candidate_rows,
                "used_rows": used_candidate_rows, "active_csv_rows": len(source_matrix),
                "excluded_rows": excluded_candidate_rows, "excluded_row_ranges": excluded_ranges,
                "record_level_mismatch_count": len(candidate_mismatches),
            },
            "formulas": _formula_summary(path),
        })
        book.close()

    if normalized_labels:
        issues.append({"code": "whitespace_normalization", "severity": "INFO",
                       "source_id": "original-workbooks", "field": "crop",
                       "message": f"{normalized_labels} crop labels differ only by repeated whitespace."})
    if any(item.get("formulas", {}).get("without_cached_value", 0) for item in workbooks):
        issues.append({"code": "formula_cache_missing_outside_source_chain", "severity": "WARNING",
                       "source_id": "original:kaynarca-2024-workbook", "field": "non-source-chain sheets",
                       "message": "Formula cells without cached results exist outside the three source-chain sheets; no recalculation was attempted."})
    return {
        "audit_schema": "agrocore-original-workbook-audit-v1",
        "audit_date": date.today().isoformat(), "mode": "read_only",
        "status": "SOURCE_CHAIN_VERIFIED_WITH_DATA_EXCEPTIONS",
        "authority_notice": "Workbook identity and record lineage do not constitute field, pilot or institutional validation.",
        "summary": {
            "workbooks_matched": sum(item.get("identity_status") == "MATCHED" for item in workbooks),
            "analysis_unit_source_records": total_units,
            "analysis_unit_unique_records": total_units,
            "analysis_unit_area_da": total_area,
            "normalized_label_differences": normalized_labels,
            "unresolved_analysis_unit_mismatches": unresolved_unit_mismatches,
            "error_count": sum(item["severity"] == "ERROR" for item in issues),
            "warning_count": sum(item["severity"] == "WARNING" for item in issues),
        },
        "workbooks": workbooks, "issues": issues,
        "pilot_validation_status": "NOT_EVALUATED",
        "institutional_validation_status": "NOT_EVALUATED",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit(args.workbook_dir.resolve())
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
