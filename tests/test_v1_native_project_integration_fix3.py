from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from test_unified_decision_demo import client_for, project_payload
from test_unified_decision_demo_browser import serve
from test_unified_v1_project_provider_browser import FULL_VISUAL_LEAFLET, _serve_v1
from test_v1_native_project_integration_fix2 import _confirm, _upload


ROOT = Path(__file__).resolve().parents[1]


def test_provider_aware_banner_uses_canonical_project_count():
    source = (ROOT / "script.js").read_text(encoding="utf-8")
    assert "window.__V1_PROJECT_PROVIDER__?.context?.unit_count" in source
    assert "${presentation.count}</strong> ${presentation.noun}" in source
    assert "const count = getVisibleUsableParcelIds().length;\n    if(getInstitutionRole(user)" not in source


def test_reference_count_and_project_unavailable_copy_are_fail_closed():
    source = (ROOT / "script.js").read_text(encoding="utf-8")
    assert "noun: 'parsel', provider: 'AKKAYA_REFERENCE'" in source
    assert "Proje kapsamındaki analiz birimleri için" in source
    assert "presentation.count === null" in source
    assert "Bölge genelindeki <strong>${count}</strong> parsel" not in source


def test_frozen_index_is_not_used_as_project_count_source():
    provider = (ROOT / "kds" / "ui" / "static" / "v1-provider.js").read_text(encoding="utf-8")
    assert "context.units" in provider
    assert "context.unit_count" in provider
    assert "querySelectorAll('#parcelSelect option')" not in provider


@pytest.mark.browser
def test_project_reference_project_banner_uses_provider_count(tmp_path):
    application, client, _ = client_for(tmp_path)
    _serve_v1(application)
    project_id = "provider-count-demo"
    payload = project_payload(project_id)
    payload["name"] = "Provider Count Demo"
    assert client.post("/api/v2/projects", json=payload).status_code == 201
    package = _upload(client, project_id)
    _confirm(client, project_id, package["items"])
    server, thread = serve(application)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 900})
            page.add_init_script(FULL_VISUAL_LEAFLET)
            page.route("https://**", lambda route: route.abort())
            requests = []
            page.on("request", lambda request: requests.append(request.url))

            project_url = (
                f"http://127.0.0.1:{server.server_port}/?provider=PROJECT_DATA"
                f"&project_id={project_id}"
            )
            page.goto(project_url)
            page.wait_for_function("typeof window.__V1_PROJECT_PROVIDER__ === 'object'")
            page.evaluate("setAuthenticatedUser(getAuthUserByUsername('kurum.nigde'), {focus:false})")
            expect(page.locator("#parcelSelect option")).to_have_count(24)
            expect(page.locator("#roleInfoBanner")).to_contain_text("24 analiz birimi")
            expect(page.locator("#roleInfoBanner")).not_to_contain_text("0 parsel")
            expect(page.locator("#userParcelCard .card-help.small").first).to_contain_text(
                "24 analiz birimi"
            )
            expect(page.locator("#userParcelCard .card-help.small").first).not_to_contain_text(
                "180 parsel"
            )

            page.evaluate("delete window.__V1_PROJECT_PROVIDER__.context.unit_count; syncRoleInfoBanner()")
            expect(page.locator("#roleInfoBanner")).to_contain_text(
                "Proje kapsamındaki analiz birimleri için"
            )
            expect(page.locator("#roleInfoBanner")).not_to_contain_text("0 parsel")
            assert not any("/api/parcels" in url or "/api/optimize" in url for url in requests)

            page.goto(f"http://127.0.0.1:{server.server_port}/")
            page.wait_for_function(
                "typeof window.__V1_PROJECT_PROVIDER__ === 'object' && "
                "window.__V1_PROJECT_PROVIDER__.provider === 'AKKAYA_REFERENCE'"
            )
            # The compact browser harness does not mount legacy /api/parcels.
            # Seed the already-verified canonical reference cardinality so this
            # journey can validate presentation switching without network data.
            page.evaluate("parcelData = Array.from({length:179}, (_, index) => "
                          "({id:`P${index + 1}`, map_only:false}))")
            page.evaluate("setAuthenticatedUser(getAuthUserByUsername('kurum.nigde'), {focus:false})")
            expect(page.locator("#roleInfoBanner")).to_contain_text("179 parsel")
            expect(page.locator("#roleInfoBanner")).not_to_contain_text("analiz birimi")

            requests.clear()
            page.goto(project_url)
            page.wait_for_function("window.__V1_PROJECT_PROVIDER__?.context?.unit_count === 24")
            page.evaluate("setAuthenticatedUser(getAuthUserByUsername('kurum.nigde'), {focus:false})")
            expect(page.locator("#roleInfoBanner")).to_contain_text("24 analiz birimi")
            expect(page.locator("#parcelSelect option")).to_have_count(24)
            assert not any("/api/parcels" in url or "/api/optimize" in url for url in requests)
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
