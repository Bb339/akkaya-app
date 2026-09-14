"""BUG-01 monthly delivery unit and key-contract regression tests."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import app
from kds.application.readiness import readiness
from test_analysis_workflow import example, with_seasons


FIXTURE = Path(__file__).parent / "fixtures/scientific_fix_phase2/minimal_monthly_delivery.json"


def test_date_keyed_dictionary_is_evaluated_in_canonical_monthly_unit():
    fixture = json.loads(FIXTURE.read_text())
    area = np.array([fixture["analysis_units"][0]["area_da"]])
    monthly_per_da = np.full((1, 1, 12), fixture["monthly_water_m3_da"])
    demand = app._monthly_demand_from_mu(
        area, monthly_per_da, np.zeros_like(monthly_per_da),
        np.array([0]), np.array([0]))
    weights = {row["month"]: 1 / 12 for row in fixture["delivery"]}
    capacities = {row["month"]: row["max_delivery_m3_assumed"] for row in fixture["delivery"]}

    assert demand == [fixture["expected_monthly_demand_m3"]] * 12
    report = app.compute_monthly_delivery_report(
        sum(demand), weights, capacities, monthly_demand_override=demand)
    assert report["unit"] == "m3/month" and report["period"] == "calendar_month"
    assert report["status"] == "violation" and report["feasible_monthly"] is False
    assert report["demand_m3"] == [fixture["expected_monthly_demand_m3"]] * 12
    assert report["cap_m3"] == [fixture["expected_monthly_capacity_m3"]] * 12
    assert report["exceed_m3"] == [fixture["expected_violation_m3"]] * 12
    assert report["violating_months"] == list(range(1, 13))
    assert report["total_demand_m3"] == 240.0
    assert report["total_capacity_m3"] == fixture["annual_budget_m3"]


def test_monthly_table_normalizes_period_keys_without_volume_conversion():
    fixture = json.loads(FIXTURE.read_text())
    frame = pd.DataFrame(fixture["delivery"])
    values = app._canonical_monthly_table_values(
        frame, fixture["planning_year"], "max_delivery_m3_assumed")
    assert values == {month: fixture["expected_monthly_capacity_m3"] for month in range(1, 13)}
    assert sum(values.values()) == fixture["annual_budget_m3"]


def test_mm_m3_per_da_and_area_are_applied_exactly_once():
    fixture = json.loads(FIXTURE.read_text())
    area_da = fixture["analysis_units"][0]["area_da"]
    monthly_m3_da = fixture["monthly_water_m3_da"]
    demand = app._monthly_demand_from_mu(
        np.array([area_da]), np.full((1, 1, 12), monthly_m3_da),
        np.zeros((1, 1, 12)), np.array([0]), np.array([0]))
    assert demand == [area_da * monthly_m3_da] * 12
    assert sum(demand) == area_da * monthly_m3_da * 12


def test_existing_fao_monthly_constraint_consumes_canonical_month_keys():
    common = dict(
        chosen_primary=np.array([0]), chosen_secondary=np.array([0]),
        areas=np.array([10.0]), W1=np.array([[24.0]]), R1=np.array([[100.0]]),
        W2=np.array([[0.0]]), R2=np.array([[0.0]]), budget=1000.0,
        objective="water_saving", crop_list=["ARPA"],
        crop_family={"ARPA": "poaceae"}, rotation_rules=pd.DataFrame(),
        month_weights={month: 1/12 for month in range(1, 13)},
        month_use1=np.full((1, 1, 12), 2.0),
        month_use2=np.zeros((1, 1, 12)), min_unique_crops=1,
        max_share_per_crop=None, year=2025, parcel_ids=["UNIT-1"])
    high = app._score_solution_two_season(
        month_caps={month: 100.0 for month in range(1, 13)}, **common)
    low = app._score_solution_two_season(
        month_caps={month: 10.0 for month in range(1, 13)}, **common)
    assert high[1:] == low[1:] == (240.0, 1000.0)
    assert low[0] < high[0]


def test_existing_calibrated_proportional_constraint_preserves_m3_values():
    common = dict(
        chosen_primary=np.array([0]), chosen_secondary=np.array([0]),
        areas=np.array([10.0]), W1=np.array([[24.0]]), R1=np.array([[100.0]]),
        W2=np.array([[0.0]]), R2=np.array([[0.0]]), budget=1000.0,
        objective="water_saving", crop_list=["ARPA"],
        crop_family={"ARPA": "poaceae"}, rotation_rules=pd.DataFrame(),
        month_weights={month: 1/12 for month in range(1, 13)},
        month_use1=None, month_use2=None, min_unique_crops=1,
        max_share_per_crop=None, year=2025, parcel_ids=["UNIT-1"])
    high = app._score_solution_two_season(
        month_caps={month: 100.0 for month in range(1, 13)}, **common)
    low = app._score_solution_two_season(
        month_caps={month: 10.0 for month in range(1, 13)}, **common)
    assert high[1:] == low[1:] == (240.0, 1000.0)
    assert low[0] < high[0]


@pytest.mark.parametrize("mutation, match", [
    (lambda rows: rows.pop(), "exactly 12"),
    (lambda rows: rows.__setitem__(1, {**rows[1], "month": rows[0]["month"]}), "duplicate"),
    (lambda rows: rows[0].__setitem__("max_delivery_m3_assumed", 0), "finite and positive"),
    (lambda rows: rows[0].__setitem__("max_delivery_m3_assumed", -1), "finite and positive"),
    (lambda rows: rows[0].__setitem__("max_delivery_m3_assumed", float("nan")), "finite and positive"),
])
def test_engine_boundary_rejects_invalid_monthly_capacity(mutation, match):
    rows = json.loads(FIXTURE.read_text())["delivery"]
    mutation(rows)
    with pytest.raises(ValueError, match=match):
        app._canonical_monthly_table_values(
            pd.DataFrame(rows), 2025, "max_delivery_m3_assumed")


@pytest.mark.parametrize("change", [
    lambda rows: rows.pop(),
    lambda rows: rows.__setitem__(1, {**rows[1], "month": rows[0]["month"]}),
    lambda rows: rows[0].__setitem__("max_delivery_m3_assumed", 0),
    lambda rows: rows[0].__setitem__("max_delivery_m3_assumed", -1),
    lambda rows: rows[0].__setitem__("max_delivery_m3_assumed", float("nan")),
    lambda rows: rows[0].__setitem__("unit", "m3/day"),
    lambda rows: rows[0].__setitem__("period", "day"),
])
def test_s2_readiness_rejects_invalid_delivery_contract(change):
    document = with_seasons(example())
    rows = document["scientific_inputs"]["seasonal_resources"]["delivery"]
    change(rows)
    report = readiness(document)
    assert report["scenarios"]["S2"]["status"] == "NOT_READY"
    assert any(issue["code"] == "seasonal_validation"
               for issue in report["scenarios"]["S2"]["issues"])


def test_legacy_rows_receive_explicit_readiness_contract_without_migration():
    document = with_seasons(example())
    before = json.loads(json.dumps(document))
    report = readiness(document)
    contract = report["scientific_data"]["unit_contracts"]
    assert report["scenarios"]["S2"]["status"] == "READY"
    assert contract["delivery_capacity"] == "m3/month; calendar_month"
    assert document == before


def test_akkaya_before_after_snapshot_is_dimensionally_consistent():
    snapshot = json.loads((FIXTURE.parent / "akkaya_before_after.json").read_text())
    rows = snapshot["months"]
    assert len(rows) == 12 and all(row["violation"] for row in rows)
    assert sum(row["delivery_capacity_raw_m3"] for row in rows) == snapshot["sum_monthly_delivery_raw_m3"]
    assert sum(row["delivery_capacity_effective_m3"] for row in rows) == pytest.approx(snapshot["sum_monthly_delivery_effective_m3"])
    assert sum(row["demand_m3"] for row in rows) == pytest.approx(snapshot["sum_monthly_demand_m3"])
    assert all(row["delivery_capacity_effective_m3"] ==
               pytest.approx(row["delivery_capacity_raw_m3"] * (1-snapshot["environmental_flow_ratio"]))
               for row in rows)
    assert snapshot["before"]["engine_report"] is None
    assert snapshot["after"]["engine_report_status"] == "violation"
    for field in ("final_water_m3", "final_profit_tl", "feasible",
                  "raw_plan_hash", "final_plan_hash", "protected_perennial_count"):
        assert snapshot["before"][field] == snapshot["after"][field]
