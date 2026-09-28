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
        """Expose the workspace link without mutating the frozen V1 artifact."""
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
                response.set_data(html.replace(marker, f'{marker}\n    {boundary}\n    {link}', 1))
        return response

    app.register_blueprint(pages)
