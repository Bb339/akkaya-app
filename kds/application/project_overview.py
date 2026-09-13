"""Project overview and bounded analysis history projections for the V2 UI."""
from kds.application.readiness import readiness


def run_summary(run):
    result=run.get('result') or {};summary=run.get('summary') or {}
    return dict(id=run['id'],timestamp=run['started_at'],scenario=run['scenario'],algorithm=run['algorithm'],seed=run['seed'],
                objective=run['configuration']['objective'],status=run['status'],feasible=result.get('feasible'),
                water=result.get('total_water_m3'),profit=result.get('total_profit_tl'),efficiency=result.get('efficiency_tl_per_m3'),score=summary.get('score'))


def history(document,offset=0,limit=50):
    if offset<0 or not 1<=limit<=200:raise ValueError('offset >= 0 and limit in [1,200] required.')
    runs=sorted(document.get('runs',{}).values(),key=lambda r:(r['started_at'],r['id']),reverse=True)
    return dict(items=[run_summary(r) for r in runs[offset:offset+limit]],count=len(runs),offset=offset,limit=limit)


def overview(document):
    report=readiness(document);counts=report['counts'];extra=document.get('scientific_inputs',{})
    reference=document.get('metadata',{}).get('source_version')=='v1.0.0-thesis-final' and not extra
    codes={i['code'] for s in report['scenarios'].values() for i in s['issues'] if i['severity']=='error'}
    batches=list(document['imports'].values())
    statuses={}
    def status(name,present,warning=False):
        value='Missing' if not present else 'Warning' if warning else 'Ready'
        relevant=sorted((b for b in batches if b['data_type']==name),key=lambda b:b.get('uploaded_at',''),reverse=True)
        latest=relevant[0] if relevant else None
        if latest and latest['status']!='applied':value='Warning' if latest['status']=='invalid' else 'Uploaded'
        statuses[name]=value
    status('analysis_units',counts['analysis_units'],'area' in codes)
    status('crops',counts['crops'],bool(codes&{'crops','phenology','crop_rules'}))
    status('economics',document['economics'],bool(codes&{'economics','currency'}))
    status('candidates',reference or extra.get('candidates'),any(c.startswith('candidate') or c=='duplicate_candidates' for c in codes))
    status('scientific_inputs',reference or extra,bool(codes-{'budget','crops','economics','currency','units','area'}))
    status('geometries',counts['geometry_covered'],counts['geometry_covered']<counts['analysis_units'])
    status('water_budget',document['water_budget'].get('amount'), 'budget' in codes or document['water_budget']['kind']=='calculated_reference')
    candidate_units=len({c['analysis_unit_id'] for c in extra.get('candidates',[])}) if not reference else counts['analysis_units']
    return dict(readiness=report,import_status=statuses,candidate_units=candidate_units,
                last_import_at=max((b.get('uploaded_at','') for b in batches),default=None),
                last_run=next(iter(history(document,limit=1)['items']),None),
                synthetic=document['project'].get('data_source_notes')=='synthetic_test_fixture',
                project_kind='reference' if reference else 'synthetic_test' if document['project'].get('data_source_notes')=='synthetic_test_fixture' else 'user_provided')
