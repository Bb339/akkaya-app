"""Project/import HTTP boundary. The scientific API remains unchanged."""
import json
from pathlib import Path
from flask import Blueprint, Flask, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge
from kds.config import MAX_UPLOAD_BYTES, project_store_path
from kds.data.project_store import FileProjectStore
from kds.data.repositories import ProjectRepository, ConflictError, NotFoundError
from kds.application.project_service import ProjectService
from kds.application.import_service import ImportService


def register_project_api(app: Flask, repository: ProjectRepository | None = None) -> None:
    if repository is None:
        root = project_store_path().resolve()
        if root.is_relative_to(Path(app.root_path).resolve()):
            raise ValueError("KDS_PROJECT_STORE must be outside the application's public source tree.")
        repository = FileProjectStore(root)
    projects, imports = ProjectService(repository), ImportService(repository)
    blueprint = Blueprint("projects", __name__, url_prefix="/api/v2")

    @blueprint.before_request
    def bound_request():
        if request.method == "POST":
            if request.content_length is None:
                return jsonify(error="Content-Length is required."), 411
            if request.content_length > MAX_UPLOAD_BYTES + 1024 * 1024:
                raise RequestEntityTooLarge()

    @blueprint.errorhandler(ValueError)
    def invalid_request(error):
        return jsonify(error=str(error), field=getattr(error, "field", None)), 400

    @blueprint.errorhandler(ConflictError)
    def conflict(error):
        return jsonify(error=str(error)), 409

    @blueprint.errorhandler(NotFoundError)
    def missing(error):
        return jsonify(error=str(error)), 404

    @blueprint.errorhandler(RequestEntityTooLarge)
    def too_large(error):
        return jsonify(error="Upload exceeds the 10 MiB file limit."), 413

    def body() -> dict:
        value = request.get_json(silent=True)
        if not isinstance(value, dict):
            raise ValueError("Expected a JSON object.")
        return value

    @blueprint.get("/projects")
    def list_projects():
        return jsonify(projects=projects.list())

    @blueprint.post("/projects")
    def create_project():
        try:
            project = projects.create(body())
        except TypeError as exc:
            raise ValueError("Missing required project fields or unknown field names.") from exc
        return jsonify(project=project), 201

    @blueprint.get("/projects/<project_id>")
    def get_project(project_id):
        document = projects.get(project_id)
        return jsonify(project=document["project"], water_budget=document["water_budget"],
                       data_revision=document["data_revision"], metadata=document["metadata"],
                       counts={name: len(document[name]) for name in ("analysis_units", "crops", "economics", "imports")})

    @blueprint.post("/projects/<project_id>/imports")
    def upload(project_id):
        file = request.files.get("file")
        if file is None:
            raise ValueError("A multipart file is required.")
        content = file.stream.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            raise RequestEntityTooLarge()
        options = json.loads(request.form.get("options", "{}"))
        result = imports.upload(project_id, request.form.get("data_type", ""), file.filename or "", content, options)
        return jsonify(result), 201

    @blueprint.get("/projects/<project_id>/imports/<batch_id>")
    def get_import(project_id, batch_id):
        return jsonify(imports.get(project_id, batch_id))

    @blueprint.post("/projects/<project_id>/imports/<batch_id>/mapping")
    def map_import(project_id, batch_id):
        payload = body()
        return jsonify(imports.map(project_id, batch_id, payload.get("mapping"), payload.get("options")))

    @blueprint.post("/projects/<project_id>/imports/<batch_id>/confirm")
    def confirm_import(project_id, batch_id):
        payload = body()
        if payload.get("confirm") is not True:
            raise ValueError("Explicit confirm=true is required.")
        return jsonify(imports.confirm(project_id, batch_id, payload.get("acknowledge_warnings", False)))

    @blueprint.get("/projects/<project_id>/<collection>")
    def get_collection(project_id, collection):
        names = {"analysis-units": "analysis_units", "crops": "crops", "economics": "economics"}
        if collection not in names:
            raise NotFoundError("Collection not found.")
        offset, limit = int(request.args.get("offset", 0)), int(request.args.get("limit", 200))
        if offset < 0 or not 1 <= limit <= 1000:
            raise ValueError("offset >= 0 and 1 <= limit <= 1000 required.")
        rows = projects.get(project_id)[names[collection]]
        return jsonify(items=rows[offset:offset + limit], count=len(rows), offset=offset, limit=limit)

    app.register_blueprint(blueprint)
