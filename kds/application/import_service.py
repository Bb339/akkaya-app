"""Explicit confirmation is the only operation that changes active imported data."""
from dataclasses import asdict
from hashlib import sha256
from pathlib import PurePath
from typing import Any
from uuid import uuid4
from werkzeug.utils import secure_filename
from kds.config import MAX_UPLOAD_BYTES
from kds.data.import_models import ImportBatch, Issue, transition
from kds.data.repositories import ProjectRepository, Document, ConflictError, NotFoundError
from kds.domain.validation import safe_id, utc_now
from kds.imports.mapping import FIELDS, suggest, check_mapping
from kds.imports.parser import parse, ParseError
from kds.imports.service import refresh, preview


class ImportService:
    def __init__(self, repository: ProjectRepository):
        self.repository = repository

    @staticmethod
    def _batch(document: Document, batch_id: str) -> Document:
        safe_id(batch_id)
        if batch_id not in document["imports"]:
            raise NotFoundError("Import batch not found in this project.")
        return document["imports"][batch_id]

    def upload(self, project_id: str, data_type: str, filename: str, content: bytes,
               options: dict[str, Any] | None = None) -> Document:
        self.repository.get(project_id)
        if data_type not in FIELDS:
            raise ValueError("Unsupported data_type.")
        if not content or len(content) > MAX_UPLOAD_BYTES:
            raise ValueError("Upload must contain 1 byte to 10 MiB.")
        filename = secure_filename(filename)
        extension = PurePath(filename).suffix.lower()
        if extension not in {".csv", ".xlsx", ".geojson"}:
            raise ValueError("Unsupported file extension.")
        if data_type == "geometries" and extension != ".geojson":
            raise ValueError("Geometry imports require .geojson.")
        if extension == ".geojson" and data_type not in {"analysis_units", "geometries"}:
            raise ValueError("GeoJSON contains analysis units or geometries only.")
        if options is not None and not isinstance(options, dict):
            raise ValueError("Options must be an object.")
        opts = options or {}
        batch = ImportBatch(uuid4().hex, project_id, data_type, filename, sha256(content).hexdigest(), options=opts).to_dict()
        transition(batch, "uploaded")
        try:
            batch["detected_columns"], batch["rows"] = parse(content, filename, opts)
            transition(batch, "parsed")
            batch["mapping"], _ = suggest(batch["detected_columns"], data_type)
        except ParseError as exc:
            batch["issues"] = [asdict(Issue("ERROR", "malformed_file", str(exc)))]
            batch["validation_summary"] = {"error": 1, "warning": 0, "info": 0}
            transition(batch, "invalid")
        def add(document: Document) -> None:
            for existing in document["imports"].values():
                if (existing["file_hash"], existing["data_type"], existing["options"]) == (batch["file_hash"], data_type, opts):
                    raise ConflictError(f"Duplicate upload; existing batch: {existing['id']}")
            batch["base_revision"] = document["data_revision"]
            if batch["detected_columns"]:
                refresh(batch, document)
            document["imports"][batch["id"]] = batch
        document = self.repository.update(project_id, add)
        return preview(batch, document)

    def get(self, project_id: str, batch_id: str) -> Document:
        document = self.repository.get(project_id)
        return preview(self._batch(document, batch_id), document)

    def map(self, project_id: str, batch_id: str, mapping: dict[str, str], options: dict[str, Any] | None = None) -> Document:
        def change(document: Document) -> None:
            batch = self._batch(document, batch_id)
            if batch["status"] == "applied":
                raise ConflictError("Applied batches are immutable.")
            if not batch["detected_columns"]:
                raise ConflictError("Malformed uploads must be uploaded again after correction.")
            check_mapping(mapping, batch["detected_columns"], batch["data_type"])
            if options is not None:
                if not isinstance(options, dict) or any(k not in {"decimal_separator", "area_unit"} for k in options):
                    raise ValueError("Only decimal_separator and area_unit can change after parsing.")
                batch["options"].update(options)
            batch["mapping"] = dict(mapping)
            batch["base_revision"] = document["data_revision"]
            refresh(batch, document)
        document = self.repository.update(project_id, change)
        return preview(document["imports"][batch_id], document)

    def confirm(self, project_id: str, batch_id: str, acknowledge_warnings: bool = False) -> Document:
        def apply(document: Document) -> None:
            batch = self._batch(document, batch_id)
            if batch["status"] == "applied":
                return
            if batch["base_revision"] != document["data_revision"]:
                raise ConflictError("Active data changed; submit mapping again to refresh preview.")
            if not batch["detected_columns"]:
                raise ConflictError("Malformed upload cannot be confirmed.")
            records = refresh(batch, document)
            if batch["status"] != "ready":
                raise ConflictError("Resolve errors and mapping before confirmation.")
            if batch["validation_summary"]["warning"] and acknowledge_warnings is not True:
                raise ConflictError("Explicitly acknowledge warnings before confirmation.")
            transition(batch, "confirmed")
            if batch["data_type"] == "geometries":
                features = {r["external_id"]: r["geometry"] for r in records}
                for unit in document["analysis_units"]:
                    if unit["external_id"] in features:
                        unit["geometry"] = features[unit["external_id"]]
                        unit["metadata"]["geometry_import_batch"] = batch_id
            else:
                for record in records:
                    record["metadata"]["import_batch_id"] = batch_id
                    record["metadata"]["file_hash"] = batch["file_hash"]
                document[batch["data_type"]] = records
            document["data_revision"] += 1
            document["project"]["updated_at"] = utc_now()
            batch["applied_revision"] = document["data_revision"]
            batch["warnings_acknowledged"] = acknowledge_warnings is True
            transition(batch, "applied")
        document = self.repository.update(project_id, apply)
        return preview(document["imports"][batch_id], document)
