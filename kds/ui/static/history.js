import {api} from './api.js';
let currentRoot=null,loaded=0;
const labels=['Run ID','Zaman','Senaryo','Algoritma','Seed','Hedef','Durum','Feasible','Su (m³)','Net kâr (TL)','TL/m³','Skor'];
export async function refreshHistory(root,safe,renderRun,append=false){
  const requestedRoot=root;
  if(!append){currentRoot=root;loaded=0;}
  const data=await api(root+`/analyses?offset=${loaded}&limit=25`);
  if(currentRoot!==requestedRoot)return;
  document.getElementById('history-section').hidden=false;
  const container=document.getElementById('history');
  let table=container.querySelector('table');
  if(!append||!table){table=document.createElement('table');const head=document.createElement('tr');for(const label of labels){const th=document.createElement('th');th.textContent=label;head.append(th);}table.append(head);container.replaceChildren(table);}
  for(const run of data.items){const row=document.createElement('tr'),link=document.createElement('button');link.textContent=run.id;link.type='button';
    link.onclick=()=>safe(async()=>{const value=await api(root+'/analyses/'+encodeURIComponent(run.id));if(currentRoot===root){renderRun(value);document.getElementById('result').scrollIntoView({behavior:'smooth'});}});
    const first=document.createElement('td');first.append(link);row.append(first);
    for(const value of [new Date(run.timestamp).toLocaleString('tr-TR'),run.scenario,run.algorithm,run.seed,run.objective,run.status,run.feasible,run.water,run.profit,run.efficiency,run.score]){const cell=document.createElement('td');cell.textContent=value===null?'Üretilmedi':typeof value==='number'?new Intl.NumberFormat('tr-TR',{maximumFractionDigits:4}).format(value):String(value);row.append(cell);}table.append(row);}
  loaded+=data.items.length;document.getElementById('history-count').textContent=data.count?`${loaded} / ${data.count} çalışma`:'Henüz analiz çalışması yok.';
  const more=document.getElementById('history-more');more.hidden=loaded>=data.count;more.onclick=()=>safe(()=>refreshHistory(root,safe,renderRun,true));
}
