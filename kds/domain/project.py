from dataclasses import dataclass, field
from .validation import required, safe_id, year, utc_now, ValidationError
from .water_budget import WaterBudget


@dataclass
class Project:
    id: str
    name: str
    planning_year: int
    annual_water_budget: float
    water_budget_unit: str
    description: str = ""
    country: str = ""
    province_or_region: str = ""
    basin_or_irrigation_area: str = ""
    data_source_notes: str = ""
    status: str = "draft"
    owner_id: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        safe_id(self.id)
        self.name = required(self.name, "name")
        year(self.planning_year)
        WaterBudget(self.id, self.annual_water_budget, self.water_budget_unit)
        if self.status not in {"draft", "active", "archived"}:
            raise ValidationError("status", "Expected draft, active or archived.")
