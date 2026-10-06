from __future__ import annotations

from pathlib import Path

import pytest
from flask import send_from_directory
from playwright.sync_api import expect, sync_playwright

from test_unified_decision_demo import PACKAGE, client_for
from test_unified_decision_demo_browser import serve
from test_unified_v1_project_provider_browser import _serve_v1


ROOT = Path(__file__).resolve().parents[1]
FULL_PACKAGE = Path(r"C:\Users\LENOVO\Desktop\CropKDS_21_Dosya_Tam_Gorsel_Demo_Paketi")
EVIDENCE = ROOT / "docs" / "project_v1_exact_ui_cleanboot_final" / "evidence"


def _assert_hit_target(page, locator):
    expect(locator).to_be_visible()
    expect(locator).to_be_enabled()
    locator.scroll_into_view_if_needed()
    box = locator.bounding_box()
    assert box and box["width"] > 0 and box["height"] > 0
    hit = page.evaluate(
        """({x,y,node}) => {
          const top=document.elementFromPoint(x,y);
          return {hit:top?.id||top?.className||top?.tagName,
                  owns:top===node||node.contains(top),
                  pointer:getComputedStyle(node).pointerEvents,
                  disabled:!!node.disabled,
                  ariaDisabled:node.getAttribute('aria-disabled')};
        }""",
        {"x": box["x"] + box["width"] / 2, "y": box["y"] + box["height"] / 2,
         "node": locator.element_handle()},
    )
    assert hit["owns"], hit
    assert hit["pointer"] != "none" and not hit["disabled"]
    assert hit["ariaDisabled"] not in {"true", True}


def _click_select(page, selector: str, value: str):
    locator = page.locator(selector)
    _assert_hit_target(page, locator)
    locator.click()
    locator.select_option(value)
    expect(locator).to_have_value(value)


def _serve_full_v1(application):
    @application.get("/data/<path:filename>")
    def v1_reference_data(filename):
        return send_from_directory(ROOT / "data", filename)

    _serve_v1(application)


@pytest.mark.browser
def test_full_native_project_workspace_clickability_and_e2e(tmp_path):
    application, _, repository = client_for(tmp_path)
    _serve_full_v1(application)
    server, thread = serve(application)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.route("**/api/parcels", lambda route: route.fulfill(json={
                "parcels": [{"id": f"P{index}", "map_only": False,
                             "area_da": 1, "current_crop": "ARPA"}
                            for index in range(1, 180)]
            }))
            requests, errors, network, console_messages = [], [], [], []
            page.on("request", lambda request: requests.append(request.url))
            page.on("response", lambda response: network.append({
                "method": response.request.method, "url": response.url,
                "status": response.status,
            }) if "/api/v2/projects/" in response.url else None)
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("console", lambda message: console_messages.append(message.text))

            page.goto(f"http://127.0.0.1:{server.server_port}/projects")
            page.locator("details.form-drawer").first.locator("summary").click()
            form = page.locator("#create-project")
            form.locator('[name="id"]').fill("kds-final-provider-e2e-2025")
            form.locator('[name="name"]').fill("KDS Kurumsal Veri E2E Demo")
            form.locator('[name="planning_year"]').fill("2025")
            form.locator('[name="province_or_region"]').fill("Synthetic Region")
            form.locator('[name="data_source_notes"]').select_option(
                label="Sentetik genel proje"
            )
            expect(form.locator('[name="data_source_notes"]')).to_have_value(
                "synthetic_test_fixture"
            )
            form.locator("button").click()
            files = [str(path) for path in sorted(FULL_PACKAGE.iterdir())
                     if path.suffix.lower() in {".csv", ".xlsx", ".geojson"}]
            assert len(files) == 21
            page.locator('#bulk-upload-form input[type="file"]').set_input_files(files)
            page.locator('#bulk-upload-form button[type="submit"]').click()
            expect(page.locator("#bulk-import-body tr")).to_have_count(21, timeout=120000)
            assert page.locator("#bulk-import-body tr", has_text="AUTO_MATCHED").count() == 21
            page.locator("#bulk-confirm").click()
            expect(page.locator("#readiness-verdict")).to_contain_text("VERIFIED READY", timeout=180000)
            page.locator("#open-v1-project").click()
            page.wait_for_function("window.__V1_PROJECT_PROVIDER__?.context?.unit_count === 24")
            page.evaluate("setAuthenticatedUser(getAuthUserByUsername('kurum.nigde'), {focus:false})")
            expect(page.locator("#v1-provider-authority")).to_have_text("SYNTHETIC / NOT_OFFICIAL")
            expect(page.locator("#v1-provider-authority")).not_to_contain_text("VERIFIED_INSTITUTIONAL")
            page.evaluate("""() => {
              map.invalidateSize();
              const geometryLayers=Object.values(map._layers||{}).filter(
                layer => typeof layer.getBounds === 'function'
              );
              if(geometryLayers.length){
                const bounds=L.featureGroup(geometryLayers).getBounds();
                if(bounds?.isValid?.()) map.fitBounds(bounds.pad(.15), {animate:false});
              }
              window.dispatchEvent(new Event('resize'));
            }""")
            page.wait_for_timeout(300)

            expect(page.locator("#parcelSelect option")).to_have_count(24)
            expect(page.locator(".leaflet-interactive")).to_have_count(24, timeout=30000)
            # Fix milestone deliberately replaces the obsolete PROJECT_DATA-only
            # tooltip class with the shared native V1 badge DOM.
            expect(page.locator(".parcel-badge")).to_have_count(24, timeout=30000)
            expect(page.locator(".parcel-badge .dot")).to_have_count(24)
            expect(page.locator(".parcel-badge .hint")).to_have_count(24)
            expect(page.locator("#roleInfoBanner")).to_contain_text("24 analiz birimi")
            expect(page.locator("#setupGroup .card-title").first).to_have_text("Analiz birimi seç")
            expect(page.locator(".map-card .card-title")).to_have_text("Analiz Birimleri Haritası")
            visible_text = page.locator("body").inner_text()
            for stale in ("Parsel seç", "Parsel Haritası", "Seçili parsel", "Parsel Bazlı Özet"):
                assert stale not in visible_text
            assert "P1" not in page.locator("#parcelSelect").inner_text()
            page.screenshot(path=str(EVIDENCE / "project_data_before_run_1366x900.png"), full_page=True)

            provider_button = page.locator("#v1-provider-toggle")
            _assert_hit_target(page, provider_button)
            provider_button.click()
            expect(page.locator("#v1-provider-shell")).to_have_attribute("aria-hidden", "false")
            expect(page.locator("#v1-provider-scrim")).to_be_visible()
            close = page.locator("#v1-provider-close")
            _assert_hit_target(page, close)
            close.click()
            expect(page.locator("#v1-provider-scrim")).to_be_hidden()
            expect(page.locator("#v1-provider-shell")).to_have_attribute("aria-hidden", "true")
            expect(provider_button).to_be_focused()

            _click_select(page, "#parcelSelect", "KDS-005")
            expect(page.locator("#parcelSummaryTitle")).to_contain_text("KDS-005")
            for unit_id in ("KDS-001", "KDS-008", "KDS-016", "KDS-024"):
                _click_select(page, "#parcelSelect", unit_id)
                expect(page.locator("#parcelSummaryTitle")).to_contain_text(unit_id)
                expect(page.locator("#mWaterCurrent")).not_to_contain_text("sağlanmadı")
                expect(page.locator("#mProfitCurrent")).not_to_contain_text("sağlanmadı")
                expect(page.locator("#mEffCurrent")).not_to_contain_text("sağlanmadı")
            _click_select(page, "#parcelSelect", "KDS-005")
            page.evaluate("""() => {
              const layers=Object.values(map._layers||{}).filter(x=>x.getBounds);
              const bounds=L.featureGroup(layers).getBounds();
              if(bounds?.isValid?.()) map.fitBounds(bounds.pad(.15), {animate:false});
            }""")
            page.wait_for_timeout(300)
            polygon = page.locator(".leaflet-interactive").nth(8)
            _assert_hit_target(page, polygon)
            polygon.click()
            expect(page.locator("#parcelSelect")).to_have_value("KDS-009")

            page.locator("#v1-provider-seed").fill("123")
            run_matrix = [
                ("s1", "ga", "su_tasarruf"),
                ("s1", "aco", "maks_kar"),
                ("s1", "abc", "su_etkin"),
            ]
            if page.evaluate("window.__V1_PROJECT_PROVIDER__.context.capabilities.scenarios.S2.ready"):
                run_matrix.append(("s2", "ga", "su_tasarruf"))
            for scenario, algorithm, objective in run_matrix:
                _click_select(page, "#seasonSourceSel", scenario)
                _click_select(page, "#algoSelect", algorithm)
                radio = page.locator(f'input[name="scenario"][value="{objective}"]')
                radio.click()
                expect(radio).to_be_checked()
                preview = page.locator("#v1-provider-preview")
                preview.click()
                expect(page.locator("#v1-provider-preview-state")).to_contain_text("PINNED", timeout=120000)
                run = page.locator("#runOptBtn")
                run.click()
                expect(page.locator("#algoStatus")).to_contain_text("Tamamlandı", timeout=240000)
            expect(page.locator("#v1-provider-scrim")).to_be_hidden()
            expect(page.locator("#v1-provider-shell")).to_have_attribute("aria-hidden", "true")
            expect(page.locator("#tblRecommended tbody")).not_to_contain_text(
                "HESAPLANMADI", timeout=30000
            )
            expect(page.locator("#tblRecommendedFooter")).to_contain_text("water_saving")
            expect(page.locator("#businessMetricsBox")).to_contain_text("Backend birim net kârı")
            for metric_id in ("#bWaterCurrent", "#bProfitCurrent", "#bEffCurrent"):
                expect(page.locator(metric_id)).not_to_contain_text("SAĞLANMADI")
            expect(page.locator("#v1-project-result")).to_be_hidden()
            assert not page.locator("#v1-project-result").inner_text().strip()
            assert page.locator("#v1-native-project-results").count() == 0
            expect(page.locator("#activeFilesBadges")).to_contain_text("SYNTHETIC / NOT_OFFICIAL")
            expect(page.locator("#basinSummaryNote")).to_contain_text("optimizer su")
            expect(page.locator("#basinSummaryNote")).to_contain_text("otoritatif su")
            expect(page.locator("#globalBudgetStatus")).to_contain_text("PASS")
            expect(page.locator("#globalBudgetBadge")).not_to_have_text("Toplam planlama su bütçesi: -")
            expect(page.locator("#deliveryBox")).to_contain_text("Backend aylık talep")
            expect(page.locator("#deliveryBox")).to_contain_text("SYNTHETIC_INSTITUTIONAL_TEST_PROJECT")
            expect(page.locator("#objectiveCompareMatrix")).to_contain_text("HHI")
            expect(page.locator("#parcelSummaryTitle")).to_contain_text("KDS-009")
            expect(page.locator("#tblCurrentFooter")).to_contain_text("9 da")
            expect(page.locator("#metricsTitle")).to_have_text("Analiz Birimi Karar Özeti (KDS-009)")
            expect(page.locator("#runMetaBox")).to_contain_text("revision 21")
            expect(page.locator("#riskSeparationBox")).to_contain_text("yıllık bütçe: PASS")
            expect(page.locator("#decisionRationale")).to_contain_text("Akkaya fallback kullanılmadı")
            expect(page.locator("#tblOfficialScenario")).to_contain_text("Ekim Alanı")
            polygon = page.locator(".leaflet-interactive").nth(8)
            polygon.click()
            native_popup = page.locator(".leaflet-popup-content")
            expect(native_popup).to_contain_text("KDS-009")
            expect(native_popup).to_contain_text("Alan")
            expect(native_popup).to_contain_text("9.0 da")
            expect(native_popup).to_contain_text("Optimize su")
            expect(native_popup).to_contain_text("Otorite")
            assert page.evaluate("""() => {
              const chart=Chart.getChart(document.getElementById('waterChart'));
              return chart.data.datasets[0].data.length===4 && chart.data.datasets[0].data.every(Number.isFinite);
            }""")
            assert page.evaluate("""() => {
              const chart=Chart.getChart(document.getElementById('profitChart'));
              return chart.data.datasets[0].data.length===1 && Number.isFinite(chart.data.datasets[0].data[0]);
            }""")
            assert page.evaluate("""() => {
              const chart=Chart.getChart(document.getElementById('v1ProjectMonthlyChart'));
              return chart.data.labels.length===12 && chart.data.datasets.length===3;
            }""")
            page.locator("#tblRecommended").screenshot(path=str(EVIDENCE / "project_crop_recommendation.png"))
            page.locator("#map").screenshot(path=str(EVIDENCE / "project_map_unit.png"))
            page.locator("#deliveryBox").screenshot(path=str(EVIDENCE / "project_monthly_water.png"))
            for unit_id in ("KDS-001", "KDS-005", "KDS-009", "KDS-024"):
                _click_select(page, "#parcelSelect", unit_id)
                assert page.evaluate(
                    "unitId => window.__V1_PROJECT_PROVIDER__.openUnitPopup(unitId)",
                    unit_id,
                )
                expect(page.locator(".leaflet-popup-content", has_text=unit_id)).to_be_visible()
                expect(page.locator("#tblCurrent tbody td").nth(5)).not_to_contain_text("NOT PROVIDED")
                expect(page.locator("#tblCurrent tbody td").nth(7)).not_to_contain_text("NOT PROVIDED")
                expect(page.locator("#parcelSummaryTitle")).to_contain_text(unit_id)
            page.locator("#basinSummaryBlock").screenshot(path=str(EVIDENCE / "project_summary_1366x900.png"))
            page.locator("#tab-parcel").screenshot(path=str(EVIDENCE / "project_current_recommended_1366x900.png"))
            page.locator("#waterRiskSection").screenshot(path=str(EVIDENCE / "project_drought_1366x900.png"))

            expected_tabs = [
                "users", "parcel", "institution-communication", "drawing",
                "district", "official", "benchmark",
            ]
            project_tabs = page.evaluate("""() => Array.from(
              document.querySelectorAll('#analysisTables .tab')
            ).filter(node => node.offsetParent !== null).map(node => node.dataset.tab)""")
            assert project_tabs == expected_tabs
            assert page.locator('.tab[data-tab="drought"]').count() == 0
            expect(page.locator("#waterRiskSection")).to_be_visible()
            expect(page.locator("#waterRiskSection")).to_contain_text("SAĞLANMADI / NOT PROVIDED")
            assert page.evaluate("""() => {
              const ids=['explainBox','rotationBox','irrigationCompareBox',
                'businessMetricsBox','deliveryBox','irrigPlanBox'];
              const nodes=ids.map(id=>document.getElementById(id));
              return nodes.every(node=>node && node.offsetParent!==null) &&
                nodes.every((node,index)=>index===0 ||
                  nodes[index-1].compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING);
            }""")

            parcel_tab = page.locator('.tab[data-tab="parcel"]')
            _assert_hit_target(page, parcel_tab)
            parcel_tab.click()
            assert "active" in (parcel_tab.get_attribute("class") or "").split()
            page.evaluate("document.getElementById('analysisTables').scrollLeft=0")
            page.locator("#analysisTables").screenshot(path=str(EVIDENCE / "project_tabs_1366x900.png"))
            benchmark_tab = page.locator('.tab[data-tab="benchmark"]')
            _assert_hit_target(page, benchmark_tab)
            benchmark_tab.click()
            expect(page.locator("#tab-benchmark")).to_have_class("tab-panel active")
            expect(page.locator("#benchmarkResults")).to_contain_text("water_saving")
            expect(page.locator("#benchmarkResults")).to_contain_text("max_profit")
            expect(page.locator("#benchmarkResults")).to_contain_text("water_efficiency")
            page.locator("#tab-benchmark").screenshot(path=str(EVIDENCE / "project_algorithm_comparison_1366x900.png"))
            for tab_name in ("users", "drawing", "district", "official"):
                expect(page.locator(f'.tab[data-tab="{tab_name}"]')).to_be_visible()
            page.locator('.tab[data-tab="district"]').click()
            expect(page.locator("#districtSummaryTable")).to_contain_text("Test West")
            page.locator("#tab-district").screenshot(path=str(EVIDENCE / "project_district_1366x900.png"))
            page.locator('.tab[data-tab="official"]').click()
            expect(page.locator("#officialWaterNote")).to_contain_text("PROJECT DATA")
            expect(page.locator("#officialSummary")).to_contain_text("PROJECT DATA")
            page.locator("#tab-official").screenshot(path=str(EVIDENCE / "project_official_1366x900.png"))
            page.locator('.tab[data-tab="benchmark"]').click()
            accordion = page.locator("#parcelGroup > summary")
            _assert_hit_target(page, accordion)
            was_open = page.locator("#parcelGroup").get_attribute("open") is not None
            accordion.click()
            assert (page.locator("#parcelGroup").get_attribute("open") is not None) is not was_open
            _assert_hit_target(page, provider_button)
            provider_button.click()
            expect(page.locator("#v1-provider-shell")).to_have_attribute("aria-hidden", "false")
            page.locator("#v1-provider-close").click()

            run_id = page.evaluate("window.__V1_PROJECT_PROVIDER__.context.run.id")
            assert f"run_id={run_id}" in page.url
            assert not any("/api/parcels" in url or "/api/optimize" in url
                           for url in requests if "provider=PROJECT_DATA" in page.url)
            project_errors = list(errors)
            assert not project_errors
            assert page.evaluate(
                "window.__V1_PROJECT_PROVIDER__.blockedReferencePaths"
            ) == []
            assert not [message for message in console_messages
                        if "reference endpoint engellendi" in message]
            reference_tokens = (
                "/api/parcels", "/api/optimize", "/api/meta",
                "/api/geojson_files", "/api/geojson_bundle",
                "/api/water_allocation_logic", "/data/",
            )
            assert not [url for url in requests
                        if any(token in url for token in reference_tokens)]
            preview_calls = [row for row in network if row["method"] == "POST" and row["url"].endswith("/analysis-preview") and row["status"] == 200]
            execution_calls = [row for row in network if row["method"] == "POST" and row["url"].endswith("/analyses") and row["status"] == 201]
            assert len(preview_calls) == len(run_matrix)
            assert len(execution_calls) == len(run_matrix)
            assert len(repository.get("kds-final-provider-e2e-2025")["runs"]) == len(run_matrix)

            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            assert page.evaluate("document.querySelector('#map').getBoundingClientRect().height >= 460")
            assert page.evaluate("document.querySelector('#map').getBoundingClientRect().height <= 620")
            assert page.evaluate("document.querySelector('#v1-native-project-results') === null")
            assert page.evaluate("""() => {
              const top=document.querySelector('.right-top');
              const next=top?.nextElementSibling;
              return !next || !next.matches('[class*=native-results],[id*=project-results]');
            }""")
            page.locator('.tab[data-tab="parcel"]').click()
            expect(page.locator("#tab-parcel")).to_have_class("tab-panel active")
            page.evaluate("map.closePopup()")
            page.screenshot(path=str(EVIDENCE / "project_data_after_run_1366x900.png"), full_page=True)
            project_page_height = page.evaluate("document.documentElement.scrollHeight")
            for width, height in ((1280, 720), (1366, 768), (1536, 864), (1920, 1080), (390, 844)):
                page.set_viewport_size({"width": width, "height": height})
                page.evaluate("map.invalidateSize(); window.dispatchEvent(new Event('resize'))")
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                # The native V1 top row owns map height.  A former PROJECT_DATA-only
                # 420/620 px cap is intentionally absent; require a usable finite map
                # while the dedicated parity test compares native row geometry.
                assert page.evaluate("""() => {
                  const rect=document.querySelector('#map').getBoundingClientRect();
                  return Number.isFinite(rect.height) && rect.height >= 360;
                }""")
                if (width, height) == (1920, 1080):
                    page.screenshot(path=str(EVIDENCE / "project_data_after_run_1920x1080.png"), full_page=True)
                if (width, height) == (390, 844):
                    page.screenshot(path=str(EVIDENCE / "project_data_after_run_390x844.png"), full_page=True)
            page.set_viewport_size({"width": 1366, "height": 900})
            for zoom in ("80%", "100%", "125%"):
                page.evaluate("value => { document.body.style.zoom=value; map.invalidateSize(); }", zoom)
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.evaluate("document.body.style.zoom='100%'; map.invalidateSize()")
            page.set_viewport_size({"width": 1366, "height": 900})

            page.reload()
            page.wait_for_function("window.__V1_PROJECT_PROVIDER__?.context?.run?.id")
            page.evaluate("setAuthenticatedUser(getAuthUserByUsername('kurum.nigde'), {focus:false})")
            expect(page.locator("#tblRecommendedFooter")).to_contain_text("water_saving")
            expect(page.locator("#buildMetaBox")).to_contain_text(run_id)
            page.locator("#buildMetaBox summary").click()
            expect(page.locator("#buildMetaBox pre")).to_contain_text("selection_hash")
            page.locator("#activeFilesBox").screenshot(path=str(EVIDENCE / "project_provenance.png"))

            page.locator("#v1-provider-toggle").click()
            page.locator("#v1-reference-provider").click()
            page.wait_for_function("window.__V1_PROJECT_PROVIDER__?.provider === 'AKKAYA_REFERENCE'")
            page.evaluate("setAuthenticatedUser(getAuthUserByUsername('kurum.nigde'), {focus:false})")
            expect(page.locator("#roleInfoBanner")).to_contain_text("179 parsel", timeout=30000)
            expect(page.locator("#roleInfoBanner")).not_to_contain_text("analiz birimi")
            page.locator('.tab[data-tab="parcel"]').click()
            expect(page.locator("#tab-parcel")).to_have_class("tab-panel active")
            page.evaluate("map.closePopup()")
            page.screenshot(path=str(EVIDENCE / "akkaya_reference_restored.png"), full_page=True)
            reference_page_height = page.evaluate("document.documentElement.scrollHeight")
            assert abs(project_page_height - reference_page_height) < 600
            page.wait_for_load_state("networkidle", timeout=120000)
            page.locator("#map").screenshot(path=str(EVIDENCE / "reference_map_1366x900.png"))
            page.locator("#parcelSelect").select_option("P1")
            page.wait_for_timeout(500)
            reference_polygon = page.locator(".leaflet-interactive").first
            expect(reference_polygon).to_be_visible(timeout=30000)
            reference_popup = page.locator(".leaflet-popup-content").last
            expect(reference_popup).to_be_visible(timeout=30000)
            selected_reference_id = page.locator("#parcelSelect").input_value()
            expect(reference_popup).to_contain_text(selected_reference_id)
            page.locator("#map").screenshot(path=str(EVIDENCE / "reference_map_unit.png"))
            page.locator("#parcelSummaryBlock").screenshot(path=str(EVIDENCE / "reference_summary_1366x900.png"))
            page.locator("#waterRiskSection").screenshot(path=str(EVIDENCE / "reference_drought_1366x900.png"))
            page.locator('.tab[data-tab="parcel"]').click()
            reference_tabs = page.evaluate("""() => Array.from(
              document.querySelectorAll('#analysisTables .tab')
            ).filter(node => node.offsetParent !== null).map(node => node.dataset.tab)""")
            assert reference_tabs == expected_tabs == project_tabs
            assert page.locator('.tab[data-tab="drought"]').count() == 0
            page.evaluate("document.getElementById('analysisTables').scrollLeft=0")
            page.locator("#analysisTables").screenshot(path=str(EVIDENCE / "reference_tabs_1366x900.png"))
            page.locator("#tab-parcel").screenshot(path=str(EVIDENCE / "reference_current_recommended_1366x900.png"))
            page.locator("#deliveryBox").screenshot(path=str(EVIDENCE / "reference_monthly_water_context_1366x900.png"))
            page.locator('.tab[data-tab="district"]').click()
            expect(page.locator("#districtSummaryTable")).not_to_contain_text("Test West")
            page.locator("#tab-district").screenshot(path=str(EVIDENCE / "reference_district_1366x900.png"))
            page.locator('.tab[data-tab="official"]').click()
            expect(page.locator("#officialSummary")).not_to_contain_text("PROJECT DATA")
            page.locator("#tab-official").screenshot(path=str(EVIDENCE / "reference_official_1366x900.png"))
            page.locator('.tab[data-tab="benchmark"]').click()
            page.locator("#tab-benchmark").screenshot(path=str(EVIDENCE / "reference_algorithm_comparison_1366x900.png"))
            page.locator("#activeFilesBox").screenshot(path=str(EVIDENCE / "reference_provenance_context_1366x900.png"))

            page.locator("#v1-provider-toggle").click()
            project_select = page.locator("#v1-project-provider-select")
            _assert_hit_target(page, project_select)
            project_select.select_option("kds-final-provider-e2e-2025")
            page.wait_for_function("window.__V1_PROJECT_PROVIDER__?.context?.unit_count === 24")
            page.evaluate("setAuthenticatedUser(getAuthUserByUsername('kurum.nigde'), {focus:false})")
            expect(page.locator("#roleInfoBanner")).to_contain_text("24 analiz birimi")
            expect(page.locator("#parcelSelect option")).to_have_count(24)
            expect(page.locator("#v1-project-result")).to_be_hidden()
            assert "run_id=" not in page.url
            assert run_id not in page.locator("#activeFilesBox").inner_text()
            assert not [error for error in errors if error not in project_errors]
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.mark.browser
def test_real_institutional_ui_project_rejects_synthetic_full_package(tmp_path):
    application, client, repository = client_for(tmp_path)
    _serve_v1(application)
    server, thread = serve(application)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.goto(f"http://127.0.0.1:{server.server_port}/projects")
            page.locator("details.form-drawer").first.locator("summary").click()
            form = page.locator("#create-project")
            form.locator('[name="id"]').fill("real-institutional-negative")
            form.locator('[name="name"]').fill("Gerçek Kurumsal Negatif Kontrol")
            form.locator('[name="planning_year"]').fill("2025")
            form.locator('[name="province_or_region"]').fill("Niğde")
            form.locator('[name="data_source_notes"]').select_option(
                label="Kurum tarafından sağlanan veri"
            )
            expect(form.locator('[name="data_source_notes"]')).to_have_value("user_provided")
            form.locator("button").click()

            files = [str(path) for path in sorted(FULL_PACKAGE.iterdir())
                     if path.suffix.lower() in {".csv", ".xlsx", ".geojson"}]
            assert len(files) == 21
            page.locator('#bulk-upload-form input[type="file"]').set_input_files(files)
            page.locator('#bulk-upload-form button[type="submit"]').click()
            expect(page.locator("#bulk-import-body tr")).to_have_count(21, timeout=120000)
            assert page.locator("#bulk-import-body tr", has_text="AUTO_MATCHED").count() == 21
            page.locator("#bulk-confirm").click()
            expect(page.locator("#project-status-badges")).to_contain_text(
                "Revizyon 21", timeout=180000
            )
            expect(page.locator("#readiness-verdict")).to_contain_text("BLOCKED")
            expect(page.locator("#blocking-summary")).to_contain_text(
                "is synthetic and cannot support a real institutional run"
            )
            browser.close()

        document = repository.get("real-institutional-negative")
        assert document["metadata"].get("synthetic_institutional_test") is None
        assert document["metadata"].get("not_official") is None
        preview = client.post(
            "/api/v2/projects/real-institutional-negative/analysis-preview",
            json={
                "execution_profile": "VERIFIED_INSTITUTIONAL",
                "scenario": "S1", "algorithm": "GA", "seed": 123,
                "objective": "water_saving", "water_budget_ratio": 1,
                "config": {"popSize": 12, "generations": 10,
                           "cxRate": .7, "mutRate": .08},
            },
        )
        assert preview.status_code == 200
        assert preview.json["ready"] is False
        assert preview.json["synthetic"] is False
        assert "is synthetic and cannot support a real institutional run" in " ".join(
            preview.json["blocking_reasons"]
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_runtime_keeps_results_native_and_drawer_non_blocking():
    provider = (ROOT / "kds" / "ui" / "static" / "v1-provider.js").read_text(encoding="utf-8")
    css = (ROOT / "kds" / "ui" / "static" / "v1-provider.css").read_text(encoding="utf-8")
    assert "renderNativeRun(run)" in provider
    assert "renderNativeUnit(unit)" in provider
    assert "sink.replaceChildren()" in provider
    for legacy_sink in (
        "v1-project-result-summary", "v1-project-water-accounting",
        "v1-project-annual-budget", "v1-project-warnings",
        "v1-project-monthly", "v1-project-crops", "v1-project-units",
        "v1-project-provenance",
    ):
        assert legacy_sink not in provider
    assert "v1-native-project-results" not in provider
    assert "ensureNativeResultSurface" not in provider
    assert ".v1-native-results" not in css
    for native_target in (
        "basinSummaryNote", "globalBudgetStatus", "deliveryBox",
        "objectiveCompareMatrix", "activeFilesBadges", "buildMetaBox",
        "activeFilesNote", "tblCurrent", "tblRecommended",
    ):
        assert native_target in provider
    assert "new Set([...(result.monthly_supply_validation?.violating_months||[])" in provider
    assert "Analiz Birimleri Haritası" in provider
    assert "setDrawer(true);\n    neutralizeReferenceSurface" not in provider
    assert ".v1-provider-scrim[hidden]{display:none!important;pointer-events:none!important}" in css
