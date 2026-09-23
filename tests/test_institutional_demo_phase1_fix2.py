from copy import deepcopy
from types import SimpleNamespace

import pytest

import app
from test_institutional_demo_phase1 import institutional
from kds.adapters.institutional import resolve_verified_water, verified_execution_plan, verified_readiness
from kds.application.optimization import configuration
from kds.application.optimization import complete_result_contract
from kds.science.institutional_water import (
    effective_rain_scs_mm, kc_curve_daily, monthly_gross_demand_m3_da,
    validate_verified_result,
)


@pytest.mark.parametrize("precip", [25.0, 100.0, 250.0, 251.0, 400.0])
def test_effective_rainfall_exactly_reuses_accepted_scs(precip):
    assert effective_rain_scs_mm(precip) == app._effective_rain_scs_mm(precip)


@pytest.mark.parametrize("days,mode,stages", [
    (20, "DAYS", (20, 30, 40, 20)),
    (120, "FRACTIONS", (.2, .3, .3, .2)),
    (7, "DAYS", (20, 30, 40, 20)),
    (730, "DAYS", (20, 30, 40, 20)),
    (100, "DAYS", (0, 0, 0, 0)),
    (273, "DAYS", (20, 30, 40, 20)),
])
def test_kc_curve_exactly_reuses_accepted_execution(days, mode, stages):
    parameter = dict(kc_ini=.4, kc_mid=1., kc_end=.5, stage_value_mode=mode,
                     p_ini=stages[0], p_dev=stages[1], p_mid=stages[2], p_late=stages[3])
    assert kc_curve_daily(days, parameter) == app._kc_curve_daily(days, .4, 1., .5, *stages)


def _parameter():
    return dict(kc_ini=.4, kc_mid=1., kc_end=.5, stage_value_mode="DAYS",
                p_ini=20, p_dev=30, p_mid=40, p_late=20)


def test_cross_year_profile_preserves_full_calendar_identity_with_explicit_normal():
    phenology = dict(mode="YEAR_SPECIFIC", planting_date="2024-10-01", harvest_date="2025-06-30")
    climate = [dict(month=f"2025-{month:02d}", et0_mm=85., precip_mm=25.,
                    climate_mode="CLIMATOLOGICAL_NORMAL", source="synthetic not_official",
                    geographic_scope="project") for month in range(1, 13)]
    profile = monthly_gross_demand_m3_da(_parameter(), phenology, climate, .83, 2025)
    assert set(profile) == {"2024-10", "2024-11", "2024-12", *
                           {f"2025-{month:02d}" for month in range(1, 7)}}


def test_year_specific_climate_never_reuses_another_year():
    phenology = dict(mode="YEAR_SPECIFIC", planting_date="2024-10-01", harvest_date="2025-06-30")
    climate = [dict(month=f"2025-{month:02d}", et0_mm=85., precip_mm=25.,
                    climate_mode="YEAR_SPECIFIC", source="synthetic not_official",
                    geographic_scope="project") for month in range(1, 13)]
    with pytest.raises(ValueError, match="2024-10"):
        monthly_gross_demand_m3_da(_parameter(), phenology, climate, .83, 2025)


def test_exact_july_capacity_is_post_run_validation_not_a_claimed_exact_optimizer_constraint():
    result = {"feasible": True, "details": [{"parcelId": "U1", "area_da": 1,
                                                "chosenCrop": "PREFERRED"}]}
    supply = {f"2025-{month:02d}": 1000.0 for month in range(1, 13)}
    delivery = dict(supply, **{"2025-07": 50.0})
    preferred = {("U1", "PREFERRED", "PRIMARY"): {"2025-07": 100.0}}
    alternative = {("U1", "PREFERRED", "PRIMARY"): {"2025-07": 40.0}}
    release = {"form": "ratio", "values": {"2025": 0.0}}
    rejected = validate_verified_result(result, "S1", preferred, 12000.0, supply,
                                        delivery, release, 2025)
    accepted = validate_verified_result(result, "S1", alternative, 12000.0, supply,
                                        delivery, release, 2025)
    assert rejected["monthly_delivery_validation"]["status"] == "FAIL"
    assert accepted["monthly_delivery_validation"]["status"] == "PASS"
    assert rejected["unit_results"][0]["selected_crops"] == accepted["unit_results"][0]["selected_crops"]


def test_missing_domain_is_not_reported_connected(institutional):
    _, repo, project_id = institutional
    document = repo.get(project_id)
    document["water_data"]["active"].pop("annual_water_supply")
    domain = verified_readiness(document, "S1")["domains"]["annual_water"]
    assert domain["status"] == "NOT_READY"
    assert domain["engine_connected"] is False
    assert domain["dataset_selected"] is False
    assert domain["consumer_available"] is True


def test_material_annual_monthly_mismatch_fails_readiness(institutional):
    _, repo, project_id = institutional
    document = repo.get(project_id)
    annual_id = document["water_data"]["active"]["annual_water_supply"]
    document["water_data"]["datasets"][annual_id]["records"][0]["amount_m3"] = 60001.0
    assert resolve_verified_water(document).annual_supply_m3 == pytest.approx(60001.0)
    document["water_data"]["datasets"][annual_id]["records"][0]["amount_m3"] = 61000.0
    state = verified_readiness(document, "S1")
    assert state["ready"] is False
    assert "Annual/monthly water supply mismatch" in state["blocking_reasons"][0]


def test_every_verified_water_type_requires_explicit_geographic_scope(institutional):
    _, repo, project_id = institutional
    baseline = repo.get(project_id)
    for data_type in ("annual_water_supply", "monthly_water_supply", "delivery_capacity",
                      "environmental_release", "conveyance_efficiency", "perennial_irrigation_requirement"):
        document = deepcopy(baseline)
        dataset = document["water_data"]["datasets"][document["water_data"]["active"][data_type]]
        for row in dataset["records"]:
            row["geographic_scope"] = None
            if data_type == "conveyance_efficiency":
                row["scope"] = None
        scenario = "S2" if data_type == "perennial_irrigation_requirement" else "S1"
        state = verified_readiness(document, scenario)
        assert state["ready"] is False
        assert "explicit geographic scope" in state["blocking_reasons"][0]


def test_every_verified_water_type_blocks_wrong_district(institutional):
    _, repo, project_id = institutional
    baseline = repo.get(project_id)
    for data_type in ("annual_water_supply", "monthly_water_supply", "delivery_capacity",
                      "environmental_release", "conveyance_efficiency", "perennial_irrigation_requirement"):
        document = deepcopy(baseline)
        dataset = document["water_data"]["datasets"][document["water_data"]["active"][data_type]]
        for row in dataset["records"]:
            row["geographic_scope"] = "other-district"
            if data_type == "conveyance_efficiency":
                row["scope"] = "other-district"
        scenario = "S2" if data_type == "perennial_irrigation_requirement" else "S1"
        assert "does not match geographic scope project" in verified_readiness(document, scenario)["blocking_reasons"][0]


def test_matching_explicit_district_scope_is_eligible(institutional):
    _, repo, project_id = institutional
    document = repo.get(project_id)
    document["project"]["pilot_geographic_scope"] = "district-a"
    for dataset in document["water_data"]["datasets"].values():
        if dataset.get("status") != "active":
            continue
        for row in dataset["records"]:
            row["geographic_scope"] = "district-a"
            if dataset["data_type"] == "conveyance_efficiency":
                row["scope"] = "district-a"
    assert resolve_verified_water(document).annual_supply_m3 == pytest.approx(60000.0)


def test_monthly_roles_distinguish_exact_validation_from_s2_optimizer_constraint(institutional):
    _, repo, project_id = institutional
    document = repo.get(project_id)
    body = {"execution_profile": "VERIFIED_INSTITUTIONAL", "scenario": "S2", "algorithm": "GA",
            "seed": 1, "objective": "max_profit", "water_budget_ratio": 1.0,
            "config": {"popSize": 8, "generations": 4, "cxRate": .7, "mutRate": .08}}
    plan = verified_execution_plan(document, configuration(body, document))
    assert plan["consumer_roles"]["monthly_supply"] == "POST_RUN_VALIDATION"
    assert plan["consumer_roles"]["delivery"] == "POST_RUN_VALIDATION"
    assert plan["consumer_roles"]["approximate_s2_monthly_optimizer"] == "OPTIMIZER_CONSTRAINT"


def _accounting_result(profile, planning_year=2025):
    months = {f"2025-{month:02d}": 1000.0 for month in range(1, 13)}
    months.update({month: 1000.0 for month in profile if month not in months})
    context = {"monthly_profiles": {("U1", "CROP", "PRIMARY"): profile},
               "planning_year": planning_year, "annual_supply_m3": 12000.0,
               "monthly_supply_m3": months, "monthly_delivery_capacity_m3": dict(months),
               "environmental_release": {"form": "ratio", "values": {"2025": 0.0}}}
    result = {"scenario": "S1", "total_water_m3": sum(profile.values()), "total_profit_tl": 900.0,
              "feasible": True, "details": [{"parcelId": "U1", "area_da": 1.0,
                                                "chosenCrop": "CROP"}], "classification": "TEST"}
    bundle = SimpleNamespace(algorithm_configuration={"scenario": "S1"})
    return complete_result_contract(result, bundle, {"consumer_roles": {}}, context, [])


def test_cross_year_authoritative_water_is_full_selected_season():
    profile = {"2024-10": 10.0, "2024-11": 10.0, "2024-12": 10.0,
               **{f"2025-{month:02d}": 10.0 for month in range(1, 7)}}
    result = _accounting_result(profile)
    assert result["planning_year_profile_water_m3"] == pytest.approx(60.0)
    assert result["annual_budget_validation"]["demand_m3"] == pytest.approx(60.0)
    assert result["verified_profile_water_m3"] == pytest.approx(90.0)
    assert result["authoritative_water_m3"] == pytest.approx(90.0)
    assert result["unit_results"][0]["total_water_m3"] == pytest.approx(90.0)
    assert result["efficiency_tl_per_m3"] == pytest.approx(10.0)
    assert result["profile_period_start"] == "2024-10"
    assert result["profile_period_end"] == "2025-06"
    assert result["water_reconciliation"]["comparison_scope"] == "FULL_SELECTED_SEASON"


def test_same_year_full_and_planning_year_water_naturally_match():
    result = _accounting_result({"2025-03": 20.0, "2025-04": 30.0})
    assert result["verified_profile_water_m3"] == pytest.approx(50.0)
    assert result["planning_year_profile_water_m3"] == pytest.approx(50.0)
    assert result["annual_budget_validation"]["demand_m3"] == pytest.approx(50.0)


def test_readiness_preserves_unrelated_domains_and_exposes_climate(institutional):
    _, repo, project_id = institutional
    baseline = repo.get(project_id)
    valid = verified_readiness(baseline, "S1")
    assert valid["ready"] is True and valid["domains"]["climate"]["status"] == "READY"
    assert valid["domains"]["perennial_requirement"]["status"] == "NOT_REQUIRED_FOR_SCENARIO"
    broken = deepcopy(baseline)
    broken["water_data"]["active"].pop("annual_water_supply")
    state = verified_readiness(broken, "S1")
    assert state["ready"] is False
    assert state["domains"]["annual_water"]["dataset_selected"] is False
    for name in ("monthly_supply", "delivery", "economics", "phenology", "climate", "candidates", "current_pattern"):
        assert state["domains"][name]["dataset_selected"] is True, name
        assert state["domains"][name]["engine_connected"] is True, name


def test_climate_only_failure_does_not_falsify_other_domains(institutional):
    _, repo, project_id = institutional
    document = repo.get(project_id)
    document["scientific_inputs"]["seasonal_resources"]["monthly_climate"] = []
    state = verified_readiness(document, "S1")
    assert state["ready"] is False
    assert state["domains"]["climate"]["connection_state"] == "MISSING_DATASET"
    assert state["domains"]["annual_water"]["dataset_selected"] is True
    assert state["domains"]["annual_water"]["engine_connected"] is True


def test_physical_release_is_selected_but_not_executable(institutional):
    _, repo, project_id = institutional
    document = repo.get(project_id)
    dataset = document["water_data"]["datasets"][document["water_data"]["active"]["environmental_release"]]
    dataset["records"][0].update(release_form="monthly_release", month="2025-01", release_m3=1.0)
    domain = verified_readiness(document, "S1")["domains"]["environmental_release"]
    assert domain["dataset_selected"] is True
    assert domain["engine_connected"] is False
    assert domain["connection_state"] == "NOT_EXECUTABLE_WITH_CURRENT_MODE"


def test_readiness_one_broken_domain_does_not_copy_failure_globally(institutional):
    _, repo, project_id = institutional
    baseline = repo.get(project_id)
    cases = {
        "annual_water": lambda d: d["water_data"]["active"].pop("annual_water_supply"),
        "monthly_supply": lambda d: d["water_data"]["active"].pop("monthly_water_supply"),
        "delivery": lambda d: d["water_data"]["active"].pop("delivery_capacity"),
        "conveyance": lambda d: d["water_data"]["active"].pop("conveyance_efficiency"),
        "economics": lambda d: d["economic_data"]["datasets"][
            d["economic_data"]["active"]["crop_net_profit|2025|project|catalog"]].update(derivation_status="STALE"),
        "crop_parameters": lambda d: d["crop_parameter_data"]["datasets"][
            d["crop_parameter_data"]["active"]["crop_water_parameters|2025|project"]]["records"][0].update(
                resolution_status="AMBIGUOUS"),
        "phenology": lambda d: d["crop_parameter_data"]["active"].pop("crop_phenology|2025|project"),
        "candidates": lambda d: d["scientific_inputs"].update(candidates=[]),
        "current_pattern": lambda d: [value.update(status="inactive") for value in d["imports"].values()
                                      if value.get("data_type") == "scientific_inputs"],
    }
    for broken_name, mutation in cases.items():
        document = deepcopy(baseline); mutation(document)
        readiness = verified_readiness(document, "S1")
        assert readiness["ready"] is False, broken_name
        assert readiness["domains"][broken_name]["status"] == "NOT_READY", broken_name
        comparison = "monthly_supply" if broken_name != "monthly_supply" else "annual_water"
        assert readiness["domains"][comparison]["dataset_selected"] is True, broken_name
        assert readiness["domains"][comparison]["engine_connected"] is True, broken_name
        if broken_name != "climate":
            assert readiness["domains"]["climate"]["dataset_selected"] is True, broken_name


def test_climate_readiness_modes_coverage_scope_and_source(institutional):
    _, repo, project_id = institutional
    baseline = repo.get(project_id)
    rows = baseline["scientific_inputs"]["seasonal_resources"]["monthly_climate"]
    year_specific = deepcopy(baseline)
    for row in year_specific["scientific_inputs"]["seasonal_resources"]["monthly_climate"]:
        row["climate_mode"] = "YEAR_SPECIFIC"
    assert verified_readiness(year_specific, "S1")["domains"]["climate"]["status"] == "READY"

    cases = []
    missing_exact = deepcopy(year_specific)
    target = str(rows[0]["parcel_id"])
    missing_exact["scientific_inputs"]["seasonal_resources"]["monthly_climate"] = [
        row for row in missing_exact["scientific_inputs"]["seasonal_resources"]["monthly_climate"]
        if not (str(row["parcel_id"]) == target and str(row["month"])[:7] == "2025-03")]
    cases.append(missing_exact)
    missing_normal = deepcopy(baseline)
    missing_normal["scientific_inputs"]["seasonal_resources"]["monthly_climate"] = [
        row for row in missing_normal["scientific_inputs"]["seasonal_resources"]["monthly_climate"]
        if not (str(row["parcel_id"]) == target and str(row["month"])[5:7] == "12")]
    cases.append(missing_normal)
    wrong_scope = deepcopy(baseline); wrong_scope["scientific_inputs"]["seasonal_resources"]["monthly_climate"][0]["geographic_scope"] = "wrong"
    cases.append(wrong_scope)
    missing_source = deepcopy(baseline); missing_source["scientific_inputs"]["seasonal_resources"]["monthly_climate"][0]["source"] = None
    cases.append(missing_source)
    no_climate = deepcopy(baseline); no_climate["scientific_inputs"]["seasonal_resources"]["monthly_climate"] = []
    cases.append(no_climate)
    for document in cases:
        readiness = verified_readiness(document, "S1")
        assert readiness["ready"] is False
        assert readiness["domains"]["climate"]["status"] == "NOT_READY"
        assert readiness["domains"]["annual_water"]["engine_connected"] is True
