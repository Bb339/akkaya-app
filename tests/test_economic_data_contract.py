"""Synthetic acceptance tests for the disconnected economics contract."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from kds.application.import_service import ImportService
from kds.application.project_service import ProjectService
from kds.data.project_store import FileProjectStore
from kds.data.repositories import ConflictError
from kds.domain.economic_data import (
    EconomicAuthorityClass, authority_rank, calculate_profit_from_verified_inputs,
    convert_price, convert_yield, economic_authority, specificity,
)


COMMON = "planning_year,observation_year,authority_class,source_institution,source_reference,currency,geographic_scope,crop_scope"


@pytest.fixture
def services(tmp_path):
    store = FileProjectStore(tmp_path / "projects")
    projects = ProjectService(store)
    for project_id in ("one", "two"):
        projects.create(dict(id=project_id, name="Synthetic economics contract", planning_year=2024,
                             annual_water_budget=1000, water_budget_unit="m3",
                             data_source_notes="synthetic_test_fixture"))
        def seed(document):
            document["crops"] = [
                {"name": "TURP"}, {"name": "KIRMIZI TURP"}, {"name": "TURP (KIRMIZI)"},
                {"name": "MISIR (DANE)"}, {"name": "MISIR (SILAJ)"},
            ]
            document["analysis_units"] = [{"external_id": "P1", "current_crop": "TURP", "area_da": 10}]
        store.update(project_id, seed)
    return store, ImportService(store)


def upload(service, kind, content, project="one"):
    return service.upload(project, kind, f"{kind}.csv", content.encode(), {})


def confirm(service, batch, project="one", **kwargs):
    return service.confirm(project, batch["id"], acknowledge_warnings=True, **kwargs)


def profit(value=4000, authority="DERIVED_PROXY", crop="TURP", method="DIRECT_SOURCE", dependencies=""):
    return (f"crop,net_profit_per_da,calculation_method,dependency_dataset_ids,{COMMON}\n"
            f"{crop},{value},{method},{dependencies},2024,2024,{authority},synthetic_test_fixture,not_official,TRY,project,catalog\n")


def yield_csv(value=2500, unit="kg/da", authority="DERIVED_PROXY", crop="TURP", planning_year=2024, observation_year=2024):
    return (f"crop,yield_value,yield_unit,{COMMON}\n"
            f"{crop},{value},{unit},{planning_year},{observation_year},{authority},synthetic_test_fixture,not_official,TRY,project,catalog\n")


def price_csv(value=6, unit="TL/kg", authority="DERIVED_PROXY", crop="TURP"):
    return (f"crop,price,price_unit,price_period,{COMMON}\n"
            f"{crop},{value},{unit},2024 average,2024,2024,{authority},synthetic_test_fixture,not_official,TRY,project,catalog\n")


def cost_csv(category="seed", amount=1000, authority="DERIVED_PROXY", crop="TURP"):
    return (f"crop,cost_category,amount,unit,{COMMON}\n"
            f"{crop},{category},{amount},TL/da,2024,2024,{authority},synthetic_test_fixture,not_official,TRY,project,catalog\n")


def test_authority_classes_precedence_and_specificity_are_separate():
    assert economic_authority("measured_farm_record") is EconomicAuthorityClass.MEASURED_FARM_RECORD
    assert authority_rank("MEASURED_FARM_RECORD") > authority_rank("OFFICIAL_STATISTICS") > authority_rank("FALLBACK")
    with pytest.raises(ValueError):
        economic_authority("SCENARIO")
    unit = specificity({"analysis_unit_id": "P1", "price_date": "2024-06-01", "authority_class": "UNKNOWN"})
    crop = specificity({"crop": "TURP", "observation_year": 2024, "authority_class": "OFFICIAL_STATISTICS"})
    assert unit["scope"] > crop["scope"] and unit["authority"] < crop["authority"]


def test_yield_and_price_conversions_are_explicit_and_never_confused_with_profit():
    assert convert_yield(2500, "kg/da") == (2.5, {"source_unit": "kg/da", "canonical_unit": "ton/da", "conversion_method": "kg/da ÷ 1000"})
    assert convert_price(6, "TL/kg")[0] == 6000
    with pytest.raises(ValueError):
        convert_price(6000, "TL/da")


def test_yield_price_cost_and_missing_components_are_preserved(services):
    store, service = services
    y = upload(service, "crop_yield", yield_csv())
    assert y["normalized_preview"][0]["yield_ton_da"] == 2.5
    confirm(service, y)
    p = upload(service, "crop_sale_price", price_csv())
    assert p["normalized_preview"][0]["price_tl_ton"] == 6000
    confirm(service, p)
    c = upload(service, "crop_cost_components", cost_csv())
    confirm(service, c)
    cost = store.get("one")["economic_data"]["datasets"][f"economic-{c['id']}"]
    assert cost["component_totals_tl_da"]["TURP"] == 1000
    assert "fertilizer" in cost["missing_cost_categories"]["TURP"]


def test_support_is_separate_and_calculated_profit_keeps_dependencies(services):
    store, service = services
    support = (f"crop,support_type,amount,unit,{COMMON}\n"
               "TURP,test_support,100,TL/da,2024,2024,DERIVED_PROXY,synthetic_test_fixture,not_official,TRY,project,catalog\n")
    batch = upload(service, "crop_support_payment", support)
    confirm(service, batch)
    assert store.get("one")["economic_data"]["datasets"][f"economic-{batch['id']}"]["records"][0]["support_type"] == "test_support"


def test_direct_and_calculated_profit_methods(services):
    _, service = services
    direct = upload(service, "crop_net_profit", profit())
    assert direct["status"] == "ready" and direct["normalized_preview"][0]["calculation_formula"] is None
    dependency = upload(service, "crop_yield", yield_csv()); confirm(service, dependency)
    calculated = (f"crop,calculation_method,gross_revenue_per_da,total_cost_per_da,dependency_dataset_ids,{COMMON}\n"
                  f"TURP,GROSS_MINUS_TOTAL_COST,15000,11000,economic-{dependency['id']},2024,2024,CALCULATED_FROM_VERIFIED_INPUTS,synthetic_test_fixture,not_official,TRY,project,catalog\n")
    batch = upload(service, "crop_net_profit", calculated)
    assert batch["normalized_preview"][0]["net_profit_per_da"] == 4000
    assert batch["normalized_preview"][0]["calculation_method"] == "GROSS_MINUS_TOTAL_COST"


def test_calculation_helper_checks_identity_and_records_lineage():
    base = {"crop": "TURP", "planning_year": 2024, "currency": "TRY"}
    y = {"dataset_id": "y", "records": [{**base, "yield_ton_da": 2.5}]}
    p = {"dataset_id": "p", "records": [{**base, "price_tl_ton": 6000}]}
    c = {"dataset_id": "c", "records": [{**base, "amount_tl_da": 11000}]}
    result = calculate_profit_from_verified_inputs(y, p, c)
    assert result["gross_revenue_per_da"] == 15000 and result["net_profit_per_da"] == 4000
    assert result["dependency_dataset_ids"] == ["y", "p", "c"] and result["engine_connected"] is False


@pytest.mark.parametrize("bad", [
    yield_csv(planning_year=2023, observation_year=2023),
    yield_csv().replace(",TRY,", ",USD,"),
    yield_csv(crop="KİMYON"),
])
def test_year_currency_and_missing_crop_are_blocked(services, bad):
    _, service = services
    assert upload(service, "crop_yield", bad)["status"] == "invalid"


@pytest.mark.parametrize("observation_year,code", [(2023, "stale_observation"), (2025, "future_observation")])
def test_stale_and_future_observation_years_are_visible_and_not_mixed(services, observation_year, code):
    _, service = services
    batch = upload(service, "crop_yield", yield_csv(observation_year=observation_year))
    assert batch["status"] == "ready"
    assert batch["normalized_preview"][0]["temporal_alignment"] == ("STALE" if observation_year < 2024 else "FUTURE")
    assert code in {issue["code"] for issue in batch["issues"]}


def test_crop_variants_are_preserved_and_aliases_are_not_merged(services):
    _, service = services
    for crop in ("TURP", "KIRMIZI TURP", "TURP (KIRMIZI)", "MISIR (DANE)", "MISIR (SILAJ)"):
        batch = upload(service, "crop_yield", yield_csv(crop=crop))
        assert batch["normalized_preview"][0]["crop"] == crop


def test_synthetic_turp_replacement_requires_preview_then_confirm(services):
    store, service = services
    old = upload(service, "crop_net_profit", profit(4000, "DERIVED_PROXY"))
    confirm(service, old)
    old_id, revision = f"economic-{old['id']}", store.get("one")["data_revision"]
    incoming = upload(service, "crop_net_profit", profit(4500, "LOCAL_INSTITUTIONAL_SOURCE"))
    preview = incoming["replacement_preview"]
    assert store.get("one")["economic_data"]["active"][preview["scope_key"]] == old_id
    assert preview["authority_change"] == "HIGHER" and preview["value_changes"][0]["absolute_difference"] == 500
    confirm(service, incoming)
    document = store.get("one")
    assert document["data_revision"] == revision + 1
    assert document["economic_data"]["datasets"][old_id]["status"] == "inactive"
    assert document["economics"] == []


def test_lower_authority_and_same_authority_conflicts(services):
    store, service = services
    official = upload(service, "crop_net_profit", profit(4000, "OFFICIAL_STATISTICS"))
    confirm(service, official)
    same = upload(service, "crop_net_profit", profit(4100, "OFFICIAL_STATISTICS"))
    assert same["replacement_preview"]["same_authority_conflict"] is True
    lower = upload(service, "crop_net_profit", profit(4200, "ASSUMED"))
    assert lower["replacement_preview"]["requires_authority_override"] is True
    with pytest.raises(ConflictError): confirm(service, lower)
    confirm(service, lower, acknowledge_authority_override=True, override_reason="synthetic downgrade test")
    assert store.get("one")["economic_data"]["datasets"][f"economic-{lower['id']}"]["override_reason"]


def test_upstream_replacement_marks_derived_profit_stale(services):
    store, service = services
    y1 = upload(service, "crop_yield", yield_csv()); confirm(service, y1)
    derived = (f"crop,calculation_method,gross_revenue_per_da,total_cost_per_da,dependency_dataset_ids,{COMMON}\n"
               f"TURP,GROSS_MINUS_TOTAL_COST,15000,11000,economic-{y1['id']},2024,2024,CALCULATED_FROM_VERIFIED_INPUTS,synthetic_test_fixture,not_official,TRY,project,catalog\n")
    d = upload(service, "crop_net_profit", derived); confirm(service, d)
    y2 = upload(service, "crop_yield", yield_csv(2600)); confirm(service, y2)
    document = store.get("one")
    stale = document["economic_data"]["datasets"][f"economic-{d['id']}"]
    assert stale["derivation_status"] == "STALE" and stale["requires_recalculation"] is True
    assert document["economic_data"]["reanalysis"]["stale_dataset_ids"] == [f"economic-{d['id']}"]


def test_unit_and_season_contracts_and_project_isolation(services):
    store, service = services
    unit = (f"analysis_unit_id,crop,gross_revenue,total_cost,net_profit,{COMMON}\n"
            "P1,TURP,150000,110000,40000,2024,2024,MEASURED_FARM_RECORD,synthetic_test_fixture,not_official,TRY,project,catalog\n")
    season = (f"analysis_unit_id,crop,season,yield_value,yield_unit,price,price_unit,cost,cost_unit,net_profit,net_profit_unit,{COMMON}\n"
              "P1,TURP,SECONDARY,2.5,ton/da,15000,TL/ton,11000,TL/da,4000,TL/da,2024,2024,DERIVED_PROXY,synthetic_test_fixture,not_official,TRY,project,catalog\n")
    for kind, content in (("analysis_unit_economics", unit), ("seasonal_economics", season)):
        batch = upload(service, kind, content); confirm(service, batch)
    assert store.get("two")["economic_data"]["datasets"] == {}
    seasonal = next(d for d in store.get("one")["economic_data"]["datasets"].values() if d["data_type"] == "seasonal_economics")
    assert seasonal["records"][0]["missing_secondary_fallback_prohibited"] is True


def test_provenance_hash_engine_and_legacy_guards(services):
    store, service = services
    content = yield_csv()
    batch = upload(service, "crop_yield", content); confirm(service, batch)
    dataset = store.get("one")["economic_data"]["datasets"][f"economic-{batch['id']}"]
    assert dataset["source"]["file_hash"] == hashlib.sha256(content.encode()).hexdigest()
    assert dataset["records"][0]["conversion"]["conversion_method"] == "kg/da ÷ 1000"
    root = Path(__file__).resolve().parents[1]
    protected = subprocess.run(["git", "diff", "--name-only", "v2-scientific-economics-audit-complete", "--",
                                "app.py", "kds/science", "data", "index.html", "script.js", "style.css"],
                               cwd=root, check=True, text=True, capture_output=True).stdout.strip()
    assert protected == ""


@pytest.mark.parametrize("kind,filename", [
    ("crop_yield", "crop_yield_template.xlsx"), ("crop_sale_price", "crop_sale_price_template.xlsx"),
    ("crop_support_payment", "crop_support_template.xlsx"), ("crop_cost_components", "crop_cost_components_template.xlsx"),
    ("crop_net_profit", "crop_net_profit_template.xlsx"), ("analysis_unit_economics", "analysis_unit_economics_template.xlsx"),
    ("seasonal_economics", "seasonal_economics_template.xlsx"),
])
def test_synthetic_templates_are_importable(services, kind, filename):
    _, service = services
    path = Path(__file__).resolve().parents[1] / "docs" / "data_templates" / filename
    batch = service.upload("one", kind, filename, path.read_bytes(), {})
    assert batch["status"] == "ready" and batch["display_label"] == "SYNTHETIC / not_official"
