from __future__ import annotations

import importlib
import re

import pytest
from playwright.sync_api import expect, sync_playwright

from test_unified_decision_demo_browser import serve
from test_paper_english_ui import _untranslated_visible_lines


@pytest.mark.browser
def test_akkaya_reference_tr_en_tr_preserves_parcel_and_values(tmp_path, monkeypatch):
    monkeypatch.setenv('KDS_PROJECT_STORE', str(tmp_path / 'projects'))
    monkeypatch.setenv('KDS_DEPLOYMENT_MODE', 'local-development')
    thesis = importlib.import_module('app')
    server, thread = serve(thesis.app)
    errors = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1366, 'height': 900})
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.route('https://**', lambda route: route.abort())
            page.goto(
                f'http://127.0.0.1:{server.server_port}/?provider=AKKAYA_REFERENCE',
                wait_until='domcontentloaded',
            )
            page.wait_for_function(
                "window.__V1_PROJECT_PROVIDER__?.provider === 'AKKAYA_REFERENCE'"
            )
            page.evaluate(
                "setAuthenticatedUser(getAuthUserByUsername('kurum.nigde'), {focus:false})"
            )
            expect(page.locator('#roleInfoBanner')).to_contain_text('179 parsel', timeout=30000)
            page.locator('#parcelSelect').select_option('P1')
            page.evaluate("window._focusParcel?.('P1')")
            expect(page.locator('.leaflet-popup-content').last).to_contain_text('P1', timeout=30000)

            state_script = """() => ({
              selected:document.querySelector('#parcelSelect')?.value,
              count:Array.from(document.querySelectorAll('#parcelSelect option')).filter(
                option=>option.value
              ).length,
              popupLatLng:map._popup?.getLatLng?.() ? [map._popup.getLatLng().lat,map._popup.getLatLng().lng] : null,
              geometry:document.querySelectorAll('.leaflet-overlay-pane path.leaflet-interactive').length,
              numeric:Object.fromEntries([
                'mWaterCurrent','mWaterScenario','mProfitCurrent','mProfitScenario',
                'mEffCurrent','mEffScenario'
              ].map(id=>[id,document.getElementById(id)?.textContent.match(/-?[0-9]+(?:[.,][0-9]+)*/)?.[0]||null])),
              chartData:JSON.stringify(Array.from(document.querySelectorAll('canvas')).map(canvas => {
                const chart=window.Chart?.getChart?.(canvas);
                return chart ? (chart.data.datasets||[]).map(dataset=>dataset.data) : null;
              }))
            })"""
            tr_before = page.evaluate(state_script)
            assert tr_before['selected'] == 'P1' and tr_before['count'] == 179

            page.locator('[data-paper-lang="en"]').click()
            expect(page.locator('html')).to_have_attribute('lang', 'en')
            expect(page.locator('#roleInfoBanner')).to_contain_text('179 parcels')
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            untranslated = _untranslated_visible_lines(page)
            untranslated = [
                line for line in untranslated
                if not re.match(r'^\d+\s+[A-Za-z0-9_ /.-]+$', line)
            ]
            assert not untranslated, '\n'.join(untranslated)
            assert page.evaluate(state_script) == tr_before

            page.locator('[data-paper-lang="tr"]').click()
            expect(page.locator('#roleInfoBanner')).to_contain_text('179 parsel')
            assert page.evaluate(state_script) == tr_before
            assert not errors
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
