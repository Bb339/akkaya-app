from pathlib import Path

from flask import Blueprint, abort, render_template, request, send_from_directory


TEMPLATE_DIR = Path(__file__).resolve().parents[2] / 'docs' / 'data_templates'


def register_project_pages(app):
    pages = Blueprint('project_pages', __name__, url_prefix='/projects',
                      template_folder='templates', static_folder='static', static_url_path='/assets')

    @pages.get('')
    @pages.get('/')
    def index():
        return render_template('projects.html')

    @pages.get('/decision')
    def decision():
        return render_template('decision.html')

    @pages.get('/templates/<filename>')
    def data_template(filename):
        allowed = {path.name for path in TEMPLATE_DIR.glob('*.xlsx')}
        if filename not in allowed:
            abort(404)
        return send_from_directory(TEMPLATE_DIR, filename, as_attachment=True)

    @pages.after_app_request
    def reference_project_navigation(response):
        """Inject provider controls without mutating the frozen V1 artifact."""
        if request.path == '/' and response.status_code == 200 and response.mimetype == 'text/html':
            response.direct_passthrough = False
            html = response.get_data(as_text=True)
            marker = '<div class="session-chip-row">'
            if marker in html and 'data-project-workspace-link' not in html:
                boundary = (
                    '<aside data-reference-mode-banner role="status" '
                    'style="display:grid;gap:2px;padding:8px 12px;border:1px solid #f1c75b;'
                    'border-radius:10px;background:#fff8dc;color:#4a3700;max-width:620px">'
                    '<strong>AKKAYA REFERENCE · REFERENCE MODEL / DEMO DATA</strong>'
                    '<span>NOT OFFICIAL / NOT FIELD VALIDATED · Resmî su tahsisi, saha doğrulaması '
                    'veya Bakanlık onaylı öneri değildir.</span></aside>'
                )
                link = ('<a data-project-workspace-link class="btn-secondary header-switch-btn" '
                        'href="/projects">Projeler / Kurumsal veri</a>')
                provider = '''<button id="v1-provider-toggle" class="v1-provider-toggle" type="button" aria-controls="v1-provider-shell" aria-expanded="false"><span>Veri Kaynağı</span><strong id="v1-provider-badge">AKKAYA REF</strong></button>
<div id="v1-provider-scrim" class="v1-provider-scrim" hidden></div>
<aside id="v1-provider-shell" class="v1-provider-shell" aria-label="Veri sağlayıcı bağlamı" aria-hidden="true">
  <div class="v1-provider-head">
    <div><span class="v1-provider-kicker">VERİ KAYNAĞI</span><strong id="v1-provider-name">AKKAYA REFERENCE</strong><span id="v1-provider-authority">REFERENCE MODEL / DEMO DATA · NOT OFFICIAL / NOT FIELD VALIDATED</span></div>
    <button id="v1-provider-close" class="v1-provider-close" type="button" aria-label="Veri kaynağı panelini kapat">×</button>
  </div>
  <div class="v1-provider-actions"><a class="btn-secondary" id="v1-reference-provider" href="/">Akkaya Reference</a><select id="v1-project-provider-select" aria-label="Kurumsal proje seç"><option value="">Kurumsal proje seç</option></select><a class="btn-secondary" id="v1-manage-project" href="/projects">Proje verilerini yönet</a></div>
  <div id="v1-provider-error" class="v1-provider-error" hidden></div>
  <div id="v1-provider-context" class="v1-provider-context" hidden>
    <div class="v1-provider-facts" id="v1-provider-facts"></div>
    <div class="v1-provider-workflow"><label>Seed<input id="v1-provider-seed" type="number" min="0" value="123"></label><button class="btn-secondary" id="v1-provider-preview" type="button">Doğrulanmış önizleme</button><span id="v1-provider-preview-state">Önizleme gerekli</span></div>
    <details id="v1-requirements"><summary>Veri yeterliliği ve gereksinimler</summary><div id="v1-requirement-list"></div></details>
    <div id="v1-geometry-status"></div>
    <section id="v1-project-result" hidden>
      <div id="v1-project-result-summary"></div>
      <div id="v1-project-water-accounting"></div>
      <div id="v1-project-annual-budget"></div>
      <div id="v1-project-warnings"></div>
      <div id="v1-project-monthly"></div>
      <div id="v1-project-crops"></div>
      <div id="v1-project-units"></div>
      <details><summary>Provenance ve teknik bağlam</summary><pre id="v1-project-provenance"></pre></details>
    </section>
    <details id="v1-project-history"><summary>Proje analiz geçmişi</summary><div id="v1-project-history-list"></div></details>
  </div>
</aside>'''
                html = html.replace(marker, f'{marker}\n    {boundary}\n    {link}\n    {provider}', 1)
                html = html.replace('</head>', '<link rel="stylesheet" href="/projects/assets/v1-provider.css">\n</head>', 1)
                html = html.replace('</body>', '<script src="/projects/assets/v1-provider.js"></script>\n</body>', 1)
                response.set_data(html)
        return response

    app.register_blueprint(pages)
