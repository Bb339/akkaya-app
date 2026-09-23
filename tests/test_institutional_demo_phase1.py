"""Institutional Phase 1 acceptance uses synthetic, explicitly non-official data."""
from __future__ import annotations

from copy import deepcopy
import io
import json

import pytest
from flask import Flask

from kds.api import register_project_api
from kds.application.optimization import OptimizationApplicationService
from kds.application.optimization import configuration
from kds.data.project_store import FileProjectStore
from kds.adapters.institutional import (
    materialize_verified_document, resolve_verified_water, verified_readiness,
)

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
    return ("planning_year,amount,unit,authority_class,source_institution,source_reference\n"
            f"2025,{amount},m3/year,{source_fields('MEASURED')}\n")


def monthly(kind):
    value = "amount" if kind == "monthly_water_supply" else "capacity"
    headers = ["planning_year", "month", value]
    if kind == "monthly_water_supply":
        headers += ["unit"]
    else:
        headers += ["source_unit", "canonical_unit", "capacity_basis"]
    headers += ["authority_class", "source_institution", "source_reference"]
    rows = [",".join(headers)]
    for month in range(1, 13):
        row = ["2025", f"2025-{month:02d}", "5000"]
        row += (["m3/month"] if kind == "monthly_water_supply" else
                ["m3/month", "m3/month", "measured_delivery"])
        row += source_fields("MEASURED").split(",")
        rows.append(",".join(row))
    return "\n".join(rows) + "\n"


def environmental():
    return ("planning_year,release_form,value,source_unit,canonical_unit,authority_class,source_institution,source_reference\n"
            f"2025,ratio,0.10,ratio,ratio,{source_fields('MEASURED')}\n")


def conveyance():
    return ("planning_year,period,efficiency,scope,authority_class,source_institution,source_reference\n"
            f"2025,annual,0.83,project,{source_fields('MEASURED')}\n")


def perennial():
    header = "planning_year,crop,value,source_unit,canonical_unit,confidence,method,authority_class,source_institution,source_reference"
    return header + "\n" + "\n".join(
        f"2025,{crop},120,m3/da,m3/da,verified,synthetic_contract,{source_fields('MEASURED')}"
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
    rows = [f"{crop},2025,project,PRIMARY,YEAR_SPECIFIC,2025-03-01,2025-09-01,LOCAL_INSTITUTIONAL,Synthetic Institute,{NOT_OFFICIAL}"
            for crop in CROPS]
    return head + "\n" + "\n".join(rows) + "\n"


def payload():
    return {"execution_profile": "VERIFIED_INSTITUTIONAL", "scenario": "S1", "algorithm": "GA",
            "seed": 2468, "objective": "max_profit", "water_budget_ratio": 1.0,
            "config": {"popSize": 12, "generations": 10, "cxRate": .7, "mutRate": .08}}


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
                       ("candidates", "candidates.csv"), ("scientific_inputs", "scientific_s1.csv")):
        upload(client, project_id, kind, (base / name).read_bytes(), name)
    for kind, content in (("annual_water_supply", annual(20000)),
                          ("monthly_water_supply", monthly("monthly_water_supply")),
                          ("delivery_capacity", monthly("delivery_capacity")),
                          ("environmental_release", environmental()),
                          ("conveyance_efficiency", conveyance()),
                          ("perennial_irrigation_requirement", perennial()),
                          ("crop_yield", economic("crop_yield")),
                          ("crop_sale_price", economic("crop_sale_price")),
                          ("crop_cost_components", economic("crop_cost_components")),
                          ("crop_net_profit", economic("crop_net_profit")),
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
    response = client.post(f"/api/v2/projects/{project_id}/analyses", json=payload())
    assert response.status_code == 201, response.json
    run = response.json; result = run["result"]
    assert result["status"] == "OK"
    assert result["execution_profile"] == "VERIFIED_INSTITUTIONAL"
    assert result["classification"] == "SYNTHETIC_TEST_OUTPUT"
    assert result["result_authority_label"] == "SYNTHETIC / NOT_OFFICIAL"
    assert result["input_provenance"]["input_datasets"]
    provenance = client.get(f"/api/v2/projects/{project_id}/analyses/{run['id']}/provenance").json
    assert provenance["input_snapshot"]["engine_commit"]
    assert repo.get(project_id)["analysis_state"]["requires_reanalysis"] is False


def test_replacement_pins_history_marks_reanalysis_and_changes_connected_output(institutional):
    client, repo, project_id = institutional
    first = client.post(f"/api/v2/projects/{project_id}/analyses", json=payload()).json
    old_result = deepcopy(first["result"])
    old_dataset = next(d for d in first["provenance"]["input_snapshot"]["input_datasets"]
                       if d["data_type"] == "annual_water_supply")
    upload(client, project_id, "annual_water_supply", annual(60000), "annual-water-v2.csv")
    state = repo.get(project_id)
    assert state["analysis_state"]["requires_reanalysis"] is True
    second = client.post(f"/api/v2/projects/{project_id}/analyses", json=payload()).json
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
    (lambda d: d["project"].update(pilot_geographic_scope="wrong-scope"), "crop_net_profit"),
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
    assert materialized["water_budget"]["amount"] == 20000
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


class _MemoryRepository:
    def __init__(self, document): self.document = deepcopy(document)
    def get(self, project_id): return deepcopy(self.document)
    def update(self, project_id, change): change(self.document); return deepcopy(self.document)
