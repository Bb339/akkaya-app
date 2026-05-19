import json
import math
import re
from pathlib import Path

import pytest

import app as app_module
from app import app

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def client():
    return app.test_client()


def optimize_payload(scenario_type="single", objective="water_saving", algorithm="GA", ratio=1.0):
    season_source = "s2" if scenario_type == "double" else "s1"
    return {
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
    assert "no browser-side decision was generated" in fallback_body


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
                "crops": [{"parcel_id": "P1", "crop_name": "BUGDAY", "area_share_pct": 100, "area_da": 1}],
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
    assert len(standardize_calls) == 3
    assert data["benchmark_mode"] == "detailed"
    assert data["requested_total_runs"] == 90
    assert data["completed_runs"] == 90
    assert data["completion_status_kind"] == "completed"
    assert data["benchmark_execution"]["candidate_matrix_build_count"] == 1
    assert data["benchmark_execution"]["standard_payload_scope"] == "best_run_only"
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
    data = post_optimize(client, scenario_type="double", objective="water_saving", ratio=5.0)
    plan = data["selected_plan"]
    assert len(plan["crops"]) == 2
    assert plan["status"] == "ok"
    assert plan["feasible"] is True
    assert plan["selectable"] is True


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
    assert "reservoir risk:" in script
    assert "plan risk:" in script
    assert "| risk: ${rTxt}" not in script
    assert "risk: düşük" not in script
    assert "baraj riski:" not in script


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
    assert "This mode uses a low repeat count" in script
    assert "fetchRunCountCalibrationPython" in script
    assert "/api/run_count_calibration" in script
    assert "Run Count Stability Analysis" in html


def test_partial_benchmark_language_is_preliminary_not_definitive():
    script = (ROOT / "script.js").read_text(encoding="utf-8")
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "Preliminary assessment" in script
    assert "Partial result:" in script
    assert "kesin en iyi algoritma dili kullanilmamalidir" in app_source
    assert "Kesin en iyi" not in script


def test_panel_open_defaults_still_preserved_in_static_ui():
    script = (ROOT / "script.js").read_text(encoding="utf-8")
    assert "PANEL_OPEN_DEFAULTS" in script
    assert 'parcelId: "P1"' in script
    assert 'scenario: "su_tasarruf"' in script
    assert 'cropCategoryMode: "mixed"' in script
    assert 'tab: "parcel"' in script
    assert 'switchTabByKey(key)' in script
