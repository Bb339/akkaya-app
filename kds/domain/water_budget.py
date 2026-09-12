from dataclasses import dataclass, field
from typing import Any
from .validation import safe_id, number, ValidationError


@dataclass
class WaterBudget:
    project_id: str
    amount: float
    unit: str
    kind: str = "unknown"
    period: str = "annual"
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        safe_id(self.project_id)
        number(self.amount, "amount", 0)
        if self.unit not in {"m3", "hm3"}:
            raise ValidationError("water_budget_unit", "Use m3 or hm3 explicitly.")
        if self.kind not in {"measured", "official_allocation", "calculated_reference", "scenario", "unknown"}:
            raise ValidationError("kind", "Unknown water budget kind.")
