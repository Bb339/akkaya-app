"""All thesis resource names and filesystem knowledge terminate here."""
import json
from pathlib import Path
from kds.science.contract import FrozenValue

READERS = {
    'units': 'load_parcels', 'unit_summary': 'load_parcels_csv',
    'crop_catalog': 'load_crop_catalog', 'crop_table': 'load_crops_csv',
    'area_overrides': 'load_area_overrides', 'crop_families': 'load_crop_family_map',
    'irrigation_map': 'load_crop_irrigation_map', 'irrigation_methods': 'load_irrigation_methods',
    'suitability_map': 'load_crop_suitability_map', 'rotation': 'load_rotation_rules',
    'calendar': 'load_s1_crop_calendar_rules', 'environment': 'load_enhanced_frames',
    'candidate_options': 'load_matrix_candidates',
}
OPTIONAL = {
    'calendar_annotations': 's1_crop_calendar_rules.json',
    'season_annotations': 'scenario1_crop_calendar.json',
    'irrigation_annotations': 'crop_irrigation_map.json',
    'village_patterns': 'village_crop_patterns.json',
    'district_patterns': 'district_crop_patterns.json',
    'orchard_interrow': 'orchard_interrow_alternatives.csv',
}


def read_optional(name, fresh=False):
    import app
    import pandas as pd
    path = app.DATA_DIR / OPTIONAL[name]
    if not path.exists():
        return pd.DataFrame() if path.suffix == '.csv' else {}
    return pd.read_csv(path) if path.suffix == '.csv' else (json.loads(path.read_text(encoding='utf-8-sig')) if fresh else app.load_json(path))


def snapshot():
    import app
    from kds.science.providers import LegacyReferenceProvider, using_provider
    with using_provider(LegacyReferenceProvider()):
        values = {name: FrozenValue.of(getattr(app, reader)()) for name, reader in READERS.items()}
        values.update({name: FrozenValue.of(read_optional(name, fresh=True)) for name in OPTIONAL})
    return values
