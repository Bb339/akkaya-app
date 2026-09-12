"""Structural WGS84 validation only; no topology engine or area estimation."""
import math
from typing import Any


def geometry_error(geometry: Any) -> str | None:
    if geometry is None:
        return None
    if not isinstance(geometry, dict):
        return "Geometry must be an object."

    def position(value: Any) -> bool:
        return (isinstance(value, list) and 2 <= len(value) <= 3
                and all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in value)
                and abs(value[0]) <= 180 and abs(value[1]) <= 90)

    def line(value: Any) -> bool:
        return isinstance(value, list) and len(value) >= 2 and all(position(p) for p in value)

    def polygon(value: Any) -> bool:
        return (isinstance(value, list) and bool(value) and all(line(r) and len(r) >= 4 and r[0] == r[-1] for r in value))

    kind, coords = geometry.get("type"), geometry.get("coordinates")
    validators = {"Point": position, "LineString": line, "Polygon": polygon,
                  "MultiPoint": lambda c: isinstance(c, list) and bool(c) and all(position(p) for p in c),
                  "MultiLineString": lambda c: isinstance(c, list) and bool(c) and all(line(p) for p in c),
                  "MultiPolygon": lambda c: isinstance(c, list) and bool(c) and all(polygon(p) for p in c)}
    if kind not in validators:
        return "Unsupported geometry type."
    if not validators[kind](coords):
        return "Invalid coordinates, ring closure or WGS84 bounds."
    return None
