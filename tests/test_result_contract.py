"""S2 optimizer and validated-final stages stay explicit and internally consistent."""
from copy import deepcopy
import pytest
from kds.application.optimization import OptimizationApplicationService, configuration
from kds.application.project_overview import history
from kds.data.project_store import FileProjectStore
from kds.science.results import RESULT_CONTRACT_VERSION, project_result
from test_analysis_workflow import example, request_body, with_seasons


def engine_result():
    def recommendation(name, water, profit):
        return dict(name=name, season="test", area=10.0, waterPerDa=water / 10,
                    waterTotal=water, profitPerDa=profit / 10, profitTotal=profit)

    return dict(
        status="OK", algorithm="GA", objective="water_saving", year=2025,
        water_budget_m3=1000.0, feasible=True,
        total_water_m3=450.0, total_profit_tl=4500.0, efficiency_tl_per_m3=10.0,
        details=[
            dict(parcelId="P1", parcelName="P1", area_da=10.0,
                 primary=dict(crop="ARPA", water_m3=100.0, profit_tl=1000.0),
                 secondary=dict(crop="NOHUT", water_m3=200.0, profit_tl=2000.0)),
            dict(parcelId="P2", parcelName="P2", area_da=10.0,
                 primary=dict(crop="NOHUT", water_m3=150.0, profit_tl=1500.0),
                 secondary=dict(crop="ARPA", water_m3=100.0, profit_tl=1000.0)),
        ],
        parcels=[
            dict(id="P1", result=dict(parcel=dict(id="P1", name="P1", area_da=10.0),
                                      recommended=[recommendation("NOHUT", 150.0, 1500.0),
                                                   recommendation("NADAS", 0.0, 0.0)])),
            dict(id="P2", result=dict(parcel=dict(id="P2", name="P2", area_da=10.0),
                                      recommended=[recommendation("ARPA", 100.0, 1000.0),
                                                   recommendation("NOHUT", 200.0, 2000.0)])),
        ],
        meta=dict(selected_parcel_ids=["P1", "P2"], delivery_report=None,
                  run_params=dict(algorithm="GA", seed=123, bestScore=99.0)),
        delta=dict(water_m3=-50.0, profit_tl=-500.0),
    )


def test_s2_contract_separates_raw_choices_from_final_authority():
    document = with_seasons(example())
    config = configuration(request_body("S2"), document)
    source = engine_result()
    projected = project_result(source, config, document["analysis_units"])

    assert projected["result_contract_version"] == RESULT_CONTRACT_VERSION
    assert projected["raw_optimizer_plan"]["details"][0]["primary"]["crop"] == "ARPA"
    assert projected["validated_final_plan"]["details"][0]["primary"]["crop"] == "NOHUT"
    assert projected["details"] == projected["validated_final_plan"]["details"]
    assert projected["total_water_m3"] == projected["final_metrics"]["total_water_m3"] == 450.0
    assert projected["total_profit_tl"] == projected["final_metrics"]["total_profit_tl"] == 4500.0
    assert projected["raw_optimizer_plan"]["metrics"]["total_water_m3"] == 550.0
    assert projected["raw_optimizer_plan"]["metrics"]["feasible"] is None
    assert projected["raw_optimizer_plan"]["feasibility_status"] == "not_validated"
    assert projected["validated_final_plan"]["validation"] == {
        "authority": "engine post-guard parcel recommendations",
        "engine_guard_feasible": True,
        "annual_water_budget_met": True,
        "monthly_delivery_evaluated": False,
        "engine_reported_totals_consistent": True,
        "scope": "Existing engine guards only; monthly feasibility is reported only when the engine supplies a delivery report.",
    }
    assert projected["final_metrics"]["active_area_da"] == 20.0
    assert projected["final_metrics"]["fallow_area_da"] == 0.0
    assert projected["final_metrics"]["crop_distribution_da"] == {"NOHUT": 20.0, "ARPA": 10.0}
    assert projected["details"][0]["secondary"] is None

    source["details"][0]["primary"]["crop"] = "MUTATED"
    projected["raw_optimizer_plan"]["details"][0]["primary"]["crop"] = "RAW-MUTATED"
    assert projected["details"][0]["primary"]["crop"] == "NOHUT"


def test_s1_result_contract_is_pass_through_copy():
    result = {"status": "OK", "details": [{"parcelId": "P1", "chosenCrop": "ARPA"}]}
    projected = project_result(result, {"scenario": "S1"}, [])
    assert projected == result and projected is not result


def test_service_persists_final_defaults_and_consistent_summary(tmp_path):
    repository = FileProjectStore(tmp_path / "projects")
    document = with_seasons(example())
    repository.create(document)
    run = OptimizationApplicationService(repository, lambda bundle: engine_result()).run("sample-a", request_body("S2"))

    assert run["status"] == "completed"
    assert run["result"]["details"][0]["primary"]["crop"] == "NOHUT"
    assert run["result"]["raw_optimizer_plan"]["details"][0]["primary"]["crop"] == "ARPA"
    assert run["summary"]["total_water_m3"] == run["result"]["total_water_m3"] == 450.0
    assert run["summary"]["total_profit_tl"] == run["result"]["total_profit_tl"] == 4500.0
    assert run["summary"]["active_area_da"] == 20.0
    assert history(repository.get("sample-a"))["items"][0]["water"] == 450.0


def test_legacy_s2_get_is_projected_without_store_migration(tmp_path):
    repository = FileProjectStore(tmp_path / "projects")
    document = with_seasons(example())
    config = configuration(request_body("S2"), document)
    old = dict(
        id="run-old", project_id="sample-a", data_version="old", configuration=config,
        scenario="S2", algorithm="GA", seed=123, started_at="2025-01-01T00:00:00+00:00",
        completed_at="2025-01-01T00:01:00+00:00", status="completed",
        result=engine_result(), error=None, provenance={}, warnings=[],
        summary=dict(total_water_m3=999.0, total_profit_tl=999.0, active_area_da=999.0),
    )
    document["runs"] = {"run-old": deepcopy(old)}
    repository.create(document)
    before = repository.get("sample-a")

    presented = OptimizationApplicationService(repository).get("sample-a", "run-old")
    assert presented["result"]["result_contract_version"] == RESULT_CONTRACT_VERSION
    assert presented["result"]["total_water_m3"] == presented["summary"]["total_water_m3"] == 450.0
    assert presented["result"]["monthly_delivery_validation"]["status"] == "not_available"
    assert history(repository.get("sample-a"))["items"][0]["water"] == 450.0
    assert repository.get("sample-a") == before
    assert "result_contract_version" not in repository.get("sample-a")["runs"]["run-old"]["result"]


def test_contract_exposes_inconsistent_engine_totals_without_using_them_as_final():
    document = with_seasons(example())
    source = engine_result()
    source["total_water_m3"] = 999.0
    projected = project_result(source, configuration(request_body("S2"), document), document["analysis_units"])
    assert projected["total_water_m3"] == 450.0
    assert projected["validated_final_plan"]["validation"]["engine_reported_totals_consistent"] is False


def test_result_contract_exposes_real_monthly_delivery_validation():
    document = with_seasons(example())
    source = engine_result()
    source["meta"]["delivery_report"] = {
        "status": "violation", "unit": "m3/month", "period": "calendar_month",
        "months": list(range(1, 13)), "cap_m3": [30.0] * 12,
        "demand_m3": [40.0] * 12, "exceed_m3": [10.0] * 12,
        "feasible_monthly": False, "violating_months": list(range(1, 13)),
        "worst_exceed_m3": 10.0, "total_capacity_m3": 360.0,
        "total_demand_m3": 480.0,
    }
    projected = project_result(
        source, configuration(request_body("S2"), document), document["analysis_units"])
    monthly = projected["monthly_delivery_validation"]
    assert monthly == projected["validated_final_plan"]["monthly_delivery_validation"]
    assert monthly["status"] == "violation" and monthly["unit"] == "m3/month"
    assert monthly["months"] == 12 and monthly["violating_months"] == list(range(1, 13))
    assert monthly["max_violation_m3"] == 10.0
    assert monthly["total_capacity_m3"] == 360.0
    assert monthly["total_demand_m3"] == 480.0


def _stable_hash(value):
    import hashlib
    import json
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@pytest.mark.full_project
def test_full_akkaya_s2_ga_phase1_acceptance():
    """Optional Tier 2 gate: exactly one full engine execution for this phase."""
    import json
    import os
    from pathlib import Path
    import app
    from general_project_support import config
    from kds.adapters.akkaya_demo import build_demo
    from kds.adapters.project_science import build_bundle
    from kds.science.execution import execute

    document = build_demo(app.DATA_DIR)
    configured = configuration(config("S2", "GA", 123), document)
    engine = execute(build_bundle(document, configured))
    result = project_result(engine, configured, document["analysis_units"])
    final = result["validated_final_plan"]
    assert len(document["analysis_units"]) == len(final["details"]) == 179
    assert result["total_water_m3"] == pytest.approx(23933291.2028)
    assert result["total_profit_tl"] == pytest.approx(188154778.3904635)
    assert result["feasible"] is False
    assert final["validation"]["engine_reported_totals_consistent"] is True

    by_unit = {u["external_id"]: u for u in document["analysis_units"]}
    protected = {uid for uid, unit in by_unit.items()
                 if app.canonical_crop_key(unit["current_crop"]) in app.PERENNIAL_CROPS}
    assert len(protected) == 52
    by_result = {row["parcelId"]: row for row in final["details"]}
    assert all(app.canonical_crop_key(by_result[uid]["primary"]["crop"]) ==
               app.canonical_crop_key(by_unit[uid]["current_crop"]) for uid in protected)

    folder = os.environ.get("KDS_FIX1_ACCEPTANCE_OUTPUT")
    if folder:
        output = Path(folder)
        output.mkdir(parents=True, exist_ok=True)
        (output / "full-Akkaya-S2-GA-123.json").write_text(json.dumps(dict(
            scenario="S2", algorithm="GA", seed=123, units=179,
            protected_orchards=52, raw_plan_hash=_stable_hash(result["raw_optimizer_plan"]["details"]),
            final_plan_hash=_stable_hash(final["details"]),
            raw_water_m3=result["raw_optimizer_plan"]["metrics"]["total_water_m3"],
            raw_profit_tl=result["raw_optimizer_plan"]["metrics"]["total_profit_tl"],
            final_water_m3=result["total_water_m3"], final_profit_tl=result["total_profit_tl"],
            water_budget_m3=result["water_budget_m3"], feasible=result["feasible"],
            validation=final["validation"]), indent=2), encoding="utf8")
