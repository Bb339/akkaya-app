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
    from kds.application.optimization import OptimizationApplicationService
    analysis = OptimizationApplicationService(repository)
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

    @blueprint.get("/projects/<project_id>/overview")
    def project_overview(project_id):
        from kds.application.project_overview import overview
        return jsonify(overview(projects.get(project_id)))

    @blueprint.get("/projects/<project_id>/analyses")
    def list_analyses(project_id):
        from kds.application.project_overview import history
        return jsonify(history(projects.get(project_id),int(request.args.get('offset',0)),int(request.args.get('limit',50))))

    @blueprint.get("/projects/<project_id>/readiness")
    def scientific_readiness(project_id):
        return jsonify(analysis.readiness(project_id))

    @blueprint.post("/projects/<project_id>/analyses")
    def run_analysis(project_id):
        result = analysis.run(project_id, body())
        return jsonify(result), 201 if result['status']=='completed' else 422

    @blueprint.get("/projects/<project_id>/analyses/<run_id>")
    def analysis_result(project_id, run_id):
        return jsonify(analysis.get(project_id, run_id))

    @blueprint.get("/projects/<project_id>/scientific-inputs")
    def scientific_inputs(project_id):
        return jsonify(projects.get(project_id).get('scientific_inputs', {}))

    @blueprint.post("/projects/<project_id>/water-budget")
    def save_water_budget(project_id):
        from dataclasses import asdict
        from kds.domain.water_budget import WaterBudget
        payload = body()
        try:
            budget = WaterBudget(project_id=project_id, **payload)
        except TypeError as exc:
            raise ValueError('Use amount, unit, kind and source for water budget.') from exc
        def update(document):
            document['water_budget'] = asdict(budget)
            document['project']['annual_water_budget'] = budget.amount
            document['project']['water_budget_unit'] = budget.unit
            document['data_revision'] += 1
        repository.update(project_id, update)
        return jsonify(analysis.readiness(project_id))

    @blueprint.post("/projects/<project_id>/scientific-inputs")
    def save_scientific_inputs(project_id):
        payload = body()
        allowed = {'candidates','unit_parameters','irrigation','seasonal_resources','rotation_rules','crop_families','calendar'}
        if set(payload)-allowed:
            raise ValueError('Unknown scientific input sections.')
        for key,value in payload.items():
            expected = list if key in ('candidates','rotation_rules') else dict
            if not isinstance(value, expected):
                raise ValueError(key+' has an invalid type.')
        if len(payload.get('candidates', [])) > 20000:
            raise ValueError('At most 20000 explicit candidates are accepted.')
        if any(not isinstance(row,dict) for row in payload.get('candidates', [])):
            raise ValueError('Candidates must be JSON objects.')
        for key in ('unit_parameters','irrigation','calendar'):
            if any(not isinstance(v,dict) for v in payload.get(key,{}).values()):
                raise ValueError(key+' entries must be objects.')
        for rows in payload.get('seasonal_resources',{}).values():
            if not isinstance(rows,list) or any(not isinstance(r,dict) for r in rows):
                raise ValueError('Seasonal resources must contain arrays of row objects.')
        json.dumps(payload, allow_nan=False)
        from kds.science.validation import validate_payload
        validate_payload(payload)
        def update(document):
            document['scientific_inputs'] = payload
            document['data_revision'] += 1
        repository.update(project_id, update)
        return jsonify(analysis.readiness(project_id))

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
        return jsonify(imports.confirm(
            project_id, batch_id, payload.get("acknowledge_warnings", False),
            payload.get("acknowledge_authority_override", False), payload.get("override_reason"),
        ))

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
    from kds.ui import register_project_pages
    register_project_pages(app)
