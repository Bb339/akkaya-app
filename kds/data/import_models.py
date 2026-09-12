from dataclasses import dataclass, field, asdict
from typing import Any
from kds.domain.validation import utc_now


@dataclass
class Issue:
    severity: str
    code: str
    message: str
    row: int | None = None
    column: str | None = None
    value: Any = None


@dataclass
class ImportBatch:
    id: str
    project_id: str
    data_type: str
    filename: str
    file_hash: str
    uploaded_at: str = field(default_factory=utc_now)
    status: str = "uploaded"
    detected_columns: list[str] = field(default_factory=list)
    mapping: dict[str, str] = field(default_factory=dict)
    validation_summary: dict[str, int] = field(default_factory=dict)
    issues: list[dict[str, Any]] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)
    base_revision: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def transition(batch: dict[str, Any], status: str) -> None:
    batch["status"] = status
    batch["history"].append({"status": status, "at": utc_now()})
