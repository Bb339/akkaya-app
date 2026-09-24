from copy import deepcopy

import pytest

from test_institutional_demo_phase1 import institutional
from kds.adapters.institutional import verified_execution_plan, verified_readiness
from kds.application.optimization import configuration


CROP_NET_POINTER = "crop_net_profit|2025|project|catalog"
SEASONAL_POINTER = "seasonal_economics|2025|project|catalog"
REQUIRED_BY_SCENARIO = {
    "S1": ["crop_net_profit"],
    "S2": ["crop_net_profit", "seasonal_economics"],
}


def _baseline(institutional):
    _, repo, project_id = institutional
    return repo.get(project_id)


def _configuration(document, scenario):
    return configuration({
        "execution_profile": "VERIFIED_INSTITUTIONAL",
        "scenario": scenario,
        "algorithm": "GA",
        "objective": "max_profit",
        "seed": 1,
        "water_budget_ratio": 1.0,
        "config": {"popSize": 8, "generations": 4, "cxRate": .7, "mutRate": .08},
    }, document)


def _remove_required(document, *, crop_net=False, seasonal=False):
    active = document["economic_data"]["active"]
    if crop_net:
        active.pop(CROP_NET_POINTER)
    if seasonal:
        active.pop(SEASONAL_POINTER)


def _assert_economics(
        document, scenario, *, selected, complete, missing, connection, valid=False, connected=False):
    economics = verified_readiness(document, scenario)["domains"]["economics"]
    assert economics["dataset_selected"] is selected
    assert economics["selection_complete"] is complete
    assert economics["required_dataset_types"] == REQUIRED_BY_SCENARIO[scenario]
    assert economics["missing_required_datasets"] == missing
    assert economics["dataset_valid"] is valid
    assert economics["consumer_available"] is True
    assert economics["engine_connected"] is connected
    assert economics["connection_state"] == connection
    assert bool(economics["datasets"]) is selected
    assert sorted({item["data_type"] for item in economics["datasets"]}) == economics[
        "selected_dataset_types"]
    return economics


def test_s2_partial_and_complete_selection_states_are_truthful_and_fail_closed(institutional):
    baseline = _baseline(institutional)
    baseline_domains = verified_readiness(deepcopy(baseline), "S2")["domains"]

    cases = []
    crop_only = deepcopy(baseline)
    _remove_required(crop_only, seasonal=True)
    cases.append((crop_only, True, ["seasonal_economics"]))

    seasonal_only = deepcopy(baseline)
    _remove_required(seasonal_only, crop_net=True)
    cases.append((seasonal_only, True, ["crop_net_profit"]))

    optional_only = deepcopy(baseline)
    _remove_required(optional_only, crop_net=True, seasonal=True)
    cases.append((optional_only, True, ["crop_net_profit", "seasonal_economics"]))

    no_economics = deepcopy(baseline)
    no_economics["economic_data"]["active"].clear()
    no_economics["economic_data"]["datasets"].clear()
    cases.append((no_economics, False, ["crop_net_profit", "seasonal_economics"]))

    for document, selected, missing in cases:
        economics = _assert_economics(
            document, "S2", selected=selected, complete=False, missing=missing,
            connection="MISSING_DATASET")
        if selected:
            assert economics["selected_dataset_types"]
        else:
            assert economics["selected_dataset_types"] == []
        with pytest.raises(ValueError):
            verified_execution_plan(document, _configuration(document, "S2"))
        current_domains = verified_readiness(document, "S2")["domains"]
        for domain in ("monthly_supply", "climate", "annual_water", "crop_parameters"):
            assert current_domains[domain] == baseline_domains[domain]

    complete = _assert_economics(
        deepcopy(baseline), "S2", selected=True, complete=True, missing=[],
        connection="CONNECTED", valid=True, connected=True)
    assert {"crop_net_profit", "seasonal_economics"} <= set(
        complete["selected_dataset_types"])


def test_s1_optional_only_is_selected_but_incomplete_and_fails_closed(institutional):
    document = _baseline(institutional)
    _remove_required(document, crop_net=True)
    economics = _assert_economics(
        document, "S1", selected=True, complete=False, missing=["crop_net_profit"],
        connection="MISSING_DATASET")
    assert set(economics["selected_dataset_types"]) - {"crop_net_profit"}
    with pytest.raises(ValueError):
        verified_execution_plan(document, _configuration(document, "S1"))


def test_invalid_selected_economics_preserves_completeness_and_selection(institutional):
    baseline = _baseline(institutional)

    stale = deepcopy(baseline)
    stale_dataset = stale["economic_data"]["datasets"][
        stale["economic_data"]["active"][CROP_NET_POINTER]]
    stale_dataset.update(derivation_status="STALE")
    _assert_economics(
        stale, "S1", selected=True, complete=True, missing=[], connection="STALE")

    wrong_year = deepcopy(baseline)
    wrong_year["project"]["planning_year"] = 2026
    _assert_economics(
        wrong_year, "S1", selected=True, complete=True, missing=[], connection="INVALID_YEAR")

    wrong_scope = deepcopy(baseline)
    wrong_scope["project"]["pilot_geographic_scope"] = "district-x"
    _assert_economics(
        wrong_scope, "S1", selected=True, complete=True, missing=[], connection="INVALID_SCOPE")

    for document in (stale, wrong_year, wrong_scope):
        with pytest.raises(ValueError):
            verified_execution_plan(document, _configuration(document, "S1"))
