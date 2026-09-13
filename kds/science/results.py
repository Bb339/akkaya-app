"""Presentation metrics from the existing engine output; no optimization math."""
def summarize(result, bundle):
    config=bundle.algorithm_configuration.copy()
    ids=set(config['selected_ids'])
    units=[u for u in bundle.analysis_units.copy() if not ids or u['external_id'] in ids]
    total_area=sum(u['area_da'] for u in units)
    active=0.; distribution={}
    for row in result.get('details',[]):
        area=float(row.get('area_da',0))
        crops=[row.get('chosenCrop')] if config['scenario']=='S1' else [row.get(s,{}).get('crop') for s in ('primary','secondary')]
        planted=[c for c in crops if c and c.upper() not in ('NADAS','FALLOW')]
        if planted:active+=area
        for crop in planted:distribution[crop]=distribution.get(crop,0.)+area
    params=result.get('meta',{}).get('run_params',{})
    return dict(total_area_da=total_area,active_area_da=active,fallow_area_da=max(0.,total_area-active),
                total_water_m3=result.get('total_water_m3'),total_profit_tl=result.get('total_profit_tl'),
                efficiency_tl_per_m3=result.get('efficiency_tl_per_m3'),feasible=result.get('feasible'),
                score=params.get('bestScore'),score_note='S2 raw engine output does not expose final fitness.' if config['scenario']=='S2' else None,
                crop_distribution_da=distribution,distribution_basis='seasonal cropped area; S2 can count land twice',
                plan_difference=result.get('delta'),diversity=params.get('diversity'),
                effective_run_parameters=params)
