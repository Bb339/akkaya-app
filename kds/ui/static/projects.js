import {api,post,facts,message,badge} from './api.js';
import {wireImports} from './imports.js';
import {wireAnalysis,invalidatePreview,setReadiness} from './analysis.js';
import {refreshHistory} from './history.js';
import {renderReadiness} from './readiness.js';
import {renderData,renderTemplates} from './data-management.js';
import {renderRun} from './results.js';

const SECTION_TARGETS=Object.freeze({
  project:'projects-section',
  data:'data-management',
  readiness:'readiness-section',
  analysis:'analysis-section',
  result:'result',
  provenance:'provenance-section',
  reference:'reference-demo',
});
const DEFAULT_SECTION='project';
let projectId=null;
const root=()=>`/projects/${encodeURIComponent(projectId)}`;
const canonicalHash=(id,section=DEFAULT_SECTION)=>`#project=${encodeURIComponent(id)}&section=${section}`;

function decodeHashPart(value){return decodeURIComponent(value.replace(/\+/g,' '));}

function hashProjectContext(){
  const fragment=location.hash.replace(/^#/,'');
  if(!fragment)return {id:null,error:'URL hash içinde proje bağlamı eksik.'};
  const projects=[],sections=[];
  let sectionIssue=null;
  for(const part of fragment.split('&')){
    const split=part.indexOf('=');
    const rawKey=split<0?part:part.slice(0,split),rawValue=split<0?'':part.slice(split+1);
    let key;
    try{key=decodeHashPart(rawKey);}catch(_error){return {id:null,error:'URL hash içindeki proje kimliği geçersiz kodlanmış.'};}
    if(key==='project'){
      try{projects.push(decodeHashPart(rawValue));}catch(_error){return {id:null,error:'URL hash içindeki proje kimliği geçersiz kodlanmış.'};}
    }else if(key==='section'){
      try{sections.push(decodeHashPart(rawValue));}catch(_error){sectionIssue='URL hash içindeki section parametresi geçersiz kodlanmış; proje bölümü gösteriliyor.';}
    }
  }
  if(projects.length!==1)return {id:null,error:'URL hash içinde tek bir project parametresi gerekli.'};
  const id=projects[0].trim();
  if(!id)return {id:null,error:'URL hash içindeki project parametresi boş.'};
  let section=DEFAULT_SECTION;
  if(sections.length>1)sectionIssue='URL hash içinde en fazla bir section parametresi olabilir; proje bölümü gösteriliyor.';
  else if(sections.length===1){
    const requested=sections[0].trim();
    if(Object.hasOwn(SECTION_TARGETS,requested))section=requested;
    else sectionIssue=`Bilinmeyen çalışma alanı bölümü: ${requested||'(boş)'}. Proje bölümü gösteriliyor.`;
  }
  return {id,section:sectionIssue?DEFAULT_SECTION:section,sectionIssue,error:null};
}

export async function safe(action){try{await action();}catch(error){message(error.message,true);}}

function syncNavigationLinks(){
  for(const link of document.querySelectorAll('[data-project-section]')){
    const section=link.dataset.projectSection;
    link.href=projectId?canonicalHash(projectId,section):'#';
  }
}

function sectionTarget(section){
  const target=document.getElementById(SECTION_TARGETS[section]);
  if(section==='result'&&target?.hidden)return document.getElementById('history-section');
  return target;
}

function applySection(section,{issue=null,smooth=false}={}){
  if(issue){
    history.replaceState(null,'',canonicalHash(projectId,DEFAULT_SECTION));
    syncNavigationLinks();
    message(issue,true);
  }
  const target=sectionTarget(section);
  if(target)target.scrollIntoView({behavior:smooth?'smooth':'auto'});
  if(section==='result'&&document.getElementById('result').hidden&&!issue){
    message('Sonuç bölümünü açmak için kayıtlı bir çalışma seçin veya yeni analiz çalıştırın.');
  }
}

function navigateToSection(section,{replace=false,smooth=true}={}){
  if(!projectId){message('Çalışma alanında gezinmek için önce tam proje kimliğiyle bir proje seçin.',true);return;}
  if(!Object.hasOwn(SECTION_TARGETS,section)){message(`Bilinmeyen çalışma alanı bölümü: ${section}`,true);return;}
  const next=canonicalHash(projectId,section);
  if(location.hash===next){applySection(section,{smooth});return;}
  if(replace){history.replaceState(null,'',next);syncNavigationLinks();applySection(section,{smooth});}
  else location.hash=next;
}

function projectMode(project,overview){return overview.synthetic?'synthetic':overview.project_kind==='reference'?'reference':'institutional';}

async function refresh(){
  if(!projectId)return;
  const selected=projectId;
  const [projectDoc,overview,catalog]=await Promise.all([api(root()),api(root()+'/overview'),api(root()+'/data-catalog')]);
  if(selected!==projectId)return;
  const report=overview.readiness,project=projectDoc.project,mode=projectMode(project,overview);
  document.getElementById('detail').hidden=false;
  document.getElementById('project-name').textContent=project.name;
  document.getElementById('project-description').textContent=project.description||'Proje açıklaması girilmedi.';
  document.getElementById('open-v1-project').href=`/?provider=PROJECT_DATA&project_id=${encodeURIComponent(project.id)}`;
  document.getElementById('hero-project-name').textContent=project.name;
  document.getElementById('hero-project-meta').textContent=`${project.owner_id||'Kurum belirtilmedi'} · ${project.province_or_region||'Bölge belirtilmedi'} · ${project.planning_year}`;
  document.getElementById('synthetic-watermark').hidden=mode!=='synthetic';
  document.getElementById('reference-label').hidden=projectDoc.water_budget.kind!=='calculated_reference';
  document.getElementById('reanalysis-banner').hidden=!report.requires_reanalysis;
  const badges=document.getElementById('project-status-badges');
  badges.replaceChildren(badge(`Revizyon ${projectDoc.data_revision}`,'ready'),badge(mode==='synthetic'?'SYNTHETIC / NOT OFFICIAL':mode==='reference'?'REFERENCE DEMO':'INSTITUTIONAL',mode==='institutional'?'ready':'warning'));
  facts('facts',[['Kurum / kuruluş',project.owner_id],['Planlama yılı',project.planning_year],['İl / bölge',project.province_or_region],['Havza / sulama alanı',project.basin_or_irrigation_area],['Su bütçesi',`${projectDoc.water_budget.amount??'—'} ${projectDoc.water_budget.unit}`],['Bütçe türü',projectDoc.water_budget.kind],['Analiz birimi',report.counts.analysis_units],['Toplam alan (da)',report.counts.total_area_da],['Ürün',report.counts.crops],['Ekonomi kapsamı',`${report.counts.economics_covered}/${report.counts.crops}`],['Geometri kapsamı',`${report.counts.geometry_covered}/${report.counts.analysis_units}`],['Aday birim kapsamı',`${overview.candidate_units}/${report.counts.analysis_units}`],['Water Data authority',JSON.stringify(Object.fromEntries(Object.entries(report.water_data_authority||{}).map(([key,value])=>[key,value.authority_class])))],['Veri revizyonu',projectDoc.data_revision]]);
  renderData(overview.import_status,catalog);
  renderReadiness(report,document.querySelector('#analysis-form [name=scenario]').value);
  setReadiness(report);
  showImports(report.imports);
  await refreshHistory(root(),safe,renderRun,()=>navigateToSection('result'));
}

function showImports(imports){document.getElementById('imports').textContent=JSON.stringify(imports,null,2);}

function clearProjectContext(container,reason){
  projectId=null;
  syncNavigationLinks();
  container.querySelectorAll('.project-card.active').forEach(card=>card.classList.remove('active'));
  document.getElementById('detail').hidden=true;
  document.getElementById('result').hidden=true;
  invalidatePreview(reason);
  document.getElementById('analysis-preview-card').hidden=true;
  document.getElementById('stale-preview-alert').hidden=true;
  message(reason,true);
}

async function openProject(id,{writeHash=false,scroll=true,section=DEFAULT_SECTION}={}){
  const changed=projectId!==id;
  projectId=id;
  syncNavigationLinks();
  if(writeHash)history.replaceState(null,'',canonicalHash(id,section));
  if(changed){
    document.getElementById('result').hidden=true;
    invalidatePreview('Proje değişti; yeni önizleme gerekli.');
  }
  await list(false);
  await refresh();
  if(scroll)applySection(section,{smooth:true});
}

async function list(restoreHash=true){
  const data=await api('/projects'),container=document.getElementById('projects');
  container.replaceChildren();
  if(!data.projects.length)container.textContent='Henüz proje yok. Yeni proje oluşturarak başlayın.';
  for(const project of data.projects){
    const button=document.createElement('button');
    button.type='button';button.className=`project-card${project.id===projectId?' active':''}`;button.setAttribute('aria-label',project.name);
    const title=document.createElement('strong'),meta=document.createElement('small');
    title.textContent=project.name;meta.textContent=`${project.owner_id||'Kurum belirtilmedi'} · ${project.planning_year}`;
    button.append(title,meta);button.onclick=()=>safe(()=>openProject(project.id,{writeHash:true}));container.append(button);
  }
  if(!restoreHash)return;
  const requested=hashProjectContext();
  if(requested.error){clearProjectContext(container,requested.error);return;}
  const found=data.projects.some(project=>project.id===requested.id);
  if(!found){clearProjectContext(container,`Hash bağlamındaki proje bulunamadı: ${requested.id}`);return;}
  if(projectId!==requested.id)await openProject(requested.id,{writeHash:false,scroll:false,section:requested.section});
  syncNavigationLinks();
  applySection(requested.section,{issue:requested.sectionIssue});
}

document.getElementById('create-project').onsubmit=event=>{event.preventDefault();safe(async()=>{const values=Object.fromEntries(new FormData(event.target));values.planning_year=Number(values.planning_year);values.annual_water_budget=values.annual_water_budget?Number(values.annual_water_budget):0;values.water_budget_unit='m3';const data=await post('/projects',values);await openProject(data.project.id,{writeHash:true});message('Proje oluşturuldu.');});};
document.getElementById('budget-form').onsubmit=event=>{event.preventDefault();safe(async()=>{const data=Object.fromEntries(new FormData(event.target));data.amount=Number(data.amount);data.unit='m3';await post(root()+'/water-budget',data);invalidatePreview('Su bütçesi değişti; yeni önizleme gerekli.');await refresh();message('Su bütçesi güncellendi.');});};
document.querySelector('[data-project-skip]').onclick=event=>{event.preventDefault();document.getElementById('main-content').scrollIntoView();};
for(const link of document.querySelectorAll('[data-project-section]'))link.onclick=event=>{event.preventDefault();navigateToSection(link.dataset.projectSection);};
wireImports(root,refresh,safe,()=>invalidatePreview('Proje verisi değişti; yeni önizleme gerekli.'));
wireAnalysis(root,safe,refresh,()=>navigateToSection('result'));
renderTemplates();
syncNavigationLinks();
window.addEventListener('hashchange',()=>safe(()=>list(true)));
safe(list);
