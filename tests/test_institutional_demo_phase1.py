"""Institutional Phase 1 acceptance uses synthetic, explicitly non-official data."""
from __future__ import annotations

from copy import deepcopy
import io
import json
from pathlib import Path
import subprocess

import pytest
from flask import Flask

from kds.api import register_project_api
from kds.application.optimization import OptimizationApplicationService
from kds.application.optimization import configuration
from kds.data.project_store import FileProjectStore
from kds.adapters.institutional import (
    build_verified_bundle, materialize_verified_document, resolve_verified_water, verified_readiness,
)
from kds.science.institutional_water import validate_verified_result

FIXTURE_PROJECT = "SYNTHETIC_INSTITUTIONAL_TEST_PROJECT"
NOT_OFFICIAL = "synthetic not_official institutional integration fixture"
CROPS = ("ARPA", "NOHUT", "MERCIMEK", "AYCICEGI", "MISIR", "BUGDAY", "ELMA", "ARMUT")


def upload(client, project_id, data_type, content, filename=None):
    if isinstance(content, str):
        content = content.encode("utf-8")
    root = f"/api/v2/projects/{project_id}/imports"
    response = client.post(root, data={"data_type": data_type,
        "file": (io.BytesIO(content), filename or f"{data_type}.csv")}, content_type="multipart/form-data")
    assert response.status_code == 201, response.json
    batch = response.json
    mapped = client.post(root + "/" + batch["id"] + "/mapping",
                         json={"mapping": batch["suggested_mapping"]})
    assert mapped.status_code == 200 and mapped.json["status"] == "ready", mapped.json
    confirmed = client.post(root + "/" + batch["id"] + "/confirm",
                            json={"confirm": True, "acknowledge_warnings": True})
    assert confirmed.status_code == 200 and confirmed.json["status"] == "applied", confirmed.json
    return confirmed.json


def source_fields(authority):
    return f"{authority},Synthetic Institute,{NOT_OFFICIAL}"


def annual(amount):
    return ("planning_year,amount,unit,geographic_scope,authority_class,source_institution,source_reference\n"
            f"2025,{amount},m3/year,project,{source_fields('MEASURED')}\n")


def monthly(kind):
    value = "amount" if kind == "monthly_water_supply" else "capacity"
    headers = ["planning_year", "month", value]
    if kind == "monthly_water_supply":
        headers += ["unit"]
    else:
        headers += ["source_unit", "canonical_unit", "capacity_basis"]
    headers += ["geographic_scope", "authority_class", "source_institution", "source_reference"]
    rows = [",".join(headers)]
    for month in range(1, 13):
        row = ["2025", f"2025-{month:02d}", "5000"]
        row += (["m3/month"] if kind == "monthly_water_supply" else
                ["m3/month", "m3/month", "measured_delivery"])
        row += ["project", *source_fields("MEASURED").split(",")]
        rows.append(",".join(row))
    return "\n".join(rows) + "\n"


def environmental():
    return ("planning_year,release_form,value,source_unit,canonical_unit,geographic_scope,authority_class,source_institution,source_reference\n"
            f"2025,ratio,0.10,ratio,ratio,project,{source_fields('MEASURED')}\n")


def conveyance():
    return ("planning_year,period,efficiency,scope,authority_class,source_institution,source_reference\n"
            f"2025,annual,0.83,project,{source_fields('MEASURED')}\n")


def perennial():
    header = "planning_year,crop,value,source_unit,canonical_unit,geographic_scope,confidence,method,authority_class,source_institution,source_reference"
    return header + "\n" + "\n".join(
        f"2025,{crop},120,m3/da,m3/da,project,verified,synthetic_contract,{source_fields('MEASURED')}"
        for crop in CROPS) + "\n"


ECON_COMMON = "planning_year,observation_year,authority_class,source_institution,source_reference,currency,geographic_scope,crop_scope"


def economic(kind, profit_shift=0):
    authority = "LOCAL_INSTITUTIONAL_SOURCE"
    if kind == "crop_yield":
        head = f"crop,yield_value,yield_unit,{ECON_COMMON}"
        rows = [f"{crop},2,ton/da,2025,2025,{source_fields(authority)},TRY,project,catalog" for crop in CROPS]
    elif kind == "crop_sale_price":
        head = f"crop,price,price_unit,price_period,{ECON_COMMON}"
        rows = [f"{crop},1000,TL/ton,2025 average,2025,2025,{source_fields(authority)},TRY,project,catalog" for crop in CROPS]
    elif kind == "crop_cost_components":
        head = f"crop,cost_category,amount,unit,{ECON_COMMON}"
        rows = [f"{crop},other,400,TL/da,2025,2025,{source_fields(authority)},TRY,project,catalog" for crop in CROPS]
    elif kind == "crop_net_profit":
        head = f"crop,net_profit_per_da,calculation_method,{ECON_COMMON}"
        rows = [f"{crop},{1000 + i * 100 + profit_shift},DIRECT_SOURCE,2025,2025,{source_fields(authority)},TRY,project,catalog" for i,crop in enumerate(CROPS)]
    else:
        raise AssertionError(kind)
    return head + "\n" + "\n".join(rows) + "\n"


def crop_parameters():
    head = ("crop_identity,applicable_year,geographic_scope,kc_ini,kc_mid,kc_end,stage_value_mode,"
            "p_ini,p_dev,p_mid,p_late,authority_class,source,source_reference")
    rows = [f"{crop},2025,project,0.4,1.0,0.5,DAYS,20,30,40,20,LOCAL_INSTITUTIONAL,Synthetic Institute,{NOT_OFFICIAL}"
            for crop in CROPS]
    return head + "\n" + "\n".join(rows) + "\n"


def phenology():
    head = ("crop_identity,applicable_year,geographic_scope,season,mode,planting_date,harvest_date,"
            "authority_class,source,source_reference")
    rows = [f"{crop},2025,project,{season},YEAR_SPECIFIC,{planting},{harvest},LOCAL_INSTITUTIONAL,Synthetic Institute,{NOT_OFFICIAL}"
            for crop in CROPS for season,planting,harvest in (
                ("PRIMARY", "2025-03-01", "2025-06-30"),
                ("SECONDARY", "2025-07-01", "2025-10-31"))]
    return head + "\n" + "\n".join(rows) + "\n"


def seasonal_economics():
    head = ("crop,season,yield_value,yield_unit,price,price_unit,cost,cost_unit,net_profit,net_profit_unit,"
            "planning_year,observation_year,authority_class,source_institution,source_reference,currency,geographic_scope,crop_scope")
    rows = [f"{crop},{season},2,ton/da,1000,TL/ton,400,TL/da,{1000+i*100},TL/da,"
            f"2025,2025,LOCAL_INSTITUTIONAL_SOURCE,Synthetic Institute,{NOT_OFFICIAL},TRY,project,catalog"
            for i,crop in enumerate(CROPS) for season in ("PRIMARY", "SECONDARY")]
    return head + "\n" + "\n".join(rows) + "\n"


def payload():
    return {"execution_profile": "VERIFIED_INSTITUTIONAL", "scenario": "S1", "algorithm": "GA",
            "seed": 2468, "objective": "max_profit", "water_budget_ratio": 1.0,
            "config": {"popSize": 12, "generations": 10, "cxRate": .7, "mutRate": .08}}


def execution_payload(client, project_id, body=None):
    body = dict(body or payload())
    preview = client.post(f"/api/v2/projects/{project_id}/analysis-preview", json=body)
    assert preview.status_code == 200 and preview.json["ready"] is True, preview.json
    return {**body, **{key: preview.json[key] for key in ("preview_token", "preview_revision", "selection_hash")}}


@pytest.fixture
def institutional(tmp_path):
    repo = FileProjectStore(tmp_path / "projects")
    app = Flask("institutional-phase1"); app.config["TESTING"] = True
    register_project_api(app, repo)
    client = app.test_client(); project_id = "institutional-synthetic"
    project = json.loads((__import__("pathlib").Path(__file__).parent / "fixtures/general_project/project.json").read_text())
    project.update(id=project_id, name=FIXTURE_PROJECT, planning_year=2025,
                   data_source_notes=NOT_OFFICIAL)
    assert client.post("/api/v2/projects", json=project).status_code == 201
    base = __import__("pathlib").Path(__file__).parent / "fixtures/general_project"
    for kind, name in (("crops", "crops.xlsx"), ("analysis_units", "analysis_units.csv"),
                       ("economics", "economics.csv"), ("water_budget", "water_budget.csv"),
                       ("candidates", "candidates.csv"), ("scientific_inputs", "scientific_s1.csv"),
                       ("scientific_inputs", "scientific_s2.csv")):
        upload(client, project_id, kind, (base / name).read_bytes(), name)
    for kind, content in (("annual_water_supply", annual(60000)),
                          ("monthly_water_supply", monthly("monthly_water_supply")),
                          ("delivery_capacity", monthly("delivery_capacity")),
                          ("environmental_release", environmental()),
                          ("conveyance_efficiency", conveyance()),
                          ("perennial_irrigation_requirement", perennial()),
                          ("crop_yield", economic("crop_yield")),
                          ("crop_sale_price", economic("crop_sale_price")),
                          ("crop_cost_components", economic("crop_cost_components")),
                          ("crop_net_profit", economic("crop_net_profit")),
                          ("seasonal_economics", seasonal_economics()),
                          ("crop_water_parameters", crop_parameters()),
                          ("crop_phenology", phenology())):
        upload(client, project_id, kind, content)
    return client, repo, project_id


def test_verified_institutional_end_to_end_and_explicit_result_contract(institutional):
    client, repo, project_id = institutional
    ready = client.get(f"/api/v2/projects/{project_id}/readiness").json
    assert ready["execution_profiles"]["VERIFIED_INSTITUTIONAL"]["ready"]["S1"] is True
    assert all(domain["engine_connected"] for domain in ready["domains"].values())
    preview = client.post(f"/api/v2/projects/{project_id}/analysis-preview", json=payload()).json
    assert preview["ready"] is True and preview["execution_profile"] == "VERIFIED_INSTITUTIONAL"
    assert preview["result_authority_label"] == "SYNTHETIC / NOT_OFFICIAL"
    assert preview["candidate_source"]["candidate_count"] == 24 * 8
    response = client.post(f"/api/v2/projects/{project_id}/analyses", json=execution_payload(client, project_id))
    assert response.status_code == 201, response.json
    run = response.json; result = run["result"]
    assert result["status"] == "OK"
    assert result["execution_profile"] == "VERIFIED_INSTITUTIONAL"
    assert result["classification"] == "SYNTHETIC_TEST_OUTPUT"
    assert result["result_authority_label"] == "SYNTHETIC / NOT_OFFICIAL"
    assert result["input_provenance"]["input_datasets"]
    assert result["HHI"] >= 0 and result["top_crops"] and result["crop_shares"]
    assert result["hhi"] == result["HHI"]
    assert result["authoritative_water_m3"] == result["verified_profile_water_m3"]
    assert result["total_water_m3"] == result["authoritative_water_m3"]
    assert result["water_reconciliation"]["optimizer_water_m3"] == result["optimizer_water_m3"]
    assert result["water_reconciliation"]["status"] in {"PASS", "DIFFERENT_DEFINITIONS"}
    assert result["unit_results"]
    assert result["annual_budget_validation"]["status"] in {"PASS", "FAIL"}
    assert result["monthly_supply_validation"]["status"] in {"PASS", "FAIL"}
    assert result["monthly_delivery_validation"]["status"] in {"PASS", "FAIL"}
    assert isinstance(result["overall_feasible"], bool)
    assert result["result_provenance"]["selection_hash"]
    assert result["result_provenance"]["consumer_roles"]["monthly_supply"] == "POST_RUN_VALIDATION"
    assert run["provenance"]["input_snapshot"]["climate_source"]["mode"] == "CLIMATOLOGICAL_NORMAL"
    assert run["provenance"]["input_snapshot"]["current_pattern_source"]["file_hash"]
    provenance = client.get(f"/api/v2/projects/{project_id}/analyses/{run['id']}/provenance").json
    assert provenance["input_snapshot"]["engine_commit"]
    assert repo.get(project_id)["analysis_state"]["requires_reanalysis"] is False


def test_replacement_pins_history_marks_reanalysis_and_changes_connected_output(institutional):
    client, repo, project_id = institutional
    first = client.post(f"/api/v2/projects/{project_id}/analyses", json=execution_payload(client, project_id)).json
    old_result = deepcopy(first["result"])
    old_dataset = next(d for d in first["provenance"]["input_snapshot"]["input_datasets"]
                       if d["data_type"] == "annual_water_supply")
    upload(client, project_id, "annual_water_supply", annual(120000), "annual-water-v2.csv")
    upload(client, project_id, "monthly_water_supply",
           monthly("monthly_water_supply").replace(",5000,m3/month,", ",10000,m3/month,"),
           "monthly-water-v2.csv")
    state = repo.get(project_id)
    assert state["analysis_state"]["requires_reanalysis"] is True
    second = client.post(f"/api/v2/projects/{project_id}/analyses", json=execution_payload(client, project_id)).json
    new_dataset = next(d for d in second["provenance"]["input_snapshot"]["input_datasets"]
                       if d["data_type"] == "annual_water_supply")
    assert old_dataset["dataset_id"] != new_dataset["dataset_id"]
    assert old_dataset["version"] == 1 and new_dataset["version"] == 2
    assert first["provenance"]["input_snapshot"]["input_datasets"] != second["provenance"]["input_snapshot"]["input_datasets"]
    stored_first = client.get(f"/api/v2/projects/{project_id}/analyses/{first['id']}").json
    assert stored_first["result"] == old_result
    assert first["result"]["water_budget_m3"] != second["result"]["water_budget_m3"]


@pytest.mark.parametrize("mutation,reason", [
    (lambda d: d["water_data"]["active"].pop("annual_water_supply"), "annual_water_supply"),
    (lambda d: d["crop_parameter_data"]["active"].pop("crop_phenology|2025|project"), "crop_phenology"),
    (lambda d: d["economic_data"]["active"].pop("crop_net_profit|2025|project|catalog"), "crop_net_profit"),
    (lambda d: d["water_data"]["datasets"][d["water_data"]["active"]["annual_water_supply"]].update(status="inactive"), "active and confirmed"),
    (lambda d: d["water_data"]["datasets"][d["water_data"]["active"]["annual_water_supply"]]["records"][0].update(planning_year=2024), "planning year"),
    (lambda d: d["economic_data"]["datasets"][d["economic_data"]["active"]["crop_net_profit|2025|project|catalog"]].update(derivation_status="STALE"), "stale"),
    (lambda d: d["project"].update(pilot_geographic_scope="wrong-scope"), "geographic scope"),
    (lambda d: d["crop_parameter_data"]["datasets"][d["crop_parameter_data"]["active"]["crop_water_parameters|2025|project"]]["records"][0].update(resolution_status="AMBIGUOUS"), "incomplete or ambiguous"),
])
def test_verified_mode_fails_closed_without_silent_reference_fallback(institutional, mutation, reason):
    _, repo, project_id = institutional
    document = repo.get(project_id); mutation(document)
    status = verified_readiness(document, "S1")
    assert status["ready"] is False and reason in status["blocking_reasons"][0]
    service = OptimizationApplicationService(_MemoryRepository(document), lambda bundle: pytest.fail("engine must not run"))
    with pytest.raises(ValueError, match=reason):
        service.run(project_id, payload())


def test_reference_demo_remains_available_and_verified_materialization_is_project_scoped(institutional):
    client, repo, project_id = institutional
    reference = {**payload(), "execution_profile": "REFERENCE_DEMO"}
    assert client.post(f"/api/v2/projects/{project_id}/analysis-preview", json=reference).json["ready"] is True
    document = repo.get(project_id)
    before = deepcopy(document)
    materialized, _, plan = materialize_verified_document(document, configuration(payload(), document))
    assert document == before
    assert materialized["project"]["id"] == project_id
    assert materialized["water_budget"]["amount"] == 54000
    assert plan["candidate_source"]["analysis_unit_count"] == 24


def test_project_isolation(institutional):
    client, repo, project_id = institutional
    response = client.post("/api/v2/projects", json={
        "id": "isolated-project", "name": FIXTURE_PROJECT, "planning_year": 2025,
        "annual_water_budget": 1, "water_budget_unit": "m3", "data_source_notes": NOT_OFFICIAL,
    })
    assert response.status_code == 201
    isolated = repo.get("isolated-project")
    assert isolated["water_data"]["datasets"] == {}
    assert isolated["economic_data"]["datasets"] == {}
    assert verified_readiness(isolated, "S1")["ready"] is False
    assert repo.get(project_id)["water_data"]["datasets"]


def test_reference_demo_regression_values_and_authority_label():
    from decimal import Decimal
    import app
    from kds.adapters.akkaya_demo import build_demo
    document = build_demo(app.DATA_DIR)
    assert len(document["analysis_units"]) == 179
    assert sum(Decimal(str(u["area_da"])) for u in document["analysis_units"]) == Decimal("134919")
    assert document["metadata"]["references"]["raw_candidate_rows"] == 6859
    assert len(document["crops"]) == 58
    assert document["water_budget"]["amount"] == 100700080.81
    assert sum(Decimal(u["metadata"]["current_profit_tl"]) for u in document["analysis_units"]) == Decimal("1041499119.212")
    service = OptimizationApplicationService(_MemoryRepository(document))
    preview = service.preview(document["project"]["id"], {
        "scenario": "S1", "algorithm": "GA", "seed": 101, "objective": "water_saving",
        "water_budget_ratio": 1.0, "config": {"popSize": 8, "generations": 4, "cxRate": .7, "mutRate": .08},
        "execution_profile": "REFERENCE_DEMO",
    })
    assert preview["ready"] is True
    assert preview["result_authority_label"] == "REFERENCE MODEL / DEMO DATA"


def test_frozen_algorithms_and_akkaya_data_match_accepted_baseline():
    root = Path(__file__).resolve().parents[1]

    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=root, check=True, text=True, capture_output=True
        ).stdout.strip()

    baseline = "v2-scientific-robustness-sensitivity-complete^{}"
    assert git("rev-parse", f"{baseline}:data") == git("rev-parse", "HEAD:data")
    assert git("diff", "--name-only", baseline, "HEAD", "--", "app.py", "data") == ""
    changed = git("diff", "--name-only", baseline, "HEAD", "--", "kds/science").splitlines()
    assert changed == ["kds/science/institutional_water.py"]


def test_stale_preview_is_rejected_and_explicit_profile_is_required(institutional):
    client, _, project_id = institutional
    missing = client.post(f"/api/v2/projects/{project_id}/analysis-preview",
                          json={key: value for key, value in payload().items() if key != "execution_profile"})
    assert missing.status_code == 400
    preview = client.post(f"/api/v2/projects/{project_id}/analysis-preview", json=payload()).json
    stale = {**payload(), **{key: preview[key] for key in ("preview_token", "preview_revision", "selection_hash")}}
    upload(client, project_id, "annual_water_supply", annual(60001), "annual-after-preview.csv")
    response = client.post(f"/api/v2/projects/{project_id}/analyses", json=stale)
    assert response.status_code == 400
    assert "STALE_PREVIEW / REVISION_CONFLICT" in response.json["error"]


def test_water_scope_and_physical_release_fail_closed(institutional):
    client, repo, project_id = institutional
    scoped = annual(60000).replace(",project,MEASURED", ",other-basin,MEASURED")
    upload(client, project_id, "annual_water_supply", scoped, "wrong-scope.csv")
    assert "geographic scope" in verified_readiness(repo.get(project_id), "S1")["blocking_reasons"][0]

    # Restore project scope, then activate a contract-valid physical release.
    upload(client, project_id, "annual_water_supply", annual(60001), "project-scope.csv")
    header = "planning_year,month,release_form,value,source_unit,canonical_unit,geographic_scope,authority_class,source_institution,source_reference"
    physical = header + "\n" + "\n".join(
        f"2025,2025-{month:02d},monthly_release,10,m3/month,m3/month,project,MEASURED,Synthetic Institute,{NOT_OFFICIAL}"
        for month in range(1, 13)) + "\n"
    upload(client, project_id, "environmental_release", physical, "physical-release.csv")
    state = verified_readiness(repo.get(project_id), "S1")
    assert state["ready"] is False
    assert state["domains"]["environmental_release"]["connection_state"] == "NOT_EXECUTABLE_WITH_CURRENT_MODE"


def _context(document, body=None):
    config = configuration(body or payload(), document)
    materialized, adjusted, plan = materialize_verified_document(document, config)
    bundle, _, _, context = build_verified_bundle(document, config)
    return materialized, adjusted, plan, bundle, context


def _one_unit_result(document):
    unit = document["analysis_units"][0]
    crop = document["crops"][0]["name"]
    return {"feasible": True, "details": [{"parcelId": unit["external_id"], "area_da": unit["area_da"],
                                              "chosenCrop": crop}]}


def test_controlled_verified_inputs_reach_scientific_consumers(institutional):
    client, repo, project_id = institutional
    baseline = repo.get(project_id)
    base_doc, _, _, _, base_context = _context(baseline)
    candidate_key = (baseline["scientific_inputs"]["candidates"][0]["analysis_unit_id"],
                     baseline["scientific_inputs"]["candidates"][0]["crop"])
    def candidate_water(document):
        return next(row["water_requirement_m3_da"] for row in document["scientific_inputs"]["candidates"]
                    if (row["analysis_unit_id"], row["crop"]) == candidate_key)

    upload(client, project_id, "crop_net_profit", economic("crop_net_profit", 5000), "profit-effect.csv")
    profit_doc, _, _, _, _ = _context(repo.get(project_id))
    assert profit_doc["scientific_inputs"]["candidates"][0]["profit_per_da"] != base_doc["scientific_inputs"]["candidates"][0]["profit_per_da"]

    before_water = candidate_water(profit_doc)
    upload(client, project_id, "crop_water_parameters",
           crop_parameters().replace("0.4,1.0,0.5", "0.9,1.4,0.8"), "kc-effect.csv")
    kc_doc, _, _, _, _ = _context(repo.get(project_id))
    assert candidate_water(kc_doc) != before_water

    before_water = candidate_water(kc_doc)
    upload(client, project_id, "crop_phenology",
           phenology().replace("2025-03-01,2025-06-30", "2025-04-01,2025-08-31"), "phenology-effect.csv")
    phenology_doc, _, _, _, _ = _context(repo.get(project_id))
    assert candidate_water(phenology_doc) != before_water

    before_water = candidate_water(phenology_doc)
    upload(client, project_id, "conveyance_efficiency", conveyance().replace("0.83", "0.45"), "conveyance-effect.csv")
    conveyance_doc, _, _, _, _ = _context(repo.get(project_id))
    assert candidate_water(conveyance_doc) > before_water

    # Annual supply and environmental release change the optimizer budget exactly once.
    upload(client, project_id, "annual_water_supply", annual(120000), "annual-effect.csv")
    upload(client, project_id, "monthly_water_supply",
           monthly("monthly_water_supply").replace(",5000,m3/month,", ",10000,m3/month,"),
           "monthly-effect.csv")
    annual_doc, _, _, _, _ = _context(repo.get(project_id))
    assert annual_doc["water_budget"]["amount"] == pytest.approx(108000)
    upload(client, project_id, "environmental_release", environmental().replace("0.10", "0.50"), "release-effect.csv")
    release_doc, _, _, _, release_context = _context(repo.get(project_id))
    assert release_doc["water_budget"]["amount"] == pytest.approx(60000)

    result = _one_unit_result(repo.get(project_id))
    high = validate_verified_result(result, "S1", release_context["monthly_profiles"],
        release_context["annual_supply_m3"], release_context["monthly_supply_m3"],
        release_context["monthly_delivery_capacity_m3"], release_context["environmental_release"])
    low_monthly = {month: 1.0 for month in release_context["monthly_supply_m3"]}
    low_supply = validate_verified_result(result, "S1", release_context["monthly_profiles"],
        release_context["annual_supply_m3"], low_monthly,
        release_context["monthly_delivery_capacity_m3"], release_context["environmental_release"])
    assert high["monthly_supply_validation"] != low_supply["monthly_supply_validation"]
    low_delivery = {month: 1.0 for month in release_context["monthly_delivery_capacity_m3"]}
    delivery = validate_verified_result(result, "S1", release_context["monthly_profiles"],
        release_context["annual_supply_m3"], release_context["monthly_supply_m3"],
        low_delivery, release_context["environmental_release"])
    assert delivery["monthly_delivery_validation"]["status"] == "FAIL"
    assert delivery["overall_feasible"] is False


def test_verified_s2_e2e_and_perennial_specificity(institutional):
    client, repo, project_id = institutional
    body = {**payload(), "scenario": "S2", "config": {"popSize": 8, "generations": 4,
                                                         "cxRate": .7, "mutRate": .08}}
    ready = client.get(f"/api/v2/projects/{project_id}/readiness").json
    assert ready["execution_profiles"]["VERIFIED_INSTITUTIONAL"]["ready"]["S2"] is True
    response = client.post(f"/api/v2/projects/{project_id}/analyses",
                           json=execution_payload(client, project_id, body))
    assert response.status_code == 201, response.json
    assert response.json["result"]["classification"] == "SYNTHETIC_TEST_OUTPUT"
    assert response.json["result"]["scenario"] == "S2"
    assert response.json["result"]["unit_results"]

    header = "planning_year,crop,analysis_unit_id,value,source_unit,canonical_unit,geographic_scope,confidence,method,authority_class,source_institution,source_reference"
    content = header + "\n" + "\n".join([
        f"2025,ELMA,,120,m3/da,m3/da,project,verified,synthetic_contract,MEASURED,Synthetic Institute,{NOT_OFFICIAL}",
        f"2025,ELMA,GX-001,900,m3/da,m3/da,project,verified,synthetic_contract,MEASURED,Synthetic Institute,{NOT_OFFICIAL}",
    ]) + "\n"
    upload(client, project_id, "perennial_irrigation_requirement", content, "perennial-specific.csv")
    materialized, _, _ = materialize_verified_document(repo.get(project_id), configuration(body, repo.get(project_id)))
    rows = materialized["scientific_inputs"]["seasonal_resources"]["s2"]
    exact = next(row for row in rows if row["parcel_id"] == "GX-001" and row["crop"] == "ELMA" and row["season"] == "primary")
    other = next(row for row in rows if row["parcel_id"] != "GX-001" and row["crop"] == "ELMA" and row["season"] == "primary")
    assert exact["water_m3_calib_gross"] / exact["area_da"] == pytest.approx(900)
    assert other["water_m3_calib_gross"] / other["area_da"] == pytest.approx(120)

    cross_year = phenology().replace("2025-03-01,2025-06-30", "2024-10-01,2025-06-30")
    upload(client, project_id, "crop_phenology", cross_year, "cross-year-phenology.csv")
    for kind, field, units in (("monthly_water_supply", "amount", "unit"),
                               ("delivery_capacity", "capacity", "source_unit,canonical_unit,capacity_basis")):
        content = monthly(kind).rstrip("\n")
        for month in (10, 11, 12):
            tail = ("5000,m3/month,project" if kind == "monthly_water_supply" else
                    "5000,m3/month,m3/month,measured_delivery,project")
            content += f"\n2025,2024-{month:02d},{tail},{source_fields('MEASURED')}"
        upload(client, project_id, kind, content + "\n", f"cross-year-{kind}.csv")
    crossed, _, _ = materialize_verified_document(repo.get(project_id), configuration(body, repo.get(project_id)))
    arpa = next(row for row in crossed["scientific_inputs"]["seasonal_resources"]["s2"]
                if row["parcel_id"] == "GX-001" and row["crop"] == "ARPA" and row["season"] == "primary")
    assert arpa["planting_date"] == "2024-10-01" and arpa["harvest_date"] == "2025-06-30"
    cross_response = client.post(f"/api/v2/projects/{project_id}/analyses",
                                 json=execution_payload(client, project_id, body))
    assert cross_response.status_code == 201, cross_response.json
    cross_result = cross_response.json["result"]
    assert cross_result["result_provenance"]["consumer_roles"]["monthly_supply"] == "POST_RUN_VALIDATION"
    assert cross_result["result_provenance"]["consumer_roles"]["approximate_s2_monthly_optimizer"] == "OPTIMIZER_CONSTRAINT"
    calendar_months = {month for row in cross_result["unit_results"]
                       for month in row["monthly_water_demand_m3"]}
    assert {"2024-10", "2024-11", "2024-12"} <= calendar_months

    duplicate = header + "\n" + "\n".join([
        f"2025,ELMA,GX-001,900,m3/da,m3/da,project,verified,synthetic_contract,MEASURED,Synthetic Institute,{NOT_OFFICIAL}",
        f"2025,ELMA,GX-001,901,m3/da,m3/da,project,verified,synthetic_contract,MEASURED,Synthetic Institute,{NOT_OFFICIAL}",
    ]) + "\n"
    root = f"/api/v2/projects/{project_id}/imports"
    uploaded = client.post(root, data={"data_type": "perennial_irrigation_requirement",
        "file": (io.BytesIO(duplicate.encode()), "duplicate-perennial.csv")}, content_type="multipart/form-data").json
    mapped = client.post(root + "/" + uploaded["id"] + "/mapping",
                         json={"mapping": uploaded["suggested_mapping"]})
    assert mapped.status_code == 200 and mapped.json["status"] == "invalid"


class _MemoryRepository:
    def __init__(self, document): self.document = deepcopy(document)
    def get(self, project_id): return deepcopy(self.document)
    def update(self, project_id, change): change(self.document); return deepcopy(self.document)
