from dataclasses import dataclass, field
from typing import Any
from .validation import safe_id, required, year, number, ValidationError


@dataclass
class Economics:
    project_id: str
    crop_name: str
    year: int
    yield_per_da: float | None
    net_profit_per_da: float
    currency: str | None = None
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        safe_id(self.project_id)
        self.crop_name = required(self.crop_name, "crop_name")
        year(self.year)
        if self.yield_per_da is not None:
            number(self.yield_per_da, "yield_per_da", 0)
        number(self.net_profit_per_da, "net_profit_per_da")
        if self.currency is not None and (not isinstance(self.currency, str) or len(self.currency) != 3 or not self.currency.isalpha() or not self.currency.isupper()):
            raise ValidationError("currency", "Use a three-letter uppercase currency code.")
