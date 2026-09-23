import {post,facts,showJSON,message} from './api.js';
function renderPlan(result,scenario){
  const container=document.getElementById('plan');container.replaceChildren();
  const table=document.createElement('table'),head=document.createElement('tr');
  for(const label of ['Birim','Sezon','Ürün','Alan (da)','Su (m³)','Net kâr (TL)']){const th=document.createElement('th');th.textContent=label;head.append(th);}table.append(head);
  for(const row of result.details||[]){
    const seasons=scenario==='S1'?[["Tek ürün",{crop:row.chosenCrop,water_m3:row.water_m3,profit_tl:row.profit_tl}]]:[['Ana',row.primary],['İkinci',row.secondary]];
    for(const [season,crop] of seasons){if(!crop)continue;const tr=document.createElement('tr');
      for(const value of [row.parcelId,season,crop.crop,crop.area_da ?? row.area_da,crop.water_m3,crop.profit_tl]){const td=document.createElement('td');td.textContent=typeof value==='number'?new Intl.NumberFormat('tr-TR',{maximumFractionDigits:2}).format(value):value;tr.append(td);}table.append(tr);
    }
  }container.append(table);
}
export function wireAnalysis(root,safe,refresh){
  const form=document.getElementById('analysis-form');
  const defaults={GA:{popSize:12,generations:10,cxRate:.7,mutRate:.08},ACO:{ants:10,iterations:10,rho:.25,q:1},ABC:{foodSources:10,cycles:10,limit:4}};
  const config=()=>{form.elements.config.value=JSON.stringify(defaults[form.elements.algorithm.value],null,2);};config();form.elements.algorithm.onchange=config;
  const payload=()=>{const value=Object.fromEntries(new FormData(form));value.seed=Number(value.seed);value.water_budget_ratio=Number(value.water_budget_ratio);value.config=JSON.parse(value.config);return value;};
  document.getElementById('preview-analysis').onclick=()=>safe(async()=>{
    const preview=await post(root()+'/analysis-preview',payload()),target=document.getElementById('analysis-preview');
    target.hidden=false;target.textContent=JSON.stringify(preview,null,2);
    message(preview.ready?'Execution preview hazır.':'Execution blocked: '+preview.blocking_reasons.join('; '),!preview.ready);
  });
  form.onsubmit=e=>{e.preventDefault();safe(async()=>{
    const request=payload();
    const button=document.getElementById('run-button');button.disabled=true;message('Analiz ayrı süreçte çalışıyor; sonuç kaydediliyor…');
    try{
      const run=await post(root()+'/analyses',request),result=run.result,summary=run.summary;
      renderRun(run);await refresh();
    }finally{button.disabled=false;}
  });};
}

export function renderRun(run){
  const result=run.result || {},summary=run.summary || {};
  const label=document.getElementById('result-source-label');
  const synthetic=run.result_authority_label==='SYNTHETIC / NOT_OFFICIAL' || run.provenance.data_source_notes==='synthetic_test_fixture';
  label.className=synthetic?'watermark':'warning';
  label.textContent=run.result_authority_label || (synthetic?'Synthetic test project / Sentetik test verisi':run.provenance.water_budget?.kind==='calculated_reference'?'calculated_reference: hesaplanmış referans talep; resmî tahsis veya ölçülmüş baraj suyu değildir.':'');
      document.getElementById('result').hidden=false;
      facts('result-facts',[['Execution profile',run.execution_profile],['Result authority',run.result_authority_label],['Classification',result.classification],['Proje',run.provenance.project_name || run.project_id],['Proje kimliği',run.project_id],['Algoritma',run.algorithm],['Senaryo',run.scenario],['Seed',run.seed],['Toplam brüt su (m³)',result.total_water_m3],
        ['Uygulanan analiz bütçesi (m³)',result.water_budget_m3],['Su bütçesi türü',run.provenance.water_budget?.kind ?? 'Kayıtta yok'],['Toplam net kâr (TL)',result.total_profit_tl],['TL/m³',result.efficiency_tl_per_m3],['Uygunluk',result.feasible===true?'Uygun':result.feasible===false?'Uygun değil':'Motor bu metrik için değer üretmedi'],
        ['Skor',summary.score ?? 'Motor bu senaryo çıktısında skoru raporlamıyor'],['Toplam alan (da)',summary.total_area_da],['Aktif alan (da)',summary.active_area_da],['Nadas / boş alan (da)',summary.fallow_area_da],['Plan farkı',result.delta?JSON.stringify(result.delta):'Motor bu metrik için değer üretmedi']]);
      const list=document.getElementById('result-warnings');list.replaceChildren();for(const warning of run.warnings.length?run.warnings:['Ek veri uyarısı yok.']){const li=document.createElement('li');li.textContent=warning;list.append(li);}
      renderPlan(result.validated_final_plan || result,run.scenario);showJSON('provenance',{id:run.id,started_at:run.started_at,completed_at:run.completed_at,...run.provenance});message(run.status==='completed'?'Kayıtlı analiz sonucu gösteriliyor.':`Çalışma durumu: ${run.status}. ${run.error || ''}`,run.status==='failed');

}
