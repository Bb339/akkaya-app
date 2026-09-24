"""Institutional Ministry UI Phase 2 presentation and metadata contracts."""
from copy import deepcopy
from pathlib import Path

from flask import Flask

from kds.api import register_project_api
from kds.application.project_overview import data_catalog
from kds.data.project_store import FileProjectStore
from test_analysis_workflow import example

ROOT = Path(__file__).parents[1]
HTML = (ROOT / "kds/ui/templates/projects.html").read_text(encoding="utf8")
CSS = (ROOT / "kds/ui/static/projects.css").read_text(encoding="utf8")
JS = "\n".join(path.read_text(encoding="utf8") for path in (ROOT / "kds/ui/static").glob("*.js"))


def test_01_reference_and_verified_profiles_are_visually_explicit():
    assert "REFERENCE MODEL / DEMO DATA" in HTML
    assert "VERIFIED INSTITUTIONAL" in HTML
    assert "RESMÎ SU TAHSİSİ VEYA SAHA DOĞRULAMASI DEĞİLDİR" in HTML
    assert "global-mode-badge" in HTML and "mode-warning" in HTML


def test_02_project_context_exposes_institutional_identity_fields():
    for label in ("Kurum / kuruluş", "Planlama yılı", "İl / bölge", "Coğrafi kapsam / havza"):
        assert label in HTML
    assert "hero-project-name" in HTML and "project-status-badges" in HTML


def test_03_data_center_separates_domain_status_axes():
    assert "Kurumsal veri merkezi" in HTML
    for axis in ("seçili", "bütünlük", "geçerli", "motor"):
        assert axis in (ROOT / "kds/ui/static/readiness.js").read_text(encoding="utf8")


def test_04_import_requires_mapping_preview_and_explicit_confirmation():
    stepper = HTML[HTML.index('<ol class="stepper"'):HTML.index('</ol>', HTML.index('<ol class="stepper"'))]
    positions = [stepper.index(value) for value in ("Dosya yükle", "Sütun eşleştir", "Doğrula", "Önizle", "Onayla", "Aktif sürüm")]
    assert positions == sorted(positions)
    assert 'id="acknowledge"' in HTML and 'id="confirm-import"' in HTML
    assert "confirm:true" in JS


def test_05_templates_are_downloadable_and_marked_non_official(tmp_path):
    repository = FileProjectStore(tmp_path / "projects")
    app = Flask("phase2-templates"); app.config["TESTING"] = True
    register_project_api(app, repository)
    response = app.test_client().get("/projects/templates/analysis_units_template.xlsx")
    assert response.status_code == 200
    assert response.headers["Content-Disposition"].startswith("attachment")
    assert "ÖRNEK / ŞABLON VERİ — RESMÎ VERİ DEĞİLDİR" in HTML
    assert app.test_client().get("/projects/templates/../secret.txt").status_code == 404


def test_06_readiness_has_verdict_blockers_and_scenario_detail():
    for token in ('id="readiness-verdict"', 'id="blocking-summary"', 'id="scenario-readiness"'):
        assert token in HTML
    assert "blocking_reasons" in JS and "VERIFIED_INSTITUTIONAL" in JS


def test_07_verified_run_is_gated_by_preview_evidence():
    analysis = (ROOT / "kds/ui/static/analysis.js").read_text(encoding="utf8")
    assert "preview_token" in analysis and "preview_revision" in analysis and "selection_hash" in analysis
    assert "verified&&!previewEvidence?.ready" in analysis
    assert 'id="run-button" class="button primary" disabled' in HTML


def test_08_stale_preview_has_a_dedicated_fail_closed_state():
    assert 'id="stale-preview-alert"' in HTML
    assert "STALE PREVIEW" in JS and "/preview|revision|selection/i" in JS


def test_09_execution_and_infeasible_states_are_explicit():
    for state in ("PREVIEWING", "RUNNING", "COMPLETED", "FAILED"):
        assert state in JS
    assert "DIAGNOSTIC / UYGULANABİLİR PLAN DEĞİL" in HTML


def test_10_canonical_water_measures_are_not_collapsed():
    results = (ROOT / "kds/ui/static/results.js").read_text(encoding="utf8")
    for field in ("optimizer_water_m3", "verified_profile_water_m3", "planning_year_profile_water_m3", "authoritative_water_m3"):
        assert field in results
    assert "efficiency_tl_per_m3_denominator" in results


def test_11_monthly_supply_and_delivery_are_labeled_post_run():
    assert "Post-run doğrulama; optimizer kısıtı olarak sunulmaz" in HTML
    results = (ROOT / "kds/ui/static/results.js").read_text(encoding="utf8")
    assert "monthly_supply_validation" in results and "monthly_delivery_validation" in results


def test_12_crop_concentration_uses_backend_hhi_and_shares():
    results = (ROOT / "kds/ui/static/results.js").read_text(encoding="utf8")
    assert "result.top_crops" in results and "result.hhi??result.HHI" in results
    assert "crop_shares" not in results  # UI must not recompute scientific shares.


def test_13_map_has_list_detail_fallback_and_bidirectional_selection():
    results = (ROOT / "kds/ui/static/results.js").read_text(encoding="utf8")
    assert "Harita kitaplığı çevrimdışı" in results
    assert "marker.on('click',()=>select(row,index))" in results
    assert "button.onclick=()=>select(row,index)" in results


def test_14_provenance_history_and_reanalysis_actions_are_present():
    for token in ('id="provenance-summary"', 'id="history"', 'id="reanalysis-banner"'):
        assert token in HTML
    assert "selection_hash" in JS and "engine_commit" in JS


def test_15_page_has_keyboard_accessibility_and_live_status():
    assert 'class="skip-link"' in HTML
    assert 'aria-live="polite"' in HTML
    assert ':focus' in CSS and "outline" in CSS
    assert "aria-label" in HTML


def test_16_layout_has_mobile_and_print_contracts():
    assert "@media(max-width:1000px)" in CSS
    assert "@media(max-width:650px)" in CSS
    assert "@media print" in CSS


def test_data_catalog_projects_metadata_without_scientific_records():
    document = example()
    dataset = {
        "dataset_id": "annual-v1", "data_type": "annual_water_supply", "version": "1",
        "status": "active", "authority_class": "OFFICIAL_ALLOCATION", "confirmed_at": "2026-01-01T00:00:00Z",
        "records": [{"planning_year": 2025, "geographic_scope": "project", "amount_m3": 123.0}],
    }
    document["water_data"] = {"datasets": {"annual-v1": deepcopy(dataset)}, "active": {"annual_water_supply": "annual-v1"}}
    projected = data_catalog(document)
    assert projected["project_id"] == document["project"]["id"]
    assert projected["datasets"][0]["selected"] is True
    assert projected["datasets"][0]["record_count"] == 1
    assert "records" not in projected["datasets"][0]
    assert "amount_m3" not in str(projected)


def test_data_catalog_endpoint_is_project_scoped(tmp_path):
    repository = FileProjectStore(tmp_path / "projects"); repository.create(example())
    app = Flask("phase2-catalog"); app.config["TESTING"] = True
    register_project_api(app, repository)
    response = app.test_client().get("/api/v2/projects/sample-a/data-catalog")
    assert response.status_code == 200
    assert response.json["project_id"] == "sample-a"
    assert set(response.json) == {"project_id", "data_revision", "analysis_state", "datasets", "imports", "project_inputs"}
