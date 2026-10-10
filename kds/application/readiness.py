"""Fail closed before invoking any legacy fallback branch."""
from copy import deepcopy
import math
from collections import Counter
from kds.imports.mapping import key as identity_key
from kds.domain.execution_profile import ExecutionProfile, effective_execution_profile
from kds.domain.water_data import authority_snapshot
from kds.domain.economic_data import authority_snapshot as economic_authority_snapshot
from kds.domain.crop_parameters import (
    CROP_PARAMETER_DATA_TYPES, authority_snapshot as crop_parameter_authority_snapshot,
    resolution_for,
)


def positive(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


REFERENCE_AUTHORITIES = {'CALCULATED_REFERENCE', 'ASSUMED'}


def _reference_climate_mode(document):
    """Resolve the legacy reference package's explicit dated climate rows without mutating them."""
    rows = document.get('scientific_inputs', {}).get('seasonal_resources', {}).get('monthly_climate', [])
    if not rows:
        return None
    explicit = {str(row.get('climate_mode') or '').strip().upper() for row in rows}
    explicit.discard('')
    if len(explicit) == 1:
        return next(iter(explicit))
    if explicit:
        return None
    year = int(document['project']['planning_year'])
    row_years = {int(row['year']) for row in rows if row.get('year') is not None}
    periods = {str(row.get('month') or '')[:4] for row in rows}
    return 'YEAR_SPECIFIC' if row_years == {year} and periods == {str(year)} else None


def _reference_demo_projection(document):
    projected = deepcopy(document)
    original_authorities = {}
    replacements = {
        'water_data': 'MEASURED',
        'economic_data': 'OFFICIAL_STATISTICS',
        'crop_parameter_data': 'EXPERT_VALIDATED',
    }
    warnings = ['REFERENCE MODEL / DEMO DATA; not official or verified institutional evidence.']
    for store_name, replacement in replacements.items():
        original_store = document.get(store_name, {})
        projected_store = projected.get(store_name, {})
        active_ids = set(original_store.get('active', {}).values())
        for dataset_id in active_ids:
            original = original_store.get('datasets', {}).get(dataset_id)
            candidate = projected_store.get('datasets', {}).get(dataset_id)
            if not original or not candidate:
                continue
            authority = str(original.get('authority_class') or '').upper()
            original_authorities[str(dataset_id)] = authority
            if authority in REFERENCE_AUTHORITIES:
                candidate['authority_class'] = replacement
                warnings.append(f"{original.get('data_type')} uses {authority} authority in REFERENCE_DEMO.")

    climate = projected.get('scientific_inputs', {}).get('seasonal_resources', {}).get('monthly_climate', [])
    climate_mode = _reference_climate_mode(document)
    if climate and climate_mode:
        required_scope = (document.get('project', {}).get('pilot_geographic_scope') or
                          document.get('metadata', {}).get('pilot_geographic_scope') or 'project')
        expected_units = {str(unit['external_id']) for unit in document.get('analysis_units', [])}
        climate_units = {str(row.get('parcel_id')) for row in climate}
        if climate_units == expected_units:
            for row in climate:
                row.setdefault('climate_mode', climate_mode)
                row.setdefault('geographic_scope', required_scope)
            warnings.append(f"Reference climate mode resolved as {climate_mode} from explicit planning-year dates.")

    return projected, original_authorities, warnings, climate_mode


def _reference_demo_authority_readiness(document, scenario, projection=None):
    """Validate reference data structurally while preserving its non-verified authority labels."""
    from kds.adapters.institutional import verified_readiness

    projected, original_authorities, base_warnings, climate_mode = (
        projection or _reference_demo_projection(document))
    warnings = list(base_warnings)
    climate = projected.get('scientific_inputs', {}).get('seasonal_resources', {}).get('monthly_climate', [])

    result = verified_readiness(projected, scenario)

    # The reference model's annual planning budget and monthly operational series
    # are separate accepted demo quantities.  Their mismatch is disclosed, but it
    # is not a verified-allocation reconciliation blocker in REFERENCE_DEMO.
    reconciliation = [message for message in result['blocking_reasons']
                      if message.startswith('Annual/monthly water supply mismatch:')]
    if reconciliation:
        result['blocking_reasons'] = [message for message in result['blocking_reasons']
                                      if message not in reconciliation]
        warnings.extend(f"Reference/demo limitation: {message}" for message in reconciliation)
        for name in ('annual_water', 'monthly_supply'):
            result['domains'][name].update(
                status='READY', dataset_valid=True, engine_connected=True,
                connection_state='CONNECTED', blocking_reason=None, blocking_reasons=[])

    # Reference climate has explicit planning-year dates but the accepted legacy
    # package predates the institutional climate_mode/scope columns.  Resolve the
    # mode only when every project unit has a complete 12-month planning-year set.
    if climate and climate_mode == 'YEAR_SPECIFIC':
        periods = {}
        for row in climate:
            periods.setdefault(str(row.get('parcel_id')), set()).add(str(row.get('month') or '')[:7])
        expected_periods = {f"{document['project']['planning_year']}-{month:02d}" for month in range(1, 13)}
        expected_units = {str(unit['external_id']) for unit in document.get('analysis_units', [])}
        climate_complete = (set(periods) == expected_units and
                            all(values == expected_periods for values in periods.values()) and
                            all(row.get('source') for row in climate))
        if climate_complete:
            climate_reason = result['domains'].get('climate', {}).get('blocking_reason')
            if climate_reason in result['blocking_reasons']:
                result['blocking_reasons'].remove(climate_reason)
            result['domains']['climate'].update(
                status='READY', dataset_selected=True, dataset_valid=True,
                engine_connected=True, connection_state='CONNECTED',
                blocking_reason=None, blocking_reasons=[], mode=climate_mode,
                geographic_scope=(document.get('project', {}).get('pilot_geographic_scope') or
                                  document.get('metadata', {}).get('pilot_geographic_scope') or 'project'),
                coverage=sorted({period for values in periods.values() for period in values}))
        else:
            warnings.append('Reference climate dates do not provide complete planning-year coverage.')

    # The accepted V1 S2 replay carries its seasonal schedule in scientific_s2;
    # the separate phenology contract is an explicitly ASSUMED reference label
    # set.  Do not recast it as verified dual-season evidence, but keep it as a
    # visible warning once the strict resolver has already proven identity/scope.
    s2_phenology = [message for message in result['blocking_reasons']
                    if message.startswith('S2 verified phenology requires PRIMARY and SECONDARY records')]
    phenology_facts = result.get('domains', {}).get('phenology', {}).get('datasets', [])
    assumed_phenology = any(original_authorities.get(str(fact.get('dataset_id'))) == 'ASSUMED'
                            for fact in phenology_facts)
    if s2_phenology and assumed_phenology:
        result['blocking_reasons'] = [message for message in result['blocking_reasons']
                                      if message not in s2_phenology]
        warnings.append('S2 phenology uses the accepted ASSUMED reference rules; seasonal timing remains sourced from the reference scientific package.')
        result['domains']['phenology'].update(
            status='READY', dataset_valid=True, engine_connected=True,
            connection_state='CONNECTED', blocking_reason=None, blocking_reasons=[])

    result['ready'] = not result['blocking_reasons']

    def restore(fact):
        if not isinstance(fact, dict):
            return
        dataset_id = str(fact.get('dataset_id') or '')
        if dataset_id in original_authorities:
            fact['authority_class'] = original_authorities[dataset_id]

    for domain in result.get('domains', {}).values():
        restore(domain)
        restore(domain.get('dataset'))
        for fact in domain.get('datasets', []):
            restore(fact)
        domain_warnings = []
        facts = [domain.get('dataset'), *domain.get('datasets', [])]
        for fact in facts:
            if isinstance(fact, dict) and fact.get('authority_class') in REFERENCE_AUTHORITIES:
                domain_warnings.append(
                    f"{fact.get('data_type')} authority {fact.get('authority_class')} is accepted with warning for REFERENCE_DEMO only."
                )
        if domain_warnings:
            domain['authority_warning'] = True
            domain['warnings'] = list(dict.fromkeys(domain_warnings))

    def reference_wording(message):
        return (str(message)
                .replace('VERIFIED_INSTITUTIONAL', 'REFERENCE_DEMO')
                .replace('Verified ', 'Reference demo ')
                .replace('verified ', 'reference-demo '))

    result['blocking_reasons'] = [reference_wording(message) for message in result['blocking_reasons']]
    for domain in result.get('domains', {}).values():
        if domain.get('blocking_reason'):
            domain['blocking_reason'] = reference_wording(domain['blocking_reason'])
            domain['blocking_reasons'] = [domain['blocking_reason']]
    result['warnings'] = list(dict.fromkeys([*warnings, *result.get('warnings', [])]))
    result['climate_mode'] = climate_mode
    return result


def _active_contract_datasets(document, data_type):
    store = document.get('crop_parameter_data', {})
    ids = [dataset_id for key,dataset_id in store.get('active', {}).items() if key.startswith(data_type+'|')]
    return [store.get('datasets', {}).get(dataset_id, {}) for dataset_id in ids]


def _readiness_dataset_selection(document, data_type):
    """Select one explicit planning-year/project scope; otherwise fail closed."""
    planning_year = int(document['project']['planning_year'])
    candidates = []
    for dataset in _active_contract_datasets(document, data_type):
        records = dataset.get('records', [])
        years = {int(record['applicable_year']) for record in records if record.get('applicable_year') is not None}
        if years == {planning_year}:
            candidates.append(dataset)
    scopes = sorted({record.get('geographic_scope') for dataset in candidates
                     for record in dataset.get('records', []) if record.get('geographic_scope')})
    configured_scope = (document.get('project', {}).get('pilot_geographic_scope') or
                        document.get('metadata', {}).get('pilot_geographic_scope'))
    if configured_scope:
        selected = [dataset for dataset in candidates if
                    {record.get('geographic_scope') for record in dataset.get('records', [])} == {configured_scope}]
        status = 'SELECTED' if len(selected) == 1 else 'MISSING_CONFIGURED_SCOPE' if not selected else 'AMBIGUOUS_CONFIGURED_SCOPE'
        return selected if status == 'SELECTED' else [], {
            'status': status, 'planning_year': planning_year, 'required_scope': configured_scope,
            'available_scopes': scopes,
        }
    if len(scopes) > 1:
        return [], {'status': 'AMBIGUOUS_SCOPE', 'planning_year': planning_year,
                    'required_scope': None, 'available_scopes': scopes}
    if not scopes:
        return [], {'status': 'MISSING_PLANNING_YEAR_DATASET', 'planning_year': planning_year,
                    'required_scope': None, 'available_scopes': []}
    if scopes[0].strip().casefold() != 'project':
        return [], {'status': 'NON_PROJECT_SCOPE_REQUIRES_EXPLICIT_SELECTION', 'planning_year': planning_year,
                    'required_scope': None, 'available_scopes': scopes}
    selected = [dataset for dataset in candidates if
                {record.get('geographic_scope') for record in dataset.get('records', [])} == {scopes[0]}]
    status = 'SELECTED' if len(selected) == 1 else 'AMBIGUOUS_PROJECT_SCOPE'
    return selected if status == 'SELECTED' else [], {
        'status': status, 'planning_year': planning_year, 'required_scope': 'project',
        'available_scopes': scopes,
    }


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
    active_parameters, parameter_selection = _readiness_dataset_selection(document, 'crop_water_parameters')
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
                'verified_parameter_evidence': bool(record and (record.get('verified_parameter_evidence') or record.get('verified_for_pilot'))),
                'verified_parameter_ready': False,
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
        'verified_parameter_evidence_count': sum(bool(r.get('verified_parameter_evidence')) for r in resolutions),
        'identity_resolved_count': sum(r['resolution_status'] in {'EXACT','REVIEWED_ALIAS'} for r in resolutions),
        'engine_connected': False,
        'dataset_selection': parameter_selection,
        'resolutions': resolutions,
    }
    active_phenology, phenology_selection = _readiness_dataset_selection(document, 'crop_phenology')
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
        'dataset_selection': phenology_selection,
        'source_fact': 'Frozen Akkaya runtime/project source data contains no sourced planting or harvest values.' if demo else None,
    }
    pilot_ready = (len(runtime)>0 and parameter_selection['status']=='SELECTED' and
                   phenology_selection['status']=='SELECTED' and
                   parameter['ambiguous_count']==0 and parameter['missing_count']==0 and
                   parameter['verified_parameter_count']==len(runtime) and phenology['verified_complete_count']==len(runtime))
    pilot = {
        'status': 'PILOT_READY' if pilot_ready else 'PILOT_DATA_NOT_READY',
        'demo_status': 'DEMO_READY' if demo else 'PROJECT_DATA_REVIEW_REQUIRED',
        'blocking_reasons': ([] if pilot_ready else [
            reason for condition,reason in (
                (len(runtime)==0, 'runtime crop catalog is empty'),
                (parameter_selection['status']!='SELECTED', 'no unambiguous verified parameter dataset for project planning year and pilot geographic scope'),
                (phenology_selection['status']!='SELECTED', 'no unambiguous verified phenology dataset for project planning year and pilot geographic scope'),
                (parameter['ambiguous_count']>0, 'ambiguous crop parameter resolution'),
                (parameter['missing_count']>0, 'missing crop parameter resolution'),
                (parameter['verified_parameter_count']<len(runtime), 'verified parameter coverage incomplete'),
                (phenology['verified_complete_count']<len(runtime), 'verified phenology coverage incomplete'),
                (True, 'crop parameter and phenology datasets are not connected to the scientific engine')) if condition]),
        'engine_connected': False,
    }
    return parameter, phenology, pilot


def readiness(document):
    units, crops, economics = (document[n] for n in ('analysis_units', 'crops', 'economics'))
    year = document['project']['planning_year']
    budget = document['water_budget']
    extra = document.get('scientific_inputs', {})
    imported_reference = bool(document.get('metadata', {}).get('reference_demo') and extra)
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
        if not imported_reference:
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
        if pairs-required or (not imported_reference and current-approved):
            issue('candidate_coverage', f'Mevcut ürünün onaylı adayı her birimde gerekli: {len(current-approved)} eksik; {len(pairs-required)} bilinmeyen eşleşme.')
        if imported_reference and len(candidates) != 6859:
            issue('reference_candidate_count', f'Accepted V1 reference candidate matrix must contain 6859 rows; found {len(candidates)}.')
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
        if imported_reference:
            if not seasonal or any(not all(positive(r.get(k)) for k in ('area_da', 'water_m3_calib_gross', 'profit_tl')) for r in seasonal):
                issue('seasonal_reference_coverage', 'S2 reference replay requires the complete accepted V1 seasonal source table.', ('S2',))
        else:
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
    from kds.adapters.institutional import verified_readiness
    verified = {scenario: verified_readiness(document, scenario) for scenario in ('S1', 'S2')}
    profile = effective_execution_profile(document)
    if profile is ExecutionProfile.REFERENCE_DEMO:
        reference_projection = _reference_demo_projection(document)
        reference = {scenario: _reference_demo_authority_readiness(
            document, scenario, reference_projection) for scenario in ('S1', 'S2')}
    else:
        reference = verified
    reference_available = {scenario: state['status'] != 'NOT_READY' for scenario,state in scenarios.items()}
    selected = reference['S1'] if profile is ExecutionProfile.REFERENCE_DEMO else verified['S1']
    profile_states = reference if profile is ExecutionProfile.REFERENCE_DEMO else verified
    profile_blockers = list(dict.fromkeys(
        [message for state in profile_states.values() for message in state['blocking_reasons']] +
        [item['message'] for state in scenarios.values() for item in state['issues']
         if item['severity'] == 'error']))
    profile_warnings = list(dict.fromkeys(
        [message for state in profile_states.values() for message in state['warnings']] +
        [item['message'] for state in scenarios.values() for item in state['issues']
         if item['severity'] == 'warning']))
    profile_ready = not profile_blockers and all(state['status'] != 'NOT_READY' for state in scenarios.values())
    global_status = ('NOT_READY' if not profile_ready else
                     'READY_WITH_WARNINGS' if profile_warnings else 'READY')
    return dict(project_id=document['project']['id'], planning_year=year, scenarios=scenarios,
        effective_execution_profile=profile.value, status=global_status, ready=profile_ready,
        blocking_reasons=profile_blockers, warnings=profile_warnings,
        execution_profiles={
            'REFERENCE_DEMO': {
                'available': any(reference_available.values()),
                'scenario_availability': reference_available,
                'ready': {scenario: reference[scenario]['ready'] and reference_available[scenario]
                          for scenario in ('S1', 'S2')},
                'blocking_reasons': {scenario: reference[scenario]['blocking_reasons']
                                     for scenario in ('S1', 'S2')},
                'warnings': sorted({warning for value in reference.values()
                                    for warning in value['warnings']}),
                'domains': {scenario: reference[scenario]['domains'] for scenario in ('S1', 'S2')},
                'climate_mode': reference['S1'].get('climate_mode'),
            },
            'VERIFIED_INSTITUTIONAL': {
                'ready': {scenario: value['ready'] for scenario,value in verified.items()},
                'blocking_reasons': {scenario: value['blocking_reasons'] for scenario,value in verified.items()},
                'warnings': sorted({warning for value in verified.values() for warning in value['warnings']}),
                'domains': {scenario: verified[scenario]['domains'] for scenario in ('S1', 'S2')},
            },
        },
        domains=selected.get('domains', {}),
        requires_reanalysis=bool(document.get('analysis_state', {}).get('requires_reanalysis', False)),
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
