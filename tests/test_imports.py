import io
import json
from pathlib import Path
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import pytest
from openpyxl import Workbook
from kds.application.import_service import ImportService
from kds.application.project_service import ProjectService
from kds.data.project_store import FileProjectStore
from kds.data.repositories import ConflictError, NotFoundError


@pytest.fixture
def services(tmp_path):
    store = FileProjectStore(tmp_path)
    project = ProjectService(store)
    for name in ("one", "two"):
        project.create(dict(id=name, name=name, planning_year=2024, annual_water_budget=1000, water_budget_unit="m3"))
    return store, ImportService(store)


def upload(service, content, data_type="analysis_units", filename="input.csv", project="one", **options):
    return service.upload(project, data_type, filename, content.encode() if isinstance(content, str) else content, options)


VALID = "external_id,settlement,area_da,current_crop\nA,Example,10,Wheat\n"


def test_csv_workflow_preview_confirm_restart_and_isolation(services):
    store, service = services
    batch = upload(service, VALID)
    assert batch["status"] == "ready"
    assert batch["row_count"] == 1
    assert batch["preview_rows"][0]["values"]["external_id"] == "A"
    assert batch["normalized_preview"][0]["area_da"] == 10
    assert store.get("one")["analysis_units"] == []
    assert store.get("one")["data_revision"] == 0
    with pytest.raises(ConflictError):
        service.confirm("one", batch["id"])
    applied = service.confirm("one", batch["id"], True)
    assert applied["status"] == "applied"
    assert [h["status"] for h in applied["history"]][-2:] == ["confirmed", "applied"]
    assert FileProjectStore(store.root).get("one")["analysis_units"][0]["external_id"] == "A"
    assert store.get("two")["analysis_units"] == []
    service.confirm("one", batch["id"], True)
    assert store.get("one")["data_revision"] == 1
    with pytest.raises(ConflictError):
        service.map("one", batch["id"], batch["mapping"])
    with pytest.raises(NotFoundError):
        service.get("two", batch["id"])


def test_turkish_headers_and_decimal_separator(services):
    _, service = services
    batch = upload(service, "parsel_id;köy;alan (da);mevcut ürün\nA;Örnek;1.234,50;Buğday", decimal_separator=",")
    assert batch["status"] == "ready"
    assert batch["normalized_preview"][0]["area_da"] == 1234.5


def test_xlsx(services):
    _, service = services
    book = Workbook()
    sheet = book.active
    sheet.append(["unit_id", "village", "area_da", "crop"])
    sheet.append(["A", "Example", 12.5, "Wheat"])
    buffer = io.BytesIO()
    book.save(buffer)
    result = upload(service, buffer.getvalue(), filename="input.xlsx")
    assert result["status"] == "ready"
    assert result["normalized_preview"][0]["area_da"] == 12.5


@pytest.mark.parametrize("content", [
    VALID + "A,Example,4,Wheat\n",
    "settlement,area_da,current_crop\nExample,10,Wheat",
    VALID.replace(",10,", ",0,"), VALID.replace(",10,", ",-5,"),
    VALID.replace(",10,", ",banana,"), VALID.replace(",10,", ",nan,"),
    VALID.replace(",10,", ",inf,"), VALID.replace("\nA,", "\n,"),
    VALID.replace(",Wheat", ","), "id,id\nA,A",
    "external_id,settlement,area_da,current_crop\nA,Example,10,Wheat,extra",
])
def test_invalid_units_never_apply(services, content):
    store, service = services
    batch = upload(service, content)
    assert batch["validation_summary"]["error"] > 0
    with pytest.raises(ConflictError):
        service.confirm("one", batch["id"], True)
    assert store.get("one")["analysis_units"] == []


def test_ambiguous_mapping_and_area_unit(services):
    _, service = services
    batch = upload(service, "id,unit_id,settlement,area,crop\nA,B,Example,10,Wheat")
    assert batch["status"] == "needs_mapping"
    assert "external_id" in batch["ambiguous_mapping"]
    mapping = dict(batch["mapping"], external_id="id")
    result = service.map("one", batch["id"], mapping, {"area_unit": "da"})
    assert result["status"] == "ready"
    assert result["normalized_preview"][0]["external_id"] == "A"
    with pytest.raises(ValueError):
        service.map("one", batch["id"], {"external_id": "not-a-column"})


def test_replacement_is_atomic_and_failed_confirm_retains_old_data(services, monkeypatch):
    store, service = services
    first = upload(service, VALID)
    service.confirm("one", first["id"], True)
    second = upload(service, VALID.replace("\nA,", "\nB,"))
    before = deepcopy(store.get("one"))
    def fail(*args):
        raise OSError("disk failure")
    with monkeypatch.context() as m:
        m.setattr("kds.data.project_store.os.replace", fail)
        with pytest.raises(OSError):
            service.confirm("one", second["id"], True)
    assert store.get("one") == before
    service.confirm("one", second["id"], True)
    assert [u["external_id"] for u in store.get("one")["analysis_units"]] == ["B"]


def test_stale_preview_requires_refresh(services):
    store, service = services
    first = upload(service, VALID)
    second = upload(service, VALID.replace("\nA,", "\nB,"))
    service.confirm("one", first["id"], True)
    with pytest.raises(ConflictError):
        service.confirm("one", second["id"], True)
    service.map("one", second["id"], second["mapping"])
    service.confirm("one", second["id"], True)
    assert store.get("one")["data_revision"] == 2


def test_duplicate_upload_and_filename_sanitization(services):
    _, service = services
    result = upload(service, VALID, filename="../../input.csv")
    assert result["filename"] == "input.csv"
    assert len(result["file_hash"]) == 64
    with pytest.raises(ConflictError):
        upload(service, VALID)


@pytest.mark.parametrize("filename,content", [("x.py", b"print(1)"), ("x.csv", b""), ("x.csv", b"x" * (10 * 1024 * 1024 + 1))], ids=["extension", "empty", "oversize"])
def test_upload_limits(services, filename, content):
    store, service = services
    with pytest.raises(ValueError):
        upload(service, content, filename=filename)
    assert store.get("one")["imports"] == {}


def test_crops_missing_kc_and_confidence_preservation(services):
    store, service = services
    batch = upload(service, "ürün adı,kaynak,güven düzeyi,çok yıllık\nBuğday,Örnek,türetilmiş,Hayır", "crops")
    assert batch["status"] == "ready"
    assert any(i["code"] == "missing_kc" for i in batch["issues"])
    service.confirm("one", batch["id"], True)
    crop = store.get("one")["crops"][0]
    assert crop["confidence_level"] == "türetilmiş"
    assert crop["kc_initial"] is None and crop["perennial"] is False


@pytest.mark.parametrize("value", ["-1", "9", "banana", "nan"])
def test_invalid_kc(services, value):
    _, service = services
    batch = upload(service, f"crop_name,kc_initial\nWheat,{value}", "crops")
    assert batch["status"] == "invalid"


def test_valid_crop_and_economics_negative_profit(services):
    store, service = services
    crop = upload(service, "crop_name,kc_initial,kc_mid,kc_end,source,confidence_level\nWheat,0.3,1.2,0.5,Example,proxy", "crops")
    assert crop["validation_summary"]["warning"] == 0
    service.confirm("one", crop["id"])
    batch = upload(service, "crop_name,year,yield_per_da,net_profit_per_da,currency,source,yield_unit\nWheat,2024,300,-50,TRY,Example,kg/da", "economics")
    assert batch["status"] == "ready" and batch["validation_summary"]["warning"] == 0
    service.confirm("one", batch["id"])
    assert store.get("one")["economics"][0]["net_profit_per_da"] == -50


@pytest.mark.parametrize("yield_value,year_value", [("-1", "2024"), ("bad", "2024"), ("1", "2024.5"), ("1", "1800")])
def test_invalid_economics(services, yield_value, year_value):
    _, service = services
    batch = upload(service, f"crop_name,year,yield_per_da,net_profit_per_da\nUnknown,{year_value},{yield_value},-5", "economics")
    assert batch["validation_summary"]["error"] > 0


def test_unknown_crop_and_missing_currency_preserved(services):
    store, service = services
    batch = upload(service, "crop_name,year,yield_per_da,net_profit_per_da\nUnknown,2024,1,-5", "economics")
    assert {"unknown_crop", "missing_currency"} <= {i["code"] for i in batch["issues"]}
    service.confirm("one", batch["id"], True)
    assert store.get("one")["economics"][0]["currency"] is None


def geo(ids=("A",)):
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"unit_id": name}, "geometry": {"type": "Point", "coordinates": [34 + index, 38]}}
        for index, name in enumerate(ids)]}


def test_valid_geojson_association(services):
    store, service = services
    units = upload(service, VALID)
    service.confirm("one", units["id"], True)
    batch = upload(service, json.dumps(geo()), "geometries", "shape.geojson")
    assert batch["status"] == "ready"
    assert store.get("one")["analysis_units"][0]["geometry"] is None
    service.confirm("one", batch["id"])
    assert store.get("one")["analysis_units"][0]["geometry"]["coordinates"] == [34, 38]


@pytest.mark.parametrize("content", ["{bad", '{"type":"Feature"}', json.dumps(geo(("",))),
                                    json.dumps(geo(("A", "A"))), json.dumps(geo(("unknown",)))])
def test_invalid_geojson(services, content):
    _, service = services
    batch = upload(service, content, "geometries", "shape.geojson")
    assert batch["validation_summary"]["error"] > 0


@pytest.mark.parametrize("geometry", [{"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]},
                                      {"type": "Point", "coordinates": [500, 20]}, {"type": "Banana", "coordinates": []}])
def test_invalid_geometry_structure(services, geometry):
    _, service = services
    feature = geo()
    feature["features"][0]["geometry"] = geometry
    batch = upload(service, json.dumps(feature), "geometries", "shape.geojson")
    assert any(i["code"] == "invalid_geometry" for i in batch["issues"])


def test_duplicate_geometry(services):
    _, service = services
    features = geo(("A", "B"))
    features["features"][1]["geometry"] = features["features"][0]["geometry"]
    batch = upload(service, json.dumps(features), "geometries", "shape.geojson")
    assert any(i["code"] == "duplicate_geometry" for i in batch["issues"])


def test_concurrent_confirm_applies_once(services):
    store, service = services
    batch = upload(service, VALID)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: service.confirm("one", batch["id"], True), range(2)))
    assert all(result["status"] == "applied" for result in results)
    assert store.get("one")["data_revision"] == 1


@pytest.mark.parametrize("name,data_type", [("analysis_units", "analysis_units"), ("crop_parameters", "crops"), ("economics", "economics")])
def test_shipped_templates_are_importable(services, name, data_type):
    _, service = services
    path = Path(__file__).resolve().parents[1] / "docs/data_templates" / f"{name}_template.xlsx"
    result = upload(service, path.read_bytes(), data_type, path.name)
    assert result["row_count"] == 1
    assert result["validation_summary"]["error"] == 0
    assert result["status"] == "ready"


@pytest.mark.parametrize("content", [b"not a zip", b"PK malformed workbook"])
def test_malformed_xlsx_creates_invalid_batch(services, content):
    store, service = services
    batch = upload(service, content, filename="broken.xlsx")
    assert batch["status"] == "invalid"
    assert batch["issues"][0]["code"] == "malformed_file"
    assert store.get("one")["analysis_units"] == []


def test_formula_xlsx_rejected(services):
    _, service = services
    book = Workbook()
    book.active.append(["external_id", "settlement", "area_da", "current_crop"])
    book.active.append(["A", "Example", "=10+5", "Wheat"])
    output = io.BytesIO()
    book.save(output)
    batch = upload(service, output.getvalue(), filename="formula.xlsx")
    assert batch["status"] == "invalid"


def test_geojson_can_create_analysis_units(services):
    store, service = services
    features = geo()
    features["features"][0]["properties"].update(settlement="Example", area_da=5, current_crop="Wheat")
    batch = upload(service, json.dumps(features), "analysis_units", "units.geojson")
    assert batch["status"] == "ready"
    service.confirm("one", batch["id"], True)
    assert store.get("one")["analysis_units"][0]["geometry"]["type"] == "Point"
