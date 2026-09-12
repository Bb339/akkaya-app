from dataclasses import dataclass, field
from datetime import date
from typing import Any
from .validation import safe_id, required, number, ValidationError


@dataclass
class Crop:
    id: str
    project_id: str
    name: str
    crop_group: str = ""
    perennial: bool | None = None
    kc_initial: float | None = None
    kc_mid: float | None = None
    kc_end: float | None = None
    stage_initial_days: float | None = None
    stage_development_days: float | None = None
    stage_mid_days: float | None = None
    stage_late_days: float | None = None
    planting_date: str | None = None
    harvest_date: str | None = None
    source: str = ""
    confidence_level: str = ""
    active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        safe_id(self.id)
        safe_id(self.project_id)
        self.name = required(self.name, "crop_name")
        for name in ("kc_initial", "kc_mid", "kc_end", "stage_initial_days", "stage_development_days", "stage_mid_days", "stage_late_days"):
            value = getattr(self, name)
            if value is not None:
                number(value, name, 0)
                if name.startswith("kc_") and value > 3:
                    raise ValidationError(name, "Kc greater than 3 is not accepted.")
        for name in ("planting_date", "harvest_date"):
            value = getattr(self, name)
            if value:
                try:
                    date.fromisoformat(value)
                except (TypeError, ValueError) as exc:
                    raise ValidationError(name, "Use ISO date YYYY-MM-DD.") from exc
        if self.perennial is not None and not isinstance(self.perennial, bool):
            raise ValidationError("perennial", "Expected boolean or null.")
        if not isinstance(self.active, bool):
            raise ValidationError("active", "Expected boolean.")
