"""Adversarial regressions for Phase 7 corrective fix 1."""
from __future__ import annotations

import csv
import io
from copy import deepcopy

import pytest

from kds.application.import_service import ImportService
from kds.application.project_service import ProjectService
from kds.application.readiness import _parameter_and_phenology_readiness
from kds.data.project_store import FileProjectStore
from kds.domain.crop_parameters import replacement_preview, resolution_for
from tools.scientific_audit.crop_identity_phenology_phase7_fix1 import generate


CROP = {"name": "TURP (KIRMIZI)", "kc_initial": None, "kc_mid": None, "kc_end": None,
        "stage_initial_days": None, "stage_development_days": None,
        "stage_mid_days": None, "stage_late_days": None, "confidence_level": "synthetic"}


@pytest.fixture
def contract(tmp_path):
    store = FileProjectStore(tmp_path / "projects")
    projects = ProjectService(store)
    projects.create(dict(id="one", name="SYNTHETIC corrective fixture", planning_year=2024,
                         annual_water_budget=1000, water_budget_unit="m3",
                         data_source_notes="SYNTHETIC not_official"))
    store.update("one", lambda document: document.update(crops=[deepcopy(CROP)]))
    return store, ImportService(store)


def _csv(values):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(values))
    writer.writeheader(); writer.writerow(values)
    return stream.getvalue().encode("utf-8")


def phenology(**changes):
    values = dict(crop_identity="TURP (KIRMIZI)", applicable_year=2024,
                  geographic_scope="project", season="PRIMARY", mode="YEAR_SPECIFIC",
                  planting_date="2024-04-15", harvest_date="2024-09-01",
                  planting_window_start="", planting_window_end="",
                  harvest_window_start="", harvest_window_end="",
                  authority_class="OFFICIAL", source="corrective_fixture",
                  source_reference="not_official", notes="SYNTHETIC")
    values.update(changes)
    return _csv(values)


def parameters(**changes):
    values = dict(crop_identity="TURP (KIRMIZI)", applicable_year=2024,
                  geographic_scope="project", kc_ini=0.2, kc_mid=0.9, kc_end=0.5,
                  stage_value_mode="FRACTIONS", p_ini=0.2, p_dev=0.3, p_mid=0.3, p_late=0.2,
                  authority_class="ASSUMED", source="corrective_fixture",
                  source_reference="not_official", notes="SYNTHETIC")
    values.update(changes)
    return _csv(values)


def upload(service, kind, content):
    return service.upload("one", kind, kind + ".csv", content, {})


def test_year_specific_same_and_cross_year_are_explicit(contract):
    _, service = contract
    same = upload(service, "crop_phenology", phenology())
    cross = upload(service, "crop_phenology", phenology(
        planting_date="2023-10-15", harvest_date="2024-06-15", notes="cross"))
    assert same["status"] == cross["status"] == "ready"
    assert same["normalized_preview"][0]["season_year_semantics"] == "SAME_CALENDAR_YEAR"
    assert cross["normalized_preview"][0]["season_year_semantics"] == "CROSSES_CALENDAR_YEAR"
    for planting, harvest in (("2024-10-15", "2024-06-15"),
                              ("2022-10-15", "2024-06-15"),
                              ("2023-10-15", "2025-06-15")):
        assert upload(service, "crop_phenology", phenology(
            planting_date=planting, harvest_date=harvest, notes=planting))["status"] == "invalid"


def test_climatological_same_year_and_wrap_are_explicit(contract):
    _, service = contract
    common = dict(mode="CLIMATOLOGICAL_WINDOW", planting_date="", harvest_date="")
    same = upload(service, "crop_phenology", phenology(**common,
        planting_window_start="04-10", planting_window_end="04-25",
        harvest_window_start="09-01", harvest_window_end="09-20", notes="same-window"))
    cross = upload(service, "crop_phenology", phenology(**common,
        planting_window_start="10-15", planting_window_end="11-15",
        harvest_window_start="06-01", harvest_window_end="07-15", notes="cross-window"))
    assert same["normalized_preview"][0]["season_year_semantics"] == "SAME_CALENDAR_YEAR"
    assert cross["normalized_preview"][0]["season_year_semantics"] == "CROSSES_CALENDAR_YEAR"
    impossible = upload(service, "crop_phenology", phenology(**common,
        planting_window_start="04-10", planting_window_end="08-01",
        harvest_window_start="07-15", harvest_window_end="09-20", notes="overlap"))
    assert impossible["status"] == "invalid"


def test_phenology_modes_are_mutually_exclusive(contract):
    _, service = contract
    mixed_dates = upload(service, "crop_phenology", phenology(planting_window_start="04-10"))
    mixed_windows = upload(service, "crop_phenology", phenology(
        mode="CLIMATOLOGICAL_WINDOW", planting_window_start="04-10", planting_window_end="04-25",
        harvest_window_start="09-01", harvest_window_end="09-20"))
    assert mixed_dates["status"] == mixed_windows["status"] == "invalid"


def test_cross_year_semantics_survive_confirmation(contract):
    store, service = contract
    batch = upload(service, "crop_phenology", phenology(
        planting_date="2023-10-15", harvest_date="2024-06-15"))
    service.confirm("one", batch["id"], acknowledge_warnings=True)
    document = store.get("one")
    pointer = "crop_phenology|2024|project"
    dataset = document["crop_parameter_data"]["datasets"][document["crop_parameter_data"]["active"][pointer]]
    assert dataset["records"][0]["season_year_semantics"] == "CROSSES_CALENDAR_YEAR"


def test_fallback_official_evidence_is_not_parameter_ready():
    row = resolution_for("KIMYON", {"KI\u0307MYON"}, legacy_direct_match=False,
                         parameter_authority="OFFICIAL")
    assert row["resolution_status"] == "REVIEWED_ALIAS"
    assert row["verified_parameter_evidence"] is True
    assert row["legacy_engine_uses_fallback"] is True
    assert row["verified_parameter_ready"] is False


def _active_dataset(dataset_id, kind, year, scope, *, verified=True):
    record = dict(runtime_crop_id="TURPKIRMIZI", parameter_crop_id="TURPKIRMIZI",
                  resolution_status="EXACT", applicable_year=year, geographic_scope=scope,
                  verified_for_pilot=verified, verified_parameter_evidence=verified,
                  mode="YEAR_SPECIFIC", planting_date=f"{year}-04-15", harvest_date=f"{year}-09-01")
    return dataset_id, {"dataset_id": dataset_id, "data_type": kind, "records": [record]}


def _readiness_document():
    return {"project": {"planning_year": 2024}, "metadata": {}, "crops": [deepcopy(CROP)],
            "crop_parameter_data": {"active": {}, "datasets": {}}}


def _install(document, kind, year, scope):
    dataset_id = f"{kind}-{year}-{scope}"
    _, dataset = _active_dataset(dataset_id, kind, year, scope)
    document["crop_parameter_data"]["datasets"][dataset_id] = dataset
    document["crop_parameter_data"]["active"][f"{kind}|{year}|{scope}"] = dataset_id


def test_wrong_year_and_scope_fail_closed():
    document = _readiness_document()
    for kind in ("crop_water_parameters", "crop_phenology"):
        _install(document, kind, 2025, "project")
    parameter, phenology, pilot = _parameter_and_phenology_readiness(document, False)
    assert pilot["status"] == "PILOT_DATA_NOT_READY"
    assert parameter["dataset_selection"]["status"] == "MISSING_PLANNING_YEAR_DATASET"
    assert phenology["dataset_selection"]["status"] == "MISSING_PLANNING_YEAR_DATASET"

    document = _readiness_document()
    for kind in ("crop_water_parameters", "crop_phenology"):
        _install(document, kind, 2024, "district-a")
    parameter, phenology, pilot = _parameter_and_phenology_readiness(document, False)
    assert pilot["status"] == "PILOT_DATA_NOT_READY"
    assert parameter["dataset_selection"]["status"] == "NON_PROJECT_SCOPE_REQUIRES_EXPLICIT_SELECTION"
    assert phenology["dataset_selection"]["status"] == "NON_PROJECT_SCOPE_REQUIRES_EXPLICIT_SELECTION"


def test_multiple_scopes_require_explicit_selection():
    document = _readiness_document()
    for kind in ("crop_water_parameters", "crop_phenology"):
        _install(document, kind, 2024, "project")
        _install(document, kind, 2024, "district-a")
    parameter, phenology, pilot = _parameter_and_phenology_readiness(document, False)
    assert pilot["status"] == "PILOT_DATA_NOT_READY"
    assert parameter["dataset_selection"]["status"] == "AMBIGUOUS_SCOPE"
    assert phenology["dataset_selection"]["status"] == "AMBIGUOUS_SCOPE"
    document["metadata"]["pilot_geographic_scope"] = "district-a"
    parameter, phenology, pilot = _parameter_and_phenology_readiness(document, False)
    assert parameter["dataset_selection"]["status"] == "SELECTED"
    assert phenology["dataset_selection"]["status"] == "SELECTED"
    assert pilot["status"] == "PILOT_DATA_NOT_READY"  # engine remains disconnected


def test_empty_runtime_catalog_fails_closed():
    document = _readiness_document(); document["crops"] = []
    _, _, pilot = _parameter_and_phenology_readiness(document, False)
    assert pilot["status"] == "PILOT_DATA_NOT_READY"
    assert "runtime crop catalog is empty" in pilot["blocking_reasons"]


def test_stage_mode_only_change_is_visible():
    record = dict(runtime_crop_id="TURPKIRMIZI", applicable_year=2024,
                  geographic_scope="project", authority_class="ASSUMED",
                  kc_ini=.2, kc_mid=.9, kc_end=.5, stage_value_mode="DAYS",
                  p_ini=.2, p_dev=.3, p_mid=.3, p_late=.2, stage_total=1.0)
    document = {"crop_parameter_data": {"active": {"crop_water_parameters|2024|project": "old"},
        "datasets": {"old": {"dataset_id": "old", "authority_class": "ASSUMED",
                               "records": [record]}}}}
    incoming = [{**record, "stage_value_mode": "FRACTIONS"}]
    preview = replacement_preview(document, "crop_water_parameters", incoming)
    assert preview["change_count"] == 1
    assert preview["changes"][0]["old_values"]["stage_value_mode"] == "DAYS"
    assert preview["changes"][0]["new_values"]["stage_value_mode"] == "FRACTIONS"


def test_kc_limits_and_stage_modes(contract):
    _, service = contract
    assert upload(service, "crop_water_parameters", parameters(kc_mid=3.01))["status"] == "invalid"
    warning = upload(service, "crop_water_parameters", parameters(kc_mid=2.5))
    assert warning["status"] == "ready"
    assert any(issue["code"] == "unusual_kc" for issue in warning["issues"])
    days = upload(service, "crop_water_parameters", parameters(
        stage_value_mode="DAYS", p_ini=15, p_dev=25, p_mid=40, p_late=20))
    assert days["status"] == "ready" and days["normalized_preview"][0]["stage_total"] == 100
    assert upload(service, "crop_water_parameters", parameters(p_late=.3))["status"] == "invalid"


def test_fix1_evidence_is_deterministic(tmp_path):
    output = tmp_path / "evidence"
    first_result = generate(output)
    first = {path.name: path.read_bytes() for path in output.iterdir()}
    second_result = generate(output)
    assert first_result == second_result
    assert first == {path.name: path.read_bytes() for path in output.iterdir()}
