from copy import deepcopy

import pytest

import app
from test_institutional_demo_phase1 import institutional
from kds.adapters.institutional import resolve_verified_water, verified_execution_plan, verified_readiness
from kds.application.optimization import configuration
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
        state = verified_readiness(document, "S1")
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
        assert "does not match geographic scope project" in verified_readiness(document, "S1")["blocking_reasons"][0]


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
