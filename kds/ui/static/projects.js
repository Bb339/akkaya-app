import {api,post,facts,showJSON,message} from './api.js';
import {wireImports} from './imports.js';
import {wireAnalysis} from './analysis.js';
let projectId=null;
const root=()=>`/projects/${encodeURIComponent(projectId)}`;
async function refresh(){
  if(!projectId)return;
  const [d,r]=await Promise.all([api(root()),api(root()+'/readiness')]);
  document.getElementById('detail').hidden=false;
  document.getElementById('project-name').textContent=d.project.name;
  facts('facts',[['Yıl',d.project.planning_year],['Bölge',d.project.province_or_region],['Havza',d.project.basin_or_irrigation_area],
    ['Su bütçesi',`${d.water_budget.amount ?? 'Belirsiz'} ${d.water_budget.unit}`],['Bütçe türü',d.water_budget.kind],
    ['Analiz birimleri',r.counts.analysis_units],['Toplam alan (da)',r.counts.total_area_da],['Ürünler',r.counts.crops],
    ['Ekonomik veri kapsamı',`${r.counts.economics_covered}/${r.counts.crops}`],['Geometri kapsamı',`${r.counts.geometry_covered}/${r.counts.analysis_units}`],
    ['Bilimsel parametre kaynağı',r.scientific_data.parameter_source],['Katalog Kc alanları',`${r.scientific_data.catalog_kc_complete}/${r.counts.crops}`],['Aday kayıtları',r.scientific_data.raw_candidate_count],['Kaynak güven sınıfları',JSON.stringify(r.scientific_data.confidence_levels)]]);
  const readiness=document.getElementById('readiness');readiness.replaceChildren();
  for(const [s,v] of Object.entries(r.scenarios)){
    const h=document.createElement('h4');h.textContent=`${s}: ${v.status}`;readiness.append(h);
    const ul=document.createElement('ul');
    for(const issue of v.issues){const li=document.createElement('li');li.textContent=issue.message;li.className=issue.severity;ul.append(li);}
    readiness.append(ul);
  }
  showJSON('imports',r.imports);
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
wireAnalysis(root,safe);
safe(list);
