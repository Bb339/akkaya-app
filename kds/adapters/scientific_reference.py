"""All thesis resource names and filesystem knowledge terminate here."""
import json
import hashlib
import multiprocessing
from functools import lru_cache
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
    'water_allocation_context': 'build_water_allocation_logic',
}
OPTIONAL = {
    'calendar_annotations': 's1_crop_calendar_rules.json',
    'season_annotations': 'scenario1_crop_calendar.json',
    'irrigation_annotations': 'crop_irrigation_map.json',
    'village_patterns': 'village_crop_patterns.json',
    'district_patterns': 'district_crop_patterns.json',
    'orchard_interrow': 'orchard_interrow_alternatives.csv',
}
PARAMETERS = ('fallback_crop_parameters', 'candidate_provenance')
COMPUTED = ('regional_candidate_options',)


def read_optional(name, fresh=False):
    import app
    import pandas as pd
    if name == 'regional_candidate_options':
        return app.load_matrix_candidates().copy()
    if name in PARAMETERS:
        value = json.loads(Path(__file__).with_name('reference_parameters.json').read_text(encoding='utf8'))[name]
        if name == 'fallback_crop_parameters':
            return {app.normalize_crop_key(k):v for k,v in value.items()}
        return value
    path = app.DATA_DIR / OPTIONAL[name]
    if not path.exists():
        return pd.DataFrame() if path.suffix == '.csv' else {}
    return pd.read_csv(path) if path.suffix == '.csv' else (json.loads(path.read_text(encoding='utf-8-sig')) if fresh else app.load_json(path))


def _snapshot_local():
    import app
    from kds.science.providers import LegacyReferenceProvider, using_provider
    with using_provider(LegacyReferenceProvider()):
        values = {name: FrozenValue.of(getattr(app, reader)()) for name, reader in READERS.items()}
        values.update({name: FrozenValue.of(read_optional(name, fresh=True)) for name in (*OPTIONAL, *PARAMETERS, *COMPUTED)})
    return values


def _snapshot_worker(connection):
    try:
        connection.send(('ok',tuple(_snapshot_local().items())))
    except Exception as exc:
        connection.send(('error',f'{type(exc).__name__}: {exc}'))
    finally:
        connection.close()


@lru_cache(maxsize=2)
def _reference_values(source_digest):
    # Cache only immutable reference values. Never cache a user's project state.
    context=multiprocessing.get_context('spawn')
    receiving,sending=context.Pipe(duplex=False)
    process=context.Process(target=_snapshot_worker,args=(sending,),daemon=True)
    process.start();sending.close()
    try:
        if not receiving.poll(120):
            raise TimeoutError('Reference data preparation timed out.')
        status,value=receiving.recv()
        if status!='ok':
            raise ValueError(value)
        return value
    finally:
        receiving.close();process.join(timeout=2)
        if process.is_alive():
            process.terminate();process.join(timeout=5)


def snapshot():
    # Reading legacy loaders can mutate their JSON cache. Keep that preparation
    # outside the serving process as well as the optimization itself.
    import app
    manifest=json.loads(Path(__file__).with_name('reference_manifest.json').read_text(encoding='utf8'))
    hashes={name:hashlib.sha256((Path(app.__file__).parent/name).read_bytes()).hexdigest()
            for name in manifest['input_hashes']}
    hashes['engine']=hashlib.sha256(Path(app.__file__).read_bytes()).hexdigest()
    hashes['reference_parameters']=hashlib.sha256(Path(__file__).with_name('reference_parameters.json').read_bytes()).hexdigest()
    digest=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()
    return dict(_reference_values(digest))
