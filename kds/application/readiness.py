"""Fail closed before invoking any legacy fallback branch."""
import math
from collections import Counter
from kds.imports.mapping import key as identity_key
from kds.domain.water_data import authority_snapshot
from kds.domain.economic_data import authority_snapshot as economic_authority_snapshot
from kds.domain.crop_parameters import (
    CROP_PARAMETER_DATA_TYPES, authority_snapshot as crop_parameter_authority_snapshot,
    resolution_for,
)


def positive(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def _active_contract_datasets(document, data_type):
    store = document.get('crop_parameter_data', {})
    ids = [dataset_id for key,dataset_id in store.get('active', {}).items() if key.startswith(data_type+'|')]
    return [store.get('datasets', {}).get(dataset_id, {}) for dataset_id in ids]


def _parameter_and_phenology_readiness(document, demo):
    """Expose data-contract truth without connecting new datasets to the engine."""
    import app
    crops = document.get('crops', [])
    runtime = [(app.canonical_crop_key(c['name']), app.normalize_crop_key(c['name'])) for c in crops]
    legacy_direct_by_crop = {}
    if demo:
        legacy_params = app.load_enhanced_frames().get('crop_params')
        legacy_keys = ({app.normalize_crop_key(v) for v in legacy_params['crop']}
                       if legacy_params is not None else set())
        legacy_direct_by_crop = {crop_id: normalized in legacy_keys for crop_id, normalized in runtime}
    active_parameters = _active_contract_datasets(document, 'crop_water_parameters')
    resolutions = []
    if active_parameters:
        records = {r['runtime_crop_id']: r for d in active_parameters for r in d.get('records', [])}
        for crop_id, normalized in runtime:
            record = records.get(crop_id)
            resolutions.append({
                'runtime_crop_id': crop_id,
                'resolution_status': record.get('resolution_status') if record else 'MISSING',
                'resolved_parameter_identity': record.get('parameter_crop_id') if record else None,
                # Contract imports are deliberately disconnected in Phase 7.  This
                # flag therefore describes the unchanged legacy engine path.
                'legacy_generic_fallback': not legacy_direct_by_crop.get(crop_id, False),
                'verified_parameter_ready': bool(record and record.get('verified_for_pilot')),
                'engine_connected': False,
            })
    elif demo:
        parameter_ids = {app.normalize_crop_key(v).replace('_','') for v in legacy_params['crop']} if legacy_params is not None else set()
        for crop_id, normalized in runtime:
            resolutions.append(resolution_for(crop_id, parameter_ids,
                                              legacy_direct_match=legacy_direct_by_crop[crop_id],
                                              parameter_authority='ASSUMED'))
    else:
        resolutions = [resolution_for(crop_id, set(), legacy_direct_match=False,
                                      parameter_authority='UNKNOWN') for crop_id,_ in runtime]
    parameter = {
        'runtime_crop_count': len(runtime),
        'exact_parameter_count': sum(r['resolution_status']=='EXACT' for r in resolutions),
        'reviewed_alias_count': sum(r['resolution_status']=='REVIEWED_ALIAS' for r in resolutions),
        'legacy_fallback_count': sum(bool(r['legacy_generic_fallback']) for r in resolutions),
        'ambiguous_count': sum(r['resolution_status']=='AMBIGUOUS' for r in resolutions),
        'missing_count': sum(r['resolution_status']=='MISSING' for r in resolutions),
        'verified_parameter_count': sum(bool(r['verified_parameter_ready']) for r in resolutions),
        'identity_resolved_count': sum(r['resolution_status'] in {'EXACT','REVIEWED_ALIAS'} for r in resolutions),
        'engine_connected': False,
        'resolutions': resolutions,
    }
    active_phenology = _active_contract_datasets(document, 'crop_phenology')
    phenology_records = [r for d in active_phenology for r in d.get('records', [])]
    verified = {r['runtime_crop_id'] for r in phenology_records if r.get('verified_for_pilot') and
                ((r.get('mode')=='YEAR_SPECIFIC' and r.get('planting_date') and r.get('harvest_date')) or
                 (r.get('mode')=='CLIMATOLOGICAL_WINDOW' and r.get('planting_window_start') and r.get('planting_window_end') and r.get('harvest_window_start') and r.get('harvest_window_end')))}
    planting = {r['runtime_crop_id'] for r in phenology_records if r.get('verified_for_pilot') and (r.get('planting_date') or (r.get('planting_window_start') and r.get('planting_window_end')))}
    harvest = {r['runtime_crop_id'] for r in phenology_records if r.get('verified_for_pilot') and (r.get('harvest_date') or (r.get('harvest_window_start') and r.get('harvest_window_end')))}
    phenology = {
        'runtime_crop_count': len(runtime),
        'verified_planting_count': len(planting), 'verified_harvest_count': len(harvest),
        'verified_complete_count': len(verified),
        'assumed_count': len({r['runtime_crop_id'] for r in phenology_records if not r.get('verified_for_pilot')}),
        'missing_count': len(runtime)-len(verified), 'engine_connected': False,
        'source_fact': 'Frozen Akkaya runtime/project source data contains no sourced planting or harvest values.' if demo else None,
    }
    pilot_ready = (parameter['ambiguous_count']==0 and parameter['missing_count']==0 and
                   parameter['verified_parameter_count']==len(runtime) and phenology['verified_complete_count']==len(runtime))
    pilot = {
        'status': 'PILOT_READY' if pilot_ready else 'PILOT_DATA_NOT_READY',
        'demo_status': 'DEMO_READY' if demo else 'PROJECT_DATA_REVIEW_REQUIRED',
        'blocking_reasons': ([] if pilot_ready else [
            reason for condition,reason in (
                (parameter['ambiguous_count']>0, 'ambiguous crop parameter resolution'),
                (parameter['missing_count']>0, 'missing crop parameter resolution'),
                (parameter['verified_parameter_count']<len(runtime), 'verified parameter coverage incomplete'),
                (phenology['verified_complete_count']<len(runtime), 'verified phenology coverage incomplete')) if condition]),
        'engine_connected': False,
    }
    return parameter, phenology, pilot


def readiness(document):
    units, crops, economics = (document[n] for n in ('analysis_units', 'crops', 'economics'))
    year = document['project']['planning_year']
    budget = document['water_budget']
    extra = document.get('scientific_inputs', {})
    issues = []
    def issue(code, message, scenarios=('S1', 'S2'), severity='error'):
        issues.append(dict(code=code, message=message, scenarios=list(scenarios), severity=severity))
    if not units:
        issue('units', 'Analiz birimi bulunmuyor; alan ve mevcut ürün verisi yükleyin.')
    if any(not positive(u['area_da']) for u in units):
        issue('area', 'Bütün analiz birimlerinin alanı pozitif olmalıdır.')
    names = {c['name'] for c in crops}
    catalog_identities={identity_key(name) for name in names}
    missing = sorted({u['current_crop'] for u in units if identity_key(u['current_crop']) not in catalog_identities})
    if not crops or missing:
        issue('crops', 'Mevcut ürün/katalog eşleşmesi eksik: ' + ', '.join(missing))
    economic_names = {e['crop_name'] for e in economics if e['year'] == year}
    if names - economic_names or not economics:
        issue('economics', 'Planlama yılı ekonomik verisi eksik: ' + ', '.join(sorted(names-economic_names)))
    if any(e.get('currency')!='TRY' for e in economics if e['year']==year):
        issue('currency', 'Mevcut bilimsel motor TRY/TL kullanır; başka para birimi veya belirsiz para birimi sessizce dönüştürülmez.')
    incomplete_economics = sorted(e['crop_name'] for e in economics if e.get('year')==year and e.get('yield_per_da') is None)
    if incomplete_economics:
        issue('economic_completeness', 'Verim/brüt hasılat tamamlığı eksik ürünler: '+', '.join(incomplete_economics), severity='warning')
    if not positive(budget.get('amount')) or budget.get('kind') == 'unknown':
        issue('budget', 'Miktarı ve türü belirlenmiş su bütçesi gerekli.')
    if budget.get('kind') == 'calculated_reference':
        issue('reference_budget', 'Su bütçesi calculated_reference: hesaplanmış talep; ölçülmüş tahsis değildir.', severity='warning')
    geometry_count = sum(bool(u.get('geometry')) for u in units)
    if geometry_count < len(units):
        issue('geometry', f'Geometri {geometry_count}/{len(units)} birimde mevcut; analiz için opsiyoneldir.', severity='warning')
    demo = document.get('metadata', {}).get('source_version') == 'v1.0.0-thesis-final'
    if demo and not extra:
        from kds.adapters.project_science import verify_reference_document
        try:
            verify_reference_document(document)
        except ValueError as exc:
            issue('reference_integrity', str(exc))
        issue('reference_assumptions', 'Tez referansı proxy Kc/toprak/iklim, bölgesel aday genişletme ve sezon tamamlama kurallarını içerir; davranış eşitliği amacıyla açıkça korunur.', severity='warning')
    else:
        import app
        from kds.adapters.project_catalog import project_catalog_scope
        with project_catalog_scope(crops):
            unsupported=[c for c in names if not app.is_annual_field_vegetable_candidate(c) and app.canonical_crop_key(c) not in app.PERENNIAL_CROPS]
        if unsupported:
            issue('crop_rules', 'Mevcut motorun ürün grubu kuralları bu adlar için doğrulanmamış: '+', '.join(sorted(unsupported)))
        candidates = extra.get('candidates', [])
        if not candidates:
            issue('candidates', 'Birim × ürün düzeyinde açık aday su/kâr verileri gerekli; otomatik değer üretilmez.')
        # Generic projects have no regional expansion source. Each unit must
        # still have its explicit current option, including perennial locks.
        pairs = {(c.get('analysis_unit_id'), c.get('crop')) for c in candidates}
        required = {(u['external_id'], c) for u in units for c in names}
        current={(u['external_id'],u['current_crop']) for u in units}
        approved={(c.get('analysis_unit_id'),c.get('crop')) for c in candidates if c.get('allowed') is True}
        if pairs-required or current-approved:
            issue('candidate_coverage', f'Mevcut ürünün onaylı adayı her birimde gerekli: {len(current-approved)} eksik; {len(pairs-required)} bilinmeyen eşleşme.')
        if len(pairs) != len(candidates):
            issue('duplicate_candidates', 'Tekrarlanan birim/ürün adayı var.')
        for c in candidates:
            if not all(positive(c.get(k)) for k in ('water_requirement_m3_da', 'profit_per_da', 'yield_ton_da')):
                issue('candidate_values', 'Her aday için pozitif, sonlu brüt su, net kâr ve verim gerekli.'); break
            if type(c.get('allowed')) is not bool or not positive(c.get('suitability')) or c['suitability']>1 or not c.get('rotation_status'):
                issue('candidate_constraints', 'Adaylarda açık allowed, suitability (0–1) ve rotation_status alanları gerekli.'); break
        params = extra.get('unit_parameters', {})
        for u in units:
            p = params.get(u['external_id'], {})
            if not all(positive(p.get(k)) for k in ('current_water_m3', 'current_profit')) or not p.get('soil_class') or p.get('parcel_type') not in ('field', 'vegetable', 'orchard'):
                issue('unit_parameters', f"{u['external_id']}: mevcut su/kâr, toprak sınıfı ve parsel türü gerekli.")
        irrig = extra.get('irrigation', {})
        for c in crops:
            if not all(positive(c.get(k)) for k in ('kc_initial', 'kc_mid', 'kc_end', 'stage_initial_days', 'stage_development_days', 'stage_mid_days', 'stage_late_days')):
                issue('phenology', f"{c['name']}: Kc ve fenoloji evreleri eksik.")
            info = irrig.get(c['name'], {})
            if not positive(info.get('efficiency')) or info.get('efficiency', 2) > 1 or not info.get('default'):
                issue('irrigation', f"{c['name']}: kaynaklı sulama yöntemi ve 0–1 arası randıman gerekli.")
        # S2 consumes calibrated seasonal observations and separate constraint tables.
        env = extra.get('seasonal_resources', {})
        for key in ('s2', 'parcels', 'reservoir', 'delivery', 'crop_params', 'monthly_climate', 'water_quality', 'soil_params', 'crop_suitability', 'irrigation_methods'):
            if not env.get(key):
                issue('seasonal_'+key, f'S2 için {key} bilimsel tablosu gerekli.', ('S2',))
        if not extra.get('rotation_rules') or not extra.get('crop_families'):
            issue('rotation', 'S2 için ürün aileleri ve rotasyon kısıtları gerekli.', ('S2',))
        seasonal = env.get('s2', [])
        coverage = {(r.get('parcel_id'), r.get('crop'), r.get('season')) for r in seasonal if r.get('year') == year}
        expected = {(u['external_id'], c, s) for u in units for c in names for s in ('primary', 'secondary')}
        if coverage != expected or any(not all(positive(r.get(k)) for k in ('area_da', 'water_m3_calib_gross', 'profit_tl')) for r in seasonal):
            issue('seasonal_coverage', 'S2: planlama yılında her birim/ürün için primary ve secondary alan/su/kâr gözlemi gerekir; başka sezondan veya bölge ortalamasından tamamlanmaz.', ('S2',))
        from kds.science.validation import seasonal_issues
        for message in seasonal_issues(document):
            issue('seasonal_validation', message, ('S2',))
    scenarios = {}
    for scenario in ('S1', 'S2'):
        relevant = [i for i in issues if scenario in i['scenarios']]
        status = 'NOT_READY' if any(i['severity']=='error' for i in relevant) else 'READY_WITH_WARNINGS' if relevant else 'READY'
        scenarios[scenario] = dict(status=status, issues=relevant)
    parameter_readiness, phenology_readiness, pilot_readiness = _parameter_and_phenology_readiness(document, demo)
    return dict(project_id=document['project']['id'], scenarios=scenarios,
        scientific_data=dict(catalog_kc_complete=sum(all(positive(c.get(k)) for k in ('kc_initial','kc_mid','kc_end')) for c in crops),
                             catalog_phenology_complete=sum(all(positive(c.get(k)) for k in ('stage_initial_days','stage_development_days','stage_mid_days','stage_late_days')) for c in crops),
                             confidence_levels=dict(Counter(c.get('confidence_level') or 'unspecified' for c in crops)),
                             parameter_source='verified supplementary thesis tables' if demo and not extra else 'project-explicit',
                             raw_candidate_count=document.get('metadata',{}).get('references',{}).get('raw_candidate_rows') if demo and not extra else len(extra.get('candidates',[])),
                             unit_contracts=dict(
                                 reservoir_irrigation='m3/month; calendar_month',
                                 delivery_capacity='m3/month; calendar_month',
                                 water_quality_ec='dS/m; calendar_month',
                                 implicit_legacy_units='Missing unit/period fields use the canonical values above; conflicting explicit values are rejected.')),
        counts=dict(
        analysis_units=len(units), crops=len(crops), total_area_da=sum(u['area_da'] for u in units),
        economics_covered=len(names & economic_names), geometry_covered=geometry_count),
        water_budget=budget, water_data_authority=authority_snapshot(document),
        economic_data_authority=economic_authority_snapshot(document),
        economic_data_reanalysis=document.get('economic_data',{}).get('reanalysis',{}),
        crop_parameter_readiness=parameter_readiness,
        phenology_readiness=phenology_readiness,
        pilot_readiness=pilot_readiness,
        crop_parameter_data_authority=crop_parameter_authority_snapshot(document),
        crop_parameter_reanalysis=document.get('crop_parameter_data',{}).get('reanalysis',{}),
        imports=[dict(id=k, status=v.get('status')) for k,v in document['imports'].items()])
