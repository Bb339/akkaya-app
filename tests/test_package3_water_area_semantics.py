import pandas as pd
import pytest

import app
from kds.application.result_presentation import analysis_csv_rows, present_run_for_ui
from kds.science.results import _metrics


def _matrix(*, area=10.0, quota=500.0, water=100.0, crop="BUĞDAY", current="BUĞDAY"):
    return pd.DataFrame([{
        "parcel_id": "U1", "candidate_crop": crop, "candidate_crop_id": crop,
        "candidate_crop_norm": crop, "current_crop": current, "area_da": area,
        "water_m3_da": water, "profit_tl_da": 1000.0, "yield_ton_da": 1.0,
        "current_quota_m3": quota, "quota_area_fair_per_da_m3": quota,
        "village": "TEST", "irrigation_text": "test",
    }])


def _parcel(*, area=10.0, crop="BUĞDAY", parcel_type="field"):
    return {"id": "U1", "name": "Synthetic unit", "area_da": area,
            "current_crop": crop, "parcel_type": parcel_type,
            "water_m3": area * 100.0, "profit_tl": area * 1000.0}


def _problem(monkeypatch, frame, parcel, policy):
    monkeypatch.setattr(app, "load_matrix_candidates", lambda: frame.copy())
    monkeypatch.setattr(app, "optional_reference", lambda _name: pd.DataFrame())
    return app._matrix_build_problem([parcel], "water_saving", 1.0, year=2024,
                                     options={"areaPolicy": policy, "seed": 1})


def test_full_area_does_not_shrink_candidate_to_quota(monkeypatch):
    problem = _problem(monkeypatch, _matrix(), _parcel(), "full_area")
    assert problem["area_policy"] == "full_area"
    assert problem["parcels"][0]["options"] == []
    diagnostic = problem["parcels"][0]["diagnostic_options"][0]
    assert diagnostic["fullAreaDa"] == 10
    assert diagnostic["area_da"] == 0
    assert diagnostic["fullAreaWaterM3"] == 1000


def test_full_area_no_solution_returns_no_feasible_without_engine_fallback(monkeypatch):
    _problem(monkeypatch, _matrix(), _parcel(), "full_area")
    monkeypatch.setattr(app, "load_matrix_candidates", lambda: _matrix())
    monkeypatch.setattr(app, "optional_reference", lambda _name: pd.DataFrame())
    result = app.optimize_from_excel_matrix([_parcel()], "GA", "water_saving", 1.0,
                                            year=2024, options={"areaPolicy": "full_area"})
    assert result["solution_status"] == "no_feasible"
    assert result["selectable"] is False
    assert result["total_water_m3"] is None


def test_partial_planting_area_totals_are_conserved(monkeypatch):
    problem = _problem(monkeypatch, _matrix(), _parcel(), "partial_planting")
    result = app._matrix_solution_to_payload(problem, [0], "GA")
    area = result["area_accounting"]
    assert area["reference_physical_area_da"] == 10
    assert area["proposed_planted_area_da"] == 5
    assert area["unplanted_area_da"] == 5
    assert area["area_utilization_ratio"] == pytest.approx(0.5)


def test_same_crop_partial_plan_exposes_area_effect(monkeypatch):
    problem = _problem(monkeypatch, _matrix(), _parcel(), "partial_planting")
    water = app._matrix_solution_to_payload(problem, [0], "GA")["water_accounting"]
    assert water["reference_calculated_need_m3"] == 1000
    assert water["counterfactual_full_reference_area_need_m3"] == 1000
    assert water["proposed_calculated_need_m3"] == 500
    assert water["crop_pattern_effect_m3"] == 0
    assert water["area_reduction_effect_m3"] == 500


def test_orchard_identity_and_full_physical_area_are_preserved(monkeypatch):
    parcel = _parcel(crop="ELMA", parcel_type="orchard")
    problem = _problem(monkeypatch, _matrix(quota=1200, crop="ELMA", current="ELMA"), parcel,
                       "partial_planting")
    option = problem["parcels"][0]["options"][0]
    assert problem["parcels"][0]["lock_kind"] == "orchard"
    assert option["name"] == "ELMA"
    assert option["area_da"] == parcel["area_da"]


def test_insufficient_orchard_budget_is_diagnostic_not_success(monkeypatch):
    parcel = _parcel(crop="ELMA", parcel_type="orchard")
    frame = _matrix(quota=500, crop="ELMA", current="ELMA")
    monkeypatch.setattr(app, "load_matrix_candidates", lambda: frame.copy())
    monkeypatch.setattr(app, "optional_reference", lambda _name: pd.DataFrame())
    result = app.optimize_from_excel_matrix([parcel], "GA", "water_saving", 1.0,
                                            year=2024, options={"areaPolicy": "partial_planting"})
    assert result["solution_status"] == "no_feasible"
    assert result["diagnostic_units"][0]["orchard_locked"] is True
    assert result["diagnostic_units"][0]["required_full_area_water_m3"] == 1000
    assert result["diagnostic_units"][0]["budget_gap_m3"] == 500


def test_rainfed_style_need_is_not_labeled_as_observed_use(monkeypatch):
    problem = _problem(monkeypatch, _matrix(crop="ARPA"), _parcel(crop="ARPA"),
                       "partial_planting")
    semantics = app._matrix_solution_to_payload(problem, [0], "GA")["water_accounting"]
    assert "REQUIREMENT" in semantics["value_semantics"]
    assert "NOT_OBSERVED_USE" in semantics["value_semantics"]


def test_need_derived_budget_is_not_documented_allocation(monkeypatch):
    problem = _problem(monkeypatch, _matrix(), _parcel(), "partial_planting")
    semantics = app._matrix_solution_to_payload(problem, [0], "GA")["water_accounting"]
    assert semantics["scenario_budget_nature"] == "CALCULATED_REFERENCE_SCENARIO_CEILING"
    assert semantics["documented_allocation_m3"] is None
    assert semantics["documented_allocation_status"] == "NOT_DEFINED"


def _run_result():
    return {
        "id": "run-1", "project_id": "project-1", "scenario": "S1",
        "execution_profile": "REFERENCE_DEMO", "result": {
            "feasible": True, "area_policy": "partial_planting",
            "area_accounting": {"reference_physical_area_da": 10.0,
                                "proposed_planted_area_da": 5.0,
                                "unplanted_area_da": 5.0,
                                "seasonal_planted_area_da": 5.0,
                                "area_utilization_ratio": 0.5},
            "water_accounting": {"value_semantics": "CALCULATED_IRRIGATION_REQUIREMENT_NOT_OBSERVED_OR_APPLIED_WATER",
                                 "reference_calculated_need_m3": 1000.0,
                                 "proposed_calculated_need_m3": 500.0,
                                 "scenario_budget_m3": 500.0,
                                 "scenario_budget_nature": "CALCULATED_REFERENCE_SCENARIO_CEILING",
                                 "documented_allocation_m3": None,
                                 "calculated_need_reduction_m3": 500.0,
                                 "budget_gap_m3": 0.0},
            "details": [{"parcelId": "U1", "chosenCrop": "BUĞDAY", "area_da": 5.0,
                         "planted_area_da": 5.0, "water_m3": 500.0, "profit_tl": 5000.0}],
            "unit_results": [],
        },
        "provenance": {"input_snapshot": {"project_revision": 1}},
    }


def _document():
    return {"data_revision": 1, "analysis_state": {},
            "analysis_units": [{"external_id": "U1", "area_da": 10.0,
                                "current_crop": "BUĞDAY"}]}


def test_api_presentation_and_csv_share_area_water_totals():
    view = present_run_for_ui(_run_result(), _document())
    row = analysis_csv_rows(_run_result(), _document())[0]
    assert row["area_policy"] == view["result"]["area_policy"]
    assert row["reference_physical_area_da"] == view["result"]["area_accounting"]["reference_physical_area_da"]
    assert row["proposed_calculated_need_m3"] == view["result"]["water_accounting"]["proposed_calculated_need_m3"]


def test_legacy_result_without_policy_is_presented_as_unknown():
    run = _run_result()
    run["result"].pop("area_policy")
    run["result"].pop("area_accounting")
    view = present_run_for_ui(run, _document())
    assert view["result"]["area_policy"] == "unknown_legacy"
    assert "tam alan varsayılmadı" in view["result"]["area_accounting"]["warning"]


def test_no_feasible_does_not_report_hundred_percent_saving(monkeypatch):
    problem = _problem(monkeypatch, _matrix(), _parcel(), "full_area")
    result = app.optimize_from_excel_matrix([_parcel()], "GA", "water_saving", 1.0,
                                            year=2024, options={"areaPolicy": "full_area"})
    assert result["water_accounting"]["proposed_calculated_need_m3"] is None
    assert result["water_accounting"]["calculated_need_reduction_pct"] is None


def test_s2_seasonal_area_is_separate_from_unique_physical_area():
    details = [{"parcelId": "U1", "area_da": 10.0,
                "primary": {"crop": "BUĞDAY", "area_da": 10.0, "water_m3": 100, "profit_tl": 200},
                "secondary": {"crop": "FASULYE", "area_da": 10.0, "water_m3": 80, "profit_tl": 150}}]
    metrics = _metrics(details, 10.0, feasible=True)
    assert metrics["physical_planted_area_da"] == 10
    assert metrics["active_area_da"] == 10
    assert metrics["seasonal_planted_area_da"] == 20
    assert metrics["fallow_area_da"] == 0

