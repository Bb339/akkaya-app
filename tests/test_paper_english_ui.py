from __future__ import annotations

import json
import re
from flask import send_from_directory
import pytest
from playwright.sync_api import expect, sync_playwright

from test_unified_decision_demo import analysis_payload, client_for, project_payload
from test_unified_decision_demo_browser import serve
from test_unified_v1_project_provider_browser import _serve_v1
from test_v1_native_project_integration_fix2 import PACKAGE, _confirm, _upload


ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]


def _prepare_run(client, repository):
    project_id = 'paper-project-demo'
    payload = project_payload(project_id)
    payload['name'] = 'Paper Project Demo'
    assert client.post('/api/v2/projects', json=payload).status_code == 201
    package = _upload(client, project_id)
    assert package['auto_matched'] == len(package['items']) == 21
    _confirm(client, project_id, package['items'])
    request = analysis_payload()
    preview = client.post(f'/api/v2/projects/{project_id}/analysis-preview', json=request)
    assert preview.status_code == 200 and preview.json['ready'] is True
    response = client.post(f'/api/v2/projects/{project_id}/analyses', json={
        **request,
        **{key: preview.json[key] for key in ('preview_token', 'preview_revision', 'selection_hash')},
    })
    assert response.status_code == 201, response.json
    document = repository.get(project_id)
    assert document['data_revision'] == 21
    assert len(document['analysis_units']) == 24
    assert sum(bool(unit.get('geometry')) for unit in document['analysis_units']) == 24
    assert len(document['crops']) == 8
    assert len({row['analysis_unit_id'] for row in document['scientific_inputs']['candidates']}) == 24
    return project_id, response.json


TURKISH_CHARACTERS = re.compile(r'[ıİğĞşŞçÇöÖüÜ]')

TURKISH_UI_TERMS = re.compile(
    r'\b(?:aktif|açıklama|aday|alan|analiz|arz|aylık|belirtilmedi|'
    r'bekleniyor|birim|birimi|bütçe|çalışma|çalıştır|doğrula|dosya|durum|ekonomi|'
    r'eksik|geçersiz|geometri|gerekçe|harita|hazır|hedef|için|karar|kapsam|kaynak|'
    r'kayıt|kullanıcı|kurum|mevcut|oluştur|önizleme|öneri|önerilen|parsel|planlama|'
    r'proje|sağlanmadı|seç|seçili|seçilmedi|sulama|sürüm|talep|uyarı|uygulanabilir|'
    r'veri|yükle|yükleme|yıllık|yok|yönetim|ürün)\b',
    re.IGNORECASE,
)

FORBIDDEN_EN_UI = re.compile(
    r'(?:Dosyaları?\s+Seç|Dosya seçilmedi|Kaydet|Miktar|Engelleyici|\bbulgu\b|'
    r'Uygulanmaz|Kurumsal analiz|Uzman|Kurum gelen|Görülenleri|bildirimleri|'
    r'Onayla|Revizyon iste|İptal|reddet|\bSil\b|Mesaj gönder|geometrileri|'
    r'Resmî|\bKöy\b|Havza|Bitki Deseni|Toplam Kâr|Su Verimliliği|CSV indir|'
    r'Benchmark sekmesi|Bu bölüm|Mevcut desen|tek sezon bağlamı|'
    r'\b(?:Fark|Senaryo|Genetik|Kurumsal|Otorite|doluluk|hedefi|altında|paneli|'
    r'Algoritma|Profil|Engeller)\b|'
    r'\b(?:gonderdi|sec|urun|onay|talep|parseli|uygulanmaz)\b)',
    re.IGNORECASE,
)

ALLOWED_NON_ENGLISH = re.compile(
    r'\b(?:Niğde|Akkaya|Sazlıca|Bahçeli|Kemerhisar|Kaynarca|Bor|Betül Demir|'
    r'Yeşim Dokuz|Burak Şen|İlçe Merkezi)\b',
    re.IGNORECASE,
)

ALLOWED_PROPER_NOUN_LINES = {
    'Niğde Ömer Halisdemir Üniversitesi',
    'Tarım Bilimleri ve Teknolojileri Fakültesi',
    'ÖNAP',
    'Betül Demir',
    'Doç. Dr. Yeşim Dokuz',
    'Doç. Dr. Burak Şen',
    'Bakanlık Sentetik Demo Projesi',
}


def _untranslated_visible_lines(page):
    lines = page.evaluate("""() => {
      const output=[];
      const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
      let node;
      while((node=walker.nextNode())){
        const parent=node.parentElement;
        if(!parent || parent.closest('script,style,pre,code,[hidden]'))continue;
        const style=getComputedStyle(parent);
        if(style.display==='none' || style.visibility==='hidden' || !parent.getClientRects().length)continue;
        const value=node.data.trim();
        if(value)output.push(value);
      }
      return output;
    }""")
    result = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line in ALLOWED_PROPER_NOUN_LINES:
            continue
        if re.fullmatch(r'\S+ / demo123', line):
            continue
        if re.search(r'\.(?:xlsx|xls|csv|geojson|json)\b', line, re.IGNORECASE):
            continue
        candidate = ALLOWED_NON_ENGLISH.sub('', line)
        if (TURKISH_CHARACTERS.search(candidate) or TURKISH_UI_TERMS.search(candidate)
                or FORBIDDEN_EN_UI.search(candidate)):
            result.append(line)
    return result


def _assert_toggle_layout(page, parent_selector):
    expect(page.locator(f'{parent_selector} > .paper-language-switch')).to_be_visible()
    for width in (1366, 1024):
        page.set_viewport_size({'width': width, 'height': 900})
        layout = page.evaluate("""parentSelector => {
          const toggle=document.querySelector('.paper-language-switch');
          const parent=document.querySelector(parentSelector);
          const rect=toggle?.getBoundingClientRect();
          const overlaps=Array.from(parent?.children||[]).filter(node => {
            if(node===toggle || node.hidden || node.offsetParent===null)return false;
            const other=node.getBoundingClientRect();
            return rect.left < other.right && rect.right > other.left &&
              rect.top < other.bottom && rect.bottom > other.top;
          }).length;
          return {
            overlaps,
            contained:Boolean(rect && parent && rect.left>=0 && rect.right<=innerWidth),
            overflow:document.documentElement.scrollWidth>innerWidth
          };
        }""", parent_selector)
        assert layout == {'overlaps': 0, 'contained': True, 'overflow': False}
    page.set_viewport_size({'width': 1366, 'height': 900})


@pytest.mark.browser
def test_english_paper_ui_preserves_project_run_and_selected_unit_parity(tmp_path):
    application, client, repository = client_for(tmp_path)

    @application.get('/data/<path:filename>')
    def v1_reference_data(filename):
        return send_from_directory(ROOT / 'data', filename)

    _serve_v1(application)
    project_id, run = _prepare_run(client, repository)
    upload_preview_id = 'paper-upload-preview'
    assert client.post('/api/v2/projects', json=project_payload(upload_preview_id)).status_code == 201
    stored_before = client.get(f'/api/v2/projects/{project_id}/analyses/{run["id"]}').json
    server, thread = serve(application)
    requests, page_errors = [], []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1366, 'height': 900})
            page.on('request', lambda request: requests.append(request.url))
            page.on('pageerror', lambda error: page_errors.append(str(error)))
            page.goto(
                f'http://127.0.0.1:{server.server_port}/?provider=PROJECT_DATA'
                f'&project_id={project_id}&run_id={run["id"]}'
            )
            page.wait_for_function(
                'runId => window.__V1_PROJECT_PROVIDER__?.context?.run?.id === runId',
                arg=run['id'],
            )
            expect(page.locator('html')).to_have_attribute('lang', 'tr')
            _assert_toggle_layout(page, '.auth-card-head')
            page.locator('[data-paper-lang="en"]').click()
            assert not _untranslated_visible_lines(page)
            page.locator('[data-auth-tab="register"]').click()
            assert not _untranslated_visible_lines(page)
            page.locator('[data-auth-tab="login"]').click()
            page.locator('[data-paper-lang="tr"]').click()
            page.evaluate(
                "setAuthenticatedUser(getAuthUserByUsername('kurum.nigde'), {focus:false})"
            )
            _assert_toggle_layout(page, '.session-chip-row')
            page.locator('#parcelSelect').select_option('KDS-001')
            page.wait_for_function(
                "document.querySelector('#metricsTitle')?.textContent.includes('KDS-001')"
            )
            page.evaluate("""() => {
              map.invalidateSize();
              const layers=Object.values(map._layers||{}).filter(
                layer => layer.__providerUnit && typeof layer.getBounds === 'function'
              );
              const bounds=L.featureGroup(layers).getBounds();
              if(bounds?.isValid?.())map.fitBounds(bounds.pad(.15),{animate:false});
            }""")
            page.evaluate("window.__V1_PROJECT_PROVIDER__.openUnitPopup('KDS-001')")
            popup = page.locator('.leaflet-popup-content', has_text='KDS-001')
            expect(popup).to_be_visible()
            page.wait_for_function("""() => {
              const popup=document.querySelector('.leaflet-popup');
              const map=document.querySelector('#map');
              if(!popup||!map)return false;
              const p=popup.getBoundingClientRect(), m=map.getBoundingClientRect();
              return p.left>=m.left && p.right<=m.right && p.top>=m.top && p.bottom<=m.bottom;
            }""")
            assert page.locator('.parcel-badge > .dot + .pid + .hint').count() == 24
            assert page.evaluate("""() => Array.from(
              document.querySelectorAll('#analysisTables .tab')
            ).filter(node => node.offsetParent !== null).length""") == 7
            assert page.locator('.tab[data-tab="drought"]').count() == 0

            before = page.evaluate("""() => ({
              project:window.__V1_PROJECT_PROVIDER__.context.project.id,
              run:window.__V1_PROJECT_PROVIDER__.context.run.id,
              revision:window.__V1_PROJECT_PROVIDER__.context.project_revision,
              selected:window.__V1_PROJECT_PROVIDER__.selectedUnit,
              units:window.__V1_PROJECT_PROVIDER__.context.units.map(x=>x.analysis_unit_id),
              selectedGeometry:JSON.stringify(window.__V1_PROJECT_PROVIDER__.context.units.find(
                x=>x.analysis_unit_id===window.__V1_PROJECT_PROVIDER__.selectedUnit
              )?.geometry),
              popupLatLng:map._popup?.getLatLng?.() ? [map._popup.getLatLng().lat,map._popup.getLatLng().lng] : null,
              geometry:document.querySelectorAll('.leaflet-overlay-pane path.leaflet-interactive').length,
              numeric:Object.fromEntries([
                'mWaterCurrent','mWaterScenario','mProfitCurrent','mProfitScenario',
                'mEffCurrent','mEffScenario'
              ].map(id=>[id,document.getElementById(id)?.textContent.match(/-?[0-9]+(?:[.,][0-9]+)*/)?.[0]||null])),
              chartData:JSON.stringify(Array.from(document.querySelectorAll('canvas')).map(canvas => {
                const chart=window.Chart?.getChart?.(canvas);
                return chart ? (chart.data.datasets||[]).map(dataset=>dataset.data) : null;
              })),
              navigationEntries:performance.getEntriesByType('navigation').length,
              result:JSON.stringify(window.__V1_PROJECT_PROVIDER__.context.run.result)
            })""")
            api_requests_before = [url for url in requests if '/api/v2/' in url]
            page.locator('[data-paper-lang="en"]').click()
            expect(page.locator('html')).to_have_attribute('lang', 'en')
            expect(page.locator('#metricsTitle')).to_have_text(
                'Analysis Unit Decision Summary (KDS-001)'
            )
            expect(page.locator('#activeObjectiveBadge')).to_have_text(
                'Active objective: Water Saving'
            )
            expect(page.locator('#algoSelect option:checked')).to_have_text(
                'Genetic Algorithm (GA)'
            )
            expect(page.locator('#seasonSourceRow .field-label')).to_have_text('Scenario Type')
            expect(page.locator('#bWaterDiff')).to_contain_text('Difference:')
            expect(page.locator('#decisionRationale')).to_contain_text(
                'GA was run using the project candidate matrix under the Water Saving objective.'
            )
            expect(popup).to_contain_text('Authority')
            expect(page.locator('.map-card .card-title')).to_have_text('Analysis Unit Map')
            expect(page.locator('#waterRiskSection')).to_contain_text('NOT PROVIDED')
            expect(page.locator('#parcelSummaryTitle')).to_contain_text('KDS-001')
            expect(page.locator('#tblCurrent')).to_contain_text('Current')
            expect(page.locator('#tblRecommended')).to_contain_text('Recommended')
            expect(page.locator('#tblRecommended')).to_contain_text('WHEAT')
            translated_application_families = page.evaluate("""() => [
              'Senaryo, su bütçesi ve etki analizi odaklı kurumsal görünüm',
              'Kurumsal analiz paneli',
              'Across the region, 24 analysis unit için ilçe özeti, su bütçesi, algoritma karşılaştırmaları ve uzun vadeli etki ekranları öne çıkar. Kullanıcı açma / pasife alma gibi işlemler yönetici hesabında tutulur.',
              'Aktif hedef: Su etkin kullanım',
              'Fark: 1 m³',
              'Genetik Algoritma (GA)',
              'Senaryo tipi',
              'GA, water_efficiency hedefi altında project candidate matrix kullanılarak çalıştırıldı.',
              'doluluk: 50 | baraj riski: düşük | plan riski: düşük',
              'Otorite'
            ].map(value => window.__CROP_KDS_I18N__.translate(value))""")
            assert translated_application_families == [
                'Institutional view focused on scenarios, water budgets, and impact analysis',
                'Institutional Analysis Panel',
                'Across the region, 24 analysis units support district summaries, water-budget assessment, algorithm comparisons, and long-term impact views. User activation and deactivation remain under the administrator account.',
                'Active objective: Water-Use Efficiency',
                'Difference: 1 m³',
                'Genetic Algorithm (GA)',
                'Scenario Type',
                'GA was run using the project candidate matrix under the Water-Use Efficiency objective.',
                'storage level: 50 | reservoir risk: low | plan risk: low',
                'Authority',
            ]
            preserved_user_text = 'Bugün sulama planım yok; uzman görüşü bekliyorum.'
            page.evaluate("""value => {
              const node=document.createElement('div');
              node.id='i18n-user-text-probe';
              node.className='request-msg-text';
              node.textContent=value;
              document.body.append(node);
              window.__CROP_KDS_I18N__.setLanguage('en');
            }""", preserved_user_text)
            expect(page.locator('#i18n-user-text-probe')).to_have_text(preserved_user_text)
            page.locator('#i18n-user-text-probe').evaluate('node => node.remove()')
            chart_labels = page.evaluate("""() => JSON.stringify(
              Array.from(document.querySelectorAll('canvas')).map(canvas => {
                const chart=window.Chart?.getChart?.(canvas);
                return chart ? {
                  labels:chart.data.labels,
                  datasets:(chart.data.datasets||[]).map(dataset=>dataset.label),
                  title:chart.options?.plugins?.title?.text,
                  axes:Object.values(chart.options?.scales||{}).map(axis=>axis?.title?.text)
                } : null;
              })
            )""")
            assert not (
                TURKISH_CHARACTERS.search(chart_labels) or TURKISH_UI_TERMS.search(chart_labels)
            ), chart_labels
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            untranslated = _untranslated_visible_lines(page)
            assert not untranslated, '\n'.join(untranslated)
            assert [url for url in requests if '/api/v2/' in url] == api_requests_before
            after = page.evaluate("""() => ({
              project:window.__V1_PROJECT_PROVIDER__.context.project.id,
              run:window.__V1_PROJECT_PROVIDER__.context.run.id,
              revision:window.__V1_PROJECT_PROVIDER__.context.project_revision,
              selected:window.__V1_PROJECT_PROVIDER__.selectedUnit,
              units:window.__V1_PROJECT_PROVIDER__.context.units.map(x=>x.analysis_unit_id),
              selectedGeometry:JSON.stringify(window.__V1_PROJECT_PROVIDER__.context.units.find(
                x=>x.analysis_unit_id===window.__V1_PROJECT_PROVIDER__.selectedUnit
              )?.geometry),
              popupLatLng:map._popup?.getLatLng?.() ? [map._popup.getLatLng().lat,map._popup.getLatLng().lng] : null,
              geometry:document.querySelectorAll('.leaflet-overlay-pane path.leaflet-interactive').length,
              numeric:Object.fromEntries([
                'mWaterCurrent','mWaterScenario','mProfitCurrent','mProfitScenario',
                'mEffCurrent','mEffScenario'
              ].map(id=>[id,document.getElementById(id)?.textContent.match(/-?[0-9]+(?:[.,][0-9]+)*/)?.[0]||null])),
              chartData:JSON.stringify(Array.from(document.querySelectorAll('canvas')).map(canvas => {
                const chart=window.Chart?.getChart?.(canvas);
                return chart ? (chart.data.datasets||[]).map(dataset=>dataset.data) : null;
              })),
              navigationEntries:performance.getEntriesByType('navigation').length,
              result:JSON.stringify(window.__V1_PROJECT_PROVIDER__.context.run.result)
            })""")
            assert after == before
            assert before == {
                **before,
                'project': project_id,
                'run': run['id'],
                'revision': 21,
                'selected': 'KDS-001',
                'geometry': 24,
            }

            tab_leaks = {}
            for tab_key in (
                'institution-communication', 'drawing', 'district', 'official', 'benchmark'
            ):
                assert page.evaluate('key => switchTabByKey(key)', tab_key)
                page.wait_for_timeout(150)
                page.evaluate("window.__CROP_KDS_I18N__.setLanguage('en')")
                assert page.locator(f'#tab-{tab_key}').is_visible()
                untranslated = _untranslated_visible_lines(page)
                if untranslated:
                    tab_leaks[tab_key] = untranslated
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            assert not tab_leaks, '\n'.join(
                f'{tab}: {line}' for tab, lines in tab_leaks.items() for line in lines
            )
            dynamic_chart_labels = page.evaluate("""() => {
              window.__CROP_KDS_I18N__.applyCharts();
              return JSON.stringify(Array.from(document.querySelectorAll('canvas')).map(canvas => {
                const chart=window.Chart?.getChart?.(canvas);
                return chart ? {
                  labels:chart.data.labels,
                  datasets:(chart.data.datasets||[]).map(dataset=>dataset.label),
                  title:chart.options?.plugins?.title?.text,
                  axes:Object.values(chart.options?.scales||{}).map(axis=>axis?.title?.text)
                } : null;
              }));
            }""")
            assert not (
                TURKISH_CHARACTERS.search(dynamic_chart_labels)
                or TURKISH_UI_TERMS.search(dynamic_chart_labels)
                or FORBIDDEN_EN_UI.search(dynamic_chart_labels)
            ), dynamic_chart_labels
            expect(page.locator('#tab-official')).to_contain_text(
                'Analysis-Unit Summary — Official'
            )
            translated_templates = page.evaluate("""() => [
              'Betül Demir P23 parseli için mesaj gönderdi.',
              'Betül Demir P23 parseli için alternatif talebi gönderdi.',
              'Talebiniz uzman tarafından onaylandı. Seçilen alternatif onaylı güncel plan sekmesine eklendi.',
              'ARPA (DANE) sonra KIMYON alternatifini seçmek istiyorum. Su: 4,327,129 m³, net kâr: 39,229,300 TL. Uzman onayı rica ediyorum.',
              'MERCIMEK tek ürün alternatifini talep ediyorum. Hedef: Su Tasarrufu. Algoritma: GA. Su: 792,511 m³, net kâr: 18,770,000 TL. Uzman onayı ve parselime atanmasını rica ediyorum.'
              ,'aaaa'
              ,'hhhhh'
            ].map(value => window.__CROP_KDS_I18N__.translate(value))""")
            assert translated_templates == [
                'Betül Demir sent a message for parcel P23.',
                'Betül Demir submitted an alternative request for parcel P23.',
                'Your request was approved by the expert. The selected alternative was added to the approved current-plan tab.',
                'I would like to select CUMIN after BARLEY (GRAIN). Water: 4,327,129 m³, net profit: 39,229,300 TRY. Expert approval is requested.',
                'I request the single-crop LENTIL alternative. Objective: Water Saving. Algorithm: GA. Water: 792,511 m³, net profit: 18,770,000 TRY. I request expert approval and assignment to my parcel.',
                'aaaa',
                'hhhhh',
            ]
            assert page.evaluate("key => switchTabByKey(key)", 'parcel')

            page.locator('[data-paper-lang="tr"]').click()
            expect(page.locator('#metricsTitle')).to_have_text(
                'Analiz Birimi Karar Özeti (KDS-001)'
            )
            tr_return = page.evaluate("""() => ({
              project:window.__V1_PROJECT_PROVIDER__.context.project.id,
              run:window.__V1_PROJECT_PROVIDER__.context.run.id,
              revision:window.__V1_PROJECT_PROVIDER__.context.project_revision,
              selected:window.__V1_PROJECT_PROVIDER__.selectedUnit,
              selectedGeometry:JSON.stringify(window.__V1_PROJECT_PROVIDER__.context.units.find(
                x=>x.analysis_unit_id===window.__V1_PROJECT_PROVIDER__.selectedUnit
              )?.geometry),
              result:JSON.stringify(window.__V1_PROJECT_PROVIDER__.context.run.result)
            })""")
            for key in ('project', 'run', 'revision', 'selected', 'selectedGeometry', 'result'):
                assert tr_return[key] == before[key]
            assert [url for url in requests if '/api/v2/' in url] == api_requests_before
            page.locator('[data-paper-lang="en"]').click()
            page.goto(f'http://127.0.0.1:{server.server_port}/projects#project={project_id}&section=result')
            expect(page.locator('html')).to_have_attribute('lang', 'en')
            expect(page.locator('h1')).to_have_text('Institutional Agricultural Decision Workflow')
            expect(page.locator('#project-status-badges')).to_contain_text('Revision 21')
            _assert_toggle_layout(page, '.topbar-actions')
            page.goto(
                f'http://127.0.0.1:{server.server_port}/projects'
                f'#project={upload_preview_id}&section=data'
            )
            expect(page.locator('#project-status-badges')).to_contain_text('Revision 0')
            file_input = page.locator('#bulk-upload-form input[type="file"]')
            file_control = page.locator('#bulk-upload-form .paper-file-control')
            expect(file_control).to_be_visible()
            expect(file_control.locator('.paper-file-button')).to_have_text('Choose Files')
            expect(file_control.locator('.paper-file-status')).to_have_text('No file selected')
            assert file_input.evaluate(
                "node => node.getBoundingClientRect().width <= 1 && node.getBoundingClientRect().height <= 1"
            )
            package_files = [
                str(path) for path in sorted(PACKAGE.iterdir())
                if path.suffix.lower() in {'.csv', '.xlsx', '.geojson'}
            ]
            file_input.set_input_files(package_files)
            expect(file_control.locator('.paper-file-status')).to_have_text('21 files selected')
            page.locator('#bulk-upload-form button[type="submit"]').click()
            expect(page.locator('#bulk-import-results')).to_be_visible(timeout=60000)
            expect(page.locator('#bulk-import-body tr')).to_have_count(21)
            untranslated = _untranslated_visible_lines(page)
            assert not untranslated, 'bulk-preview: ' + '\n'.join(untranslated)
            page.locator('[data-project-section="readiness"]').first.click()
            page.wait_for_function("location.hash.includes('section=readiness')")
            untranslated = _untranslated_visible_lines(page)
            assert not untranslated, 'blocked-readiness: ' + '\n'.join(untranslated)
            page.goto(
                f'http://127.0.0.1:{server.server_port}/projects'
                f'#project={project_id}&section=result'
            )
            expect(page.locator('#project-status-badges')).to_contain_text('Revision 21')
            for section in ('project', 'data', 'readiness', 'analysis', 'result', 'provenance', 'reference'):
                page.locator(f'[data-project-section="{section}"]').first.click()
                page.wait_for_function(
                    "section => location.hash.includes(`section=${section}`)", arg=section
                )
                if section == 'data':
                    page.locator('#budget-form').evaluate(
                        "form => { form.closest('details').open = true; }"
                    )
                    expect(page.locator('#budget-form')).to_contain_text('Amount (m³)')
                    expect(page.locator('#budget-form button')).to_have_text('Save')
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                untranslated = _untranslated_visible_lines(page)
                assert not untranslated, f'{section}: ' + '\n'.join(untranslated)
            page.goto(
                f'http://127.0.0.1:{server.server_port}/projects/decision'
                f'?project_id={project_id}&run_id={run["id"]}'
                '&execution_profile=VERIFIED_INSTITUTIONAL'
            )
            expect(page.locator('html')).to_have_attribute('lang', 'en')
            expect(page.locator('#decision-title')).to_contain_text('Paper Project Demo')
            expect(page.locator('#result')).to_contain_text('Verified Water Results')
            _assert_toggle_layout(page, '.topbar-actions')
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            untranslated = _untranslated_visible_lines(page)
            assert not untranslated, '\n'.join(untranslated)
            page.goto(
                f'http://127.0.0.1:{server.server_port}/?provider=PROJECT_DATA'
                '&project_id=missing-paper-project'
            )
            page.wait_for_function(
                "!document.body.classList.contains('app-booting')"
            )
            page.evaluate(
                "setAuthenticatedUser(getAuthUserByUsername('kurum.nigde'), {focus:false})"
            )
            expect(page.locator('html')).to_have_attribute('lang', 'en')
            expect(page.locator('#v1-provider-error')).to_be_visible()
            expect(page.locator('#v1-provider-error')).to_contain_text(
                'Project context could not be opened:'
            )
            assert not _untranslated_visible_lines(page)
            assert not page_errors
            reference_tokens = (
                '/api/parcels', '/api/optimize', '/api/meta', '/api/geojson_files',
                '/api/geojson_bundle', '/api/water_allocation_logic', '/data/',
            )
            assert not [url for url in requests if any(token in url for token in reference_tokens)]
            stored = client.get(f'/api/v2/projects/{project_id}/analyses/{run["id"]}').json
            assert json.dumps(stored, sort_keys=True) == json.dumps(stored_before, sort_keys=True)
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
