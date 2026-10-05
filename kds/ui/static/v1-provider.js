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
  let context=null,preview=null,providerMap=null,providerLayers=null,selectedUnit=null,installingUnits=false,unitObserver=null,providerMonthlyChart=null;
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
  const terminologyOriginal=new WeakMap();
  function applyProviderTerminology(isProject){
    const root=byId('panel');if(!root)return;
    const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,{acceptNode:node=>
      node.parentElement?.closest('script,style')?NodeFilter.FILTER_REJECT:NodeFilter.FILTER_ACCEPT});
    const replacements=[
      [/Parsel Haritası/g,'Analiz Birimleri Haritası'],[/Parsel seç/g,'Analiz birimi seç'],
      [/Seçili parsel/g,'Seçili analiz birimi'],[/Parsel Bazlı Özet/g,'Analiz Birimi Özeti'],
      [/Parsel çizim/g,'Analiz birimi geometrisi'],[/parsel çizim/g,'analiz birimi geometrisi'],
      [/Parseller/g,'Analiz birimleri'],[/parseller/g,'analiz birimleri'],
      [/Parselin/g,'Analiz biriminin'],[/parselin/g,'analiz biriminin'],
      [/Parselde/g,'Analiz biriminde'],[/parselde/g,'analiz biriminde'],
      [/Parsele/g,'Analiz birimine'],[/parsele/g,'analiz birimine'],
      [/Parseli/g,'Analiz birimini'],[/parseli/g,'analiz birimini'],
      [/Parsel/g,'Analiz birimi'],[/parsel/g,'analiz birimi']
    ];
    for(let node=walker.nextNode();node;node=walker.nextNode()){
      if(!terminologyOriginal.has(node))terminologyOriginal.set(node,node.nodeValue);
      const original=terminologyOriginal.get(node);
      node.nodeValue=isProject?replacements.reduce((value,[pattern,replacement])=>value.replace(pattern,replacement),original):original;
    }
  }
  function setDrawer(open,{restoreFocus=true}={}){
    const shell=byId('v1-provider-shell'),toggle=byId('v1-provider-toggle'),scrim=byId('v1-provider-scrim');
    if(!shell||!toggle)return;shell.classList.toggle('is-open',open);shell.setAttribute('aria-hidden',String(!open));
    toggle.setAttribute('aria-expanded',String(open));if(scrim){scrim.hidden=!open;scrim.setAttribute('aria-hidden',String(!open));}
    document.body.classList.toggle('v1-provider-drawer-open',open);
    if(open)queueMicrotask(()=>byId('v1-provider-close')?.focus());
    else if(restoreFocus)queueMicrotask(()=>toggle.focus());
  }
  function wireDrawer(){
    byId('v1-provider-toggle')?.addEventListener('click',()=>setDrawer(!byId('v1-provider-shell')?.classList.contains('is-open')));
    byId('v1-provider-close')?.addEventListener('click',()=>setDrawer(false));
    byId('v1-provider-scrim')?.addEventListener('click',()=>setDrawer(false));
    byId('v1-project-provider-select').onchange=event=>{if(event.target.value)location.assign(`/?provider=PROJECT_DATA&project_id=${encodeURIComponent(event.target.value)}`);};
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
  function installNativeControls(){
    const workflow=document.querySelector('.v1-provider-workflow'),anchor=byId('sideRunOptimizeRow');
    if(!workflow||!anchor)return;workflow.classList.add('v1-native-project-workflow');anchor.insertAdjacentElement('afterend',workflow);
  }
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
    applyProviderTerminology(true);
  }
  function ensureProjectTabs(){
    const tabs=byId('analysisTables');
    if(tabs&&!tabs.querySelector('[data-tab="drought"]')){
      const button=document.createElement('button');button.className='tab';button.dataset.tab='drought';button.textContent='Kuraklık göstergeleri';
      tabs.querySelector('[data-tab="benchmark"]')?.insertAdjacentElement('beforebegin',button);
      button.addEventListener('click',()=>{document.querySelectorAll('#analysisTables .tab').forEach(node=>node.classList.remove('active'));document.querySelectorAll('.tab-panels>.tab-panel').forEach(node=>node.classList.remove('active'));button.classList.add('active');byId('tab-drought')?.classList.add('active');});
    }
    if(tabs&&!tabs.dataset.projectParityBound){
      tabs.dataset.projectParityBound='1';
      tabs.addEventListener('click',event=>{
        if(!event.target.closest('.tab'))return;
        setTimeout(()=>{neutralizeReferenceSurface();renderProjectModules(context?.run);},50);
      });
    }
    const drawing=byId('tab-drawing');
    if(drawing&&!byId('v1-project-drawing-state'))drawing.querySelector('.drawing-tab-shell')?.insertAdjacentHTML('afterbegin','<div id="v1-project-drawing-state" class="v1-provider-explanation">PROJECT DATA geometrileri yüklenen proje dosyalarından gelir. Bu çalışma alanı geometriyi değiştirmeden gösterir; ekleme veya düzeltme için Projeler → Veri Yönetimi alanını kullanın.</div>');
    for(const id of ['btnExportWaterCsv','btnExportScenarioCsv','btnExportParcelsCsv','btnExportAllParcelCompareCsv']){const button=byId(id);if(button){button.disabled=true;button.title='PROJECT DATA dışa aktarımı bu stored-run sözleşmesinde sağlanmadı.';}}
  }
  function renderProjectModules(run=context?.run){
    if(!context)return;ensureProjectTabs();
    const current=context.current_summary||{},geo=context.geographic_summary||{rows:[]},result=run?.result||{};
    setText('bWaterCurrent',metric(current.water_m3));setText('bProfitCurrent',metric(current.profit_tl));setText('bEffCurrent',metric(current.efficiency_tl_per_m3,4));
    const districtRows=(geo.rows||[]).map(row=>[row.name,row.unit_count,metric(row.area_da),metric(row.current_water_m3),metric(row.current_profit_tl)]);
    const district=byId('districtSummaryTable');if(district)district.innerHTML=districtRows.length?table(['Kapsam','Analiz birimi','Alan (da)','Mevcut su (m³)','Mevcut net kâr (TL)'],districtRows):'<p class="v1-missing-state">SAĞLANMADI / NOT PROVIDED — proje coğrafi özeti üretilemedi.</p>';
    if(byId('districtKpiGrid'))byId('districtKpiGrid').innerHTML=`<div class="v1-result-card"><span>Kapsam</span><strong>${html((geo.rows||[]).length)}</strong></div><div class="v1-result-card"><span>Analiz birimi</span><strong>${html(context.unit_count)}</strong></div><div class="v1-result-card"><span>Toplam alan</span><strong>${html(number(context.total_area_da))} da</strong></div><div class="v1-result-card"><span>Kaynak</span><strong>PROJECT DATA</strong></div>`;
    setText('districtNarrative',`${context.project.province_or_region||'Proje kapsamı'} · backend karar bağlamından ${context.unit_count} analiz birimi. Akkaya özeti kullanılmadı.`);
    const districtCharts=[
      ['districtAreaChart',[{label:'Alan (da)',key:'area_da'}]],
      ['districtIrrigChart',[{label:'Mevcut su (m³)',key:'current_water_m3'},{label:'Önerilen su (m³)',key:'optimized_water_m3'}]],
      ['provinceShareChart',[{label:'Mevcut net kâr (TL)',key:'current_profit_tl'},{label:'Önerilen net kâr (TL)',key:'optimized_profit_tl'}]],
    ];
    for(const [id,series] of districtCharts){const chart=chartById(id);if(!chart)continue;chart.data.labels=(geo.rows||[]).map(row=>row.name);chart.data.datasets=series.map((item,index)=>({label:item.label,data:(geo.rows||[]).map(row=>row[item.key]),backgroundColor:index?'rgba(56,103,183,.55)':'rgba(23,107,87,.55)',borderColor:index?'#3867b7':'#176b57'}));chart.update();}
    const annual=result.annual_budget_validation||{};
    const waterBody=document.querySelector('#tblOfficialWater tbody');if(waterBody)waterBody.innerHTML=[['Proje planlama yılı',context.project.planning_year,'yıl'],['Proje su bütçesi',context.project.annual_water_budget,'m³'],['Mevcut desen suyu',current.water_m3,'m³'],['Optimize otoritatif su',result.authoritative_water_m3,'m³'],['Yıllık bütçe durumu',annual.status,'durum']].map(row=>nativeRow([row[0],metric(row[1],2,String(row[1]??'SAĞLANMADI / NOT PROVIDED')),row[2]])).join('');
    setText('officialWaterNote','PROJECT DATA · backend-authoritative proje ve saklanmış run değerleri');
    const shares=result.crop_shares&&typeof result.crop_shares==='object'?Object.entries(result.crop_shares):[];
    const areas=new Map((result.top_crops||[]).map(row=>[row.crop,row.area_da]));
    const scenarioBody=document.querySelector('#tblOfficialScenario tbody');if(scenarioBody)scenarioBody.innerHTML=shares.length?shares.map(([crop])=>nativeRow([crop,metric(areas.get(crop)),'SAĞLANMADI / NOT PROVIDED','SAĞLANMADI / NOT PROVIDED','SAĞLANMADI / NOT PROVIDED'])).join(''):nativeRow(['HESAPLANMADI / NOT CALCULATED','SAĞLANMADI / NOT PROVIDED','SAĞLANMADI / NOT PROVIDED','SAĞLANMADI / NOT PROVIDED','SAĞLANMADI / NOT PROVIDED']);
    setText('officialScenarioNote',run?`Immutable run ${run.id} · backend ürün bazında su/kâr dağılımı sağlamadığı için bu hücreler açıkça boş bırakıldı.`:'Saklanmış proje çalışması seçilmedi.');
    const parcelBody=document.querySelector('#tblOfficialParcels tbody');if(parcelBody)parcelBody.innerHTML=context.units.map(unit=>{const value=unit.result||{};return nativeRow([unit.analysis_unit_id,metric(unit.area_da),metric(value.authoritative_unit_water_m3),metric(value.unit_profit_tl),metric(value.efficiency_tl_per_m3,4)]);}).join('');
    const compareBody=document.querySelector('#tblOfficialAllParcelCompare tbody');if(compareBody)compareBody.innerHTML=context.units.map(unit=>{const value=unit.result||{},selected=(value.selected_crops||[]).map(item=>item.crop).join(' + ');return nativeRow([unit.analysis_unit_id,metric(unit.area_da),unit.current_crop||'SAĞLANMADI / NOT PROVIDED',metric(unit.current_water_m3),metric(unit.current_profit_tl),selected||'HESAPLANMADI / NOT CALCULATED',metric(value.authoritative_unit_water_m3),metric(value.unit_profit_tl),value.authoritative_unit_water_m3==null||unit.current_water_m3==null?'SAĞLANMADI / NOT PROVIDED':metric(value.authoritative_unit_water_m3-unit.current_water_m3),value.unit_profit_tl==null||unit.current_profit_tl==null?'SAĞLANMADI / NOT PROVIDED':metric(value.unit_profit_tl-unit.current_profit_tl),run?'Immutable backend sonucu':'Çalışma seçilmedi']);}).join('');
    if(byId('officialSummary'))byId('officialSummary').innerHTML='<p class="v1-provider-explanation">Bu özet yalnız yüklenmiş PROJECT DATA, doğrulanmış revision ve seçili immutable run bağlamını kullanır. Paket resmî yayımlanmış tablo içermediği için ayrı bir resmî otorite iddiası yapılmaz.</p>';
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
    const cards=byId('productCards');if(cards)cards.innerHTML=(result.selected_crops||[]).length?(result.selected_crops||[]).map((row,index)=>`<article class="product-card"><strong>${html(row.crop)}</strong><span>${html(row.season||'')}</span>${index===0?`<small>${metric(result.authoritative_unit_water_m3)} m³ · ${metric(result.unit_profit_tl)} TL</small>`:''}</article>`).join(''):'<div class="small muted">Bu birim için henüz saklanmış optimizasyon deseni yok.</div>';
    renderNativeUnit(unit);
    document.querySelectorAll('[data-v1-provider-unit]').forEach(node=>node.classList.toggle('v1-project-unit-active',node.dataset.v1ProviderUnit===selectedUnit));
    if(!unit.geometry&&!(unit.latitude!==null&&unit.latitude!==undefined&&unit.longitude!==null&&unit.longitude!==undefined)){
      setText('v1-geometry-status','Bu analiz birimi için geometri sağlanmadı.');
    }else setText('v1-geometry-status',geometryMessage());
    focusGeometry(unit);
  }
  function nativeRow(values){return `<tr>${values.map(value=>`<td>${html(value??'SAĞLANMADI / NOT PROVIDED')}</td>`).join('')}</tr>`;}
  function ensureNativeResultSurface(){
    let surface=byId('v1-native-project-results');if(surface)return surface;
    surface=document.createElement('section');surface.id='v1-native-project-results';surface.className='v1-native-results';
    surface.setAttribute('aria-label','Saklanmış proje analiz sonucu');
    surface.innerHTML='<div id="v1-native-run-summary"></div><div id="v1-native-water-accounting"></div><div id="v1-native-annual-budget"></div><div id="v1-native-monthly"></div><div id="v1-native-warnings"></div><div id="v1-native-crops"></div><div id="v1-native-unit-result"></div><details id="v1-native-provenance"><summary>Kaynak &amp; Provenance</summary><pre></pre></details>';
    const top=document.querySelector('.right-top');
    if(top)top.insertAdjacentElement('afterend',surface);
    else byId('basinSummaryBlock')?.insertAdjacentElement('afterend',surface);
    return surface;
  }
  function retireLegacyResultSink(){
    const sink=byId('v1-project-result');if(!sink)return;
    sink.replaceChildren();
    sink.hidden=true;sink.setAttribute('aria-hidden','true');
  }
  function renderNativeUnit(unit){
    const result=unit.result||{},selected=result.selected_crops||[];
    const currentBody=document.querySelector('#tblCurrent tbody'),recommendedBody=document.querySelector('#tblRecommended tbody');
    if(currentBody)currentBody.innerHTML=nativeRow([unit.current_crop||'SAĞLANMADI / NOT PROVIDED','SAĞLANMADI / NOT PROVIDED','SAĞLANMADI / NOT PROVIDED',metric(unit.area_da),metric(unit.current_water_m3_da),metric(unit.current_water_m3),metric(unit.current_profit_tl_da),metric(unit.current_profit_tl)]);
    if(recommendedBody)recommendedBody.innerHTML=selected.length?selected.map((crop,index)=>nativeRow([crop.crop||'SAĞLANMADI / NOT PROVIDED',crop.season||'SAĞLANMADI / NOT PROVIDED','SAĞLANMADI / NOT PROVIDED',index===0?metric(result.area_da??unit.area_da):'UYGULANAMAZ / NOT APPLICABLE','SAĞLANMADI / NOT PROVIDED',index===0?metric(result.authoritative_unit_water_m3):'UYGULANAMAZ / NOT APPLICABLE','SAĞLANMADI / NOT PROVIDED',index===0?metric(result.unit_profit_tl):'UYGULANAMAZ / NOT APPLICABLE'])).join(''):nativeRow(['HESAPLANMADI / NOT CALCULATED','UYGULANAMAZ / NOT APPLICABLE','SAĞLANMADI / NOT PROVIDED','SAĞLANMADI / NOT PROVIDED','SAĞLANMADI / NOT PROVIDED','HESAPLANMADI / NOT CALCULATED','SAĞLANMADI / NOT PROVIDED','HESAPLANMADI / NOT CALCULATED']);
    setText('tblCurrentFooter',`${unit.analysis_unit_id} · ${metric(unit.area_da)} da · PROJECT DATA`);
    setText('tblRecommendedFooter',context.run?`${context.run.scenario} · ${context.run.algorithm} · ${context.run.configuration?.objective||'SAĞLANMADI / NOT PROVIDED'}`:'Henüz saklanmış proje çalışması yok.');
    setText('explainBox',context.run?`Karar durumu: ${result.status||((context.run.result||{}).feasible===true?'UYGULANABİLİR':(context.run.result||{}).feasible===false?'KISIT İHLALİ / DIAGNOSTIC':'SAĞLANMADI / NOT PROVIDED')} · ${unit.current_crop||'Mevcut ürün sağlanmadı'} → ${(selected||[]).map(value=>value.crop).join(' + ')||'öneri üretilmedi'}. Bu görünüm immutable ${context.run.id} backend sonucudur; tarayıcıda bilimsel yeniden hesaplama yapılmadı.`:'Öneri için mevcut V1 Optimizasyonu Çalıştır düğmesini kullanın.');
    setText('rotationBox',context.run?.scenario==='S2'?(selected.length?selected.map(value=>`${value.season||'SEZON'}: ${value.crop}`).join(' · '):'HESAPLANMADI / NOT CALCULATED'):'UYGULANAMAZ / NOT APPLICABLE — S1 tek sezon bağlamı.');
    setText('irrigationCompareBox','SAĞLANMADI / NOT PROVIDED — proje sonucu sulama yöntemi karşılaştırması sağlamadı.');
    setText('businessMetricsBox',context.run?`Backend birim net kârı: ${metric(result.unit_profit_tl)} TL · Otoritatif birim suyu: ${metric(result.authoritative_unit_water_m3)} m³`:'HESAPLANMADI / NOT CALCULATED — saklanmış proje sonucu yok.');
    setText('irrigPlanBox','SAĞLANMADI / NOT PROVIDED — backend birim düzeyinde sulama takvimi sağlamadı.');
    const target=byId('v1-native-unit-result');if(target)target.innerHTML=`<h4>Seçili analiz birimi sonucu</h4>${context.run?table(['Birim','Alan (da)','Mevcut ürün','Seçilen desen','Otoritatif su (m³)','Net kâr (TL)','Karar durumu','Uyarılar','Geometri / kaynak'],[[unit.analysis_unit_id,metric(result.area_da??unit.area_da),unit.current_crop||'SAĞLANMADI / NOT PROVIDED',selected.map(value=>value.crop).join(' + ')||'HESAPLANMADI / NOT CALCULATED',metric(result.authoritative_unit_water_m3),metric(result.unit_profit_tl),result.status||((context.run.result||{}).feasible===true?'UYGULANABİLİR':'DIAGNOSTIC / KISIT İHLALİ'),(result.warnings||[]).join(' · ')||'Backend uyarısı yok',unit.geometry?'PROJECT DATA · GEOMETRİ MEVCUT':(unit.latitude!=null&&unit.longitude!=null?'PROJECT DATA · KOORDİNAT MEVCUT':'SAĞLANMADI / NOT PROVIDED')]]):'<p class="v1-empty-state">Henüz saklanmış proje çalışması yok.</p>'}`;
  }
  function resetMap(){
    const root=byId('map');if(!root||!window.L)return null;
    try{providerMap=(typeof map!=='undefined'&&map)?map:null;}catch(_error){providerMap=null;}
    if(!providerMap){
      try{
        providerMap=L.map(root,{zoomControl:true}).setView([37.888,34.645],12);
        try{
          if(L.esri&&typeof L.esri.basemapLayer==='function')L.esri.basemapLayer('Imagery').addTo(providerMap);
          else L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:20,attribution:'&copy; OpenStreetMap'}).addTo(providerMap);
        }catch(_error){}
        try{map=providerMap;}catch(_error){window.map=providerMap;}
      }catch(_error){providerMap=null;}
    }
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
        if(unit.geometry&&['Polygon','MultiPolygon'].includes(unit.geometry.type))layer=L.geoJSON({type:'Feature',properties:{id:unit.analysis_unit_id},geometry:unit.geometry},{style:{color:'#176b57',weight:2,opacity:.95,fillColor:'#63b39d',fillOpacity:.24}});
        else if(unit.latitude!==null&&unit.latitude!==undefined&&unit.longitude!==null&&unit.longitude!==undefined)layer=L.marker([Number(unit.latitude),Number(unit.longitude)]);
        if(layer){
          const result=unit.result||{},recommended=(result.selected_crops||[]).map(value=>value.crop).join(' + ')||'Henüz saklanmış öneri yok';
          layer.bindPopup?.(`<strong>${html(unit.analysis_unit_id)}</strong><br>${html(unit.settlement||context.project.province_or_region||'Proje kapsamı')}<br>Alan: ${html(metric(unit.area_da))} da<br>Mevcut ürün: ${html(unit.current_crop||'SAĞLANMADI / NOT PROVIDED')}<br>Mevcut su: ${html(metric(unit.current_water_m3))} m³<br>Mevcut net kâr: ${html(metric(unit.current_profit_tl))} TL<br>Önerilen: ${html(recommended)}<br>Optimize su: ${html(metric(result.authoritative_unit_water_m3))} m³<br>Optimize net kâr: ${html(metric(result.unit_profit_tl))} TL<br>Otorite: ${html(context.authority)}`,{className:'parcel-popup'});
          layer.bindTooltip?.(`<span class="parcel-badge-wrap">${html(unit.analysis_unit_id)}</span>`,{permanent:true,direction:'center',className:'v1-project-map-label'});
          layer.addTo(providerLayers||current);layer.on?.('click',()=>{selectedUnit=unit.analysis_unit_id;byId('parcelSelect').value=selectedUnit;renderUnit();history.pushState(null,'',canonicalUrl({unitId:selectedUnit}));});layer.__providerUnit=unit.analysis_unit_id;layers.push(layer);
        }
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
    return [...keys].sort().map(key=>{const states=[];if((supply.violating_months||[]).includes(key))states.push('ARZ AŞILDI');if((delivery.violating_months||[]).includes(key))states.push('KAPASİTE AŞILDI');return [key,demand[key],available[key],capacity[key],states.join(' + ')||'PASS'];});
  }
  function violatingMonths(result){
    return [...new Set([...(result.monthly_supply_validation?.violating_months||[]),...(result.monthly_delivery_validation?.violating_months||[])])].sort();
  }
  function table(headers,rows){return `<div class="v1-provider-table-wrap"><table class="v1-provider-table"><thead><tr>${headers.map(h=>`<th>${html(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map(value=>`<td>${html(value??'SAĞLANMADI')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;}
  function chartById(id){
    const canvas=byId(id);if(!canvas||!window.Chart)return null;
    try{return Chart.getChart?.(canvas)||null;}catch(_error){return null;}
  }
  function renderNativeCharts(run){
    const result=run.result||{};
    const water=chartById('waterChart');if(water){
      water.data.labels=['Optimizer planı','Otoritatif','Planlama yılı','Tam sezon'];
      water.data.datasets[0].label='Backend su değerleri (m³)';
      water.data.datasets[0].data=[result.optimizer_water_m3,result.authoritative_water_m3,result.planning_year_profile_water_m3,result.verified_profile_water_m3];
      water.canvas.closest('.small-chart-card')?.querySelector('.card-subtitle')?.replaceChildren('PROJECT DATA · Su muhasebesi karşılaştırması');water.update();
    }
    const profit=chartById('profitChart');if(profit){
      profit.data.labels=['Optimize net kâr'];profit.data.datasets[0].label='Backend net kâr (TL)';profit.data.datasets[0].data=[result.total_profit_tl];
      profit.canvas.closest('.small-chart-card')?.querySelector('.card-subtitle')?.replaceChildren('PROJECT DATA · Optimize net kâr');profit.update();
    }
    const monthly=monthlyRows(result),box=byId('deliveryBox');if(box){
      box.innerHTML=`<div class="v1-native-monthly-chart-note">Backend aylık talep, kullanılabilir arz ve teslim kapasitesi</div><div class="v1-native-monthly-chart"><canvas id="v1ProjectMonthlyChart" aria-label="Proje aylık su doğrulama grafiği"></canvas></div>`;
      providerMonthlyChart?.destroy?.();const canvas=byId('v1ProjectMonthlyChart');if(canvas&&window.Chart&&monthly.length)providerMonthlyChart=new Chart(canvas.getContext('2d'),{type:'line',data:{labels:monthly.map(row=>row[0]),datasets:[{label:'Talep (m³)',data:monthly.map(row=>row[1]),borderColor:'#c74343',backgroundColor:'rgba(199,67,67,.12)',tension:.2},{label:'Kullanılabilir arz (m³)',data:monthly.map(row=>row[2]),borderColor:'#176b57',backgroundColor:'rgba(23,107,87,.12)',tension:.2},{label:'Teslim kapasitesi (m³)',data:monthly.map(row=>row[3]),borderColor:'#3867b7',backgroundColor:'rgba(56,103,183,.12)',tension:.2}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'bottom'}},scales:{y:{beginAtZero:true}}}});
    }
  }
  function renderProjectBenchmark(run){
    const normalize=item=>({id:item.id,algorithm:item.algorithm,objective:item.objective||item.configuration?.objective,scenario:item.scenario,seed:item.seed,water:item.water??item.result?.authoritative_water_m3,profit:item.profit??item.result?.total_profit_tl,efficiency:item.efficiency??item.result?.efficiency_tl_per_m3,feasible:item.feasible??item.result?.feasible});
    const rows=(context.history?.items||[]).map(normalize);if(!rows.some(item=>item.id===run.id))rows.unshift(normalize(run));
    const target=byId('benchmarkResults');if(target)target.innerHTML=table(['Run','Algoritma','Hedef','Senaryo','Seed','Su (m³)','Net kâr (TL)','TL/m³','Feasibility'],rows.map(item=>[item.id,item.algorithm,item.objective,item.scenario,item.seed,metric(item.water),metric(item.profit),metric(item.efficiency,4),item.feasible===true?'PASS':item.feasible===false?'FAIL':'SAĞLANMADI / NOT PROVIDED']));
    const distinct=new Set(rows.map(item=>`${item.algorithm}:${item.objective}`));setText('benchmarkStatus',`PROJECT DATA · ${rows.length} immutable stored run`);
    setText('benchmarkPatterns',distinct.size>1?`${distinct.size} algoritma/hedef kombinasyonu proje run geçmişinden karşılaştırılıyor.`:'Algoritma karşılaştırması için birden fazla PROJECT_DATA stored run gerekli; Akkaya benchmark değeri gösterilmedi.');
    const specs=[['benchmarkWaterChart','water','Su (m³)'],['benchmarkProfitChart','profit','Net kâr (TL)'],['benchmarkEffChart','efficiency','TL/m³']];
    for(const [id,key,label] of specs){const chart=chartById(id);if(!chart)continue;chart.data.labels=distinct.size>1?rows.map(item=>`${item.algorithm} · ${item.objective}`):[];chart.data.datasets=[{label,data:distinct.size>1?rows.map(item=>item[key]):[],borderColor:'#176b57',backgroundColor:'rgba(23,107,87,.28)'}];chart.update();}
  }
  function renderRun(run){
    if(!run)return;const result=run.result||{},summary=run.summary||{};context.run=run;
    const resultUnits=result.presentation_units||[];
    retireLegacyResultSink();
    context.units=context.units.map(unit=>({...unit,result:resultUnits.find(row=>row.analysis_unit_id===unit.analysis_unit_id)||unit.result}));
    setText('bWaterScenario',metric(result.authoritative_water_m3));setText('bProfitScenario',metric(result.total_profit_tl));setText('bEffScenario',metric(result.efficiency_tl_per_m3,4));setText('metricsTitle',`${context.project.name} · Saklanmış analiz sonucu`);
    const objectiveLabel={water_saving:'Su tasarrufu',max_profit:'Kâr',water_efficiency:'Su etkin kullanım'}[run.configuration?.objective]||run.configuration?.objective||'SAĞLANMADI';setText('activeObjectiveBadge',`Aktif hedef: ${objectiveLabel}`);
    neutralizeReferenceSurface();
    renderNativeRun(run);
    renderProjectModules(run);
    renderMap();
    renderUnit();
  }
  function renderNativeRun(run){
    const result=run.result||{},summary=run.summary||{},warnings=[...(run.warnings||[]),...(result.warnings||[])].filter((value,index,all)=>value&&all.indexOf(value)===index);
    const annual=result.annual_budget_validation||{},monthly=monthlyRows(result),shares=result.crop_shares&&typeof result.crop_shares==='object'?Object.entries(result.crop_shares):[];
    const reconciliation=result.water_reconciliation||{},diagnostic=result.feasible===false||result.diagnostic===true;
    const warningText=warnings.length?warnings.join(' · '):'Backend uyarısı yok.';
    const annualText=annual&&Object.keys(annual).length?`${annual.status||'SAĞLANMADI'} · talep ${metric(annual.demand_m3)} m³ · bütçe ${metric(annual.usable_supply_m3??annual.available_budget_m3)} m³`:'SAĞLANMADI / NOT PROVIDED';
    setText('algoStatus',`Tamamlandı · ${run.algorithm} · ${run.configuration?.objective||'hedef sağlanmadı'}`);
    const monthlyText=monthly.length?`Aylık doğrulama: ${monthly.length} dönem · ihlal: ${violatingMonths(result).join(', ')||'yok'}`:'Aylık doğrulama SAĞLANMADI / NOT PROVIDED';
    setText('deliveryBox',`Yıllık bütçe: ${annualText} · ${monthlyText} · Uyarılar: ${warningText}`);
    setText('globalBudgetBadge',`Toplam planlama su bütçesi: ${metric(annual.usable_supply_m3??annual.available_budget_m3)} m³`);
    setText('globalBudgetStatus',`bütçe durumu: ${annual.status||'SAĞLANMADI / NOT PROVIDED'}`);
    renderProjectBenchmark(run);
    setText('objectiveCompareMatrix',`Aktif stored run: ${run.algorithm} × ${run.configuration?.objective||'SAĞLANMADI'} · ${run.scenario}. Diğer kombinasyonlar yalnız çalıştırılıp saklandığında karşılaştırılır.`);
    const note=byId('basinSummaryNote');if(note)note.textContent=`${context.project.name} · ${context.unit_count} analiz birimi · revision ${context.project_revision} · optimizer su ${metric(result.optimizer_water_m3)} m³ · otoritatif su ${metric(result.authoritative_water_m3)} m³ · planlama yılı ${metric(result.planning_year_profile_water_m3)} m³ · tam sezon ${metric(result.verified_profile_water_m3)} m³ · fark ${metric(result.water_accounting_difference_m3??result.water_reconciliation?.difference_m3)} m³ · net kâr ${metric(result.total_profit_tl)} TL · su verimliliği ${metric(result.efficiency_tl_per_m3,4)} TL/m³ · feasibility ${result.feasible===true?'PASS':result.feasible===false?'FAIL':'SAĞLANMADI / NOT PROVIDED'}`;
    ensureNativeResultSurface();
    const primarySummary=[['Proje',context.project.name],['Senaryo',run.scenario],['Algoritma',run.algorithm],['Hedef',run.configuration?.objective],['Toplam net kâr (TL)',metric(result.total_profit_tl)],['TL/m³',metric(result.efficiency_tl_per_m3,4)],['Feasibility',result.feasible===true?'PASS':result.feasible===false?'FAIL':'SAĞLANMADI / NOT PROVIDED']];
    const technicalSummary=[['Run durumu',run.status],['Classification',result.classification],['Planlama yılı',context.project.planning_year],['Run ID',run.id],['Seed',run.seed],['Otorite',run.result_authority_label],['Aktif alan (da)',metric(summary.active_area_da)],['Score',metric(summary.score,5)]];
    const summaryCards=rows=>rows.map(([label,value])=>`<div class="v1-result-card"><span>${html(label)}</span><strong>${html(value)}</strong></div>`).join('');
    byId('v1-native-run-summary').innerHTML=`<h3>${diagnostic?'DIAGNOSTIC / UYGULANABİLİR ÖNERİ DEĞİL':'Saklanmış proje sonucu'}</h3><div class="v1-result-grid">${summaryCards(primarySummary)}</div><details class="v1-result-technical"><summary>Teknik çalışma ayrıntıları</summary><div class="v1-result-grid">${summaryCards(technicalSummary)}</div></details>`;
    byId('v1-native-water-accounting').innerHTML=`<h4>Su muhasebesi ve uzlaştırma</h4><div class="v1-result-grid">${[['Optimizer su kullanımı (m³)',metric(result.optimizer_water_m3)],['Doğrulanmış / otoritatif su (m³)',metric(result.authoritative_water_m3)],['Planlama yılı suyu (m³)',metric(result.planning_year_profile_water_m3)],['Tam sezon suyu (m³)',metric(result.verified_profile_water_m3)],['Fark (m³)',metric(result.water_accounting_difference_m3??reconciliation.difference_m3)],['Fark (%)',metric(result.water_accounting_difference_pct??reconciliation.difference_pct,4)]].map(([label,value])=>`<div class="v1-result-card"><span>${html(label)}</span><strong>${html(value)}</strong></div>`).join('')}</div><p class="v1-provider-explanation">Optimizer su kullanımı motorun plan çıktısıdır. Doğrulanmış / otoritatif su, backend'in saklanmış çalışma sonrası su muhasebesidir; dönem ve doğrulama kapsamları farklı olduğunda değerler farklı olabilir.</p>`;
    byId('v1-native-annual-budget').innerHTML=`<h4>Yıllık su bütçesi doğrulaması</h4>${Object.keys(annual).length?table(['Talep (m³)','Kullanılabilir bütçe (m³)','Durum','Backend açıklaması'],[[metric(annual.demand_m3),metric(annual.usable_supply_m3??annual.available_budget_m3),annual.status||'SAĞLANMADI / NOT PROVIDED',annual.reason||annual.message||'Backend ek açıklama sağlamadı.']]):'<p class="v1-missing-state">SAĞLANMADI / NOT PROVIDED — backend yıllık bütçe doğrulaması üretmedi.</p>'}`;
    byId('v1-native-monthly').innerHTML=`<h4>Aylık su doğrulaması</h4><p class="v1-provider-explanation">İhlal ayları (tekilleştirilmiş): ${html(violatingMonths(result).join(', ')||'yok')}</p>${monthly.length?table(['Ay','Talep (m³)','Kullanılabilir arz (m³)','Teslim kapasitesi (m³)','Durum'],monthly.map(row=>row.map((value,index)=>index>0&&index<4?metric(value):value))):'<p class="v1-missing-state">SAĞLANMADI / NOT PROVIDED — backend aylık talep, arz veya teslim serisi üretmedi.</p>'}`;
    byId('v1-native-warnings').innerHTML=`<h4>Analiz uyarıları</h4>${warnings.length?`<ul class="v1-warning-list">${warnings.map(value=>`<li>${html(value)}</li>`).join('')}</ul>`:'<p class="v1-empty-state">Backend bu çalışma için uyarı bildirmedi.</p>'}`;
    const areas=new Map((result.top_crops||[]).map(row=>[row.crop,row.area_da]));byId('v1-native-crops').innerHTML=`<h4>Ürün kompozisyonu ve yoğunlaşma</h4>${shares.length?table(['Ürün','Alan (da)','Pay'],shares.map(([crop,share])=>[crop,metric(areas.get(crop)),`${number(Number(share)*100)}%`])):'<p class="v1-missing-state">SAĞLANMADI / NOT PROVIDED — kanonik crop_shares üretilmedi.</p>'}<p>HHI: <strong>${metric(result.hhi??result.HHI,4)}</strong></p>`;
    const provenance={project_id:run.project_id,project_revision:context.project_revision,run_id:run.id,status:run.status,started_at:run.started_at,completed_at:run.completed_at,execution_profile:run.execution_profile,classification:result.classification,synthetic_not_official:context.synthetic,scenario:run.scenario,algorithm:run.algorithm,objective:run.configuration?.objective,seed:run.seed,selection_hash:run.provenance?.selection_hash||result.result_provenance?.selection_hash,engine_commit:run.provenance?.engine_commit||result.result_provenance?.engine_commit,result_authority_label:run.result_authority_label,input_datasets:run.provenance?.input_snapshot?.input_datasets,provenance:run.provenance,presentation_context:run.presentation_context};
    byId('v1-native-provenance').querySelector('pre').textContent=JSON.stringify(provenance,null,2);
    setText('runMetaBox',`${context.project.name} · revision ${context.project_revision} · ${run.algorithm} · ${run.configuration?.objective} · ${run.scenario} · seed ${run.seed} · run ${run.id}`);byId('runMetaBox').style.display='block';
    setText('riskSeparationBox',`Backend feasibility: ${result.feasible===true?'PASS':'FAIL'} · yıllık bütçe: ${annual.status||'SAĞLANMADI'} · aylık arz: ${result.monthly_supply_validation?.status||'SAĞLANMADI'} · aylık teslim: ${result.monthly_delivery_validation?.status||'SAĞLANMADI'}`);byId('riskSeparationBox').style.display='block';
    setText('decisionRationale',`Karar açıklaması: ${run.algorithm}, ${run.configuration?.objective} hedefi altında project candidate matrix kullanılarak çalıştırıldı. Sonuç ${result.feasible===true?'uygulanabilir':'aylık/teslim kısıtları nedeniyle diagnostic'} durumdadır; Akkaya fallback kullanılmadı.`);byId('decisionRationale').style.display='block';
    const current=context.current_summary||{};
    setText('bWaterDiff',current.water_m3==null?'Mevcut proje suyu sağlanmadı':`Fark: ${metric(result.authoritative_water_m3-current.water_m3)} m³`);setText('bProfitDiff',current.profit_tl==null?'Mevcut proje kârı sağlanmadı':`Fark: ${metric(result.total_profit_tl-current.profit_tl)} TL`);setText('bEffDiff',current.efficiency_tl_per_m3==null?'Mevcut proje etkinliği sağlanmadı':`Fark: ${metric(result.efficiency_tl_per_m3-current.efficiency_tl_per_m3,4)} TL/m³`);
    const active=context.units.find(unit=>unit.analysis_unit_id===selectedUnit),activeResult=active?.result||{};
    setText('mWaterDiff',active?.current_water_m3==null?'Mevcut birim suyu sağlanmadı':`Fark: ${metric(activeResult.authoritative_unit_water_m3-active.current_water_m3)} m³`);setText('mProfitDiff',active?.current_profit_tl==null?'Mevcut birim kârı sağlanmadı':`Fark: ${metric(activeResult.unit_profit_tl-active.current_profit_tl)} TL`);setText('mEffDiff',active?.current_efficiency_tl_per_m3==null?'Mevcut birim etkinliği sağlanmadı':`Fark: ${metric(activeResult.efficiency_tl_per_m3-active.current_efficiency_tl_per_m3,4)} TL/m³`);
    renderNativeCharts(run);
  }
  async function createPreview(){
    preview=null;const state=byId('v1-provider-preview-state');state.textContent='Backend önizlemesi hazırlanıyor…';setText('algoStatus','Önizleme hazırlanıyor…');
    const request=payload();preview=await api(`/projects/${encodeURIComponent(context.project.id)}/analysis-preview`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});
    if(!preview.ready){state.className='v1-state-blocked';state.textContent=`BLOCKED · ${(preview.blocking_reasons||[]).join(' · ')}`;return null;}
    state.className='v1-state-ready';state.textContent=`PINNED · revision ${preview.preview_revision} · ${preview.selection_hash}`;setText('algoStatus',`Önizleme sabitlendi · revision ${preview.preview_revision}`);return {request,preview};
  }
  async function runProject(){
    if(document.querySelector('input[name="scenario"]:checked')?.value==='mevcut'){
      preview=null;const state=byId('v1-provider-preview-state');state.className='v1-empty-state';state.textContent='Mevcut görünüm yalnız proje girdilerini gösterir; optimizasyon çalıştırmaz.';setDrawer(true);return;
    }
    const buttons=['runOptBtn','runOptBtnSecondary'].map(byId).filter(Boolean);buttons.forEach(button=>button.disabled=true);setText('algoStatus','Backend optimizasyonu çalışıyor…');
    try{
      const pinned=preview?.ready?{request:payload(),preview}:await createPreview();if(!pinned)return;
      const body={...pinned.request,preview_token:pinned.preview.preview_token,preview_revision:pinned.preview.preview_revision,selection_hash:pinned.preview.selection_hash};
      const run=await api(`/projects/${encodeURIComponent(context.project.id)}/analyses`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      const url=canonicalUrl({runId:run.id,unitId:selectedUnit});history.pushState(null,'',url);
      context=await api(`/projects/${encodeURIComponent(context.project.id)}/decision-context?run_id=${encodeURIComponent(run.id)}&scenario=${encodeURIComponent(body.scenario)}`);renderRun(context.run);renderHistory();
    }finally{buttons.forEach(button=>button.disabled=false);}
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
  }
  async function loadProjectList(){
    const data=await api('/projects');const select=byId('v1-project-provider-select');for(const project of data.projects){const option=document.createElement('option');option.value=project.id;option.textContent=`${project.name} · ${project.planning_year}`;select.append(option);}if(context?.project?.id)select.value=context.project.id;
  }
  async function initProject(){
    document.body.classList.add('project-provider-mode');
    applyProviderTerminology(true);retireLegacyResultSink();ensureNativeResultSurface();
    const shell=byId('v1-provider-shell');shell.dataset.provider='PROJECT_DATA';
    if(providers.length!==1||projects.length!==1||runs.length>1||units.length>1)throw new Error('Tek bir provider, project_id, run_id ve unit parametresi gerekir.');
    const projectId=canonicalId(projects[0]);if(!projectId)throw new Error('project_id biçimi geçersiz.');
    if(requestedProvider!=='PROJECT_DATA')throw new Error('Bilinmeyen provider.');
    selectedUnit=units[0]||null;
    const suffix=`?${runs[0]?`run_id=${encodeURIComponent(runs[0])}&`:''}scenario=${encodeURIComponent((byId('seasonSourceSel')?.value||'s1').toUpperCase())}`;
    context=await api(`/projects/${encodeURIComponent(projectId)}/decision-context${suffix}`);
    shell.dataset.synthetic=String(context.synthetic);byId('v1-provider-context').hidden=false;setText('v1-provider-name',`PROJECT DATA · ${context.project.name}`);setText('v1-provider-authority',context.synthetic?context.authority:`${context.authority} · ${context.execution_profile}`);setText('v1-provider-badge','PROJECT DATA');byId('v1-manage-project').href=`/projects#project=${encodeURIComponent(projectId)}&section=data`;
    setText('dataSourceLabel',`PROJECT DATA · ${context.project.id}`);setText('dataLoadBadge',context.authority);
    installNativeControls();renderFacts();renderRequirements();installUnits();guardProjectUnits();wireControls();renderHistory();neutralizeReferenceSurface();renderProjectModules();await loadProjectList();
    renderMap();renderUnit();neutralizeReferenceSurface();renderProjectModules(context.run);if(context.run)renderNativeRun(context.run);
    window.refreshUI=()=>{if(context)renderUnit();};
    setTimeout(()=>{renderMap();renderUnit();neutralizeReferenceSurface();renderProjectModules(context.run);if(context.run)renderNativeRun(context.run);providerMap?.invalidateSize?.();},1200);
    if(context.run)renderRun(context.run);
    window.__V1_PROJECT_PROVIDER__={get context(){return context;},get blockedReferencePaths(){return [...blockedReferencePaths];},get selectedUnit(){return selectedUnit;},openUnitPopup(unitId){let opened=false;providerLayers?.eachLayer?.(layer=>{if(layer.__providerUnit===unitId){layer.openPopup?.();opened=true;}});return opened;}};
    if(typeof window.syncRoleInfoBanner==='function')window.syncRoleInfoBanner();
  }
  async function initReference(){
    applyProviderTerminology(false);
    const shell=byId('v1-provider-shell');if(shell)shell.dataset.provider='AKKAYA_REFERENCE';
    if(requestedProvider!==null&&requestedProvider!=='AKKAYA_REFERENCE')throw new Error('Bilinmeyen provider; otomatik referans geçişi uygulanmadı.');
    if(projects.length||runs.length||units.length)throw new Error('AKKAYA_REFERENCE bağlamında project/run/unit parametresi kabul edilmez.');
    wireDrawer();setText('v1-provider-badge','AKKAYA REF');await loadProjectList();window.__V1_PROJECT_PROVIDER__={provider:'AKKAYA_REFERENCE',blockedReferencePaths:[]};
    if(typeof window.syncRoleInfoBanner==='function')window.syncRoleInfoBanner();
  }
  document.addEventListener('DOMContentLoaded',()=>{
    const task=projectMode?initProject():initReference();task.catch(error=>fail(error.message));
    // V1 authentication and panel navigation use hash-only history entries.
    // Reload only when the authoritative provider query state changed.
    window.addEventListener('popstate',()=>{if(projectMode&&location.search!==initialSearch)location.reload();});
  });
})();
