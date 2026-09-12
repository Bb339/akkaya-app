from dataclasses import dataclass, field
from typing import Any
from .validation import safe_id, required, number, ValidationError


@dataclass
class AnalysisUnit:
    id: str
    project_id: str
    external_id: str
    area_da: float
    current_crop: str
    name_or_code: str = ""
    settlement: str = ""
    irrigation_method: str = ""
    latitude: float | None = None
    longitude: float | None = None
    geometry: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        safe_id(self.id)
        safe_id(self.project_id)
        self.external_id = required(self.external_id, "external_id")
        self.current_crop = required(self.current_crop, "current_crop")
        if number(self.area_da, "area_da", 0) == 0:
            raise ValidationError("area_da", "Area must be positive.")
        for name, limit in (("latitude", 90), ("longitude", 180)):
            value = getattr(self, name)
            if value is not None and abs(number(value, name)) > limit:
                raise ValidationError(name, f"Must be between {-limit} and {limit}.")
