from pathlib import Path

from flask import Blueprint, abort, render_template, send_from_directory


TEMPLATE_DIR = Path(__file__).resolve().parents[2] / 'docs' / 'data_templates'


def register_project_pages(app):
    pages = Blueprint('project_pages', __name__, url_prefix='/projects',
                      template_folder='templates', static_folder='static', static_url_path='/assets')

    @pages.get('')
    @pages.get('/')
    def index():
        return render_template('projects.html')

    @pages.get('/templates/<filename>')
    def data_template(filename):
        allowed = {path.name for path in TEMPLATE_DIR.glob('*.xlsx')}
        if filename not in allowed:
            abort(404)
        return send_from_directory(TEMPLATE_DIR, filename, as_attachment=True)

    app.register_blueprint(pages)
