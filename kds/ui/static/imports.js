import {api,post,showJSON,message,facts} from './api.js';

const text=value=>Array.isArray(value)?value.join(', ')||'—':value??'—';

export function wireImports(root,refresh,safe,onMutation=()=>{}){
  let batch=null;
  let bulkItems=[];
  const steps=[...document.querySelectorAll('.stepper li')];
  const stage=n=>steps.forEach((item,i)=>{item.classList.toggle('done',i<n);item.classList.toggle('active',i===n);});
  const render=data=>{
    batch=data.id||data.batch_id;
    document.getElementById('import-preview').hidden=false;
    showJSON('preview',data);
    document.getElementById('mapping').value=JSON.stringify(data.mapping||{},null,2);
    facts('import-summary',[
      ['Dosya',data.filename],['Veri türü',data.data_type],['Durum',data.status],
      ['Satır',data.row_count],['Hata',data.validation_summary?.error??(data.errors||[]).length],
      ['Uyarı',data.validation_summary?.warning??(data.warnings||[]).length],['Dosya hash',data.file_hash],
    ]);
    stage(data.status==='applied'?5:data.status==='ready'?3:1);
  };

  document.getElementById('upload-form').onsubmit=e=>{
    e.preventDefault();
    safe(async()=>{render(await api(root()+'/imports',{method:'POST',body:new FormData(e.target)}));stage(1);await refresh();});
  };
  document.getElementById('map-import').onclick=()=>safe(async()=>{
    render(await post(root()+`/imports/${batch}/mapping`,{mapping:JSON.parse(document.getElementById('mapping').value)}));stage(3);
  });
  document.getElementById('confirm-import').onclick=()=>safe(async()=>{
    render(await post(root()+`/imports/${batch}/confirm`,{
      confirm:true,acknowledge_warnings:document.getElementById('acknowledge').checked,
      acknowledge_authority_override:document.getElementById('authority-override').checked,
      override_reason:document.getElementById('override-reason').value,
    }));
    stage(5);onMutation();await refresh();message('Aktarım onaylandı.');
  });

  const bulkResults=document.getElementById('bulk-import-results');
  const bulkBody=document.getElementById('bulk-import-body');
  const bulkConfirm=document.getElementById('bulk-confirm');
  const bulkNote=document.getElementById('bulk-import-note');
  const renderBulk=data=>{
    bulkItems=data.items||[];
    bulkBody.replaceChildren();
    for(const item of bulkItems){
      const d=item.detection||{},b=item.batch||{};
      const tr=document.createElement('tr');
      const state=d.state||'INVALID';
      const mapping=`${d.evidence?.required_matched??0}/${d.evidence?.required_total??0} · ${state}`;
      for(const value of [d.filename,d.detected_domain,text(d.year),text(d.scope),d.rows,mapping,text(d.authority),b.status||state]){
        const td=document.createElement('td');td.textContent=value??'—';tr.append(td);
      }
      tr.className=state==='AUTO_MATCHED'&&b.status==='ready'?'ready':state==='REVIEW_REQUIRED'?'warning':'blocked';
      tr.title=[...(d.sheet_names?.length?[`Sayfalar: ${d.sheet_names.join(', ')}`]:[]),...(d.issues||[]).map(issue=>issue.message)].join(' · ');
      bulkBody.append(tr);
    }
    bulkResults.hidden=false;
    const applicable=bulkItems.length>0&&bulkItems.every(item=>item.detection?.state==='AUTO_MATCHED'&&item.batch?.id);
    bulkConfirm.disabled=!applicable;
    bulkNote.textContent=applicable
      ? `${bulkItems.length} dosya otomatik eşleştirildi. Bağımlı doğrulamalar açık onay sırasında güvenli sırayla yenilenir; henüz hiçbiri aktif değildir.`
      : 'Paket fail-closed kaldı. REVIEW_REQUIRED, AMBIGUOUS, UNSUPPORTED veya INVALID satırları çözülmeden toplu aktivasyon yapılamaz.';
  };
  document.getElementById('bulk-upload-form').onsubmit=e=>{
    e.preventDefault();
    safe(async()=>{renderBulk(await api(root()+'/bulk-imports',{method:'POST',body:new FormData(e.target)}));await refresh();});
  };
  bulkConfirm.onclick=()=>safe(async()=>{
    if(!bulkItems.length||bulkItems.some(item=>item.detection?.state!=='AUTO_MATCHED'||!item.batch?.id))throw new Error('Toplu paket açık onay için hazır değil.');
    bulkConfirm.disabled=true;
    const priority={crops:10,analysis_units:20,economics:30,water_budget:40,candidates:50,scientific_inputs:60,
      annual_water_supply:70,monthly_water_supply:71,delivery_capacity:72,environmental_release:73,conveyance_efficiency:74,
      perennial_irrigation_requirement:75,crop_yield:80,crop_sale_price:81,crop_cost_components:82,crop_net_profit:83,
      seasonal_economics:84,crop_water_parameters:90,crop_phenology:91,geometries:100};
    const ordered=[...bulkItems].sort((a,b)=>(priority[a.detection.detected_data_type]??999)-(priority[b.detection.detected_data_type]??999));
    for(const item of ordered){
      const id=item.batch.id;
      const remapped=await post(root()+`/imports/${id}/mapping`,{mapping:item.detection.mapping});
      if(remapped.status!=='ready')throw new Error(`${item.detection.filename}: doğrulama READY üretmedi.`);
      item.batch=await post(root()+`/imports/${id}/confirm`,{confirm:true,acknowledge_warnings:true});
    }
    onMutation();await refresh();renderBulk({items:bulkItems});message('Toplu paket açık onayla projeye uygulandı.');
  });

  document.getElementById('scientific-form').onsubmit=e=>{
    e.preventDefault();
    safe(async()=>{const file=new FormData(e.target).get('file');await post(root()+'/scientific-inputs',JSON.parse(await file.text()));onMutation();await refresh();message('Bilimsel girdiler kaydedildi; hazırlık raporu yenilendi.');});
  };
}
