import {api,post,facts,showJSON,message} from './api.js';
import {wireImports} from './imports.js';
import {wireAnalysis,renderRun} from './analysis.js';
import {refreshHistory} from './history.js';
let projectId=null;
const root=()=>`/projects/${encodeURIComponent(projectId)}`;
async function refresh(){
  if(!projectId)return;
  const selected=projectId;
  const [d,o]=await Promise.all([api(root()),api(root()+'/overview')]);
  if(selected!==projectId)return;
  const r=o.readiness;
  document.getElementById('synthetic-watermark').hidden=!o.synthetic;
  document.getElementById('reference-label').hidden=d.water_budget.kind!=='calculated_reference';
  document.getElementById('detail').hidden=false;
  document.getElementById('project-name').textContent=d.project.name;
  facts('facts',[['Yıl',d.project.planning_year],['Bölge',d.project.province_or_region],['Havza',d.project.basin_or_irrigation_area],
    ['Su bütçesi',`${d.water_budget.amount ?? 'Belirsiz'} ${d.water_budget.unit}`],['Bütçe türü',d.water_budget.kind],
    ['Analiz birimleri',r.counts.analysis_units],['Toplam alan (da)',r.counts.total_area_da],['Ürünler',r.counts.crops],
    ['Ekonomik veri kapsamı',`${r.counts.economics_covered}/${r.counts.crops}`],['Geometri kapsamı',`${r.counts.geometry_covered}/${r.counts.analysis_units}`],
    ['Bilimsel parametre kaynağı',r.scientific_data.parameter_source],['Katalog Kc alanları',`${r.scientific_data.catalog_kc_complete}/${r.counts.crops}`],['Aday kayıtları',r.scientific_data.raw_candidate_count],['REFERENCE_DEMO',r.execution_profiles.REFERENCE_DEMO.available],['VERIFIED_INSTITUTIONAL S1',r.execution_profiles.VERIFIED_INSTITUTIONAL.ready.S1],['VERIFIED_INSTITUTIONAL S2',r.execution_profiles.VERIFIED_INSTITUTIONAL.ready.S2],['Project requires reanalysis',r.requires_reanalysis],['Kaynak güven sınıfları',JSON.stringify(r.scientific_data.confidence_levels)],['Water Data authority',JSON.stringify(Object.fromEntries(Object.entries(r.water_data_authority).map(([k,v])=>[k,v.authority_class])))],['Economics authority',JSON.stringify(Object.fromEntries(Object.entries(r.economic_data_authority).map(([k,v])=>[k,v.authority_class])))],['Parameter resolution',`${r.crop_parameter_readiness.identity_resolved_count}/${r.crop_parameter_readiness.runtime_crop_count}`],['Legacy generic fallback',r.crop_parameter_readiness.legacy_fallback_count],['Verified phenology',`${r.phenology_readiness.verified_complete_count}/${r.phenology_readiness.runtime_crop_count}`],['Pilot readiness',r.pilot_readiness.status],['Crop contracts engine connected',r.domains.crop_parameters?.engine_connected ?? false],['Ekonomik veri yeniden analiz gereksinimi',r.economic_data_reanalysis.requires_reanalysis ?? false],['Aday birim kapsamı',`${o.candidate_units}/${r.counts.analysis_units}`],['S1 hazırlık',r.scenarios.S1.status],['S2 hazırlık',r.scenarios.S2.status],['Son import tarihi',o.last_import_at],['Son analiz',o.last_run?.id ?? 'Henüz çalışma yok']]);
  const readiness=document.getElementById('readiness');readiness.replaceChildren();
  for(const [s,v] of Object.entries(r.scenarios)){
    const h=document.createElement('h4');h.textContent=`${s}: ${v.status}`;readiness.append(h);
    const ul=document.createElement('ul');
    for(const issue of v.issues){const li=document.createElement('li');li.textContent=issue.message;li.className=issue.severity;ul.append(li);}
    readiness.append(ul);
  }
  showJSON('imports',r.imports);
  const labels={analysis_units:'Analysis Units',crops:'Crops',economics:'Economics',candidates:'Candidate Rules / Options',scientific_inputs:'Scientific Inputs',geometries:'Geometry',water_budget:'Water Budget',annual_water_supply:'Annual Water Supply',monthly_water_supply:'Monthly Water Supply',delivery_capacity:'Delivery Capacity',environmental_release:'Environmental Release',conveyance_efficiency:'Conveyance Efficiency',perennial_irrigation_requirement:'Perennial Irrigation Requirement',crop_yield:'Crop Yield',crop_sale_price:'Crop Sale Price',crop_support_payment:'Crop Support Payment',crop_cost_components:'Crop Cost Components',crop_net_profit:'Crop Net Profit',analysis_unit_economics:'Analysis-unit Economics',seasonal_economics:'Seasonal Economics',crop_water_parameters:'Crop Water Parameters',crop_phenology:'Crop Phenology'};
  const table=document.createElement('table');
  for(const [key,status] of Object.entries(o.import_status)){const tr=document.createElement('tr');for(const value of [labels[key],status]){const td=document.createElement('td');td.textContent=value;tr.append(td);}table.append(tr);}
  document.getElementById('data-status').replaceChildren(table);
  await refreshHistory(root(),safe,renderRun);
}
async function list(){
  const data=await api('/projects'), container=document.getElementById('projects');container.replaceChildren();
  if(!data.projects.length)container.textContent='Henüz proje yok.';
  for(const p of data.projects){const b=document.createElement('button');b.textContent=p.name;b.onclick=()=>safe(async()=>{projectId=p.id;document.getElementById('result').hidden=true;await refresh();});container.append(b);}
}
export async function safe(action){try{await action();}catch(e){message(e.message,true);}}
document.getElementById('create-project').onsubmit=e=>{e.preventDefault();safe(async()=>{
  const values=Object.fromEntries(new FormData(e.target));values.planning_year=Number(values.planning_year);values.annual_water_budget=values.annual_water_budget?Number(values.annual_water_budget):0;values.water_budget_unit='m3';
  const d=await post('/projects',values);projectId=d.project.id;await list();await refresh();message('Proje oluşturuldu.');
});};
document.getElementById('budget-form').onsubmit=e=>{e.preventDefault();safe(async()=>{const d=Object.fromEntries(new FormData(e.target));d.amount=Number(d.amount);d.unit='m3';await post(root()+'/water-budget',d);await refresh();});};
wireImports(root,refresh,safe);
wireAnalysis(root,safe,refresh);
safe(list);
