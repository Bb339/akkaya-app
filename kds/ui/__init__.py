from flask import Blueprint, render_template


def register_project_pages(app):
    pages = Blueprint('project_pages', __name__, url_prefix='/projects',
                      template_folder='templates', static_folder='static', static_url_path='/assets')

    @pages.get('')
    @pages.get('/')
    def index():
        return render_template('projects.html')

    app.register_blueprint(pages)
