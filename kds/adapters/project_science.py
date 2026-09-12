"""Translate stored project data into canonical values and legacy-shaped views."""
from hashlib import sha256
import json
from pathlib import Path
from kds.science.contract import CandidateOption, FrozenValue, ScientificInputBundle


def data_hash(document):
    return sha256(json.dumps({k:v for k,v in document.items() if k not in ('runs', 'imports')},
                            ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()


def verify_reference_document(document):
    import app
    from .akkaya_demo import build_demo
    reference = build_demo(app.DATA_DIR)
    for key in ('analysis_units', 'crops', 'economics', 'water_budget'):
        if document[key] != reference[key]:
            raise ValueError(f'Referans proje {key} verisi değişmiş; açık bilimsel girdileri yeniden yükleyin.')
    metadata = json.loads((Path(__file__).with_name('reference_manifest.json')).read_text(encoding='utf-8'))
    for name, expected in metadata['input_hashes'].items():
        path = Path(app.__file__).parent / name
        if not path.is_file() or sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f'Referans ek bilimsel kaynak değişmiş: {name}')


def candidate_from_row(row):
    water, profit = float(row['water_m3_da']), float(row['profit_tl_da'])
    return CandidateOption(str(row['parcel_id']), str(row['candidate_crop']), water, profit,
                           profit/water if water else 0., bool(row['is_feasible_under_current_quota']),
                           None, None, None, None, FrozenValue.of(row))


def build_bundle(document, configuration):
    import pandas as pd
    from .scientific_reference import snapshot
    extra = document.get('scientific_inputs', {})
    if document.get('metadata', {}).get('source_version') == 'v1.0.0-thesis-final' and not extra:
        verify_reference_document(document)
        resources = snapshot()
        candidates = tuple(candidate_from_row(r) for r in resources['candidate_options'].copy().to_dict('records'))
    else:
        resources, candidates = generic_resources(document)
    env = resources['environment'].copy()
    provenance = dict(source_version=document['metadata'].get('source_version', 'project-explicit'),
                      source_commit=document['metadata'].get('source_commit'),
                      resource_hashes={k:v.digest for k,v in resources.items()})
    return ScientificInputBundle(document['project']['id'], document['project']['planning_year'], data_hash(document),
        FrozenValue.of(document['analysis_units']), FrozenValue.of(document['crops']), FrozenValue.of(document['economics']),
        FrozenValue.of(document['water_budget']), candidates, resources['irrigation_map'],
        FrozenValue.of(env.get('monthly_climate', pd.DataFrame())), resources['suitability_map'], resources['rotation'],
        FrozenValue.of({'objective': configuration['objective'], 'weights': 'thesis-engine-unchanged'}),
        FrozenValue.of(configuration), tuple(resources.items()), FrozenValue.of(provenance))


def generic_resources(document):
    import app
    import pandas as pd
    from .scientific_reference import READERS, OPTIONAL
    extra = document['scientific_inputs']
    unit_map = {u['external_id']:u for u in document['analysis_units']}
    total_area = sum(u['area_da'] for u in unit_map.values())
    budget = document['water_budget']['amount'] * (1e6 if document['water_budget']['unit']=='hm3' else 1)
    units = []
    for uid,u in unit_map.items():
        p = extra['unit_parameters'][uid]
        units.append(dict(id=uid, name=u.get('name') or uid, area_da=u['area_da'], current_crop=u['current_crop'],
                          water_m3=p['current_water_m3'], profit_tl=p['current_profit'], parcel_type=p['parcel_type'],
                          village=u.get('village', ''), district=document['project'].get('province_or_region',''),
                          soil={'class':p['soil_class']}, lcc=p['soil_class']))
    rows, candidates = [], []
    for c in extra['candidates']:
        u = unit_map[c['analysis_unit_id']]; area=u['area_da']; quota=budget*area/total_area
        water,profit=c['water_requirement_m3_da'],c['profit_per_da']
        row=dict(parcel_id=u['external_id'], candidate_crop=c['crop'], candidate_crop_id=app.canonical_crop_key(c['crop']),
                 candidate_crop_norm=app.canonical_crop_key(c['crop']), current_crop=u['current_crop'], area_da=area,
                 water_m3_da=water, profit_tl_da=profit, water_m3_total=water*area, profit_tl_total=profit*area,
                 current_quota_m3=quota, quota_area_fair_per_da_m3=quota, yield_ton_da=c['yield_ton_da'],
                 is_feasible_under_current_quota=int(water*area<=quota), village=u.get('village',''),
                 irrigation_text=extra['irrigation'][c['crop']]['default'])
        rows.append(row)
        candidates.append(CandidateOption(u['external_id'],c['crop'],water,profit,profit/water,water*area<=quota,
                          c['allowed'],c['rotation_status'],c['suitability'],c.get('risk'),FrozenValue.of({'source':'project-explicit'})))
    env = {k:pd.DataFrame(v) for k,v in extra.get('seasonal_resources',{}).items()}
    env['climate'] = env.get('monthly_climate', pd.DataFrame()).copy()
    catalog = {app.normalize_crop_key(c['name']):dict(name=c['name'],category=c.get('crop_group','')) for c in document['crops']}
    values = {k:{} for k in READERS}
    values.update({k:{} for k in OPTIONAL})
    values.update(units=units,crop_catalog=catalog,candidate_options=pd.DataFrame(rows),environment=env,
                  crop_table=pd.DataFrame(document['crops']),unit_summary=pd.DataFrame(),
                  rotation=pd.DataFrame(extra.get('rotation_rules',[])), crop_families=extra.get('crop_families',{}),
                  irrigation_map=extra['irrigation'],irrigation_annotations=extra['irrigation'],
                  calendar=extra.get('calendar',{}),calendar_annotations=extra.get('calendar',{}),
                  orchard_interrow=pd.DataFrame(),suitability_map={})
    return {k:FrozenValue.of(v) for k,v in values.items()}, tuple(candidates)
