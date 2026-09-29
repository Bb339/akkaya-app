import {api,post,showJSON,message,facts} from './api.js';

const text=value=>Array.isArray(value)?value.join(', ')||'—':value??'—';

export function issueGuidance(issue={},detection={}){
  const fields=issue.fields||detection.missing_required_fields||[];
  const examples=issue.invalid_examples||[];
  const mappings=issue.fields&&typeof issue.fields==='object'&&!Array.isArray(issue.fields)?Object.keys(issue.fields):[];
  const values={
    missing_required_fields:{what:`Zorunlu sütun bulunamadı${fields.length?`: ${fields.join(', ')}`:''}.`,action:'Dosyanızdaki parsel/birim kimliği ve diğer zorunlu sütunları kontrol edin veya sütun eşleştirme adımından doğru alanları seçin.'},
    required_numeric_field_not_parseable:{what:`Sayısal olması gereken ${issue.field||'bir alanda'} okunamayan değer bulundu${examples.length?`: ${examples.join(', ')}`:''}.`,action:'Virgül/nokta biçimini ve sayı alanlarında metin içeren hücreleri kontrol edin.'},
    explicit_year_not_parseable:{what:`Planlama yılı okunamadı${examples.length?`: ${examples.join(', ')}`:''}.`,action:'Yıl değerini 2025 gibi dört haneli bir sayı olarak girin.'},
    wrong_planning_year:{what:`Dosyadaki planlama yılı proje yılıyla uyuşmuyor. Proje yılı: ${issue.project_year??'SAĞLANMADI'}; dosya yılı: ${(issue.file_years||[]).join(', ')||'SAĞLANMADI'}.`,action:'Doğru planlama yılına ait dosyayı yükleyin veya proje yılını doğrulayın.'},
    wrong_geographic_scope:{what:`Dosyanın coğrafi kapsamı projeyle uyuşmuyor: ${(issue.file_scopes||[]).join(', ')||'SAĞLANMADI'}.`,action:'Dosya kapsamını proje/bölge kimliğiyle aynı olacak şekilde kontrol edin.'},
    ambiguous_mapping:{what:`Bazı sütunlar birden fazla alana eşleşebilir${mappings.length?`: ${mappings.join(', ')}`:''}.`,action:'Önerilen sütun eşleştirmelerini inceleyip doğru canonical alanı seçin.'},
    ambiguous_data_type:{what:'Sistem bu dosyanın hangi veri türüne ait olduğunu güvenle belirleyemedi.',action:`Olası türleri kontrol edin: ${(issue.candidates||[]).join(', ')||'birden fazla eşleşme'}. İlgisiz ek dosyayı paketten çıkarın veya doğru veri dosyasını yükleyin.`},
    ambiguous_workbook_sheet:{what:'Çalışma kitabında aynı derecede uygun birden fazla sayfa bulundu.',action:`Doğru veri sayfasını seçin: ${(issue.sheets||[]).join(', ')||'sayfa adlarını kontrol edin'}.`},
    unsupported_extension:{what:'Bu dosya türü desteklenmiyor.',action:'Desteklenen biçimler: CSV, XLSX, GeoJSON.'},
    invalid_file:{what:'Dosya güvenli biçimde okunamadı.',action:detection.extension==='.geojson'?'GeoJSON geometrilerini ve analysis_unit_id eşleşmesini kontrol edin.':'Dosya biçimini, karakter kodlamasını ve tablo yapısını kontrol edin.'},
    ignored_not_relevant:{what:'Bu dosyada desteklenen bir veri alanına ait güvenilir yapısal kanıt bulunmadı.',action:'Dosya projeye uygulanmadı ve eksiksiz bir paketin aktivasyonunu engellemez. Dosya aslında proje verisiyse doğru şablonu ve zorunlu sütunları kullanın.'},
    unknown_unit:{what:'Harita geometrisindeki birim kimliği proje analiz birimleriyle eşleşmiyor.',action:'Geometri dosyasındaki kimlikleri analiz birimi dosyasıyla karşılaştırın.'},
    invalid_geometry:{what:'Coğrafi veri geometrisi geçersiz.',action:'GeoJSON koordinatlarını, geometri tipini ve kapalı poligon halkalarını kontrol edin.'},
    duplicate_geometry:{what:'Aynı geometri birden fazla analiz birimine atanmış.',action:'Her geometrinin tek bir analysis_unit_id ile eşleştiğini doğrulayın.'},
  };
  return values[issue.code]||{what:'Dosya otomatik olarak uygulanamadı.',action:'Teknik ayrıntıdaki hata kodunu inceleyin ve dosyayı onaylamadan önce düzeltin.'};
}

function guidancePanel(detection,batch){
  const issues=[...(detection.issues||[]),...(batch.issues||[])];
  const section=document.createElement('section');section.className='import-guidance';
  const heading=document.createElement('h5');heading.textContent='Türkçe kullanıcı yönlendirmesi';section.append(heading);
  if(!issues.length){const p=document.createElement('p');p.textContent='Dosya otomatik eşleştirildi; projeye uygulanması için açık onay bekleniyor.';section.append(p);return section;}
  for(const issue of issues){const guidance=issueGuidance(issue,detection);const article=document.createElement('article');
    const what=document.createElement('p');what.textContent=`Ne oldu? ${guidance.what}`;const action=document.createElement('p');action.textContent=`Ne yapmalısınız? ${guidance.action}`;
    article.append(what,action);section.append(article);
  }
  const technical=document.createElement('details');const summary=document.createElement('summary');summary.textContent='Teknik ayrıntı';const pre=document.createElement('pre');pre.textContent=JSON.stringify(issues,null,2);technical.append(summary,pre);section.append(technical);return section;
}

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
  const deferredDependencyCodes=new Set(['scientific_table','economic_contract','crop_parameter_contract']);
  const hasDefinitiveBatchError=item=>(item.batch?.issues||[]).some(issue=>
    issue.severity==='ERROR'&&!deferredDependencyCodes.has(issue.code)&&
      !(issue.code==='unknown_unit'&&item.batch?.base_revision===0));
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
      const details=document.createElement('details');
      const summary=document.createElement('summary');summary.textContent='Dosya önizlemesi';details.append(summary);
      const facts=document.createElement('dl');facts.className='import-preview-facts';
      for(const [label,value] of [['Seçilen sayfa',d.selected_sheet||'UYGULANMAZ'],['Sayfalar',text(d.sheet_names)],['Sütunlar',text(d.columns)],['İlk satırlar',`${(d.preview_rows||[]).length}/5`],['Önerilen eşleşme',`${d.evidence?.required_matched??0}/${d.evidence?.required_total??0}`]]){
        const dt=document.createElement('dt');dt.textContent=label;const dd=document.createElement('dd');dd.textContent=value;facts.append(dt,dd);
      }
      details.append(facts,guidancePanel(d,b));
      const technical=document.createElement('details');const technicalSummary=document.createElement('summary');technicalSummary.textContent='Ham önizleme JSON';
      const preview=document.createElement('pre');preview.textContent=JSON.stringify({
        selected_sheet:d.selected_sheet||null,sheet_names:d.sheet_names||[],columns:d.columns||[],
        preview_rows:d.preview_rows||[],mapping:d.mapping||{},issues:[...(d.issues||[]),...(b.issues||[])],
        planned_dataset:d.detected_data_type||null,sheet_selection:d.evidence?.sheet_selection||[]
      },null,2);technical.append(technicalSummary,preview);details.append(technical);tr.firstElementChild.append(details);
      tr.className=state==='AUTO_MATCHED'&&b.status==='ready'?'ready':state==='IGNORED_NOT_RELEVANT'?'warning':state==='REVIEW_REQUIRED'?'warning':'blocked';
      tr.title=state==='AUTO_MATCHED'?'Otomatik eşleşti; açık onay bekleniyor.':state==='IGNORED_NOT_RELEVANT'?'İlgisiz dosya güvenli biçimde yok sayıldı.':'Dosya otomatik uygulanmadı; Türkçe yönlendirmeyi açın.';
      bulkBody.append(tr);
    }
    bulkResults.hidden=false;
    const applicable=bulkItems.some(item=>item.detection?.state==='AUTO_MATCHED')&&bulkItems.every(item=>
      item.detection?.state==='IGNORED_NOT_RELEVANT'||(item.detection?.state==='AUTO_MATCHED'&&item.batch?.id&&!hasDefinitiveBatchError(item)));
    bulkConfirm.disabled=!applicable;
    bulkNote.textContent=applicable
      ? `${bulkItems.filter(item=>item.detection?.state==='AUTO_MATCHED').length} dosya otomatik eşleştirildi; ${bulkItems.filter(item=>item.detection?.state==='IGNORED_NOT_RELEVANT').length} açıkça ilgisiz dosya uygulanmadan yok sayıldı. Bağımlı doğrulamalar açık onay sırasında güvenli sırayla yenilenir.`
      : 'Paket fail-closed kaldı. REVIEW_REQUIRED, AMBIGUOUS, UNSUPPORTED veya INVALID satırları çözülmeden toplu aktivasyon yapılamaz.';
  };
  document.getElementById('bulk-upload-form').onsubmit=e=>{
    e.preventDefault();
    safe(async()=>{renderBulk(await api(root()+'/bulk-imports',{method:'POST',body:new FormData(e.target)}));await refresh();});
  };
  bulkConfirm.onclick=()=>safe(async()=>{
    if(!bulkItems.some(item=>item.detection?.state==='AUTO_MATCHED')||bulkItems.some(item=>item.detection?.state!=='IGNORED_NOT_RELEVANT'&&(item.detection?.state!=='AUTO_MATCHED'||!item.batch?.id||hasDefinitiveBatchError(item))))throw new Error('Toplu paket açık onay için hazır değil.');
    bulkConfirm.disabled=true;
    const priority={crops:10,analysis_units:20,economics:30,water_budget:40,candidates:50,scientific_inputs:60,
      annual_water_supply:70,monthly_water_supply:71,delivery_capacity:72,environmental_release:73,conveyance_efficiency:74,
      perennial_irrigation_requirement:75,crop_yield:80,crop_sale_price:81,crop_cost_components:82,crop_net_profit:83,
      seasonal_economics:84,crop_water_parameters:90,crop_phenology:91,geometries:100};
    const ordered=bulkItems.filter(item=>item.detection?.state==='AUTO_MATCHED').sort((a,b)=>(priority[a.detection.detected_data_type]??999)-(priority[b.detection.detected_data_type]??999));
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
