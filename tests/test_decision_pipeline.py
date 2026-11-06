import json
import math
import re
import threading
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

import app as app_module
from app import app

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def client():
    return app.test_client()


def optimize_payload(scenario_type="single", objective="water_saving", algorithm="GA", ratio=1.0,
                     enforce_delivery_caps=None):
    season_source = "s2" if scenario_type == "double" else "s1"
    payload = {
        "selectedParcelIds": ["P1"],
        "algorithm": algorithm,
        "scenario": objective,
        "waterBudgetRatio": ratio,
        "year": 2024,
        "options": {
            "scenarioType": scenario_type,
            "seasonSource": season_source,
            "twoSeason": scenario_type == "double",
            "seed": 123,
            "fastPreview": True,
            "fastRepeatCount": 3,
        },
    }
    if enforce_delivery_caps is not None:
        payload["options"]["enforceDeliveryCaps"] = bool(enforce_delivery_caps)
    return payload


def post_optimize(client, **kwargs):
    resp = client.post("/api/optimize", json=optimize_payload(**kwargs))
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "OK"
    for key in ("context", "baseline", "selected_plan", "alternatives", "charts", "tables", "diagnostics"):
        assert key in data
    return data


def js_function_body(source, name):
    match = re.search(rf"function\s+{name}\s*\([^)]*\)\s*\{{", source)
    assert match, f"{name} function not found"
    idx = match.end()
    depth = 1
    while idx < len(source) and depth:
        if source[idx] == "{":
            depth += 1
        elif source[idx] == "}":
            depth -= 1
        idx += 1
    assert depth == 0, f"{name} function body was not closed"
    return source[match.end():idx - 1]


def test_baseline_is_invariant_across_objective_and_scenario(client):
    single_water = post_optimize(client, scenario_type="single", objective="water_saving")
    single_profit = post_optimize(client, scenario_type="single", objective="max_profit")
    double_balanced = post_optimize(client, scenario_type="double", objective="water_efficiency", ratio=5.0)

    assert single_water["baseline"] == single_profit["baseline"]
    assert single_water["baseline"] == double_balanced["baseline"]


def test_s1_single_crop_and_alternatives(client):
    data = post_optimize(client, scenario_type="single", objective="water_saving")
    plan = data["selected_plan"]
    feasible_alts = [a for a in data["alternatives"] if a.get("feasible")]

    assert data["context"]["scenario_type"] == "single"
    assert len(plan["crops"]) == 1
    assert plan["feasible"] is True
    assert len(data["alternatives"]) >= 4 or "Kisitlar nedeniyle" in " ".join(data["diagnostics"]["warnings"])
    assert len(feasible_alts) >= 4 or "Kisitlar nedeniyle" in " ".join(data["diagnostics"]["warnings"])


def test_s2_two_crop_pattern_and_no_single_main(client):
    data = post_optimize(client, scenario_type="double", objective="water_saving", ratio=5.0)
    plan = data["selected_plan"]
    crops = plan["crops"]

    assert data["context"]["scenario_type"] == "double"
    assert len(crops) == 2
    assert all((c.get("crop_name") or "").upper() not in ("NADAS", "FALLOW", "") for c in crops)
    if plan.get("pattern_type") == "Alan paylasimli desen":
        share_sum = sum(float(c.get("area_share_pct") or 0) for c in crops)
        assert math.isclose(share_sum, 100.0, abs_tol=2.0)


def test_algorithm_choice_is_reported_as_preserved(client):
    for algo in ("GA", "ACO", "ABC"):
        data = post_optimize(client, scenario_type="single", objective="water_saving", algorithm=algo)
        parcel_result = data["parcels"][0]["result"]
        dbg = parcel_result["primaryRecommendation"]["debugRank"]
        assert dbg["algorithmChoicePreserved"] is True
        assert data["selected_plan"]["plan_id"].startswith(algo)


def test_benchmark_metrics_and_completion(client):
    resp = client.post(
        "/api/benchmark",
        json={
            "selectedParcelIds": ["P1"],
            "algorithms": ["GA"],
            "benchmarkMode": "fast",
            "repeats": 5,
            "scenario": "water_saving",
            "waterBudgetRatio": 1.0,
            "year": 2024,
            "options": {"scenarioType": "single", "seasonSource": "s1", "twoSeason": False, "seed": 222},
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    ga = data["algorithms"]["GA"]

    assert data["benchmark_mode"] == "fast"
    assert ga["run_count"] == 5
    assert ga["completion_status_kind"] == "completed"
    assert data["completion_status_kind"] == "completed"
    assert data["requested_total_runs"] == 5
    for key in ("best_profit", "mean_profit", "std_profit", "cv", "best_water", "mean_water", "tl_per_m3", "feasible_rate", "mean_runtime"):
        assert ga[key] is not None
    assert "ustunluk yorumu" in data["interpretation"]


def test_optimize_payload_keeps_core_contract_and_no_infeasible_contradiction(client):
    data = post_optimize(client, scenario_type="single", objective="water_saving", algorithm="GA")

    assert "baseline" in data
    assert "diversity" in data
    assert "agronomic_risk" in data
    payload_text = json.dumps(data, ensure_ascii=False).lower()
    assert not ("uygunluk %100" in payload_text and "uygulanabilir değildir" in payload_text)


def test_benchmark_payload_keeps_all_algorithms_diversity_and_risk(client):
    resp = client.post(
        "/api/benchmark",
        json={
            "selectedParcelIds": ["P1"],
            "algorithms": ["GA", "ABC", "ACO"],
            "benchmarkMode": "fast",
            "repeats": 3,
            "scenario": "water_saving",
            "waterBudgetRatio": 1.0,
            "year": 2024,
            "options": {"scenarioType": "single", "seasonSource": "s1", "twoSeason": False, "seed": 222},
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "OK"
    for algo in ("GA", "ABC", "ACO"):
        assert algo in data["algorithms"]
        assert "diversity" in data["algorithms"][algo]
        assert "agronomic_risk" in data["algorithms"][algo]


def test_benchmark_recomputes_final_plan_totals_and_reports_evaluation_effort(client):
    resp = client.post(
        "/api/benchmark",
        json={
            "selectedParcelIds": ["P1"],
            "algorithms": ["GA", "ABC", "ACO"],
            "benchmarkMode": "fast",
            "repeats": 3,
            "baseSeed": 4242,
            "scenario": "water_efficiency",
            "waterBudgetRatio": 1.0,
            "year": 2024,
            "includeBaseline": False,
            "options": {
                "scenarioType": "single",
                "seasonSource": "s1",
                "twoSeason": False,
                "cropCategoryMode": "same_category",
                "areaPolicy": "partial_planting",
                "allocationModel": "area_fair_per_da",
                "enforceDeliveryCaps": True,
            },
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["conditions"]["selected_parcel_ids"] == ["P1"]
    assert data["conditions"]["enforce_delivery_caps"] is True
    for algo in ("GA", "ABC", "ACO"):
        result = data["algorithms"][algo]
        assert result["completed_runs"] == 3
        assert result["valid_runs"] == 3
        assert result["feasible_runs"] == 3
        assert len(set(result["seeds"])) == 3
        assert result["evaluation_budget"]["count_status"] == "measured"
        assert result["evaluation_budget"]["total_evaluations"] > 0
        assert len(result["run_audits"]) == 3
        assert all(audit["water_matches"] and audit["profit_matches"] for audit in result["run_audits"])
        best = result["best"]
        assert math.isclose(sum(float(row["water_m3"]) for row in best["crops"]), best["total_water_m3"], rel_tol=0, abs_tol=1e-6)
        assert math.isclose(sum(float(row["profit_tl"]) for row in best["crops"]), best["total_profit_tl"], rel_tol=0, abs_tol=1e-6)
        assert math.isclose(best["efficiency_tl_per_m3"], best["total_profit_tl"] / best["total_water_m3"], rel_tol=1e-12)


def test_benchmark_excludes_invalid_and_infeasible_runs_from_statistics(monkeypatch, client):
    calls = []

    def fake_optimize(selected_ids, algorithm, scenario, water_budget_ratio, year, options):
        calls.append(dict(options))
        return {"status": "OK", "idx": len(calls) - 1}

    def fake_standardize(result, selected_ids, algorithm, scenario, water_budget_ratio, year_val, options):
        idx = int(result["idx"])
        feasible = idx != 2
        crop = {"parcel_id": "P1", "crop_name": "BUGDAY", "area_da": 10.0, "water_m3": 100.0, "profit_tl": 500.0}
        if idx == 1:
            crop.pop("water_m3")
        return {
            "status": "OK",
            "feasible": feasible,
            "selected_plan": {
                "status": "ok" if feasible else "quota_exceeded",
                "feasible": feasible,
                "selectable": feasible,
                "total_water_m3": 100.0,
                "total_profit_tl": 500.0,
                "tl_per_m3": 5.0,
                "crops": [crop],
            },
            "diagnostics": {"legacy_meta": {"delivery_report": {"feasible_monthly": feasible, "violations": [] if feasible else [{"month": 7}]}}},
            "parcels": [],
        }

    monkeypatch.setattr(app_module, "_matrix_build_problem", lambda *args, **kwargs: None)
    monkeypatch.setattr(app_module, "optimize", fake_optimize)
    monkeypatch.setattr(app_module, "_standardize_optimize_payload", fake_standardize)
    resp = client.post("/api/benchmark", json={
        "selectedParcelIds": ["P1"], "algorithms": ["GA"], "benchmarkMode": "fast",
        "repeats": 3, "baseSeed": 77, "scenario": "water_efficiency", "includeBaseline": False,
        "year": 2024, "waterBudgetRatio": 1.0,
        "options": {"scenarioType": "single", "seasonSource": "s1", "enforceDeliveryCaps": True},
    })
    assert resp.status_code == 200
    ga = resp.get_json()["algorithms"]["GA"]
    assert ga["attempted_runs"] == ga["completed_runs"] == 3
    assert ga["valid_runs"] == 2
    assert ga["invalid_runs"] == 1
    assert ga["infeasible"] == 1
    assert ga["statistics_run_count"] == ga["profit"]["n"] == 1
    assert ga["profit"]["mean"] == 500.0
    assert ga["efficiency"]["mean"] == 5.0
    assert ga["profit"]["cv"] is None
    assert ga["profit"]["cv_status"] == "undefined_single_run"
    assert [opts["seed"] for opts in calls] == [77, 78, 79]


def test_benchmark_search_algorithms_keep_empty_candidate_parcel_as_no_feasible():
    problem = {
        "benchmark_fast": True,
        "objective": "water_efficiency",
        "budget": 100.0,
        "total_area": 10.0,
        "profit_upper": 1.0,
        "water_lower": 0.0,
        "eff_upper": 1.0,
        "parcels": [{
            "id": "P1",
            "locked": False,
            "options": [],
            "no_feasible": True,
        }],
    }

    runs = (
        app_module._matrix_ga_optimize(problem, seed=11, pop_size=4, generations=3),
        app_module._matrix_abc_optimize(problem, seed=12, food_sources=4, cycles=3),
        app_module._matrix_aco_optimize(problem, seed=13, ants=4, iterations=3),
    )
    for solution, metadata in runs:
        assert solution == [0]
        assert metadata["evaluations"] > 0
        assert metadata["coverage"] == 0.0
        assert metadata["total_profit"] == 0.0
        assert metadata["total_water"] == 0.0


def test_benchmark_audit_keeps_explicit_no_feasible_separate_from_invalid_data():
    audit = app_module._benchmark_plan_audit(
        {
            "status": "OK",
            "selected_plan": {
                "status": "no_feasible_plan",
                "recommendation_status": "no_feasible_plan",
                "feasible": False,
                "selectable": False,
                "crops": [],
            },
        },
        enforce_delivery_caps=True,
    )
    assert audit["valid"] is True
    assert audit["feasible"] is False
    assert audit["no_feasible"] is True
    assert audit["diagnostic_only"] is True
    assert audit["recomputed_water_m3"] is None
    assert audit["recomputed_profit_tl"] is None


def test_frontend_backend_result_is_authoritative_and_fallback_is_warning_only():
    script = (ROOT / "script.js").read_text(encoding="utf-8")
    fetch_body = js_function_body(script, "fetchAndCacheBasinPlanPython")
    local_body = js_function_body(script, "buildLocalPlanForIds")
    fallback_body = js_function_body(script, "runOptimizationWithFallback")

    assert "normalizeBackendRecommendationPayload" in fetch_body
    assert "return backendUnavailablePlan(" in local_body
    assert "computeBasinPlan(" not in local_body
    assert "rankPlanCandidatesV8(" not in local_body
    assert "rankAnnualCandidates(" not in local_body
    assert "return await fetchAndCacheBasinPlanPython" in fallback_body
    assert "backendUnavailablePlan" in fallback_body
    assert "buildLocalPlanForIds" not in fallback_body
    assert "tarayıcı içi karar üretilmedi" in fallback_body


def test_detailed_benchmark_runs_all_requested_repeats(monkeypatch, client):
    calls = []
    standardize_calls = []

    def fake_optimize(selected_ids, algorithm, scenario, water_budget_ratio, year, options):
        calls.append(str(algorithm).upper())
        raise AssertionError("benchmark matrix path should not call optimize per run")

    def fake_standardize(result, selected_ids, algorithm, scenario, water_budget_ratio, year_val, options):
        standardize_calls.append(str(algorithm).upper())
        idx = len(standardize_calls)
        algo = str(algorithm).upper()
        profit = 100000.0 + idx
        water = 50000.0 + (idx % 7)
        return {
            "status": "OK",
            "algorithm": algo,
            "feasible": True,
            "selected_plan": {
                "plan_id": f"{algo}-{idx}",
                "total_profit_tl": profit,
                "total_water_m3": water,
                "tl_per_m3": profit / water,
                "feasible": True,
                "status": "ok",
                "crops": [{"parcel_id": "P1", "crop_name": "BUGDAY", "area_share_pct": 100, "area_da": 1, "water_m3": water, "profit_tl": profit}],
            },
            "parcels": [{
                "id": "P1",
                "result": {"recommended": [{"name": "BUGDAY", "area": 1, "waterTotal": water, "profitTotal": profit}]},
            }],
        }

    def fake_matrix_problem(selected_parcels, scenario, water_budget_ratio, year=None, options=None):
        return {
            "objective": "water_saving",
            "year": year or 2024,
            "ratio": water_budget_ratio,
            "budget": 100000.0,
            "total_area": 1.0,
            "profit_upper": 120000.0,
            "water_lower": 1000.0,
            "eff_upper": 100.0,
            "allocation_model": "area_fair_per_da",
            "quota_column": "quota_area_fair_per_da_m3",
            "planning_rule": "test",
            "crop_category_mode": "mixed",
            "parcels": [{
                "id": "P1",
                "parcelName": "P1",
                "parcel_type": "field",
                "village": "TEST",
                "area_da": 1.0,
                "quota_m3": 100000.0,
                "current_crop": "BUGDAY",
                "locked": False,
                "lock_kind": "",
                "best_local_idx": 0,
                "min_water_idx": 1,
                "max_profit_idx": 0,
                "options": [
                    {"name": "BUGDAY", "area_da": 1.0, "plannedAreaDa": 1.0, "coverage_pct": 100.0, "totalWater": 1000.0, "totalProfit": 100000.0, "tlPerM3": 100.0, "fullFeasible": True, "localUtility": 1.0, "isCurrent": True, "categoryFitScore": 1.0},
                    {"name": "ARPA", "area_da": 1.0, "plannedAreaDa": 1.0, "coverage_pct": 100.0, "totalWater": 900.0, "totalProfit": 95000.0, "tlPerM3": 105.0, "fullFeasible": True, "localUtility": 0.9, "isCurrent": False, "categoryFitScore": 1.0},
                ],
            }],
        }

    def fake_solution_payload(problem, sol, algorithm):
        return {"status": "OK", "algorithm": str(algorithm).upper()}

    monkeypatch.setattr(app_module, "optimize", fake_optimize)
    monkeypatch.setattr(app_module, "_standardize_optimize_payload", fake_standardize)
    monkeypatch.setattr(app_module, "_matrix_build_problem", fake_matrix_problem)
    monkeypatch.setattr(app_module, "_matrix_solution_to_payload", fake_solution_payload)

    resp = client.post(
        "/api/benchmark",
        json={
            "selectedParcelIds": ["P1"],
            "algorithms": ["GA", "ABC", "ACO"],
            "benchmarkMode": "detailed",
            "repeats": 30,
            "scenario": "water_saving",
            "waterBudgetRatio": 1.0,
            "year": 2024,
            "maxSeconds": 1,
            "includeBaseline": False,
            "options": {"scenarioType": "single", "seasonSource": "s1", "twoSeason": False, "seed": 444},
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    algo_calls = [c for c in calls if c in ("GA", "ABC", "ACO")]
    assert len(algo_calls) == 0
    assert len(standardize_calls) == 90
    assert data["benchmark_mode"] == "detailed"
    assert data["requested_total_runs"] == 90
    assert data["completed_runs"] == 90
    assert data["completion_status_kind"] == "completed"
    assert data["benchmark_execution"]["candidate_matrix_build_count"] == 1
    assert data["benchmark_execution"]["standard_payload_scope"] == "all_runs_shared_standardization"
    assert data["algorithm_count"] == 3
    assert all(data["algorithms"][algo]["run_count"] == 30 for algo in ("GA", "ABC", "ACO"))


def test_chart_rows_match_table_rows_and_titles_are_not_scenario_mislabeled(client):
    data = post_optimize(client, scenario_type="single", objective="water_saving")
    water_chart = data["charts"]["target_mode_water"]
    profit_chart = data["charts"]["target_mode_profit"]
    table = data["tables"]["plan_summary"]

    assert "Senaryolara Göre" not in water_chart["title"]
    assert "Senaryolara Göre" not in profit_chart["title"]
    assert water_chart["rows"][0]["value"] == table[0]["water_m3"]
    assert water_chart["rows"][1]["value"] == table[1]["water_m3"]
    assert profit_chart["rows"][0]["value"] == table[0]["profit_tl"]
    assert profit_chart["rows"][1]["value"] == table[1]["profit_tl"]
    labels = " ".join(str(r["label"]) for r in water_chart["rows"] + profit_chart["rows"])
    assert "water_saving" not in labels
    assert "max_profit" not in labels
    assert "balanced" not in labels


def test_water_efficiency_objective_identity_is_preserved_in_result_contract(client):
    data = post_optimize(client, scenario_type="single", objective="water_efficiency")

    assert data["context"]["objective_mode"] == "water_efficiency"
    assert data["diagnostics"]["objective_mode"] == "water_efficiency"
    assert data["charts"]["target_mode_water"]["objective_mode"] == "water_efficiency"
    assert data["charts"]["target_mode_profit"]["objective_mode"] == "water_efficiency"
    assert data["charts"]["target_mode_water"]["title"] == (
        "Mevcut ve Önerilen Desen — Hesaplanan Sulama İhtiyacı"
    )
    assert data["charts"]["target_mode_profit"]["title"] == (
        "Mevcut ve Önerilen Desen — Hesaplanan Net Getiri"
    )
    expected_labels = ["Mevcut desen", "Öneri · Su etkin kullanım"]
    assert [row["label"] for row in data["charts"]["target_mode_water"]["rows"]] == expected_labels
    assert [row["label"] for row in data["charts"]["target_mode_profit"]["rows"]] == expected_labels


def test_quota_exceeded_plan_or_alternative_is_not_selectable(client):
    data = post_optimize(client, scenario_type="double", objective="water_saving", ratio=1.0)
    plan = data["selected_plan"]
    if plan["feasible"] is False:
        assert plan["selectable"] is False
        assert plan["status"] == "no_feasible_two_crop_plan"
        assert "uygulanabilir iki urunlu/desenli plan bulunamadi" in plan["explanation"]
    for alt in data["alternatives"]:
        if alt.get("feasible") is False:
            assert alt.get("selectable") is False


def test_s2_high_budget_can_return_feasible_two_crop_plan(client):
    constrained = post_optimize(client, scenario_type="double", objective="water_saving", ratio=5.0)
    constrained_plan = constrained["selected_plan"]
    assert constrained_plan["total_water_m3"] == pytest.approx(621000.0)
    assert constrained["context"]["water_budget_m3"] == pytest.approx(854594.8175295407)
    assert constrained_plan["total_water_m3"] < constrained["context"]["water_budget_m3"]
    assert constrained_plan["status"] == "no_feasible_two_crop_plan"
    assert constrained_plan["feasible"] is False
    assert constrained_plan["selectable"] is False

    selected = [p for p in app_module.load_parcels() if p.get("id") == "P1"]
    _base_budget, month_weights, month_caps = app_module.basin_budget_and_delivery_caps(
        2024, selected, env_flow_ratio=0.10)
    monthly = app_module.compute_monthly_delivery_report(
        constrained_plan["total_water_m3"], month_weights, month_caps)
    assert monthly["unit"] == "m3/month"
    assert monthly["total_demand_m3"] == pytest.approx(621000.0)
    assert monthly["total_capacity_m3"] == pytest.approx(196556.8040981227)
    assert monthly["violating_months"] == list(range(1, 13))
    assert monthly["worst_month"] == 6
    assert monthly["worst_exceed_m3"] == pytest.approx(73649.39447685292)

    report = constrained["diagnostics"]["legacy_meta"]["delivery_report"]
    assert report["evaluation_plan_stage"] == "standardized_final_plan"
    assert report["capacity_constraint_enabled"] is True
    assert report["plan_total_calculated_need_m3"] == pytest.approx(621000.0)
    assert report["total_demand_m3"] == pytest.approx(621000.0)
    assert report["demand_m3"] == pytest.approx(monthly["demand_m3"])
    assert report["cap_m3"] == pytest.approx(monthly["cap_m3"])
    assert report["exceed_m3"] == pytest.approx(monthly["exceed_m3"])
    assert report["violating_months"] == list(range(1, 13))
    assert report["worst_month"] == 6
    assert report["worst_exceed_m3"] == pytest.approx(73649.39447685292)
    assert [(c["role"], c["crop_name"], c["area_da"], c["annual_calculated_need_m3"])
            for c in report["plan_components"]] == [
        ("primary", "MERCIMEK", 2700.0, 297000.0),
        ("secondary", "NOHUT", 2700.0, 324000.0),
    ]
    component_monthly = [
        sum(component["monthly_calculated_need_m3"][i]
            for component in report["plan_components"])
        for i in range(12)
    ]
    assert component_monthly == pytest.approx(report["demand_m3"])

    # This test's original purpose is the annual-budget branch. Make that scope
    # explicit; the default call above separately proves real monthly feasibility.
    data = post_optimize(
        client, scenario_type="double", objective="water_saving", ratio=5.0,
        enforce_delivery_caps=False)
    plan = data["selected_plan"]
    assert len(plan["crops"]) == 2
    assert plan["total_water_m3"] == pytest.approx(621000.0)
    assert plan["status"] == "ok"
    assert plan["feasible"] is True
    assert plan["selectable"] is True
    disabled = data["diagnostics"]["legacy_meta"]["delivery_report"]
    assert disabled["status"] == "not_evaluated"
    assert disabled["capacity_constraint_enabled"] is False
    assert disabled["feasible_monthly"] is None
    assert disabled["demand_m3"] is None
    assert disabled["cap_m3"] is None
    assert disabled["total_demand_m3"] is None
    assert disabled["plan_total_calculated_need_m3"] == pytest.approx(621000.0)
    assert "degerlendirilmedi" in disabled["reason"]


def test_final_plan_delivery_report_component_arithmetic_and_single_crop(monkeypatch):
    weights = {month: float(month) for month in range(1, 13)}
    capacities = {month: 50.0 for month in range(1, 13)}
    monkeypatch.setattr(
        app_module, "basin_budget_and_delivery_caps",
        lambda year, parcels, env_flow_ratio: (1000.0, weights, capacities))
    rows = [
        {"parcel_id": "PX", "role": "primary", "crop_name": "A", "season": "S1",
         "area_da": 10.0, "water_m3": 300.0},
        {"parcel_id": "PX", "role": "secondary", "crop_name": "B", "season": "S2",
         "area_da": 10.0, "water_m3": 480.0},
    ]
    report = app_module._standardized_plan_delivery_report(rows, [{"id": "PX"}], 2024, 0.10, True)
    expected = [10.0 * month for month in range(1, 13)]
    assert report["total_demand_m3"] == pytest.approx(780.0)
    assert report["demand_m3"] == pytest.approx(expected)
    assert report["exceed_m3"] == pytest.approx([max(0.0, value - 50.0) for value in expected])
    assert report["violating_months"] == list(range(6, 13))
    assert report["worst_month"] == 12
    assert report["worst_exceed_m3"] == pytest.approx(70.0)
    assert report["plan_components"][0]["monthly_calculated_need_m3"] == pytest.approx(
        [300.0 * month / 78.0 for month in range(1, 13)])
    assert report["plan_components"][1]["monthly_calculated_need_m3"] == pytest.approx(
        [480.0 * month / 78.0 for month in range(1, 13)])
    assert [component["season"] for component in report["plan_components"]] == ["S1", "S2"]

    single = app_module._standardized_plan_delivery_report(rows[:1], [{"id": "PX"}], 2024, 0.10, True)
    assert single["plan_total_calculated_need_m3"] == pytest.approx(300.0)
    assert single["total_demand_m3"] == pytest.approx(300.0)
    assert len(single["plan_components"]) == 1
    assert single["plan_components"][0]["crop_name"] == "A"

    monkeypatch.setattr(
        app_module, "basin_budget_and_delivery_caps",
        lambda year, parcels, env_flow_ratio: (1000.0, None, None))
    missing = app_module._standardized_plan_delivery_report(rows, [{"id": "PX"}], 2024, 0.10, True)
    assert missing["status"] == "not_available"
    assert missing["feasible_monthly"] is None
    assert missing["total_demand_m3"] is None
    assert "eski plana ait rapor yeniden kullanilmadi" in missing["reason"]


def test_s2_area_share_repair_can_show_50_50_on_2700_da():
    result = {
        "status": "OK",
        "algorithm": "GA",
        "objective": "water_saving",
        "year": 2024,
        "water_budget_m3": 810000.0,
        "feasible": True,
        "total_water_m3": 1620000.0,
        "total_profit_tl": 5400000.0,
        "parcels": [{
            "id": "PX",
            "result": {"recommended": [
                {"name": "BUGDAY", "season": "Yazlik", "area": 2700, "waterTotal": 810000, "profitTotal": 2700000},
                {"name": "NOHUT", "season": "Yazlik", "area": 2700, "waterTotal": 810000, "profitTotal": 2700000},
            ]},
        }],
    }
    data = app_module._standardize_optimize_payload(
        result,
        selected_ids=["PX"],
        algorithm="GA",
        scenario="water_saving",
        water_budget_ratio=1.0,
        year_val=2024,
        options={
            "scenarioType": "double",
            "seasonSource": "s2",
            "twoSeason": True,
            "customParcels": [{"id": "PX", "area_da": 2700, "current_crop": "BUGDAY", "water_m3": 900000, "profit_tl": 3000000}],
        },
    )
    plan = data["selected_plan"]
    shares = [round(c["area_share_pct"]) for c in plan["crops"]]
    areas = [round(c["area_da"]) for c in plan["crops"]]
    assert plan["pattern_type"] == "Alan paylasimli desen"
    assert shares == [50, 50]
    assert areas == [1350, 1350]
    assert sum(shares) == 100


def test_s2_close_canonical_crop_pair_is_repaired_or_flagged():
    result = {
        "status": "OK",
        "algorithm": "GA",
        "objective": "water_saving",
        "year": 2024,
        "water_budget_m3": 900000.0,
        "feasible": True,
        "parcels": [{
            "id": "P1",
            "result": {"recommended": [
                {"name": "MERCIMEK", "season": "Kislik", "area": 2700, "waterTotal": 300000, "profitTotal": 1000000},
                {"name": "MERCIMEK_KURU", "season": "Kislik", "area": 2700, "waterTotal": 300000, "profitTotal": 900000},
            ]},
        }],
    }
    data = app_module._standardize_optimize_payload(
        result,
        selected_ids=["P1"],
        algorithm="GA",
        scenario="water_saving",
        water_budget_ratio=5.0,
        year_val=2024,
        options={"scenarioType": "double", "seasonSource": "s2", "twoSeason": True},
    )
    crops = data["selected_plan"]["crops"]
    assert len(crops) == 2
    assert app_module._standard_close_crop_key(crops[0]["crop_name"]) != app_module._standard_close_crop_key(crops[1]["crop_name"])


def test_index_has_no_duplicate_chart_or_risk_ids():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert html.count("Senaryolara Göre Toplam Su Kullanımı") == 0
    assert html.count("Senaryolara Göre Toplam Net Kâr") == 0
    for item in ('id="waterChart"', 'id="profitChart"', 'id="runMetaBox"', 'id="riskSeparationBox"'):
        assert html.count(item) == 1


def test_legacy_15y_projection_ui_and_routes_are_inactive():
    routes = {rule.rule for rule in app_module.app.url_map.iter_rules()}
    html = (ROOT / "index.html").read_text(encoding="utf-8")

    assert "/api/impact15y" not in routes
    assert "/api/profit15y" not in routes
    for legacy_id in (
        "runImpact15yBtn",
        "runProfit15yBtn",
        "impact15ySummary",
        "profit15ySummary",
        "impactHorizonYears",
    ):
        assert legacy_id not in html


def test_data_quality_report_has_no_matrix_feasibility_error():
    report = app_module.build_data_quality_report()
    assert "error" not in report.get("matrix_feasibility", {})


def test_geojson_bundle_filters_out_of_scope_and_reports_pending_drawings(client):
    resp = client.get("/api/geojson_bundle")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "OK"

    features = data["parcels"]["features"]
    parcel_ids = [str((f.get("properties") or {}).get("id") or "") for f in features]
    assert "P180" not in parcel_ids
    assert parcel_ids.count("P1") == 1
    assert len(parcel_ids) == len(set(parcel_ids))
    assert "P138" in data.get("missing_drawing_ids", [])
    assert "P138" in data.get("drawing_pending_ids", [])
    assert data.get("errors") == []


def test_script_has_single_active_decision_flow_functions():
    script = (ROOT / "script.js").read_text(encoding="utf-8")
    funcs = [
        "normalizeBackendRecommendationPayload",
        "fetchAndCacheBasinPlanPython",
        "buildLocalPlanForIds",
        "runOptimizationWithFallback",
        "runAutoBestOptimizationV7",
        "getOptimizationResult",
        "computeBasinPlan",
        "runOptimization",
    ]
    for func in funcs:
        assert len(re.findall(rf"function\s+{func}\s*\(", script)) == 1
    assert "alternativePatterns.slice(0,3)" not in script
    assert "topRows.slice(0,3)" not in script
    assert "disabled aria-disabled=\"true\"" in script
    assert "backendChartLabelTr" in script


def test_benchmark_objective_matrix_does_not_render_fake_zero_table():
    script = (ROOT / "script.js").read_text(encoding="utf-8")
    matrix_block = re.search(r"function\s+renderObjectiveCompareMatrix\s*\(\)\s*\{(?P<body>.*?)\n\}", script, re.S)
    assert matrix_block
    body = matrix_block.group("body")
    assert "computeScopeTotalsLocal(obj" not in body
    assert "sahte 0 m³ / 0 TL tablo gösterilmez" in body
    assert "if(!ready || allZero)" in body


def test_s1_benchmark_pattern_cards_hide_second_crop_block():
    script = (ROOT / "script.js").read_text(encoding="utf-8")
    assert "const isDoubleBenchmark" in script
    assert "const secondaryBlock = isDoubleBenchmark ?" in script
    assert "const secondaryMeta = isDoubleBenchmark ?" in script
    assert "isDoubleBenchmark ? ' (1. / 2.)' : ' (ürün)'" in script


def test_water_badge_names_risk_types_explicitly():
    script = (ROOT / "script.js").read_text(encoding="utf-8")
    assert "baraj riski:" in script
    assert "plan riski:" in script
    assert "| risk: ${rTxt}" not in script
    assert "risk: düşük" not in script


def test_benchmark_feasible_rate_clamped_and_s2_best_has_second_crop_or_status(client):
    resp = client.post(
        "/api/benchmark",
        json={
            "selectedParcelIds": ["P1"],
            "algorithms": ["GA"],
            "benchmarkMode": "fast",
            "repeats": 5,
            "scenario": "water_saving",
            "waterBudgetRatio": 5.0,
            "year": 2024,
            "options": {"scenarioType": "double", "seasonSource": "s2", "twoSeason": True, "seed": 333},
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    ga = data["algorithms"]["GA"]
    assert 0 <= ga["feasible_rate"] <= 1
    best = ga["best"]
    if best.get("status") == "no_feasible_two_crop_plan":
        assert best["status"] == "no_feasible_two_crop_plan"
    else:
        assert best["parcels"][0]["secondary"]["crop"]


def test_app_has_single_standard_helpers_and_no_legacy_optimize_return():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert source.count("def _standardize_optimize_payload") == 1
    assert source.count("def _calendar_warnings_for_plan") == 1
    assert len(re.findall(r'@app\.get\("/"\)', source)) == 1
    assert len(re.findall(r"def\s+index\s*\(", source)) == 1
    assert "return jsonify(optimize(" not in source
    assert len(re.findall(r"def\s+api_benchmark\s*\(", source)) == 1


def test_run_count_calibration_candidates_and_selection_not_best_score_only():
    assert app_module.RUN_COUNT_CALIBRATION_CANDIDATES == [10, 15, 30, 50, 100]
    rows = []
    for count in app_module.RUN_COUNT_CALIBRATION_CANDIDATES:
        for algo in ("GA", "ABC", "ACO"):
            rows.append({
                "repeat_count": count,
                "algorithm": algo,
                "completed_runs": count,
                "requested_runs": count,
                "feasible_rate": 1.0 if count != 15 else 0.90,
                "cv_score": 0.20 if count == 10 else 0.03,
                "marginal_gain_vs_previous": None if count == 10 else (0.005 if count >= 30 else 0.03),
                "dominant_plan_rate": 0.55,
                "best_score": 1000 + count * 100,
                "mean_score": 900 + count,
            })
    selection = app_module._select_recommended_repeat_count(rows)
    assert selection["recommended_repeat_count"] == 30
    assert "best_score" not in selection["selection_rule"]


def test_run_count_calibration_groups_real_levels_and_excludes_bad_runs(monkeypatch, client):
    calls = []

    def fake_optimize(selected_ids, algorithm, scenario, water_budget_ratio, year, options):
        idx = len(calls)
        calls.append({"idx": idx, "seed": int(options["seed"])})
        return {"status": "OK", "idx": idx}

    def fake_standardize(result, selected_ids, algorithm, scenario, water_budget_ratio, year_val, options):
        idx = int(result["idx"])
        group_start = idx in (0, 10)
        group_infeasible = idx in (1, 11)
        crop = {"parcel_id": "P1", "crop_name": "BUGDAY", "area_da": 10.0,
                "water_m3": 100.0, "profit_tl": 500.0}
        if group_start:
            crop.pop("water_m3")
        return {
            "status": "OK",
            "selected_plan": {
                "status": "no_feasible" if group_infeasible else "ok",
                "feasible": not group_infeasible,
                "selectable": not group_infeasible,
                "total_water_m3": 100.0,
                "total_profit_tl": 500.0,
                "tl_per_m3": 5.0,
                "crops": [crop],
            },
            "diagnostics": {"legacy_meta": {"delivery_report": {
                "feasible_monthly": not group_infeasible,
                "violations": [] if not group_infeasible else [{"month": 7}],
            }}},
        }

    monkeypatch.setattr(app_module, "optimize", fake_optimize)
    monkeypatch.setattr(app_module, "_standardize_optimize_payload", fake_standardize)
    response = client.post("/api/run_count_calibration", json={
        "selectedParcelIds": ["P1"],
        "algorithms": ["GA"],
        "repeatCandidates": [10, 15],
        "baseSeed": 900,
        "scenario": "water_efficiency",
        "year": 2024,
        "waterBudgetRatio": 1.0,
        "options": {"scenarioType": "single", "seasonSource": "s1", "enforceDeliveryCaps": True},
    })
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["requested_total_runs"] == payload["completed_runs"] == 25
    assert [row["repeat_count"] for row in payload["rows"]] == [10, 15]
    for row in payload["rows"]:
        assert row["attempted_runs"] == row["completed_runs"] == row["requested_runs"]
        assert row["invalid_runs"] == 1
        assert row["valid_runs"] == row["requested_runs"] - 1
        assert row["feasible_runs"] == row["requested_runs"] - 2
        assert row["mean_profit"] == 500.0
        assert row["mean_water"] == 100.0
        assert row["mean_tl_per_m3"] == 5.0
        assert len(set(row["seeds"])) == row["requested_runs"]
    assert set(payload["rows"][0]["seeds"]).isdisjoint(payload["rows"][1]["seeds"])


def test_completion_status_helpers_distinguish_partial_and_completed():
    assert app_module._completion_status_kind(4, 90) == "partial"
    assert "K" in app_module._completion_status_label(4, 90)
    assert app_module._completion_status_kind(90, 90) == "completed"


def test_optimize_payload_contains_real_default_30_run_policy(monkeypatch, client):
    calls = []

    def fake_optimize(selected_ids, algorithm, scenario, water_budget_ratio, year, options):
        idx = len(calls)
        calls.append(idx)
        return {"status": "OK", "algorithm": algorithm, "idx": idx}

    def fake_standardize(result, selected_ids, algorithm, scenario, water_budget_ratio, year_val, options):
        idx = int(result["idx"])
        infeasible = idx == 0
        profit = 9999999.0 if infeasible else 100000.0 + idx
        water = 1.0 if infeasible else 50000.0 - idx
        return {
            "status": "OK",
            "algorithm": str(algorithm).upper(),
            "selected_plan": {
                "plan_id": f"{algorithm}-{idx}",
                "total_profit_tl": profit,
                "total_water_m3": water,
                "tl_per_m3": profit / max(1.0, water),
                "feasible": not infeasible,
                "selectable": not infeasible,
                "status": "quota_exceeded" if infeasible else "ok",
                "crops": [{"parcel_id": "P1", "crop_name": "BUGDAY", "area_share_pct": 100, "area_da": 1}],
            },
            "alternatives": [],
            "context": {"scenario_type": "single"},
            "diagnostics": {},
            "parcels": [],
        }

    monkeypatch.setattr(app_module, "optimize", fake_optimize)
    monkeypatch.setattr(app_module, "_standardize_optimize_payload", fake_standardize)
    resp = client.post("/api/optimize", json={
        "selectedParcelIds": ["P1"],
        "algorithm": "GA",
        "scenario": "water_saving",
        "waterBudgetRatio": 1.0,
        "year": 2024,
        "options": {"scenarioType": "single", "seasonSource": "s1", "twoSeason": False, "seed": 123},
    })
    assert resp.status_code == 200
    data = resp.get_json()
    policy = data["optimization_run_policy"]
    assert len(calls) == 30
    assert policy["algorithm"] == "GA"
    assert policy["selected_repeat_count"] == 30
    assert policy["calibration_available"] is False
    assert policy["mode"] == "default_30"
    assert policy["requested_runs"] == 30
    assert policy["completed_runs"] == 30
    assert policy["completion_status_kind"] == "completed"
    assert policy["best_run_index"] != 0
    assert policy["feasible_run_count"] == 29
    assert data["selected_plan"]["feasible"] is True
    assert data["selected_plan"]["selectable"] is True


def test_benchmark_ui_defaults_and_calibration_copy_are_academic_not_fast():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "script.js").read_text(encoding="utf-8")
    assert 'id="benchmarkRepeats"' in html
    assert 'value="30"' in html
    assert '<option selected="" value="detailed">' in html
    assert "Bu mod düşük tekrar sayısı kullanır" in script
    assert "fetchRunCountCalibrationPython" in script
    assert "/api/run_count_calibration" in script
    assert "Tekrar sayısı kararlılık analizi" in html


def test_partial_benchmark_language_is_preliminary_not_definitive():
    script = (ROOT / "script.js").read_text(encoding="utf-8")
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "Ön değerlendirme" in script
    assert "Kısmi sonuç:" in script
    assert "kesin en iyi algoritma dili kullanilmamalidir" in app_source
    assert "Kesin en iyi" not in script


def test_panel_open_defaults_still_preserved_in_static_ui():
    script = (ROOT / "script.js").read_text(encoding="utf-8")
    assert "PANEL_OPEN_DEFAULTS" in script
    assert 'parcelId: "P1"' in script
    assert 'scenario: "su_etkin"' in script
    assert 'cropCategoryMode: "same_category"' in script
    assert 'tab: "parcel"' in script
    assert 'switchTabByKey(key)' in script


def test_recommendation_cards_bind_totals_and_preserve_zero_missing_distinction():
    script = (ROOT / "script.js").read_text(encoding="utf-8")
    formatter = script.split("function lowRiskMetricTextV150", 1)[1].split(
        "function lowRiskIsManagementAlternativeV150", 1
    )[0]

    assert "['totalWater','total_water_m3','water']" in script
    assert "['totalProfit','total_profit_tl','profit']" in script
    assert "if(n === 0) return fallback" not in formatter
    assert "Hesaplanan toplam ihtiyaç" in script
    assert "Hesaplanan net getiri" in script
    assert "İhtiyaç farkı" in script
    assert "Net getiri farkı" in script
    assert 'data-select-pattern-v102' in script
    assert 'data-pattern-detail-v102="${escapeHtml(id)}"' not in script
    assert "disclosureOpenAttrV151(panelDisclosureKey, true)" in script
    assert "disclosureOpenAttrV151(detailDisclosureKey, false)" in script


def test_decision_charts_reject_missing_values_and_have_explicit_empty_states():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "script.js").read_text(encoding="utf-8")

    assert 'id="waterChartState" role="status"' in html
    assert 'id="profitChartState" role="status"' in html
    assert "r.value !== null" in script
    assert "Number.isFinite(Number(r.value))" in script
    assert "waterRows.map(r=>r.value)" in script
    assert "profitRows.map(r=>r.value)" in script
    assert "safeNum(r.value,0)" not in script
    assert "başarılı plan değeri çizilmedi" in script
    assert "setDecisionChartStateV151" in script


def test_allocation_panel_keeps_key_metrics_visible_and_long_sections_collapsed():
    script = (ROOT / "script.js").read_text(encoding="utf-8")

    for label in (
        "Referans toplam alan",
        "Referans hesaplanan ihtiyaç",
        "Alan başına senaryo kotası",
        "Kota yöntemi ve uzun adalet yorumu",
        "Eşit köy–dekar karşılaştırması",
        "Yerleşim ayrıntıları",
    ):
        assert label in script
    assert '<details class="allocation-disclosure-v151">' in script
    assert "Baraj serisi yalnız bağlamsal veridir" in script


@pytest.mark.browser
def test_decision_first_recommendation_and_chart_behaviour_in_browser(tmp_path):
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.route("https://**", lambda route: route.abort())
            page.goto(f"http://127.0.0.1:{server.server_port}/", wait_until="domcontentloaded")
            page.wait_for_function(
                "typeof alternativePatternPanelHtmlV94 === 'function' && "
                "typeof setDecisionChartStateV151 === 'function' && typeof waterChart !== 'undefined'"
            )
            page.evaluate("""() => {
              const host=document.createElement('section');
              host.id='ui-v151-test-host';
              host.style.cssText='position:relative;z-index:99999;background:white;padding:16px;max-width:1200px;margin:auto';
              document.body.prepend(host);
              const patterns=[{
                patternName:'ARPA + NOHUT', mainCrop:'ARPA', secondaryCrop:'NOHUT',
                selectedRecommendation:true, targetOrder:1, totalWater:1234,
                totalProfit:5678, tlPerM3:4.6, deltaWater:-100, deltaProfit:200,
                feasible:true, selectable:true, areaSplit:'İki sezonlu desen',
                components:[
                  {role:'Ana ürün',crop:'ARPA',area:10,season:'Kışlık'},
                  {role:'İkinci ürün / desen',crop:'NOHUT',area:10,season:'Yazlık'}
                ], note:'Takvim ve kota denetimi tamamlandı.'
              }];
              window.__uiV151Patterns=patterns;
              STATE.selectedFarmerAlternativeV102=null;
              host.innerHTML=alternativePatternPanelHtmlV94(patterns,'Su tasarrufu','Senaryo 2');
            }""")

            panel = page.locator("#ui-v151-test-host > details.pattern-panel-v94")
            card = panel.locator(".pattern-card-v94")
            expect(panel).to_have_attribute("open", "")
            expect(card).to_contain_text("1.234 m³")
            expect(card).to_contain_text("5.678 TL")
            expect(card).to_contain_text("ARPA")
            expect(card).to_contain_text("NOHUT")
            expect(card).to_contain_text("10 da")
            expect(card.locator(".pattern-card-details-v150")).not_to_have_attribute("open", "")
            expect(card.locator("[data-select-pattern-v102]")).to_be_visible()
            assert card.locator("[data-pattern-detail-v102]").count() == 0
            panel.screenshot(path=str(tmp_path / "agrocore-ui-v151-recommendations.png"))

            page.evaluate("""() => {
              document.querySelector('#ui-v151-test-host .pattern-card-details-v150 summary').click();
            }""")
            assert page.evaluate("STATE.selectedFarmerAlternativeV102 === null")

            page.evaluate("""() => {
              const panel=document.querySelector('#ui-v151-test-host > details');
              panel.open=false;
              panel.dispatchEvent(new Event('toggle'));
              document.querySelector('#ui-v151-test-host').innerHTML=
                alternativePatternPanelHtmlV94(window.__uiV151Patterns,'Su tasarrufu','Senaryo 2');
            }""")
            expect(page.locator("#ui-v151-test-host > details")).not_to_have_attribute("open", "")
            page.evaluate("""() => {
              window.__agroUiMarkRecommendationsFreshV151();
              document.querySelector('#ui-v151-test-host').innerHTML=
                alternativePatternPanelHtmlV94(window.__uiV151Patterns,'Su tasarrufu','Senaryo 2');
            }""")
            expect(page.locator("#ui-v151-test-host > details")).to_have_attribute("open", "")

            values = page.evaluate("""() => {
              const host=document.querySelector('#ui-v151-test-host');
              host.innerHTML=alternativePatternPanelHtmlV94([
                {mainCrop:'SIFIR',totalWater:0,totalProfit:0,tlPerM3:0,deltaWater:0,deltaProfit:0,feasible:true,selectable:true},
                {mainCrop:'EKSIK',feasible:true,selectable:true},
                {mainCrop:'UYGUN DEGIL',totalWater:99,totalProfit:88,metricsUnavailable:true,noFeasibleRecommendation:true,feasible:false,selectable:false}
              ],'Test','S1');
              return Array.from(host.querySelectorAll('.pattern-card-v94')).map(card=>({
                text:card.querySelector('.pattern-card-metrics-summary-v151').innerText,
                disabled:card.querySelector('[data-select-pattern-v102]').disabled
              }));
            }""")
            assert "0 m³" in values[0]["text"] and "0 TL" in values[0]["text"]
            assert "—" in values[1]["text"]
            assert "—" in values[2]["text"] and values[2]["disabled"] is True

            chart_state = page.evaluate("""() => {
              setDecisionChartStateV151(waterChart,'waterChartState',0,'Sayısal değer yok.');
              const empty={canvasHidden:waterChart.canvas.hidden,stateHidden:document.querySelector('#waterChartState').hidden};
              waterChart.data.labels=['Mevcut'];
              waterChart.data.datasets[0].data=[1234];
              waterChart.data.datasets[0].backgroundColor=['rgba(37,99,235,.82)'];
              setDecisionChartStateV151(waterChart,'waterChartState',1,'');
              return {empty,canvasHidden:waterChart.canvas.hidden,stateHidden:document.querySelector('#waterChartState').hidden};
            }""")
            assert chart_state == {
                "empty": {"canvasHidden": True, "stateHidden": False},
                "canvasHidden": False,
                "stateHidden": True,
            }
            page.wait_for_timeout(100)
            page.evaluate("""() => {
              const host=document.querySelector('#ui-v151-test-host');
              const card=document.createElement('div');
              card.id='ui-v151-evidence-chart';
              card.className='card small-chart-card';
              card.innerHTML='<h3 class="card-subtitle">Hedef Modlarına Göre Hesaplanan Sulama İhtiyacı</h3><canvas height="150"></canvas><div class="decision-chart-state" role="status" hidden></div><div class="small muted">Geçerli sayısal karşılaştırma • m³</div>';
              host.append(card);
              const canvas=card.querySelector('canvas');
              window.__uiV151EvidenceChart=new Chart(canvas.getContext('2d'),{
                type:'bar',
                data:{labels:['Mevcut'],datasets:[{label:'Sulama ihtiyacı (m³)',data:[1234],backgroundColor:['rgba(37,99,235,.82)'],borderRadius:10}]},
                options:chartBarOptions('m³')
              });
              setDecisionChartStateV151(window.__uiV151EvidenceChart,'',1,'');
              window.__uiV151EvidenceChart.resize();
              window.__uiV151EvidenceChart.update('none');
            }""")
            page.wait_for_timeout(100)
            assert page.evaluate("""() => {
              const bar=window.__uiV151EvidenceChart.getDatasetMeta(0).data[0];
              return !!bar && Number.isFinite(bar.height) && bar.height > 0;
            }""")
            page.locator("#ui-v151-evidence-chart").screenshot(
                path=str(tmp_path / "agrocore-ui-v151-water-chart.png")
            )

            allocation = page.locator("#waterAllocationExplain")
            expect(allocation).to_contain_text("Referans toplam alan", timeout=15000)
            expect(allocation).to_contain_text("Referans hesaplanan ihtiyaç")
            expect(allocation).to_contain_text("Alan başına senaryo kotası")
            allocation_details = allocation.locator("details.allocation-disclosure-v151")
            assert allocation_details.count() >= 3
            for index in range(allocation_details.count()):
                expect(allocation_details.nth(index)).not_to_have_attribute("open", "")
            page.evaluate("""() => {
              const allocation=document.querySelector('#waterAllocationExplain');
              allocation.style.display='block';
              document.querySelector('#ui-v151-test-host').append(allocation);
            }""")
            allocation.screenshot(path=str(tmp_path / "agrocore-ui-v151-allocation.png"))

            page.set_viewport_size({"width": 390, "height": 844})
            page.evaluate("""() => {
              window.__agroUiMarkRecommendationsFreshV151();
              document.querySelector('#ui-v151-test-host').innerHTML=
                alternativePatternPanelHtmlV94(window.__uiV151Patterns,'Su tasarrufu','Senaryo 2');
            }""")
            dimensions = page.locator("#ui-v151-test-host .pattern-card-v94").bounding_box()
            assert dimensions and dimensions["width"] <= 358
            assert page.evaluate(
                "document.querySelector('#ui-v151-test-host').scrollWidth <= "
                "document.querySelector('#ui-v151-test-host').clientWidth"
            )
            page.screenshot(path=str(tmp_path / "agrocore-ui-v151-mobile.png"), full_page=False)
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.mark.browser
def test_native_decision_charts_follow_real_optimize_response(tmp_path):
    """Normal kullanıcı akışı gerçek /api/optimize yanıtını özgün iki canvasa bağlar."""
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.set_default_timeout(240000)
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{server.server_port}/", wait_until="domcontentloaded")
            page.wait_for_function(
                "typeof setAuthenticatedUser === 'function' && "
                "typeof getAuthUserByUsername === 'function' && "
                "!document.body.classList.contains('app-booting')"
            )
            served_assets = page.evaluate("""async () => {
              const src=Array.from(document.scripts).map(node=>node.src).find(value=>value.includes('/script.js'));
              const paperSrc=Array.from(document.scripts).map(node=>node.src).find(value=>value.includes('/paper-i18n.js'));
              const text=await fetch(src,{cache:'no-store'}).then(response=>response.text());
              const paperText=await fetch(paperSrc,{cache:'no-store'}).then(response=>response.text());
              return {src,paperSrc,hasChartState:text.includes('setDecisionChartStateV151'),
                hasNativeRows:text.includes('charts?.target_mode_water'),
                hasDynamicLabelSync:paperText.includes('promote those labels to the translation source')};
            }""")
            assert served_assets["hasChartState"] is True
            assert served_assets["hasNativeRows"] is True
            assert "ui-v159-benchmark-audit" in served_assets["src"]
            assert "dynamic-chart-v153" in served_assets["paperSrc"]
            assert served_assets["hasDynamicLabelSync"] is True

            page.evaluate("setAuthenticatedUser(getAuthUserByUsername('kurum.nigde'), {focus:false})")
            expect(page.locator("#panel")).to_be_visible(timeout=240000)
            expect(page.locator('input[name="scenario"][value="su_etkin"]')).to_be_checked()
            expect(page.locator("#cropCategoryModeSel")).to_have_value("same_category")
            expect(page.locator("#algoStatus")).to_contain_text("Su etkin kullanım")

            reference_disclosure = page.locator("[data-reference-mode-banner]")
            expect(reference_disclosure.locator("summary")).to_have_text("Referans veri")
            assert reference_disclosure.evaluate("node => node.open") is False
            assert reference_disclosure.bounding_box()["height"] < 50
            reference_disclosure.locator("summary").click()
            expect(reference_disclosure).to_contain_text(
                "Referans/model verileriyle çalışır. Resmî su tahsisi veya saha doğrulaması yerine geçmez."
            )
            reference_disclosure.locator("summary").press("Enter")
            assert reference_disclosure.evaluate("node => node.open") is False

            page.locator("#parcelSelect").select_option("P1")
            page.locator("#algoSelect").select_option("ga")
            page.locator("#seasonSourceSel").select_option("s1")

            with page.expect_response(
                lambda response: response.request.method == "POST" and response.url.endswith("/api/optimize"),
                timeout=240000,
            ) as response_info:
                page.locator("#runOptBtn").click()
            response = response_info.value
            assert response.ok
            request_payload = response.request.post_data_json
            assert request_payload["scenario"] == "water_efficiency"
            assert request_payload["cropCategoryMode"] == "same_category"
            assert request_payload["options"]["cropCategoryMode"] == "same_category"
            payload = response.json()
            assert payload["context"]["objective_mode"] == "water_efficiency"
            page.wait_for_function("!STATE.isOptimizing", timeout=240000)
            page.wait_for_function("""() => {
              const water=Chart.getChart(document.getElementById('waterChart'));
              const profit=Chart.getChart(document.getElementById('profitChart'));
              return water?.data?.datasets?.[0]?.data?.length > 0 && profit?.data?.datasets?.[0]?.data?.length > 0;
            }""")

            diagnostic = page.evaluate("""() => {
              const inspect=id=>{
                const canvas=document.getElementById(id);
                const chart=Chart.getChart(canvas);
                const state=document.getElementById(id+'State');
                return {
                  chartCanvasIsNative:chart?.canvas===canvas,
                  labels:[...(chart?.data?.labels||[])],
                  values:[...(chart?.data?.datasets?.[0]?.data||[])],
                  colors:Array.isArray(chart?.data?.datasets?.[0]?.backgroundColor)?[...chart.data.datasets[0].backgroundColor]:chart?.data?.datasets?.[0]?.backgroundColor,
                  hidden:canvas.hidden,
                  stateHidden:state.hidden,
                  stateText:state.textContent.trim(),
                  title:canvas.closest('.small-chart-card')?.querySelector('.card-subtitle')?.textContent.trim(),
                  description:document.getElementById(id+'Description')?.textContent.trim(),
                  rect:{width:canvas.getBoundingClientRect().width,height:canvas.getBoundingClientRect().height},
                  bars:(chart?.getDatasetMeta(0)?.data||[]).map(bar=>({width:bar.width,height:bar.height,base:bar.base,y:bar.y}))
                };
              };
              return {
                water:inspect('waterChart'),profit:inspect('profitChart'),
                status:document.getElementById('algoStatus')?.textContent,
                activeObjective:document.getElementById('activeObjectiveBadge')?.textContent,
                selectionDirty:STATE.selectionDirty,
                currentScenario:selectedScenario,currentAlgo:selectedAlgo,
                cacheKeys:Object.keys(basinPlanCache||{})
              };
            }""")
            print(json.dumps({"served": served_assets, "api_charts": payload.get("charts"), "ui": diagnostic}, ensure_ascii=False, indent=2))

            for chart_id, contract_key in (("water", "target_mode_water"), ("profit", "target_mode_profit")):
                expected_rows = payload["charts"][contract_key]["rows"]
                expected_values = [float(row["value"]) for row in expected_rows]
                expected_labels = ["Mevcut desen", "Öneri · Su etkin kullanım"]
                actual = diagnostic[chart_id]
                assert actual["chartCanvasIsNative"] is True
                assert actual["labels"] == expected_labels
                assert actual["values"] == pytest.approx(expected_values)
                assert "Seçili parsel" in actual["description"]
                assert "Su etkin kullanım" in actual["description"]
                assert actual["hidden"] is False
                assert actual["stateHidden"] is True
                assert actual["rect"]["width"] > 0 and actual["rect"]["height"] > 0
                for value, bar in zip(expected_values, actual["bars"]):
                    if value > 0:
                        assert bar["width"] > 0 and bar["height"] > 0

            assert diagnostic["water"]["title"] == "Mevcut ve Önerilen Desen — Hesaplanan Sulama İhtiyacı"
            assert diagnostic["profit"]["title"] == "Mevcut ve Önerilen Desen — Hesaplanan Net Getiri"
            assert "Su etkin kullanım" in diagnostic["activeObjective"]

            consistency = page.evaluate(r"""() => {
              const parseTr=value=>Number(String(value||'').replace(/\./g,'').replace(',','.').replace(/[^0-9+\-.]/g,''));
              const econCards=[...document.querySelectorAll('#businessMetricsBox .business-metrics-card')];
              const recommended=econCards.find(card=>card.querySelector('h4')?.textContent.includes('Önerilen'));
              const econCells=[...(recommended?.querySelector('tbody tr')?.children||[])].map(cell=>cell.innerText.trim());
              const methodTable=document.querySelector('#irrigationCompareBox table');
              const methodHeaders=[...(methodTable?.querySelectorAll('thead th')||[])].map(cell=>cell.innerText.trim());
              const methodRows=[...(methodTable?.querySelectorAll('tbody tr')||[])].map(row=>[...row.children].map(cell=>cell.innerText.trim()));
              const cards=[...document.querySelectorAll('#tblRecommendedFooter .pattern-card-v94')].map(card=>({
                text:card.innerText,
                title:card.querySelector('.pattern-card-top strong')?.textContent.trim(),
                button:card.querySelector('[data-select-pattern-v102]')?.textContent.trim(),
                disabled:!!card.querySelector('[data-select-pattern-v102]')?.disabled
              }));
              const deliveryDemand=[...document.querySelectorAll('#deliveryBox .delivery-table tbody tr')]
                .map(row=>parseTr(row.children[1]?.innerText)).filter(Number.isFinite);
              return {
                econCells,
                econNote:document.querySelector('#businessMetricsBox')?.innerText,
                methodHeaders,methodRows,methodText:document.querySelector('#irrigationCompareBox')?.innerText,
                cards,countText:document.querySelector('#tblRecommendedFooter .low-risk-count-note-v150')?.innerText,
                deliveryDemandTotal:deliveryDemand.reduce((a,b)=>a+b,0),
                deliveryText:document.querySelector('#deliveryBox')?.innerText,
                deltaClasses:{
                  water:document.querySelector('#mWaterDiff')?.className,
                  profit:document.querySelector('#mProfitDiff')?.className,
                  efficiency:document.querySelector('#mEffDiff')?.className
                }
              };
            }""")
            print(json.dumps({"consistency": consistency}, ensure_ascii=True, indent=2))
            selected_plan = payload["selected_plan"]
            assert "YULAF" in consistency["econCells"][0]
            assert float(consistency["econCells"][1].replace(",", ".")) == pytest.approx(2700.0)
            assert int(consistency["econCells"][8].replace(".", "")) == pytest.approx(selected_plan["total_water_m3"], abs=1)
            assert float(consistency["econCells"][9].replace(",", ".")) == pytest.approx(selected_plan["tl_per_m3"], abs=0.01)
            assert "fiilen uygulanmış/ölçülmüş su anlamına gelmez" in consistency["econNote"]
            assert "karşı-olgusal" in consistency["methodText"]
            assert "mevcut desene göre değil" in consistency["methodText"]
            assert "1.330.641" in consistency["methodText"]
            surface = next(row for row in consistency["methodRows"] if "Karık" in row[0])
            surface_water = int(surface[3].replace(".", ""))
            surface_delta = int(surface[5].replace(".", "").replace("+", "").replace(" m³", ""))
            independent_counterfactual_base = selected_plan["total_water_m3"] * 0.20
            independent_surface = selected_plan["total_water_m3"] / 0.55
            assert surface_water == pytest.approx(independent_surface, abs=1)
            assert surface_delta == pytest.approx(independent_surface - independent_counterfactual_base, abs=1)
            assert consistency["countText"].count("Gösterilen alternatif") >= 1
            assert "Toplam aday:" not in consistency["countText"]
            assert [card["title"] for card in consistency["cards"]] == ["ARPA (Dane)", "ÇAVDAR (Dane)", "MISIR (Dane)"]
            corn = consistency["cards"][2]
            assert "2.700 da" in corn["text"] and "2.016,9 da" in corn["text"]
            assert "683,1 da" in corn["text"] and "%74,7" in corn["text"]
            assert "Kota içinde · kısmi ekim" in corn["text"]
            assert "+360.570 m³" in corn["text"]
            assert "Kategori: Tahıl / tarla" in corn["text"]
            assert corn["button"] == "Talep için önizle" and corn["disabled"] is False
            assert consistency["deltaClasses"]["profit"].endswith("metric-delta-negative")
            assert consistency["deltaClasses"]["efficiency"].endswith("metric-delta-positive")
            assert consistency["deliveryDemandTotal"] == pytest.approx(selected_plan["total_water_m3"], abs=12)
            assert "Tahmini" in consistency["deliveryText"] or "Kapasite" in consistency["deliveryText"]

            chart_values_before_preview = diagnostic["water"]["values"]
            page.locator("#tblRecommendedFooter .pattern-card-v94", has_text="MISIR").locator("[data-select-pattern-v102]").click()
            expect(page.locator("#tblRecommendedFooter .alternative-preview-notice-v154")).to_contain_text(
                "Talep önizlemesi · ana plan değişmedi"
            )
            chart_values_after_preview = page.evaluate(
                "[...Chart.getChart(document.getElementById('waterChart')).data.datasets[0].data]"
            )
            assert chart_values_after_preview == chart_values_before_preview
            rotation = page.locator("#rotationBox details.rotation-disclosure-v153")
            expect(rotation).to_be_visible()
            assert rotation.evaluate("node => node.open") is True
            expect(rotation).to_contain_text(
                "Bu bölüm rotasyon bilgisidir; çalıştırılan S1 planına ikinci ürün eklenmiş değildir."
            )
            rotation.locator("summary").click()
            assert rotation.evaluate("node => node.open") is False

            # The normal language controls may reapply chart translations after
            # an analysis; they must not restore the empty initialization labels.
            page.locator('[data-paper-lang="en"]').first.click()
            page.wait_for_function("document.documentElement.lang === 'en'")
            page.locator('[data-paper-lang="tr"]').first.click()
            page.wait_for_function("document.documentElement.lang === 'tr'")
            assert rotation.evaluate("node => node.open") is False
            after_language_roundtrip = page.evaluate("""() => Object.fromEntries(
              ['waterChart','profitChart'].map(id=>{
                const chart=Chart.getChart(document.getElementById(id));
                return [id,{labels:[...chart.data.labels],values:[...chart.data.datasets[0].data],
                  bars:chart.getDatasetMeta(0).data.map(bar=>({width:bar.width,height:bar.height}))}];
              })
            )""")
            assert after_language_roundtrip["waterChart"]["labels"] == diagnostic["water"]["labels"]
            assert after_language_roundtrip["waterChart"]["values"] == diagnostic["water"]["values"]
            assert after_language_roundtrip["profitChart"]["labels"] == diagnostic["profit"]["labels"]
            assert after_language_roundtrip["profitChart"]["values"] == diagnostic["profit"]["values"]
            assert all(bar["width"] > 0 and bar["height"] > 0
                       for result in after_language_roundtrip.values() for bar in result["bars"])

            rotation.locator("summary").click()
            assert rotation.evaluate("node => node.open") is True
            page.locator(".app-header").screenshot(path=str(tmp_path / "reference-data-header.png"))
            page.locator("#scenarioCard").screenshot(path=str(tmp_path / "default-objective-controls.png"))
            page.locator(".right-middle").screenshot(
                path=str(tmp_path / "native-target-mode-charts-after-analysis.png")
            )
            page.locator("#rotationBox").screenshot(path=str(tmp_path / "open-rotation-after-analysis.png"))
            assert not page_errors
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.mark.browser
def test_real_benchmark_button_preserves_analysis_and_reports_completed_runs(tmp_path):
    """Gerçek düğme aynı problem koşullarını üç algoritmaya gönderir ve ayrı ekranda tutar."""
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.set_default_timeout(300000)
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{server.server_port}/", wait_until="domcontentloaded")
            page.wait_for_function(
                "typeof setAuthenticatedUser === 'function' && "
                "typeof getAuthUserByUsername === 'function' && "
                "!document.body.classList.contains('app-booting')"
            )
            page.evaluate("setAuthenticatedUser(getAuthUserByUsername('kurum.nigde'), {focus:false})")
            expect(page.locator("#panel")).to_be_visible(timeout=240000)
            page.locator("#parcelSelect").select_option("P1")
            page.locator("#algoSelect").select_option("ga")
            page.locator("#seasonSourceSel").select_option("s1")

            with page.expect_response(
                lambda response: response.request.method == "POST" and response.url.endswith("/api/optimize"),
                timeout=300000,
            ) as normal_response_info:
                page.locator("#runOptBtn").click()
            assert normal_response_info.value.request.post_data_json["selectedParcelIds"] == ["P1"]
            page.wait_for_function("!STATE.isOptimizing", timeout=300000)
            normal_before = page.evaluate("""() => ({
              selectedAlgo,
              selectValue:document.getElementById('algoSelect').value,
              water:[...Chart.getChart(document.getElementById('waterChart')).data.datasets[0].data],
              profit:[...Chart.getChart(document.getElementById('profitChart')).data.datasets[0].data]
            })""")

            page.locator('.tab[data-tab="benchmark"]').click()
            expect(page.locator("#tab-benchmark")).to_have_class(re.compile(r"\bactive\b"))
            option_state = page.evaluate("""() => {
              const select=document.getElementById('benchmarkSeasonSourceSel');
              const option=select.options[0];
              return {
                texts:[...select.options].map(item=>item.textContent.trim()),
                selectColor:getComputedStyle(select).color,
                optionColor:getComputedStyle(option).color,
                optionBackground:getComputedStyle(option).backgroundColor
              };
            }""")
            assert option_state["texts"] == [
                "Seçili (soldaki Sezon veri seti)",
                "Senaryo-1 (tek ürün)",
                "Senaryo-2 (çift ürün / desen)",
                "İkisini de çalıştır (karşılaştır)",
            ]
            assert option_state["selectColor"] != "rgba(0, 0, 0, 0)"
            assert option_state["optionColor"] != option_state["optionBackground"]
            expect(page.locator("#benchmarkStatus")).to_have_text("Karşılaştırmayı çalıştırın")
            expect(page.locator("#tab-benchmark .benchmark-chart-state-v154")).to_have_count(4)
            assert all(page.locator("#tab-benchmark .benchmark-chart-state-v154").nth(i).is_visible() for i in range(4))
            assert all(page.locator("#tab-benchmark canvas").nth(i).is_hidden() for i in range(4))

            page.locator("#benchmarkSeasonSourceSel").select_option("s1")
            page.locator("#benchmarkModeSel").select_option("fast")
            page.locator("#benchmarkRepeats").fill("5")
            page.locator("#benchmarkSeed").fill("321")
            with page.expect_response(
                lambda response: response.request.method == "POST" and response.url.endswith("/api/benchmark"),
                timeout=300000,
            ) as response_info:
                page.locator("#runBenchmarkBtn").click()
                expect(page.locator("#benchmarkStatus")).to_contain_text("Çalışıyor")
            response = response_info.value
            assert response.ok
            request_payload = response.request.post_data_json
            result = response.json()
            assert request_payload["selectedParcelIds"] == ["P1"]
            assert request_payload["algorithms"] == ["GA", "ABC", "ACO"]
            assert request_payload["scenario"] == "water_efficiency"
            assert request_payload["year"] == 2024
            assert request_payload["dataVersion"]
            assert request_payload["benchmarkMode"] == "fast"
            assert request_payload["repeats"] == 5
            assert request_payload["cropCategoryMode"] == "same_category"
            assert request_payload["options"]["cropCategoryMode"] == "same_category"
            assert request_payload["options"]["areaPolicy"] == "partial_planting"
            assert request_payload["options"]["allocationModel"] == "area_fair_per_da"
            assert request_payload["options"]["seasonSource"] == "s1"
            assert request_payload["options"]["scenarioType"] == "single"
            assert request_payload["options"]["enforceDeliveryCaps"] is True
            assert request_payload["waterBudgetRatio"] > 0

            assert result["status"] == "OK"
            assert set(result["algorithms"]) == {"GA", "ABC", "ACO"}
            assert result["requested_total_runs"] == 15
            assert result["completed_runs"] == 15
            assert result["valid_runs"] == 15
            assert result["feasible_runs"] == 15
            assert result["failed_runs"] == 0
            assert result["completion_status_kind"] == "completed"
            assert result["conditions"]["selected_parcel_ids"] == ["P1"]
            assert result["conditions"]["year"] == 2024
            assert result["conditions"]["data_version"] == request_payload["dataVersion"]
            assert result["conditions"]["objective_mode"] == "water_efficiency"
            assert result["conditions"]["crop_category_mode"] == "same_category"
            assert result["conditions"]["area_policy"] == "partial_planting"
            assert result["conditions"]["allocation_model"] == "area_fair_per_da"
            assert result["conditions"]["enforce_delivery_caps"] is True
            assert result["benchmark_execution"]["standard_payload_scope"] == "all_runs_shared_standardization"
            for algorithm in ("GA", "ABC", "ACO"):
                algorithm_result = result["algorithms"][algorithm]
                assert algorithm_result["run_count"] == 5
                assert algorithm_result["completion_status_kind"] == "completed"
                assert algorithm_result["valid_runs"] == 5
                assert algorithm_result["feasible_runs"] == 5
                assert algorithm_result["statistics_run_count"] == 5
                assert len(algorithm_result["run_audits"]) == 5
                assert all(
                    audit["water_matches"] and audit["profit_matches"] and audit["included_in_statistics"]
                    for audit in algorithm_result["run_audits"]
                )
                assert algorithm_result["evaluation_budget"]["total_evaluations"] > 0

            expect(page.locator("#benchmarkReport")).to_be_visible(timeout=300000)
            expect(page.locator("#benchmarkStatus")).to_contain_text("Tamamlandı: 15/15")
            benchmark_ui = page.evaluate("""() => ({
              normal:{
                selectedAlgo,
                selectValue:document.getElementById('algoSelect').value,
                water:[...Chart.getChart(document.getElementById('waterChart')).data.datasets[0].data],
                profit:[...Chart.getChart(document.getElementById('profitChart')).data.datasets[0].data]
              },
              charts:['benchmarkProfitChart','benchmarkWaterChart','benchmarkEffChart','benchmarkRuntimeChart'].map(id=>{
                const canvas=document.getElementById(id),chart=Chart.getChart(canvas);
                const state=canvas.closest('.chart-card')?.querySelector('.benchmark-chart-state-v154');
                return {id,hidden:canvas.hidden,labels:[...(chart?.data?.labels||[])],datasets:(chart?.data?.datasets||[]).map(ds=>({label:ds.label,data:[...ds.data]})),points:(chart?.getDatasetMeta(0)?.data||[]).map(point=>({x:point.x,y:point.y})),stateHidden:state?.hidden,stateHeight:state?.getBoundingClientRect().height};
              }),
              report:document.getElementById('benchmarkReport')?.innerText,
              effectiveConditions:document.getElementById('benchmarkEffectiveConditions')?.innerText,
              methodologyOpen:document.querySelector('#benchmarkMethodologyV98 details')?.open,
              methodologyHeight:document.getElementById('benchmarkMethodologyV98')?.getBoundingClientRect().height,
              dataCoverage:document.getElementById('benchmarkDataCoverageV100')?.innerText
            })""")
            assert benchmark_ui["normal"] == normal_before
            for chart in benchmark_ui["charts"]:
                assert chart["hidden"] is False
                assert chart["stateHidden"] is True
                assert chart["stateHeight"] == 0
                assert chart["labels"]
                assert [dataset["label"] for dataset in chart["datasets"]] == ["GA", "ABC", "ACO"]
                assert all(dataset["data"] for dataset in chart["datasets"])
                assert chart["points"] and all(math.isfinite(point["x"]) and math.isfinite(point["y"]) for point in chart["points"])
            assert "15/15" in benchmark_ui["report"]
            assert "Ön değerlendirme" not in benchmark_ui["report"]
            assert "Algoritmalar aynı optimuma yakınsadı" in benchmark_ui["report"]
            assert "öne çıkmıştır" not in benchmark_ui["report"]
            assert "kapsam: P1" in benchmark_ui["effectiveConditions"]
            assert "hedef: water_efficiency" in benchmark_ui["effectiveConditions"]
            assert "alan: partial_planting" in benchmark_ui["effectiveConditions"]
            assert benchmark_ui["methodologyOpen"] is False
            assert benchmark_ui["methodologyHeight"] < 80
            assert "Yüklü analiz parseli" in benchmark_ui["dataCoverage"]
            assert "Bu koşumun kapsamı\n1\nP1" in benchmark_ui["dataCoverage"]

            for width in (1920, 1536, 1366, 390):
                page.set_viewport_size({"width": width, "height": 1080 if width > 390 else 844})
                page.wait_for_timeout(100)
                layout = page.evaluate("""() => ({
                  viewport:innerWidth,
                  documentWidth:document.documentElement.scrollWidth,
                  sectionWidth:document.getElementById('tab-benchmark').getBoundingClientRect().width,
                  sectionScrollWidth:document.getElementById('tab-benchmark').scrollWidth,
                  runButtonVisible:!!(document.getElementById('runBenchmarkBtn').offsetWidth || document.getElementById('runBenchmarkBtn').offsetHeight),
                  canvases:['benchmarkProfitChart','benchmarkWaterChart','benchmarkEffChart','benchmarkRuntimeChart'].map(id=>{
                    const rect=document.getElementById(id).getBoundingClientRect();
                    return {width:rect.width,height:rect.height,hidden:document.getElementById(id).hidden};
                  })
                })""")
                assert layout["viewport"] == width
                assert layout["documentWidth"] <= width
                assert layout["sectionScrollWidth"] <= math.ceil(layout["sectionWidth"] + 1)
                assert layout["runButtonVisible"] is True
                assert all(not canvas["hidden"] and canvas["width"] > 0 and canvas["height"] > 0 for canvas in layout["canvases"])
                if width in (1920, 390):
                    page.locator("#tab-benchmark").screenshot(
                        path=str(tmp_path / f"real-benchmark-completed-{width}.png")
                    )

            page.set_viewport_size({"width": 1536, "height": 960})
            cdp = page.context.new_cdp_session(page)
            for scale in (1.0, 1.25):
                cdp.send("Emulation.setPageScaleFactor", {"pageScaleFactor": scale})
                page.wait_for_timeout(100)
                zoom_layout = page.evaluate("""() => ({
                  documentWidth:document.documentElement.scrollWidth,
                  viewportWidth:document.documentElement.clientWidth,
                  runButtonRect:document.getElementById('runBenchmarkBtn').getBoundingClientRect().toJSON(),
                  status:document.getElementById('benchmarkStatus').innerText
                })""")
                assert zoom_layout["documentWidth"] <= zoom_layout["viewportWidth"]
                assert zoom_layout["runButtonRect"]["width"] > 0
                assert "15/15" in zoom_layout["status"]
                if scale == 1.25:
                    page.locator("#tab-benchmark").screenshot(
                        path=str(tmp_path / "real-benchmark-completed-1536-zoom-125.png")
                    )
            cdp.send("Emulation.setPageScaleFactor", {"pageScaleFactor": 1.0})
            assert not page_errors
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.mark.browser
def test_target_change_requires_new_run_and_uses_result_objective_metadata(tmp_path):
    """Gerçek form/buton akışı eski sonucu yeni hedef diye yeniden etiketlemez."""
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    requests = []

    def response_for(objective):
        target = {
            "water_efficiency": (410000.0, 920000.0, "Su-kâr dengesi"),
            "max_profit": (520000.0, 1180000.0, "Su etkin kullanım"),
        }[objective]
        return {
            "status": "OK",
            "context": {
                "parcel_id": "P1", "scenario_type": "single", "objective_mode": objective,
                "algorithm": "GA", "water_year": 2024, "water_budget_m3": 800000.0,
            },
            "baseline": {
                "total_water_m3": 600000.0, "total_profit_tl": 700000.0,
                "crop_pattern": [{"parcel_id": "P1", "crop_name": "BUGDAY", "water_m3": 600000.0,
                                  "profit_tl": 700000.0, "area_da": 100.0}],
            },
            "selected_plan": {
                "plan_id": f"fixture-{objective}", "status": "feasible", "recommendation_status": "feasible",
                "feasible": True, "selectable": True, "total_water_m3": target[0],
                "total_profit_tl": target[1], "tl_per_m3": target[1] / target[0],
                "crops": [{"parcel_id": "P1", "crop_name": "ARPA", "area_da": 100.0,
                           "water_m3": target[0], "profit_tl": target[1], "season": "Kışlık"}],
            },
            "alternatives": [],
            "charts": {
                "target_mode_water": {
                    "title": "legacy title", "unit": "m3", "scope": "Secili parsel",
                    "objective_mode": objective,
                    "rows": [{"label": "Mevcut", "value": 600000.0},
                             {"label": target[2], "value": target[0]}],
                },
                "target_mode_profit": {
                    "title": "legacy title", "unit": "TL", "scope": "Secili parsel",
                    "objective_mode": objective,
                    "rows": [{"label": "Mevcut", "value": 700000.0},
                             {"label": target[2], "value": target[1]}],
                },
            },
            "tables": {"plan_summary": []},
            "diagnostics": {"warnings": []},
            "optimization_run_policy": {"mode": "controlled_fixture"},
        }

    def fulfill_optimize(route):
        request = route.request.post_data_json
        requests.append(request)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(response_for(request["scenario"]), ensure_ascii=False),
        )

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.set_default_timeout(240000)
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.route("**/api/optimize", fulfill_optimize)
            page.goto(f"http://127.0.0.1:{server.server_port}/", wait_until="domcontentloaded")
            page.wait_for_function(
                "typeof setAuthenticatedUser === 'function' && "
                "typeof getAuthUserByUsername === 'function' && "
                "!document.body.classList.contains('app-booting')"
            )
            page.evaluate("setAuthenticatedUser(getAuthUserByUsername('kurum.nigde'), {focus:false})")
            expect(page.locator("#panel")).to_be_visible(timeout=240000)
            expect(page.locator('input[name="scenario"][value="su_etkin"]')).to_be_checked()

            page.locator("#runOptBtn").click()
            page.wait_for_function("!STATE.isOptimizing")
            page.wait_for_function(
                "Chart.getChart(document.getElementById('waterChart'))?.data?.labels?.[1] === "
                "'Öneri · Su etkin kullanım'"
            )
            assert requests[-1]["scenario"] == "water_efficiency"
            assert requests[-1]["cropCategoryMode"] == "same_category"
            rotation = page.locator("#rotationBox details.rotation-disclosure-v153")
            assert rotation.evaluate("node => node.open") is True
            rotation.locator("summary").click()
            assert rotation.evaluate("node => node.open") is False

            page.locator('input[name="scenario"][value="maks_kar"]').check()
            expect(page.locator("#activeObjectiveBadge")).to_contain_text("Beklemede")
            expect(page.locator("#activeObjectiveBadge")).to_contain_text("Kâr odaklı")
            expect(page.locator("#waterChart")).to_be_hidden()
            expect(page.locator("#profitChart")).to_be_hidden()
            expect(page.locator("#waterChartState")).to_contain_text("eski grafik gösterilmiyor")

            page.locator("#runOptBtn").click()
            page.wait_for_function("!STATE.isOptimizing")
            page.wait_for_function(
                "Chart.getChart(document.getElementById('waterChart'))?.data?.labels?.[1] === "
                "'Öneri · Kâr odaklı'"
            )
            assert requests[-1]["scenario"] == "max_profit"
            target_state = page.evaluate("""() => ({
              waterLabels:[...Chart.getChart(document.getElementById('waterChart')).data.labels],
              profitLabels:[...Chart.getChart(document.getElementById('profitChart')).data.labels],
              waterValues:[...Chart.getChart(document.getElementById('waterChart')).data.datasets[0].data],
              profitValues:[...Chart.getChart(document.getElementById('profitChart')).data.datasets[0].data],
              rotationOpen:document.querySelector('#rotationBox details.rotation-disclosure-v153')?.open,
              badge:document.getElementById('activeObjectiveBadge')?.textContent
            })""")
            assert target_state["waterLabels"] == ["Mevcut desen", "Öneri · Kâr odaklı"]
            assert target_state["profitLabels"] == ["Mevcut desen", "Öneri · Kâr odaklı"]
            assert target_state["waterValues"] == [600000, 520000]
            assert target_state["profitValues"] == [700000, 1180000]
            assert target_state["rotationOpen"] is True
            assert "Kâr odaklı" in target_state["badge"]
            page.locator(".right-middle").screenshot(path=str(tmp_path / "changed-target-native-charts.png"))
            assert not page_errors
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.mark.browser
def test_native_decision_charts_show_no_feasible_state_without_fake_target(tmp_path):
    """Kontrollü no-feasible yanıt normal buton akışında yalnız gerçek referansı çizer."""
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    no_feasible = {
        "status": "OK",
        "context": {
            "parcel_id": "P1", "scenario_type": "single", "objective_mode": "water_saving",
            "algorithm": "GA", "water_year": 2024, "water_budget_m3": 500000.0,
        },
        "baseline": {"total_water_m3": 321000.0, "total_profit_tl": 765000.0, "crop_pattern": []},
        "selected_plan": {
            "plan_id": "no-feasible", "status": "no_feasible_plan", "recommendation_status": "no_feasible_plan",
            "feasible": False, "selectable": False, "crops": [], "total_water_m3": None,
            "total_profit_tl": None, "warnings": ["Kota altında uygulanabilir aday bulunamadı."],
        },
        "alternatives": [],
        "charts": {
            "target_mode_water": {
                "title": "Hedef Modlarına Göre Hesaplanan Sulama İhtiyacı", "unit": "m3",
                "scope": "Secili parsel", "objective_mode": "water_saving", "rows": [
                    {"label": "Mevcut", "value": 321000.0},
                    {"label": "Su tasarrufu", "value": None},
                ],
            },
            "target_mode_profit": {
                "title": "Hedef Modlarına Göre Toplam Net Kâr", "unit": "TL",
                "scope": "Secili parsel", "objective_mode": "water_saving", "rows": [
                    {"label": "Mevcut", "value": 765000.0},
                    {"label": "Su tasarrufu", "value": None},
                ],
            },
        },
        "tables": {"plan_summary": []},
        "diagnostics": {"warnings": ["Kota altında uygulanabilir aday bulunamadı."]},
        "optimization_run_policy": {"mode": "controlled_fixture"},
    }
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.set_default_timeout(240000)
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.route(
                "**/api/optimize",
                lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(no_feasible)),
            )
            page.goto(f"http://127.0.0.1:{server.server_port}/", wait_until="domcontentloaded")
            page.wait_for_function(
                "typeof setAuthenticatedUser === 'function' && "
                "typeof getAuthUserByUsername === 'function' && "
                "!document.body.classList.contains('app-booting')"
            )
            page.evaluate("setAuthenticatedUser(getAuthUserByUsername('kurum.nigde'), {focus:false})")
            page.locator("#parcelSelect").select_option("P1")
            page.locator("#algoSelect").select_option("ga")
            page.locator("#seasonSourceSel").select_option("s1")
            page.locator('input[name="scenario"][value="su_tasarruf"]').check()
            page.locator("#runOptBtn").click()
            page.wait_for_function("!STATE.isOptimizing")

            state = page.evaluate("""() => {
              const inspect=id=>{
                const canvas=document.getElementById(id),chart=Chart.getChart(canvas),message=document.getElementById(id+'State');
                const bar=chart.getDatasetMeta(0).data[0];
                const messageRect=message.getBoundingClientRect(),cardRect=message.closest('.small-chart-card').getBoundingClientRect();
                return {labels:[...chart.data.labels],values:[...chart.data.datasets[0].data],canvasHidden:canvas.hidden,
                  messageHidden:message.hidden,message:message.textContent.trim(),barHeight:bar?.height||0,
                  messageFullyInsideCard:messageRect.top >= cardRect.top && messageRect.bottom <= cardRect.bottom};
              };
              return {water:inspect('waterChart'),profit:inspect('profitChart')};
            }""")
            assert state["water"]["labels"] == ["Mevcut desen"]
            assert state["water"]["values"] == [321000]
            assert state["profit"]["labels"] == ["Mevcut desen"]
            assert state["profit"]["values"] == [765000]
            for chart_state in state.values():
                assert chart_state["canvasHidden"] is False
                assert chart_state["messageHidden"] is False
                assert "uygulanabilir plan bulunamadı" in chart_state["message"]
                assert chart_state["barHeight"] > 0
                assert chart_state["messageFullyInsideCard"] is True
            expect(page.locator("#waterChartState")).to_be_visible()
            expect(page.locator("#profitChartState")).to_be_visible()
            page.locator(".right-middle").screenshot(
                path=str(tmp_path / "native-target-mode-charts-no-feasible.png")
            )
            assert not page_errors
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
