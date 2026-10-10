"""Explicit confirmation is the only operation that changes active imported data."""
from dataclasses import asdict
from hashlib import sha256
import json
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
from kds.domain.water_data import WATER_DATA_TYPES, replacement_preview
from kds.domain.economic_data import ECONOMIC_DATA_TYPES, replacement_preview as economic_replacement_preview
from kds.domain.crop_parameters import CROP_PARAMETER_DATA_TYPES, replacement_preview as crop_parameter_replacement_preview
from kds.imports.detection import detect as detect_file


class ImportService:
    def __init__(self, repository: ProjectRepository):
        self.repository = repository

    def detect(self, project_id: str, filename: str, content: bytes,
               options: dict[str, Any] | None = None) -> Document:
        document = self.repository.get(project_id)
        return detect_file(content, secure_filename(filename), options, document.get("project", {}))

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

    def duplicate(self, project_id: str, data_type: str, file_hash: str,
                  options: dict[str, Any] | None = None) -> Document | None:
        document = self.repository.get(project_id)
        opts = options or {}
        for existing in document["imports"].values():
            if (existing["file_hash"], existing["data_type"], existing["options"]) == (file_hash, data_type, opts):
                return preview(existing, document)
        return None

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

    def confirm(self, project_id: str, batch_id: str, acknowledge_warnings: bool = False,
                acknowledge_authority_override: bool = False, override_reason: str | None = None) -> Document:
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
            if batch["data_type"] in WATER_DATA_TYPES:
                replacement = replacement_preview(document, batch["data_type"], records)
                batch["replacement_preview_at_confirmation"] = replacement
                if replacement["requires_authority_override"]:
                    if acknowledge_authority_override is not True or not str(override_reason or "").strip():
                        raise ConflictError("Lower-authority activation requires explicit acknowledgement and a non-empty override reason.")
            if batch["data_type"] in ECONOMIC_DATA_TYPES:
                replacement = economic_replacement_preview(document, batch["data_type"], records)
                batch["replacement_preview_at_confirmation"] = replacement
                if replacement["requires_authority_override"]:
                    if acknowledge_authority_override is not True or not str(override_reason or "").strip():
                        raise ConflictError("Lower-authority economic activation requires explicit acknowledgement and a non-empty override reason.")
            if batch["data_type"] in CROP_PARAMETER_DATA_TYPES:
                replacement = crop_parameter_replacement_preview(document, batch["data_type"], records)
                batch["replacement_preview_at_confirmation"] = replacement
                if replacement["requires_authority_override"]:
                    if acknowledge_authority_override is not True or not str(override_reason or "").strip():
                        raise ConflictError("Lower-authority crop parameter activation requires explicit acknowledgement and a non-empty override reason.")
            transition(batch, "confirmed")
            if batch['data_type'] in WATER_DATA_TYPES:
                from kds.imports.water_tables import apply_water_records
                apply_water_records(document, batch, records, str(override_reason).strip() if override_reason else None)
            elif batch['data_type'] in ECONOMIC_DATA_TYPES:
                from kds.imports.economic_tables import apply_economic_records
                apply_economic_records(document, batch, records, str(override_reason).strip() if override_reason else None)
            elif batch['data_type'] in CROP_PARAMETER_DATA_TYPES:
                from kds.imports.crop_parameter_tables import apply_crop_parameter_records
                apply_crop_parameter_records(document, batch, records, str(override_reason).strip() if override_reason else None)
            elif batch['data_type'] in {'candidates','scientific_inputs','water_budget'}:
                from kds.imports.scientific_tables import apply_records
                apply_records(document, batch, records)
            elif batch["data_type"] == "geometries":
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
            if any(run.get("status") == "completed" for run in document.get("runs", {}).values()):
                previous = document.get("analysis_state", {})
                document["analysis_state"] = {
                    **previous, "requires_reanalysis": True,
                    "trigger_import_batch_id": batch_id,
                    "trigger_data_type": batch["data_type"],
                    "triggered_at": document["project"]["updated_at"],
                }
            batch["warnings_acknowledged"] = acknowledge_warnings is True
            transition(batch, "applied")
        document = self.repository.update(project_id, apply)
        return preview(document["imports"][batch_id], document)


class BulkImportService:
    """Manifest-scoped lifecycle for recoverable multi-file previews."""

    def __init__(self, repository: ProjectRepository):
        self.repository = repository

    @staticmethod
    def manifest_hash(files: list[dict[str, Any]]) -> str:
        canonical = sorted(
            ({"filename": item["filename"], "file_hash": item["file_hash"],
              "options": item.get("options", {})} for item in files),
            key=lambda item: (item["filename"], item["file_hash"],
                              json.dumps(item["options"], sort_keys=True)),
        )
        return sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def find(self, project_id: str, manifest_hash: str) -> Document | None:
        document = self.repository.get(project_id)
        matches = [package for package in document.get("bulk_imports", {}).values()
                   if package["manifest_hash"] == manifest_hash and package.get("status") != "DISCARDED"]
        if not matches:
            return None
        package = max(matches, key=lambda item: (item["created_at"], item["id"]))
        return self._present(package, document, duplicate=True)

    def create(self, project_id: str, manifest_hash: str, items: list[Document],
               duplicate: bool = False) -> Document:
        package_id = uuid4().hex
        created_at = utc_now()
        record = {
            "id": package_id,
            "project_id": project_id,
            "manifest_hash": manifest_hash,
            "created_at": created_at,
            "status": "PREVIEW",
            "items": [{
                "detection": item["detection"],
                "batch_id": (item.get("batch") or {}).get("id"),
                "batch_snapshot": item.get("batch"),
            } for item in items],
        }

        def add(document: Document) -> None:
            document.setdefault("bulk_imports", {})[package_id] = record

        document = self.repository.update(project_id, add)
        return self._present(record, document, duplicate=duplicate)

    def list(self, project_id: str) -> list[Document]:
        document = self.repository.get(project_id)
        packages = sorted(document.get("bulk_imports", {}).values(),
                          key=lambda item: (item["created_at"], item["id"]), reverse=True)
        return [self._summary(package, document) for package in packages]

    def get(self, project_id: str, package_id: str) -> Document:
        safe_id(package_id)
        document = self.repository.get(project_id)
        package = document.get("bulk_imports", {}).get(package_id)
        if package is None:
            raise NotFoundError("Bulk import not found in this project.")
        return self._present(package, document)

    def discard(self, project_id: str, package_id: str) -> Document:
        safe_id(package_id)

        def remove(document: Document) -> None:
            package = document.get("bulk_imports", {}).get(package_id)
            if package is None:
                raise NotFoundError("Bulk import not found in this project.")
            batch_ids = [item.get("batch_id") for item in package["items"] if item.get("batch_id")]
            if any(document.get("imports", {}).get(batch_id, {}).get("status") == "applied"
                   for batch_id in batch_ids):
                raise ConflictError("Applied bulk imports cannot be discarded.")
            other_references = {
                item.get("batch_id")
                for other_id, other in document.get("bulk_imports", {}).items()
                if other_id != package_id and other.get("status") != "DISCARDED"
                for item in other.get("items", [])
            }
            for batch_id in batch_ids:
                if batch_id not in other_references:
                    document.get("imports", {}).pop(batch_id, None)
            package["status"] = "DISCARDED"
            package["discarded_at"] = utc_now()

        document = self.repository.update(project_id, remove)
        return self._present(document["bulk_imports"][package_id], document)

    @staticmethod
    def _stored_batch(package_item: Document, document: Document) -> Document | None:
        batch_id = package_item.get("batch_id")
        batch = document.get("imports", {}).get(batch_id) if batch_id else None
        return batch or package_item.get("batch_snapshot")

    @classmethod
    def _batch(cls, package_item: Document, document: Document) -> Document | None:
        batch_id = package_item.get("batch_id")
        batch = document.get("imports", {}).get(batch_id) if batch_id else None
        if batch is not None:
            result = {key: value for key, value in batch.items() if key != "rows"}
            result["row_count"] = len(batch.get("rows", []))
            result["preview_rows"] = batch.get("rows", [])[:20]
            result["stale"] = batch["status"] != "applied" and batch["base_revision"] != document["data_revision"]
            return result
        return package_item.get("batch_snapshot")

    def _status(self, package: Document, document: Document) -> str:
        if package.get("status") == "DISCARDED":
            return "DISCARDED"
        batches = [self._stored_batch(item, document) for item in package["items"] if item.get("batch_id")]
        if batches and all(batch and batch.get("status") == "applied" for batch in batches):
            return "APPLIED"
        states = [item["detection"].get("state") for item in package["items"]]
        if batches and all(state in {"AUTO_MATCHED", "IGNORED_NOT_RELEVANT"} for state in states):
            return "READY"
        return "PREVIEW"

    def _summary(self, package: Document, document: Document) -> Document:
        status = self._status(package, document)
        detections = [item["detection"] for item in package["items"]]
        batches = [self._stored_batch(item, document) for item in package["items"] if item.get("batch_id")]
        revisions = [batch.get("applied_revision") for batch in batches if batch and batch.get("applied_revision")]
        return {
            "id": package["id"], "project_id": package["project_id"],
            "created_at": package["created_at"], "manifest_hash": package["manifest_hash"],
            "file_count": len(detections),
            "auto_matched": sum(item.get("state") == "AUTO_MATCHED" for item in detections),
            "unsupported": sum(item.get("state") == "UNSUPPORTED" for item in detections),
            "ignored_not_relevant": sum(item.get("state") == "IGNORED_NOT_RELEVANT" for item in detections),
            "review_required": sum(item.get("state") not in {"AUTO_MATCHED", "IGNORED_NOT_RELEVANT"}
                                   for item in detections),
            "detected_domains": sorted({item.get("detected_domain") for item in detections if item.get("detected_domain")}),
            "status": status, "applied": status == "APPLIED",
            "applied_revision": max(revisions) if revisions else None,
            "discarded_at": package.get("discarded_at"),
        }

    def _present(self, package: Document, document: Document, duplicate: bool = False) -> Document:
        summary = self._summary(package, document)
        items = [{"detection": item["detection"], "batch": self._batch(item, document)}
                 for item in package["items"]]
        status = summary["status"]
        message = ("This dataset package has already been applied to the project."
                   if status == "APPLIED" else
                   "An identical validated import already exists. The existing import has been reopened."
                   if duplicate else None)
        return {**summary, "items": items, "duplicate": duplicate, "message": message,
                "active_revision": document.get("data_revision")}
