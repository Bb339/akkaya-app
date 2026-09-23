"""Synthetic-only acceptance tests for the future water replacement contract."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from kds.application.import_service import ImportService
from kds.application.project_service import ProjectService
from kds.application.readiness import readiness
from kds.data.project_store import FileProjectStore
from kds.data.repositories import ConflictError
from kds.domain.water_data import AuthorityClass, authority, authority_rank, resolve_perennial_requirement


HEADER_SOURCE = "source_institution,source_reference,authority_class"


@pytest.fixture
def services(tmp_path):
    store = FileProjectStore(tmp_path / "projects")
    projects = ProjectService(store)
    for project_id in ("one", "two"):
        projects.create(dict(id=project_id, name="Synthetic contract test", planning_year=2024,
                             annual_water_budget=1000, water_budget_unit="m3",
                             data_source_notes="synthetic_test_fixture"))
    return store, ImportService(store)


def upload(service, data_type, content, project="one"):
    return service.upload(project, data_type, f"{data_type}.csv", content.encode(), {})


def annual(amount=1000, authority_class="DERIVED_PROXY", year=2024):
    return (f"planning_year,amount,unit,{HEADER_SOURCE}\n"
            f"{year},{amount},m3/year,synthetic_test_fixture,synthetic_test_fixture,{authority_class}\n")


def monthly(data_type="monthly_water_supply", authority_class="DERIVED_PROXY", delta=0,
            source_unit="m3/month", canonical_unit="m3/month", extra_header="", extra_value=""):
    amount_name = "capacity" if data_type == "delivery_capacity" else "amount"
    headers = ["planning_year", "month", amount_name]
    if data_type == "delivery_capacity":
        headers += ["source_unit", "canonical_unit", "capacity_basis"]
    else:
        headers += ["unit"]
    if extra_header:
        headers += extra_header.split(",")
    headers += HEADER_SOURCE.split(",")
    rows = [",".join(headers)]
    for month in range(1, 13):
        row = ["2024", f"2024-{month:02d}-15", str(100 + month + delta)]
        if data_type == "delivery_capacity":
            basis = "official_allocation" if authority_class == "OFFICIAL_ALLOCATION" else "measured_delivery" if authority_class == "MEASURED" else "derived_proxy"
            row += [source_unit, canonical_unit, basis]
        else:
            row += [source_unit]
        if extra_value:
            row += extra_value.split(",")
        row += ["synthetic_test_fixture", "synthetic_test_fixture", authority_class]
        rows.append(",".join(row))
    return "\n".join(rows) + "\n"


def confirm(service, batch, project="one", **kwargs):
    return service.confirm(project, batch["id"], acknowledge_warnings=True, **kwargs)


def test_authority_enum_and_scenario_special_handling():
    assert authority("measured") is AuthorityClass.MEASURED
    assert authority_rank("MEASURED") > authority_rank("OFFICIAL_ALLOCATION") > authority_rank("UNKNOWN")
    assert authority_rank("SCENARIO") is None
    with pytest.raises(ValueError):
        authority("official-ish")


@pytest.mark.parametrize("year,amount", [(2024.5, 100), (1800, 100), (2024, 0), (2024, -1), (2024, "nan")])
def test_annual_supply_rejects_invalid_year_or_amount(services, year, amount):
    _, service = services
    batch = upload(service, "annual_water_supply", annual(amount, year=year))
    assert batch["status"] == "invalid"


def test_annual_supply_valid_and_only_one_active_version(services):
    store, service = services
    first = upload(service, "annual_water_supply", annual(1000))
    confirm(service, first)
    second = upload(service, "annual_water_supply", annual(1200))
    preview = second["replacement_preview"]
    assert preview["same_authority_conflict"] is True
    assert store.get("one")["water_data"]["active"]["annual_water_supply"] == f"water-{first['id']}"
    confirm(service, second)
    document = store.get("one")
    datasets = [d for d in document["water_data"]["datasets"].values() if d["data_type"] == "annual_water_supply"]
    assert sum(d["status"] == "active" for d in datasets) == 1
    assert sorted(d["version"] for d in datasets) == [1, 2]


def test_explicit_hm3_and_unicode_unit_normalization(services):
    _, service = services
    hm3 = annual(2).replace("m3/year", "hm3/year")
    batch = upload(service, "annual_water_supply", hm3)
    assert batch["normalized_preview"][0]["amount_m3"] == 2_000_000
    assert batch["normalized_preview"][0]["conversion"]["source_unit"] == "hm3/year"
    unicode_unit = annual(3).replace("m3/year", "m³/year")
    assert upload(service, "annual_water_supply", unicode_unit)["normalized_preview"][0]["amount_m3"] == 3
    plain_hm3 = annual(4).replace("m3/year", "hm3")
    assert upload(service, "annual_water_supply", plain_hm3)["normalized_preview"][0]["amount_m3"] == 4_000_000


def test_monthly_supply_complete_normalized_and_nonnegative(services):
    _, service = services
    batch = upload(service, "monthly_water_supply", monthly())
    assert batch["status"] == "ready" and batch["row_count"] == 12
    assert batch["normalized_preview"][0]["month"] == "2024-01"
    zero = monthly().replace("2024-01-15,101", "2024-01-15,0")
    assert upload(service, "monthly_water_supply", zero)["status"] == "ready"


def test_monthly_supply_rejects_missing_duplicate_and_wrong_year(services):
    _, service = services
    valid = monthly()
    missing = "\n".join(valid.splitlines()[:-1]) + "\n"
    duplicate = valid + valid.splitlines()[1] + "\n"
    wrong_year = valid.replace("2024-06-15", "2025-06-15")
    for content in (missing, duplicate, wrong_year):
        assert upload(service, "monthly_water_supply", content)["status"] == "invalid"


def test_mixed_authority_dataset_is_invalid_without_preview_failure(services):
    _, service = services
    content = monthly().replace("synthetic_test_fixture,DERIVED_PROXY\n", "synthetic_test_fixture,MEASURED\n", 1)
    batch = upload(service, "monthly_water_supply", content)
    assert batch["status"] == "invalid"
    assert "replacement_preview" not in batch


def test_delivery_m3_per_second_requires_operating_period_and_keeps_trace(services):
    _, service = services
    missing = monthly("delivery_capacity", source_unit="m3/s")
    assert upload(service, "delivery_capacity", missing)["status"] == "invalid"
    converted = monthly("delivery_capacity", source_unit="m3/s",
                        extra_header="operating_hours_per_day,operating_days_in_month",
                        extra_value="8,20")
    batch = upload(service, "delivery_capacity", converted)
    assert batch["status"] == "ready"
    record = batch["normalized_preview"][0]
    assert record["capacity_m3"] == 101 * 3600 * 8 * 20
    assert record["conversion"]["operating_hours_per_day"] == 8


def test_environmental_conveyance_and_perennial_contracts(services):
    _, service = services
    release = (f"planning_year,release_form,value,source_unit,canonical_unit,{HEADER_SOURCE}\n"
               "2024,ratio,0.10,ratio,ratio,synthetic_test_fixture,synthetic_test_fixture,ASSUMED\n")
    assert upload(service, "environmental_release", release)["status"] == "ready"
    conveyance = (f"planning_year,period,efficiency,scope,{HEADER_SOURCE}\n"
                  "2024,annual,0.82,reservoir_to_farm_gate,synthetic_test_fixture,synthetic_test_fixture,DERIVED_PROXY\n")
    assert upload(service, "conveyance_efficiency", conveyance)["status"] == "ready"
    perennial = (f"planning_year,crop,analysis_unit_id,month,value,source_unit,canonical_unit,confidence,method,{HEADER_SOURCE}\n"
                 "2024,APPLE,,,600,mm,m3/da,synthetic,synthetic_protocol,synthetic_test_fixture,synthetic_test_fixture,CALCULATED_REFERENCE\n")
    batch = upload(service, "perennial_irrigation_requirement", perennial)
    assert batch["status"] == "ready"
    assert batch["normalized_preview"][0]["conversion"]["conversion_method"] == "1 mm over 1 da = 1 m3/da"


def test_perennial_precedence_does_not_invent_monthly_values():
    records = [
        {"crop": "APPLE", "analysis_unit_id": None, "month": None, "value": 1},
        {"crop": "APPLE", "analysis_unit_id": "P1", "month": None, "value": 2},
        {"crop": "APPLE", "analysis_unit_id": None, "month": "2024-06", "value": 3},
    ]
    assert resolve_perennial_requirement(records, "APPLE", "P1", "2024-06")["value"] == 2
    assert resolve_perennial_requirement(records, "APPLE", None, "2024-06")["value"] == 3
    assert resolve_perennial_requirement(records, "PEAR", None, "2024-06") is None


def test_high_authority_replacement_requires_confirm_and_retains_history(services):
    store, service = services
    proxy = upload(service, "delivery_capacity", monthly("delivery_capacity"))
    confirm(service, proxy)
    old_id = store.get("one")["water_data"]["active"]["delivery_capacity"]
    official = upload(service, "delivery_capacity", monthly("delivery_capacity", "OFFICIAL_ALLOCATION", 50))
    assert official["display_label"] == "SYNTHETIC"
    assert official["replacement_preview"]["authority_change"] == "HIGHER"
    assert len(official["replacement_preview"]["affected_months"]) == 12
    assert official["replacement_preview"]["new_annual_total"] > official["replacement_preview"]["old_annual_total"]
    assert official["replacement_preview"]["requires_reanalysis"] is True
    assert store.get("one")["water_data"]["active"]["delivery_capacity"] == old_id
    before_revision = store.get("one")["data_revision"]
    confirm(service, official)
    document = store.get("one")
    new_id = document["water_data"]["active"]["delivery_capacity"]
    assert new_id != old_id and document["water_data"]["datasets"][old_id]["status"] == "inactive"
    assert document["water_data"]["datasets"][old_id]["superseded_by"] == new_id
    assert document["data_revision"] == before_revision + 1
    record = document["water_data"]["datasets"][new_id]["records"][0]
    assert record["file_hash"] == hashlib.sha256(monthly("delivery_capacity", "OFFICIAL_ALLOCATION", 50).encode()).hexdigest()
    assert record["source_institution"] == "synthetic_test_fixture" and record["import_batch_id"] == official["id"]
    assert document["water_data"]["datasets"][new_id]["source"]["institutions"] == ["synthetic_test_fixture"]


def test_lower_authority_cannot_silently_replace_measured(services):
    store, service = services
    measured = upload(service, "annual_water_supply", annual(1000, "MEASURED"))
    confirm(service, measured)
    proxy = upload(service, "annual_water_supply", annual(900, "DERIVED_PROXY"))
    assert proxy["replacement_preview"]["requires_authority_override"] is True
    with pytest.raises(ConflictError):
        confirm(service, proxy)
    with pytest.raises(ConflictError):
        confirm(service, proxy, acknowledge_authority_override=True)
    confirm(service, proxy, acknowledge_authority_override=True, override_reason="Synthetic downgrade test")
    active = store.get("one")["water_data"]["datasets"][f"water-{proxy['id']}"]
    assert active["override_reason"] == "Synthetic downgrade test"


def test_project_isolation_and_readiness_status_are_backward_compatible(services):
    store, service = services
    before = readiness(store.get("one"))["scenarios"]
    batch = upload(service, "annual_water_supply", annual())
    confirm(service, batch)
    assert store.get("two")["water_data"]["datasets"] == {}
    report = readiness(store.get("one"))
    assert report["scenarios"] == before
    assert report["water_data_authority"]["annual_water_supply"]["authority_class"] == "DERIVED_PROXY"
    assert report["water_data_authority"]["annual_water_supply"]["engine_connected"] is False


def test_existing_import_pipeline_and_scientific_engine_guard(services):
    store, service = services
    units = upload(service, "analysis_units", "external_id,settlement,area_da,current_crop\nA,Synthetic,10,Wheat\n")
    confirm(service, units)
    assert store.get("one")["analysis_units"][0]["external_id"] == "A"
    changed = subprocess.run(
        ["git", "diff", "--name-only", "v2-scientific-water-audit-complete", "--", "app.py", "kds/science"],
        check=True, text=True, capture_output=True,
    ).stdout.splitlines()
    assert [path for path in changed if path != "kds/science/institutional_water.py"] == []


@pytest.mark.parametrize("data_type,filename", [
    ("annual_water_supply", "annual_water_supply_template.xlsx"),
    ("monthly_water_supply", "monthly_water_supply_template.xlsx"),
    ("delivery_capacity", "delivery_capacity_template.xlsx"),
    ("environmental_release", "environmental_release_template.xlsx"),
    ("conveyance_efficiency", "conveyance_efficiency_template.xlsx"),
    ("perennial_irrigation_requirement", "perennial_irrigation_requirement_template.xlsx"),
])
def test_synthetic_water_templates_are_importable(services, data_type, filename):
    _, service = services
    path = Path(__file__).resolve().parents[1] / "docs" / "data_templates" / filename
    batch = service.upload("one", data_type, filename, path.read_bytes(), {})
    assert batch["status"] == "ready"
    assert batch["display_label"] == "SYNTHETIC"


def test_projects_ui_exposes_water_authority_without_changing_legacy_panel():
    root = Path(__file__).resolve().parents[1]
    html = (root / "kds/ui/templates/projects.html").read_text(encoding="utf-8")
    script = (root / "kds/ui/static/projects.js").read_text(encoding="utf-8")
    assert "annual_water_supply" in html and "perennial_irrigation_requirement" in html
    assert "Water Data authority" in script
    changed_panel = subprocess.run(
        ["git", "diff", "--name-only", "v2-scientific-water-audit-complete", "--", "index.html", "script.js", "style.css"],
        check=True, text=True, capture_output=True,
    ).stdout.strip()
    assert changed_panel == ""
