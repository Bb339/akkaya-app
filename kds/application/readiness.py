"""Fail closed before invoking any legacy fallback branch."""
import math


def positive(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


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
    missing = sorted({u['current_crop'] for u in units} - names)
    if not crops or missing:
        issue('crops', 'Mevcut ürün/katalog eşleşmesi eksik: ' + ', '.join(missing))
    economic_names = {e['crop_name'] for e in economics if e['year'] == year}
    if names - economic_names or not economics:
        issue('economics', 'Planlama yılı ekonomik verisi eksik: ' + ', '.join(sorted(names-economic_names)))
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
        candidates = extra.get('candidates', [])
        if not candidates:
            issue('candidates', 'Birim × ürün düzeyinde açık aday su/kâr verileri gerekli; otomatik değer üretilmez.')
        # A complete grid prevents the legacy regional-median augmentation.
        pairs = {(c.get('analysis_unit_id'), c.get('crop')) for c in candidates}
        required = {(u['external_id'], c) for u in units for c in names}
        if pairs != required:
            issue('candidate_coverage', f'Aday matrisi tam kapsamlı olmalı: {len(required-pairs)} eksik, {len(pairs-required)} bilinmeyen eşleşme.')
        if len(pairs) != len(candidates):
            issue('duplicate_candidates', 'Tekrarlanan birim/ürün adayı var.')
        for c in candidates:
            if not all(positive(c.get(k)) for k in ('water_requirement_m3_da', 'profit_per_da', 'yield_ton_da')):
                issue('candidate_values', 'Her aday için pozitif, sonlu brüt su, net kâr ve verim gerekli.'); break
            if c.get('allowed') is not True or not positive(c.get('suitability')) or not c.get('rotation_status'):
                issue('candidate_constraints', 'Bu sürüm, agronomik olarak onaylanmış tam aday tablosu gerektirir (allowed, suitability, rotation_status).'); break
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
    scenarios = {}
    for scenario in ('S1', 'S2'):
        relevant = [i for i in issues if scenario in i['scenarios']]
        status = 'NOT_READY' if any(i['severity']=='error' for i in relevant) else 'READY_WITH_WARNINGS' if relevant else 'READY'
        scenarios[scenario] = dict(status=status, issues=relevant)
    return dict(project_id=document['project']['id'], scenarios=scenarios, counts=dict(
        analysis_units=len(units), crops=len(crops), total_area_da=sum(u['area_da'] for u in units),
        economics_covered=len(names & economic_names), geometry_covered=geometry_count),
        water_budget=budget, imports=[dict(id=k, status=v.get('status')) for k,v in document['imports'].items()])
