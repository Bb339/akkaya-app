from copy import deepcopy
from pathlib import Path

import pytest
from flask import Flask
from playwright.sync_api import expect, sync_playwright

from kds.adapters.institutional import verified_readiness
from kds.api import register_project_api
from kds.application.decision_provider import project_decision_context
from kds.application.optimization import OptimizationApplicationService
from kds.application.readiness import _reference_demo_authority_readiness, readiness
from scripts.import_v1_reference_dataset import import_package
from test_unified_decision_demo_browser import serve
from test_v1_reference_project_workflow import MemoryProjectRepository


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "data" / "project_packages" / "v1_reference_dataset"


@pytest.fixture(scope="module")
def reference_project():
    repository = MemoryProjectRepository()
    document, evidence = import_package(repository, PACKAGE)
    assert len(evidence) == 21 and document["data_revision"] == 21
    return repository, document


@pytest.fixture(scope="module")
def reference_report(reference_project):
    return readiness(reference_project[1])


def test_reference_demo_global_readiness_uses_reference_policy(reference_report):
    report = reference_report
    assert report["effective_execution_profile"] == "REFERENCE_DEMO"
    assert report["status"] == "READY_WITH_WARNINGS"
    assert report["ready"] is True
    assert not report["blocking_reasons"]
    assert report["domains"]["annual_water"]["connection_state"] == "CONNECTED"


def test_reference_demo_calculated_reference_is_warning_not_blocker(reference_report):
    report = reference_report
    assert any("CALCULATED_REFERENCE" in warning for warning in report["warnings"])
    for name in ("annual_water", "monthly_supply", "delivery", "environmental_release", "conveyance", "economics"):
        domain = report["domains"][name]
        assert domain["status"] == "READY"
        assert domain["authority_warning"] is True
        assert domain["blocking_reason"] is None


def test_reference_demo_assumed_is_warning_not_blocker(reference_report):
    report = reference_report
    assert any("ASSUMED" in warning for warning in report["warnings"])
    for name in ("crop_parameters", "phenology"):
        domain = report["domains"][name]
        assert domain["status"] == "READY" and domain["authority_warning"] is True


def test_reference_demo_global_and_scenario_readiness_agree(reference_report):
    report = reference_report
    assert report["status"] == "READY_WITH_WARNINGS"
    assert {name: state["status"] for name, state in report["scenarios"].items()} == {
        "S1": "READY_WITH_WARNINGS", "S2": "READY_WITH_WARNINGS"
    }
    assert report["execution_profiles"]["REFERENCE_DEMO"]["ready"] == {"S1": True, "S2": True}


def test_reference_demo_revision21_has_zero_blockers(reference_project, reference_report):
    report = reference_report
    assert reference_project[1]["data_revision"] == 21
    assert len(report["blocking_reasons"]) == 0


def test_verified_institutional_still_rejects_nonverified_authority(reference_project):
    strict = verified_readiness(reference_project[1], "S1")
    assert strict["ready"] is False
    assert any("authority is not eligible for verified execution" in reason
               for reason in strict["blocking_reasons"])


def test_reference_demo_does_not_weaken_verified_institutional_rules(reference_project):
    institutional = deepcopy(reference_project[1])
    institutional["metadata"].pop("reference_demo", None)
    institutional["metadata"]["classification"] = "INSTITUTIONAL"
    institutional["project"]["data_source_notes"] = "user_provided"
    report = readiness(institutional)
    assert report["effective_execution_profile"] == "VERIFIED_INSTITUTIONAL"
    assert report["ready"] is False
    assert any("authority is not eligible for verified execution" in reason
               for reason in report["blocking_reasons"])


def test_reference_demo_still_blocks_a_genuinely_missing_required_dataset(reference_project):
    missing = deepcopy(reference_project[1])
    missing["water_data"]["active"].pop("annual_water_supply")
    report = _reference_demo_authority_readiness(missing, "S1")
    assert report["ready"] is False
    assert any("annual_water_supply" in reason for reason in report["blocking_reasons"])


def test_reference_demo_climate_mode_resolves_correctly(reference_report):
    report = reference_report
    assert report["execution_profiles"]["REFERENCE_DEMO"]["climate_mode"] == "YEAR_SPECIFIC"
    assert report["domains"]["climate"]["mode"] == "YEAR_SPECIFIC"
    assert report["domains"]["climate"]["connection_state"] == "CONNECTED"


def test_reference_demo_profile_is_shared_by_context_preview_and_run_contract(reference_project):
    repository, document = reference_project
    context = project_decision_context(document)
    payload = {
        "execution_profile": "REFERENCE_DEMO", "scenario": "S1", "algorithm": "GA",
        "seed": 123, "objective": "water_saving", "water_budget_ratio": 1.0,
        "config": {"popSize": 8, "generations": 2, "cxRate": .7, "mutRate": .08},
    }
    preview = OptimizationApplicationService(repository).preview(document["project"]["id"], payload)
    assert context["execution_profile"] == preview["execution_profile"] == "REFERENCE_DEMO"
    assert preview["ready"] is True
    with pytest.raises(ValueError, match="require execution_profile REFERENCE_DEMO"):
        OptimizationApplicationService(repository).preview(
            document["project"]["id"], {**payload, "execution_profile": "VERIFIED_INSTITUTIONAL"})


@pytest.mark.browser
def test_reference_demo_readiness_browser(reference_project):
    repository, _ = reference_project
    application = Flask("reference-demo-readiness")
    application.config["TESTING"] = True
    register_project_api(application, repository)
    server, thread = serve(application)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.goto(
                f"http://127.0.0.1:{server.server_port}/projects"
                "#project=v1-reference-demo&section=readiness"
            )
            expect(page.locator("#readiness-verdict")).to_have_text("READY_WITH_WARNINGS", timeout=120000)
            expect(page.locator("#readiness")).to_contain_text("CONNECTED / WARNING")
            expect(page.locator("#scenario-readiness")).to_contain_text("S1")
            expect(page.locator("#scenario-readiness")).to_contain_text("READY_WITH_WARNINGS")
            expect(page.locator('#analysis-form [name="execution_profile"]')).to_have_value("REFERENCE_DEMO")
            assert "VERIFIED_INSTITUTIONAL requires" not in page.locator("body").inner_text()
            assert not page_errors
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
