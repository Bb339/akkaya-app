from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook

from kds.imports.detection import detect
from kds.application.import_service import ImportService
from kds.application.project_service import ProjectService
from kds.data.project_store import FileProjectStore
from kds.data.repositories import ConflictError
import json
import pytest


PROJECT = {"planning_year": 2025, "province_or_region": "Niğde"}


def _xlsx(sheets: list[tuple[str, list[list[object]]]]) -> bytes:
    workbook = Workbook()
    workbook.remove(workbook.active)
    for title, rows in sheets:
        sheet = workbook.create_sheet(title)
        for row in rows:
            sheet.append(row)
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def test_turkish_aliases_semicolon_bom_and_column_order_are_deterministic():
    content = ("\ufeffBİTKİ;BOYLAM;ALAN_DEKAR;KÖY;PARSELNO;ENLEM;İLGİSİZ\n"
               "Buğday;34,5;12,5;Merkez;GX-1;38,1;x\n").encode("utf-8")
    result = detect(content, "kurum_analiz_birimleri.csv", project=PROJECT)
    assert result["state"] == "AUTO_MATCHED"
    assert result["detected_data_type"] == "analysis_units"
    assert result["mapping"] == {
        "external_id": "PARSELNO", "settlement": "KÖY", "area_da": "ALAN_DEKAR",
        "current_crop": "BİTKİ", "latitude": "ENLEM", "longitude": "BOYLAM",
    }
    assert result["preview_rows"][0]["PARSELNO"] == "GX-1"


def test_unambiguous_english_and_turkish_grouped_numbers_are_parseable():
    for value in ("1,234.56", "1.234,56"):
        content = f"external_id,settlement,area_da,current_crop\nGX-1,X,\"{value}\",WHEAT\n".encode()
        result = detect(content, "analysis_units.csv", project=PROJECT)
        assert result["state"] == "AUTO_MATCHED", result


def test_partial_numeric_contamination_requires_review():
    content = b"external_id,settlement,area_da,current_crop\nGX-1,X,12,WHEAT\nGX-2,X,not-a-number,BARLEY\n"
    result = detect(content, "analysis_units.csv", project=PROJECT)
    assert result["state"] == "REVIEW_REQUIRED"
    issue = next(item for item in result["issues"] if item["code"] == "required_numeric_field_not_parseable")
    assert issue["parseable"] == 1 and issue["unparseable"] == 1


def test_workbook_skips_cover_and_empty_sheet_and_records_selection_reason():
    content = _xlsx([
        ("Kapak", [["KURUMSAL VERİ DOSYASI"], ["Talimatlar"]]),
        ("Boş", []),
        ("Analiz Birimleri", [["parsel_no", "yerleşim", "alan_da", "ürün"],
                              ["GX-1", "Merkez", 10, "Buğday"]]),
    ])
    result = detect(content, "kurum_verisi.xlsx", project=PROJECT)
    assert result["state"] == "AUTO_MATCHED"
    assert result["selected_sheet"] == "Analiz Birimleri"
    assert result["detected_data_type"] == "analysis_units"
    assert result["evidence"]["sheet_selection"]


def test_equally_plausible_workbook_sheets_fail_closed():
    header = ["external_id", "settlement", "area_da", "current_crop"]
    content = _xlsx([("Veri A", [header, ["A", "X", 1, "WHEAT"]]),
                     ("Veri B", [header, ["B", "X", 2, "BARLEY"]])])
    result = detect(content, "analysis_units.xlsx", project=PROJECT)
    assert result["state"] == "AMBIGUOUS"
    assert "ambiguous_workbook_sheet" in {item["code"] for item in result["issues"]}


def test_negative_file_states_are_explicit():
    missing = detect(b"external_id,area_da\nA,1\n", "analysis_units.csv", project=PROJECT)
    unsupported = detect(b"not parsed", "kurum_raporu.pdf", project=PROJECT)
    invalid_geojson = detect(b"{broken", "geometry.geojson", project=PROJECT)
    wrong_year = detect(
        b"planning_year,amount,unit,geographic_scope,authority_class\n2024,1,m3/year,project,MEASURED\n",
        "annual_water_supply.csv", project=PROJECT)
    assert missing["state"] == "REVIEW_REQUIRED"
    assert unsupported["state"] == "UNSUPPORTED"
    assert invalid_geojson["state"] == "INVALID"
    assert wrong_year["state"] == "REVIEW_REQUIRED"
    assert "wrong_planning_year" in {item["code"] for item in wrong_year["issues"]}


def test_irrelevant_extra_file_is_ignored_without_joining_auto_matched_package():
    result = detect(b"note,owner\nmeeting agenda,office\n", "meeting_notes.csv", project=PROJECT)
    assert result["state"] == "IGNORED_NOT_RELEVANT"
    assert result["confidence"] == 0
    assert result["detected_data_type"] is None
    assert "ignored_not_relevant" in {item["code"] for item in result["issues"]}


def test_geometry_unit_id_mismatch_is_invalid_and_cannot_be_confirmed(tmp_path):
    store = FileProjectStore(tmp_path / "projects")
    ProjectService(store).create({
        "id": "geometry-mismatch", "name": "Geometry mismatch", "planning_year": 2025,
        "annual_water_budget": 0, "water_budget_unit": "m3",
    })
    service = ImportService(store)
    units = service.upload(
        "geometry-mismatch", "analysis_units", "analysis_units.csv",
        b"external_id,settlement,area_da,current_crop\nGX-001,X,10,WHEAT\n", {},
    )
    service.confirm("geometry-mismatch", units["id"], True)
    geojson = json.dumps({
        "type": "FeatureCollection", "features": [{
            "type": "Feature", "properties": {"unit_id": "GX-999"},
            "geometry": {"type": "Point", "coordinates": [34.5, 38.0]},
        }],
    }).encode()
    batch = service.upload("geometry-mismatch", "geometries", "geometry.geojson", geojson, {})
    assert batch["status"] == "invalid"
    assert "unknown_unit" in {item["code"] for item in batch["issues"]}
    with pytest.raises(ConflictError):
        service.confirm("geometry-mismatch", batch["id"], True)
