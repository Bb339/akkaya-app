"""One UTF-8 atomic document per project, including import audit records."""
import json
import os
import tempfile
from pathlib import Path
from typing import Callable
from kds.domain.validation import safe_id
from .locking import exclusive_lock
from .repositories import Document, ConflictError, NotFoundError


class FileProjectStore:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def _path(self, project_id: str) -> Path:
        safe_id(project_id)
        folder = self.root / project_id
        if folder.is_symlink() or not folder.resolve().is_relative_to(self.root):
            raise ValueError("Project path escapes store root.")
        target = folder / "state.json"
        if target.is_symlink():
            raise ValueError("Project documents may not be symlinks.")
        return target

    def _lock_path(self, project_id: str) -> Path:
        safe_id(project_id)
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root / f".{project_id}.lock"

    def list_projects(self) -> list[Document]:
        if not self.root.exists():
            return []
        return [self.get(p.parent.name)["project"] for p in sorted(self.root.glob("*/state.json"))]

    def get(self, project_id: str) -> Document:
        path = self._path(project_id)
        if not path.exists():
            raise NotFoundError("Project not found.")
        return json.loads(path.read_text(encoding="utf-8"))

    def _write(self, path: Path, document: Document) -> None:
        encoded = json.dumps(document, ensure_ascii=False, allow_nan=False, indent=2)
        path.parent.mkdir(parents=True, exist_ok=True)
        name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=".write-", delete=False) as stream:
                name = stream.name
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, path)
        finally:
            if name is not None:
                Path(name).unlink(missing_ok=True)

    def create(self, document: Document) -> Document:
        project_id = document["project"]["id"]
        path = self._path(project_id)
        with exclusive_lock(self._lock_path(project_id)):
            if path.exists():
                raise ConflictError("Project already exists.")
            self._write(path, document)
        return document

    def update(self, project_id: str, change: Callable[[Document], None]) -> Document:
        path = self._path(project_id)
        with exclusive_lock(self._lock_path(project_id)):
            document = self.get(project_id)
            change(document)
            self._write(path, document)
        return document
