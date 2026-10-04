from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from test_unified_decision_demo import PACKAGE, client_for
from test_unified_decision_demo_browser import serve
from test_unified_v1_project_provider_browser import _serve_v1


ROOT = Path(__file__).resolve().parents[1]
FULL_PACKAGE = Path(r"C:\Users\LENOVO\Desktop\CropKDS_21_Dosya_Tam_Gorsel_Demo_Paketi")
EVIDENCE = ROOT / "docs" / "v1_project_provider_full_parity_final"


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


@pytest.mark.browser
def test_full_native_project_workspace_clickability_and_e2e(tmp_path):
    application, _, repository = client_for(tmp_path)
    _serve_v1(application)
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
            requests, errors, network = [], [], []
            page.on("request", lambda request: requests.append(request.url))
            page.on("response", lambda response: network.append({
                "method": response.request.method, "url": response.url,
                "status": response.status,
            }) if "/api/v2/projects/" in response.url else None)
            page.on("pageerror", lambda error: errors.append(str(error)))

            page.goto(f"http://127.0.0.1:{server.server_port}/projects")
            page.locator("details.form-drawer").first.locator("summary").click()
            form = page.locator("#create-project")
            form.locator('[name="id"]').fill("kds-final-provider-e2e-2025")
            form.locator('[name="name"]').fill("KDS Kurumsal Veri E2E Demo")
            form.locator('[name="planning_year"]').fill("2025")
            form.locator('[name="province_or_region"]').fill("Synthetic Region")
            form.locator('[name="data_source_notes"]').select_option(
                "synthetic not_official institutional integration fixture"
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

            for algorithm in ("ga", "aco", "abc"):
                _click_select(page, "#algoSelect", algorithm)
                for objective in ("su_tasarruf", "maks_kar", "su_etkin"):
                    radio = page.locator(f'input[name="scenario"][value="{objective}"]')
                    _assert_hit_target(page, radio)
                    radio.click()
                    expect(radio).to_be_checked()
                    page.locator("#v1-provider-preview").click()
                    expect(page.locator("#v1-provider-preview-state")).to_contain_text(
                        "PINNED", timeout=120000
                    )
            _click_select(page, "#seasonSourceSel", "s1")
            _click_select(page, "#algoSelect", "ga")
            page.locator('input[name="scenario"][value="su_tasarruf"]').click()
            page.locator("#v1-provider-seed").fill("123")

            preview = page.locator("#v1-provider-preview")
            _assert_hit_target(page, preview)
            preview.click()
            expect(page.locator("#v1-provider-preview-state")).to_contain_text("PINNED", timeout=120000)
            run = page.locator("#runOptBtn")
            _assert_hit_target(page, run)
            run.click()
            expect(page.locator("#algoStatus")).to_contain_text("Tamamlandı", timeout=240000)
            expect(page.locator("#v1-provider-scrim")).to_be_hidden()
            expect(page.locator("#v1-provider-shell")).to_have_attribute("aria-hidden", "true")
            expect(page.locator("#tblRecommended tbody")).not_to_contain_text(
                "HESAPLANMADI", timeout=30000
            )
            expect(page.locator("#tblRecommendedFooter")).to_contain_text("water_saving")
            expect(page.locator("#businessMetricsBox")).to_contain_text("Backend birim net kârı")
            expect(page.locator("#v1-project-result")).to_be_hidden()
            assert not page.locator("#v1-project-result").inner_text().strip()
            expect(page.locator("#v1-native-run-summary")).to_contain_text("SYNTHETIC / NOT_OFFICIAL")
            expect(page.locator("#v1-native-water-accounting")).to_contain_text("Optimizer su")
            expect(page.locator("#v1-native-water-accounting")).to_contain_text("Doğrulanmış / otoritatif su")
            expect(page.locator("#v1-native-annual-budget")).to_contain_text("Yıllık su bütçesi")
            expect(page.locator("#globalBudgetStatus")).to_contain_text("PASS")
            expect(page.locator("#globalBudgetBadge")).not_to_have_text("Toplam planlama su bütçesi: -")
            expect(page.locator("#v1-native-monthly")).to_contain_text("Aylık su doğrulaması")
            expect(page.locator("#v1-native-warnings")).to_contain_text("Analiz uyarıları")
            expect(page.locator("#v1-native-crops")).to_contain_text("HHI")
            expect(page.locator("#v1-native-unit-result")).to_contain_text("KDS-009")
            expect(page.locator("#v1-native-unit-result")).to_contain_text("9")
            expect(page.locator("#v1-native-run-summary")).to_contain_text("KDS Kurumsal Veri E2E Demo")
            expect(page.locator("#runMetaBox")).to_contain_text("revision 21")
            expect(page.locator("#riskSeparationBox")).to_contain_text("yıllık bütçe: PASS")
            expect(page.locator("#decisionRationale")).to_contain_text("Akkaya fallback kullanılmadı")
            expect(page.locator("#v1-native-crops")).to_contain_text("Alan (da)")
            polygon = page.locator(".leaflet-interactive").nth(8)
            polygon.click()
            expect(page.locator(".leaflet-popup-content")).to_contain_text("KDS-009")
            expect(page.locator(".leaflet-popup-content")).to_contain_text("Alan: 9 da")
            expect(page.locator(".leaflet-popup-content")).to_contain_text("Optimize su:")
            expect(page.locator(".leaflet-popup-content")).to_contain_text("Otorite:")
            monthly_violation = page.locator("#v1-native-monthly .v1-provider-explanation").inner_text()
            values = [value.strip() for value in monthly_violation.split(":", 1)[-1].split(",")]
            assert len(values) == len(set(values))
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
            page.locator("#v1-native-crops").screenshot(path=str(EVIDENCE / "project_crop_recommendation.png"))
            page.locator("#map").screenshot(path=str(EVIDENCE / "project_map_unit.png"))
            page.locator("#v1-native-monthly").screenshot(path=str(EVIDENCE / "project_monthly_water.png"))

            parcel_tab = page.locator('.tab[data-tab="parcel"]')
            _assert_hit_target(page, parcel_tab)
            parcel_tab.click()
            assert "active" in (parcel_tab.get_attribute("class") or "").split()
            benchmark_tab = page.locator('.tab[data-tab="benchmark"]')
            _assert_hit_target(page, benchmark_tab)
            benchmark_tab.click()
            expect(page.locator("#tab-benchmark")).to_have_class("tab-panel active")
            expect(page.locator("#benchmarkResults")).to_contain_text("water_saving")
            accordion = page.locator("#parcelGroup > summary")
            _assert_hit_target(page, accordion)
            was_open = page.locator("#parcelGroup").get_attribute("open") is not None
            accordion.click()
            assert (page.locator("#parcelGroup").get_attribute("open") is not None) is not was_open
            _assert_hit_target(page, provider_button)
            provider_button.click()
            expect(page.locator("#v1-provider-shell")).to_have_attribute("aria-hidden", "false")
            page.locator("#v1-provider-close").click()

            run_id = next(iter(repository.get("kds-final-provider-e2e-2025")["runs"]))
            assert f"run_id={run_id}" in page.url
            assert not any("/api/parcels" in url or "/api/optimize" in url
                           for url in requests if "provider=PROJECT_DATA" in page.url)
            project_errors = list(errors)
            assert not project_errors
            preview_calls = [row for row in network if row["method"] == "POST" and row["url"].endswith("/analysis-preview") and row["status"] == 200]
            execution_calls = [row for row in network if row["method"] == "POST" and row["url"].endswith("/analyses") and row["status"] == 201]
            assert len(preview_calls) >= 10 and len(execution_calls) == 1

            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.screenshot(path=str(EVIDENCE / "project_data_after_run_1366x900.png"), full_page=True)
            page.set_viewport_size({"width": 1920, "height": 1080})
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.screenshot(path=str(EVIDENCE / "project_data_after_run_1920x1080.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.screenshot(path=str(EVIDENCE / "project_data_after_run_390x844.png"), full_page=True)
            page.set_viewport_size({"width": 1366, "height": 900})

            page.reload()
            page.wait_for_function("window.__V1_PROJECT_PROVIDER__?.context?.run?.id")
            page.evaluate("setAuthenticatedUser(getAuthUserByUsername('kurum.nigde'), {focus:false})")
            expect(page.locator("#tblRecommendedFooter")).to_contain_text("water_saving")
            expect(page.locator("#v1-native-provenance")).to_contain_text(run_id)
            page.locator("#v1-native-provenance summary").click()
            expect(page.locator("#v1-native-provenance pre")).to_contain_text("selection_hash")
            page.locator("#v1-native-provenance").screenshot(path=str(EVIDENCE / "project_provenance.png"))

            page.locator("#v1-provider-toggle").click()
            page.locator("#v1-reference-provider").click()
            page.wait_for_function("window.__V1_PROJECT_PROVIDER__?.provider === 'AKKAYA_REFERENCE'")
            page.evaluate("setAuthenticatedUser(getAuthUserByUsername('kurum.nigde'), {focus:false})")
            expect(page.locator("#roleInfoBanner")).to_contain_text("179 parsel", timeout=30000)
            expect(page.locator("#roleInfoBanner")).not_to_contain_text("analiz birimi")
            page.screenshot(path=str(EVIDENCE / "akkaya_reference_restored.png"), full_page=True)

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
            assert run_id not in page.locator("#v1-native-provenance").inner_text()
            assert not [error for error in errors if error not in project_errors]
            browser.close()
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
    for native_target in (
        "v1-native-run-summary", "v1-native-water-accounting",
        "v1-native-annual-budget", "v1-native-monthly",
        "v1-native-warnings", "v1-native-crops",
        "v1-native-unit-result", "v1-native-provenance",
    ):
        assert native_target in provider
    assert "new Set([...(result.monthly_supply_validation?.violating_months||[])" in provider
    assert "Analiz Birimleri Haritası" in provider
    assert "setDrawer(true);\n    neutralizeReferenceSurface" not in provider
    assert ".v1-provider-scrim[hidden]{display:none!important;pointer-events:none!important}" in css
