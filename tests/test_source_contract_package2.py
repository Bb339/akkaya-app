"""Package 2 source contract tests use only temporary writes and read-only reference data."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from kds.adapters.project_science import build_bundle
from kds.adapters.scientific_reference import snapshot
from kds.data.project_store import FileProjectStore
from kds.science.source_contract import (
    SourceContractError,
    area_to_da,
    audit_project_document_sources,
    audit_reference_analysis_units,
    audit_reference_runtime_bindings,
    audit_source_manifest,
    audit_tabular_records,
    parse_localized_number,
    raise_for_source_errors,
)
from test_analysis_workflow import example, request_body


ROOT = Path(__file__).resolve().parents[1]
LINEAGE = ROOT / "kds" / "adapters" / "source_lineage_manifest.json"


def write_manifest(tmp_path, sources, lineage=None, target_contracts=None):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({
        "schema_version": "test-v1", "sources": sources,
        "lineage": lineage or [], "datasets": [],
        "target_contracts": target_contracts or [],
    }), encoding="utf-8")
    return path


def source_for(path, *, source_id="source", expected=None, required=True):
    return {
        "source_id": source_id, "source_type": "csv",
        "portable_path": path.name,
        "sha256": expected if expected is not None else sha256(path.read_bytes()).hexdigest(),
        "required_for_execution": required,
    }


def test_valid_source_record_binds_to_declared_target(tmp_path):
    source = tmp_path / "units.csv"
    source.write_text("id,area\nP1,10\n", encoding="utf-8")
    manifest = write_manifest(tmp_path, [source_for(source)], [{
        "lineage_id": "units-area", "source_ids": ["source"],
        "source_locator": {"kind": "csv", "columns": ["id", "area"], "record_key": "id"},
        "target": {"dataset": "units", "field": "area_da"},
        "transformation": {"function": "test.identity"},
        "source_unit": "da", "target_unit": "da", "unit_required": True,
        "data_period": "2024", "period_required": True,
        "data_nature": "DIRECT_OBSERVATION", "validation_status": "HASH_CHECKED",
    }], [{"dataset": "units", "fields": ["area_da"],
          "transformation": "test.identity"}])
    result = audit_source_manifest(tmp_path, manifest)
    assert result["status"] == "READY"
    assert result["sources"][0]["status"] == "HASH_MATCH"
    assert result["sources"][0]["portable_path"] == "units.csv"
    assert result["bindings"] == [{
        "lineage_id": "units-area", "source_id": "source",
        "target_dataset": "units", "target_fields": ["area_da"],
        "transformation": "test.identity", "status": "BOUND",
        "source_columns": ["area", "id"],
    }]


@pytest.mark.parametrize(("case", "expected_code"), [
    ("missing_column", "missing_source_column"),
    ("missing_key", "missing_record_key"),
    ("unknown_source", "unknown_lineage_source"),
    ("invalid_target", "invalid_target_mapping"),
    ("invalid_transform", "invalid_transformation_mapping"),
])
def test_invalid_declared_binding_is_rejected(tmp_path, case, expected_code):
    source = tmp_path / "units.csv"
    source.write_text("id,area\nP1,10\n", encoding="utf-8")
    source_ids = ["unknown"] if case == "unknown_source" else ["source"]
    columns = ["id", "missing"] if case == "missing_column" else ["id", "area"]
    record_key = "missing" if case == "missing_key" else "id"
    target_field = "missing" if case == "invalid_target" else "area_da"
    transformation = "wrong.loader" if case == "invalid_transform" else "test.identity"
    manifest = write_manifest(tmp_path, [source_for(source)], [{
        "lineage_id": "units-area", "source_ids": source_ids,
        "source_locator": {"kind": "csv", "columns": columns, "record_key": record_key},
        "target": {"dataset": "units", "field": target_field},
        "transformation": {"function": transformation},
        "source_unit": "da", "target_unit": "da", "unit_required": True,
        "data_period": "2024", "period_required": True,
        "data_nature": "DIRECT_OBSERVATION", "validation_status": "HASH_CHECKED",
    }], [{"dataset": "units", "fields": ["area_da"],
          "transformation": "test.identity"}])
    result = audit_source_manifest(tmp_path, manifest)
    assert any(item["code"] == expected_code and item["severity"] == "ERROR"
               for item in result["issues"])


@pytest.mark.parametrize("case", ["missing", "hash"])
def test_missing_source_and_hash_mismatch_fail_without_alternate_search(tmp_path, case):
    active = tmp_path / "declared.csv"
    alternate = tmp_path / "same-looking-alternate.csv"
    alternate.write_text("id,value\nP1,99\n", encoding="utf-8")
    if case == "hash":
        active.write_text("id,value\nP1,10\n", encoding="utf-8")
    expected = "0" * 64 if case == "hash" else "1" * 64
    manifest = write_manifest(tmp_path, [{
        "source_id": "active", "source_type": "csv", "portable_path": active.name,
        "sha256": expected, "required_for_execution": True,
    }])
    result = audit_source_manifest(tmp_path, manifest)
    expected_code = "missing_source" if case == "missing" else "source_hash_mismatch"
    assert any(item["code"] == expected_code and item["severity"] == "ERROR" for item in result["issues"])
    assert all(item["portable_path"] != alternate.name for item in result["sources"])
    with pytest.raises(SourceContractError):
        raise_for_source_errors(result)


@pytest.mark.parametrize("case", ["missing", "hash"])
def test_real_snapshot_entry_stops_on_required_source_failure(tmp_path, case):
    active = tmp_path / "declared.csv"
    alternate = tmp_path / "same-looking-alternate.csv"
    alternate.write_text("id,value\nP1,99\n", encoding="utf-8")
    if case == "hash":
        active.write_text("id,value\nP1,10\n", encoding="utf-8")
    manifest = write_manifest(tmp_path, [{
        "source_id": "active", "source_type": "csv",
        "portable_path": active.name, "sha256": "0" * 64,
        "required_for_execution": True,
    }])
    with pytest.raises(SourceContractError):
        snapshot(source_root=tmp_path, lineage_path=manifest)
    assert alternate.read_text(encoding="utf-8") == "id,value\nP1,99\n"


def test_turkish_numbers_and_area_units_are_explicit():
    assert parse_localized_number("134.919") == 134919
    assert parse_localized_number("1.234,50") == pytest.approx(1234.5)
    assert area_to_da("1.234,50", "da") == pytest.approx(1234.5)
    assert area_to_da("12,5", "ha") == pytest.approx(125)
    assert area_to_da("12.500", "m²") == pytest.approx(12.5)
    with pytest.raises(ValueError):
        area_to_da("10", None)


def test_row_unique_unit_and_area_totals_are_separate():
    records = [
        {"id": "P1", "area": "1.000", "settlement": "A"},
        {"id": "P2", "area": "2,5", "settlement": "A"},
        {"id": "TOPLAM", "area": "1.002,5", "settlement": "A"},
        {"id": "", "area": "", "settlement": ""},
    ]
    result = audit_tabular_records(records, {
        "source_id": "units", "id_field": "id", "area_field": "area",
        "area_unit": "da", "settlement_field": "settlement",
    })
    assert result["source_row_count"] == 4
    assert result["used_row_count"] == 2
    assert result["unique_unit_count"] == 2
    assert result["excluded_row_count"] == 2
    assert result["total_area_da"] == pytest.approx(1002.5)
    assert result["settlement_subtotals"]["A"]["unique_unit_count"] == 2


def test_zero_area_positive_production_remains_visible():
    result = audit_tabular_records([{"id": "P1", "area": "0", "production": "3,5"}], {
        "source_id": "production", "id_field": "id", "area_field": "area",
        "area_unit": "da", "production_field": "production",
    })
    assert any(item["code"] == "zero_area_positive_production" for item in result["issues"])


def test_observation_calculation_and_assumption_remain_distinct(tmp_path):
    source = tmp_path / "values.csv"
    source.write_text("id,value\nP1,1\n", encoding="utf-8")
    links = []
    for nature in ("DIRECT_OBSERVATION", "FORMULA_DERIVED", "ASSUMPTION"):
        links.append({
            "lineage_id": nature.lower(), "source_ids": ["source"],
            "source_locator": {"kind": "csv", "columns": ["value"], "record_key": "id"},
            "target": {"dataset": "values", "field": nature.lower()},
            "transformation": {"function": "test"}, "source_unit": "x", "target_unit": "x",
            "unit_required": True, "data_period": "2024", "period_required": True,
            "data_nature": nature, "validation_status": "HASH_CHECKED",
        })
    manifest = write_manifest(tmp_path, [source_for(source)], links)
    result = audit_source_manifest(tmp_path, manifest)
    assert not any(item["code"] == "derived_value_labeled_measured" for item in result["issues"])
    raw = json.loads(manifest.read_text(encoding="utf-8"))
    raw["lineage"][1]["validation_status"] = "MEASURED"
    manifest.write_text(json.dumps(raw), encoding="utf-8")
    result = audit_source_manifest(tmp_path, manifest)
    assert any(item["code"] == "derived_value_labeled_measured" for item in result["issues"])


def test_missing_year_and_unit_are_reported_not_inferred():
    result = audit_tabular_records([{"id": "P1", "area": "10", "year": ""}], {
        "source_id": "units", "id_field": "id", "area_field": "area",
        "area_unit": None, "year_field": "year",
    })
    assert {item["code"] for item in result["issues"]} >= {"missing_unit", "missing_year"}


def test_hash_check_never_elevates_pilot_or_institutional_validation():
    result = audit_source_manifest(ROOT, LINEAGE)
    assert result["pilot_validation_status"] == "NOT_EVALUATED"
    assert result["institutional_validation_status"] == "NOT_EVALUATED"
    assert all(item["status"] == "HASH_MATCH" for item in result["sources"] if item["required_for_execution"])


def test_old_project_audit_is_read_only_and_does_not_backfill(tmp_path):
    repository = FileProjectStore(tmp_path / "projects")
    legacy = example()
    legacy["imports"] = {}
    repository.create(legacy)
    files = sorted((tmp_path / "projects").rglob("*"))
    before = {str(path): sha256(path.read_bytes()).hexdigest() for path in files if path.is_file()}
    loaded = repository.get(legacy["project"]["id"])
    snapshot = deepcopy(loaded)
    result = audit_project_document_sources(loaded)
    after = {str(path): sha256(path.read_bytes()).hexdigest() for path in files if path.is_file()}
    assert loaded == snapshot and before == after
    assert any(item["code"] == "untraced_source_location" for item in result["issues"])


def test_real_reference_audit_reproduces_179_units_and_134919_da():
    report = audit_reference_analysis_units(ROOT, LINEAGE)
    units = report["analysis_units"]
    assert units["source_row_count"] == 179
    assert units["used_row_count"] == units["unique_unit_count"] == 179
    assert units["total_area_da"] == pytest.approx(134919.0)
    assert units["settlement_subtotals"] == {
        "Bahçeli": {"row_count": 31, "unique_unit_count": 31, "total_area_da": 19692.0},
        "Bor İlçe Merkezi": {"row_count": 43, "unique_unit_count": 43, "total_area_da": 35036.0},
        "Kaynarca": {"row_count": 23, "unique_unit_count": 23, "total_area_da": 10191.0},
        "Kemerhisar": {"row_count": 35, "unique_unit_count": 35, "total_area_da": 41102.0},
        "Sazlıca": {"row_count": 47, "unique_unit_count": 47, "total_area_da": 28898.0},
    }
    assert report["status"] in {"READY", "READY_WITH_WARNINGS"}


def test_real_loaders_apply_declared_source_bindings_without_value_changes():
    result = audit_reference_runtime_bindings(ROOT, LINEAGE)
    assert result["status"] == "READY"
    assert result["unit_binding"] == {
        "source_rows": 179, "loaded_rows": 179, "matched_keys": 179,
    }
    assert result["candidate_binding"] == {
        "source_rows": 6859, "loaded_rows": 6859, "matched_keys": 6859,
    }


def test_bundle_provenance_links_manifest_and_candidate_semantics():
    document = example()
    bundle = build_bundle(document, request_body())
    provenance = bundle.provenance.copy()
    assert provenance["source_validation"]["pilot_validation_status"] == "NOT_EVALUATED"
    assert provenance["source_lineage_manifest_sha256"] is None
    metadata = bundle.candidates[0].metadata.copy()
    assert metadata["water_value_semantics"] == "REQUIREMENT_NOT_OBSERVED_USE"
    assert metadata["source_locator_status"] == "UNTRACED"


def test_reference_bundle_preserves_manifest_record_and_water_semantics():
    import app
    from kds.adapters.akkaya_demo import build_demo

    document = build_demo(app.DATA_DIR)
    bundle = build_bundle(document, request_body())
    provenance = bundle.provenance.copy()
    assert provenance["source_lineage_manifest_sha256"] == sha256(LINEAGE.read_bytes()).hexdigest()
    assert provenance["source_validation"]["pilot_validation_status"] == "NOT_EVALUATED"
    metadata = bundle.candidates[0].metadata.copy()["_source_lineage"]
    assert metadata["source_id"] == "active:candidate-matrix"
    assert metadata["record_key"]
    assert metadata["water_value_semantics"] == "MODELED_FULL_IRRIGATION_REQUIREMENT_NOT_OBSERVED_USE"
