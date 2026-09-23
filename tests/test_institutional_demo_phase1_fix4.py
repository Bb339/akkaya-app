from copy import deepcopy

import pytest

from test_institutional_demo_phase1 import institutional
from kds.adapters.institutional import verified_execution_plan, verified_readiness
from kds.application.optimization import configuration


def _baseline(institutional):
    _, repo, project_id = institutional
    return repo.get(project_id)


@pytest.mark.parametrize("domain,mutation,connection", [
    ("economics", lambda d: d["economic_data"]["datasets"][
        d["economic_data"]["active"]["crop_net_profit|2025|project|catalog"]].update(
            derivation_status="STALE"), "STALE"),
    ("crop_parameters", lambda d: d["crop_parameter_data"]["datasets"][
        d["crop_parameter_data"]["active"]["crop_water_parameters|2025|project"]]["records"][0].update(
            resolution_status="AMBIGUOUS"), "AMBIGUOUS_OR_INCOMPLETE"),
    ("annual_water", lambda d: d["water_data"]["datasets"][
        d["water_data"]["active"]["annual_water_supply"]]["records"][0].update(
            geographic_scope="wrong-scope"), "INVALID_SCOPE"),
])
def test_active_invalid_dataset_retains_selection_truth_and_fails_closed(
        institutional, domain, mutation, connection):
    document = _baseline(institutional)
    mutation(document)
    readiness = verified_readiness(document, "S1")
    broken = readiness["domains"][domain]
    assert readiness["ready"] is False
    assert broken["status"] == "NOT_READY"
    assert broken["dataset_selected"] is True
    assert broken["dataset_valid"] is False
    assert broken["consumer_available"] is True
    assert broken["engine_connected"] is False
    assert broken["connection_state"] == connection
    assert broken.get("dataset") or broken.get("datasets")
    assert readiness["domains"]["monthly_supply"]["dataset_valid"] is True
    assert readiness["domains"]["monthly_supply"]["engine_connected"] is True
    assert readiness["domains"]["climate"]["dataset_valid"] is True
    assert readiness["domains"]["climate"]["engine_connected"] is True
    with pytest.raises(ValueError):
        verified_execution_plan(document, configuration({
            "execution_profile": "VERIFIED_INSTITUTIONAL", "scenario": "S1", "algorithm": "GA",
            "objective": "max_profit", "seed": 1, "water_budget_ratio": 1.0,
            "config": {"popSize": 8, "generations": 4, "cxRate": .7, "mutRate": .08},
        }, document))


@pytest.mark.parametrize("domain,remove", [
    ("annual_water", lambda d: d["water_data"]["active"].pop("annual_water_supply")),
    ("economics", lambda d: d["economic_data"]["active"].pop(
        "crop_net_profit|2025|project|catalog")),
    ("crop_parameters", lambda d: d["crop_parameter_data"]["active"].pop(
        "crop_water_parameters|2025|project")),
])
def test_missing_required_dataset_remains_unselected(institutional, domain, remove):
    document = _baseline(institutional)
    remove(document)
    broken = verified_readiness(document, "S1")["domains"][domain]
    assert broken["status"] == "NOT_READY"
    assert broken["dataset_selected"] is False
    assert broken["dataset_valid"] is False
    assert broken["engine_connected"] is False
    assert broken["connection_state"] == "MISSING_DATASET"


@pytest.mark.parametrize("mutation,connection", [
    (lambda d: d["project"].update(planning_year=2026), "INVALID_YEAR"),
    (lambda d: d["project"].update(pilot_geographic_scope="district-x"), "INVALID_SCOPE"),
])
def test_economics_active_pointer_survives_year_or_scope_mismatch(institutional, mutation, connection):
    document = _baseline(institutional)
    mutation(document)
    economics = verified_readiness(document, "S1")["domains"]["economics"]
    assert economics["dataset_selected"] is True
    assert economics["dataset_valid"] is False
    assert economics["engine_connected"] is False
    assert economics["connection_state"] == connection
    assert economics["datasets"]


def test_domain_contract_and_physical_release_keep_independent_axes(institutional):
    document = _baseline(institutional)
    release = document["water_data"]["datasets"][
        document["water_data"]["active"]["environmental_release"]]
    release["records"][0].update(release_form="monthly_release", month="2025-01", release_m3=1.0)
    readiness = verified_readiness(document, "S1")
    required = {"status", "dataset_selected", "dataset_valid", "consumer_available",
                "engine_connected", "connection_state", "consumer_role", "execution_scope",
                "blocking_reason", "blocking_reasons"}
    assert all(required <= set(domain) for domain in readiness["domains"].values())
    physical = readiness["domains"]["environmental_release"]
    assert physical["dataset_selected"] is True
    assert physical["dataset_valid"] is True
    assert physical["consumer_available"] is True
    assert physical["engine_connected"] is False
    assert physical["connection_state"] == "NOT_EXECUTABLE_WITH_CURRENT_MODE"


def test_s1_and_s2_perennial_requirement_semantics_remain_distinct(institutional):
    document = _baseline(institutional)
    s1 = verified_readiness(deepcopy(document), "S1")["domains"]["perennial_requirement"]
    s2 = verified_readiness(deepcopy(document), "S2")["domains"]["perennial_requirement"]
    assert (s1["status"], s1["dataset_selected"], s1["dataset_valid"], s1["engine_connected"]) == (
        "NOT_REQUIRED_FOR_SCENARIO", True, True, False)
    assert (s2["status"], s2["dataset_selected"], s2["dataset_valid"], s2["engine_connected"]) == (
        "READY", True, True, True)
