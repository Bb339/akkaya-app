"""BUG-01 monthly delivery unit and key-contract regression tests."""
import json
from pathlib import Path

import numpy as np

import app


FIXTURE = Path(__file__).parent / "fixtures/scientific_fix_phase2/minimal_monthly_delivery.json"


def test_phase1_date_keyed_dictionary_bug_is_reproduced_before_fix():
    fixture = json.loads(FIXTURE.read_text())
    area = np.array([fixture["analysis_units"][0]["area_da"]])
    monthly_per_da = np.full((1, 1, 12), fixture["monthly_water_m3_da"])
    demand = app._monthly_demand_from_mu(
        area, monthly_per_da, np.zeros_like(monthly_per_da),
        np.array([0]), np.array([0]))
    weights = {row["month"]: 1 / 12 for row in fixture["delivery"]}
    capacities = {row["month"]: row["max_delivery_m3_assumed"] for row in fixture["delivery"]}

    assert demand == [fixture["expected_monthly_demand_m3"]] * 12
    assert app.compute_monthly_delivery_report(
        sum(demand), weights, capacities, monthly_demand_override=demand) is None
