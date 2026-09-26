"""Project overview and bounded analysis history projections for the V2 UI."""
from kds.application.readiness import readiness
from kds.science.results import present_stored_run


def run_summary(run):
    result=run.get('result') or {};summary=run.get('summary') or {}
    return dict(id=run['id'],timestamp=run['started_at'],scenario=run['scenario'],algorithm=run['algorithm'],seed=run['seed'],
                objective=run['configuration']['objective'],status=run['status'],feasible=result.get('feasible'),
                water=result.get('total_water_m3'),profit=result.get('total_profit_tl'),efficiency=result.get('efficiency_tl_per_m3'),score=summary.get('score'))


def history(document,offset=0,limit=50):
    if offset<0 or not 1<=limit<=200:raise ValueError('offset >= 0 and limit in [1,200] required.')
    runs=sorted(document.get('runs',{}).values(),key=lambda r:(r['started_at'],r['id']),reverse=True)
    return dict(items=[run_summary(present_stored_run(r,document)) for r in runs[offset:offset+limit]],count=len(runs),offset=offset,limit=limit)


def overview(document):
    report=readiness(document);counts=report['counts'];extra=document.get('scientific_inputs',{})
    reference=document.get('metadata',{}).get('source_version')=='v1.0.0-thesis-final' and not extra
    legacy_synthetic=document['project'].get('data_source_notes')=='synthetic_test_fixture'
    synthetic=legacy_synthetic or bool(document.get('metadata',{}).get('synthetic_institutional_test')
                                       and document.get('metadata',{}).get('not_official'))
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
    for water_type in ('annual_water_supply','monthly_water_supply','delivery_capacity','environmental_release','conveyance_efficiency','perennial_irrigation_requirement'):
        active=document.get('water_data',{}).get('active',{}).get(water_type)
        status(water_type,active)
    for economic_type in ('crop_yield','crop_sale_price','crop_support_payment','crop_cost_components','crop_net_profit','analysis_unit_economics','seasonal_economics'):
        active=any(key.startswith(economic_type+'|') for key in document.get('economic_data',{}).get('active',{}))
        status(economic_type,active)
    for parameter_type in ('crop_water_parameters','crop_phenology'):
        active=any(key.startswith(parameter_type+'|') for key in document.get('crop_parameter_data',{}).get('active',{}))
        status(parameter_type,active)
    candidate_units=len({c['analysis_unit_id'] for c in extra.get('candidates',[])}) if not reference else counts['analysis_units']
    return dict(readiness=report,import_status=statuses,candidate_units=candidate_units,
                last_import_at=max((b.get('uploaded_at','') for b in batches),default=None),
                last_run=next(iter(history(document,limit=1)['items']),None),
                synthetic=synthetic,
                project_kind='reference' if reference else 'synthetic_test' if synthetic else 'user_provided')


def data_catalog(document):
    """Project-scoped metadata projection for the institutional UI.

    This deliberately exposes identifiers and provenance only.  Scientific
    records stay behind their accepted import/readiness boundaries.
    """
    datasets = []
    for store_name in ('water_data', 'economic_data', 'crop_parameter_data'):
        store = document.get(store_name, {})
        active_ids = set(store.get('active', {}).values())
        for dataset_id, dataset in store.get('datasets', {}).items():
            source = dataset.get('source') or {}
            records = dataset.get('records') or []
            scopes = sorted({str(row.get('geographic_scope') or row.get('scope'))
                             for row in records
                             if row.get('geographic_scope') or row.get('scope')})
            years = sorted({int(row['planning_year']) for row in records
                            if row.get('planning_year') is not None})
            datasets.append({
                'store': store_name,
                'dataset_id': dataset.get('dataset_id') or dataset_id,
                'data_type': dataset.get('data_type'),
                'version': dataset.get('version'),
                'status': dataset.get('status'),
                'selected': dataset_id in active_ids,
                'authority_class': dataset.get('authority_class'),
                'confirmed_at': dataset.get('confirmed_at'),
                'created_at': dataset.get('created_at'),
                'source': source,
                'scope_key': dataset.get('scope_key'),
                'geographic_scope': scopes,
                'planning_years': years,
                'supersedes': dataset.get('supersedes'),
                'derivation_status': dataset.get('derivation_status'),
                'requires_recalculation': bool(dataset.get('requires_recalculation', False)),
                'record_count': len(records),
            })
    imports = []
    for batch_id, batch in document.get('imports', {}).items():
        imports.append({key: batch.get(key) for key in (
            'data_type', 'filename', 'status', 'uploaded_at', 'confirmed_at',
            'file_hash', 'applied_revision', 'row_count', 'supersedes',
        )} | {'id': batch_id})
    imports.sort(key=lambda item: (item.get('uploaded_at') or '', item['id']), reverse=True)
    datasets.sort(key=lambda item: (str(item.get('data_type') or ''),
                                    str(item.get('version') or ''),
                                    str(item.get('dataset_id') or '')))
    return {
        'project_id': document['project']['id'],
        'data_revision': document.get('data_revision', 0),
        'analysis_state': document.get('analysis_state', {}),
        'datasets': datasets,
        'imports': imports,
        'project_inputs': {
            'analysis_units': len(document.get('analysis_units', [])),
            'crops': len(document.get('crops', [])),
            'economics': len(document.get('economics', [])),
            'candidates': len(document.get('scientific_inputs', {}).get('candidates', [])),
            'climate_rows': len(document.get('scientific_inputs', {}).get('seasonal_resources', {}).get('monthly_climate', [])),
        },
    }
