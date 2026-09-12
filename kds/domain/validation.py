"""Shared invariants. No site-specific aliases or defaults belong here."""
import math
import re
from datetime import datetime, timezone
from typing import Any


class ValidationError(ValueError):
    def __init__(self, field: str, message: str):
        self.field = field
        super().__init__(message)


def safe_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", value):
        raise ValidationError("id", "Use 1–64 lowercase letters, digits and hyphens.")
    if value.split("-")[0] in {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(10)), *(f"lpt{i}" for i in range(10))}:
        raise ValidationError("id", "Reserved filesystem name.")
    return value


def required(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(field, "A non-empty text value is required.")
    return value.strip()


def number(value: Any, field: str, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValidationError(field, "A finite numeric value is required.")
    if minimum is not None and value < minimum:
        raise ValidationError(field, f"Must be at least {minimum}.")
    return value


def year(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1900 <= value <= 2200:
        raise ValidationError("year", "Year must be an integer between 1900 and 2200.")
    return value


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
