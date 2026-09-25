import {facts,formatNumber,kpis,showJSON,table} from './api.js';

const statusValue=value=>value?.status||'NOT_AVAILABLE';

function validationCard(label,value){
  const card=document.createElement('article');card.className='validation-card';
  const title=document.createElement('strong');title.textContent=label;
  const state=document.createElement('p');state.textContent=statusValue(value);state.className=statusValue(value).toUpperCase().includes('PASS')?'ready':'warning';
  const detail=document.createElement('small');detail.textContent=value?.reason||`Talep ${formatNumber(value?.demand_m3)} · Kullanılabilir ${formatNumber(value?.usable_supply_m3||value?.total_capacity_m3)}`;
  card.append(title,state,detail);return card;
}

function monthlyRows(result){
  const supply=result.monthly_supply_validation||{},delivery=result.monthly_delivery_validation||{},account=result.water_profile_accounting||{};
  const demand=account.monthly_demand_m3||account.planning_year_monthly_demand_m3||supply.demand_m3||delivery.demand_m3||{};
  const supplied=supply.usable_supply_m3||supply.supply_m3||supply.available_supply_m3||{};
  const capacity=delivery.capacity_m3||delivery.cap_m3||{};
  const keys=new Set([...Object.keys(demand||{}),...Object.keys(supplied||{}),...Object.keys(capacity||{})]);
  if(Array.isArray(demand))demand.forEach((_,i)=>keys.add(String(i+1)));
  return [...keys].sort().map((key,i)=>({month:key,demand:Array.isArray(demand)?demand[i]:demand[key],supply:Array.isArray(supplied)?supplied[i]:supplied[key],capacity:Array.isArray(capacity)?capacity[i]:capacity[key],status:(supply.violating_months||[]).includes(key)?'ARZ AŞILDI':(delivery.violating_months||[]).includes(key)?'TESLİM KAPASİTESİ AŞILDI':'PASS'}));
}

function renderMonthly(result){
  const rows=monthlyRows(result),chart=document.getElementById('monthly-chart'),target=document.getElementById('monthly-table');chart.replaceChildren();
  if(!rows.length){chart.innerHTML='<div class="map-fallback">Aylık seri bu sonuç sözleşmesinde bulunmuyor.</div>';target.replaceChildren();return;}
  const max=Math.max(1,...rows.flatMap(row=>[row.demand||0,row.supply||0,row.capacity||0]));
  rows.forEach(row=>{const col=document.createElement('div');col.className='month-column';[['demand',row.demand],['supply',row.supply],['capacity',row.capacity]].forEach(([kind,value])=>{const bar=document.createElement('span');bar.className=`bar ${kind}`;bar.style.height=`${Math.max(1,(Number(value)||0)/max*100)}%`;bar.title=`${kind}: ${formatNumber(value)} m³`;col.append(bar);});const label=document.createElement('span');label.className='month-label';label.textContent=String(row.month).slice(-2);col.append(label);chart.append(col);});
  target.replaceChildren(table(['Ay','Talep (m³)','Kullanılabilir arz (m³)','Teslim kapasitesi (m³)','Durum'],rows.map(row=>[row.month,formatNumber(row.demand),formatNumber(row.supply),formatNumber(row.capacity),row.status])));
}

function renderCrops(result,diagnostic){
  const root=document.getElementById('crop-summary');root.replaceChildren();
  for(const crop of result.top_crops||[]){const card=document.createElement('article');card.className='crop-card';card.innerHTML='<strong></strong><div></div><small></small>';card.children[0].textContent=crop.crop;card.children[1].textContent=`${formatNumber(crop.area_da)} da`;card.children[2].textContent=`Pay: ${formatNumber((crop.share||0)*100,1)}%${diagnostic?' · TEŞHİS':''}`;root.append(card);}
  if(!root.children.length)root.textContent='Ürün yoğunlaşma özeti üretilmedi.';
  const hhi=Number(result.hhi??result.HHI);const level=!Number.isFinite(hhi)?'ÜRETİLMEDİ':hhi>=.25?'YÜKSEK YOĞUNLAŞMA':hhi>=.15?'ORTA YOĞUNLAŞMA':'DAĞITILMIŞ';
  document.getElementById('concentration-badge').textContent=`HHI ${formatNumber(hhi,3)} · ${level}`;
  const shares=document.getElementById('crop-shares');shares.replaceChildren();
  if(!result.crop_shares||typeof result.crop_shares!=='object'||Array.isArray(result.crop_shares)){
    shares.textContent='Kanonik crop_shares backend sonucu tarafından üretilmedi; top_crops üzerinden türetilmedi.';return;
  }
  const areas=new Map((result.top_crops||[]).map(row=>[row.crop,row.area_da]));
  const rows=Object.entries(result.crop_shares).sort((a,b)=>Number(b[1])-Number(a[1])||a[0].localeCompare(b[0],'tr')).map(([crop,share])=>[crop,areas.has(crop)?formatNumber(areas.get(crop)):'—',`${formatNumber(Number(share)*100,2)}%`,diagnostic?'DIAGNOSTIC / ÖNERİ DEĞİL':'KANONİK SONUÇ']);
  shares.replaceChildren(rows.length?table(['Ürün','Alan (da, sağlandıysa)','Kanonik pay','Karar durumu'],rows):document.createTextNode('Kanonik crop_shares boş üretildi.'));
}

function selections(row,scenario){
  if(row.selected_crops)return row.selected_crops.map(item=>`${item.season}: ${item.crop}`).join(', ')||'—';
  if(scenario==='S1')return row.chosenCrop||row.crop||'—';
  return [row.primary&&`Ana: ${row.primary.crop}`,row.secondary&&`İkinci: ${row.secondary.crop}`].filter(Boolean).join(', ')||'—';
}

export function renderUnits(result,scenario,diagnostic=false){
  const units=result.presentation_units?.length?result.presentation_units:result.unit_results?.length?result.unit_results:result.details||[];
  const list=document.getElementById('unit-list'),detail=document.getElementById('unit-detail'),mapRoot=document.getElementById('institutional-map');
  list.replaceChildren();mapRoot.replaceChildren();let map=null;const layers=[];
  if(window.L){map=window.L.map(mapRoot).setView([38.0,34.7],7);window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap'}).addTo(map);}
  else mapRoot.innerHTML='<div class="map-fallback">Harita kitaplığı çevrimdışı. Birim listesi ve detayları kullanılabilir; harita senkronizasyonu uygulanmadı.</div>';

  const select=(row,index)=>{
    [...list.children].forEach((button,i)=>button.classList.toggle('active',i===index));
    layers.forEach((layer,i)=>{if(layer?._icon)layer._icon.classList.toggle('selected-unit-marker',i===index);if(layer?.setStyle)layer.setStyle({weight:i===index?5:2});});
    const missing=row.missing_presentation_metadata||[];
    const warnings=(row.warnings||[]).join(' · ')||'Yok / sağlanmadı';
    facts('unit-detail',[
      ['Karar durumu',diagnostic?'DIAGNOSTIC / UYGULANABİLİR ÖNERİ DEĞİL':'SONUÇ'],
      ['Birim',row.analysis_unit_id||row.parcelId],['Alan (da)',row.area_da],
      ['Mevcut ürün',row.current_crop],['Seçili / önerilen ürün',selections(row,scenario)],
      ['Otoritatif birim suyu (m³)',row.authoritative_unit_water_m3??row.total_water_m3??row.water_m3],
      ['Su otoritesi',row.unit_water_authority],['Birim net kârı (TL)',row.unit_profit_tl??row.total_profit_tl??row.profit_tl],
      ['Durum',row.status],['Uyarılar',warnings],
      ['Geometri',layers[index]?'Haritada mevcut':'GEOMETRİ YOK — yalnız liste/detay'],
      ['Eksik sunum metadatası',missing.join(', ')||'Yok'],
    ]);
    const layer=layers[index];
    if(layer&&map){if(layer.getLatLng)map.setView(layer.getLatLng(),12);else if(layer.getBounds)map.fitBounds(layer.getBounds().pad?.(.1)||layer.getBounds());}
  };

  units.forEach((row,index)=>{
    const id=row.analysis_unit_id||row.parcelId||`Birim ${index+1}`,button=document.createElement('button');
    button.type='button';button.textContent=`${diagnostic?'TEŞHİS · ':''}${id} · ${selections(row,scenario)}`;button.onclick=()=>select(row,index);list.append(button);
    const lat=Number(row.latitude??row.lat),lon=Number(row.longitude??row.lon);let layer=null;
    if(map&&Number.isFinite(lat)&&Number.isFinite(lon))layer=window.L.marker([lat,lon]).addTo(map).bindTooltip(String(id));
    else if(map&&row.geometry&&window.L.geoJSON)layer=window.L.geoJSON(row.geometry).addTo(map).bindTooltip?.(String(id))||null;
    if(layer){layer.on('click',()=>select(row,index));layers[index]=layer;}
  });

  const spatial=layers.filter(Boolean);
  if(map&&spatial.length){const group=window.L.featureGroup(spatial);if(group.getLayers().length)map.fitBounds(group.getBounds().pad(.1));}
  else if(map){map.remove();map=null;mapRoot.innerHTML='<div class="map-fallback">Bu çalışmada koordinat/geometri yok. Birim listesi ve detayları kullanılabilir; harita senkronizasyonu uygulanmadı.</div>';}
  if(units.length)select(units[0],0);else list.textContent='Birim sonucu bulunmuyor.';
}

function renderPlan(result,scenario){
  const rows=[];
  for(const row of result.details||[]){const seasons=scenario==='S1'?[['Tek ürün',{crop:row.chosenCrop||row.crop,water_m3:row.water_m3,profit_tl:row.profit_tl,area_da:row.area_da}]]:[['Ana',row.primary],['İkinci',row.secondary]];for(const [season,crop] of seasons){if(crop)rows.push([row.parcelId||row.analysis_unit_id,season,crop.crop,formatNumber(crop.area_da??row.area_da),formatNumber(crop.water_m3),formatNumber(crop.profit_tl)]);}}
  document.getElementById('plan').replaceChildren(rows.length?table(['Birim','Sezon','Ürün','Alan (da)','Su (m³)','Net kâr (TL)'],rows):document.createTextNode('Plan satırı üretilmedi.'));
}

export function renderRun(run){
  const result=run.result||{},summary=run.summary||{},context=run.presentation_context||{};
  const synthetic=run.result_authority_label==='SYNTHETIC / NOT_OFFICIAL'||run.provenance?.data_source_notes==='synthetic_test_fixture';
  document.getElementById('result').hidden=false;
  const source=document.getElementById('result-source-label');source.className=synthetic?'alert danger':'alert warning';source.textContent=synthetic?'SYNTHETIC / NOT OFFICIAL · Sentetik test verisi':run.result_authority_label||'REFERENCE MODEL / DEMO DATA';
  const feasible=result.overall_feasible??result.feasible,diagnostic=feasible===false;
  const status=document.getElementById('result-status');status.textContent=feasible===true?'UYGULANABİLİR':diagnostic?'DIAGNOSTIC':'DURUM YOK';status.className=`verdict ${feasible===true?'ready':'blocked'}`;document.getElementById('infeasible-banner').hidden=!diagnostic;
  kpis('result-kpis',[['Toplam net kâr',`${formatNumber(result.total_profit_tl)} TL`],['Otoritatif su',`${formatNumber(result.authoritative_water_m3??result.total_water_m3)} m³`],['Su verimliliği',`${formatNumber(result.efficiency_tl_per_m3,4)} TL/m³`],['Aktif alan',`${formatNumber(summary.active_area_da)} da`],['Nadas / boş',`${formatNumber(summary.fallow_area_da)} da`],['Uygunluk',feasible===true?'PASS':diagnostic?'FAIL':'—']]);
  facts('result-facts',[['Execution profile',run.execution_profile],['Classification',result.classification],['Proje',run.provenance?.project_name||run.project_id],['Proje kimliği',run.project_id],['Algoritma',run.algorithm],['scenario',run.scenario],['Seed',run.seed],['Hedef',run.configuration?.objective||result.objective],['Skor',summary.score??'Motor bu metrik için değer üretmedi'],['Plan farkı',result.delta?JSON.stringify(result.delta):'Motor bu metrik için değer üretmedi'],['Çalışma kimliği',run.id],['Başlangıç',run.started_at],['Tamamlanma',run.completed_at]]);
  kpis('water-kpis',[['Optimizer suyu',`${formatNumber(result.optimizer_water_m3)} m³`],['Doğrulanmış tam sezon',`${formatNumber(result.verified_profile_water_m3)} m³`],['Planlama yılı',`${formatNumber(result.planning_year_profile_water_m3)} m³`],['Otoritatif değer',`${formatNumber(result.authoritative_water_m3)} m³`]]);
  document.getElementById('efficiency-denominator').textContent=result.efficiency_tl_per_m3_denominator||'—';
  const validation=document.getElementById('water-validation');validation.replaceChildren(validationCard('Yıllık bütçe',result.annual_budget_validation),validationCard('Aylık arz',result.monthly_supply_validation),validationCard('Aylık teslim',result.monthly_delivery_validation),validationCard('Su uzlaştırma',result.water_reconciliation));
  renderMonthly(result);renderCrops(result,diagnostic);renderPlan(result,run.scenario);renderUnits(result,run.scenario,diagnostic);
  const warnings=[...(run.warnings||[]),...(result.warnings||[])],warningList=document.getElementById('result-warnings');warningList.replaceChildren();
  for(const warning of warnings.length?[...new Set(warnings)]:['Ek veri uyarısı yok.']){const item=document.createElement('li');item.textContent=warning;warningList.append(item);}
  const econLabel=document.getElementById('economics-label');econLabel.textContent=synthetic?'SYNTHETIC / NOT OFFICIAL':run.execution_profile==='VERIFIED_INSTITUTIONAL'?'VERIFIED INSTITUTIONAL EKONOMİ':'KATALOG TÜREVİ REFERANS EKONOMİ';econLabel.className=`mode-badge ${synthetic?'synthetic':run.execution_profile==='VERIFIED_INSTITUTIONAL'?'verified':'reference'}`;
  kpis('economics-kpis',[['Toplam net kâr',`${formatNumber(result.total_profit_tl)} TL`],['TL/m³',formatNumber(result.efficiency_tl_per_m3,4)],['Hedef',run.configuration?.objective||result.objective||'—']]);
  showJSON('provenance',{id:run.id,started_at:run.started_at,completed_at:run.completed_at,...run.provenance,result_provenance:result.result_provenance,input_provenance:result.input_provenance,current_project_state:context});
  facts('provenance-summary',[['Çalışma kimliği',run.id],['Proje kimliği',run.project_id],['Run veri revizyonu',context.run_project_revision??result.result_provenance?.preview_revision],['Güncel proje revizyonu',context.current_project_revision],['Yeniden analiz gerekli',context.requires_reanalysis],['Eski input snapshotına sabitlenmiş',context.pinned_to_older_input_snapshot],['Revizyon ilişkisi',context.revision_relationship],['Selection hash',result.result_provenance?.selection_hash],['Engine commit',result.result_provenance?.engine_commit],['Profil',run.execution_profile],['Sınıflandırma',result.classification],['Kaynak etiketi',run.result_authority_label],['Zaman',run.completed_at]]);
}
