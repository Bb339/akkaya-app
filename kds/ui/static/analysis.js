import {post,facts,showJSON,message} from './api.js';
function renderPlan(result,scenario){
  const container=document.getElementById('plan');container.replaceChildren();
  const table=document.createElement('table'),head=document.createElement('tr');
  for(const label of ['Birim','Sezon','Ürün','Alan (da)','Su (m³)','Net kâr (TL)']){const th=document.createElement('th');th.textContent=label;head.append(th);}table.append(head);
  for(const row of result.details||[]){
    const seasons=scenario==='S1'?[["Tek ürün",{crop:row.chosenCrop,water_m3:row.water_m3,profit_tl:row.profit_tl}]]:[['Ana',row.primary],['İkinci',row.secondary]];
    for(const [season,crop] of seasons){if(!crop)continue;const tr=document.createElement('tr');
      for(const value of [row.parcelId,season,crop.crop,row.area_da,crop.water_m3,crop.profit_tl]){const td=document.createElement('td');td.textContent=typeof value==='number'?new Intl.NumberFormat('tr-TR',{maximumFractionDigits:2}).format(value):value;tr.append(td);}table.append(tr);
    }
  }container.append(table);
}
export function wireAnalysis(root,safe){
  const form=document.getElementById('analysis-form');
  const defaults={GA:{popSize:12,generations:10,cxRate:.7,mutRate:.08},ACO:{ants:10,iterations:10,rho:.25,q:1},ABC:{foodSources:10,cycles:10,limit:4}};
  const config=()=>{form.elements.config.value=JSON.stringify(defaults[form.elements.algorithm.value],null,2);};config();form.elements.algorithm.onchange=config;
  form.onsubmit=e=>{e.preventDefault();safe(async()=>{
    const payload=Object.fromEntries(new FormData(form));payload.seed=Number(payload.seed);payload.water_budget_ratio=Number(payload.water_budget_ratio);payload.config=JSON.parse(payload.config);
    const button=document.getElementById('run-button');button.disabled=true;message('Analiz ayrı süreçte çalışıyor; sonuç kaydediliyor…');
    try{
      const run=await post(root()+'/analyses',payload),result=run.result,summary=run.summary;
      document.getElementById('result').hidden=false;
      facts('result-facts',[['Proje',run.project_id],['Algoritma',run.algorithm],['Senaryo',run.scenario],['Seed',run.seed],['Toplam brüt su (m³)',result.total_water_m3],
        ['Uygulanan analiz bütçesi (m³)',result.water_budget_m3],['Toplam net kâr (TL)',result.total_profit_tl],['TL/m³',result.efficiency_tl_per_m3],['Uygunluk',result.feasible?'Uygun':'Uygun değil'],
        ['Skor',summary.score ?? 'Motor bu senaryo çıktısında skoru raporlamıyor'],['Toplam alan (da)',summary.total_area_da],['Aktif alan (da)',summary.active_area_da],['Nadas / boş alan (da)',summary.fallow_area_da],['Plan farkı',result.delta?JSON.stringify(result.delta):'Motor bu alanda fark raporlamıyor']]);
      const list=document.getElementById('result-warnings');list.replaceChildren();for(const warning of run.warnings.length?run.warnings:['Ek veri uyarısı yok.']){const li=document.createElement('li');li.textContent=warning;list.append(li);}
      renderPlan(result,run.scenario);showJSON('provenance',{id:run.id,started_at:run.started_at,completed_at:run.completed_at,...run.provenance});message('Analiz tamamlandı ve projeye kaydedildi.');
    }finally{button.disabled=false;}
  });};
}
