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
            "repeats": 3,
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
    assert ga["run_count"] == 3
    assert ga["completion_status"] == "completed"
    for key in ("best_profit", "mean_profit", "std_profit", "cv", "best_water", "mean_water", "tl_per_m3", "feasible_rate", "mean_runtime"):
        assert ga[key] is not None
    assert "ustunluk yorumu" in data["interpretation"]


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
            "repeats": 3,
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
