from typing import Any, Callable, Protocol

Document = dict[str, Any]


class ConflictError(ValueError):
    """An existing record or stale import conflicts with this operation."""


class NotFoundError(LookupError):
    """Requested project or batch does not exist."""


class ProjectRepository(Protocol):
    def list_projects(self) -> list[Document]: ...
    def get(self, project_id: str) -> Document: ...
    def create(self, document: Document) -> Document: ...
    def update(self, project_id: str, change: Callable[[Document], None]) -> Document: ...
