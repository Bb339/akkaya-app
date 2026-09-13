"""Deterministic synthetic inputs. No reference-project data is read."""
import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
SOURCE='synthetic_test_fixture'
NAMES=['ARPA','NOHUT','MERCIMEK','AYCICEGI','MISIR','BUGDAY','ELMA','ARMUT']
FAMILIES=['poaceae','fabaceae','fabaceae','asteraceae','poaceae','poaceae','rosaceae','rosaceae']
PROFITS=[650.,800.,5.,920.,1200.,700.,1900.,1700.]
WATERS=[110.,95.,90.,160.,240.,130.,280.,260.]
METHODS=['sprinkler','drip','surface','drip','sprinkler','surface','drip','drip']
EFF={'drip':.88,'sprinkler':.76,'surface':.60}

def write(name,rows):
 with (ROOT/name).open('w',encoding='utf8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def flatten(sections):
 rows=[]
 for section,records in sections.items():
  for identity,fields in records.items():
   for field,value in fields.items():
    typ='boolean' if type(value)is bool else 'integer' if type(value)is int else 'number' if type(value)is float else 'text'
    rows.append(dict(section=section,record_id=identity,field=field,value_type=typ,value=value,source=SOURCE))
 return rows

def build():
 units=[dict(external_id=f'GX-{i+1:03}',settlement=['Test West','Test Central','Test East'][i//8],area_da=8.+i%7,
             current_crop=NAMES[i%8],name_or_code=f'Synthetic unit {i+1}',irrigation_method=METHODS[i%8],source=SOURCE) for i in range(24)]
 write('analysis_units.csv',units)
 crops=[dict(crop_name=c,crop_group='orchard' if i>=6 else 'field',perennial=i>=6,kc_initial=.35,kc_mid=.95,kc_end=.45,
             stage_initial_days=20,stage_development_days=30,stage_mid_days=45,stage_late_days=25,source=SOURCE,confidence_level='synthetic') for i,c in enumerate(NAMES)]
 write('crops.csv',crops)
 econ=[dict(crop_name=c,year=2025,yield_per_da=.4+i*.1,net_profit_per_da=PROFITS[i],currency='TRY',source=SOURCE,yield_unit='ton/da') for i,c in enumerate(NAMES)]
 write('economics.csv',econ)
 negative=[dict(r,net_profit_per_da=-50. if i==2 else r['net_profit_per_da']) for i,r in enumerate(econ)]
 write('economics_negative.csv',negative)
 candidates=[dict(analysis_unit_id=u['external_id'],crop=c,water_requirement_m3_da=WATERS[i],profit_per_da=PROFITS[i],yield_ton_da=.4+i*.1,
                  allowed=True,rotation_status='synthetic_explicit',suitability=1.,risk=0.,source=SOURCE) for u in units for i,c in enumerate(NAMES)]
 write('candidates.csv',candidates)
 basic={'unit_parameters':{u['external_id']:dict(current_water_m3=u['area_da']*WATERS[NAMES.index(u['current_crop'])],current_profit=u['area_da']*PROFITS[NAMES.index(u['current_crop'])],soil_class='II',parcel_type='orchard' if NAMES.index(u['current_crop'])>=6 else 'field') for u in units},
        'irrigation':{c:dict(default=METHODS[i],recommended=METHODS[i],efficiency=EFF[METHODS[i]]) for i,c in enumerate(NAMES)}}
 write('scientific_s1.csv',flatten(basic))
 months=[f'2025-{i:02}-01' for i in range(1,13)]
 env=dict(
  s1=[dict(parcel_id=u['external_id'],crop=NAMES[(i+1)%6],year=2024) for i,u in enumerate(units)],
  s2=[dict(parcel_id=u['external_id'],crop=c,year=2025,season=s,area_da=u['area_da'],water_m3_calib_gross=u['area_da']*WATERS[i],profit_tl=u['area_da']*PROFITS[i],
           planting_date='2025-03-01' if s=='primary' else '2025-08-01',harvest_date='2025-06-30' if s=='primary' else '2025-11-30',yield_ton=u['area_da']*(.4+i*.1),price_tl_ton=4000.,variable_cost_tl=1000.,irrig_efficiency=EFF[METHODS[i]]) for u in units for i,c in enumerate(NAMES) for s in ('primary','secondary')],
  parcels=[dict(parcel_id=u['external_id'],district='Synthetic Region',land_capability_class='II') for u in units],
  reservoir=[dict(month=m,irrigation_m3_baseline=10000.) for m in months],delivery=[dict(month=m,max_delivery_m3_assumed=18000.) for m in months],
  crop_params=[dict(crop=c,kc_ini=.35,kc_mid=.95,kc_end=.45) for c in NAMES],
  monthly_climate=[dict(parcel_id=u['external_id'],month=m,et0_mm=85.,precip_mm=25.) for u in units for m in months],
  water_quality=[dict(month=m,ec_dS_m_assumed=.5) for m in months],soil_params=[dict(land_capability_class='II')],
  crop_suitability=[dict(crop=c,land_capability_class='II',suitability_score=1.) for c in NAMES],
  irrigation_methods=[dict(method=k,typical_total_efficiency=v) for k,v in EFF.items()])
 sections={'crop_families':{c:dict(family=FAMILIES[i]) for i,c in enumerate(NAMES)},'rotation_rules':{'rule-1':dict(type='hard',from_family='*',to_family='same_family',penalty_weight=1.)}}
 sections.update({'seasonal_resources.'+k:{f'row-{i+1}':r for i,r in enumerate(rows)} for k,rows in env.items()})
 write('scientific_s2.csv',flatten(sections))
 write('water_budget.csv',[dict(amount=120000.,unit='m3',kind='scenario',source=SOURCE)])
 features=[dict(type='Feature',properties=dict(external_id=u['external_id'],source=SOURCE),geometry=dict(type='Point',coordinates=[28.+i*.01,39.+i*.01])) for i,u in enumerate(units)]
 for name,values in [('geometry_partial.geojson',features[:12]),('geometry_all.geojson',features)]:
  (ROOT/name).write_text(json.dumps(dict(type='FeatureCollection',features=values),indent=2),encoding='utf8')
 (ROOT/'project.json').write_text(json.dumps(dict(id='synthetic-general',name='Synthetic test project',planning_year=2025,annual_water_budget=0,water_budget_unit='m3',province_or_region='Synthetic Region',data_source_notes=SOURCE,description='Synthetic test project / Sentetik test verisi'),indent=2),encoding='utf8')
 (ROOT/'crop_matrix.json').write_text(json.dumps([list(crops[0]),*[list(r.values()) for r in crops]]),encoding='utf8')
 print('Synthetic fixture generated: 24 units, 3 settlements, 8 crops; no reference inputs.')
if __name__=='__main__':build()
