from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from test_unified_decision_demo import analysis_payload, client_for, project_payload
from test_unified_decision_demo_browser import serve
from test_v1_native_project_integration_fix2 import _confirm, _upload
from test_v1_native_project_interactivity_final import _serve_full_v1


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "project_data_v1_map_selected_unit_parity_final" / "evidence"
REFERENCE_PATHS = (
    "/api/parcels", "/api/optimize", "/api/meta", "/api/geojson_files",
    "/api/geojson_bundle", "/api/water_allocation_logic", "/data/",
)


def _create_run(client, project_id: str, scenario: str = "S2"):
    body = analysis_payload()
    body.update(scenario=scenario, algorithm="GA", objective="water_saving", seed=123)
    preview = client.post(f"/api/v2/projects/{project_id}/analysis-preview", json=body)
    assert preview.status_code == 200 and preview.json["ready"] is True
    execution = {**body, **{key: preview.json[key]
                            for key in ("preview_token", "preview_revision", "selection_hash")}}
    response = client.post(f"/api/v2/projects/{project_id}/analyses", json=execution)
    assert response.status_code == 201, response.json
    return response.json


def _signature(page, selector: str):
    return page.locator(selector).first.evaluate(
        """node => ({tag:node.tagName, cls:[...node.classList], children:[...node.children].map(
          child=>({tag:child.tagName,cls:[...child.classList],children:[...child.children].map(
            nested=>({tag:nested.tagName,cls:[...nested.classList]}))}))})"""
    )


def _family_signature(page, selector: str):
    return page.locator(selector).first.evaluate(
        """node => ({tag:node.tagName, cls:[...node.classList], families:[...new Set(
          [...node.children].map(child=>JSON.stringify({tag:child.tagName,cls:[...child.classList],children:[...child.children].map(
            nested=>({tag:nested.tagName,cls:[...nested.classList]}))})))].map(JSON.parse)})"""
    )


@pytest.mark.browser
def test_exact_native_map_popup_selected_unit_and_recommendation_parity(tmp_path):
    application, client, repository = client_for(tmp_path)
    _serve_full_v1(application)
    project_id = "native-map-parity"
    payload = project_payload(project_id)
    payload["name"] = "Native V1 Map Parity"
    assert client.post("/api/v2/projects", json=payload).status_code == 201
    package = _upload(client, project_id)
    assert len(package["items"]) == package["auto_matched"] == 21
    _confirm(client, project_id, package["items"])
    s1_run = _create_run(client, project_id, "S1")
    assert len({row["analysis_unit_id"]: row for row in s1_run["result"]["unit_results"]}["KDS-009"]["selected_crops"]) == 1
    run = _create_run(client, project_id, "S2")
    result_units = {row["analysis_unit_id"]: row
                    for row in run["result"]["unit_results"]}
    assert len(result_units["KDS-009"]["selected_crops"]) == 2
    document = repository.get(project_id)
    assert document["data_revision"] == 21
    assert len(document["analysis_units"]) == 24
    assert len(document["crops"]) == 8
    assert all(unit.get("geometry", {}).get("type") == "Polygon"
               for unit in document["analysis_units"])

    server, thread = serve(application)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1366, "height": 900})
            page = context.new_page()
            requests, pageerrors, console_messages = [], [], []
            page.on("request", lambda request: requests.append(request.url))
            page.on("pageerror", lambda error: pageerrors.append(str(error)))
            page.on("console", lambda message: console_messages.append(message.text))
            page.route("**/api/parcels", lambda route: route.fulfill(json={
                "parcels": [{"id": f"P{index}", "map_only": False,
                             "area_da": 1, "current_crop": "ARPA"}
                            for index in range(1, 180)]
            }))
            url = (f"http://127.0.0.1:{server.server_port}/?provider=PROJECT_DATA"
                   f"&project_id={project_id}&run_id={run['id']}&unit=KDS-001")
            page.goto(url)
            page.wait_for_function("window.__V1_PROJECT_PROVIDER__?.context?.unit_count === 24")
            page.wait_for_function("!document.body.classList.contains('app-booting')")
            page.evaluate("setAuthenticatedUser(getAuthUserByUsername('kurum.nigde'), {focus:false})")
            expect(page.locator("#panel")).to_be_visible()
            page.wait_for_function("window.__V1_PROJECT_PROVIDER__.mapState().zoom >= 10")
            expect(page.locator(".parcel-badge")).to_have_count(24, timeout=30000)
            expect(page.locator(".parcel-badge .dot")).to_have_count(24)
            expect(page.locator(".parcel-badge .hint")).to_have_count(24)
            assert page.locator(".v1-project-map-label").count() == 0
            assert page.locator("#v1-native-project-results").count() == 0

            # Shared renderer identity: project badge/popup/card output is produced
            # by the exact same global functions invoked by AKKAYA_REFERENCE.
            assert page.evaluate("typeof NativeV1Presentation.unitBadgeHtml") == "function"
            assert page.evaluate("typeof NativeV1Presentation.unitPopupHtml") == "function"
            assert page.evaluate("typeof NativeV1Presentation.productCardsHtml") == "function"
            project_badge_signature = _signature(page, ".parcel-badge")
            project_card_signature = _signature(page, "#productCards .crop-detail-card")

            page.screenshot(path=str(EVIDENCE / "01_project_top_workspace_1366x900.png"), full_page=True)
            page.locator("#map").screenshot(path=str(EVIDENCE / "02_project_selected_map_state.png"))
            page.locator(".parcel-badge").first.screenshot(path=str(EVIDENCE / "03_project_native_badge.png"))

            # Capture the single-crop S1 native strip/card, then restore the S2
            # run used for two-crop synchronization and paired evidence.
            s1_url = (f"http://127.0.0.1:{server.server_port}/?provider=PROJECT_DATA"
                      f"&project_id={project_id}&run_id={s1_run['id']}&unit=KDS-009")
            page.goto(s1_url)
            page.wait_for_function("window.__V1_PROJECT_PROVIDER__?.context?.run?.id")
            page.evaluate("setAuthenticatedUser(getAuthUserByUsername('kurum.nigde'), {focus:false})")
            expect(page.locator("#productCards .crop-pill")).to_have_count(1)
            expect(page.locator("#productCards .crop-emoji")).to_have_count(1)
            page.locator("#productCards").screenshot(path=str(EVIDENCE / "07_project_recommendation_card.png"))
            page.goto(url)
            page.wait_for_function("window.__V1_PROJECT_PROVIDER__?.context?.run?.id")
            page.evaluate("setAuthenticatedUser(getAuthUserByUsername('kurum.nigde'), {focus:false})")

            previous = None
            for unit_id in ("KDS-001", "KDS-005", "KDS-009", "KDS-024"):
                page.locator("#parcelSelect").select_option(unit_id)
                expect(page.locator("#parcelSelect")).to_have_value(unit_id)
                expect(page.locator("#metricsTitle")).to_contain_text(unit_id)
                expect(page.locator("#parcelSummaryTitle")).to_contain_text(unit_id)
                expect(page.locator("#tblCurrentFooter")).to_contain_text(unit_id)
                expected_crops = len(result_units[unit_id]["selected_crops"])
                expect(page.locator("#productCards .crop-pill")).to_have_count(expected_crops)
                expect(page.locator("#productCards .crop-emoji")).to_have_count(expected_crops)
                assert page.evaluate(
                    "unit => window.__V1_PROJECT_PROVIDER__.openUnitPopup(unit)", unit_id
                ) is True
                expect(page.locator(".leaflet-popup .parcel-pop")).to_be_visible()
                expect(page.locator(".leaflet-popup .parcel-pop .t")).to_contain_text(unit_id)
                popup_text = page.locator(".leaflet-popup .parcel-pop").inner_text()
                assert "Analiz birimi" in popup_text
                assert previous is None or previous not in popup_text
                state = page.evaluate(
                    "unit => window.__V1_PROJECT_PROVIDER__.unitLayerState(unit)", unit_id
                )
                assert state["style"] == {
                    "color": "#0b74c4", "weight": 3,
                    "fillColor": "#3aa0ff", "fillOpacity": .35,
                }
                assert "parcel-badge" in state["tooltipHtml"]
                assert "parcel-pop" in state["popupHtml"]
                if unit_id == "KDS-009":
                    page.locator("#productCards").screenshot(
                        path=str(EVIDENCE / "08_project_s2_recommendation_cards.png")
                    )
                previous = unit_id

            # Use a central two-crop unit for paired popup/card evidence and
            # retain a DOM-family signature for the reference comparison.
            page.locator("#parcelSelect").select_option("KDS-009")
            page.wait_for_function("window.__V1_PROJECT_PROVIDER__.selectedUnit === 'KDS-009'")
            page.evaluate("window.__V1_PROJECT_PROVIDER__.openUnitPopup('KDS-009')")
            expect(page.locator(".leaflet-popup .parcel-pop")).to_be_visible()
            assert page.locator(".leaflet-popup-pane").evaluate(
                "node => getComputedStyle(node).pointerEvents"
            ) == "none"
            assert page.locator(".leaflet-popup-tip").evaluate(
                "node => getComputedStyle(node).pointerEvents"
            ) == "none"
            page.locator(".leaflet-interactive").nth(8).click()
            expect(page.locator("#parcelSelect")).to_have_value("KDS-009")
            project_popup_signature = _family_signature(page, ".leaflet-popup .parcel-pop")
            page.locator("#map").scroll_into_view_if_needed()
            page.evaluate("window.scrollBy(0, -180)")
            page.locator(".leaflet-popup .parcel-pop").screenshot(path=str(EVIDENCE / "04_project_native_popup.png"))
            page.locator("#parcelSummaryBlock").screenshot(path=str(EVIDENCE / "05_project_selected_summary.png"))
            page.locator(".metrics-grid").screenshot(path=str(EVIDENCE / "06_project_water_profit_metrics.png"))

            # Direct PROJECT_DATA trace ends here, before any reference navigation.
            reference_requests = [url for url in requests if any(path in url for path in REFERENCE_PATHS)]
            assert reference_requests == []
            assert page.evaluate("window.__V1_PROJECT_PROVIDER__.blockedReferencePaths") == []
            assert pageerrors == []
            assert not [message for message in console_messages
                        if "reference endpoint engellendi" in message]

            # Desktop same-row parity is structural at the viewport where both
            # columns are active. Compact widths follow native V1's stacked rule.
            page.set_viewport_size({"width": 1920, "height": 1080})
            page.wait_for_function("document.documentElement.scrollWidth <= window.innerWidth")
            row_state = page.evaluate("window.__V1_PROJECT_PROVIDER__.mapRowState()")
            assert abs(row_state["mapCard"]["y"] - row_state["metrics"]["y"]) < 2
            assert abs(row_state["mapCard"]["height"] - row_state["metrics"]["height"]) < 2
            page.set_viewport_size({"width": 1366, "height": 900})

            for width, height in ((1280, 720), (1366, 768), (1366, 900),
                                  (1536, 864), (1920, 1080), (390, 844)):
                page.set_viewport_size({"width": width, "height": height})
                page.evaluate("window.dispatchEvent(new Event('resize'))")
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                expect(page.locator(".leaflet-popup .parcel-pop")).to_be_visible()
                expect(page.locator("#productCards .crop-detail-card").first).to_be_visible()
            page.set_viewport_size({"width": 1366, "height": 900})
            for zoom in ("80%", "100%", "125%"):
                page.evaluate("value => { document.body.style.zoom=value; window.dispatchEvent(new Event('resize')); }", zoom)
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.evaluate("document.body.style.zoom='100%'; window.dispatchEvent(new Event('resize'))")

            # Equivalent reference state and native-family signatures.
            page.goto(f"http://127.0.0.1:{server.server_port}/?provider=AKKAYA_REFERENCE")
            page.wait_for_function("window.__V1_PROJECT_PROVIDER__?.provider === 'AKKAYA_REFERENCE'")
            page.evaluate("setAuthenticatedUser(getAuthUserByUsername('kurum.nigde'), {focus:false})")
            expect(page.locator("#roleInfoBanner")).to_contain_text("179 parsel", timeout=30000)
            expect(page.locator(".parcel-badge").first).to_be_visible(timeout=30000)
            page.locator("#parcelSelect").select_option("P1")
            page.evaluate("window._focusParcel?.('P1')")
            expect(page.locator(".leaflet-popup .parcel-pop")).to_be_visible(timeout=30000)
            assert _signature(page, ".parcel-badge") == project_badge_signature
            assert _family_signature(page, ".leaflet-popup .parcel-pop") == project_popup_signature
            assert _signature(page, "#productCards .crop-detail-card") == project_card_signature
            page.screenshot(path=str(EVIDENCE / "09_reference_top_workspace_1366x900.png"), full_page=True)
            page.locator("#map").scroll_into_view_if_needed()
            page.evaluate("window.scrollBy(0, -180)")
            page.locator("#map").screenshot(path=str(EVIDENCE / "10_reference_selected_map_state.png"))
            page.locator(".parcel-badge").first.screenshot(path=str(EVIDENCE / "11_reference_native_badge.png"))
            page.locator(".leaflet-popup .parcel-pop").first.screenshot(path=str(EVIDENCE / "12_reference_native_popup.png"))
            page.locator("#parcelSummaryBlock").screenshot(path=str(EVIDENCE / "13_reference_selected_summary.png"))
            page.locator(".metrics-grid").screenshot(path=str(EVIDENCE / "14_reference_water_profit_metrics.png"))
            page.locator("#productCards").screenshot(path=str(EVIDENCE / "15_reference_recommendation_cards.png"))
            assert pageerrors == []
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
