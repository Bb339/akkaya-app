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


def confirmed_inputs(service, authority="LOCAL_INSTITUTIONAL_SOURCE"):
    batches = []
    for kind, content in (
        ("crop_yield", yield_csv(authority=authority)),
        ("crop_sale_price", price_csv(authority=authority)),
        ("crop_cost_components", cost_csv(amount=11000, authority=authority)),
    ):
        batch = upload(service, kind, content)
        confirm(service, batch)
        batches.append(batch)
    return [f"economic-{batch['id']}" for batch in batches]


def support_csv(amount=100, authority="LOCAL_INSTITUTIONAL_SOURCE", crop="TURP"):
    return (f"crop,support_type,amount,unit,{COMMON}\n"
            f"{crop},test_support,{amount},TL/da,2024,2024,{authority},synthetic_test_fixture,not_official,TRY,project,catalog\n")


def calculated_csv(y, p, c, *, authority="CALCULATED_FROM_VERIFIED_INPUTS", method="GROSS_MINUS_TOTAL_COST",
                   support_value=None, support_id="", crop="TURP"):
    value = "" if support_value is None else support_value
    return (f"crop,calculation_method,gross_revenue_per_da,total_cost_per_da,support_payment_per_da,"
            f"yield_dataset_id,price_dataset_id,cost_dataset_id,support_dataset_id,{COMMON}\n"
            f"{crop},{method},15000,11000,{value},{y},{p},{c},{support_id},2024,2024,{authority},"
            "synthetic_test_fixture,not_official,TRY,project,catalog\n")


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
    y, p, c = confirmed_inputs(service)
    calculated = (f"crop,calculation_method,gross_revenue_per_da,total_cost_per_da,yield_dataset_id,price_dataset_id,cost_dataset_id,{COMMON}\n"
                  f"TURP,GROSS_MINUS_TOTAL_COST,15000,11000,{y},{p},{c},2024,2024,CALCULATED_FROM_VERIFIED_INPUTS,synthetic_test_fixture,not_official,TRY,project,catalog\n")
    batch = upload(service, "crop_net_profit", calculated)
    assert batch["normalized_preview"][0]["net_profit_per_da"] == 4000
    assert batch["normalized_preview"][0]["calculation_method"] == "GROSS_MINUS_TOTAL_COST"


def test_calculation_helper_checks_identity_and_records_lineage():
    base = {"crop": "TURP", "planning_year": 2024, "currency": "TRY"}
    common = {"status": "active", "confirmed_at": "2024-01-01", "derivation_status": "CURRENT",
              "requires_recalculation": False, "authority_class": "LOCAL_INSTITUTIONAL_SOURCE"}
    y = {"dataset_id": "y", "data_type": "crop_yield", **common, "records": [{**base, "yield_ton_da": 2.5}]}
    p = {"dataset_id": "p", "data_type": "crop_sale_price", **common, "records": [{**base, "price_tl_ton": 6000}]}
    c = {"dataset_id": "c", "data_type": "crop_cost_components", **common, "records": [{**base, "amount_tl_da": 11000}]}
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
    y, p, c = confirmed_inputs(service)
    derived = (f"crop,calculation_method,gross_revenue_per_da,total_cost_per_da,yield_dataset_id,price_dataset_id,cost_dataset_id,{COMMON}\n"
               f"TURP,GROSS_MINUS_TOTAL_COST,15000,11000,{y},{p},{c},2024,2024,CALCULATED_FROM_VERIFIED_INPUTS,synthetic_test_fixture,not_official,TRY,project,catalog\n")
    d = upload(service, "crop_net_profit", derived); confirm(service, d)
    y2 = upload(service, "crop_yield", yield_csv(2600, authority="LOCAL_INSTITUTIONAL_SOURCE")); confirm(service, y2)
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


def test_calculated_authority_requires_verified_complete_roles(services):
    _, service = services
    proxy_ids = confirmed_inputs(service, authority="DERIVED_PROXY")
    assert upload(service, "crop_net_profit", calculated_csv(*proxy_ids))["status"] == "invalid"

    # A calculated result cannot claim the authority of a direct measured record.
    assert upload(service, "crop_net_profit", calculated_csv(*proxy_ids, authority="MEASURED_FARM_RECORD"))["status"] == "invalid"

    verified_ids = confirmed_inputs(service)
    valid = upload(service, "crop_net_profit", calculated_csv(*verified_ids))
    assert valid["status"] == "ready"
    row = valid["normalized_preview"][0]
    assert row["authority_class"] == "CALCULATED_FROM_VERIFIED_INPUTS"
    assert [row[name] for name in ("yield_dataset_id", "price_dataset_id", "cost_dataset_id")] == verified_ids


def test_calculated_dependency_types_and_completeness_are_enforced(services):
    store, service = services
    y, p, c = confirmed_inputs(service)
    only_yield = calculated_csv(y, "", "")
    assert upload(service, "crop_net_profit", only_yield)["status"] == "invalid"
    wrong_role = calculated_csv(p, y, c)
    assert upload(service, "crop_net_profit", wrong_role)["status"] == "invalid"

    def make_inactive(document):
        document["economic_data"]["datasets"][y]["status"] = "inactive"
    store.update("one", make_inactive)
    assert upload(service, "crop_net_profit", calculated_csv(y, p, c))["status"] == "invalid"


@pytest.mark.parametrize("mutation", ["stale", "wrong_year", "wrong_crop", "unknown_authority"])
def test_calculated_dependency_state_year_crop_and_authority_are_enforced(services, mutation):
    store, service = services
    y, p, c = confirmed_inputs(service)

    def alter(document):
        dataset = document["economic_data"]["datasets"][y]
        if mutation == "stale":
            dataset.update(derivation_status="STALE", requires_recalculation=True)
        elif mutation == "wrong_year":
            dataset["records"][0]["planning_year"] = 2023
        elif mutation == "wrong_crop":
            dataset["records"][0]["crop"] = "KIRMIZI TURP"
        else:
            dataset["authority_class"] = "UNKNOWN"
    store.update("one", alter)
    assert upload(service, "crop_net_profit", calculated_csv(y, p, c))["status"] == "invalid"


def test_support_missing_and_explicit_zero_are_distinct(services):
    _, service = services
    y, p, c = confirmed_inputs(service)
    support = upload(service, "crop_support_payment", support_csv(0)); confirm(service, support)
    support_id = f"economic-{support['id']}"
    missing = calculated_csv(y, p, c, method="GROSS_PLUS_SUPPORT_MINUS_TOTAL_COST", support_id=support_id)
    assert upload(service, "crop_net_profit", missing)["status"] == "invalid"
    explicit_zero = calculated_csv(y, p, c, method="GROSS_PLUS_SUPPORT_MINUS_TOTAL_COST",
                                   support_value=0, support_id=support_id)
    ready = upload(service, "crop_net_profit", explicit_zero)
    assert ready["status"] == "ready"
    assert ready["normalized_preview"][0]["support_payment_per_da"] == 0
    assert upload(service, "crop_net_profit", calculated_csv(y, p, c))["status"] == "ready"


@pytest.mark.parametrize("amount,status", [(-1, "invalid"), (0, "ready"), (1, "ready")])
def test_cost_components_are_nonnegative(services, amount, status):
    _, service = services
    assert upload(service, "crop_cost_components", cost_csv(amount=amount))["status"] == status


@pytest.mark.parametrize("price_date,observation_year,status", [
    ("2024-06-01", 2024, "ready"),
    ("not-a-date", 2024, "invalid"),
    ("2023-06-01", 2024, "invalid"),
    ("2023-02-29", 2023, "invalid"),
    ("2024-02-29", 2024, "ready"),
])
def test_price_date_is_iso_calendar_date_aligned_to_observation_year(services, price_date, observation_year, status):
    _, service = services
    csv = (f"crop,price,price_unit,price_date,{COMMON}\n"
           f"TURP,6,TL/kg,{price_date},2024,{observation_year},DERIVED_PROXY,synthetic_test_fixture,not_official,TRY,project,catalog\n")
    batch = upload(service, "crop_sale_price", csv)
    assert batch["status"] == status
    if status == "ready":
        assert batch["normalized_preview"][0]["price_alignment"] == "CURRENT"


def test_price_period_cannot_contradict_price_date(services):
    _, service = services
    csv = (f"crop,price,price_unit,price_date,price_period,{COMMON}\n"
           "TURP,6,TL/kg,2024-06-01,2023 average,2024,2024,DERIVED_PROXY,synthetic_test_fixture,not_official,TRY,project,catalog\n")
    assert upload(service, "crop_sale_price", csv)["status"] == "invalid"


def test_seasonal_replacement_preview_uses_net_profit_per_da_and_unit(services):
    _, service = services
    def seasonal(value):
        return (f"analysis_unit_id,crop,season,yield_value,yield_unit,price,price_unit,cost,cost_unit,net_profit,net_profit_unit,{COMMON}\n"
                f"P1,TURP,SECONDARY,2.5,ton/da,6000,TL/ton,11000,TL/da,{value},TL/da,2024,2024,DERIVED_PROXY,synthetic_test_fixture,not_official,TRY,project,catalog\n")
    old = upload(service, "seasonal_economics", seasonal(4000)); confirm(service, old)
    new = upload(service, "seasonal_economics", seasonal(4500))
    preview = new["replacement_preview"]
    assert preview["unit"] == "TL/da" and preview["value_change_count"] == 1
    assert preview["value_changes"][0] == {
        "identity": "P1|TURP|SECONDARY", "old_value": 4000.0, "new_value": 4500.0,
        "absolute_difference": 500.0, "percentage_difference": 12.5,
    }


def test_seasonal_dependencies_must_exist_and_be_active_current_same_year(services):
    store, service = services
    source = upload(service, "crop_yield", yield_csv()); confirm(service, source)
    source_id = f"economic-{source['id']}"

    def seasonal(dependency, net_profit=4000):
        return (f"analysis_unit_id,crop,season,yield_value,yield_unit,price,price_unit,cost,cost_unit,net_profit,net_profit_unit,dependency_dataset_ids,{COMMON}\n"
                f"P1,TURP,SECONDARY,2.5,ton/da,6000,TL/ton,11000,TL/da,{net_profit},TL/da,{dependency},2024,2024,DERIVED_PROXY,synthetic_test_fixture,not_official,TRY,project,catalog\n")

    assert upload(service, "seasonal_economics", seasonal(source_id))["status"] == "ready"

    def make_stale(document):
        document["economic_data"]["datasets"][source_id].update(derivation_status="STALE", requires_recalculation=True)
    store.update("one", make_stale)
    assert upload(service, "seasonal_economics", seasonal(source_id, 4100))["status"] == "invalid"


def test_verified_helper_rejects_unverified_or_invalid_inputs():
    base = {"crop": "TURP", "planning_year": 2024, "currency": "TRY"}
    state = {"status": "active", "confirmed_at": "2024-01-01", "derivation_status": "CURRENT",
             "requires_recalculation": False, "authority_class": "OFFICIAL_STATISTICS"}
    y = {"dataset_id": "y", "data_type": "crop_yield", **state, "records": [{**base, "yield_ton_da": 2.5}]}
    p = {"dataset_id": "p", "data_type": "crop_sale_price", **state, "records": [{**base, "price_tl_ton": 6000}]}
    c = {"dataset_id": "c", "data_type": "crop_cost_components", **state, "records": [{**base, "amount_tl_da": 1000}]}
    assert calculate_profit_from_verified_inputs(y, p, c)["net_profit_per_da"] == 14000
    for authority in ("DERIVED_PROXY", "ASSUMED", "UNKNOWN"):
        bad = {**y, "authority_class": authority}
        with pytest.raises(ValueError):
            calculate_profit_from_verified_inputs(bad, p, c)
    for changes in (
        {"status": "inactive"}, {"derivation_status": "STALE"}, {"requires_recalculation": True},
        {"data_type": "crop_sale_price"},
    ):
        with pytest.raises(ValueError):
            calculate_profit_from_verified_inputs({**y, **changes}, p, c)
    for row_changes in (
        {"crop": "KIRMIZI TURP"}, {"planning_year": 2023}, {"currency": "USD"},
    ):
        bad = {**y, "records": [{**y["records"][0], **row_changes}]}
        with pytest.raises(ValueError):
            calculate_profit_from_verified_inputs(bad, p, c)


def scoped_helper_inputs(geographies=("district-a", "district-a", "district-a"),
                         crop_scopes=("catalog", "catalog", "catalog")):
    state = {"status": "active", "confirmed_at": "2024-01-01", "derivation_status": "CURRENT",
             "requires_recalculation": False, "authority_class": "OFFICIAL_STATISTICS"}
    def record(crop, year, currency, geography, crop_scope, **values):
        return {"crop": crop, "planning_year": year, "currency": currency,
                "geographic_scope": geography, "crop_scope": crop_scope, **values}
    y = {"dataset_id": "y", "data_type": "crop_yield", **state,
         "records": [record("TURP", 2024, "TRY", geographies[0], crop_scopes[0], yield_ton_da=2.5)]}
    p = {"dataset_id": "p", "data_type": "crop_sale_price", **state,
         "records": [record("TURP", 2024, "TRY", geographies[1], crop_scopes[1], price_tl_ton=6000)]}
    c = {"dataset_id": "c", "data_type": "crop_cost_components", **state,
         "records": [record("TURP", 2024, "TRY", geographies[2], crop_scopes[2], amount_tl_da=11000)]}
    return y, p, c


def test_verified_helper_rejects_wrong_geographic_scope():
    y, p, c = scoped_helper_inputs(geographies=("district-a", "district-b", "district-a"))
    with pytest.raises(ValueError, match="same geographic_scope and crop_scope"):
        calculate_profit_from_verified_inputs(y, p, c)


def test_verified_helper_rejects_wrong_crop_scope():
    y, p, c = scoped_helper_inputs(crop_scopes=("catalog", "vegetables", "catalog"))
    with pytest.raises(ValueError, match="same geographic_scope and crop_scope"):
        calculate_profit_from_verified_inputs(y, p, c)


def test_verified_helper_accepts_same_scope_and_preserves_provenance():
    y, p, c = scoped_helper_inputs()
    result = calculate_profit_from_verified_inputs(y, p, c)
    assert result["geographic_scope"] == "district-a"
    assert result["crop_scope"] == "catalog"
    assert result["authority_class"] == "CALCULATED_FROM_VERIFIED_INPUTS"
    assert result["dependency_dataset_ids"] == ["y", "p", "c"]
    assert [result[name] for name in ("yield_dataset_id", "price_dataset_id", "cost_dataset_id")] == ["y", "p", "c"]


def test_verified_helper_rejects_support_scope_mismatch():
    y, p, c = scoped_helper_inputs()
    support = {**y, "dataset_id": "s", "data_type": "crop_support_payment",
               "records": [{**y["records"][0], "geographic_scope": "district-b", "amount_tl_da": 100}]}
    with pytest.raises(ValueError, match="same geographic_scope and crop_scope"):
        calculate_profit_from_verified_inputs(y, p, c, support)


def test_verified_helper_canonicalizes_missing_and_explicit_default_scopes():
    y, p, c = scoped_helper_inputs(geographies=(None, "project", ""),
                                   crop_scopes=(None, "catalog", "   "))
    result = calculate_profit_from_verified_inputs(y, p, c)
    assert result["geographic_scope"] == "project"
    assert result["crop_scope"] == "catalog"


def test_verified_helper_default_scope_does_not_match_different_explicit_scope():
    y, p, c = scoped_helper_inputs(geographies=(None, "district-a", "project"))
    with pytest.raises(ValueError, match="same geographic_scope and crop_scope"):
        calculate_profit_from_verified_inputs(y, p, c)


def test_verified_helper_rejects_mixed_scope_cost_components():
    y, p, c = scoped_helper_inputs()
    c["records"].append({**c["records"][0], "geographic_scope": "district-b", "amount_tl_da": 0})
    with pytest.raises(ValueError, match="same geographic_scope and crop_scope"):
        calculate_profit_from_verified_inputs(y, p, c)
