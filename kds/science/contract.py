"""Deeply immutable, path-free values; mutable engine views are fresh copies."""
from dataclasses import dataclass
import hashlib
import json
import math


def pack(value):
    import pandas as pd
    if isinstance(value, pd.DataFrame):
        return {'$table': pack(value.to_dict(orient='split')), '$dtypes': [str(t) for t in value.dtypes]}
    if isinstance(value, dict):
        return {'$map': [[pack(k), pack(v)] for k, v in value.items()]}
    if isinstance(value, tuple):
        return {'$tuple': [pack(v) for v in value]}
    if isinstance(value, list):
        return [pack(v) for v in value]
    if hasattr(value, 'item'):
        return pack(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return {'$float': str(value)}
    return value


def unpack(value):
    if isinstance(value, list):
        return [unpack(v) for v in value]
    if isinstance(value, dict):
        if '$table' in value:
            import pandas as pd
            data = unpack(value['$table'])
            frame = pd.DataFrame(data['data'], columns=data['columns'], index=data['index'])
            return frame.astype(dict(zip(data['columns'], value['$dtypes'])))
        if '$map' in value:
            return {unpack(k): unpack(v) for k, v in value['$map']}
        if '$tuple' in value:
            return tuple(unpack(v) for v in value['$tuple'])
        if '$float' in value:
            return float(value['$float'])
    return value


@dataclass(frozen=True)
class FrozenValue:
    encoded: str

    @classmethod
    def of(cls, value):
        return cls(json.dumps(pack(value), ensure_ascii=False, allow_nan=False, separators=(',', ':')))

    def copy(self):
        return unpack(json.loads(self.encoded))

    @property
    def digest(self):
        return hashlib.sha256(self.encoded.encode()).hexdigest()


@dataclass(frozen=True)
class CandidateOption:
    analysis_unit_id: str
    crop: str
    water_requirement_m3_da: float
    profit_per_da: float
    water_productivity: float
    quota_compatible: bool
    allowed: bool | None
    rotation_status: str | None
    suitability: float | None
    risk: float | None
    metadata: FrozenValue


@dataclass(frozen=True)
class ScientificInputBundle:
    project_id: str
    planning_year: int
    data_version: str
    analysis_units: FrozenValue
    crop_parameters: FrozenValue
    economics: FrozenValue
    water_budget: FrozenValue
    candidates: tuple[CandidateOption, ...]
    irrigation_parameters: FrozenValue
    climate_references: FrozenValue
    soil_suitability: FrozenValue
    rotation_rules: FrozenValue
    objective_configuration: FrozenValue
    algorithm_configuration: FrozenValue
    resources: tuple[tuple[str, FrozenValue], ...]
    provenance: FrozenValue

