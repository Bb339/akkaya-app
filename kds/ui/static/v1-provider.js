(function(){
  'use strict';
  const query=new URLSearchParams(location.search);
  const providers=query.getAll('provider'),projects=query.getAll('project_id'),runs=query.getAll('run_id'),units=query.getAll('unit');
  const requestedProvider=providers.length===0?'AKKAYA_REFERENCE':providers.length===1?providers[0]:null;
  // Only the absent/default provider and one explicit AKKAYA_REFERENCE value
  // may boot reference data. Every other provider-shaped context is isolated
  // before validity is evaluated.
  const canonicalReference=(providers.length===0||
    (providers.length===1&&providers[0]==='AKKAYA_REFERENCE'))&&
    projects.length===0&&runs.length===0&&units.length===0;
  const projectMode=!canonicalReference;
  const initialSearch=location.search;
  const canonicalId=value=>typeof value==='string'&&/^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(value)?value:null;
  let context=null,preview=null,providerMap=null,providerLayers=null,selectedUnit=null,installingUnits=false,unitObserver=null;
  const blockedReferencePaths=[];
  const nativeFetch=window.fetch.bind(window);

  if(projectMode){
    // The frozen V1 refresh assumes an Akkaya parcel object.  Project mode
    // owns the same panels through the provider adapter, so stop that legacy
    // refresh before DOMContentLoaded can dereference reference-only state.
    window.refreshUI=()=>{};
    window.fetch=function(input,options){
      const url=new URL(input instanceof Request?input.url:String(input),location.origin);
      const blocked=(url.pathname==='/api/parcels'||url.pathname==='/api/optimize'||url.pathname==='/api/meta'||
        url.pathname==='/api/water_allocation_logic'||url.pathname==='/api/defense-datasets'||
        url.pathname==='/api/years'||url.pathname.startsWith('/api/geojson_')||url.pathname.startsWith('/data/'));
      if(blocked){blockedReferencePaths.push(url.pathname);return Promise.reject(new Error(`PROJECT_DATA modunda reference endpoint engellendi: ${url.pathname}`));}
      return nativeFetch(input,options);
    };
  }

  const html=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const number=(value,digits=2)=>value===null||value===undefined||!Number.isFinite(Number(value))?'—':Number(value).toLocaleString('tr-TR',{maximumFractionDigits:digits});
  const metric=(value,digits=2,missing='SAĞLANMADI / NOT PROVIDED')=>
    value===null||value===undefined||!Number.isFinite(Number(value))?missing:number(value,digits);
  const byId=id=>document.getElementById(id);
  function setDrawer(open){
    const shell=byId('v1-provider-shell'),toggle=byId('v1-provider-toggle'),scrim=byId('v1-provider-scrim');
    if(!shell||!toggle)return;shell.classList.toggle('is-open',open);shell.setAttribute('aria-hidden',String(!open));
    toggle.setAttribute('aria-expanded',String(open));if(scrim)scrim.hidden=!open;
  }
  function wireDrawer(){
    byId('v1-provider-toggle')?.addEventListener('click',()=>setDrawer(!byId('v1-provider-shell')?.classList.contains('is-open')));
    byId('v1-provider-close')?.addEventListener('click',()=>setDrawer(false));
    byId('v1-provider-scrim')?.addEventListener('click',()=>setDrawer(false));
    document.addEventListener('keydown',event=>{if(event.key==='Escape')setDrawer(false);});
  }
  const api=async(path,options={})=>{
    const response=await nativeFetch(`/api/v2${path}`,options);
    const body=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(body.error||`İstek başarısız (${response.status}).`);
    return body;
  };
  const payload=()=>{
    const algorithm=(byId('algoSelect')?.value||'ga').toUpperCase();
    const scenario=(byId('seasonSourceSel')?.value||'s1').toUpperCase();
    const selected=document.querySelector('input[name="scenario"]:checked')?.value||'su_tasarruf';
    const objective={su_tasarruf:'water_saving',maks_kar:'max_profit',su_etkin:'water_efficiency'}[selected]||'water_saving';
    const configs={GA:{popSize:12,generations:10,cxRate:.7,mutRate:.08},ACO:{ants:10,iterations:10,rho:.25,q:1},ABC:{foodSources:10,cycles:10,limit:4}};
    return {execution_profile:'VERIFIED_INSTITUTIONAL',scenario,algorithm,objective,seed:Number(byId('v1-provider-seed')?.value||123),water_budget_ratio:1,config:configs[algorithm]};
  };
  function canonicalUrl({projectId=context?.project?.id,runId=context?.run?.id,unitId=selectedUnit}={}){
    const next=new URL('/',location.origin);next.searchParams.set('provider','PROJECT_DATA');next.searchParams.set('project_id',projectId);
    if(runId)next.searchParams.set('run_id',runId);if(unitId)next.searchParams.set('unit',unitId);return next.pathname+next.search;
  }
  function fail(message){
    document.body.classList.add('project-provider-failed');
    const target=byId('v1-provider-error');if(target){target.hidden=false;target.textContent=`Proje bağlamı açılamadı: ${message} Akkaya verisine otomatik geçiş yapılmadı.`;}
    const name=byId('v1-provider-name');if(name)name.textContent='PROJECT DATA · BAĞLAM GEÇERSİZ';
    for(const id of ['runOptBtn','runOptBtnSecondary','v1-provider-preview']){const button=byId(id);if(button)button.disabled=true;}
    wireDrawer();setDrawer(true);
  }
  function setText(id,value){const node=byId(id);if(node)node.textContent=value??'—';}
  function neutralizeReferenceSurface(){
    if(!context)return;
    const title=document.querySelector('.summary-block-title');if(title)title.textContent=`${context.project.name} · Proje Özeti`;
    setText('basinSummaryNote',`${context.project.planning_year} proje toplamı · yalnız PROJECT_DATA`);
    const droughtTitle=document.querySelector('#waterRiskSection .drought-details__title');if(droughtTitle)droughtTitle.textContent='Kuraklık göstergeleri · proje verisi sağlanmadı';
    setText('droughtSummaryBadge','SAĞLANMADI');
    const droughtBody=document.querySelector('#waterRiskSection .drought-details__body');if(droughtBody)droughtBody.innerHTML='<p class="v1-missing-state">SAĞLANMADI / NOT PROVIDED — proje paketi kuraklık gösterge serisi içermiyor; Akkaya reference verisi kullanılmadı.</p>';
    const headings=[...document.querySelectorAll('.card-subtitle')];
    const economics=headings.find(node=>node.textContent.includes('Ekonomik dayanak'));if(economics)economics.textContent=`${context.project.planning_year} proje ekonomik dayanağı`;
    const current=headings.find(node=>node.textContent.includes('Mevcut Ürün Deseni'));if(current)current.textContent='Proje mevcut ürün deseni';
    const business=byId('businessMetricsBox');if(business&&!context.run)business.textContent='SAĞLANMADI / NOT PROVIDED — saklanmış proje sonucu açıldığında backend ekonomik çıktısı gösterilir.';
    const waterYear=byId('waterYear');if(waterYear){waterYear.replaceChildren(new Option(`${context.project.planning_year} · proje planlama yılı`,String(context.project.planning_year),true,true));waterYear.disabled=true;}
  }
  function renderFacts(){
    const s1=context.capabilities.scenarios.S1,s2=context.capabilities.scenarios.S2;
    const rows=[['Proje',context.project.name],['Project ID',context.project.id],['Planlama yılı',context.project.planning_year],['Revision',context.project_revision],['Authority',context.authority],['Classification',context.synthetic?'SYNTHETIC_TEST_PROJECT':'INSTITUTIONAL_PROJECT'],['Analiz birimi',context.unit_count],['Toplam alan',`${number(context.total_area_da)} da`],['Ürün',context.crop_count],['Aday kapsamı',`${context.candidate_unit_count}/${context.unit_count}`],['Geometri',`${context.geometry.available}/${context.geometry.total} · ${context.geometry.coverage}`],['Readiness',`S1 ${s1.ready?'READY':'BLOCKED'} · S2 ${s2.ready?'READY':'BLOCKED'}`]];
    byId('v1-provider-facts').innerHTML=rows.map(([label,value])=>`<div class="v1-provider-fact"><span>${html(label)}</span><strong>${html(value)}</strong></div>`).join('');
  }
  function renderRequirements(){
    const requirement=context.requirements;
    const guidance={
      analysis_units:'Analiz birimleri gerekli; parsel veya birim kimliği, alan ve mevcut ürün sütunlarını içeren dosyayı yükleyin.',
      annual_water:'Yıllık su arzı gerekli; proje yılına ait doğrulanabilir yıllık tahsis veya arz verisini yükleyin.',
      monthly_supply:'Aylık su arzı gerekli; planlama yılının aylık kullanılabilir su serisini yükleyin.',
      delivery:'Teslim kapasitesi gerekli; aylık kanal veya sistem teslim kapasitesini yükleyin.',
      conveyance:'İletim randımanı gerekli; proje kapsamındaki doğrulanabilir randıman değerini yükleyin.',
      crop_parameters:'Ürün su parametreleri gerekli; ürün bazında doğrulanabilir su parametrelerini yükleyin.',
      phenology:'Fenoloji verisi gerekli; ekim, gelişim ve hasat dönemlerini içeren kaynağı yükleyin.',
      economics:'Ekonomik veri gerekli; seçilen kapsam için verim, fiyat ve maliyet bileşenlerini yükleyin.',
      geometry:'Harita geometrisi analiz için zorunlu değildir; ancak harita üzerinde birim gösterimi için GeoJSON yükleyebilirsiniz.'
    };
    byId('v1-requirement-list').innerHTML=requirement.items.map(item=>{
      const action=item.status==='PROVIDED'||item.status==='NOT_APPLICABLE'?'':guidance[item.key]||'Bu veri eksik veya doğrulanamadı; teknik ayrıntıyı inceleyip uygun proje verisini yükleyin.';
      const explanation=[item.requirement,item.explanation_tr,action].filter(Boolean).join(' · ');
      return `<article class="v1-requirement" data-status="${html(item.status)}"><strong><span>${html(item.label)}</span><span>${html(item.status)}</span></strong><small>${html(explanation)}</small>${item.technical_detail?`<details><summary>Teknik ayrıntı</summary><code>${html(item.technical_status)}: ${html(item.technical_detail)}</code></details>`:''}</article>`;
    }).join('');
    const scenario=context.capabilities.scenarios[requirement.scenario];
    byId('v1-provider-preview-state').className=scenario.ready?'v1-state-ready':'v1-state-blocked';
    byId('v1-provider-preview-state').textContent=scenario.ready?'VERIFIED READY':'BLOCKED · Gereksinimleri inceleyin';
    byId('v1-provider-preview').disabled=!scenario.ready;
    for(const option of byId('seasonSourceSel')?.options||[]){const key=option.value.toUpperCase();option.disabled=!context.capabilities.scenarios[key]?.ready;option.title=option.disabled?(context.capabilities.scenarios[key]?.blocking_reasons||[]).join(' · '):'';}
  }
  function geometryMessage(){
    const coverage=context.geometry;
    return coverage.coverage==='FULL'?`${coverage.total} birimin tamamında proje geometrisi mevcut.`:
      coverage.coverage==='PARTIAL'?`${coverage.total} birimin ${coverage.available}'sinde harita geometrisi mevcut. Tüm birimler seçilebilir.`:
      'Bu proje için harita geometrisi sağlanmadı. Analiz haritasız çalışabilir; koordinat üretilmedi.';
  }
  function installUnits(){
    const select=byId('parcelSelect');if(!select)return;
    installingUnits=true;
    select.replaceChildren();
    for(const unit of context.units){const option=document.createElement('option');option.value=unit.analysis_unit_id;option.textContent=`${unit.analysis_unit_id}${unit.settlement?' · '+unit.settlement:''}${unit.current_crop?' · '+unit.current_crop:''}`;select.append(option);}
    selectedUnit=(units.length===1?units[0]:null)||selectedUnit||context.units[0]?.analysis_unit_id||null;
    if(selectedUnit&&!context.units.some(unit=>unit.analysis_unit_id===selectedUnit))selectedUnit=context.units[0]?.analysis_unit_id||null;
    if(selectedUnit)select.value=selectedUnit;
    if(!select.dataset.projectProviderBound){
      select.dataset.projectProviderBound='1';
      select.addEventListener('change',event=>{event.stopImmediatePropagation();selectedUnit=select.value;renderUnit();history.pushState(null,'',canonicalUrl({unitId:selectedUnit}));},{capture:true});
    }
    installingUnits=false;
    renderUnit();
  }
  function guardProjectUnits(){
    const select=byId('parcelSelect');if(!select||unitObserver)return;
    unitObserver=new MutationObserver(()=>{
      if(installingUnits||!context)return;
      const values=[...select.options].map(option=>option.value);
      const expected=context.units.map(unit=>unit.analysis_unit_id);
      if(values.length!==expected.length||values.some((value,index)=>value!==expected[index]))queueMicrotask(installUnits);
    });
    unitObserver.observe(select,{childList:true});
  }
  function renderUnit(){
    const unit=context.units.find(value=>value.analysis_unit_id===selectedUnit);if(!unit)return;
    const result=unit.result||{};
    setText('parcelSummaryTitle',`${unit.analysis_unit_id} · Proje analiz birimi`);
    setText('parcelSummaryNote',`${unit.current_crop||'Mevcut ürün sağlanmadı'} · ${number(unit.area_da)} da`);
    setText('mWaterCurrent',unit.current_water_m3==null?'Mevcut su değeri sağlanmadı':metric(unit.current_water_m3));setText('mWaterScenario',metric(result.authoritative_unit_water_m3));
    setText('mProfitCurrent',unit.current_profit_tl==null?'Mevcut kâr değeri sağlanmadı':metric(unit.current_profit_tl));setText('mProfitScenario',metric(result.unit_profit_tl));
    setText('mEffCurrent',unit.current_efficiency_tl_per_m3==null?'Mevcut etkinlik değeri sağlanmadı':metric(unit.current_efficiency_tl_per_m3,4));setText('mEffScenario',metric(result.efficiency_tl_per_m3,4,'SAĞLANMADI / NOT PROVIDED'));
    const cards=byId('productCards');if(cards)cards.innerHTML=(result.selected_crops||[]).length?(result.selected_crops||[]).map(row=>`<article class="product-card"><strong>${html(row.crop)}</strong><span>${html(row.season||'')}</span></article>`).join(''):'<div class="small muted">Bu birim için henüz saklanmış optimizasyon deseni yok.</div>';
    document.querySelectorAll('[data-v1-provider-unit]').forEach(node=>node.classList.toggle('v1-project-unit-active',node.dataset.v1ProviderUnit===selectedUnit));
    focusGeometry(unit);
  }
  function resetMap(){
    const root=byId('map');if(!root||!window.L)return null;
    try{providerMap=(typeof map!=='undefined'&&map)?map:null;}catch(_error){providerMap=null;}
    if(!providerMap)return null;
    try{if(parcelLayer)providerMap.removeLayer(parcelLayer);}catch(_error){}
    try{if(typeof customUserLayer!=='undefined'&&customUserLayer)providerMap.removeLayer(customUserLayer);}catch(_error){}
    try{if(providerLayers)providerMap.removeLayer(providerLayers);}catch(_error){}
    try{providerLayers=L.featureGroup().addTo(providerMap);}catch(_error){providerLayers=null;}
    return providerMap;
  }
  function renderMap(){
    byId('v1-geometry-status').textContent=geometryMessage();
    const current=resetMap();if(!current)return;
    const layers=[];
    for(const unit of context.units){
      let layer=null;
      try{
        if(unit.geometry&&['Polygon','MultiPolygon'].includes(unit.geometry.type))layer=L.geoJSON({type:'Feature',properties:{id:unit.analysis_unit_id},geometry:unit.geometry});
        else if(unit.latitude!==null&&unit.latitude!==undefined&&unit.longitude!==null&&unit.longitude!==undefined)layer=L.marker([Number(unit.latitude),Number(unit.longitude)]);
        if(layer){layer.addTo(providerLayers||current);layer.on?.('click',()=>{selectedUnit=unit.analysis_unit_id;byId('parcelSelect').value=selectedUnit;renderUnit();history.pushState(null,'',canonicalUrl({unitId:selectedUnit}));});layer.__providerUnit=unit.analysis_unit_id;layers.push(layer);}
      }catch(_error){}
    }
    if(layers.length){try{const group=L.featureGroup(layers);current.fitBounds(group.getBounds().pad(.15));}catch(_error){}}
  }
  function focusGeometry(unit){
    if(!providerMap)return;
    try{(providerLayers||providerMap).eachLayer?.(layer=>{if(layer.__providerUnit===unit.analysis_unit_id){if(layer.setStyle)layer.setStyle({color:'#f59f00',weight:4,fillOpacity:.28});if(layer.getBounds)providerMap.fitBounds(layer.getBounds().pad(.3));else if(layer.getLatLng)providerMap.setView(layer.getLatLng(),14);}else if(layer.setStyle)layer.setStyle({color:'#176b57',weight:2,fillOpacity:.16});});}catch(_error){}
  }
  function monthlyRows(result){
    const supply=result.monthly_supply_validation||{},delivery=result.monthly_delivery_validation||{},account=result.water_profile_accounting||{};
    const demand=account.monthly_demand_m3||account.planning_year_monthly_demand_m3||supply.demand_m3||delivery.demand_m3||{};
    const available=supply.usable_supply_m3||supply.supply_m3||supply.available_supply_m3||{};const capacity=delivery.capacity_m3||delivery.delivery_capacity_m3||{};
    const keys=new Set([...Object.keys(demand||{}),...Object.keys(available||{}),...Object.keys(capacity||{})]);
    return [...keys].sort().map(key=>[key,demand[key],available[key],capacity[key],(supply.violating_months||[]).includes(key)?'ARZ AŞILDI':(delivery.violating_months||[]).includes(key)?'KAPASİTE AŞILDI':'PASS']);
  }
  function table(headers,rows){return `<table class="v1-provider-table"><thead><tr>${headers.map(h=>`<th>${html(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map(value=>`<td>${html(value??'SAĞLANMADI')}</td>`).join('')}</tr>`).join('')}</tbody></table>`;}
  function renderRun(run){
    if(!run)return;const result=run.result||{},summary=run.summary||{};context.run=run;
    const diagnostic=result.feasible===false||result.diagnostic===true;
    byId('v1-project-result').hidden=false;
    byId('v1-project-result-summary').innerHTML=`<h3>${diagnostic?'DIAGNOSTIC / UYGULANABİLİR ÖNERİ DEĞİL':'Saklanmış proje sonucu'}</h3><div class="v1-result-grid">${[
      ['Run ID',run.id],['Senaryo',run.scenario],['Algoritma',run.algorithm],['Hedef',run.configuration?.objective],['Seed',run.seed],['Otorite',run.result_authority_label],['Toplam net kâr (TL)',metric(result.total_profit_tl)],['TL/m³',metric(result.efficiency_tl_per_m3,4)],['Aktif alan (da)',metric(summary.active_area_da)],['Feasibility',result.feasible===true?'PASS':result.feasible===false?'FAIL':'SAĞLANMADI'],['Score',metric(summary.score,5)]
    ].map(([label,value])=>`<div class="v1-result-card"><span>${html(label)}</span><strong>${html(value)}</strong></div>`).join('')}</div>`;
    const reconciliation=result.water_reconciliation||{};
    byId('v1-project-water-accounting').innerHTML=`<h4>Su muhasebesi ve uzlaştırma</h4><div class="v1-result-grid">${[
      ['Optimizer su kullanımı (m³)',metric(result.optimizer_water_m3)],
      ['Doğrulanmış / otoritatif su (m³)',metric(result.authoritative_water_m3)],
      ['Planlama yılı suyu (m³)',metric(result.planning_year_profile_water_m3)],
      ['Tam sezon suyu (m³)',metric(result.verified_profile_water_m3)],
      ['Fark (m³)',metric(result.water_accounting_difference_m3??reconciliation.difference_m3)],
      ['Fark (%)',metric(result.water_accounting_difference_pct??reconciliation.difference_pct,4)]
    ].map(([label,value])=>`<div class="v1-result-card"><span>${html(label)}</span><strong>${html(value)}</strong></div>`).join('')}</div><p class="v1-provider-explanation">Optimizer su kullanımı motorun plan çıktısıdır. Doğrulanmış / otoritatif su, backend'in saklanmış çalışma sonrası su muhasebesidir; dönem ve doğrulama kapsamları farklı olduğunda değerler farklı olabilir.</p>`;
    const annual=result.annual_budget_validation;
    byId('v1-project-annual-budget').innerHTML=`<h4>Yıllık su bütçesi doğrulaması</h4>${annual&&typeof annual==='object'?table(['Talep (m³)','Kullanılabilir bütçe (m³)','Durum','Backend açıklaması'],[[metric(annual.demand_m3),metric(annual.usable_supply_m3??annual.available_budget_m3),annual.status||'SAĞLANMADI',annual.reason||annual.message||'Backend ek açıklama sağlamadı.']]):'<p class="v1-missing-state">SAĞLANMADI / NOT PROVIDED — backend yıllık bütçe doğrulaması üretmedi.</p>'}`;
    const warnings=[...(run.warnings||[]),...(result.warnings||[])].filter((value,index,all)=>value&&all.indexOf(value)===index);
    byId('v1-project-warnings').innerHTML=`<h4>Analiz uyarıları</h4>${warnings.length?`<ul class="v1-warning-list">${warnings.map(value=>`<li>${html(value)}</li>`).join('')}</ul>`:'<p class="v1-empty-state">Backend bu çalışma için uyarı bildirmedi.</p>'}`;
    const monthly=monthlyRows(result);byId('v1-project-monthly').innerHTML=`<h4>Aylık su doğrulaması</h4>${monthly.length?table(['Ay','Talep','Kullanılabilir arz','Teslim kapasitesi','Durum'],monthly.map(row=>row.map((value,index)=>index>0&&index<4?metric(value):value))):'<p class="v1-missing-state">SAĞLANMADI / NOT PROVIDED — backend aylık talep, arz veya teslim serisi üretmedi.</p>'}`;
    const shares=result.crop_shares&&typeof result.crop_shares==='object'?Object.entries(result.crop_shares):[];byId('v1-project-crops').innerHTML=`<h4>Ürün kompozisyonu</h4>${shares.length?table(['Ürün','Pay'],shares.map(([crop,share])=>[crop,`${number(Number(share)*100)}%`])):'<p>NOT PROVIDED / NOT APPLICABLE — kanonik crop_shares üretilmedi.</p>'}<p>HHI: <strong>${number(result.hhi??result.HHI,4)}</strong></p>`;
    const resultUnits=result.presentation_units||[];byId('v1-project-units').innerHTML=`<h4>Birim sonuçları</h4><div class="v1-provider-table-wrap">${table(['Birim','Mevcut ürün','Seçilen desen','Su (m³)','Kâr (TL)','Uyarılar'],resultUnits.map(unit=>[unit.analysis_unit_id,unit.current_crop,(unit.selected_crops||[]).map(v=>v.crop).join(' + '),metric(unit.authoritative_unit_water_m3),metric(unit.unit_profit_tl),(unit.warnings||[]).join(' · ')||'Backend uyarısı yok']))}</div>`;
    byId('v1-project-provenance').textContent=JSON.stringify({project_id:run.project_id,project_revision:context.project_revision,run_id:run.id,execution_profile:run.execution_profile,scenario:run.scenario,algorithm:run.algorithm,objective:run.configuration?.objective,seed:run.seed,selection_hash:run.provenance?.selection_hash||run.result?.result_provenance?.selection_hash,engine_commit:run.provenance?.engine_commit||run.result?.result_provenance?.engine_commit,result_authority_label:run.result_authority_label,provenance:run.provenance,presentation_context:run.presentation_context},null,2);
    context.units=context.units.map(unit=>({...unit,result:resultUnits.find(row=>row.analysis_unit_id===unit.analysis_unit_id)||unit.result}));
    setText('bWaterCurrent','SAĞLANMADI / NOT PROVIDED');setText('bWaterScenario',metric(result.authoritative_water_m3));setText('bProfitCurrent','SAĞLANMADI / NOT PROVIDED');setText('bProfitScenario',metric(result.total_profit_tl));setText('bEffCurrent','SAĞLANMADI / NOT PROVIDED');setText('bEffScenario',metric(result.efficiency_tl_per_m3,4));setText('metricsTitle',`${context.project.name} · Saklanmış analiz sonucu`);
    const objectiveLabel={water_saving:'Su tasarrufu',max_profit:'Kâr',water_efficiency:'Su etkin kullanım'}[run.configuration?.objective]||run.configuration?.objective||'SAĞLANMADI';setText('activeObjectiveBadge',`Aktif hedef: ${objectiveLabel}`);
    setDrawer(true);
    neutralizeReferenceSurface();
    renderUnit();
  }
  async function createPreview(){
    preview=null;const state=byId('v1-provider-preview-state');state.textContent='Backend önizlemesi hazırlanıyor…';
    const request=payload();preview=await api(`/projects/${encodeURIComponent(context.project.id)}/analysis-preview`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});
    if(!preview.ready){state.className='v1-state-blocked';state.textContent=`BLOCKED · ${(preview.blocking_reasons||[]).join(' · ')}`;return null;}
    state.className='v1-state-ready';state.textContent=`PINNED · revision ${preview.preview_revision} · ${preview.selection_hash}`;return {request,preview};
  }
  async function runProject(){
    if(document.querySelector('input[name="scenario"]:checked')?.value==='mevcut'){
      preview=null;const state=byId('v1-provider-preview-state');state.className='v1-empty-state';state.textContent='Mevcut görünüm yalnız proje girdilerini gösterir; optimizasyon çalıştırmaz.';setDrawer(true);return;
    }
    const pinned=preview?.ready?{request:payload(),preview}:await createPreview();if(!pinned)return;
    const body={...pinned.request,preview_token:pinned.preview.preview_token,preview_revision:pinned.preview.preview_revision,selection_hash:pinned.preview.selection_hash};
    const run=await api(`/projects/${encodeURIComponent(context.project.id)}/analyses`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const url=canonicalUrl({runId:run.id,unitId:selectedUnit});history.pushState(null,'',url);renderRun(run);renderHistory();
  }
  function renderHistory(){
    const items=context.history?.items||[];byId('v1-project-history-list').innerHTML=items.length?items.map(item=>`<button type="button" class="btn-secondary v1-history-button" data-run-id="${html(item.id)}">${html(item.id)} · ${html(item.scenario)} · ${html(item.algorithm)} · ${html(item.status)}</button>`).join(''):'Henüz saklanmış çalışma yok.';
    byId('v1-project-history-list').querySelectorAll('[data-run-id]').forEach(button=>button.onclick=()=>location.assign(canonicalUrl({runId:button.dataset.runId,unitId:selectedUnit})));
  }
  function wireControls(){
    wireDrawer();
    byId('v1-provider-preview').onclick=()=>createPreview().catch(error=>fail(error.message));
    for(const id of ['runOptBtn','runOptBtnSecondary']){const button=byId(id);if(button)button.addEventListener('click',event=>{event.preventDefault();event.stopImmediatePropagation();runProject().catch(error=>fail(error.message));},{capture:true});}
    for(const input of document.querySelectorAll('#algoSelect,#seasonSourceSel,input[name="scenario"],#v1-provider-seed')){
      const invalidate=event=>{event.stopImmediatePropagation();preview=null;const baseline=document.querySelector('input[name="scenario"]:checked')?.value==='mevcut';byId('v1-provider-preview-state').textContent=baseline?'Mevcut görünüm: optimizasyon uygulanmaz.':'Yapılandırma değişti; yeni önizleme gerekli.';byId('v1-provider-preview').disabled=baseline||!context.capabilities.scenarios[(byId('seasonSourceSel')?.value||'s1').toUpperCase()]?.ready;};
      input.addEventListener('input',invalidate,{capture:true});
      input.addEventListener('change',invalidate,{capture:true});
    }
    byId('v1-project-provider-select').onchange=event=>{if(event.target.value)location.assign(`/?provider=PROJECT_DATA&project_id=${encodeURIComponent(event.target.value)}`);};
  }
  async function loadProjectList(){
    const data=await api('/projects');const select=byId('v1-project-provider-select');for(const project of data.projects){const option=document.createElement('option');option.value=project.id;option.textContent=`${project.name} · ${project.planning_year}`;select.append(option);}if(context?.project?.id)select.value=context.project.id;
  }
  async function initProject(){
    document.body.classList.add('project-provider-mode');
    const shell=byId('v1-provider-shell');shell.dataset.provider='PROJECT_DATA';
    if(providers.length!==1||projects.length!==1||runs.length>1||units.length>1)throw new Error('Tek bir provider, project_id, run_id ve unit parametresi gerekir.');
    const projectId=canonicalId(projects[0]);if(!projectId)throw new Error('project_id biçimi geçersiz.');
    if(requestedProvider!=='PROJECT_DATA')throw new Error('Bilinmeyen provider.');
    selectedUnit=units[0]||null;
    const suffix=`?${runs[0]?`run_id=${encodeURIComponent(runs[0])}&`:''}scenario=${encodeURIComponent((byId('seasonSourceSel')?.value||'s1').toUpperCase())}`;
    context=await api(`/projects/${encodeURIComponent(projectId)}/decision-context${suffix}`);
    shell.dataset.synthetic=String(context.synthetic);byId('v1-provider-context').hidden=false;setText('v1-provider-name',`PROJECT DATA · ${context.project.name}`);setText('v1-provider-authority',`${context.authority} · ${context.execution_profile}`);setText('v1-provider-badge','PROJECT DATA');byId('v1-manage-project').href=`/projects#project=${encodeURIComponent(projectId)}&section=data`;
    setText('dataSourceLabel',`PROJECT DATA · ${context.project.id}`);setText('dataLoadBadge',context.authority);
    renderFacts();renderRequirements();installUnits();guardProjectUnits();wireControls();renderHistory();neutralizeReferenceSurface();await loadProjectList();
    window.refreshUI=()=>{if(context)renderUnit();};
    setTimeout(()=>{renderMap();renderUnit();neutralizeReferenceSurface();},1200);
    if(context.run)renderRun(context.run);
    window.__V1_PROJECT_PROVIDER__={get context(){return context;},get blockedReferencePaths(){return [...blockedReferencePaths];},get selectedUnit(){return selectedUnit;}};
  }
  async function initReference(){
    const shell=byId('v1-provider-shell');if(shell)shell.dataset.provider='AKKAYA_REFERENCE';
    if(requestedProvider!==null&&requestedProvider!=='AKKAYA_REFERENCE')throw new Error('Bilinmeyen provider; otomatik referans geçişi uygulanmadı.');
    if(projects.length||runs.length||units.length)throw new Error('AKKAYA_REFERENCE bağlamında project/run/unit parametresi kabul edilmez.');
    wireDrawer();setText('v1-provider-badge','AKKAYA REF');await loadProjectList();window.__V1_PROJECT_PROVIDER__={provider:'AKKAYA_REFERENCE',blockedReferencePaths:[]};
  }
  document.addEventListener('DOMContentLoaded',()=>{
    const task=projectMode?initProject():initReference();task.catch(error=>fail(error.message));
    // V1 authentication and panel navigation use hash-only history entries.
    // Reload only when the authoritative provider query state changed.
    window.addEventListener('popstate',()=>{if(projectMode&&location.search!==initialSearch)location.reload();});
  });
})();
