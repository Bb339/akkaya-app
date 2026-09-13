"""Persisted analysis audit record; scientific snapshots are identified by hash."""
from dataclasses import dataclass, field
from typing import Any, Literal
from .validation import safe_id


@dataclass
class AnalysisRun:
    id: str
    project_id: str
    data_version: str
    scenario: str
    algorithm: str
    seed: int
    configuration: dict[str, Any]
    started_at: str
    provenance: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    completed_at: str | None = None
    status: Literal['running','completed','failed'] = 'running'
    result: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None
    error: str | None = None

    def __post_init__(self):
        safe_id(self.id)
        safe_id(self.project_id)
        if self.scenario not in ('S1','S2') or self.algorithm not in ('GA','ACO','ABC'):
            raise ValueError('Invalid scientific run identity.')
