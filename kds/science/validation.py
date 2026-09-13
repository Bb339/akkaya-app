"""Structural input validation and complete seasonal coverage checks."""
import math
from datetime import date


def validate_payload(payload):
    for row in payload.get('candidates', []):
        for name in ('analysis_unit_id','crop','rotation_status'):
            if name in row and not isinstance(row[name],str):
                raise ValueError(name+' must be text.')
        for name in ('water_requirement_m3_da','profit_per_da','yield_ton_da','suitability','risk'):
            if name in row and row[name] is not None and (type(row[name]) not in (int,float) or not math.isfinite(row[name])):
                raise ValueError(name+' must be a finite number.')
        if 'allowed' in row and type(row['allowed']) is not bool:
            raise ValueError('allowed must be a boolean.')
    for name,value in payload.get('crop_families',{}).items():
        if not isinstance(value,str) or not value.strip():
            raise ValueError('Crop families must be nonempty text.')
    for row in payload.get('rotation_rules',[]):
        if not isinstance(row,dict):
            raise ValueError('Rotation rules must be objects.')
    for rows in payload.get('seasonal_resources',{}).values():
        for row in rows:
            if any(isinstance(v,(dict,list)) for v in row.values()):
                raise ValueError('Seasonal table cells must be scalar values.')


def seasonal_issues(document):
    extra=document.get('scientific_inputs',{})
    env=extra.get('seasonal_resources',{})
    names={c['name'] for c in document['crops']}
    ids={u['external_id'] for u in document['analysis_units']}
    year=document['project']['planning_year']
    messages=[]
    schemas={
        'parcels':{'parcel_id','district','land_capability_class'},
        's2':{'parcel_id','crop','year','season','area_da','water_m3_calib_gross','profit_tl',
              'planting_date','harvest_date','yield_ton','price_tl_ton','variable_cost_tl','irrig_efficiency'},
        'reservoir':{'month','irrigation_m3_baseline'},
        'delivery':{'month','max_delivery_m3_assumed'},
        'monthly_climate':{'parcel_id','month','et0_mm','precip_mm'},
        'water_quality':{'month','ec_dS_m_assumed'},
        'crop_suitability':{'crop','land_capability_class','suitability_score'},
        'irrigation_methods':{'method','typical_total_efficiency'},
    }
    for key,columns in schemas.items():
        if any(not columns <= r.keys() for r in env.get(key,[])):
            messages.append(f'{key}: gerekli sütunlar '+', '.join(sorted(columns)))
    if messages:
        return messages
    numeric={'s2':('area_da','water_m3_calib_gross','profit_tl','yield_ton','price_tl_ton','variable_cost_tl','irrig_efficiency'),
             'monthly_climate':('et0_mm','precip_mm'),'irrigation_methods':('typical_total_efficiency',)}
    for key,fields in numeric.items():
        if any(any(type(r.get(f)) not in (int,float) or not math.isfinite(r[f]) or r[f]<0 for f in fields) for r in env.get(key,[])):
            messages.append(key+': bilimsel sayısal alanlar sonlu ve negatif olmayan değerler içermelidir.')
    if messages:
        return messages
    for key,field in [('reservoir','irrigation_m3_baseline'),('delivery','max_delivery_m3_assumed'),('water_quality','ec_dS_m_assumed')]:
        rows=env.get(key,[])
        months={str(r.get('month',''))[:7] for r in rows}
        expected={f'{year}-{m:02}' for m in range(1,13)}
        if months!=expected or len(rows)!=12 or any(type(r.get(field)) not in (int,float) or r[field]<=0 for r in rows):
            messages.append(f'{key}: planlama yılına ait 12 benzersiz ay ve pozitif {field} gerekli.')
    rows=env.get('parcels',[])
    if {r.get('parcel_id') for r in rows}!=ids or len(rows)!=len(ids):
        messages.append('parcels: birim parametre tablosu projenin bütün birimlerini birebir kapsamalıdır.')
    lcc={str(r.get('land_capability_class','')).upper() for r in rows}
    if {(str(r.get('land_capability_class','')).upper(),r.get('crop')) for r in env.get('crop_suitability',[])}!={(s,c) for s in lcc for c in names}:
        messages.append('crop_suitability: her toprak sınıfı/ürün için açık skor gerekli; 0.85 varsayımı kullanılmaz.')
    if any(type(r.get('suitability_score')) not in (int,float) or not 0<=r['suitability_score']<=1 for r in env.get('crop_suitability',[])):
        messages.append('crop_suitability: skorlar 0–1 aralığında olmalıdır.')
    if not names <= set(extra.get('crop_families',{})):
        messages.append('Her katalog ürünü için rotasyon ailesi gerekli.')
    scores={(str(r.get('land_capability_class','')).upper(),r.get('crop')):r.get('suitability_score') for r in env.get('crop_suitability',[])}
    unit_soil={r.get('parcel_id'):str(r.get('land_capability_class','')).upper() for r in rows}
    for candidate in extra.get('candidates',[]):
        score=scores.get((unit_soil.get(candidate.get('analysis_unit_id')),candidate.get('crop')))
        if type(score) in (int,float) and (score>=.60)!=candidate.get('allowed'):
            messages.append('S2 allowed bayrağı ile toprak/ürün uygunluk eşiği (0.60) çelişiyor.');break
    history=env.get('s1',[])
    if {r.get('parcel_id') for r in history if r.get('year')==year-1}!=ids or any(r.get('crop') not in names for r in history):
        messages.append('s1: önceki yılın birim/ürün geçmişi gerekli; aile geçmişi sıfır varsayılmaz.')
    if any(not {'type','from_family','to_family','penalty_weight'}<=r.keys() for r in extra.get('rotation_rules',[])):
        messages.append('Rotasyon kuralları type, from_family, to_family, penalty_weight içermelidir.')
    expected={(uid,f'{year}-{m:02}') for uid in ids for m in range(1,13)}
    climate=env.get('monthly_climate',[])
    if {(r.get('parcel_id'),str(r.get('month',''))[:7]) for r in climate}!=expected or len(climate)!=len(expected):
        messages.append('monthly_climate: her birim için 12 aylık ETo/yağış verisi gerekli.')
    for r in env.get('s2',[]):
        try:
            start,end=date.fromisoformat(r['planting_date']),date.fromisoformat(r['harvest_date'])
            valid=start<=end and start.year==year and end.year==year and 0<float(r['irrig_efficiency'])<=1
        except (ValueError,KeyError,TypeError):
            valid=False
        if not valid:
            messages.append('s2: tarihler planlama yılı içinde ve sıralı, sulama randımanı (0,1] olmalıdır.');break
    budget=document['water_budget']['amount']*(1e6 if document['water_budget']['unit']=='hm3' else 1)
    rows=env.get('reservoir',[])
    if rows and all(type(r.get('irrigation_m3_baseline')) in (int,float) for r in rows):
        if not math.isclose(sum(r['irrigation_m3_baseline'] for r in rows),budget,rel_tol=1e-9,abs_tol=1e-6):
            messages.append('reservoir aylık toplamı proje su bütçesine eşit olmalıdır.')
    return messages
