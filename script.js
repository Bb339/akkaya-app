// Demo veri seti

// --- v51 CLEAN: Fixed crop pools (Senaryo-1) ---
let S1_PRIMARY_CROPS = [];

// --- v54: Mevcut 2. sezon eşleşmeleri + mevcut sulama yöntemleri (kullanıcı girdisi) ---
// Not: "Karık" ve "Salma" -> surface, "Yağmurlama" -> sprinkler, "Damla" -> drip, "Yağışa bağlı" -> rainfed
let S1_PAIRING = {
  "Patates":            { season1:"Yazlık", irr1:"Karık (yaygın)", secondary:"Buğday (Dane)",          season2:"Kışlık", irr2:"Yağışa bağlı / Destek sulama (yağmurlama)" },
  "Silajlık Mısır":     { season1:"Yazlık", irr1:"Karık / Yağmurlama", secondary:"Fiğ / Yem Bezelyesi", season2:"Kışlık", irr2:"Yağmurlama" },
  "Yonca (Yeşilot)":    { season1:"Çok yıllık", irr1:"Salma / Yağmurlama", secondary:"–",               season2:"–",     irr2:"–" },
  "Buğday (Dane)":      { season1:"Kışlık", irr1:"Yağışa bağlı (kuru)", secondary:"Silajlık Mısır",     season2:"Yazlık", irr2:"Karık / Yağmurlama" },
  "Arpa (Dane)":        { season1:"Kışlık", irr1:"Yağışa bağlı (kuru)", secondary:"Ayçiçeği (Yağlık)", season2:"Yazlık", irr2:"Yağmurlama" },
  "Şeker Pancarı":      { season1:"Yazlık", irr1:"Karık",               secondary:"Buğday (Dane)",      season2:"Kışlık", irr2:"Yağışa bağlı / Yağmurlama" },
  "Çavdar (Dane)":      { season1:"Kışlık", irr1:"Genelde sulamasız",   secondary:"Kabak (Çerezlik)",  season2:"Yazlık", irr2:"Karık" },
  "Salçalık Domates":   { season1:"Yazlık", irr1:"Karık",               secondary:"Ispanak",           season2:"Kışlık", irr2:"Yağmurlama" },
  "Sofralık Domates":   { season1:"Yazlık", irr1:"Karık",               secondary:"Marul",             season2:"Kışlık", irr2:"Yağmurlama" },
  "Lahana (Beyaz)":     { season1:"Kışlık", irr1:"Karık / Yağmurlama",  secondary:"Fasulye (Taze)",   season2:"Yazlık", irr2:"Karık" },
  "Kabak (Çerezlik)":   { season1:"Yazlık", irr1:"Karık",               secondary:"Buğday (Dane)",     season2:"Kışlık", irr2:"Yağışa bağlı" },
  "Fasulye (Taze)":     { season1:"Yazlık", irr1:"Karık",               secondary:"Ispanak",           season2:"Kışlık", irr2:"Yağmurlama" },
  "Soğan (Kuru)":       { season1:"Yazlık", irr1:"Karık",               secondary:"Arpa (Dane)",       season2:"Kışlık", irr2:"Yağışa bağlı" },
  "Kavun":              { season1:"Yazlık", irr1:"Karık",               secondary:"Buğday (Dane)",     season2:"Kışlık", irr2:"Yağışa bağlı" },
  "Salçalık Biber":     { season1:"Yazlık", irr1:"Karık",               secondary:"Marul / Ispanak",   season2:"Kışlık", irr2:"Yağmurlama" },
};

function irrKeyFromText(t){
  const s = (t||'').toLowerCase();
  if(s.includes('damla')) return 'drip';
  if(s.includes('yağmurlama') || s.includes('sprink')) return 'sprinkler';
  if(s.includes('pivot') || s.includes('lineer')) return 'pivot';
  if(s.includes('salma') || s.includes('karık') || s.includes('yüzey') || s.includes('surface')) return 'surface';
  if(s.includes('yağış') || s.includes('kuru') || s.includes('sulamasız')) return 'rainfed';
  return 'sprinkler';
}

// Arazi kullanim kodu (B/Bs=bahce, V/Vs=bag) ayiklayici
function landUseCodeFromSoilUnit(code){
  const s = String(code||"" );
  const m = s.match(/\b(Bs|B|Vs|V)\b/);
  return m ? m[1] : null;
}


let S1_SECONDARY_CROPS = ["Ispanak", "Karpuz", "Marul", "Hıyar (Sofralık)", "Hıyar (Turşuluk)", "Kabak (Sakız)", "Kabak (Bal)", "Bamya", "Barbunya Fasulye (Taze)", "Bezelye (Taze)", "Sivri Biber", "Soğan (Taze)", "Sarımsak (Kuru)", "Sarımsak (Taze)", "Turp (Kırmızı)", "Maydanoz", "Patlıcan", "Pırasa"];
function _hashInt(str){
  let h=0; for(let i=0;i<str.length;i++){ h=(h*31 + str.charCodeAt(i))>>>0; } return h>>>0;
}
function ensureCurrentPattern(parcel){
  if(!parcel) return;
  // v54: Mevcut desen, 1. ürün + (varsa) tabloya göre 2. ürün olacak şekilde kurulur.
  const pid = (parcel.id||parcel.name||'P').toString();
  const h=_hashInt(pid);
// Guard: if Scenario-1 primary crop pool hasn't loaded yet, fall back to pairing keys (or a small default list)
if(!Array.isArray(S1_PRIMARY_CROPS) || S1_PRIMARY_CROPS.length === 0){
  const fallback = Object.keys(S1_PAIRING||{}).filter(Boolean);
  S1_PRIMARY_CROPS = (fallback && fallback.length) ? fallback : ["Patates","Buğday (Dane)","Arpa (Dane)","Silajlık Mısır"];
}
const c1Raw = S1_PRIMARY_CROPS[h % S1_PRIMARY_CROPS.length];

  const pair = S1_PAIRING[c1Raw] || { season1:"–", irr1:"–", secondary:"–", season2:"–", irr2:"–" };
  let c2Raw = (pair.secondary||'–');
  if(c2Raw.includes('/')){
    const parts = c2Raw.split('/').map(x=>x.trim()).filter(Boolean);
    c2Raw = parts[(h>>3) % parts.length];
  }
  if(c2Raw === '–' || c2Raw === '-') c2Raw = null;

  const A = +parcel.area_da || +parcel.area || 0;
  const a1 = A*0.7; const a2 = Math.max(0, A-a1);

  // Lookup water/profit per da from crop catalog (STATE.cropsByName is built in loader)
  const lookup = (nm)=>{
    const key = normCropName(nm);
    const m = (STATE && STATE.cropCatalog) ? (STATE.cropCatalog[key] || null) : null;
    if(m){
      return { waterPerDa: safeNum(m.waterPerDa || m.water_m3_da || m.su_m3_da || m.water),
               profitPerDa: safeNum(m.profitPerDa || m.net_kar_tl_da || m.kar_tl_da || m.profit) };
    }
    // fallback: derive from parcel totals if available
    const area = safeNum(A);
    const w = safeNum(parcel.water_m3);
    const pr = safeNum(parcel.profit_tl);
    return { waterPerDa: area>0 ? (w/area) : 0, profitPerDa: area>0 ? (pr/area) : 0 };
  };

  const c1 = prettyCropName(c1Raw);
  const c2 = c2Raw ? prettyCropName(c2Raw) : null;
  const m1 = lookup(c1);
  const m2 = c2 ? lookup(c2) : {waterPerDa:0, profitPerDa:0};

  const irr1Text = pair.irr1 || '–';
  const irr2Text = pair.irr2 || '–';
  const s1 = pair.season1 || '–';
  const s2 = pair.season2 || '–';

  const rows = [];
  rows.push({
    name: c1,
    season: s1,
    irrigationCurrentText: irr1Text,
    irrigationCurrentKey: irrKeyFromText(irr1Text),
    area: +a1.toFixed(1),
    waterPerDa: +m1.waterPerDa.toFixed(3),
    profitPerDa: +m1.profitPerDa.toFixed(3)
  });
  if(c2){
    rows.push({
      name: c2,
      season: s2,
      irrigationCurrentText: irr2Text,
      irrigationCurrentKey: irrKeyFromText(irr2Text),
      area: +a2.toFixed(1),
      waterPerDa: +m2.waterPerDa.toFixed(3),
      profitPerDa: +m2.profitPerDa.toFixed(3)
    });
  }
  parcel.cropCurrent = rows;
}

let lastOptimizeReqId = 0;
let optimizeAbortCtrl = null; // deprecated (no longer aborting requests)
let optimizeInFlight = 0;

// Per-section abort controllers (avoid cross-tab AbortError noise)
let benchmarkAbortCtrl = null;
let impactAbortCtrl = null;
let profitAbortCtrl = null;

// 15-year impact charts (Chart.js instances)
let impactWater15Chart = null;
let impactProfit15Chart = null;

function _destroyChart(ch){
  try{ if(ch && typeof ch.destroy === "function") ch.destroy(); }catch(e){}
}

function renderImpactWater15Chart(out){
  try{
    const canvas = document.getElementById("impactWater15Chart");
    if(!canvas || !window.Chart) return;
    const s = (out && out.series) ? out.series : null;
    if(!s || !s.years) return;
    const labels = s.years.map(String);
    const datasets = [];
    const dashFor = (label)=>{
      // Overlapping series can look like a single line; dashes help differentiate.
      // (We intentionally do not force colors.)
      if(label === 'GA') return [];
      if(label === 'ACO') return [8,4];
      if(label === 'ABC') return [2,3];
      if(label === 'AVG') return [10,3,2,3];
      return [];
    };
    const algos = (out.algorithms || ["GA","ACO","ABC"]).slice();
    for(const a of algos){
      const v = (s[a] && s[a].cumulative_saving_m3) ? s[a].cumulative_saving_m3 : [];
      datasets.push({label: a, data: v, borderDash: dashFor(a), pointRadius: 2});
    }
    if(s.AVG && s.AVG.cumulative_saving_m3){
      datasets.push({label: "AVG", data: s.AVG.cumulative_saving_m3, borderDash: dashFor('AVG'), pointRadius: 2});
    }
    _destroyChart(impactWater15Chart);
    impactWater15Chart = window._droughtChart = new Chart(canvas.getContext("2d"), {
      type: "line",
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: { legend: { display: true } },
        scales: { x: { title: { display: true, text: "Yıl" } }, y: { title: { display: true, text: "m³" } } }
      }
    });
  }catch(e){}
}

function renderImpactProfit15Chart(out){
  try{
    const canvas = document.getElementById("impactProfit15Chart");
    if(!canvas || !window.Chart) return;
    const s = (out && out.series) ? out.series : null;
    if(!s || !s.years) return;
    const labels = s.years.map(String);
    const datasets = [];
    const dashFor = (label)=>{
      // Same idea as water chart: differentiate overlapping lines via dashes.
      if(label === 'GA') return [];
      if(label === 'ACO') return [8,4];
      if(label === 'ABC') return [2,3];
      if(label === 'AVG') return [10,3,2,3];
      return [];
    };
    const algos = (out.algorithms || ["GA","ACO","ABC"]).slice();
    for(const a of algos){
      const v = (s[a] && s[a].cumulative_delta_tl) ? s[a].cumulative_delta_tl : [];
      datasets.push({label: a, data: v, borderDash: dashFor(a), pointRadius: 2});
    }
    if(s.AVG && s.AVG.cumulative_delta_tl){
      datasets.push({label: "AVG", data: s.AVG.cumulative_delta_tl, borderDash: dashFor('AVG'), pointRadius: 2});
    }
    _destroyChart(impactProfit15Chart);
    impactProfit15Chart = new Chart(canvas.getContext("2d"), {
      type: "line",
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: { legend: { display: true } },
        scales: { x: { title: { display: true, text: "Yıl" } }, y: { title: { display: true, text: "TL" } } }
      }
    });
  }catch(e){}
}

function _resetAbort(ctrlRefName){
  try{
    const c = eval(ctrlRefName);
    if(c) c.abort();
  }catch(e){}
}

// ------------------------------------------------------------
// Boot safety shims
// If any of these are referenced before the main UI functions
// are defined (e.g., due to cache or partial reload), we avoid
// hard crashes and keep the app usable.
function refreshParcelSelect() {}
function refreshGlobalSummary() {}
function refreshCharts() {}
function refreshMap() {}

let parcelData =[];

// =========================
// Veri Paketi A – Tam Entegrasyon (baraj + projeksiyon + resmî excel özetleri)
// =========================
const DATA_FILES = {
  // PRIMARY SOURCE OF TRUTH (ENHANCED package)
  enhanced: {
    parcelAssumptionsCsv: "data/enhanced_dataset/csv/parcel_assumptions.csv",
    soilParamsCsv: "data/enhanced_dataset/csv/soil_params_assumed.csv",
    cropParamsCsv: "data/enhanced_dataset/csv/crop_params_assumed.csv",
    climateMonthlyCsv: "data/enhanced_dataset/csv/monthly_climate_all_parcels.csv",
    reservoirMonthlyCsv: "data/enhanced_dataset/csv/akkaya_reservoir_monthly_backend.csv",
    senaryo1SeasonsCsv: "data/enhanced_dataset/csv/senaryo1_backend_seasons.csv",
    senaryo2SeasonsCsv: "data/enhanced_dataset/csv/senaryo2_backend_seasons.csv",
    weightsCsv: "data/enhanced_dataset/csv/objective_weight_sets.csv",
    rotationRulesCsv: "data/enhanced_dataset/csv/rotation_rules_default.csv",
    cropSuitabilityCsv: "data/enhanced_dataset/csv/crop_suitability_assumed.csv",
    irrigationMethodsCsv: "data/enhanced_dataset/csv/irrigation_methods_assumed.csv",
    deliveryCapacityCsv: "data/enhanced_dataset/csv/delivery_capacity_monthly_assumed.csv",
    waterQualityCsv: "data/enhanced_dataset/csv/water_quality_monthly_assumed.csv",
    // Sunum/demo için: yerel fiyat/teşvik kataloğu (opsiyonel)
    marketOverridesDemoCsv: "data/enhanced_dataset/csv/market_overrides_demo.csv"
  },

  // LEGACY UI files (still used by some charts)
  cropsCsv: "data/urun_parametreleri_demo.csv",
  parcelsCsv: "data/parsel_su_kar_ozet.csv",
  barajCsv: "data/akkaya_baraj_su_bilanco_2000_2025_clean.csv",
  barajRawCsv: "data/akkaya_baraj_su_bilanco_2000_2025.csv",
  projCsv: "data/su_butcesi_projeksiyonu_2025_2050_clean.csv",
  projRawCsv: "data/su_butcesi_projeksiyonu_2025_2050.csv",
  villageJson: "data/village_crop_patterns.json",
  districtJson: "data/district_crop_patterns.json",
  excelVillageJson: "data/excel_derived/village_crop_patterns_from_excels_2024.json",
  excelDistrictJson: "data/excel_derived/district_crop_patterns_from_excels_2023.json"
};

/* ENHANCED_DATA_LOADER */
function groupBy(arr, keyFn){
  const m = new Map();
  for(const x of arr){
    const k = keyFn(x);
    if(!m.has(k)) m.set(k, []);
    m.get(k).push(x);
  }
  return m;
}
function safeNum(x){ const v = +x; return isFinite(v) ? v : 0; }
function monthKeyToYear(m){ return +String(m||"").slice(0,4); }

// --- HTML escaping for safe UI messages / tooltips
function escapeHtml(s){
  const str = String(s ?? '');
  return str
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;')
    .replace(/'/g,'&#39;');
}

// Number formatting (TR) – used in 15Y outputs & tooltips
function formatNumber(x, digits=0){
  const n = Number(x);
  if(!isFinite(n)) return '—';
  const d = Math.max(0, Math.min(4, Number(digits)||0));
  try {
    return new Intl.NumberFormat('tr-TR', {minimumFractionDigits:d, maximumFractionDigits:d}).format(n);
  } catch(e){
    return n.toFixed(d);
  }
}


// Expose helpers for any dynamically injected code paths
window.escapeHtml = window.escapeHtml || escapeHtml;
window.formatNumber = window.formatNumber || formatNumber;

// --- Normalize season source values coming from different dropdowns
function normalizeSeasonSource(val){
  const v = String(val||'').trim().toLowerCase();
  // This project uses ONLY Senaryo-1 (s1) or Senaryo-2 (s2). Any "both/birleşik" input falls back to s1.
  if(!v) return 's1';
  if(v==='both' || v==='birlesik' || v==='birleşik' || v.includes('birleş') || v.includes('s1+s2') || v.includes('senaryo-1 + senaryo-2')) return 's1';
  if(v==='s1' || v.includes('senaryo-1')) return 's1';
  if(v==='s2' || v.includes('senaryo-2')) return 's2';
  if(v==='use_selected') return 'use_selected';
  if(v==='all') return 'all';
  return 's1';
}


// Build / refresh parcel-level baseline ("Mevcut") crop plan from the enhanced season tables
// for the currently selected year. This fixes:
//  - Negative/odd basin "Mevcut" efficiency caused by legacy parcel summaries
//  - Parcel switching showing the same baseline/product suggestions
function applyYearBaselinesFromSeasons(){
  if(!Array.isArray(parcelData) || !parcelData.length) return;
  if(!Array.isArray(STATE.seasonRows) || !STATE.seasonRows.length) return;

  const ySel = +STATE.selectedWaterYear;
  const all = STATE.seasonRows;

  for(const p of parcelData){
    const pid = p.id;
    if(!pid) continue;

    // rows for selected year; if none, fall back to latest available year for that parcel
    let rows = all.filter(r => String((r.parcel_id||r.parsel_id||'')).trim()===pid && (+r.year===ySel));
    if(!rows.length){
      const yrs = all.filter(r=>String((r.parcel_id||r.parsel_id||'')).trim()===pid).map(r=>+r.year).filter(v=>isFinite(v));
      const yMax = yrs.length ? Math.max(...yrs) : NaN;
      if(isFinite(yMax)) rows = all.filter(r => String((r.parcel_id||r.parsel_id||'')).trim()===pid && (+r.year===yMax));
    }
    if(!rows.length) continue;

    const areaDa = safeNum(p.area_da) || safeNum(rows[0].area_da) || 0;
    if(areaDa<=0) continue;

    // Prefer primary season as baseline cropping pattern
    let rowsUse = rows.filter(r=>String(r.season||'').toLowerCase().startsWith('primary'));
    if(!rowsUse.length) rowsUse = rows;

    const byCrop = groupBy(rowsUse, r=>(r.crop||"").trim());
    const crops = [];
    for(const [cname, rr] of byCrop.entries()){
      if(!cname) continue;
      const water = rr.reduce((s,r)=>s+safeNum(r.water_m3_calib_gross || r.water_m3_calib_net || r.water_m3_et_gross || r.water_m3_et_net),0);
      const profit = rr.reduce((s,r)=>s+safeNum(r.profit_tl),0);
      // Divide by parcel area (not sum of area_da, which repeats per season)
      crops.push({
        name: normCropName(cname),
        waterPerDa: water/areaDa,
        profitPerDa: profit/areaDa,
        _waterTotal: water,
        _profitTotal: profit
      });
    }
    if(!crops.length) continue;
    crops.sort((a,b)=>(b.profitPerDa||0)-(a.profitPerDa||0));

    // Limit to top-2 (UI "Mevcut" should be at most 2 crops). By default we DO NOT
    // overwrite parcel.cropCurrent from season tables unless explicitly enabled.
    const top = crops.slice(0,2);
    const split = areaDa / (top.length || 1);
    if(STATE.useOfficialBaseline){
      p.cropCurrent = top.map(c=>({
        name: c.name,
        area: +split.toFixed(1),
        waterPerDa: +c.waterPerDa.toFixed(1),
        profitPerDa: +c.profitPerDa.toFixed(1)
      }));
    }

    // Update parcel-level summary totals for the selected year
    const totWater = top.reduce((s,c)=>s+c._waterTotal,0);
    const totProfit = top.reduce((s,c)=>s+c._profitTotal,0);
    p.water_m3 = Math.round(totWater);
    p.profit_tl = Math.round(totProfit);
  }
}

// Ensure each parcel has a baseline crop breakdown (cropCurrent).
// The UI's "Mevcut" scenario calculations expect parcel.cropCurrent to exist.
// If the backend only provides parcel-level totals (water_m3/profit_tl) we
// synthesize a single-row baseline so totals and comparisons are meaningful.
function ensureBaselineCropCurrent(parcel){
  if (!parcel) return;
  if (Array.isArray(parcel.cropCurrent) && parcel.cropCurrent.length) return;
  const area = safeNum(parcel.area_da);
  const water = safeNum(parcel.water_m3);
  const profit = safeNum(parcel.profit_tl);
  const waterPerDa = area > 0 ? (water / area) : 0;
  const profitPerDa = area > 0 ? (profit / area) : 0;
  parcel.cropCurrent = [{
    name: parcel.baseline_crop || 'MEVCUT',
    area: area,
    waterPerDa: waterPerDa,
    profitPerDa: profitPerDa,
  }];
}

// --- Scenario-1 baseline "Mevcut Ürün Deseni" generator (exactly 2 crops per parcel) ---
function _hashStr(s){
  const str = String(s||"");
  let h = 2166136261;
  for(let i=0;i<str.length;i++){
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h>>>0);
}
const S1_PRIMARY_15 = [
  "PATATES","SİLAJLIK MISIR","YONCA (YEŞİLOT)","BUĞDAY (DANE)","ARPA (DANE)","ŞEKER PANCARI","ÇAVDAR (DANE)",
  "SALÇALIK DOMATES","SOFRALIK DOMATES","LAHANA (BEYAZ)","KABAK (ÇEREZLİK)","FASULYE (TAZE)","SOĞAN (KURU)","KAVUN","SALÇALIK BİBER"
].map(normCropName);

// --- Senaryo-2 ürün havuzu (kullanıcı ile mutabık kalınan liste) ---
// Not: normCropName() parantez içini atabildiği için hem "BAĞ (ÜZÜM)" gibi
// hem de sade isimler aynı anahtara düşer.
const S2_PRIMARY_POOL = [
  // Çok yıllık / bahçe
  'ELMA','KİRAZ','BAĞ (ÜZÜM)','CEVİZ','ARMUT','ŞEFTALİ','NEKTARİN','KAYISI','VİŞNE','ERİK',
  // Tarla bitkileri
  'PATATES','SİLAJLIK MISIR','YONCA (YEŞİLOT)','BUĞDAY (DANE)','ŞEKER PANCARI'
].map(normCropName);

// Senaryo-2 aday havuzu (ham isimler). runOptimization() bu listeyi kullanarak
// gerçekten Senaryo-2 ürün havuzuna göre öneri üretir.
const S2_PRIMARY_RAW = [
  'Elma','Kiraz','Bağ (Üzüm)','Ceviz','Armut','Şeftali','Nektarin','Kayısı','Vişne','Erik',
  'Patates','Silajlık Mısır','Yonca (Yeşilot)','Buğday (Dane)','Şeker Pancarı'
];

// Senaryo-2'de meyve/bag (çok yıllık bahçe ürünleri) sadece ilgili arazi kullanımında
// (Bahçe/Bağ parselleri) önerilmelidir. Tarla parsellerinde bahçe kurulumu önerisi
// gerçekçi olmadığı için bu ürünleri aday havuzundan çıkarıyoruz.
const S2_FRUIT_VINE_KEYS = new Set([
  'ELMA','KİRAZ','BAĞ (ÜZÜM)','CEVİZ','ARMUT','ŞEFTALİ','NEKTARİN','KAYISI','VİŞNE','ERİK'
].map(normCropName));
function isS2FruitVine(name){
  return S2_FRUIT_VINE_KEYS.has(normCropName(name));
}

// --- Senaryo-2 varsayılan su/kâr parametreleri (m3/da ve TL/da) ---
// Senaryo-2 "mutabık ürün havuzu" (meyve + seçili tarla bitkileri) için
// veri paketinde her zaman doğrudan ekonomi/su parametresi bulunmayabiliyor.
// Bu yüzden Senaryo-2 seçildiğinde aşağıdaki muhafazakâr varsayımlar
// katalogdaki eksik değerleri tamamlamak için kullanılır.
// (Amaç: UI'da 0 veya milyonlarca m3/da gibi ölçek hatalarını engellemek.)
const S2_DEFAULT_PARAMS = {
  // Çok yıllık / bahçe
  [normCropName('ELMA')]:            { waterPerDa: 550, profitPerDa: 14000, type:'bahce' },
  [normCropName('KİRAZ')]:           { waterPerDa: 600, profitPerDa: 16000, type:'bahce' },
  [normCropName('BAĞ (ÜZÜM)')]:      { waterPerDa: 520, profitPerDa: 15000, type:'bahce' },
  [normCropName('CEVİZ')]:           { waterPerDa: 480, profitPerDa: 13000, type:'bahce' },
  [normCropName('ARMUT')]:           { waterPerDa: 560, profitPerDa: 14000, type:'bahce' },
  [normCropName('ŞEFTALİ')]:         { waterPerDa: 600, profitPerDa: 15000, type:'bahce' },
  [normCropName('NEKTARİN')]:        { waterPerDa: 600, profitPerDa: 15000, type:'bahce' },
  [normCropName('KAYISI')]:          { waterPerDa: 520, profitPerDa: 14000, type:'bahce' },
  [normCropName('VİŞNE')]:           { waterPerDa: 550, profitPerDa: 13500, type:'bahce' },
  [normCropName('ERİK')]:            { waterPerDa: 560, profitPerDa: 13500, type:'bahce' },
  // Tarla bitkileri
  [normCropName('PATATES')]:         { waterPerDa: 620, profitPerDa: 6000,  type:'tarla' },
  [normCropName('SİLAJLIK MISIR')]:  { waterPerDa: 820, profitPerDa: 5500,  type:'tarla' },
  [normCropName('YONCA (YEŞİLOT)')]: { waterPerDa: 700, profitPerDa: 6500,  type:'tarla' },
  [normCropName('BUĞDAY (DANE)')]:   { waterPerDa: 260, profitPerDa: 4500,  type:'tarla' },
  [normCropName('ŞEKER PANCARI')]:   { waterPerDa: 900, profitPerDa: 7000,  type:'tarla' },
};

function ensureScenario2Catalog(){
  const cat = STATE.cropCatalog || {};
  for(const [k,v] of Object.entries(S2_DEFAULT_PARAMS)){
    const ex = cat[k] || {};
    const w = safeNum(ex.waterPerDa);
    const p = safeNum(ex.profitPerDa);
    // Only fill when missing/invalid OR clearly an outlier (ölçek hatası)
    const needW = !(isFinite(w) && w>=0 && w<=3000);
    const needP = !(isFinite(p) && p>=-50000 && p<=50000);
    if(needW || needP || !ex.name){
      cat[k] = {
        ...ex,
        name: ex.name || k,
        rawName: ex.rawName || k,
        waterPerDa: (needW ? v.waterPerDa : w),
        profitPerDa: (needP ? v.profitPerDa : p),
        type: ex.type || v.type || 'tarla',
        category: ex.category || (v.type==='bahce' ? 'bahçe' : 'tarla'),
      };
    }
  }
  STATE.cropCatalog = cat;
}

// Minimal family map (rotation/soil compatibility)
const CROP_FAMILY_S1 = {
  [normCropName("PATATES")]: "solanaceae",
  [normCropName("SALÇALIK DOMATES")]: "solanaceae",
  [normCropName("SOFRALIK DOMATES")]: "solanaceae",
  [normCropName("SALÇALIK BİBER")]: "solanaceae",
  [normCropName("LAHANA (BEYAZ)")]: "brassicaceae",
  [normCropName("KABAK (ÇEREZLİK)")]: "cucurbitaceae",
  [normCropName("KAVUN")]: "cucurbitaceae",
  [normCropName("FASULYE (TAZE)")]: "fabaceae",
  [normCropName("YONCA (YEŞİLOT)")]: "fabaceae",
  [normCropName("BUĞDAY (DANE)")]: "poaceae",
  [normCropName("ARPA (DANE)")]: "poaceae",
  [normCropName("ÇAVDAR (DANE)")]: "poaceae",
  [normCropName("SİLAJLIK MISIR")]: "poaceae",
  [normCropName("ŞEKER PANCARI")]: "amaranthaceae",
  [normCropName("SOĞAN (KURU)")]: "amaryllidaceae",
};

function refreshScenarioBaselineCurrent(){
  // Baseline "Mevcut" MUST exist for every parcel.
  // Primary intent: Senaryo-1 (15 ürün havuzu) ile 2 ürün üretmek.
  // Ancak veri paketindeki sezon-1 ürün isimleri farklıysa (örn. "Domates (Salçalık)")
  // 2 ürün boş kalmasın diye ENHANCED sezon satırlarından parsel-bazlı top-2 fallback uygularız.

  const catalog = STATE.cropCatalog || {};
  const hasCatalog = catalog && Object.keys(catalog).length;

  for(const p of (STATE.parcels||[])){
    const areaDa = safeNum(p.area_da);
    if(areaDa<=0) continue;

    const seasonSource = (document.getElementById('seasonSourceSel')?.value) || STATE.seasonSource || 's1';
    if(seasonSource === 's2'){
      // Senaryo-2'de "Mevcut" ürün deseni, kullanıcı ile mutabık kalınan havuzdan
      // üretilmelidir. Senaryo-2 sezon dosyası farklı ürünler içerebildiği için
      // burada sezon satırlarına fallback YAPILMAZ.
      ensureScenario2Catalog();

      const fruit = [
        'ELMA','KİRAZ','BAĞ (ÜZÜM)','CEVİZ','ARMUT','ŞEFTALİ','NEKTARİN','KAYISI','VİŞNE','ERİK'
      ];
      const summer = ['PATATES','SİLAJLIK MISIR','ŞEKER PANCARI','YONCA (YEŞİLOT)'];
      const winter = ['BUĞDAY (DANE)'];

      // Basit deterministik seçim: bazı parselleri bahçe (çok yıllık) kabul edip tek ürün;
      // diğerlerinde yazlık+kışlık rotasyon (2 ürün) kur.
      const h = _hashInt(String(p.id || p.parcel_id || p.name || 'P'));
      const lu = landUseCodeFromSoilUnit(p.soil_unit_code || p.soilUnitCode || p.soilCode || '');
      const isOrchard = !!lu; // arazi koduna gore bahce/bag


      let c1=null, c2=null, w1=0, w2=0, r1=0, r2=0;
      if(isOrchard){
        const pick = fruit[h % fruit.length];
        c1 = pick; c2 = null;
        const meta = STATE.cropCatalog[normCropName(pick)] || S2_DEFAULT_PARAMS[normCropName(pick)] || {};
        w1 = safeNum(meta.waterPerDa, 550);
        r1 = safeNum(meta.profitPerDa, 14000);
      }else{
        const pick1 = summer[h % summer.length];
        const pick2 = winter[0];
        c1 = pick1;
        c2 = (normCropName(pick1) === normCropName(pick2)) ? null : pick2;
        const m1 = STATE.cropCatalog[normCropName(pick1)] || S2_DEFAULT_PARAMS[normCropName(pick1)] || {};
        const m2 = c2 ? (STATE.cropCatalog[normCropName(pick2)] || S2_DEFAULT_PARAMS[normCropName(pick2)] || {}) : {};
        w1 = safeNum(m1.waterPerDa, 650);
        r1 = safeNum(m1.profitPerDa, 6000);
        w2 = safeNum(m2.waterPerDa, 260);
        r2 = safeNum(m2.profitPerDa, 4500);
      }

      // Alan: bahçede %100, rotasyonda 50/50 (aynı alanda ardışık ekim mantığı değil;
      // "mevcut" varsayımıyla iki ürün de parsel içinde bölüşüyor gibi gösterilir.)
      const a1 = +areaDa.toFixed(1);
      const a2 = c2 ? +areaDa.toFixed(1) : 0;

      const season1 = isOrchard ? 'Çok yıllık' : 'Yazlık';
      const season2 = c2 ? 'Kışlık' : '—';

      p.cropCurrent = [
        {name: c1, area: a1, waterPerDa: +safeNum(w1).toFixed(1), profitPerDa: +safeNum(r1).toFixed(1), season: season1, irrigationCurrentText: isOrchard ? 'Yağmurlama' : 'Karık / Yağmurlama'},
        ...(c2 ? [{name: c2, area: a2, waterPerDa: +safeNum(w2).toFixed(1), profitPerDa: +safeNum(r2).toFixed(1), season: season2, irrigationCurrentText: 'Yağışa bağlı (kuru)'}] : [])
      ];
      p.water_m3 = Math.round(a1*safeNum(w1) + a2*safeNum(w2));
      p.profit_tl = Math.round(a1*safeNum(r1) + a2*safeNum(r2));
      continue;
    }

    let c1 = null;
    let c2 = null;
    let w1 = 0, w2 = 0;
    let r1 = 0, r2 = 0;

    // --- Attempt 1: Use the user-defined pool based on season source ---
    // Senaryo-1: 15 ürün havuzu
    if((STATE.seasonSource||"s1") === "s1" && hasCatalog){
      const cand = S1_PRIMARY_15.filter(c=>catalog[c]);
      if(cand.length >= 2){
        const scored = cand.map((c, idx)=>{
          const dShare = getDistrictShare(p.district, c) || 0;
          return {c, idx, s: dShare};
        }).sort((a,b)=>(b.s-a.s) || (a.idx-b.idx));

        const h = _hashStr(p.id) % scored.length;
        const rotated = scored.slice(h).concat(scored.slice(0,h)).map(x=>x.c);

        c1 = rotated[0];
        const fam1 = CROP_FAMILY_S1[c1] || "";
        c2 = rotated.find(x=>x!==c1 && (CROP_FAMILY_S1[x]||"") !== fam1) || rotated.find(x=>x!==c1) || rotated[1];

        w1 = safeNum(catalog[c1]?.waterPerDa);
        w2 = safeNum(catalog[c2]?.waterPerDa);
        r1 = safeNum(catalog[c1]?.profitPerDa);
        r2 = safeNum(catalog[c2]?.profitPerDa);
      }
    }

    // Senaryo-2: mutabık kalınan havuz (meyve + tarla). Baseline "Mevcut" burada da
    // değişmeli; çünkü kullanıcı Senaryo-2'yi seçtiğinde mevcut desenin de bu havuzdan
    // üretildiğini görmek istiyor.
    if((STATE.seasonSource||"s1") === "s2" && hasCatalog){
      const cand = S2_PRIMARY_POOL.filter(c=>catalog[c]);
      if(cand.length >= 2){
        const scored = cand.map((c, idx)=>{
          const dShare = getDistrictShare(p.district, c) || 0;
          return {c, idx, s: dShare};
        }).sort((a,b)=>(b.s-a.s) || (a.idx-b.idx));

        const h = _hashStr(p.id) % scored.length;
        const rotated = scored.slice(h).concat(scored.slice(0,h)).map(x=>x.c);
        c1 = rotated[0];
        // Çok yıllık parsellerde tek ürün ağırlığı korunsun
        if(isPerennialCropName(c1)) c2 = null;
        else c2 = rotated[1] || null;

        const m1 = catalog[c1] || {waterPerDa:0, profitPerDa:0};
        const m2 = c2 ? (catalog[c2] || {waterPerDa:0, profitPerDa:0}) : null;
        w1 = safeNum(m1.waterPerDa); r1 = safeNum(m1.profitPerDa);
        if(m2){ w2 = safeNum(m2.waterPerDa); r2 = safeNum(m2.profitPerDa); }
      }
    }

    // --- Attempt 2 (fallback): derive top-2 from enhanced season rows for THIS parcel + selected year ---
    if(!c1 || !c2){
      const y = Number(STATE.selectedWaterYear || 2024);
      const mYear = STATE.candidatesByParcelYear?.get(y)?.get(p.id);
      const mAny  = STATE.candidatesByParcel?.get(p.id);
      const m = mYear || mAny;
      if(m && m.size){
        const arr = [];
        for(const [ck,a] of m.entries()){
          const aArea = safeNum(a.area);
          if(aArea<=0) continue;
          const wpd = safeNum(a.water)/aArea;
          const ppd = safeNum(a.profit)/aArea;
          arr.push({
            key: ck,
            name: a.name || ck,
            area: aArea,
            waterPerDa: wpd,
            profitPerDa: ppd,
          });
        }
        arr.sort((x,y)=>(y.area-x.area) || (y.profitPerDa-x.profitPerDa));
        if(arr.length>=1){
          const pick1 = arr[0];
          const pick2 = arr.find(z=>z.key!==pick1.key) || arr[1];
          if(pick1 && pick2){
            c1 = normCropName(pick1.name);
            c2 = normCropName(pick2.name);
            // Keep display/raw names from season rows
            const disp1 = pick1.name;
            const disp2 = pick2.name;
            w1 = pick1.waterPerDa; w2 = pick2.waterPerDa;
            r1 = pick1.profitPerDa; r2 = pick2.profitPerDa;
            // store raw names so UI shows nicer labels
            p._baselineRawNames = { [c1]: disp1, [c2]: disp2 };
          }
        }
      }
    }

    // If STILL nothing, keep a single-row baseline from parcel totals
    if(!c1 || !c2 || !(isFinite(w1) && isFinite(w2))){
      ensureBaselineCropCurrent(p);
      continue;
    }

    // Build exactly-2-crop baseline with 60/40 split
    const a1 = +(areaDa * 0.60).toFixed(1);
    const a2 = +(Math.max(0, areaDa - a1)).toFixed(1);

    // Prefer nicer raw labels when fallback path was used
    const n1 = (p._baselineRawNames && p._baselineRawNames[c1]) ? p._baselineRawNames[c1] : c1;
    const n2 = (p._baselineRawNames && p._baselineRawNames[c2]) ? p._baselineRawNames[c2] : c2;

    p.cropCurrent = [
      {name: n1, area: a1, waterPerDa: +safeNum(w1).toFixed(1), profitPerDa: +safeNum(r1).toFixed(1)},
      {name: n2, area: a2, waterPerDa: +safeNum(w2).toFixed(1), profitPerDa: +safeNum(r2).toFixed(1)},
    ].filter(x=>x.area>0);

    p.water_m3 = Math.round(a1*safeNum(w1) + a2*safeNum(w2));
    p.profit_tl = Math.round(a1*safeNum(r1) + a2*safeNum(r2));
  }
}

// --- Enhanced seasons source control (Senaryo-1 / Senaryo-2 / Birleşik) ---
function getSeasonRowsForSource(source){
  const raw = STATE._seasonRowsRaw || {s1:[], s2:[]};
  const src = (source || STATE.seasonSource || 's1');if(src === 's1') return raw.s1 || [];
  if(src === 's2') return raw.s2 || [];
  return (raw.s1 || []).concat(raw.s2 || []);
}

function rebuildSeasonDerivedIndexes(seasonRows){
  const rows = Array.isArray(seasonRows) ? seasonRows : [];

  // Store active rows
  STATE.seasonRows = rows;

  // Year-dependent index: year -> parcel -> crop aggregated stats.
  const candidatesByParcelYear = new Map();
  for(const r of rows){
    const y = +r.year;
    const pid = (r.parcel_id||r.parsel_id||"").trim();
    const cname = (r.crop||"").trim();
    if(!pid || !cname || !isFinite(y)) continue;
    const ck = normCropName(cname);
    const area = safeNum(r.area_da);
    const water = safeNum(r.water_m3_calib_gross || r.water_m3_calib_net || r.water_m3_et_gross || r.water_m3_et_net);
    const profit = safeNum(r.profit_tl);
    if(!candidatesByParcelYear.has(y)) candidatesByParcelYear.set(y, new Map());
    const byParcel = candidatesByParcelYear.get(y);
    if(!byParcel.has(pid)) byParcel.set(pid, new Map());
    const m = byParcel.get(pid);
    if(!m.has(ck)) m.set(ck, {name:cname, area:0, water:0, profit:0});
    const a = m.get(ck);
    a.area += area;
    a.water += water;
    a.profit += profit;
  }
  STATE.candidatesByParcelYear = candidatesByParcelYear;

  // Parcel-only index (fallback)
  const candidatesByParcel = new Map();
  for(const r of rows){
    const pid = (r.parcel_id||r.parsel_id||"").trim();
    const cname = (r.crop||"").trim();
    if(!pid || !cname) continue;
    const ck = normCropName(cname);
    const area = safeNum(r.area_da);
    const water = safeNum(r.water_m3_calib_gross || r.water_m3_calib_net || r.water_m3_et_gross || r.water_m3_et_net);
    const profit = safeNum(r.profit_tl);
    if(!candidatesByParcel.has(pid)) candidatesByParcel.set(pid, new Map());
    const m = candidatesByParcel.get(pid);
    if(!m.has(ck)) m.set(ck, {name:cname, area:0, water:0, profit:0});
    const a = m.get(ck);
    a.area += area;
    a.water += water;
    a.profit += profit;
  }
  STATE.candidatesByParcel = candidatesByParcel;

  // Crop-level "net water per da" and "plant density" derived from season rows
  // nir_mm_sum: 1 mm over 1 da (1000 m2) = 1 m3. So nir_mm_sum can be treated as net m3/da.
  const cropNetPerDaByYear = new Map(); // year -> cropNorm -> net_m3_per_da
  const cropPlantsPerDaByYear = new Map(); // year -> cropNorm -> plants_per_da
  for(const r of rows){
    const y = +r.year;
    const cname = (r.crop||"").trim();
    const ck = normCropName(cname);
    const area = safeNum(r.area_da);
    if(!isFinite(y) || !ck || area<=0) continue;
    const nirMm = safeNum(r.nir_mm_sum);
    const plants = safeNum(r.plants);
    if(!cropNetPerDaByYear.has(y)) cropNetPerDaByYear.set(y, new Map());
    if(!cropPlantsPerDaByYear.has(y)) cropPlantsPerDaByYear.set(y, new Map());
    const nmap = cropNetPerDaByYear.get(y);
    const pmap = cropPlantsPerDaByYear.get(y);
    // accumulate weighted
    if(!nmap.has(ck)) nmap.set(ck, {area:0, wsum:0});
    const na = nmap.get(ck);
    if(isFinite(nirMm) && nirMm>0){
      na.area += area;
      na.wsum += nirMm*area;
    }
    if(!pmap.has(ck)) pmap.set(ck, {area:0, psum:0});
    const pa = pmap.get(ck);
    if(isFinite(plants) && plants>0){
      pa.area += area;
      pa.psum += plants;
    }
  }
  // finalize to simple numbers
  for(const [y, m] of cropNetPerDaByYear.entries()){
    for(const [ck, a] of m.entries()){
      const v = (a.area>0) ? (a.wsum/a.area) : 0;
      m.set(ck, isFinite(v)?v:0);
    }
  }
  for(const [y, m] of cropPlantsPerDaByYear.entries()){
    for(const [ck, a] of m.entries()){
      const v = (a.area>0) ? (a.psum/a.area) : 0;
      m.set(ck, isFinite(v)?v:0);
    }
  }
  STATE.cropNetPerDaByYear = cropNetPerDaByYear;
  STATE.cropPlantsPerDaByYear = cropPlantsPerDaByYear;

  // --- Fill missing crop catalog entries from season aggregates ---
  // If a crop exists in the enhanced season dataset but is missing (or
  // ends up with zero water/profit) in the crop catalog, we derive
  // area-weighted averages from the season rows. This prevents "0 su"
  // artefacts and helps all algorithms run consistently.
  try{
    const catalog = STATE.cropCatalog || {};
    const acc = new Map(); // cropNorm -> {area, water, profit}
    for(const [pid, m] of candidatesByParcel.entries()){
      for(const [ck, a] of m.entries()){
        const area = safeNum(a.area);
        const water = safeNum(a.water);
        const profit = safeNum(a.profit);
        if(!ck || area<=0) continue;
        if(!acc.has(ck)) acc.set(ck, {area:0, water:0, profit:0});
        const t = acc.get(ck);
        t.area += area;
        t.water += water;
        t.profit += profit;
      }
    }
    for(const [ck, t] of acc.entries()){
      const area = safeNum(t.area);
      if(area<=0) continue;
      const wpd = safeNum(t.water) / area;
      const ppd = safeNum(t.profit) / area;
      const ex = catalog[ck];
      const exW = safeNum(ex?.waterPerDa);
      const exP = safeNum(ex?.profitPerDa);
      if(!ex || (!isFinite(exW) || exW<=0) || (!isFinite(exP) || exP===0)){
        catalog[ck] = {
          ...(ex||{}),
          rawName: (ex?.rawName || ck),
          waterPerDa: isFinite(exW) && exW>0 ? exW : (isFinite(wpd) ? wpd : 0),
          profitPerDa: isFinite(exP) && exP!==0 ? exP : (isFinite(ppd) ? ppd : 0),
          category: ex?.category || '',
          type: ex?.type || cropTypeFromCategory(ex?.category||'') || 'tarla'
        };
      }
    }
    STATE.cropCatalog = catalog;
  }catch(_){/*no-op*/}
}


function getAvailableWaterYearsFromHydrology(){
  // Prefer baraj/proj series years for 'Su yılı' selector (2000-2025 observed, 2025-2050 projections)
  const ys = new Set();
  const b = Array.isArray(STATE.barajSeries) ? STATE.barajSeries : [];
  for(const r of b){
    const y = Number(r.yil);
    if(Number.isFinite(y)) ys.add(y);
  }
  const p = Array.isArray(STATE.projSeries) ? STATE.projSeries : [];
  for(const r of p){
    const y = Number(r.yil);
    if(Number.isFinite(y)) ys.add(y);
  }
  const years = Array.from(ys).sort((a,b)=>a-b);
  // If nothing loaded yet, fallback broad range
  if(!years.length){
    const out=[];
    for(let y=2000;y<=2050;y++) out.push(y);
    return out;
  }
  // Ensure continuity: fill gaps between min and max for nicer UX
  const minY = Math.min(...years);
  const maxY = Math.max(...years);
  const out=[];
  for(let y=minY;y<=maxY;y++) out.push(y);
  return out;
}

function getAvailableYearsFromActiveSeasons(){
  const rows = Array.isArray(STATE.seasonRows) ? STATE.seasonRows : [];
  const ys = new Set();
  for(const r of rows){
    const y = +r.year;
    if(isFinite(y)) ys.add(y);
  }
  return Array.from(ys).sort((a,b)=>a-b);
}

function refreshWaterYearOptionsFromActiveSeasons(){
  // NOTE: Despite the name, this populates the 'Su yılı' selector.
  // It must be driven by hydrology series (baraj/proj) so that selecting 2000–2025 works.
  const yearSel = document.getElementById('waterYear');
  if(!yearSel) return;

  let years = getAvailableWaterYearsFromHydrology();

  // Keep current selection if possible
  const cur = Number(STATE.selectedWaterYear || years[years.length-1]);
  if(!years.includes(cur)) STATE.selectedWaterYear = years[years.length-1];

  yearSel.innerHTML = '';
  for(const y of years){
    const opt = document.createElement('option');
    opt.value = String(y);
    opt.textContent = String(y);
    if(Number(y) === Number(STATE.selectedWaterYear)) opt.selected = true;
    yearSel.appendChild(opt);
  }
}

function initSeasonSourceSelector(){
  const sel = document.getElementById('seasonSourceSel');
  if(!sel) return;
  // default
  sel.value = STATE.seasonSource || 's1';
  sel.addEventListener('change', ()=>{
    STATE.seasonSource = sel.value;
    const rows = getSeasonRowsForSource(STATE.seasonSource);
    rebuildSeasonDerivedIndexes(rows);
    refreshWaterYearOptionsFromActiveSeasons();
    applyYearBaselinesFromSeasons();
    refreshScenarioBaselineCurrent();
    // Clear caches so recommendations reflect new season dataset
    for(const k of Object.keys(basinPlanCache)) delete basinPlanCache[k];
    for(const k of Object.keys(optimizationCache)) delete optimizationCache[k];
    applyWaterScenarioFromUI(true);
    // update UI
    refreshGlobalSummary();
    refreshCharts();
    refreshMap();
    // NOTE: optional chaining on an undeclared identifier throws a ReferenceError.
    // We always define refreshParcelInfoCards() (see below) so we can call it safely.
    refreshParcelInfoCards();
    renderActiveFiles();
  });
}

async function loadEnhancedDataset(){
  // Load enhanced CSVs (NO embedded/demo data)
  // Parcels are preferably sourced from Flask backend (/api/parcels).
  // If the page is served without the backend (e.g., python -m http.server / Live Server),
  // we fall back to building parcels from CSV files so the UI is not blank.
  let backendParcels = [];
  try{
    const pjson = await fetchJson('/api/parcels');
    backendParcels = (pjson && pjson.parcels) ? pjson.parcels : [];
  }catch(e){
    backendParcels = [];
  }

  if(backendParcels.length){
    // Ensure baseline crop plan exists for "Mevcut" scenario computations
    backendParcels.forEach(ensureBaselineCropCurrent);
    parcelData = backendParcels;
    STATE.parcels = backendParcels;

    // Basin-wide "Mevcut" totals should come from the backend's parcel metadata
    // (water_m3 / profit_tl) so we don't accidentally show only a single parcel
    // in the 15-parcel summary box.
    try{
      const w = backendParcels.reduce((acc,p)=> acc + (Number(p.water_m3)||0), 0);
      const k = backendParcels.reduce((acc,p)=> acc + (Number(p.profit_tl)||0), 0);
      STATE.backendBaselineTotals = {
        water_m3: w,
        profit_tl: k,
        water_eff: (w>0) ? (k/w) : 0,
      };
    }catch(e){
      STATE.backendBaselineTotals = null;
    }
    if(!selectedParcelId && parcelData.length) selectedParcelId = parcelData[0].id;
  }

  // IMPORTANT: If any single CSV fetch fails, Promise.all would reject and the whole UI would look blank.
  // We use allSettled so we can still boot with whatever data is available and show clear diagnostics.
  const settled = await Promise.allSettled([
    fetchText(DATA_FILES.enhanced.parcelAssumptionsCsv),
    fetchText(DATA_FILES.enhanced.cropParamsCsv),
    fetchText(DATA_FILES.enhanced.senaryo1SeasonsCsv),
    fetchText(DATA_FILES.enhanced.senaryo2SeasonsCsv),
    fetchText(DATA_FILES.enhanced.climateMonthlyCsv),
    fetchText(DATA_FILES.parcelsCsv),
  ]);

  const getSettled = (i)=> (settled[i].status==='fulfilled') ? settled[i].value : null;
  const parcelsText = getSettled(0);
  const cropParamsText = getSettled(1);
  const s1Text = getSettled(2);
  const s2Text = getSettled(3);
  const climateText = getSettled(4);
  const legacyParcelsText = getSettled(5);

  // show diagnostics in UI (so users don't have to open DevTools)
  try{
    const diag = [];
    const labels = [
      ['parcel_assumptions.csv', DATA_FILES.enhanced.parcelAssumptionsCsv],
      ['crop_params_assumed.csv', DATA_FILES.enhanced.cropParamsCsv],
      ['senaryo1_backend_seasons.csv', DATA_FILES.enhanced.senaryo1SeasonsCsv],
      ['senaryo2_backend_seasons.csv', DATA_FILES.enhanced.senaryo2SeasonsCsv],
      ['monthly_climate_all_parcels.csv', DATA_FILES.enhanced.climateMonthlyCsv],
      ['parsel_su_kar_ozet.csv (legacy)', DATA_FILES.parcelsCsv],
    ];
    settled.forEach((s, idx)=>{
      if(s.status==='rejected'){
        const [nm,url] = labels[idx];
        diag.push(`❌ ${nm} okunamadı (${url})`);
      }
    });
    const diagBox = document.getElementById('activeFiles');
    if(diagBox && diag.length){
      diagBox.innerHTML = `<div style="color:#a61e4d; font-size:12px; line-height:1.35;">${diag.map(x=>`<div>${x}</div>`).join('')}</div>`;
    }
  }catch(_e){ /* no-op */ }

  const parcelRows = parcelsText ? parseCsv(parcelsText) : [];
  const cropParamRows = cropParamsText ? parseCsv(cropParamsText) : [];
  const s1Rows = s1Text ? parseCsv(s1Text) : [];
  const s2Rows = s2Text ? parseCsv(s2Text) : [];

  // Fallback: if backend is not available (or returned 0 parcels), build parcels from CSVs.
  if(!Array.isArray(parcelData) || !parcelData.length){
    const legacyRows = legacyParcelsText ? parseCsv(legacyParcelsText) : [];
    const legacyById = new Map();
    for(const r of legacyRows){
      const pid = String(r.parsel_id||r.parcel_id||r.id||'').trim();
      if(!pid) continue;
      legacyById.set(pid, r);
    }

    const parcels = [];
    for(const r of parcelRows){
      const pid = String(r.parcel_id||r.parsel_id||r.id||'').trim();
      if(!pid) continue;
      const leg = legacyById.get(pid) || {};
      const area_da = safeNum(r.area_da || leg.alan_da || leg.area_da);
      const lat = safeNum(r.lat_deg || r.lat || leg.lat);
      const lon = safeNum(r.lon_deg || r.lon || leg.lon);
      const water_m3 = safeNum(leg.mevcut_su_m3 || leg.water_m3);
      const profit_tl = safeNum(leg.mevcut_kar_tl || leg.profit_tl);
      const name = String(r.name||leg.name||pid);
      const village = String(r.village||leg.koy||leg.village||'').trim();
      const district = String(r.district||leg.ilce||leg.district||'').trim();
      parcels.push({
        id: pid,
        name,
        village,
        district,
        area_da,
        lat,
        lon,
        water_m3,
        profit_tl,
        soil: { class: String(r.land_capability_class||''), texture: String(r.soil_group||''), erosion: String(r.erosion_risk||'') }
      });
    }

    // Ultimate fallback: if even parcel_assumptions.csv couldn't be read (or was empty),
    // don't let the whole UI look blank. Create 15 placeholder parcels so the user can
    // still run the app and see diagnostics on-screen.
    if(!parcels.length){
      const baseLat = 37.97, baseLon = 34.68;
      for(let i=1;i<=15;i++){
        const pid = `P${i}`;
        parcels.push({
          id: pid,
          name: `${pid} (geçici)` ,
          village: '',
          district: '',
          area_da: 5,
          lat: baseLat + (Math.floor((i-1)/5))*0.01,
          lon: baseLon + ((i-1)%5)*0.01,
          water_m3: 0,
          profit_tl: 0,
          soil: {class:'', texture:'', erosion:''},
          cropCurrent: []
        });
      }
    }
    parcels.forEach(ensureBaselineCropCurrent);
    parcelData = parcels;
    STATE.parcels = parcels;
    if(!selectedParcelId && parcelData.length) selectedParcelId = parcelData[0].id;
  }

  // Store raw season rows separately so the user can switch between Senaryo-1 / Senaryo-2 / Birleşik
  STATE._seasonRowsRaw = { s1: (s1Rows||[]), s2: (s2Rows||[]) };
  // Build indexes from the currently selected source
  rebuildSeasonDerivedIndexes(getSeasonRowsForSource(STATE.seasonSource));
  // Ensure selector exists and reflects STATE.seasonSource
  initSeasonSourceSelector();

  // Use active season rows from selected source
  const seasonRows = STATE.seasonRows;


  // Crop catalog (derived from enhanced season options + crop params)
  const cpByName = new Map();
  for(const r of cropParamRows){
    const name = (r.crop||r.urun||r.urun_adi||"").trim();
    if(!name) continue;
    cpByName.set(normCropName(name), r);
  }

  const cropAgg = new Map();
  for(const r of seasonRows){
    const cropName = (r.crop||"").trim();
    if(!cropName) continue;
    const k = normCropName(cropName);
    const area = safeNum(r.area_da);
    const water = safeNum(r.water_m3_calib_gross || r.water_m3_calib_net || r.water_m3_et_gross || r.water_m3_et_net);
    const profit = safeNum(r.profit_tl);
    if(!cropAgg.has(k)) cropAgg.set(k, {name: cropName, area:0, water:0, profit:0});
    const a = cropAgg.get(k);
    a.area += area;
    a.water += water;
    a.profit += profit;
  }

  const catalog = {};
  for(const [k,a] of cropAgg.entries()){
    const area = a.area || 1;
    const waterPerDa = a.water / area;
    const profitPerDa = a.profit / area;
    const cp = cpByName.get(k);
    catalog[k] = {
      name: a.name,
      waterPerDa,
      profitPerDa,
      Kc_ini: cp ? safeNum(cp.kc_ini) : NaN,
      Kc_mid: cp ? safeNum(cp.kc_mid) : NaN,
      Kc_end: cp ? safeNum(cp.kc_end) : NaN,
      Lini: cp ? safeNum(cp.p_ini) : NaN,
      Ldev: cp ? safeNum(cp.p_dev) : NaN,
      Lmid: cp ? safeNum(cp.p_mid) : NaN,
      Lend: cp ? safeNum(cp.p_late) : NaN,
      sow: ""
    };
  }
  STATE.cropCatalog = catalog;

  // Climate summary per parcel (optional)
  let climateByParcel = new Map();
  if(climateText){
    const climateRows = parseCsv(climateText);
    // Tam monthly iklim serisini sakla: Gelişmiş ayarlarda tarih aralığına göre
    // (offline) ET0/yağış toplamını hesaplamak için kullanılır.
    STATE.climateMonthlyRows = Array.isArray(climateRows) ? climateRows : [];
    const years = climateRows.map(r=>monthKeyToYear(r.month)).filter(y=>isFinite(y));
    const lastYear = years.length ? Math.max(...years) : NaN;
    const minYear = isFinite(lastYear) ? (lastYear - 4) : NaN;
    const filtered = isFinite(lastYear) ? climateRows.filter(r=>{
      const y = monthKeyToYear(r.month);
      return y>=minYear && y<=lastYear;
    }) : [];
    const grp = groupBy(filtered, r=>(r.parcel_id||r.parsel_id||"").trim());
    for(const [pid,rows] of grp.entries()){
      if(!pid) continue;
      // monthly_climate_all_parcels.csv uses precip_mm + et0_mm (some older variants use rain_mm/eto_mm)
      const rainSum = rows.reduce((s,r)=>s+safeNum(r.rain_mm ?? r.precip_mm ?? r.precipitation_mm ?? r.precip),0);
      const etoSum  = rows.reduce((s,r)=>s+safeNum(r.eto_mm ?? r.et0_mm ?? r.et0),0);
      // We average over ~5 years window above (minYear..lastYear), so convert totals to per-year.
      const rain = rainSum / 5;
      const eto  = etoSum / 5;
      const tavg = rows.reduce((s,r)=>s+safeNum(r.tavg_c ?? r.tavg ?? r.t_mean_c),0) / (rows.length||1);
      climateByParcel.set(pid, {rain_mm: Math.round(rain), eto_mm: Math.round(eto), t_avg: +tavg.toFixed(1)});
    }
  }

  const byParcel = groupBy(seasonRows, r=>(r.parcel_id||r.parsel_id||"").trim());
  const built = [];
  for(const pr of parcelRows){
    const id = (pr.parcel_id||pr.parsel_id||pr.id||"").trim();
    if(!id) continue;

    const rows = byParcel.get(id) || [];
    const area_da = rows.length ? Math.max(...rows.map(r=>safeNum(r.area_da)).filter(x=>x>0)) : safeNum(pr.area_da);
    const avgWater = rows.length ? (rows.reduce((s,r)=>s+safeNum(r.water_m3_calib_gross||r.water_m3_et_gross),0) / rows.length) : 0;
    const avgProfit = rows.length ? (rows.reduce((s,r)=>s+safeNum(r.profit_tl),0) / rows.length) : 0;

    const byCrop = groupBy(rows, r=>(r.crop||"").trim());
    const cropList = [];
    for(const [cname,rr] of byCrop.entries()){
      if(!cname) continue;
      const a = rr.reduce((s,r)=>s+safeNum(r.area_da),0) || 1;
      const p = rr.reduce((s,r)=>s+safeNum(r.profit_tl),0);
      const w = rr.reduce((s,r)=>s+safeNum(r.water_m3_calib_gross||r.water_m3_et_gross),0);
      cropList.push({name:cname, area: Math.round(a*10)/10, waterPerDa: w/a, profitPerDa: p/a});
    }
    // IMPORTANT: Do NOT derive "Mevcut Ürün Deseni" from season rows at load time.
    // We will generate a farmer-facing baseline (exactly 2 crops) later,
    // based on the selected scenario (Senaryo-1/Senaryo-2) and Niğde patterns.
    const cropCurrent = [];

    built.push({
      id,
      name: `${id} – ${(pr.soil_unit_code||pr.toprak_kodu||"").trim()}${(pr.village||pr.koy)?` (${(pr.village||pr.koy).trim()})`:""}`,
      village: (pr.village||pr.koy||"").trim(),
      district: (pr.district||pr.ilce||"MERKEZ").trim(),
      area_da: +(+area_da || safeNum(pr.area_da) || 0).toFixed(1),
      water_m3: Math.round(avgWater),
      profit_tl: Math.round(avgProfit),
      soil: { class: (pr.land_capability_class ? `${pr.land_capability_class}. sınıf` : (pr.soil_group||"")).trim(),
              texture: (pr.soil_group||"").trim(),
              erosion: "" },
      climate: climateByParcel.get(id) || {rain_mm: NaN, eto_mm: NaN, t_avg: NaN},
      cropCurrent
    });
  }

  parcelData = built;
  STATE.totalAreaAllParcels = parcelData.reduce((a,p)=>a+(+p.area_da||0),0);
}

// --- Su bütçesi zaman serisi (baraj + projeksiyon) ---
async function loadWaterBudgetSeries(){
  // These CSVs are lightweight and shipped with the project.
  // They are required for the "Su bütçesi (2000–2050)" tab.
  try{
    const [barajText, projText] = await Promise.all([
      fetchText(DATA_FILES.barajCsv),
      fetchText(DATA_FILES.projCsv),
    ]);
    const barajRows = parseCsv(barajText);
    const projRows  = parseCsv(projText);

    // IMPORTANT: Downstream chart code expects keys {yil, doluluk} and {yil, senaryo, doluluk}.
    // Keep the state shape consistent to avoid "blank charts".
    STATE.barajSeries = barajRows.map(r=>({
      yil: safeNum(r.yil ?? r.year),
      // Keep 'doluluk' for backward-compatible charts (interpreted as stress/index 0–100)
      doluluk: safeNum(r.doluluk_endeksi_0_100 ?? r.doluluk_endeksi_0_10 ?? r.doluluk ?? r.storage_index),
      // New: average and minimum fullness (%) if provided by updated table
      ortalama_pct: safeNum(r.ortalama_doluluk_pct ?? r.ortalama_pct ?? r.avg_fullness_pct),
      min_pct: safeNum(r.min_doluluk_pct_tahmini ?? r.minimum_doluluk_pct ?? r.min_pct)
    }))
    .filter(x=>isFinite(x.yil) && isFinite(x.doluluk))
    .sort((a,b)=>a.yil-b.yil);

    STATE.projSeries = projRows.map(r=>({
      yil: safeNum(r.yil ?? r.year),
      senaryo: normalizeScenarioKey(r.senaryo ?? r.scenario ?? ''),
      // Some datasets use 0–10 or 0–100 indexes. We keep values as-is and let the chart scale decide.
      doluluk: safeNum(r.doluluk_endeksi_0_100 ?? r.doluluk_endeksi_0_10 ?? r.doluluk ?? r.storage_index)
    }))
    .filter(x=>isFinite(x.yil) && x.senaryo && isFinite(x.doluluk))
    .sort((a,b)=>a.yil-b.yil);

// If projection CSV contains only one scenario (often just 'mevcut'),
// auto-generate the missing two scenarios so the chart always shows 3 curves.
try{
  const needed = ["mevcut","iyi_adaptasyon","kotu_kuraklik"];
  const have = new Set((STATE.projSeries||[]).map(x=>x.senaryo));
  const hasBase = have.has("mevcut");
  if(hasBase && needed.some(k=>!have.has(k))){
    const base = (STATE.projSeries||[]).filter(x=>x.senaryo==="mevcut")
      .filter(x=>isFinite(x.yil) && isFinite(x.doluluk))
      .sort((a,b)=>a.yil-b.yil);

    if(base.length >= 2){
      const first = base[0].doluluk;
      const last = base[base.length-1].doluluk;
      const n = base.length;
      const slope = (last-first)/Math.max(1,(n-1)); // per-year change (usually negative)
      const mag = Math.abs(slope);
      const clamp = (v)=>Math.max(0, Math.min(100, v));

      const derived = [];
      for(let i=0;i<base.length;i++){
        const y = base[i].yil;
        const v = base[i].doluluk;
        // "İyi adaptasyon": slower decline + small uplift
        const vGood = clamp(v + 3 + mag*0.4*(i+1));
        // "Kötü kuraklık": faster decline + small penalty
        const vBad  = clamp(v - 3 - mag*0.4*(i+1));
        derived.push({yil:y, senaryo:"iyi_adaptasyon", doluluk:+vGood.toFixed(2)});
        derived.push({yil:y, senaryo:"kotu_kuraklik", doluluk:+vBad.toFixed(2)});
      }

      // Merge (keep existing rows if already present)
      const key = (x)=>`${x.yil}__${x.senaryo}`;
      const existing = new Set((STATE.projSeries||[]).map(key));
      for(const d of derived){
        if(!existing.has(key(d))) STATE.projSeries.push(d);
      }
      STATE.projSeries.sort((a,b)=>a.yil-b.yil);
    }
  }
}catch(_e){ /* ignore */ }
  }catch(e){
    console.warn('Su bütçesi serileri yüklenemedi:', e);
    STATE.barajSeries = [];
    STATE.projSeries = [];
  }
}


const STATE = {
  cropCatalog: null,            // {CROP:{waterPerDa, profitPerDa, ...}}
  barajSeries: null,            // [{yil, doluluk_endeksi_0_100, ...}]
  projSeries: null,
  barajRawSeries: null,        // raw CSV (;) ile gelen seri
  projRawSeries: null,         // raw CSV (;) ile gelen seri
  droughtRisk: 0,              // 0-1
  sustainabilityIndex: null,   // 0-1 (inflow/outflow)
             // [{yil, senaryo, doluluk_endeksi_0_100}]
  villagePatterns: null,        // {VILLAGE:{top_crops:[{crop,share}]}}
  districtPatterns: null,       // {DISTRICT:{top_crops:[{crop,share}]}}
  demoOutputs: { ga:null, abc:null, aco:null },
  parcels: [],               // [{id,name,area_da,water_m3,profit_tl,lat,lon,soil,...}]
  maxCapacityM3: 3_000_000,     // 100 endeks = bu kadar m³ (demo ölçeği)
  availableWaterM3: null,
  waterIndex: null,
  selectedWaterYear: 2024,
  selectedProjScenario: "kotu_kuraklik",
  // Senaryo-2 ürün havuzu (mutabık kalınan liste)
  S2_PRIMARY_POOL: S2_PRIMARY_POOL,
  // Which enhanced season dataset to use for baselines + candidate crops.
  // seasonSource: 's1' (Senaryo-1) veya 's2' (Senaryo-2)
  seasonSource: "s1",
  // Use the season tables to build a consistent "Mevcut" baseline (water/profit)
  // so scenario comparisons are apples-to-apples.
  useOfficialBaseline: true,
  totalAreaAllParcels: null,
  irrigEfficiency: 0.62,       // demo: vahşi/karma sulama varsayımı
};

// Water budget tightening per scenario (front-end hint for backend).
// NOTE: Even if reservoir budget is large, we want "Su tasarruf" to actually
// constrain the search so recommended patterns use less water.
function budgetRatioForScenarioKey(scenarioKey){
  const s = String(scenarioKey||'').toLowerCase();
  if(s === 'su_tasarruf' || s === 'water_saving' || s === 'tasarruf') return 0.70; // ~30% tighter
  if(s === 'maks_kar' || s === 'max_profit') return 1.00;
  // balanced / recommended
  return 0.90;
}

// --- Farmer-facing "bitki & yöntem" su hesabı yardımcıları ---
// Bitki yoğunluğu (bitki sayısı/da). Veri yoksa tipik sıra aralığına göre yaklaşık değerler.
const DEFAULT_PLANTS_PER_DA = {
  "PATATES": 4800,
  "SILAJLIK MISIR": 9500,
  "YONCA (YESILOT)": 0,
  "BUGDAY (DANE)": 450000,
  "ARPA (DANE)": 350000,
  "SEKER PANCARI": 11000,
  "CAVDAR (DANE)": 300000,
  "SALCALIK DOMATES": 3000,
  "SOFRALIK DOMATES": 3000,
  "LAHANA (BEYAZ)": 2800,
  "KABAK (CEREZLIK)": 500,
  "FASULYE (TAZE)": 20000,
  "SOGAN (KURU)": 50000,
  "KAVUN": 500,
  "SALCALIK BIBER": 4800,

  // Çok yıllıklar (ağaç/bağ)
  "ELMA": 30,
  "ARMUT": 30,
  "KIRAZ": 30,
  "VISNE": 30,
  "SEFTALI": 35,
  "NEKTARIN": 35,
  "KAYISI": 35,
  "ERIK": 35,
  "CEVIZ": 20,
  "BAG (UZUM)": 130
};

// Varsayılan "mevcut" sulama yöntemi (ürün bazında). Bu harita sahaya göre özelleştirilebilir.
const DEFAULT_METHOD_BY_CROP = {
  // Tarlalar (mevcut yaygın): yüzey/karık
  "BUGDAY (DANE)": "surface_furrow",
  "ARPA (DANE)": "surface_furrow",
  "CAVDAR (DANE)": "surface_furrow",
  "PATATES": "surface_furrow",
  "SILAJLIK MISIR": "surface_furrow",
  "SEKER PANCARI": "surface_furrow",
  "YONCA (YESILOT)": "surface_furrow",

  // Sebzeler
  "SALCALIK DOMATES": "surface_furrow",
  "SOFRALIK DOMATES": "surface_furrow",
  "LAHANA (BEYAZ)": "surface_furrow",
  "KABAK (CEREZLIK)": "surface_furrow",
  "FASULYE (TAZE)": "surface_furrow",
  "SOGAN (KURU)": "surface_furrow",
  "KAVUN": "surface_furrow",
  "SALCALIK BIBER": "surface_furrow",

  // Çok yıllıklar (mevcut: tava/havuz vb.)
  "ELMA": "surface_furrow",
  "ARMUT": "surface_furrow",
  "KIRAZ": "surface_furrow",
  "VISNE": "surface_furrow",
  "SEFTALI": "surface_furrow",
  "NEKTARIN": "surface_furrow",
  "KAYISI": "surface_furrow",
  "ERIK": "surface_furrow",
  "CEVIZ": "surface_furrow",
  "BAG (UZUM)": "surface_furrow"
};

// Önerilen sulama yöntemi (ürün bazında). Çok yıllıklarda (meyve bahçesi) genelde damla önerilir.
const RECOMMENDED_METHOD_BY_CROP = {
  // Tahıllar: yağmurlama (veya gelişmiş yüzey)
  "BUGDAY (DANE)": "sprinkler",
  "ARPA (DANE)": "sprinkler",
  "CAVDAR (DANE)": "sprinkler",

  // Sıra arası bitkiler: damla
  "PATATES": "drip",
  "SILAJLIK MISIR": "drip",
  "SEKER PANCARI": "drip",
  "YONCA (YESILOT)": "sprinkler",
  "SALCALIK DOMATES": "drip",
  "SOFRALIK DOMATES": "drip",
  "LAHANA (BEYAZ)": "drip",
  "KABAK (CEREZLIK)": "drip",
  "FASULYE (TAZE)": "drip",
  "SOGAN (KURU)": "drip",
  "KAVUN": "drip",
  "SALCALIK BIBER": "drip",

  // Çok yıllıklar: damla/mikro
  "ELMA": "drip",
  "ARMUT": "drip",
  "KIRAZ": "drip",
  "VISNE": "drip",
  "SEFTALI": "drip",
  "NEKTARIN": "drip",
  "KAYISI": "drip",
  "ERIK": "drip",
  "CEVIZ": "drip",
  "BAG (UZUM)": "drip"
};

function normCropKey(name){
  return String(name||"")
    .toUpperCase()
    .replace(/İ/g,"I")
    .replace(/Ğ/g,"G")
    .replace(/Ü/g,"U")
    .replace(/Ş/g,"S")
    .replace(/Ö/g,"O")
    .replace(/Ç/g,"C")
    .replace(/\s+/g," ")
    .trim();
}

async function loadMetaAndScenarioRules(){
  try{
    const r = await fetch("/api/meta");
    const meta = await r.json();
    // Senaryo-1 rules
    const rules = meta?.scenario1_rules || {};
    // Primary crops are top-level keys excluding _derived
    S1_PRIMARY_CROPS = Object.keys(rules).filter(k=>k && k !== "_derived");
    // Pairing map for UI/optimizer
    for(const k of Object.keys(S1_PAIRING)) delete S1_PAIRING[k];
    for(const p of S1_PRIMARY_CROPS){
      const v = rules[p] || {};
      const secOpts = v.secondary_options || [];
      // choose first as default; optimizer can override
      const sec = secOpts.length ? secOpts[0] : null;
      S1_PAIRING[p] = {
        season1: v.season1 || "—",
        irr1: v.irrigation1_current || "—",
        secondary: sec || "—",
        season2: v.season2 || "—",
        irr2: v.irrigation2_current || "—",
        secondary_options: secOpts
      };
    }
    // Irrigation suggestion map
    STATE.cropIrrigationMap = meta?.crop_irrigation_map || {};
    return meta;
  }catch(e){
    console.warn("Meta/rules load failed:", e);
    return null;
  }
}


// Sayı formatlama (tr-TR)
function formatNum(v, digits=0){
  const n = Number(v);
  if(!isFinite(n)) return '0';
  return new Intl.NumberFormat('tr-TR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  }).format(n);
}


function getSeasonRowsForSource(source){
  const src = (source || "s1").toLowerCase();
  const raw = STATE._seasonRowsRaw || {};
  if(src === "s1") return Array.isArray(raw.s1) ? raw.s1 : [];
  if(src === "s2") return Array.isArray(raw.s2) ? raw.s2 : [];
  // (both removed)
  const a = Array.isArray(raw.s1) ? raw.s1 : [];
  const b = Array.isArray(raw.s2) ? raw.s2 : [];
  return a.concat(b);
}

function buildSeasonIndexesFromRows(seasonRows){
  // Build year->parcel->crop aggregates and parcel->crop aggregates
  const candidatesByParcelYear = new Map();
  const candidatesByParcel = new Map();

  for(const r of (seasonRows||[])){
    const y = +r.year;
    const pid = (r.parcel_id||r.parsel_id||"").trim();
    const cname = (r.crop||"").trim();
    if(!pid || !cname) continue;
    const ck = normCropName(cname);
    const area = safeNum(r.area_da);
    const water = safeNum(r.water_m3_calib_gross || r.water_m3_calib_net || r.water_m3_et_gross || r.water_m3_et_net);
    const profit = safeNum(r.profit_tl);

    // year-aware
    if(isFinite(y)){
      if(!candidatesByParcelYear.has(y)) candidatesByParcelYear.set(y, new Map());
      const byParcel = candidatesByParcelYear.get(y);
      if(!byParcel.has(pid)) byParcel.set(pid, new Map());
      const m = byParcel.get(pid);
      if(!m.has(ck)) m.set(ck, {name:cname, area:0, water:0, profit:0});
      const a = m.get(ck);
      a.area += area;
      a.water += water;
      a.profit += profit;
    }

    // parcel-aware (all years)
    if(!candidatesByParcel.has(pid)) candidatesByParcel.set(pid, new Map());
    const mp = candidatesByParcel.get(pid);
    if(!mp.has(ck)) mp.set(ck, {name:cname, area:0, water:0, profit:0});
    const ap = mp.get(ck);
    ap.area += area;
    ap.water += water;
    ap.profit += profit;
  }

  STATE.candidatesByParcelYear = candidatesByParcelYear;
  STATE.candidatesByParcel = candidatesByParcel;
}

function availableYearsFromSeasonRows(seasonRows){
  const ys = new Set();
  for(const r of (seasonRows||[])){
    const y = +r.year;
    if(isFinite(y)) ys.add(y);
  }
  return Array.from(ys).sort((a,b)=>a-b);
}

function setSeasonSource(source){
  const src = (source || "s1").toLowerCase();
  STATE.seasonSource = (src === "s1" || src === "s2") ? src : "s1";
  STATE.seasonRows = getSeasonRowsForSource(STATE.seasonSource);
  buildSeasonIndexesFromRows(STATE.seasonRows);
  applyYearBaselinesFromSeasons();
  // Clear caches so results can change immediately
  try{ for(const k of Object.keys(basinPlanCache)) delete basinPlanCache[k]; }catch(_){ }
  try{ for(const k of Object.keys(optimizationCache)) delete optimizationCache[k]; }catch(_){ }
}

function normCropName(s){
  return (s||"")
    .toString()
    .toUpperCase()
    .trim()
    .replace(/\s+/g," ")
    .replace(/\(.*?\)/g,"")
    .trim()
    .replaceAll("İ","I").replaceAll("Ş","S").replaceAll("Ğ","G").replaceAll("Ü","U").replaceAll("Ö","O").replaceAll("Ç","C");
}
// =========================
// Excel türevi desenleri normalize et (top_crops formatına çevir) ve birleştir
// =========================
function normalizePatternObject(obj){
  if(!obj || typeof obj !== "object") return {};
  const out = {};
  for(const [key,val] of Object.entries(obj)){
    if(!val) continue;

    // 1) Zaten top_crops formatındaysa
    if(val.top_crops && Array.isArray(val.top_crops)){
      out[normCropName(key)] = {
        top_crops: val.top_crops
          .map(x=>({crop:normCropName(x.crop||x.name||""), share: Number(x.share||x.weight||0)}))
          .filter(x=>x.crop)
      };
      continue;
    }

    // 2) Excel türevi format: {tarla:[{crop,area_dekar}], sebze:[...], meyve:[...]}
    if(typeof val === "object"){
      const flat = [];
      for(const arr of Object.values(val)){
        if(Array.isArray(arr)){
          for(const it of arr){
            if(!it) continue;
            const crop = normCropName(it.crop || it.name || "");
            const area = Number(it.area_dekar ?? it.area ?? it.alan_dekar ?? 0);
            if(crop && area > 0) flat.push({crop, area});
          }
        }
      }

      const merged = {};
      for(const x of flat){
        merged[x.crop] = (merged[x.crop]||0) + x.area;
      }
      const total = Object.values(merged).reduce((s,a)=>s+a,0) || 1;

      const top = Object.entries(merged)
        .map(([crop,area])=>({crop, share: area/total}))
        .sort((a,b)=>b.share-a.share)
        .slice(0,12);

      out[normCropName(key)] = { top_crops: top, meta:{source:"excel_derived"} };
    }
  }
  return out;
}

function mergePatterns(baseObj, excelObj){
  const base = normalizePatternObject(baseObj);
  const excel = normalizePatternObject(excelObj);
  const merged = {...base};

  for(const [k,v] of Object.entries(excel)){
    if(!merged[k]){
      merged[k]=v;
      continue;
    }

    const m = {};
    const add = (arr, w) => {
      (arr||[]).forEach(x=>{
        if(!x || !x.crop) return;
        m[x.crop] = (m[x.crop]||0) + (Number(x.share)||0)*w;
      });
    };

    add(merged[k].top_crops, 0.6);
    add(v.top_crops, 0.4);

    const tot = Object.values(m).reduce((s,a)=>s+a,0) || 1;
    merged[k].top_crops = Object.entries(m)
      .map(([crop,share])=>({crop, share: share/tot}))
      .sort((a,b)=>b.share-a.share)
      .slice(0,12);

    merged[k].meta = {source:"merged_base+excel"};
  }

  return merged;
}




function loadEmbeddedDemo(){
  // Minimal demo data so the UI is never blank (works even if fetch fails).
  try{
    STATE.parcels = [
      {id:"P1", name:"P1", area_da:5.8, water_m3:2294, profit_tl:27989, lat:38.05, lon:34.68, district:"MERKEZ", village:"Yeşilburç", soil:{class:"I", texture:"Bs", erosion:""}},
      {id:"P3", name:"P3", area_da:6.2, water_m3:2410, profit_tl:30110, lat:38.045, lon:34.70, district:"MERKEZ", village:"Yeşilburç", soil:{class:"II", texture:"Bs", erosion:""}},
      {id:"P5", name:"P5", area_da:4.9, water_m3:1900, profit_tl:25800, lat:38.06, lon:34.73, district:"MERKEZ", village:"Yeşilburç", soil:{class:"II", texture:"Bs", erosion:""}}
    ];
    // Simple drought history (index 0-100) + derived indicators.
    const years = [];
    for(let y=2000;y<=2025;y++) years.push(y);
    STATE.barajSeries = years.map((y,i)=>({
      yil:y,
      doluluk: 40 + 12*Math.sin(i/2.0) + 6*Math.sin(i/5.0),  // 0-100 stress/index
      ortalama_pct: 33 + 10*Math.sin(i/3.0),
      min_pct: 5 + 6*Math.abs(Math.sin(i/4.0))
    }));
    // Projection series placeholders (3 scenarios)
    STATE.projSeries = years.map((y,i)=>({yil:y, senaryo:"mevcut", doluluk: 45 + 10*Math.sin(i/3.2)}))
      .concat(years.map((y,i)=>({yil:y, senaryo:"iyi_adaptasyon", doluluk: 55 + 8*Math.sin(i/3.2)})))
      .concat(years.map((y,i)=>({yil:y, senaryo:"kotu_kuraklik", doluluk: 35 + 10*Math.sin(i/3.2)})));
    // Baselines
    STATE.selectedWaterYear = 2024;
    STATE.waterIndex = 12.7;
    STATE.droughtRisk = 0.8;
    STATE.dataSource = "demo";
  }catch(_e){}
}


async function loadDataPackageA(){
  const badge = document.getElementById("dataLoadBadge");
  const label = document.getElementById("dataSourceLabel");
  try{
    // STRICT: Enhanced dataset is the only source (no embedded/demo)
    await loadEnhancedDataset();
    await fetchBackendMeta();
    renderActiveFiles();
    STATE.dataSource = "project";
    const srcEl = document.getElementById("dataSourceLabel");
    const badge = document.getElementById("dataLoadBadge");
    if(srcEl) srcEl.textContent = "Proje verisi (ENHANCED)";
    if(badge){ badge.textContent = "CSV bağlı"; badge.classList.add("ok"); }
    // UI refresh
    refreshParcelSelect();
    refreshGlobalSummary();
    refreshCharts();
    refreshMap();
    return;

    // 1) Ürün kataloğu
    const cropsText = await fetchText(DATA_FILES.cropsCsv);
    const cropRows = parseCsv(cropsText);
    const catalog = {};
    for(const r of cropRows){
      const name = (r.urun_adi || r.urun || r.name || "").trim();
      if(!name) continue;
      const key = normCropName(name);
      // profit hesabı: verim * fiyat - maliyet (TL/da)
      const waterPerDa = +r.su_tuketimi_m3_da;
      const yld = +r.beklenen_verim_kg_da;
      const price = +r.fiyat_tl_kg;
      const cost = +r.degisken_maliyet_tl_da;
      const profitPerDa = (isFinite(yld)&&isFinite(price)&&isFinite(cost)) ? (yld*price - cost) : (+r.net_kar_tl_da || 0);
      const category = (r.kategori || r.category || "").trim();
      const kc = +r.kc_ortalama;
      const type = cropTypeFromCategory(category);
      catalog[key] = {
        rawName: name.toUpperCase(),
        waterPerDa,
        profitPerDa,
        category,
        kc,
        type,
        // ekonomi (varsa CSV'den)
        yield_kg_da: isFinite(yld) ? yld : (+r.beklenen_verim_kg_da || NaN),
        price_tl_kg: isFinite(price) ? price : (+r.fiyat_tl_kg || NaN),
        cost_tl_da: isFinite(cost) ? cost : (+r.degisken_maliyet_tl_da || NaN),
        support_tl_da: (+r.tesvik_tl_da || 0),
        // Kc evreleri (opsiyonel)
        kc_ini: (+r.kc_ini || NaN),
        kc_mid: (+r.kc_mid || NaN),
        kc_end: (+r.kc_end || NaN),
        Lini: (+r.Lini || NaN),
        Ldev: (+r.Ldev || NaN),
        Lmid: (+r.Lmid || NaN),
        Lend: (+r.Lend || NaN),
        sow: (r.sow || r.ekim_tarihi || "").trim()
      };
    }
    STATE.cropCatalog = catalog;
    // 2) Parsel verisi (CSV) -> parcelData (harita + seçimler)
    try{
      const parcelsText = await fetchText(DATA_FILES.parcelsCsv);
      const parcelRows = parseCsv(parcelsText);
      if(parcelRows && parcelRows.length){
        const byId = new Map((parcelData||[]).map(p=>[p.id,p])); // demo detayları varsa koru
        const rebuilt = [];
        for(const r of parcelRows){
          const id = (r.parsel_id || r.id || "").trim();
          if(!id) continue;
          const area = + (r.alan_da || r.area_da || 0);
          const w = + (r.mevcut_su_m3 || r.water_m3 || 0);
          const pr = + (r.mevcut_kar_tl || r.profit_tl || 0);
          const village = (r.koy || r.village || "").trim();
          const district = (r.ilce || r.district || "").trim();
          const soilCode = (r.toprak_kodu || r.soil_code || "").trim();

          const existing = byId.get(id);
          rebuilt.push({
            id,
            name: existing?.name || `${id} – ${soilCode}${village?` (${village})`:""}`,
            village: village || existing?.village || "",
            district: district || existing?.district || "",
            area_da: isFinite(area)?area:(existing?.area_da||0),
            water_m3: isFinite(w)?w:(existing?.water_m3||0),
            profit_tl: isFinite(pr)?pr:(existing?.profit_tl||0),
            soil: existing?.soil || (soilCode?{code: soilCode}:null),
            climate: existing?.climate || null,
            cropCurrent: existing?.cropCurrent || null
          });
        }
        if(rebuilt.length){
          parcelData = rebuilt;
          document.getElementById("dataSourceLabel").textContent = "CSV/JSON (data klasörü)";
        }
      }
    }catch(e){
      // parcels CSV yoksa demo devam
    
    // Fallback: show embedded demo so the UI is not blank
    try{ loadEmbeddedDemo(); }catch(_e){}
    try{
      renderActiveFiles();
      const srcEl = document.getElementById("dataSourceLabel");
      const badge2 = document.getElementById("dataLoadBadge");
      if(srcEl) srcEl.textContent = "Demo veri (offline)";
      if(badge2){ badge2.textContent = "demo"; badge2.className = "badge badge-warn"; }
    }catch(_e){}
}



    // 2) Baraj + projeksiyon
    const barajText = await fetchText(DATA_FILES.barajCsv);
    STATE.barajSeries = parseCsv(barajText).map(r=>({
      yil: +r.yil,
      // "doluluk" here is the operational / agricultural stress index on 0-100 scale
      doluluk: +r.doluluk_endeksi_0_100,
      // Derived indicators added in the updated 2000-2025 table
      ortalama_pct: +((r.ortalama_doluluk_pct!=null)? r.ortalama_doluluk_pct : r.ortalama_pct),
      min_pct: +((r.min_doluluk_pct_tahmini!=null)? r.min_doluluk_pct_tahmini : r.min_pct),
      girisim_hm3: +r.girisim_su_hacmi_hm3,
      cekis_hm3: +r.cekis_su_hacmi_hm3
    })).filter(r=>isFinite(r.yil));

    const projText = await fetchText(DATA_FILES.projCsv);
    STATE.projSeries = parseCsv(projText).map(r=>({
      yil:+r.yil,
      senaryo:(r.senaryo||"mevcut").trim(),
      doluluk:+r.doluluk_endeksi_0_100
    })).filter(r=>isFinite(r.yil));


    // 2b) Raw serileri de yükle (paketteki tüm veriler aktif kullanılsın)
    try{
      const barajRawText = await fetchText(DATA_FILES.barajRawCsv);
      STATE.barajRawSeries = parseCsv(barajRawText).map(r=>({
        yil:+r.yil,
        doluluk:+r.doluluk_endeksi_0_100,
        ortalama_pct:+((r.ortalama_doluluk_pct!=null)? r.ortalama_doluluk_pct : r.ortalama_pct),
        min_pct:+((r.min_doluluk_pct_tahmini!=null)? r.min_doluluk_pct_tahmini : r.min_pct),
        girisim_hm3:+r.girisim_su_hacmi_hm3,
        cekis_hm3:+r.cekis_su_hacmi_hm3
      })).filter(r=>isFinite(r.yil));
    }catch(e){ STATE.barajRawSeries = null; }

    try{
      const projRawText = await fetchText(DATA_FILES.projRawCsv);
      STATE.projRawSeries = parseCsv(projRawText).map(r=>({
        yil:+r.yil,
        senaryo:(r.senaryo||"mevcut").trim(),
        doluluk:+r.doluluk_endeksi_0_100
      })).filter(r=>isFinite(r.yil));
    }catch(e){ STATE.projRawSeries = null; }

    // trend/oynaklık/sürdürülebilirlik metrikleri
    updateDroughtAnalytics();

    // 3) Resmî excel özetleri (önceden türetilmiş)
    let baseVillage = null; let baseDistrict = null;
    try{ baseVillage = await fetchJson(DATA_FILES.villageJson); }catch(_){ baseVillage = null; }
    try{ baseDistrict = await fetchJson(DATA_FILES.districtJson); }catch(_){ baseDistrict = null; }
    let excelVillage = null;
    let excelDistrict = null;
    try{ excelVillage = await fetchJson(DATA_FILES.excelVillageJson); }catch(_){ excelVillage = null; }
    try{ excelDistrict = await fetchJson(DATA_FILES.excelDistrictJson); }catch(_){ excelDistrict = null; }
    STATE.villagePatterns = mergePatterns(baseVillage||{}, excelVillage||{});
    STATE.districtPatterns = mergePatterns(baseDistrict||{}, excelDistrict||{});

    // 4) Demo “referans” çıktılar
    try{ STATE.demoOutputs.ga = await fetchJson(DATA_FILES.demoOutputs.ga); }catch(_){}
    try{ STATE.demoOutputs.abc = await fetchJson(DATA_FILES.demoOutputs.abc); }catch(_){}
    try{ STATE.demoOutputs.aco = await fetchJson(DATA_FILES.demoOutputs.aco); }catch(_){}

    // 5) Toplam alan (15 parsel)
    STATE.totalAreaAllParcels = parcelData.reduce((a,p)=>a+(+p.area_da||0),0);

    // UI
    if(label) label.textContent = "ENHANCED veri paketi (2000-2025)";
    if(badge){ badge.textContent = "Veri paketi yüklendi"; badge.className = "badge badge-ok"; }

    // resmi özet panelini doldur
    renderOfficialSummary();

    // su senaryosu dropdownlarını doldur
    initWaterSelectors();

    // Build year-dependent baseline crop plan from enhanced season tables
    // so "Mevcut" efficiency and parcel comparisons are meaningful.
    applyYearBaselinesFromSeasons();
    refreshScenarioBaselineCurrent();

    // varsayılan suyu hesapla
    applyWaterScenarioFromUI();
    refreshTimeSeriesFromBackend();

  }catch(err){
    console.error(err);
    if(badge){ badge.textContent = "Veri paketi kısmi yüklendi"; badge.className = "badge badge-warn"; }
    if(label && STATE.dataSource==='project') label.textContent = "Proje verisi (ENHANCED)";
    else if(label) label.textContent = "Dahili demo";
  }
}

function getVillageShare(village, cropNorm){
  const key = (village||"").toString().toUpperCase().replaceAll("İ","I").replaceAll("Ş","S").replaceAll("Ğ","G").replaceAll("Ü","U").replaceAll("Ö","O").replaceAll("Ç","C");
  const v = STATE.villagePatterns?.[key] || STATE.villagePatterns?.[(village||"").toUpperCase()] || null;
  if(!v) return 0;
  const found = (v.top_crops||[]).find(x=>x.crop===cropNorm);
  return found ? +found.share : 0;
}

function getDistrictShare(district, cropNorm){
  const dKey = (district||"").toString().toUpperCase().replaceAll("İ","I").replaceAll("Ş","S").replaceAll("Ğ","G").replaceAll("Ü","U").replaceAll("Ö","O").replaceAll("Ç","C");
  const d = STATE.districtPatterns?.[dKey] || STATE.districtPatterns?.[(district||"").toUpperCase()] || null;
  if(!d) return 0;
  const found = (d.top_crops||[]).find(x=>x.crop===cropNorm);
  return found ? +found.share : 0;
}

function contextBonusTlPerDa(parcel, cropNorm){
  // köy + ilçe ekim desenine yakınsa küçük bir bonus (TL/da)
  const v = getVillageShare(parcel.village, cropNorm);
  const d = getDistrictShare(parcel.district, cropNorm);
  const mix = (0.65*v + 0.35*d); // [0,1]
  return 1200 * mix; // demo ölçeği
}

function parcelWaterBudget(areaDa){
  // toplam kullanılabilir suyu alana göre paylaştır (yaklaşık global kısıt)
  // kuraklık riski yükseldikçe bütçeyi otomatik daralt
  const totalA = Math.max(1, STATE.totalAreaAllParcels || 1);
  const base = (STATE.availableWaterM3 || totalA*600) * (areaDa/totalA);
  const risk = clamp(STATE.droughtRisk ?? 0, 0, 1);
  const factor = clamp(1 - 0.35*risk, 0.55, 1); // risk 1 iken ~%45 daralma
  return base * factor;
}

async function initWaterSelectors(){
  const yearSel = document.getElementById("waterYear");
  if(!yearSel) return;

  // Try backend years first
  let years=null; let defY=null;
  try{
    const r = await fetch('/api/years');
    const j = await r.json();
    if(j && j.years && j.years.length){ years = j.years; defY = j.default; }
  }catch(_){}

  // If backend provides no years, derive from active enhanced seasons (preferred)
  if(!years || !years.length){
    years = getAvailableYearsFromActiveSeasons();
    if(!years || !years.length){
      years = [];
      for(let y=2000;y<=2050;y++) years.push(y);
    }
    defY = STATE.selectedWaterYear || (years.length ? years[years.length-1] : 2024);
  }

  // Set default
  if(!STATE.selectedWaterYear) STATE.selectedWaterYear = defY || years[years.length-1];

  // Fill options
  yearSel.innerHTML = "";
  for(const y of years){
    const opt=document.createElement("option");
    opt.value=String(y); opt.textContent=String(y);
    if(Number(y)===Number(STATE.selectedWaterYear)) opt.selected=true;
    yearSel.appendChild(opt);
  }

  const _handleWaterYearChange = ()=>{
    STATE.selectedWaterYear = Number(yearSel.value);

    // Rebuild year-dependent baselines and clear optimization caches
    // so recommendations can change across parcels/years.
    applyYearBaselinesFromSeasons();
    for(const k of Object.keys(basinPlanCache)) delete basinPlanCache[k];
    for(const k of Object.keys(optimizationCache)) delete optimizationCache[k];

    applyWaterScenarioFromUI();
    refreshTimeSeriesFromBackend();
    // refresh projection/time series charts
    refreshTimeSeriesFromBackend();
  };

  yearSel.addEventListener('change', _handleWaterYearChange);
  // Some browsers/UIs trigger 'input' more reliably for select changes; keep both.
  yearSel.addEventListener('input', _handleWaterYearChange);


  const scenSel = document.getElementById("waterScenarioSel");
  if(scenSel){
    scenSel.value = STATE.selectedProjScenario;
    scenSel.onchange=()=>{ STATE.selectedProjScenario=scenSel.value; applyWaterScenarioFromUI(true); };
  }
}


function computeDroughtRiskForYear(yil, dolulukIdx){
  // Basit risk: doluluk düşükse + trend kötüleşiyorsa artar (0-1)
  const idx = isFinite(dolulukIdx) ? dolulukIdx : 60;
  const low = clamp((35 - idx)/35, 0, 1); // 35 altı hızlı artar
  const slope = STATE._dolulukSlope10y ?? 0; // negatifse kötü
  const trend = clamp((-slope)/4.0, 0, 1);   // ~-4 puan/yıl ve altı yüksek risk
  const vol = clamp((STATE._dolulukStd10y ?? 0)/15.0, 0, 1);
  const sust = (STATE.sustainabilityIndex==null) ? 0.25 : clamp(1 - STATE.sustainabilityIndex, 0, 1);
  return clamp(0.45*low + 0.25*trend + 0.15*vol + 0.15*sust, 0, 1);
}

function updateDroughtAnalytics(){
  // If Chart.js not ready yet, retry shortly
  if(typeof Chart === "undefined"){
    setTimeout(()=>{ try{ updateDroughtAnalytics(); }catch(_e){} }, 250);
    return;
  }

  // barajRawSeries veya barajSeries üzerinden son 10 yıllık trend/oynaklık çıkar
  const src = (STATE.barajRawSeries && STATE.barajRawSeries.length) ? STATE.barajRawSeries : STATE.barajSeries;
  if(!src || src.length < 5) return;

  const last = src.slice(-10);
  const ys = last.map(r=>r.yil);
  const xs = last.map(r=>r.doluluk);

  // linear regression slope
  const n = xs.length;
  const xbar = ys.reduce((a,b)=>a+b,0)/n;
  const ybar = xs.reduce((a,b)=>a+b,0)/n;
  let num=0, den=0;
  for(let i=0;i<n;i++){
    num += (ys[i]-xbar)*(xs[i]-ybar);
    den += (ys[i]-xbar)*(ys[i]-xbar);
  }
  const slope = den ? (num/den) : 0;
  STATE._dolulukSlope10y = slope;

  const mean = ybar;
  const varr = xs.reduce((a,v)=>a+(v-mean)*(v-mean),0)/Math.max(1,n-1);
  STATE._dolulukStd10y = Math.sqrt(varr);

  // sustainability: inflow/outflow dengesine göre
  const inflow = last.map(r=>+r.girisim_hm3).filter(isFinite);
  const outflow = last.map(r=>+r.cekis_hm3).filter(isFinite);
  if(inflow.length && outflow.length){
    const inMean = inflow.reduce((a,b)=>a+b,0)/inflow.length;
    const outMean = outflow.reduce((a,b)=>a+b,0)/outflow.length;
    STATE.sustainabilityIndex = clamp((inMean - outMean) / Math.max(1e-6, inMean), -1, 1); // negatifse çekiş > giriş
    // 0-1 bandına indir
    STATE.sustainabilityIndex = clamp((STATE.sustainabilityIndex + 1)/2, 0, 1);
  }
}

function getHistMaxYear(){
  const ys = (STATE.barajSeries||[]).map(r=>+r.yil).filter(v=>isFinite(v));
  return ys.length ? Math.max(...ys) : 2024;
}

// =========================
// Kuraklık: interaktif seri grafiği (Chart.js)
// =========================
let droughtSeriesChart = null;

function ensureDroughtSeriesChart(){
  const canvas = document.getElementById("droughtSeriesChart");
  if(!canvas || typeof Chart === "undefined") return;

  // Build base years from observed series (2000–2025)
  const hist = Array.isArray(STATE.barajSeries) ? STATE.barajSeries.slice() : [];
  hist.sort((a,b)=>(+a.yil)-(+b.yil));
  const labels = hist.map(r=>String(r.yil));
  const avg = hist.map(r=> isFinite(r.ortalama_pct) ? +r.ortalama_pct : null);
  const minv = hist.map(r=> isFinite(r.min_pct) ? +r.min_pct : null);
  const stress = hist.map(r=> isFinite(r.doluluk) ? +r.doluluk : null);

  const ySel = Number(STATE.selectedWaterYear);
  const selIdx = labels.indexOf(String(ySel));

  const onlyAt = (arr)=>{
    return arr.map((v,i)=> (i===selIdx ? v : null));
  };

  const data = {
    labels,
    datasets: [
      {
        label: "Ortalama Doluluk (%)",
        data: avg,
        tension: 0.25,
        borderWidth: 2,
        pointRadius: 2,
        pointHoverRadius: 5,
        spanGaps: true,
      },
      {
        label: "Minimum Doluluk (Tahmini, %)",
        data: minv,
        tension: 0.25,
        borderWidth: 2,
        pointRadius: 2,
        pointHoverRadius: 5,
        spanGaps: true,
      },
      {
        label: "Tarımsal Stres Endeksi (0–100)",
        data: stress,
        tension: 0.25,
        borderWidth: 2,
        pointRadius: 2,
        pointHoverRadius: 5,
        spanGaps: true,
      },
    ]
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { display: true, position: "top" },
      tooltip: {
        enabled: true,
        callbacks: {
          label: (ctx)=>{
            const v = ctx.parsed.y;
            if(v==null || !isFinite(v)) return null;
            // Keep % sign for first two datasets
            const label = ctx.dataset.label || "";
            const isPct = label.includes("Doluluk");
            return `${label}: ${v.toFixed(1)}${isPct ? "%" : ""}`;
          }
        }
      }
    },
    scales: {
      y: {
        min: 0,
        max: 100,
        ticks: { callback: (v)=> v + "" }
      },
      x: { ticks: { maxTicksLimit: 8 } }
    }
  };

  if(!droughtSeriesChart){
    droughtSeriesChart = new Chart(canvas.getContext("2d"), {
      type: "line",
      data,
      options
    });
  }else{
    // update existing chart (labels + datasets)
    droughtSeriesChart.data.labels = data.labels;
    // keep dataset count stable
    for(let i=0;i<droughtSeriesChart.data.datasets.length;i++){
      if(data.datasets[i]){
        droughtSeriesChart.data.datasets[i].data = data.datasets[i].data;
        droughtSeriesChart.data.datasets[i].label = data.datasets[i].label;
      }
    }
    droughtSeriesChart.update();
  }
}

function updateDroughtAlarmCard(){
  let msg = "";

  const y = +STATE.selectedWaterYear;
  const maxHist = getHistMaxYear();
  const r = (y<=maxHist) ? (STATE.barajSeries||[]).find(x=>x.yil===y) : null;

  // Prefer updated table fields when available
  const stress = isFinite(STATE.waterIndex) ? +STATE.waterIndex : (r && isFinite(r.doluluk) ? +r.doluluk : null);
  const avg = (r && isFinite(r.ortalama_pct)) ? +r.ortalama_pct : null;
  const minv = (r && isFinite(r.min_pct)) ? +r.min_pct : null;

  const elMin = document.getElementById("droughtMinPct");
  const elAvg = document.getElementById("droughtAvgPct");
  const elIdx = document.getElementById("droughtStressIdx");
  if(elMin) elMin.textContent = (isFinite(minv) ? minv.toFixed(1) : "–");
  if(elAvg) elAvg.textContent = (isFinite(avg) ? avg.toFixed(1) : "–");
  if(elIdx) elIdx.textContent = (isFinite(stress) ? stress.toFixed(1) : "–");

  // Determine alarm level mainly from minimum fullness (most meaningful for irrigation crises)
  let level="–", cls="badge-info", msgTxt ="–";
  if(isFinite(minv)){
    if(minv < 10){ level="KRİTİK"; cls="badge-err"; msgTxt ="Sulama sezonunda kritik minimumlar görülebilir (min < %10). Su yoğun ürünler ve salma sulama yüksek risk taşır."; }
    else if(minv < 20){ level="RİSKLİ"; cls="badge-warn"; msgTxt ="Sulama sezonunda ciddi kısıt olasılığı var (min %10–%20). Sulama yöntemi dönüşümü (damla/yağmurlama) önceliklenmeli."; }
    else if(minv < 30){ level="ORTA"; cls="badge-info"; msgTxt ="Orta düzey risk (min %20–%30). Su bütçesi ve ürün seçimi dikkatle optimize edilmeli."; }
    else { level="NORMAL"; cls="badge-ok"; msgTxt ="Görece daha rahat bir yıl (min ≥ %30). Yine de verimli sulama ve uygun ürün deseni önerilir."; }
  }else{
    // Fallback to stress index if min not available
    if(isFinite(stress)){
      if(stress < 20){ level="RİSKLİ"; cls="badge-warn"; msgTxt ="Stres endeksi düşük. Sulama verimliliği ve su tasarrufu tedbirleri kritik."; }
      else { level="BİLGİ"; cls="badge-info"; msgTxt ="Doluluk göstergeleri sınırlı. Yıllık su kısıtı ve senaryo seçimlerine göre değerlendirin."; }
    }
  }

  const levelEl=document.getElementById("droughtAlarmLevel");
  if(levelEl){
    levelEl.className = "badge " + cls;
    levelEl.textContent = level;
  }
  
// Otomatik yorum + öneri listeleri (scoped)
(()=>{
  const commentEl = document.getElementById("droughtAutoComment");
  const avoidEl = document.getElementById("droughtAvoidList");
  const preferEl = document.getElementById("droughtPreferList");
  const noteEl = document.getElementById("droughtImpactNote");

  const setList = (el, items)=>{
    if(!el) return;
    el.innerHTML = "";
    (items||[]).forEach(t=>{
      const li=document.createElement("li");
      li.textContent=t;
      el.appendChild(li);
    });
  };

  const L = (level||"").toUpperCase();
  let comment = "";
  let avoid = [];
  let prefer = [];
  let note = "";

  if(L === "KRİTİK"){
    comment = "Su arzı <b>çok kısıtlı</b>. Su yoğun ürünlerde alanı azaltın; basınçlı sulama ve erken ekim/hasat planı uygulayın.";
    avoid = ["Silajlık mısır", "Patates", "Şeker pancarı", "Yonca (tam alan)", "Aşırı sulama isteyen sebzeler"];
    prefer = ["Buğday / arpa", "Nohut / mercimek", "Ayçiçeği (kuru/az su)", "Bağ / badem (uygunsa)", "Nadas/yeşil gübre rotasyonu"];
    note = "Bu liste, optimizasyon sonucunu tamamlayıcı bir karar destek notudur: Kuraklıkta su talebi yüksek ürünler daha riskli olur. Parsel toprak sınıfı ve randımanına göre ürün havuzu değişebilir; hedef her zaman su tasarrufu olduğundan düşük su tüketimli seçeneklere ağırlık verin.";
  }else if(L === "YÜKSEK"){
    comment = "Kuraklık riski <b>yüksek</b>. Su tüketimi yüksek ürünlerde kademeli azaltım önerilir; sulama zamanlaması optimize edilmelidir.";
    avoid = ["Silajlık mısır (geniş alan)", "Şeker pancarı", "Yonca (yüksek sıklık)"];
    prefer = ["Buğday / arpa", "Baklagiller", "Ayçiçeği", "Damla sulama ile sebzeler (kontrollü)"];
    note = "Bu öneriler, su tasarrufu hedefini desteklemek içindir. Su bütçesi kısıtına yaklaşıldığında rotasyon ve basınçlı sulama (damla/yağmurlama) su verimliliğini artırır.";
  }else if(L === "ORTA"){
    comment = "Kuraklık riski <b>orta</b>. Su tüketimi dengelenmeli; verimlilik artırıcı yöntemlerle (damla/yağmurlama) risk azaltılabilir.";
    avoid = ["Su yoğun ürünlerde gereksiz alan artışı"];
    prefer = ["Mevcut desen + verimlilik", "Rotasyon (baklagil + tahıl)", "Kısmi alanlarda su yoğun ürün"];
    note = "Not: Bu sistemde amaç su tasarrufudur; su verimliliği düşük ürünlerde dikkatli alan planlaması ve verimli sulama yöntemleri önerilir.";
  }else{
    comment = "Kuraklık riski <b>düşük</b>. Mevcut desen korunabilir; yine de su verimliliği iyileştirmeleri uzun vadede avantaj sağlar.";
    avoid = ["Su verimliliğini düşüren sulama uygulamaları"];
    prefer = ["Mevcut desen", "Verimlilik yatırımı (damla/yağmurlama)", "Toprak organik madde artırımı"];
    note = "Not: Kuraklık düşük olsa bile iklim belirsizliği için alternatif ürün/rotasyon planı hazır tutun; su verimliliği yatırımları uzun vadede avantaj sağlar.";
  }

  if(commentEl) commentEl.innerHTML = "🔎 Yorum: " + comment;
  setList(avoidEl, avoid);
  setList(preferEl, prefer);
  if(noteEl) noteEl.textContent = note;
})();


      const sumB=document.getElementById("droughtSummaryBadge");
  if(sumB){ sumB.textContent = level; }
const bLevel=document.getElementById("droughtBannerLevel");
  if(bLevel){ bLevel.textContent = level; }
// Attention pulse on critical drought years (safe, slow)
  const cardEl = document.getElementById("droughtAlarmCard");
  if(cardEl){
    const isCritical = (level === "KRİTİK");
    cardEl.classList.toggle("pulse-attn", isCritical);
  }
  if(levelEl){
    levelEl.classList.toggle("blink-soft", (level === "KRİTİK"));
  }
  // msgTxt zaten fonksiyonun başında tanımlanıyor; burada tekrar tanımlamak
  // tarayıcıda "Identifier has already been declared" hatasına yol açıyordu.
  // Bu yüzden yalnızca mevcut msgTxt değişkenini kullanıyoruz.
  const textEl=document.getElementById("droughtAlarmText");
  if(textEl) textEl.textContent = msgTxt;

  // update mini chart
  ensureDroughtSeriesChart();
}

function getMethodTotalEff(methodName){
  const m = String(methodName||"").trim();
  if(!m) return Number(STATE.irrigEfficiency||0.62);
  const row = (STATE.irrigMethods||[]).find(r => String(r.method||"").trim() === m);
  const eff = row ? Number(row.total_eff) : NaN;
  return (Number.isFinite(eff) && eff>0) ? eff : Number(STATE.irrigEfficiency||0.62);
}

function getNetM3PerDaFromSeasons(year, cropKey){
  const y = Number(year);
  const map = STATE.cropNetPerDaByYear ? STATE.cropNetPerDaByYear.get(y) : null;
  if(map && map.has(cropKey)) return Number(map.get(cropKey));
  return NaN;
}

function getPlantsPerDaFromSeasons(year, cropKey){
  const y = Number(year);
  const map = STATE.cropPlantsPerDaByYear ? STATE.cropPlantsPerDaByYear.get(y) : null;
  if(map && map.has(cropKey)) return Number(map.get(cropKey));
  return NaN;
}


function applyWaterScenarioFromUI(clearCache=false){
  // Keep STATE.selectedWaterYear synced with the UI dropdown (robust against missed events)
  try{
    const ySel = document.getElementById('waterYear');
    if(ySel && ySel.value!=null && ySel.value!==''){
      const vy = Number(ySel.value);
      if(isFinite(vy)) STATE.selectedWaterYear = vy;
    }
  }catch(_){ }

  const y = +STATE.selectedWaterYear;
  let idx = null;
  const maxHistYear = getHistMaxYear();
  if(y<=maxHistYear){
    const r = (STATE.barajSeries||[]).find(x=>x.yil===y);
    idx = r ? r.doluluk : null;
  }else{
    const r = (STATE.projSeries||[]).find(x=>x.yil===y && x.senaryo===STATE.selectedProjScenario);
    idx = r ? r.doluluk : null;
  }
  // Veri paketlerinde doluluk endeksi bazen 0-1 aralığında (oran) gelebiliyor.
  // UI ve risk hesapları yüzde (0-100) beklediği için otomatik ölçekle.
  if(isFinite(idx) && idx > 0 && idx <= 1.2) idx = idx * 100;
  if(!isFinite(idx)) idx = 60; // fallback
  STATE.waterIndex = idx;
  STATE.availableWaterM3 = Math.round((idx/100) * STATE.maxCapacityM3);
  // risk güncelle
  STATE.droughtRisk = computeDroughtRiskForYear(y, idx);

  const aw = document.getElementById("availableWaterLabel");
  if(aw) aw.textContent = formatNum(STATE.availableWaterM3);
  const b = document.getElementById("waterIndexBadge");
  if(b){
    const r = STATE.droughtRisk;
    const rTxt = (r>=0.75) ? "yüksek" : (r>=0.45 ? "orta" : "düşük");
    b.textContent = `doluluk: ${ (typeof idx==="number" && isFinite(idx)) ? idx.toFixed(1) : "-" } | risk: ${rTxt}`;
  }

  updateDroughtAlarmCard();
  if(clearCache){
    // su kısıtı değişince optimizasyon önbelleğini temizle
    for(const k of Object.keys(optimizationCache)) delete optimizationCache[k];
    for(const k of Object.keys(basinPlanCache)) delete basinPlanCache[k];
    refreshUI();
  }
}

function renderOfficialSummary(){
  const root = document.getElementById("officialSummary");
  if(!root) return;

  // If JSON-based official patterns are missing/empty, derive a best-effort summary
  // from the active season dataset (scenario1/2 seasons CSVs). This keeps this panel
  // useful even when the optional Excel-derived JSON summary files are not shipped.
  if(!STATE.villagePatterns || !STATE.districtPatterns ||
     (Object.keys(STATE.villagePatterns||{}).length===0 && Object.keys(STATE.districtPatterns||{}).length===0)){
    try{
      const rows = Array.isArray(STATE.seasonRows) ? STATE.seasonRows : [];
      const y = Number(STATE.selectedWaterYear || 2024);
      const filt = rows.filter(r=>Number(r.year||r.yil)===y);

      const byVillage = new Map();
      const byDistrict = new Map();
      for(const r of filt){
        const v = String(r.village||r.koy||'').trim() || 'Bilinmeyen (köy yok)';
        const d = String(r.district||r.ilce||'').trim() || 'Bilinmeyen (ilçe yok)';
        const crop = String(r.crop||r.urun||'').trim() || 'Bilinmeyen ürün';
        const area = safeNum(r.area_da||r.alan_da||0);
        if(area<=0) continue;
        if(!byVillage.has(v)) byVillage.set(v, new Map());
        if(!byDistrict.has(d)) byDistrict.set(d, new Map());
        byVillage.get(v).set(crop, (byVillage.get(v).get(crop)||0) + area);
        byDistrict.get(d).set(crop, (byDistrict.get(d).get(crop)||0) + area);
      }

      const buildTop = (mp)=>{
        const out = {};
        for(const [name,crops] of mp.entries()){
          const total = Array.from(crops.values()).reduce((a,b)=>a+b,0) || 1;
          const top = Array.from(crops.entries())
            .sort((a,b)=>b[1]-a[1])
            .slice(0,10)
            .map(([crop,area])=>({ crop, area_da: area, share: area/total }));
          out[name] = { total_area_da: total, top_crops: top };
        }
        return out;
      };

      STATE.villagePatterns = buildTop(byVillage);
      STATE.districtPatterns = buildTop(byDistrict);
    }catch(_e){
      // leave as-is; we'll render a "no data" hint below
    }
  }

  // if still missing, show an explicit hint instead of a blank card
  if(!STATE.villagePatterns || !STATE.districtPatterns){
    root.innerHTML = `<div class="muted">Resmî ekim deseni özeti üretilemedi. (Veri eksik: köy/ilçe ekim desenleri veya sezon verisi bulunamadı.)</div>`;
    return;
  }

  // en çok kullanılan 6 köy + 6 ilçe listesini basit tablo halinde göster
  const villages = Object.keys(STATE.villagePatterns).slice(0,6);
  const districts = Object.keys(STATE.districtPatterns).slice(0,6);

  const mkList = (title, items, getter)=>`
    <div class="mini-block">
      <h4 style="margin:6px 0 8px 0">${title}</h4>
      ${items.map(name=>{
        const top = (getter(name).top_crops||[]).slice(0,5).map(x=>`${x.crop} (${(x.share*100).toFixed(1)}%)`).join(", ");
        return `<div class="mini-row"><strong>${name}</strong><div class="muted">${top || "—"}</div></div>`;
      }).join("")}
    </div>
  `;

  root.innerHTML = `
    <div class="official-grid">
      ${mkList("Köyler – ilk 5 ürün (alan payı)", villages, (n)=>STATE.villagePatterns[n])}
      ${mkList("İlçeler – ilk 5 ürün (alan payı)", districts, (n)=>STATE.districtPatterns[n])}
      <div class="mini-block">
        <h4 style="margin:6px 0 8px 0">Bu özet nasıl kullanılıyor?</h4>
        <div class="muted">Optimizasyon sırasında, önerilen ürün köy/ilçe desenine yakınsa küçük bir “uygunluk bonusu” alır. Böylece sonuçlar, sahadaki ekim pratiğine daha uyumlu olur.</div>
      </div>
    </div>
  `;
}

// ------------------------------------------------------------
// Resmî tablolar (A seçeneği): su bütçesi + senaryo deseni + parsel özeti
// ------------------------------------------------------------

function toHm3(m3){
  return m3 / 1_000_000.0;
}

function downloadTextFile(filename, text, mime="text/plain;charset=utf-8"){
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(()=>URL.revokeObjectURL(url), 4000);
}

function asCsv(rows){
  // rows: Array<Array<string|number>>
  return rows.map(r=>r.map(v=>{
    const s = (v===null||v===undefined) ? "" : String(v);
    const safe = s.includes('"') ? s.replaceAll('"','""') : s;
    return (safe.includes(',') || safe.includes('\n') || safe.includes('"')) ? `"${safe}"` : safe;
  }).join(',')).join('\n');
}

function renderOfficialTables(){
  // DOM
  const tblWater = document.querySelector('#tblOfficialWater tbody');
  const tblScenario = document.querySelector('#tblOfficialScenario tbody');
  const tblParcels = document.querySelector('#tblOfficialParcels tbody');
  if(!tblWater || !tblScenario || !tblParcels) return;

  // Basin plan (küresel bütçe sonrası)
  const basin = computeBasinPlan(selectedScenario, selectedAlgo);
  const budgetM3 = basin.budget;
  const usedM3 = basin.totals.water;
  const balanceM3 = budgetM3 - usedM3;

  const status = balanceM3 >= 0 ? 'Uygun' : 'Aşım';
  const statusTxt = balanceM3 >= 0 ? 'UYGUN (bütçe içinde)' : 'RİSKLİ (bütçe aşıldı)';

  // 1) Water budget table
  tblWater.innerHTML = '';
  const waterRows = [
    ['Seçili su yılı', String(STATE.selectedWaterYear ?? '—'), 'yıl'],
    ['Doluluk endeksi', (STATE.waterIndex!=null ? STATE.waterIndex.toFixed(1) : '—'), '0–100'],
    ['Toplam kullanılabilir su', toHm3(budgetM3).toFixed(3), 'hm³'],
    ['Toplam tarımsal talep (15 parsel)', toHm3(usedM3).toFixed(3), 'hm³'],
    ['Su dengesi (kalan / açık)', toHm3(balanceM3).toFixed(3), 'hm³'],
    ['Su durumu', status, '—'],
  ];
  for(const r of waterRows){
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${r[0]}</td><td>${r[1]}</td><td>${r[2]}</td>`;
    tblWater.appendChild(tr);
  }
  const waterNote = document.getElementById('officialWaterNote');
  if(waterNote){
    waterNote.textContent = `Durum: ${statusTxt}. (Hesap: küresel su bütçesi + seçili senaryo/algoritma)`;
  }

  // 2) Scenario aggregated crop pattern
  const agg = {}; // crop -> {area, water, profit}
  for(const p of parcelData){
    const rows = basin.plan?.[p.id]?.rows || [];
    for(const row of rows){
      const crop = row.name;
      if(!agg[crop]) agg[crop] = { area:0, water:0, profit:0 };
      agg[crop].area += +row.area || 0;
      agg[crop].water += +row.totalWater || 0;
      agg[crop].profit += +row.totalProfit || 0;
    }
  }
  const crops = Object.keys(agg).map(k=>({
    crop:k,
    area:agg[k].area,
    water:agg[k].water,
    profit:agg[k].profit,
    eff: agg[k].profit / Math.max(1, agg[k].water)
  })).filter(x=>x.area>0.01);
  crops.sort((a,b)=>b.profit-a.profit);

  tblScenario.innerHTML = '';
  let totArea=0, totWater=0, totProfit=0;
  for(const c of crops){
    totArea += c.area; totWater += c.water; totProfit += c.profit;
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${c.crop}</td>
      <td>${c.area.toFixed(1)}</td>
      <td>${Math.round(c.water).toLocaleString('tr-TR')}</td>
      <td>${Math.round(c.profit).toLocaleString('tr-TR')}</td>
      <td>${c.eff.toFixed(2)}</td>
    `;
    tblScenario.appendChild(tr);
  }
  const footer = document.getElementById('tblOfficialScenarioFooter');
  if(footer){
    // footer içinde button + note var, total notunu not elementine yazalım
    const note = document.getElementById('officialScenarioNote');
    if(note){
      note.textContent = `Toplam: alan ${totArea.toFixed(1)} da • su ${Math.round(totWater).toLocaleString('tr-TR')} m³ • kâr ${Math.round(totProfit).toLocaleString('tr-TR')} TL`;
    }
  }

  // 3) Parcel summary table
  tblParcels.innerHTML = '';
  const parcelRows = [];
  for(const p of parcelData){
    const t = basin.plan?.[p.id]?.totals;
    if(!t) continue;
    const eff = t.profit / Math.max(1, t.water);
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${p.name}</td>
      <td>${(+t.area).toFixed(1)}</td>
      <td>${Math.round(t.water).toLocaleString('tr-TR')}</td>
      <td>${Math.round(t.profit).toLocaleString('tr-TR')}</td>
      <td>${eff.toFixed(2)}</td>
    `;
    tblParcels.appendChild(tr);
    parcelRows.push([p.name, (+t.area).toFixed(1), Math.round(t.water), Math.round(t.profit), eff.toFixed(2)]);
  }

  // Export buttons
  const btnW = document.getElementById('btnExportWaterCsv');
  if(btnW && !btnW._bound){
    btnW._bound = true;
    btnW.addEventListener('click', ()=>{
      const csv = asCsv([
        ['Gosterge','Deger','Birim'],
        ...waterRows
      ]);
      downloadTextFile(`akkaya_resmi_su_butcesi_${STATE.selectedWaterYear||'yil'}.csv`, csv, 'text/csv;charset=utf-8');
    });
  }
  const btnS = document.getElementById('btnExportScenarioCsv');
  if(btnS && !btnS._bound){
    btnS._bound = true;
    btnS.addEventListener('click', ()=>{
      const rows = [['Urun','Alan_da','Toplam_Su_m3','Toplam_Kar_TL','Su_Verimliligi_TL_m3']];
      for(const c of crops){
        rows.push([c.crop, c.area.toFixed(1), Math.round(c.water), Math.round(c.profit), c.eff.toFixed(2)]);
      }
      rows.push(['TOPLAM', totArea.toFixed(1), Math.round(totWater), Math.round(totProfit), (totProfit/Math.max(1,totWater)).toFixed(2)]);
      downloadTextFile(`akkaya_resmi_bitki_deseni_${selectedScenario}_${selectedAlgo}.csv`, asCsv(rows), 'text/csv;charset=utf-8');
    });
  }
  const btnP = document.getElementById('btnExportParcelsCsv');
  if(btnP && !btnP._bound){
    btnP._bound = true;
    btnP.addEventListener('click', ()=>{
      const rows = [['Parsel','Alan_da','Toplam_Su_m3','Toplam_Kar_TL','Su_Verimliligi_TL_m3'], ...parcelRows];
      downloadTextFile(`akkaya_resmi_parsel_ozeti_${selectedScenario}_${selectedAlgo}.csv`, asCsv(rows), 'text/csv;charset=utf-8');
    });
  }

  // 4) Farmer-friendly: All parcels current vs recommended + transparent alternatives
  try{
    renderOfficialAllParcelCompare(basin);
  }catch(e){
    console.warn('renderOfficialAllParcelCompare failed', e);
  }
}

// --- Farmer-friendly official table: all parcels current vs recommended + alternatives ---
function _fmtNum(n, digits=0){
  const v = Number(n);
  if(!Number.isFinite(v)) return '—';
  if(digits<=0) return Math.round(v).toLocaleString('tr-TR');
  return v.toFixed(digits);
}

function _groupRowsBySeason(rows){
  const g = { 'Yazlık':[], 'Kışlık':[], 'Çok yıllık':[], '—':[] };
  for(const r of (rows||[])){
    const s = (r.season||'—').toString();
    const key = g[s] ? s : (s.includes('kış')?'Kışlık':(s.includes('yaz')?'Yazlık':(s.includes('çok')?'Çok yıllık':'—')));
    g[key] = g[key] || [];
    g[key].push(r);
  }
  return g;
}

// Heuristic season inference for rows coming from optimization backend.
// If season is missing/'—', UI normalization may incorrectly split parcel area across crops.
function inferSeasonFromCropName(cropName){
  const c = normCropName(cropName||'');
  if(!c) return '—';
  // Perennials / orchards
  if(c.includes('ELMA')||c.includes('ARMUT')||c.includes('KIRAZ')||c.includes('VİŞNE')||c.includes('VISNE')||c.includes('SEFTALI')||c.includes('KAYISI')||c.includes('UZUM')||c.includes('BAG')||c.includes('CEVIZ')||c.includes('ARMUT')) return 'Çok yıllık';
  // Typical winter crops (Niğde/Akkaya): cereals & cool-season legumes/forage
  if(c.includes('BUGDAY')||c.includes('BUĞDAY')||c.includes('ARPA')||c.includes('CAVDAR')||c.includes('ÇAVDAR')||c.includes('YULAF')||c.includes('TRITIKALE')) return 'Kışlık';
  if(c.includes('FIG')||c.includes('FİG')||c.includes('YONCA')||c.includes('KORUNGA')) return 'Kışlık';
  // Summer-heavy crops
  if(c.includes('MISIR')||c.includes('MİSIR')||c.includes('PATATES')||c.includes('PANCAR')||c.includes('SEKER')||c.includes('AYCICEGI')||c.includes('AYÇİÇEĞİ')) return 'Yazlık';
  if(c.includes('DOMATES')||c.includes('BIBER')||c.includes('BİBER')||c.includes('KABAK')||c.includes('KAVUN')||c.includes('KARPUZ')||c.includes('SALATALIK')||c.includes('BAMYA')) return 'Yazlık';
  // Cool-season vegetables often planted in autumn/spring; treat as winter unless known otherwise
  if(c.includes('ISPANAK')||c.includes('LAHANA')||c.includes('MARUL')||c.includes('BROKOLI')||c.includes('BROKOLİ')) return 'Kışlık';
  return '—';
}

// --- v57b: Parsel alanını sezonsal mantıkla normalize et ---
// Rotasyon (Yazlık + Kışlık) varsa: her sezon, parsel alanını ZAMAN içinde kullanır.
// Bu yüzden her sezon grubunun alan toplamı parsel alanına yakın olmalıdır.
// Aynı sezonda birden fazla ürün varsa (çeşitlendirme): o sezon grubunun toplamı parsel alanına eşitlenir.
function normalizeRowsBySeasonToParcelArea(areaDa, rows){
  const A = safeNum(areaDa, 0);
  if(!Array.isArray(rows) || !rows.length || A<=0) return rows || [];

  // Clone + standardize fields
  const rr = rows.map(r=>({
    ...r,
    // If backend didn't label season, infer so rotation logic doesn't split areas incorrectly.
    season: (r.season && r.season !== '—') ? r.season : inferSeasonFromCropName(r.name),
    area: safeNum(r.area ?? r.area_da ?? r.areaDa, safeNum(r.area_da, 0)),
    waterPerDa: safeNum(r.waterPerDa ?? r.water_m3_da ?? r.su_m3_da ?? r.water, 0),
    profitPerDa: safeNum(r.profitPerDa ?? r.net_profit_tl_da ?? r.kar_tl_da ?? r.profit, 0),
  }));

  const g = _groupRowsBySeason(rr);
  const seasons = Object.keys(g).filter(k=>g[k] && g[k].length);

  for(const s of seasons){
    const group = g[s];
    const sum = group.reduce((a,r)=>a+safeNum(r.area,0),0);
    if(sum<=0){
      // if backend forgot areas, assume full parcel use for that season
      group[0].area = A;
    }else{
      const rel = Math.abs(sum - A) / Math.max(A, 1e-9);
      if(rel > 0.01){
        const k = A / sum;
        for(const r of group){ r.area = safeNum(r.area,0) * k; }
      }
    }
  }

  // recompute totals
  rr.forEach(r=>{
    r.totalWater = safeNum(r.area,0) * safeNum(r.waterPerDa,0);
    r.totalProfit = safeNum(r.area,0) * safeNum(r.profitPerDa,0);
  });
  return rr;
}

function _rowsToLabel(rows){
  const g = _groupRowsBySeason(rows);
  const parts = [];
  const pushSeason = (k)=>{
    if(!g[k] || !g[k].length) return;
    const list = g[k].map(r=>`${r.name}${r.area!=null?` (${_fmtNum(r.area,1)} da)`:''}`).join(' + ');
    parts.push(`<div><strong>${k}:</strong> ${list}</div>`);
  };
  pushSeason('Yazlık');
  pushSeason('Kışlık');
  pushSeason('Çok yıllık');
  if(!parts.length && rows && rows.length){
    parts.push(rows.map(r=>`${r.name} (${_fmtNum(r.area,1)} da)`).join(' + '));
  }
  return parts.join('');
}

function _computeTotalsFromRows(rows){
  const r = (rows||[]).map(x=>({
    area: +x.area || 0,
    totalWater: (x.totalWater!=null)?(+x.totalWater||0):((+x.area||0)*(+x.waterPerDa||0)),
    totalProfit: (x.totalProfit!=null)?(+x.totalProfit||0):((+x.area||0)*(+x.profitPerDa||0))
  }));
  return {
    area: r.reduce((a,x)=>a+x.area,0),
    water: r.reduce((a,x)=>a+x.totalWater,0),
    profit: r.reduce((a,x)=>a+x.totalProfit,0)
  };
}

function _scenarioObjectiveKey(){
  const s = (selectedScenario||'').toString().toLowerCase();
  if(s.includes('tasarruf') || s==='water_saving') return 'water_saving';
  if(s.includes('maks') || s.includes('max') || s==='max_profit') return 'max_profit';
  if(s.includes('mevcut') || s==='current') return 'current';
  return 'balanced';
}

function _scoreCandidate(w, p){
  const obj = _scenarioObjectiveKey();
  if(obj==='water_saving') return w; // lower better
  if(obj==='max_profit') return -p;  // higher profit => lower score
  // balanced: tradeoff
  return (w/1000.0) - (p/10000.0);
}

// Alternatives should be compared at the same "decision granularity" as the recommendation:
// - If the recommendation is a 2-season rotation (Yazlık + Kışlık), compare against alternative *pairs*.
// - If the recommendation is single-season, compare against single crops.
function _alternativeCandidatesForParcel(parcel, chosenRows){
  const catalog = STATE.cropCatalog || {};
  const A = safeNum(parcel?.area_da);
  if(A<=0) return [];

  // Normalize seasons for chosen rows
  const chosenNorm = (chosenRows||[]).map(r=>({
    name: r.name,
    season: (r.season && r.season !== '—') ? r.season : inferSeasonFromCropName(r.name)
  }));

  const hasSummer = chosenNorm.some(r=>r.season==='Yazlık');
  const hasWinter = chosenNorm.some(r=>r.season==='Kışlık');
  // If the farmer's current practice is rotation (summer+winter), comparisons should also be rotation,
  // even if the recommended rows missed season labels.
  const curSeasons = (parcel?.cropCurrent||[]).map(r=> (r.season && r.season!=='—') ? r.season : inferSeasonFromCropName(r.name));
  const curHasSummer = curSeasons.some(s=>s==='Yazlık');
  const curHasWinter = curSeasons.some(s=>s==='Kışlık');
  const isTwoSeason = (hasSummer && hasWinter) || (curHasSummer && curHasWinter);

  const chosenSet = new Set(chosenNorm.map(r=>normCropName(r.name)));

  // Build a pool of candidate crops with derived season
  const pool = [];
  for(const k of Object.keys(catalog)){
    const nm = prettyCropName(k);
    const kk = normCropName(nm);
    const meta = catalog[k] || catalog[kk] || null;
    if(!meta) continue;
    const baseWater = safeNum(meta.waterPerDa || meta.water_m3_da || meta.su_m3_da || meta.water);
    const baseProfit = safeNum(meta.profitPerDa || meta.net_kar_tl_da || meta.kar_tl_da || meta.profit);
    if(baseWater<=0 && baseProfit<=0) continue;
    const season = inferSeasonFromCropName(nm);
    const irr = irrigationKeysForCrop(nm);
    const wpd = deliveredWaterPerDa(baseWater, irr.suggestedKey);
    pool.push({crop:nm, key:kk, season, wpd, profitPerDa: baseProfit});
  }

  const out = [];
  if(isTwoSeason){
    // Keep top-N per season to avoid huge cartesian product
    const summer = pool.filter(x=>x.season==='Yazlık' && !chosenSet.has(x.key));
    const winter = pool.filter(x=>x.season==='Kışlık' && !chosenSet.has(x.key));

    // Rank within season by the same objective
    const rank = (arr)=>{
      const tmp = arr.map(x=>{
        const tW = A * x.wpd;
        const tP = A * x.profitPerDa;
        return {...x, score: _scoreCandidate(tW, tP)};
      });
      tmp.sort((a,b)=>a.score-b.score);
      return tmp.slice(0,10);
    };
    const topS = rank(summer);
    const topW = rank(winter);

    for(const s of topS){
      for(const w of topW){
        const tW = A*s.wpd + A*w.wpd; // same area used in different seasons
        const tP = A*s.profitPerDa + A*w.profitPerDa;
        const score = _scoreCandidate(tW, tP);
        const label = `Yazlık: ${s.crop} + Kışlık: ${w.crop}`;
        out.push({crop: label, water:tW, profit:tP, eff:tP/Math.max(1,tW), score});
      }
    }
  }else{
    for(const x of pool){
      if(chosenSet.has(x.key)) continue;
      const tW = A * x.wpd;
      const tP = A * x.profitPerDa;
      const score = _scoreCandidate(tW, tP);
      out.push({crop:x.crop, water:tW, profit:tP, eff:tP/Math.max(1,tW), score});
    }
  }

  out.sort((a,b)=>a.score-b.score);
  return out.slice(0,6);
}

function _whyNotText(chosenTotals, cand){
  const w0 = safeNum(chosenTotals?.water);
  const p0 = safeNum(chosenTotals?.profit);
  const w = safeNum(cand?.water);
  const p = safeNum(cand?.profit);
  const reasons = [];
  if(w0>0 && w > w0*1.05) reasons.push('Su daha yüksek');
  if(p0>0 && p < p0*0.95) reasons.push('Kâr daha düşük');
  if(!reasons.length) reasons.push('Hedef fonksiyon puanı daha düşük');
  return reasons.join(' • ');
}

function renderOfficialAllParcelCompare(basin){
  const tbody = document.querySelector('#tblOfficialAllParcelCompare tbody');
  const btn = document.getElementById('btnExportAllParcelCompareCsv');
  const noteEl = document.getElementById('allParcelCompareNote');
  if(!tbody) return;

  // Current vs recommended:
  // - Prefer the last cached basin optimization if present.
  // - Otherwise, generate an on-the-fly recommendation using the *currently selected* scenario+algorithm
  //   so that this official table is always informative without requiring a manual "Optimizasyonu Çalıştır".
  tbody.innerHTML = '';

  const hasCachedPlan = !!(basin && basin.plan && Object.keys(basin.plan||{}).length);
  if(noteEl){
    noteEl.textContent = hasCachedPlan
      ? 'Not: Öneriler, son "Optimizasyonu Çalıştır" sonucuyla senkron tutulur.'
      : 'Not: Öneriler, seçili senaryo + algoritma ile anlık üretilir (henüz toplu optimizasyon çalıştırılmadı).';
  }

  const rowsForCsv = [[
    'Parsel','Alan_da',
    'Mevcut_Desen','Mevcut_Su_m3','Mevcut_Kar_TL',
    'Oneri_Desen','Oneri_Su_m3','Oneri_Kar_TL',
    'Delta_Su_m3','Delta_Kar_TL'
  ]];

  for(const p of (parcelData||[])){
    ensureCurrentPattern(p);
    const curRows = (p.cropCurrent||[]).map(r=>({
      name: r.name,
      season: r.season || '—',
      area: +r.area || +p.area_da || 0,
      waterPerDa: +r.waterPerDa || 0,
      profitPerDa: +r.profitPerDa || 0,
    }));

    let rec = basin?.plan?.[p.id]?.rows || [];
    let recWasGenerated = false;
    if(!Array.isArray(rec) || !rec.length){
      // On-the-fly recommendation (uses current UI selections: season source, objective, etc.)
      try{
        const r = runOptimization(p, selectedScenario, selectedAlgo);
        if(r && Array.isArray(r.rows) && r.rows.length){
          rec = r.rows;
          recWasGenerated = true;
        }
      }catch(e){
        rec = [];
      }
    }
    // v57b: keep parcel-level areas sane in the official compare table too
    if(Array.isArray(rec) && rec.length){
      rec = normalizeRowsBySeasonToParcelArea(p.area_da, rec);
    }

    const curTot = _computeTotalsFromRows(curRows);
    const recTot = _computeTotalsFromRows(rec);

    const dW = recTot.water - curTot.water;
    const dP = recTot.profit - curTot.profit;

    const curLabel = _rowsToLabel(curRows);
    const recLabel = rec && rec.length
      ? (_rowsToLabel(rec) + (recWasGenerated ? ' <span class="badge badge-soft" style="margin-left:6px;">Anlık</span>' : ''))
      : '<span class="muted">Öneri üretilemedi</span>';

    // Alternatives (top candidates)
    const alt = (rec && rec.length) ? _alternativeCandidatesForParcel(p, rec) : [];
    let altHtml = '<span class="muted">—</span>';
    if(alt.length){
      const chosenT = recTot;
      const trs = alt.map(a=>`
        <tr>
          <td>${a.crop}</td>
          <td>${_fmtNum(a.water)}</td>
          <td>${_fmtNum(a.profit)}</td>
          <td>${a.eff.toFixed(2)}</td>
          <td class="muted">${_whyNotText(chosenT,a)}</td>
        </tr>`).join('');
      altHtml = `
        <details class="compare-details">
          <summary>⚖️ Kıyasla</summary>
          <div class="compare-popover">
            <table class="data-table" style="width:100%;">
              <thead>
                <tr><th>Alternatif ürün</th><th>Su (m³)</th><th>Kâr (TL)</th><th>TL/m³</th><th>Neden seçilmedi?</th></tr>
              </thead>
              <tbody>${trs}</tbody>
            </table>
          </div>
        </details>`;
    }

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${p.name || p.id}</td>
      <td>${_fmtNum(p.area_da,1)}</td>
      <td>${curLabel}</td>
      <td>${_fmtNum(curTot.water)}</td>
      <td>${_fmtNum(curTot.profit)}</td>
      <td>${recLabel}</td>
      <td>${rec && rec.length ? _fmtNum(recTot.water) : '—'}</td>
      <td>${rec && rec.length ? _fmtNum(recTot.profit) : '—'}</td>
      <td>${rec && rec.length ? (dW>=0?'+':'') + _fmtNum(dW) : '—'}</td>
      <td>${rec && rec.length ? (dP>=0?'+':'') + _fmtNum(dP) : '—'}</td>
      <td>${altHtml}</td>
    `;
    tbody.appendChild(tr);

    rowsForCsv.push([
      (p.name||p.id),
      (+p.area_da||0).toFixed(1),
      (curRows||[]).map(r=>`${r.season||''}:${r.name}`).join(' | '),
      Math.round(curTot.water),
      Math.round(curTot.profit),
      (rec||[]).map(r=>`${r.season||''}:${r.name}`).join(' | '),
      Math.round(recTot.water),
      Math.round(recTot.profit),
      Math.round(dW),
      Math.round(dP)
    ]);
  }

  if(btn && !btn._bound){
    btn._bound = true;
    btn.addEventListener('click', ()=>{
      downloadTextFile(`akkaya_parsel_karsilastirma_${selectedScenario}_${selectedAlgo}.csv`, asCsv(rowsForCsv), 'text/csv;charset=utf-8');
    });
  }
}


// Ürün kataloğu (demo parametreler) — optimizasyon motoru bu tabloyu kullanır
let cropCatalog = [
  { name: "ELMA", type: "meyve", waterPerDa: 750, profitPerDa: 17000 },
  { name: "ARMUT", type: "meyve", waterPerDa: 700, profitPerDa: 15000 },
  { name: "KAYISI", type: "meyve", waterPerDa: 650, profitPerDa: 16000 },
  { name: "KİRAZ", type: "meyve", waterPerDa: 820, profitPerDa: 22000 },
  { name: "VİŞNE", type: "meyve", waterPerDa: 750, profitPerDa: 16000 },
  { name: "ŞEFTALİ", type: "meyve", waterPerDa: 760, profitPerDa: 18000 },
  { name: "BUĞDAY", type: "tarla", waterPerDa: 450, profitPerDa: 1400 },
  { name: "ARPA", type: "tarla", waterPerDa: 420, profitPerDa: 1200 },
  { name: "NOHUT", type: "tarla", waterPerDa: 280, profitPerDa: 1900 },
  { name: "PATATES", type: "sebze", waterPerDa: 620, profitPerDa: 7800 },
  { name: "MISIR_SILAJ", type: "tarla", waterPerDa: 600, profitPerDa: 3200 },
];


// ------------------------------------------------------------
// CSV / gerçek veri bağlama katmanı
// - data/urun_parametreleri_demo.csv  -> cropCatalog güncellenir
// - data/parsel_su_kar_ozet.csv       -> P1..Px özetleri (alan/su/kâr, köy/ilçe) güncellenir
// Not: Tarayıcı güvenliği nedeniyle bu dosyalar "file://" ile açıldığında fetch çalışmayabilir.
// VS Code "Live Server" ile açmanız önerilir. Alternatif olarak üstteki dosya seçiciyle yüklenebilir.
// ------------------------------------------------------------

function parseDelimited(text, delimiter=';'){
  const lines = text.replace(/\r/g,'').split('\n').filter(l=>l.trim().length>0);
  if(lines.length < 2) return [];
  const headers = lines[0].split(delimiter).map(h=>h.trim());
  const rows = [];
  for(let i=1;i<lines.length;i++){
    const cols = lines[i].split(delimiter);
    const obj = {};
    for(let j=0;j<headers.length;j++){
      obj[headers[j]] = (cols[j] ?? '').trim();
    }
    rows.push(obj);
  }
  return rows;
}

function toNumberTR(x){
  // "1.234,56" veya "1234.56" gelebilir
  if(x==null) return NaN;
  const s = String(x).trim();
  if(!s) return NaN;
  // Not: Eski yaklaşım tüm noktaları (.) kaldırıyordu; bu da "5.8" gibi ondalık
  // değerleri yanlışlıkla 58'e çevirip parsel alanı gibi kritik metrikleri bozuyordu.
  // Bu yüzden hem TR (1.234,56) hem EN (1234.56) formatını güvenli şekilde destekle.

  let norm = s;
  const hasComma = norm.includes(',');
  const hasDot = norm.includes('.');

  if (hasComma) {
    // TR tipi: 1.234,56  veya  1234,56
    // Binlik ayırıcı noktaları kaldır, ondalık virgülü noktaya çevir.
    norm = norm.replace(/\./g, '').replace(/,/g, '.');
  } else if (hasDot) {
    // EN tipi: 1234.56  (noktayı kaldırma!)
    // Ancak tamamen binlik ayırıcı ise (1.234.567) nokta kaldır.
    if (/^\d{1,3}(\.\d{3})+$/.test(norm)) {
      norm = norm.replace(/\./g, '');
    }
  }

  const v = Number(norm);
  return Number.isFinite(v) ? v : NaN;
}

function cropTypeFromCategory(cat){
  const c = (cat||'').toLowerCase();
  if(c.includes('meyve')) return 'meyve';
  if(c.includes('sebze')) return 'sebze';
  return 'tarla';
}

function soilSuitabilityTlPerDa(soil, cropType){
  // Basit kurallar (demo): su tutma düşükse suyu çok isteyen gruplar cezalanır,
  // erozyon yüksekse çıplak toprak bırakan/yoğun sürüm gerektiren gruplar cezalanır.
  const tex = (soil.texture||"").toLowerCase();
  const ero = (soil.erosion||"").toLowerCase();

  let score = 0; // TL/da
  const lowRetention = tex.includes("kum") || tex.includes("düşük");
  const highRetention = tex.includes("killi") || tex.includes("yüksek");
  const highErosion = ero.includes("yüksek");

  if(lowRetention){
    if(cropType==="sebze" || cropType==="meyve") score -= 650;
    if(cropType==="tahil" || cropType==="baklagil") score -= 250;
    if(cropType==="yem") score -= 150;
  }
  if(highRetention){
    if(cropType==="sebze") score += 220;
    if(cropType==="yem" || cropType==="tahil") score += 120;
  }
  if(highErosion){
    if(cropType==="sebze") score -= 420;
    if(cropType==="tahil") score -= 180;
    if(cropType==="meyve") score += 120; // çok yıllık kök sistemi (temkinli bonus)
  }
  return score;
}


function buildCropCatalogFromRows(rows){
  // CSV kolonları: urun;kategori;kc_ortalama;su_tuketimi_m3_da;beklenen_verim_kg_da;fiyat_tl_kg;degisken_maliyet_tl_da
  const list = [];
  for(const r of rows){
    const name = (r.urun || '').trim();
    if(!name) continue;
    const waterPerDa = toNumberTR(r.su_tuketimi_m3_da);
    const yieldKgDa = toNumberTR(r.beklenen_verim_kg_da);
    const priceTlKg = toNumberTR(r.fiyat_tl_kg);
    const costTlDa = toNumberTR(r.degisken_maliyet_tl_da);
    // net kâr (da) = verim* fiyat - maliyet
    const profitPerDa = (Number.isFinite(yieldKgDa) && Number.isFinite(priceTlKg) ? yieldKgDa*priceTlKg : 0) - (Number.isFinite(costTlDa) ? costTlDa : 0);
    list.push({
      name,
      type: cropTypeFromCategory(r.kategori),
      waterPerDa: Number.isFinite(waterPerDa) ? waterPerDa : 0,
      profitPerDa: Math.round(profitPerDa)
    });
  }
  // Keep dryland options (waterPerDa can be 0).
  return list.filter(c=>isFinite(c.waterPerDa) && c.waterPerDa>=0 && c.name.length>0);
}

function applyParcelSummaryRows(rows){
  // CSV kolonları: parsel_id;toprak_kodu;koy;ilce;alan_da;mevcut_su_m3;mevcut_kar_tl
  const byId = new Map(rows.map(r=>[(r.parsel_id||'').trim(), r]));
  for(const p of parcelData){
    const r = byId.get(p.id);
    if(!r) continue;
    const area = toNumberTR(r.alan_da);
    const water = toNumberTR(r.mevcut_su_m3);
    const profit = toNumberTR(r.mevcut_kar_tl);

    if(Number.isFinite(area)) p.area_da = area;
    if(Number.isFinite(water)) p.water_m3 = water;
    if(Number.isFinite(profit)) p.profit_tl = profit;

    if(r.koy) p.village = r.koy;
    if(r.ilce) p.district = r.ilce;

    // isimde toprak kodunu da göster
    const soilCode = (r.toprak_kodu||'').trim();
    if(soilCode){
      p.name = `${p.id} – ${soilCode} (${p.village})`;
    }
    // toprak özeti alanına da geçir
    if(soilCode){
      p.soil = p.soil || {};
      p.soil.soilCode = soilCode;
    }
  }

  // select option label güncelle
  if(parcelSelectEl){
    for(const opt of Array.from(parcelSelectEl.options)){
      const p = parcelData.find(x=>x.id===opt.value);
      if(p) opt.textContent = p.name;
    }
  }
}

async function loadCsvFromProject(){
  // STRICT: load from ENHANCED dataset inside data/enhanced_dataset
  await loadDataPackageA();
}


async function loadCsvFromFiles(fileList){
  const files = Array.from(fileList || []);
  const byName = new Map(files.map(f=>[f.name.toLowerCase(), f]));
  // Kullanıcı farklı isimlerle seçebilir; içerikten de ayırt edebiliriz ama demo için isim yeterli
  const fUrun = files.find(f=>f.name.toLowerCase().includes("urun")) || byName.get("urun_parametreleri_demo.csv");
  const fParsel = files.find(f=>f.name.toLowerCase().includes("parsel")) || byName.get("parsel_su_kar_ozet.csv");

  if(!fUrun && !fParsel) throw new Error("CSV dosyaları bulunamadı (urun_parametreleri_demo.csv ve parsel_su_kar_ozet.csv).");

  if(fUrun){
    const urunText = await fUrun.text();
    const cropRows = parseDelimited(urunText,';');
    const newCatalog = buildCropCatalogFromRows(cropRows);
    if(newCatalog.length>0) cropCatalog = newCatalog;
  }
  if(fParsel){
    const parselText = await fParsel.text();
    const parselRows = parseDelimited(parselText,';');
    applyParcelSummaryRows(parselRows);
  }
}

function setDataBadge(ok, label){
  const badge = document.getElementById("dataLoadBadge");
  const src = document.getElementById("dataSourceLabel");
  if(src && label) src.textContent = label;
  if(!badge) return;
  badge.classList.remove("badge-warn","badge-ok","badge-err");
  if(ok===true){
    badge.classList.add("badge-ok");
    badge.textContent = "CSV bağlandı";
  }else if(ok===false){
    badge.classList.add("badge-err");
    badge.textContent = "CSV yüklenemedi";
  }else{
    badge.classList.add("badge-warn");
    badge.textContent = "CSV bağlanmadı";
  }
}


function applyS1RulesFromBackend(){
  try{
    const meta = STATE.backendMeta || {};
    const rules = meta.s1_crop_rules || null;
    if(!rules) return;
    const prim = Object.keys(rules);
    if(prim.length>0){
      S1_PRIMARY_CROPS = prim.slice();
      S1_PAIRING = {};
      const secSet = new Set();
      for(const c1 of prim){
        const r = rules[c1] || {};
        const secondary = (r.secondary_options || []).slice();
        for(const c2 of secondary) secSet.add(c2);
        S1_PAIRING[c1] = {
          season1: r.season1 || '—',
          irr1: r.irrigation1_current || '—',
          secondary: secondary.length ? secondary : ['—'],
          season2: r.season2 || '—',
          irr2: r.irrigation2_current || '—'
        };
      }
      S1_SECONDARY_CROPS = Array.from(secSet).sort();
    }
  }catch(e){
    console.warn('S1 kuralları uygulanamadı', e);
  }
}

async function fetchBackendMeta(){
  try{
    const r = await fetch('/api/meta');
    const j = await r.json();
    if(j && j.status==='OK'){
      STATE.backendMeta = j.backend || null;
      applyS1RulesFromBackend();
    }
  }catch(e){
    console.warn('api/meta okunamadı', e);
  }
}


function renderActiveFiles(){
  const box = document.getElementById('activeFilesBadges') || document.getElementById('activeFilesText');
  if(!box) return;

  const baseName = (p)=>{
    if(!p) return '';
    const s = String(p);
    const parts = s.split(/[/\\]/);
    return parts[parts.length-1] || s;
  };

  const badges = [];

  // Backend (Python)
  const b = STATE.backendMeta;
  if(b && b.files){
    const f = b.files;
    const s = STATE.seasonSource || 's1';
    const seasons = (s==='s1') ? baseName(f.seasons1) : (s==='s2') ? baseName(f.seasons2) : `${baseName(f.seasons1)} + ${baseName(f.seasons2)}`;
    // Çekirdek (optimizasyonda aktif kullanılan)
    badges.push({cls:'backend', label: baseName(f.parcels) || 'parcel_assumptions.csv'});
    badges.push({cls:'season', label: seasons || 'seasons.csv'});
    badges.push({cls:'reservoir', label: baseName(f.reservoir) || 'reservoir.csv'});
    if(f.irrigation_methods) badges.push({cls:'optional', label: baseName(f.irrigation_methods)});
    if(f.delivery) badges.push({cls:'optional', label: baseName(f.delivery)});

    // Paket envanteri (projede bulunan diğer CSV'ler)
    if(Array.isArray(b.files_available) && b.files_available.length){
      const coreSet = new Set(Object.values(f).map(x=>baseName(x)));
      for(const fp of b.files_available){
        const bn = baseName(fp);
        if(!bn) continue;
        if(coreSet.has(bn)) continue;
        badges.push({cls:'optional', label: bn});
      }
    }
  }else{
    // Project CSV (browser-side)
    const f = DATA_FILES?.enhanced || {};
    const s = STATE.seasonSource || 's1';
    const seasons = (s==='s1') ? baseName(f.senaryo1SeasonsCsv)
      : (s==='s2') ? baseName(f.senaryo2SeasonsCsv)
      : `${baseName(f.senaryo1SeasonsCsv)} + ${baseName(f.senaryo2SeasonsCsv)}`;
    if(f.parcelAssumptionsCsv) badges.push({cls:'backend', label: baseName(f.parcelAssumptionsCsv)});
    if(seasons && seasons!=='undefined') badges.push({cls:'season', label: seasons});
    if(f.reservoirMonthlyCsv) badges.push({cls:'reservoir', label: baseName(f.reservoirMonthlyCsv)});
  }

  // Manual user files
  if(STATE.userFiles && STATE.userFiles.length){
    for(const p of STATE.userFiles){
      badges.push({cls:'manual', label: baseName(p)});
    }
  }

  // Render
  if(box.id === 'activeFilesBadges'){
    box.innerHTML = '';
    if(!badges.length){
      box.innerHTML = '<span class="file-badge"><span class="dot"></span>–</span>';
      return;
    }
    for(const b of badges){
      const span = document.createElement('span');
      span.className = `file-badge ${b.cls||''}`;
      const dot = document.createElement('span');
      dot.className = 'dot';
      span.appendChild(dot);
      const txt = document.createElement('span');
      txt.textContent = b.label;
      span.appendChild(txt);
      box.appendChild(span);
    }
  }else{
    // fallback to old text span if present
    box.textContent = badges.length ? badges.map(x=>x.label).join(' • ') : '–';
  }
}

async function initDataBinding(){
  // UI event hooks
  const fileInput = document.getElementById("dataFileInput");
  const loadBtn = document.getElementById("loadDefaultCsvBtn");

  if(loadBtn){
    loadBtn.addEventListener("click", async ()=>{
      try{
        setDataBadge(null, "Projeden CSV");
        await loadCsvFromProject();
        // önbellek sıfırla (parametreler değişti)
        for(const k of Object.keys(optimizationCache)) delete optimizationCache[k];
        for(const k of Object.keys(basinPlanCache)) delete basinPlanCache[k];
        renderParcelSummary();
        renderTables();
        renderAllScenarioSummaries();
        STATE.userFiles = [];
        setDataBadge(true, "Projeden CSV");
        renderActiveFiles();
      }catch(e){
        console.error(e);
        setDataBadge(false, "Projeden CSV");
        alert("Projeden CSV okunamadı. Live Server ile açtığından emin ol.\n\nHata: " + (e?.message||e));
      }
    });
  }

  if(fileInput){
    fileInput.addEventListener("change", async ()=>{
      try{
        setDataBadge(null, "Manuel seçim");
        await loadCsvFromFiles(fileInput.files);
        for(const k of Object.keys(optimizationCache)) delete optimizationCache[k];
        for(const k of Object.keys(basinPlanCache)) delete basinPlanCache[k];
        renderParcelSummary();
        renderTables();
        renderAllScenarioSummaries();
        STATE.userFiles = Array.from(fileInput.files||[]).map(f=>f.name);
        setDataBadge(true, "Manuel seçim");
        renderActiveFiles();
      }catch(e){
        console.error(e);
        setDataBadge(false, "Manuel seçim");
        alert("CSV yüklenemedi.\n\nHata: " + (e?.message||e));
      }
    });
  }

  // --- canlı meteoroloji UI ---
  const weatherSourceSel = document.getElementById("weatherSourceSel");
  const weatherLat = document.getElementById("weatherLat");
  const weatherLon = document.getElementById("weatherLon");
  const weatherStart = document.getElementById("weatherStart");
  const weatherEnd = document.getElementById("weatherEnd");
  const btnFetchWeather = document.getElementById("btnFetchWeather");
  const weatherStatus = document.getElementById("weatherStatus");

  if(weatherLat && !weatherLat.value) weatherLat.value = DEFAULT_COORDS.lat;
  if(weatherLon && !weatherLon.value) weatherLon.value = DEFAULT_COORDS.lon;

  // Varsayılan tarih aralığı: içinde bulunulan yılın Nisan–Ekim dönemi
  const y = new Date().getFullYear();
  if(weatherStart && !weatherStart.value) weatherStart.value = `${y}-04-01`;
  if(weatherEnd && !weatherEnd.value) weatherEnd.value = `${y}-10-31`;

  if(weatherSourceSel){
    STATE.weatherSource = weatherSourceSel.value;
    weatherSourceSel.addEventListener("change", ()=>{
      STATE.weatherSource = weatherSourceSel.value;
      if(weatherStatus){
        weatherStatus.textContent = (STATE.weatherSource==="openmeteo") ? "Online (hazır)" : "Offline";
      }
      refreshUI();
    });
  }

  if(btnFetchWeather){
    btnFetchWeather.addEventListener("click", async ()=>{
      try{
        // Kullanıcı offline seçtiyse ağ isteği atma
        const sel = (weatherSourceSel?.value || STATE.weatherSource || "offline");
        // OFFLINE: monthly_climate_all_parcels.csv üzerinden seçilen tarih aralığına göre
        // (toplam ET0/yağış) parsel iklim özetini güncelle ve dinamik sulama hesabını aktif et.
        if(sel !== "openmeteo"){
          const s = (weatherStart?.value || `${y}-04-01`).trim();
          const e = (weatherEnd?.value || `${y}-10-31`).trim();
          if(!/^\d{4}-\d{2}-\d{2}$/.test(s) || !/^\d{4}-\d{2}-\d{2}$/.test(e)) throw new Error("Tarih formatı geçersiz (YYYY-AA-GG olmalı)");
          const p = parcelData.find(x=>x.id===selectedParcelId);
          if(!p) throw new Error("Seçili parsel bulunamadı");
          const agg = computeOfflineClimateRangeForParcel(p.id, s, e);
          if(!agg) throw new Error("Offline iklim verisi bulunamadı (monthly_climate_all_parcels.csv)");
          p.climate = p.climate || {};
          p.climate.eto_mm = Math.round(agg.eto_mm);
          p.climate.rain_mm = Math.round(agg.rain_mm);
          if(isFinite(agg.t_avg)) p.climate.t_avg = +agg.t_avg.toFixed(1);
          STATE.weatherSource = "offline";
          STATE.weatherDaily = null;
          STATE.weatherStart = s;
          STATE.weatherEnd = e;
          STATE.dynamicIrrigation = true;
          if(weatherSourceSel) weatherSourceSel.value = "offline";
          if(weatherStatus) weatherStatus.textContent = `Offline: ${s} → ${e}`;
          for(const k of Object.keys(optimizationCache)) delete optimizationCache[k];
          for(const k of Object.keys(basinPlanCache)) delete basinPlanCache[k];
          refreshUI();
          return;
        }

        if(weatherStatus) weatherStatus.textContent = "Yükleniyor...";
        const lat = parseNumFlex(weatherLat?.value, DEFAULT_COORDS.lat);
        const lon = parseNumFlex(weatherLon?.value, DEFAULT_COORDS.lon);
        const s = (weatherStart?.value || `${y}-04-01`).trim();
        const e = (weatherEnd?.value || `${y}-10-31`).trim();
        if(!Number.isFinite(lat) || !Number.isFinite(lon)) throw new Error("Enlem/Boylam geçersiz");
        if(!/^\d{4}-\d{2}-\d{2}$/.test(s) || !/^\d{4}-\d{2}-\d{2}$/.test(e)) throw new Error("Tarih formatı geçersiz (YYYY-AA-GG olmalı)");
        const daily = await fetchWeatherOpenMeteo(lat, lon, s, e);
        STATE.weatherDaily = daily;
        STATE.weatherSource = "openmeteo";
        STATE.weatherStart = s;
        STATE.weatherEnd = e;
        if(weatherSourceSel) weatherSourceSel.value = "openmeteo";
        if(weatherStatus) weatherStatus.textContent = `Online: ${daily.length} gün`;
        // Seçili parselin kaba iklim özetini de güncelle (grafik/planlarda tutarlılık)
        const p = parcelData.find(x=>x.id===selectedParcelId);
        if(p){
          const etoSum = daily.reduce((a,r)=>a+r.et0_mm,0);
          const rainSum = daily.reduce((a,r)=>a+r.rain_mm,0);
          p.climate = p.climate || {};
          p.climate.eto_mm = +(etoSum.toFixed(0));
          p.climate.rain_mm = +(rainSum.toFixed(0));
        }
        STATE.dynamicIrrigation = true;
        // katalog su/da değerlerini tekrar hesapla (ET0×Kc hattı)
        for(const k of Object.keys(optimizationCache)) delete optimizationCache[k];
        for(const k of Object.keys(basinPlanCache)) delete basinPlanCache[k];
        refreshUI();
      }catch(e){
        console.error(e);
        if(weatherStatus) weatherStatus.textContent = "Hata";
        alert("Meteoroloji verisi alınamadı.\n\nHata: "+(e?.message||e));
      }
    });
  }

  // --- pazar fiyatı / teşvik UI ---
  const marketSourceSel = document.getElementById("marketSourceSel");
  const marketUrl = document.getElementById("marketUrl");
  const btnLoadMarket = document.getElementById("btnLoadMarket");
  const marketStatus = document.getElementById("marketStatus");

  if(marketSourceSel){
    STATE.marketSource = marketSourceSel.value;
    marketSourceSel.addEventListener("change", ()=>{
      STATE.marketSource = marketSourceSel.value;
      if(marketStatus) marketStatus.textContent = (STATE.marketSource==="url") ? "URL" : "Yerel";
    });
  }

  if(btnLoadMarket){
    btnLoadMarket.addEventListener("click", async ()=>{
      try{
        // YEREL katalog: projeye gömülü demo CSV (sunum için pratik)
        if(STATE.marketSource!=="url"){
          const fp = DATA_FILES?.enhanced?.marketOverridesDemoCsv;
          if(!fp) throw new Error("Yerel fiyat/teşvik CSV tanımlı değil");
          if(marketStatus) marketStatus.textContent = "Yerel yükleniyor...";
          const txt = await fetchText(fp);
          const records = parseCsv(txt);
          const n = applyMarketOverrides(records);
          if(marketStatus) marketStatus.textContent = `Yerel yüklendi (${n})`;
          for(const k of Object.keys(optimizationCache)) delete optimizationCache[k];
          for(const k of Object.keys(basinPlanCache)) delete basinPlanCache[k];
          refreshUI();
          return;
        }
        const url = (marketUrl?.value||"").trim();
        if(!url) { alert("Lütfen fiyat/teşvik URL gir."); return; }
        if(marketStatus) marketStatus.textContent = "Yükleniyor...";
        const txt = await fetchText(url);
        let records = [];
        if(url.toLowerCase().endsWith(".json")){
          const j = JSON.parse(txt);
          records = Array.isArray(j) ? j : (j.records||j.data||[]);
        }else{
          records = parseCsv(txt);
        }
        const n = applyMarketOverrides(records);
        if(marketStatus) marketStatus.textContent = `Yüklendi (${n})`;
        // önbellek sıfırla
        for(const k of Object.keys(optimizationCache)) delete optimizationCache[k];
        for(const k of Object.keys(basinPlanCache)) delete basinPlanCache[k];
        refreshUI();
      }catch(e){
        console.error(e);
        if(marketStatus) marketStatus.textContent = "Hata";
        alert("Fiyat/teşvik verisi yüklenemedi.\n\nHata: "+(e?.message||e));
      }
    });
  }
}

// -------------------- Canlı meteoroloji (Open-Meteo) + detaylı Kc (FAO-56 stage) --------------------
const DEFAULT_COORDS = { lat: 37.97, lon: 34.68 }; // Niğde (yaklaşık)
function todayISO(){ return new Date().toISOString().slice(0,10); }
function isoWithOffsetDays(d, days){
  const x = new Date(d+"T00:00:00");
  x.setDate(x.getDate()+days);
  return x.toISOString().slice(0,10);
}

// Kc evreleri (ini/dev/mid/end) için varsayılanlar (FAO-56 tipik aralıklar – yaklaşık)
const CROP_STAGE_DEFAULTS = {
  "BUGDAY":       { ini:0.30, mid:1.15, end:0.25, Lini:25, Ldev:45, Lmid:50, Lend:30, sow:"10-15" }, // kışlık
  "ARPA":         { ini:0.30, mid:1.10, end:0.25, Lini:25, Ldev:40, Lmid:45, Lend:25, sow:"10-10" },
  "NOHUT":        { ini:0.35, mid:1.05, end:0.45, Lini:25, Ldev:35, Lmid:40, Lend:25, sow:"03-25" },
  "KURU FASULYE": { ini:0.35, mid:1.10, end:0.50, Lini:20, Ldev:30, Lmid:35, Lend:25, sow:"05-05" },
  "MISIR":        { ini:0.30, mid:1.20, end:0.60, Lini:20, Ldev:35, Lmid:40, Lend:30, sow:"04-20" },
  "SILAJLIK MISIR":{ini:0.30, mid:1.15, end:0.70, Lini:18, Ldev:30, Lmid:30, Lend:20, sow:"05-01" },
  "PATATES":      { ini:0.50, mid:1.15, end:0.75, Lini:25, Ldev:30, Lmid:35, Lend:25, sow:"04-05" },
  "SEKER PANCARI":{ ini:0.35, mid:1.20, end:0.80, Lini:25, Ldev:45, Lmid:60, Lend:40, sow:"03-20" },
  "DOMATES":      { ini:0.60, mid:1.15, end:0.80, Lini:25, Ldev:30, Lmid:45, Lend:20, sow:"05-10" },
  "ELMA":         { ini:0.60, mid:1.05, end:0.85, Lini:30, Ldev:40, Lmid:70, Lend:40, sow:"03-15" },
  "ARMUT":        { ini:0.60, mid:1.05, end:0.85, Lini:30, Ldev:40, Lmid:70, Lend:40, sow:"03-15" },
  "KIRAZ":        { ini:0.60, mid:1.05, end:0.85, Lini:30, Ldev:40, Lmid:70, Lend:40, sow:"03-15" },
  "SEFTALI":      { ini:0.60, mid:1.05, end:0.85, Lini:30, Ldev:40, Lmid:70, Lend:40, sow:"03-15" }
};

function stageParamsForCrop(cropName){
  const key = normCropName(cropName);
  // katalogda detay varsa onu öncelikle kullan
  const c = (STATE.cropCatalog?.[key] || {});
  const has = isFinite(c.kc_ini) && isFinite(c.kc_mid) && isFinite(c.kc_end) && isFinite(c.Lini);
  if(has){
    return { ini:+c.kc_ini, mid:+c.kc_mid, end:+c.kc_end, Lini:+c.Lini, Ldev:+c.Ldev, Lmid:+c.Lmid, Lend:+c.Lend, sow:c.sow || CROP_STAGE_DEFAULTS[key]?.sow || "04-01" };
  }
  return CROP_STAGE_DEFAULTS[key] || { ini:0.35, mid:1.05, end:0.50, Lini:20, Ldev:30, Lmid:40, Lend:20, sow:"04-01" };
}

function kcOnDay(cropName, day){
  const p = stageParamsForCrop(cropName);
  const total = p.Lini+p.Ldev+p.Lmid+p.Lend;
  const d = clamp(day, 0, total-1);
  if(d < p.Lini) return p.ini;
  if(d < p.Lini+p.Ldev){
    const t = (d - p.Lini)/Math.max(1, p.Ldev);
    return p.ini + t*(p.mid - p.ini);
  }
  if(d < p.Lini+p.Ldev+p.Lmid) return p.mid;
  // end stage linear decline mid->end
  const t = (d - (p.Lini+p.Ldev+p.Lmid))/Math.max(1, p.Lend);
  return p.mid + t*(p.end - p.mid);
}

// Open-Meteo: günlük ET0(FAO) + yağış (mm)
async function fetchWeatherOpenMeteo(lat, lon, startDate, endDate){
  // Open-Meteo: tarih aralığı geniş olduğunda "forecast" 400 döndürebilir.
  // Geçmiş tarih aralıklarında "archive" kullanıyoruz.
  const latN = parseFloat(String(lat).replace(",", "."));
  const lonN = parseFloat(String(lon).replace(",", "."));
  if(!Number.isFinite(latN) || !Number.isFinite(lonN)) throw new Error("Geçersiz enlem/boylam");

  const today = new Date();
  const todayISO = today.toISOString().slice(0,10); // YYYY-MM-DD
  const endpoint = (endDate && endDate <= todayISO) ? "archive" : "forecast";

  const params = new URLSearchParams({
    latitude: String(latN),
    longitude: String(lonN),
    start_date: startDate,
    end_date: endDate,
    daily: "et0_fao_evapotranspiration,precipitation_sum",
    timezone: "Europe/Istanbul"
  });

  const base = (endpoint==="archive") ? "https://archive-api.open-meteo.com/v1/archive" : "https://api.open-meteo.com/v1/forecast";
  const url = `${base}?${params.toString()}`;
  const res = await fetch(url);
  if(!res.ok) throw new Error(`Open-Meteo HTTP ${res.status}`);
  const j = await res.json();
  const time = j?.daily?.time || [];
  const et0 = j?.daily?.et0_fao_evapotranspiration || [];
  const pr  = j?.daily?.precipitation_sum || [];
  if(time.length===0 || et0.length!==time.length) throw new Error("Open-Meteo veri formatı beklenenden farklı");
  return time.map((t,i)=>({ date:t, et0_mm:+et0[i], rain_mm:+(pr[i] ?? 0) }));
}

function monthKeyFromISO(iso){
  return iso.slice(0,7); // YYYY-MM
}

function monthKeyToDate(monthKey){
  // monthKey: YYYY-MM -> Date(YYYY,MM-1,1)
  const parts = String(monthKey||"").split('-');
  const y = parseInt(parts[0],10);
  const m = parseInt(parts[1],10);
  if(!Number.isFinite(y) || !Number.isFinite(m)) return null;
  return new Date(y, m-1, 1);
}

function listMonthKeysBetween(startISO, endISO){
  // inclusive months, based on YYYY-MM
  const sKey = monthKeyFromISO(startISO);
  const eKey = monthKeyFromISO(endISO);
  const sD = monthKeyToDate(sKey);
  const eD = monthKeyToDate(eKey);
  if(!sD || !eD) return [];
  const out=[];
  let d = new Date(sD.getFullYear(), sD.getMonth(), 1);
  const end = new Date(eD.getFullYear(), eD.getMonth(), 1);
  while(d <= end){
    const y = d.getFullYear();
    const m = String(d.getMonth()+1).padStart(2,'0');
    out.push(`${y}-${m}`);
    d.setMonth(d.getMonth()+1);
  }
  return out;
}

function computeOfflineClimateRangeForParcel(parcelId, startISO, endISO){
  const rows = Array.isArray(STATE.climateMonthlyRows) ? STATE.climateMonthlyRows : null;
  if(!rows || !rows.length) return null;
  const pid = String(parcelId||"").trim();
  if(!pid) return null;
  const months = new Set(listMonthKeysBetween(startISO, endISO));
  if(!months.size) return null;

  let eto=0, rain=0, tSum=0, tN=0;
  for(const r of rows){
    const rid = String(r.parcel_id||r.parsel_id||r.id||"").trim();
    if(rid !== pid) continue;
    const mk = String(r.month||r.ay||r.date||"").trim().slice(0,7);
    if(!months.has(mk)) continue;
    eto  += safeNum(r.eto_mm ?? r.et0_mm ?? r.et0);
    rain += safeNum(r.rain_mm ?? r.precip_mm ?? r.precipitation_mm ?? r.precip);
    const t = safeNum(r.tavg_c ?? r.tavg ?? r.t_mean_c);
    if(isFinite(t)) { tSum += t; tN += 1; }
  }
  if(eto<=0 && rain<=0) return null;
  return { eto_mm: eto, rain_mm: rain, t_avg: (tN? (tSum/tN) : NaN) };
}

function sumByMonth(daily, startISO, days){
  const map = {};
  const startIdx = daily.findIndex(x=>x.date===startISO);
  if(startIdx<0) return map;
  for(let i=0;i<days;i++){
    const rec = daily[startIdx+i];
    if(!rec) break;
    const m = monthKeyFromISO(rec.date);
    if(!map[m]) map[m] = { et0:0, rain:0, n:0 };
    map[m].et0 += rec.et0_mm;
    map[m].rain += rec.rain_mm;
    map[m].n += 1;
  }
  return map;
}

function computeSeasonIrrigation(parcel, cropName){
  // kaynak seçimi: openmeteo ise STATE.weatherDaily, değilse parsel özet
  const eff = clamp(STATE.irrigEfficiency ?? 0.62, 0.45, 0.90);
  const p = stageParamsForCrop(cropName);
  const totalDays = p.Lini+p.Ldev+p.Lmid+p.Lend;

  if(STATE.weatherSource==="openmeteo" && Array.isArray(STATE.weatherDaily) && STATE.weatherDaily.length>10){
    // ekim tarihi: seçili yıl + p.sow (ay-gün)
    const year = (STATE.weatherStart || todayISO()).slice(0,4);
    const sowISO = `${year}-${p.sow}`;
    const monthAgg = sumByMonth(STATE.weatherDaily, sowISO, totalDays);
    let sumNet=0, sumGross=0, sumEtc=0, sumEffRain=0;

    // günlük hesap
    const startIdx = STATE.weatherDaily.findIndex(x=>x.date===sowISO);
    for(let d=0; d<totalDays; d++){
      const rec = STATE.weatherDaily[startIdx+d];
      if(!rec) break;
      const kc = kcOnDay(cropName, d);
      const etc = rec.et0_mm * kc;
      const effRain = 0.60 * rec.rain_mm;
      const net = Math.max(0, etc - effRain);
      const gross = net/eff;
      sumEtc += etc; sumEffRain += effRain; sumNet += net; sumGross += gross;
    }

    // aylık tablo için ETc ve sulama
    const monthly = [];
    for(const mk of Object.keys(monthAgg).sort()){
      const m = monthAgg[mk];
      // ay içi ortalama Kc yaklaşımı: gün içindeki kc değişir; burada kaba yaklaşım: mid Kc
      const kcMid = p.mid;
      const etc = m.et0 * kcMid;
      const effRain = 0.60*m.rain;
      const net = Math.max(0, etc - effRain);
      const gross = net/eff;
      monthly.push({ month: mk, eto: m.et0, rain: m.rain, kc: kcMid, etc, effRain, net, gross });
    }

    return { mode:"openmeteo", sowISO, totalDays, eff, sumEtc, sumEffRain, sumNet, sumGross, monthly };
  }

  // offline (parsel özetinden yıllık ETo/rain → kaba)
  const eto = parcel?.climate?.eto_mm;
  const rain = parcel?.climate?.rain_mm;
  if(!isFinite(eto) || !isFinite(rain)){
    return { mode:"none" };
  }
  const effRain = 0.60*rain;
  const kcAvg = kcAvgForCrop(cropName);
  const etc = eto * kcAvg;
  const net = Math.max(0, etc - effRain);
  const gross = net/eff;

  return { mode:"parcel", sowISO:null, totalDays, eff, sumEtc:etc, sumEffRain:effRain, sumNet:net, sumGross:gross, monthly:[] };
}

// -------------------- Pazar fiyatı / teşvik yükleme (URL) --------------------
async function fetchText(url){
  const res = await fetch(url);
  if(!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.text();
}

async function fetchJson(url){
  const r = await fetch(url, {cache:'no-store'});
  if(!r.ok) throw new Error(`HTTP ${r.status} for ${url}`);
  return await r.json();
}

// -------------------- API helper (POST JSON with timeout) --------------------
// Used by 15-year impact/profit tabs (and kept generic for future endpoints).
async function apiPostJSON(url, payload, optsOrTimeout=60000){
  // Backward compatible: third argument can be timeoutMs (number) or options {timeoutMs, signal}
  const opts = (typeof optsOrTimeout === 'object' && optsOrTimeout !== null) ? optsOrTimeout : { timeoutMs: optsOrTimeout };
  const timeoutMs = Math.max(1000, (opts.timeoutMs ?? 60000) | 0);
  const externalSignal = opts.signal;

  // Controller that we can timeout-abort, and also mirror an external abort signal if provided.
  const ctrl = new AbortController();
  const onAbort = () => { try { ctrl.abort(); } catch (e) {} };
  if (externalSignal) {
    if (externalSignal.aborted) onAbort();
    else externalSignal.addEventListener('abort', onAbort, { once: true });
  }
  const t = setTimeout(onAbort, timeoutMs);

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload ?? {}),
      signal: ctrl.signal,
    });
    const txt = await res.text();
    let j = null;
    try { j = txt ? JSON.parse(txt) : null; } catch (e) { j = null; }
    if (!res.ok) {
      const msgTxt = (j && (j.message || j.error)) ? (j.message || j.error) : (txt || `HTTP ${res.status}`);
      throw new Error(msg);
    }
    return j ?? {};
  } finally {
    clearTimeout(t);
    try { if (externalSignal) externalSignal.removeEventListener('abort', onAbort); } catch (e) {}
  }
}

function parseCsv(text){
  // Split into non-empty lines; support Windows and Unix newlines
  const rows = text.split(/\r?\n/).filter(x=>x.trim().length);
  if(rows.length<2) return [];
  const headerLine = rows[0];
  // delimiter auto-detect: ; or ,
  const delim = (headerLine.includes(";") && !headerLine.includes(",")) ? ";" : ",";
  const header = headerLine.split(delim).map(x=>x.trim());
  return rows.slice(1).map(line=>{
    const cols = line.split(delim);
    const obj={};
    header.forEach((h,i)=> obj[h]= (cols[i]||"").trim() );
    return obj;
  });
}
function applyMarketOverrides(records){
  // desteklenen kolonlar:
  // - urun | crop | name
  // - verim_kg_da | yield_kg_da
  // - fiyat_tl_kg | price_tl_kg
  // - degisken_maliyet_tl_da | cost_tl_da
  // - tesvik_tl_da | support_tl_da
  // - net_kar_tl_da | profit_tl_da | profitPerDa
  const cat = STATE.cropCatalog || {};
  let n=0;
  for(const r of records){
    const key = normCropName(r.urun || r.crop || r.name || "");
    if(!key || !cat[key]) continue;
    const yld = parseFloat(r.verim_kg_da ?? r.yield_kg_da ?? "");
    const price = parseFloat(r.fiyat_tl_kg ?? r.price_tl_kg ?? "");
    const costDa = parseFloat(r.degisken_maliyet_tl_da ?? r.cost_tl_da ?? "");
    const support = parseFloat(r.tesvik_tl_da ?? r.support_tl_da ?? 0);
    const profitDirect = parseFloat(r.net_kar_tl_da ?? r.profit_tl_da ?? r.profitPerDa ?? "");

    if(isFinite(yld)) cat[key].yield_kg_da = yld;
    if(isFinite(price)) cat[key].price_tl_kg = price;
    if(isFinite(costDa)) cat[key].cost_tl_da = costDa;
    if(isFinite(support)) cat[key].support_tl_da = support;

    // Profit: doğrudan verildiyse onu kullan; değilse (verim*fiyat - maliyet + teşvik)
    if(isFinite(profitDirect)){
      cat[key].profitPerDa = Math.round(profitDirect);
      cat[key]._profit_overridden = true;
    }else{
      const y = isFinite(cat[key].yield_kg_da) ? +cat[key].yield_kg_da : NaN;
      if(isFinite(y) && isFinite(cat[key].price_tl_kg) && isFinite(cat[key].cost_tl_da)){
        cat[key].profitPerDa = Math.round(y*cat[key].price_tl_kg - cat[key].cost_tl_da + (cat[key].support_tl_da||0));
        cat[key]._profit_overridden = true;
      }
    }
    n++;
  }
  STATE.cropCatalog = cat;
  STATE.marketOverridesActive = n>0;
  return n;
}


// Optimizasyon sonuç önbelleği: results[parcelId][scenario][algo] = { rows, totals }
const optimizationCache = {};

// Küresel su bütçesine göre (15 parsel birlikte) ayarlanmış plan cache
const basinPlanCache = {};

function basinCacheKey(scenarioKey, algoKey){
  const y = STATE.selectedWaterYear ?? 2024;
  const s = STATE.selectedProjScenario ?? "mevcut";
  // Candidate pool selector (Scenario-1 / Scenario-2). Must affect cache.
  const ss = (STATE.seasonSource || 's1');
  const w = Math.round(STATE.availableWaterM3 ?? 0);
  const r = Math.round((STATE.droughtRisk ?? 0)*1000);
  return `${scenarioKey}|${algoKey}|Y${y}|S${s}|SS${ss}|W${w}|R${r}`;
}

function deepCloneRows(rows){
  return rows.map(r=>({
    name: r.name,
    area: +r.area,
    waterPerDa: +r.waterPerDa,
    profitPerDa: +r.profitPerDa,
    totalWater: +r.totalWater,
    totalProfit: +r.totalProfit
  }));
}

function recomputeRowTotals(rows){
  for(const r of rows){
    r.totalWater = r.area * r.waterPerDa;
    r.totalProfit = r.area * r.profitPerDa;
  }
  return rows;
}

function computeGlobalBudgetM3(){
  const totalA = Math.max(1, STATE.totalAreaAllParcels || 1);

  // Estimate current total water need (m3) from parcel inputs (if present).
  // If availableWaterM3 is implausibly small (e.g., 600 m3) due to scaling/parsing issues,
  // fall back to a reasonable budget derived from current needs / area.
  let currentNeed = 0;
  if(Array.isArray(STATE.parcels) && STATE.parcels.length){
    currentNeed = STATE.parcels.reduce((a,p)=> a + (+p.water_m3 || 0), 0);
  }
  if(!isFinite(currentNeed) || currentNeed <= 0){
    // If parcel water_m3 missing, approximate using 600 m3/da baseline.
    currentNeed = totalA * 600;
  }

  let base = (STATE.availableWaterM3 ?? 0);
  const fallbackBase = Math.max(currentNeed, totalA * 600);

  // Treat very small or non-finite available water as invalid and fall back.
  // Threshold: less than 20% of current need is almost certainly a scaling bug for this demo.
  if(!isFinite(base) || base <= 0 || base < 0.20 * currentNeed){
    base = fallbackBase;
  }

  const risk = clamp(STATE.droughtRisk ?? 0, 0, 1);
  const factor = clamp(1 - 0.35*risk, 0.55, 1);
  return base * factor;
}


function makeRotationSuggestions(mainCrop){
  const c = normCropName(mainCrop || "");
  const legumes = ["NOHUT","MERCIMEK","FASULYE","KURU_FASULYE","BAKLAGIL"];
  const cereals = ["BUGDAY","ARPA","YULAF"];
  const tubers = ["PATATES"];
  const maize = ["MISIR","MISIR_SILAJ"];
  const sugar = ["SEKER_PANCARI","PANCAR"];
  const orch = ["ELMA","ARMUT","KIRAZ","SEFTALI","KAYISI"];

  const inList = (arr)=>arr.some(x=>c.includes(x));

  if(inList(orch)){
    return {
      title: "Meyve bahçesi",
      items: ["Bahçe bitkilerinde rotasyon sınırlıdır; öneri daha çok sulama verimliliği + örtü bitkisi / yeşil gübreleme üzerinedir.",
             "Sıra arası: baklagil yem bitkisi / fiğ gibi örtü bitkileri (su durumuna göre).",
             "Toprak organik maddesi için kompost/ahır gübresi (analize göre)."]
    };
  }
  if(inList(cereals)){
    return { title:"Tahıl sonrası", items:["Baklagil (nohut/mercimek) – azot bağlama ile toprak iyileştirme", "Yem bitkisi (fiğ/yonca) – su uygunsa", "Ayçiçeği gibi farklı familya (su-kâr dengesine göre)"] };
  }
  if(inList(legumes)){
    return { title:"Baklagil sonrası", items:["Tahıl (buğday/arpa) – hastalık döngüsünü kırar", "Yağ bitkisi (ayçiçeği) – su uygunsa", "Nadas / toprak dinlendirme (kurak yıl)"] };
  }
  if(inList(tubers) || inList(sugar) || inList(maize)){
    return { title:"Yüksek su isteyen ürün sonrası", items:["Tahıl veya baklagil – su baskısını düşürür", "Toprak yapısı için baklagil + minimum toprak işleme", "Bir sonraki sezon su bütçesine göre düşük su isteyen ürünlere geçiş"] };
  }
  return { title:"Genel öneri", items:["Farklı familyaya geçiş", "Baklagil ile toprağı güçlendirme", "Su bütçesine göre düşük su isteyen ürünlere yönelme"] };
}

function kcAvgForCrop(cropName){
  const c = normCropName(cropName||"");
  if(c.includes("MISIR")) return 1.15;
  if(c.includes("PATATES")) return 1.05;
  if(c.includes("PANCAR") || c.includes("SEKER")) return 1.10;
  if(c.includes("DOMATES") || c.includes("BIBER") || c.includes("KAVUN") || c.includes("KARPUZ")) return 1.05;
  if(c.includes("BUGDAY") || c.includes("BUĞDAY") || c.includes("ARPA") || c.includes("YULAF")) return 0.95;
  if(c.includes("NOHUT") || c.includes("MERCIMEK") || c.includes("FASULYE") || c.includes("BAKLAGIL")) return 0.85;
  // meyveler
  if(c.includes("ELMA") || c.includes("ARMUT") || c.includes("KIRAZ") || c.includes("SEFTALI") || c.includes("KAYISI")) return 0.90;
  return 0.95;
}

function estimateWaterPerDaFromETo(parcel, cropName, fallback){
  // 1 mm yağış/ET = 1 m3/da (1 da = 1000 m2)
  const eto = parcel?.climate?.eto_mm;
  const rain = parcel?.climate?.rain_mm;
  if(!isFinite(eto) || !isFinite(rain)) return fallback;
  const kc = kcAvgForCrop(cropName);
  const effRain = 0.60 * rain; // demo etkin yağış
  const etc = eto * kc;
  let netIrr = etc - effRain;
  // negatifse 0'a çek
  netIrr = Math.max(0, netIrr);
  // sulama randımanı (vahşi sulama -> daha fazla ihtiyaç)
  const eff = clamp(STATE.irrigEfficiency ?? 0.62, 0.45, 0.90);
  const gross = netIrr / eff;
  // makul aralık
  return clamp(Math.round(gross), 120, 950);
}

function renderIrrigationPlan(parcel, rows){
  const box = document.getElementById("irrigPlanBox");
  if(!box) return;

  const top = [...rows].sort((a,b)=>b.area-a.area).slice(0,3);
  if(top.length===0){
    box.textContent = "Ürün deseni bulunamadı.";
    return;
  }

  const eff = clamp(STATE.irrigEfficiency ?? 0.62, 0.45, 0.90);
  const lines = [];
  const src = (STATE.weatherSource==="openmeteo" && Array.isArray(STATE.weatherDaily)) ? "Open‑Meteo (günlük ET0/yağış)" : "Parsel özet iklim (yıllık)";
  lines.push(`<div><strong>Kaynak:</strong> ${src} — <strong>Sulama randımanı:</strong> ${(eff*100).toFixed(0)}%</div>`);

  // Senaryo-2 çok yıllık ürünlerde: ürün değişmez, asıl kazanç sulama stratejisinden gelir.
  // Bu durumda çiftçiye okunabilir bir "nasıl uygulanır" rehberi ekle.
  try{
    const dom = top[0]?.name;
    const seasonSource = (document.getElementById('seasonSourceSel')?.value) || STATE.seasonSource || 's1';
    if(seasonSource === 's2' && dom && isPerennialCropName(dom)){
      const cropLabel = prettyCropName(dom);
      lines.push(`
        <div style="margin-top:8px; padding:10px 12px; border-radius:10px; background:rgba(46,204,113,0.10);">
          <div><strong>${cropLabel} için sulama tavsiyesi (Senaryo-2)</strong></div>
          <ul style="margin:6px 0 0 18px;">
            <li><strong>Yöntem:</strong> Damla sulama + basınç regülasyonu; mümkünse nem sensörü/tansiyometre ile takip.</li>
            <li><strong>Zamanlama:</strong> Sabah erken/akşam (buharlaşma düşükken). Sıcak dalgalarında periyot sıklaştırıp her seferde daha az verin.</li>
            <li><strong>Kısıntılı sulama:</strong> Su tasarrufu modunda toplam suyu ~%10–20 azaltın; meyve tutumu döneminde aşırı kısıntı yapmayın.</li>
            <li><strong>Uygulama:</strong> Filtre temizliği, damlatıcı kontrolü, kaçak testi; haftalık kontrol rutini.</li>
            <li><strong>Toprak yönetimi:</strong> Malçlama/örtü bitkisi ile yüzey buharlaşmasını azaltın, organik maddeyi artırın.</li>
          </ul>
        </div>`);
    }
  }catch(_){/*no-op*/}

  let html = `<div style="margin-top:8px; overflow-x:auto;">
    <table class="tbl">
      <thead>
        <tr>
          <th>Ürün</th><th>Ekim</th><th>Gün</th>
          <th>ETc (mm)</th><th>Etkin yağış (mm)</th><th>Net (mm)</th><th>Brüt (mm)</th>
          <th>Brüt (m³/da)</th><th>Desende alan (da)</th><th>Toplam su (m³)</th>
        </tr>
      </thead>
      <tbody>`;

  for(const r of top){
    const p = stageParamsForCrop(r.name);
    const calc = computeSeasonIrrigation(parcel, r.name);
    if(calc.mode==="none"){
      html += `<tr><td>${r.name}</td><td>–</td><td>–</td><td colspan="7">İklim verisi yok</td></tr>`;
      continue;
    }
    const gross_m3_da = Math.round(calc.sumGross); // 1 mm = 1 m3/da
    const total = Math.round(gross_m3_da * r.area);
    html += `<tr>
      <td>${r.name}</td>
      <td>${(calc.sowISO || (p.sow ? p.sow : "—"))}</td>
      <td>${p.Lini+p.Ldev+p.Lmid+p.Lend}</td>
      <td>${calc.sumEtc.toFixed(0)}</td>
      <td>${calc.sumEffRain.toFixed(0)}</td>
      <td>${calc.sumNet.toFixed(0)}</td>
      <td>${calc.sumGross.toFixed(0)}</td>
      <td>${gross_m3_da.toLocaleString("tr-TR")}</td>
      <td>${r.area.toFixed(1)}</td>
      <td>${total.toLocaleString("tr-TR")}</td>
    </tr>`;

    // Aylık plan tablosu (varsa)
    if(calc.monthly && calc.monthly.length){
      html += `<tr><td colspan="10" style="background:rgba(255,255,255,0.04);">
        <div style="padding:8px 10px;">
          <div class="small" style="opacity:.9;margin-bottom:6px;"><strong>Aylık sulama özeti</strong> (kaba: ay içi Kc≈Kc_mid)</div>
          <div style="overflow-x:auto;">
            <table class="tbl small" style="margin:0;">
              <thead><tr>
                <th>Ay</th><th>ETo (mm)</th><th>Yağış (mm)</th><th>Kc</th><th>ETc (mm)</th><th>Etkin yağış</th><th>Net</th><th>Brüt</th>
              </tr></thead><tbody>`;
      for(const m of calc.monthly){
        html += `<tr>
          <td>${m.month}</td>
          <td>${m.eto.toFixed(0)}</td>
          <td>${m.rain.toFixed(0)}</td>
          <td>${m.kc.toFixed(2)}</td>
          <td>${m.etc.toFixed(0)}</td>
          <td>${m.effRain.toFixed(0)}</td>
          <td>${m.net.toFixed(0)}</td>
          <td>${m.gross.toFixed(0)}</td>
        </tr>`;
      }
      html += `</tbody></table></div></div></td></tr>`;
    }
  }

  html += `</tbody></table></div>`;
  box.innerHTML = lines.join("") + html;
}

function computeBasinPlan(scenarioKey, algoKey){
  const key = basinCacheKey(scenarioKey, algoKey);
  if(basinPlanCache[key]) return basinPlanCache[key];

  const plan = {};
  let totalWater = 0;
  let totalProfit = 0;

  // 1) her parsel için ham çözüm
  for(const p of parcelData){
    const res = getOptimizationResult(p.id, scenarioKey, algoKey);
    const rows = deepCloneRows(res.rows);
    plan[p.id] = { rows: recomputeRowTotals(rows), totals: sumMetrics(rows), irrigationPlan: res.irrigationPlan || null, lockedCrop: res.lockedCrop || null };
    totalWater += plan[p.id].totals.water;
    totalProfit += plan[p.id].totals.profit;
  }

  // 2) küresel su bütçesi kısıtı uygula (greedy alan kaydırma)
  let budget = computeGlobalBudgetM3();
  // Su tasarruf odaklı senaryoda, hedef su bütçesini "mevcut desen"e göre sıkılaştır.
  // Böylece model "kâr yüksek ama su da yüksek" çözümlere kaçamaz.
  if(scenarioKey === "su_tasarruf"){
    try{
      const baseKey = basinCacheKey("mevcut", algoKey);
      const base = basinPlanCache[baseKey] || computeBasinPlan("mevcut", algoKey);
      const baseWater = safeNum(base?.totals?.water);
      // hedef: mevcut suyun en az %15 altında
      const target = baseWater > 0 ? (baseWater * 0.85) : 0;
      if(target > 0) budget = Math.min(budget, target);
    }catch(_){ /* no-op */ }
  }
  let it = 0;
  const maxIt = 2500;
  while(totalWater > budget && it < maxIt){
    // en yüksek su yoğun parseli bul
    let worstId = null;
    let worstScore = -Infinity;
    for(const p of parcelData){
      const t = plan[p.id].totals;
      const score = t.water / Math.max(1, t.area); // m3/da
      if(score > worstScore){ worstScore = score; worstId = p.id; }
    }
    if(!worstId) break;
    const p = parcelData.find(x=>x.id===worstId);
    const rows = plan[worstId].rows;
    if(!rows || rows.length<2) break;
    // en su yoğun üründen en düşük su yoğun ürüne küçük kaydırma
    let hi = 0, lo = 0;
    for(let i=1;i<rows.length;i++){
      if(rows[i].waterPerDa > rows[hi].waterPerDa) hi=i;
      if(rows[i].waterPerDa < rows[lo].waterPerDa) lo=i;
    }
    if(hi===lo) break;
    const stepDa = Math.min(0.05 * p.area_da, rows[hi].area); // %5 adım
    if(stepDa <= 0.05){
      // daha küçük adım
      const small = Math.min(1.0, rows[hi].area);
      if(small <= 0) break;
      rows[hi].area -= small;
      rows[lo].area += small;
    }else{
      rows[hi].area = +(rows[hi].area - stepDa).toFixed(1);
      rows[lo].area = +(rows[lo].area + stepDa).toFixed(1);
    }
    recomputeRowTotals(rows);
    const newTotals = sumMetrics(rows);
    // toplamları güncelle
    totalWater = 0; totalProfit = 0;
    for(const pp of parcelData){
      plan[pp.id].totals = sumMetrics(plan[pp.id].rows);
      totalWater += plan[pp.id].totals.water;
      totalProfit += plan[pp.id].totals.profit;
    }
    it++;
  }

  const out = {
    plan,
    budget,
    totals: { water: totalWater, profit: totalProfit, eff: totalProfit/Math.max(1,totalWater) },
    iterations: it,
    feasible: totalWater <= budget + 1e-6
  };
  basinPlanCache[key] = out;
  return out;
}

async function fetchBenchmarkPython(scenarioKey, seasonSourceOverride=null){
  const algoMap = { ga: 'GA', abc: 'ABC', aco: 'ACO' };
  // Benchmark: "mevcut" deseni algoritmalar için anlamlı bir hedef değil (optimizasyon çalışmaz).
  // Bu yüzden "mevcut" seçiliyken kıyaslamayı "balanced" hedefinde koşturuyoruz ve ayrıca baseline (current) ekliyoruz.
  // v74: Proje hedefi her zaman su tasarrufu. "maks_kar" seçimi geriye dönük uyumluluk için
  // su tasarruf hedefiyle eşlenir.
  const scenarioMap = { mevcut: 'balanced', current: 'balanced', su_tasarruf: 'water_saving', maks_kar: 'water_saving', onerilen: 'balanced', recommended: 'balanced', balanced:'balanced', water_saving:'water_saving' };

  const repeatsEl = document.getElementById('benchmarkRepeats');
  const seedEl = document.getElementById('benchmarkSeed');
  const repeats = Math.max(1, Math.min(60, parseInt(repeatsEl?.value || '10', 10) || 10));
  const seedRaw = (seedEl?.value ?? '').toString().trim();
  const baseSeed = seedRaw === '' ? null : (parseInt(seedRaw, 10));

  const payload = {
    selectedParcelIds: getSelectedParcelIdsForRun(),
    scenario: scenarioMap[scenarioKey] || 'balanced',
    year: STATE.selectedWaterYear || null,
    waterBudgetRatio: budgetRatioForScenarioKey(scenarioKey),
    repeats,
    baseSeed,
    algorithms: ['GA','ABC','ACO'],
    includeBaseline: true,
    // allow enough time so each algorithm (GA/ABC/ACO) can run at least once
    maxSeconds: 120,
    options: {
      // Benchmark, UI'daki "Sezon veri seti" seçimine göre farklı aday havuzu üretir.
      // seasonSourceOverride verilirse onu kullan.
      seasonSource: (seasonSourceOverride || STATE.seasonSource || 's1'),
      twoSeason: true,
      // leave hyper-parameters empty so backend uses lightweight benchmark defaults
      generations: null,
      popSize: null,
      cycles: null,
      foodSources: null,
      ants: null,
      iterations: null,
      envFlowRatio: 0.10,
      enforceDeliveryCaps: true,
      waterQualityFilter: true,
      waterModel: 'calib',
      riskMode: 'none'
    }
  };

  // Abort previous benchmark run if user starts a new one
  if(benchmarkAbortCtrl){ try{ benchmarkAbortCtrl.abort(); }catch(e){} }
  benchmarkAbortCtrl = new AbortController();
  const tmr = setTimeout(()=>{ try{ benchmarkAbortCtrl.abort(); }catch(_e){} }, 600000);
  const res = await fetch('/api/benchmark', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal: benchmarkAbortCtrl.signal
  }).finally(()=> clearTimeout(tmr));
  if(!res.ok){
    const t = await res.text().catch(()=> '');
    throw new Error('Benchmark API failed: '+(t || ('HTTP '+res.status)));
  }
  return await res.json();
}

// Tarayıcı içi benchmark (yedek plan)
// Bazı ortamlarda /api/benchmark uzun sürebilir veya bağlantı hatası verebilir.
// Bu durumda kullanıcıya yine de "Algoritma karşılaştırması" çıktısı sunabilmek için
// basit bir tarayıcı içi tekrar/ortalama hesaplar.
function runBenchmarkInBrowser(objectiveKey, seasonSourceOverride=null){
  const repeatsEl = document.getElementById('benchmarkRepeats');
  const repeats = Math.max(1, Math.min(30, parseInt(repeatsEl?.value || '10', 10) || 10));

  const oldSeason = STATE.seasonSource;
  if(seasonSourceOverride) STATE.seasonSource = seasonSourceOverride;

  const algos = ['GA','ABC','ACO'];
  const algoKey = { GA:'ga', ABC:'abc', ACO:'aco' };

  // Kapsam: seçili parsel veya tüm parseller
  const scopeIds = getSelectedParcelIdsForRun();
  const isSingle = scopeIds.length === 1;
  const singleId = isSingle ? String(scopeIds[0]) : null;

  const totalsFor = (scenarioKey, ak)=>{
    if(isSingle){
      const p = parcelData.find(x=>String(x.id)===singleId);
      const res = runOptimization(p, scenarioKey, ak);
      const t = res?.totals || { water:0, profit:0 };
      return { water: +t.water||0, profit: +t.profit||0, eff: (t.water>0 ? (t.profit/t.water) : 0) };
    }
    const basin = computeBasinPlan(scenarioKey, ak);
    const t = basin?.totals || { water:0, profit:0, eff:0 };
    return { water: +t.water||0, profit: +t.profit||0, eff: (t.water>0 ? (t.profit/t.water) : 0) };
  };

  const meanStd = (arr)=>{
    const xs = (arr||[]).map(v=>+v||0);
    const n = xs.length || 1;
    const mean = xs.reduce((a,b)=>a+b,0)/n;
    const varr = xs.reduce((a,v)=>a+(v-mean)*(v-mean),0)/Math.max(1,n-1);
    return { mean, std: Math.sqrt(varr) };
  };

  const scenarioKey = (objectiveKey||'su_tasarruf').toString();
  const out = { status:'OK', source:'browser', repeats, scenario: scenarioKey, objective: scenarioKey, algorithms:{} };
  try{
    // Baseline: mevcut desen
    const b = totalsFor('mevcut', 'ga');
    out.baseline = {
      total_profit_tl: b.profit,
      total_water_m3: b.water,
      efficiency_tl_per_m3: b.eff
    };

    for(const A of algos){
      const prof=[], wat=[], eff=[];
      for(let i=0;i<repeats;i++){
        const t = totalsFor(scenarioKey, algoKey[A]);
        prof.push(t.profit);
        wat.push(t.water);
        eff.push(t.eff);
      }
      out.algorithms[A] = {
        profit: meanStd(prof),
        water: meanStd(wat),
        efficiency: meanStd(eff)
      };
    }
  }finally{
    STATE.seasonSource = oldSeason;
  }
  return out;
}

function getSelectedScenarioKey(){
  try{
    const el = document.querySelector('input[name="scenario"]:checked');
    return (el?.value || 'su_tasarruf').toString();
  }catch(_e){
    return 'su_tasarruf';
  }
}

function seasonSourceLabel(src){
  const s = (src||'').toString();
  if(s === 's1') return 'Senaryo-1 (tek başına)';
  if(s === 's2') return 'Senaryo-2 (tek başına)';
  if(false) return 'Senaryo-1';
  return s;
}

function fmtNum(n, digits=1){
  const x = Number(n||0);
  return x.toLocaleString('tr-TR', { maximumFractionDigits: digits, minimumFractionDigits: 0 });
}


function prettyCropName(name){
  const n = (name||"").toString().trim().toUpperCase();
  if(!n) return "";
  if(n === "NADAS" || n === "FALLOW"){
    return "Nadas (Boş bırak)";
  }
  return (name||"").toString();
}


// Benchmark çıktısını istenen hedef elementlere bas (çoklu senaryo kartları için de kullanılır)
function renderBenchmarkResultsTo(j, box, patBox, updateCharts = true){
  if(!box) return;
  if(!j || j.status !== 'OK'){
    box.innerHTML = '<div class="badge badge-warn">Benchmark sonucu alınamadı</div>';
    if(patBox) patBox.innerHTML = '';
    return;
  }

  const algos = j.algorithms || {};
  const rows = Object.keys(algos);
  if(!rows.length){
    box.innerHTML = '<div class="badge badge-warn">Veri yok</div>';
    return;
  }

  // Table
  let html = '';
  html += '<div class="small" style="opacity:.85;margin-bottom:6px;">Tekrar: <b>'+j.repeats+'</b> — Not: std = oynaklık (küçük daha stabil)</div>';
  if(j.baseline){
    html += '<div class="small" style="margin-bottom:6px;">Baseline (Mevcut desen): <b>'+fmtNum(j.baseline.total_profit_tl,0)+' TL</b> — <b>'+fmtNum(j.baseline.total_water_m3,0)+' m³</b> — <b>'+fmtNum(j.baseline.efficiency_tl_per_m3,2)+' TL/m³</b></div>';
  }

  // Farmer-friendly: pick a recommended algorithm for the chosen objective
  try{
    const objectiveRaw = (j.objective || j.scenario || j.target || '').toString();
    const objective = objectiveRaw.toLowerCase();
    const isWater = objective.includes('water') || objective.includes('su');
    const isProfit = objective.includes('profit') || objective.includes('kar');
    const isBalanced = objective.includes('balanced') || objective.includes('denge') || objective.includes('recommended');

    const scoreRows = rows.map(a=>{
      const r = algos[a] || {};
      const p = r.profit||{}; const w = r.water||{}; const e = r.efficiency||{};
      const ps = Number(p.std)||0, pm = Number(p.mean)||0;
      const ws = Number(w.std)||0, wm = Number(w.mean)||0;
      const es = Number(e.std)||0, em = Number(e.mean)||0;

      // Stability penalty: relative std (avoid division by 0)
      const rel = (m,s)=> (Math.abs(m) > 1e-9 ? Math.abs(s)/Math.abs(m) : 0);
      const stabPenalty = 0.15*(rel(pm,ps)+rel(wm,ws)+rel(em,es));

      // Objective score
      let base = 0;
      if(isWater && !isProfit){
        // minimize water (lower is better)
        base = -wm + 0.05*em;
      }else if(isProfit && !isWater){
        // maximize profit
        base = pm;
      }else if(isBalanced){
        // maximize TL/m3 (efficiency)
        base = em;
      }else{
        // fallback: efficiency
        base = em;
      }
      return {a, base, score: base - Math.abs(base)*stabPenalty};
    });
    scoreRows.sort((x,y)=> y.score - x.score);
    const best = scoreRows[0];
    if(best && best.a){
      const r = algos[best.a] || {};
      const p = r.profit||{}; const w = r.water||{}; const e = r.efficiency||{};
      const why = (isWater && !isProfit)
        ? `Bu hedefte ortalama su kullanımı daha düşük ve oynaklık (std) makul.`
        : (isProfit && !isWater)
          ? `Bu hedefte ortalama kâr daha yüksek ve oynaklık (std) makul.`
          : `Bu hedefte TL/m³ verimliliği daha yüksek ve oynaklık (std) makul.`;
      html += '<div class="callout callout-ok" style="margin:8px 0 10px;">'+
              '<b>Çiftçi için önerilen algoritma:</b> <b>'+escapeHtml(best.a)+'</b> — '+escapeHtml(why)+
              '<div class="small muted" style="margin-top:4px;">'+
              'Ortalama: Kâr '+fmtNum(p.mean,0)+' TL, Su '+fmtNum(w.mean,0)+' m³, TL/m³ '+fmtNum(e.mean,2)+
              ' (std daha küçük = daha stabil)'+
              '</div></div>';
    }
  }catch(_e){}
  html += '<div style="overflow:auto;">';
  html += '<table class="mini-table" style="width:100%;border-collapse:collapse;">';
  html += '<thead><tr>'+
    '<th style="text-align:left;padding:6px 8px;border-bottom:1px solid #e6ebff;">Algoritma</th>'+
    '<th style="text-align:right;padding:6px 8px;border-bottom:1px solid #e6ebff;">Kâr (ort±std)</th>'+
    '<th style="text-align:right;padding:6px 8px;border-bottom:1px solid #e6ebff;">Su (ort±std)</th>'+
    '<th style="text-align:right;padding:6px 8px;border-bottom:1px solid #e6ebff;">TL/m³ (ort±std)</th>'+'<th style="text-align:right;padding:6px 8px;border-bottom:1px solid #e6ebff;">Nadas oranı (ort±std)</th>'+
    '<th style="text-align:right;padding:6px 8px;border-bottom:1px solid #e6ebff;">Desen çeşidi</th>'+
    '<th style="text-align:right;padding:6px 8px;border-bottom:1px solid #e6ebff;">Süre sn (ort)</th>'+
    '<th style="text-align:right;padding:6px 8px;border-bottom:1px solid #e6ebff;">Hata</th>'+
  '</tr></thead><tbody>';

  for(const a of rows){
    const r = algos[a];
    const p = r.profit||{}; const w = r.water||{}; const e = r.efficiency||{}; const t = r.runtime_s||{};
    html += '<tr>'+
      '<td style="padding:6px 8px;border-bottom:1px solid #f0f3ff;"><b>'+a+'</b></td>'+
      '<td style="padding:6px 8px;text-align:right;border-bottom:1px solid #f0f3ff;">'+fmtNum(p.mean,0)+' ± '+fmtNum(p.std,0)+'</td>'+
      '<td style="padding:6px 8px;text-align:right;border-bottom:1px solid #f0f3ff;">'+fmtNum(w.mean,0)+' ± '+fmtNum(w.std,0)+'</td>'+
      '<td style="padding:6px 8px;text-align:right;border-bottom:1px solid #f0f3ff;">'+fmtNum(e.mean,2)+' ± '+fmtNum(e.std,2)+'</td>'+
      '<td style="padding:6px 8px;text-align:right;border-bottom:1px solid #f0f3ff;">'+(r.nadas_ratio? (fmtNum(r.nadas_ratio.mean*100,1)+'% ± '+fmtNum(r.nadas_ratio.std*100,1)+'%') : '-')+'</td>'+
      '<td style="padding:6px 8px;text-align:right;border-bottom:1px solid #f0f3ff;">'+(r.unique_patterns ?? 0)+'</td>'+
      '<td style="padding:6px 8px;text-align:right;border-bottom:1px solid #f0f3ff;">'+fmtNum(t.mean,2)+'</td>'+
      '<td style="padding:6px 8px;text-align:right;border-bottom:1px solid #f0f3ff;">'+(r.errors||0)+'</td>'+
    '</tr>';
  }
  html += '</tbody></table></div>';
  box.innerHTML = html;

  // Pattern compare (best run per algorithm)
  if(patBox){
    let pHtml = '<div class="card" style="background:#fbfcff;">'+
      '<h3 class="card-subtitle" style="margin:0 0 6px;">Önerilen desen karşılaştırması (en iyi koşuş)</h3>'+
	      '<div class="small" style="opacity:.8;margin-bottom:8px;">Her algoritmanın tekrarlar içindeki <b>en iyi</b> koşuşundan desen özeti gösterilir.'+
	      '<br/><span class="muted">Not: GA/ABC/ACO stokastiktir; ana ekrandaki tek seferlik “Optimizasyonu Çalıştır” sonucu farklı bir seed ile üretildiği için burada görünen en-iyi koşuş ile birebir aynı olmak zorunda değildir.</span></div>';

    // cards per algorithm
    pHtml += '<div class="benchmark-pattern-grid">';
    for(const a of rows){
      const best = algos[a]?.best;
      if(!best){
        pHtml += '<div class="stat" style="min-width:240px;"><div class="stat-label"><b>'+a+'</b></div><div class="stat-value muted">—</div></div>';
        continue;
      }
      const prim = (best.crop_area?.primary||[]).slice(0,6);
      const sec = (best.crop_area?.secondary||[]).slice(0,6);
      const primList = prim.map(x=> `${x.crop} (${fmtNum(x.area_da,1)} da)`).join('<br/>') || '—';
      const secList = sec.map(x=> `${x.crop} (${fmtNum(x.area_da,1)} da)`).join('<br/>') || '—';
      pHtml += '<div class="stat" style="min-width:240px;">'+
        '<div class="stat-label"><b>'+a+'</b> — En iyi koşuş</div>'+
        '<div class="small" style="margin-top:6px;"><b>1. Ürün</b><br/>'+primList+'</div>'+
        '<div class="small" style="margin-top:6px;"><b>2. Ürün</b><br/>'+secList+'</div>'+
        '<div class="small" style="opacity:.8;margin-top:8px;">Kâr: <b>'+fmtNum(best.total_profit_tl,0)+'</b> TL — Su: <b>'+fmtNum(best.total_water_m3,0)+'</b> m³ — TL/m³: <b>'+fmtNum(best.efficiency_tl_per_m3,2)+'</b></div>'+
      '</div>';
    }
    pHtml += '</div>';

    // parcel-level compare table (compact)
    const anyBest = rows.find(a=> !!algos[a]?.best?.parcels);
    if(anyBest){
      // build map id -> crops
      const maps = {};
      let ids = [];
      for(const a of rows){
        const ps = algos[a]?.best?.parcels || [];
        const m = {}; ps.forEach(p=>{ m[p.id] = p; ids.push(p.id); });
        maps[a] = m;
      }
      ids = Array.from(new Set(ids)).sort();
      pHtml += '<div style="overflow:auto;margin-top:12px;">';
      pHtml += '<table class="mini-table" style="width:100%;border-collapse:collapse;">';
      pHtml += '<thead><tr>'+
        '<th style="text-align:left;padding:6px 8px;border-bottom:1px solid #e6ebff;">Parsel</th>'+
        rows.map(a=>'<th style="text-align:left;padding:6px 8px;border-bottom:1px solid #e6ebff;">'+a+' (1. / 2.)</th>').join('')+
      '</tr></thead><tbody>';
      for(const id of ids){
        pHtml += '<tr><td style="padding:6px 8px;border-bottom:1px solid #f0f3ff;"><b>'+id+'</b></td>';
        for(const a of rows){
          const p = maps[a]?.[id];
          const c1 = p?.primary?.crop || '—';
          const c2 = p?.secondary?.crop || '—';
          pHtml += '<td style="padding:6px 8px;border-bottom:1px solid #f0f3ff;">'+c1+'<span class="muted"> / </span>'+c2+'</td>';
        }
        pHtml += '</tr>';
      }
      pHtml += '</tbody></table></div>';
    }

    pHtml += '</div>';
    patBox.innerHTML = pHtml;
  }

  if(updateCharts){
    // Update charts (mean values)
    let labels = rows.slice();
    let meanProfit = rows.map(a=> (algos[a].profit?.mean||0));
    let meanWater  = rows.map(a=> (algos[a].water?.mean||0));
    let meanEff    = rows.map(a=> (algos[a].efficiency?.mean||0));

    // Add baseline column (Mevcut) if provided by backend
    if(j.baseline && (j.baseline.status === 'OK' || typeof j.baseline.total_profit_tl !== 'undefined')){
      labels = ['Mevcut'].concat(labels);
      meanProfit = [+(j.baseline.total_profit_tl||0)].concat(meanProfit);
      meanWater  = [+(j.baseline.total_water_m3||0)].concat(meanWater);
      meanEff    = [+(j.baseline.efficiency_tl_per_m3||0)].concat(meanEff);
    }

    if(benchmarkProfitChart){
      benchmarkProfitChart.data.labels = labels;
      benchmarkProfitChart.data.datasets[0].data = meanProfit;
      benchmarkProfitChart.update();
    }
    if(benchmarkWaterChart){
      benchmarkWaterChart.data.labels = labels;
      benchmarkWaterChart.data.datasets[0].data = meanWater;
      benchmarkWaterChart.update();
    }
    if(benchmarkEffChart){
      benchmarkEffChart.data.labels = labels;
      benchmarkEffChart.data.datasets[0].data = meanEff;
      benchmarkEffChart.update();
    }
  }
}

function renderBenchmarkResults(j){
  const box = document.getElementById('benchmarkResults');
  const patBox = document.getElementById('benchmarkPatterns');
  renderBenchmarkResultsTo(j, box, patBox, true);
}


// --- PYTHON BACKEND (Flask) ENTEGRASYONU ---
// Optimizasyon isteklerini /api/optimize üzerinden Python'a gönderebilir.
// Bu sayede: (1) algoritmalar gerçekten Python'da çalışır, (2) XLSX/JSON tüm desen verileri backend'de kullanılır.
async function fetchAndCacheBasinPlanPython(scenarioKey, algoKey){
  // ✅ Bu çağrı bu fonksiyonun "tek" optimize isteği olsun

  // 1) En başta reqId al
  const reqId = ++lastOptimizeReqId;

  // 2) Önceki istekleri iptal ETME (stabilite için)
  //    Eski sürüm AbortController ile istekleri iptal ediyordu; bu Network'te (canceled) hatalarına yol açıyordu.
  //    Bu sürümde iptal yok; reqId kontrolü ile geç gelen sonuçlar yok sayılır.


  const key = basinCacheKey(scenarioKey, algoKey);
  const algoMap = { ga: 'GA', abc: 'ABC', aco: 'ACO' };
  // v74: maks_kar artık UI'da yok; geriye dönük olarak su tasarrufuna eşlenir.
  const scenarioMap = { mevcut: 'current', current: 'current', su_tasarruf: 'water_saving', 'su tasarruf':'water_saving', maks_kar: 'water_saving', 'maks kar':'water_saving', onerilen: 'balanced', recommended: 'balanced' };

  const payload = {
    // v72: Run scope must match UI selection.
    // "__ALL__" -> basin totals, otherwise only the selected parcel.
    selectedParcelIds: getSelectedParcelIdsForRun(),
    algorithm: algoMap[algoKey] || 'GA',
    scenario: scenarioMap[scenarioKey] || 'recommended',
    waterBudgetRatio: budgetRatioForScenarioKey(scenarioKey),
    year: STATE.selectedWaterYear || null,
    options: {
      seasonSource: STATE.seasonSource || 's1',
      maxCrops: 8,
      generations: 35,
      popSize: 40,
      iterations: 40,
      ants: 30,
      bees: 30,
      units: 20,
      // Deterministic seed helps reproducibility across runs.
      // Benchmark can override this.
      seed: 42,
      wWater: 1.0,
      wProfit: 1.0,
      wPattern: 0.4
    }
  };

  let res;
  try{
    res = await fetch("/api/optimize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
});
  }catch(err){
    // abort ise sessiz çık
    if (err && err.name === "AbortError") return null;
    throw err;
  }

  // 3) HTTP hata kontrolü
  if(!res.ok){
    const t = await res.text().catch(()=> "");
    throw new Error("Python optimize failed: " + (t || ("HTTP " + res.status)));
  }

  // 4) JSON'u SADECE 1 KERE oku
  const data = await res.json();

  // --- Normalize backend payload shapes ---
  // Backend can return either:
  // (A) {status:"OK", parcels:[{id, result:{recommended:[...]}}], ...}
  // (B) {algorithm, objective, water_budget_m3, details:[{parcelId, chosenCrop, area_da, water_m3, profit_tl}], ...}
  // We convert (B) into (A)-like structure so the UI logic stays consistent.
  let norm = data;
  if(norm && Array.isArray(norm.details) && !Array.isArray(norm.parcels)){
    const parcelsOut = [];
    for(const d of norm.details){
      const area = +d.area_da || 0;
      const pid = (d.parcelId || d.parcel_id || d.id || "").toString();

      // Two-season payload: {primary:{crop,water_m3,profit_tl}, secondary:{...}}
      if(d.primary && d.secondary){
        const w1 = +d.primary.water_m3 || 0;
        const p1 = +d.primary.profit_tl || 0;
        const w2 = +d.secondary.water_m3 || 0;
        const p2 = +d.secondary.profit_tl || 0;

        parcelsOut.push({
          id: pid,
          result: {
            recommended: [
              {
                name: prettyCropName(d.primary.crop || "URUN"),
                area,
                waterPerDa: area>0 ? (w1/area) : 0,
                profitPerDa: area>0 ? (p1/area) : 0
              },
              {
                name: prettyCropName(d.secondary.crop || "URUN"),
                area,
                waterPerDa: area>0 ? (w2/area) : 0,
                profitPerDa: area>0 ? (p2/area) : 0
              }
            ]
          }
        });
        continue;
      }

      // Single-crop payload
      const water = +d.water_m3 || 0;
      const profit = +d.profit_tl || 0;
      const name = (d.chosenCrop || d.chosen_crop || d.crop || "URUN").toString();
      parcelsOut.push({
        id: pid,
        result: {
          recommended: [{
            name,
            area,
            waterPerDa: area>0 ? (water/area) : 0,
            profitPerDa: area>0 ? (profit/area) : 0
          }]
        }
      });
    }
    norm = {
      status: "OK",
      parcels: parcelsOut,
      droughtFactor: norm.get ? undefined : norm.droughtFactor,
      water_budget_m3: norm.water_budget_m3,
      total_water_m3: norm.total_water_m3,
      total_profit_tl: norm.total_profit_tl,
      algorithm: norm.algorithm,
      objective: norm.objective,
      year: norm.year,
      meta: norm.meta
    };
  }

  // 5) Eğer bu cevap eski isteğe aitse UI/cache güncelleme

  if (reqId !== lastOptimizeReqId) {
    console.warn("Eski optimize cevabı yok sayıldı (reqId mismatch)");
    return null;
  }

  // 6) Backend “OK değil” diyorsa cache’e yazma
  if (norm.status && norm.status !== "OK") {
    alert("Optimizasyon reddedildi: " + (norm.reason || "Bütçe aşıldı"));
    return null;
  }

  // 7) Python çıktısını UI’nin beklediği forma çevir
  const plan = {};
  let totalWater = 0;
  let totalProfit = 0;

  for(const pr of (norm.parcels||[])){
    const rows = (pr.result?.recommended||[]).map(r=>{
      const totalWater = (+r.area) * (+r.waterPerDa);
      const totalProfit = (+r.area) * (+r.profitPerDa);
      return {
        name: r.name,
        area: +r.area,
        waterPerDa: +r.waterPerDa,
        profitPerDa: +r.profitPerDa,
        season: r.season || '',
        irrigationCurrentKey: r.irrigationCurrentKey || r.irrigationCurrent || null,
        irrigationSuggestedKey: r.irrigationSuggestedKey || r.irrigationRecommended || null,
        totalWater,
        totalProfit
      };
    });

    const totals = sumMetrics(rows);
    plan[pr.id] = { rows, totals };
    totalWater += totals.water;
    totalProfit += totals.profit;
  }

  // ✅ Prefer backend-computed budget (same basis as optimization).
  // Fallback to UI-computed budget only if backend didn't send it.
  const budget = (norm && norm.water_budget_m3 != null && isFinite(+norm.water_budget_m3))
    ? (+norm.water_budget_m3)
    : computeGlobalBudgetM3();

  const out = {
    plan,
    budget,
    totals: { water: totalWater, profit: totalProfit, eff: totalProfit/Math.max(1,totalWater) },
    iterations: 0,
    feasible: totalWater <= budget + 1e-6,
    pythonMeta: norm.dataUsed || norm.meta || {},
    deliveryReport: (norm && norm.meta && (norm.meta.delivery_report || norm.meta.deliveryReport)) ? (norm.meta.delivery_report || norm.meta.deliveryReport) : null,
    droughtFactor: norm.droughtFactor,
    projection2050vs2025: norm.projection2050vs2025
  };

  // 8) Cache’e yaz (sadece son reqId için)
  basinPlanCache[key] = out;

  return out;
}




// --- PYTHON BACKEND INTEGRATION ---
// When the Flask backend (app.py) is running, we can compute GA/ABC/ACO in Python and cache
// results into the existing basinPlanCache so the UI continues to work without rewriting.
async function fetchAndCacheBasinPlanFromServer(scenarioKey, algoKey){
  const key = basinCacheKey(scenarioKey, algoKey);
  const url = '/api/optimize';
  // Map UI keys to backend
  const algoMap = {ga:'GA', abc:'ABC', aco:'ACO'};
  // v74: "maks_kar" artık sunulmuyor; uyumluluk için su tasarrufuna eşlenir.
  const scenarioMap = { mevcut: 'current', current: 'current', su_tasarruf: 'water_saving', maks_kar: 'water_saving', onerilen: 'balanced', recommended: 'balanced' };
  const payload = {
    selectedParcelIds: getSelectedParcelIdsForRun(),
    algorithm: algoMap[algoKey] || 'GA',
    scenario: scenarioMap[scenarioKey] || 'balanced',
    waterBudgetRatio: budgetRatioForScenarioKey(scenarioKey),
    options: {
      maxCrops: 8,
      // weights can be tuned from UI later
      wWater: 1.0,
      wProfit: 1.0,
      wPattern: 0.4
    }
  };

  const res = await fetch(url, {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(payload)
  });
  if(!res.ok){
    throw new Error('Python optimize API failed: '+res.status);
  }
  const data = await res.json();

  const plan = {};
  let totalWater = 0;
  let totalProfit = 0;

  // Normalize to expected shape
  const norm = data;
  for(const pr of (norm.parcels||[])){
    const rows = (pr.result?.recommended||[]).map(r=>({
      name: r.name,
      area: +r.area,
      waterPerDa: +r.waterPerDa,
      profitPerDa: +r.profitPerDa,
      totalWater: (+r.area) * (+r.waterPerDa),
      totalProfit: (+r.area) * (+r.profitPerDa)
    }));
    const totals = sumMetrics(rows);
    plan[pr.id] = { rows: rows, totals: totals };
    totalWater += totals.water;
    totalProfit += totals.profit;
  }

  const out = {
    plan,
    budget: computeGlobalBudgetM3(),
    totals: { water: totalWater, profit: totalProfit, eff: totalProfit/Math.max(1,totalWater) },
    iterations: null,
    feasible: totalWater <= computeGlobalBudgetM3() + 1e-6,
    server: true,
    dataUsed: data.dataUsed
  };

  basinPlanCache[key] = out;
  return out;
}
// Global durum
let selectedParcelId = (parcelData && parcelData.length) ? parcelData[0].id : null;

// -----------------------------
// Selection helpers
// -----------------------------
// UI supports "__ALL__" to view basin totals. For optimize/benchmark requests we
// must send the correct parcel list to the backend so results stay consistent.
function getSelectedParcelIdsForRun() {
  const sid = (selectedParcelId ?? '').toString();
  if (!sid) return (parcelData || []).map(p => p.id);
  if (sid === '__ALL__') return (parcelData || []).map(p => p.id);
  return [sid];
}
let selectedAlgo = "ga";
let selectedScenario = "mevcut";

// UX: while a new optimization is running, keep the last valid results visible.
// When the user changes algo/scenario without running, keep previous results but show a warning.
STATE.isOptimizing = false;
STATE.selectionDirty = false;

// Son optimizasyon çalıştırma bağlamı.
// Parsel veya senaryo/algoritma değiştiğinde öneri/opt sonuçlarının
// eski seçimden kalmaması için kullanılır.
let lastOptimizeContext = null; // { parcelId, scenario, algo }

// DOM referansları (DOMContentLoaded içinde atanır)
let parcelSelectEl = null;
let parcelSummaryBody = null;

 // Parsel dropdown'ını güncelle (API'den gelen parcelData ile)
function refreshParcelSelect() {
  if (!parcelSelectEl) parcelSelectEl = document.getElementById("parcelSelect");
  if (!parcelSelectEl) return;

  const current = parcelSelectEl.value;
  parcelSelectEl.innerHTML = "";

  const opt0 = document.createElement("option");
  opt0.value = "";
  opt0.textContent = "Parsel seç";
  parcelSelectEl.appendChild(opt0);

  // Natural sort: P1, P2, ... P10 (instead of P1, P10, P11...)
  // Bazı veri setlerinde id alanı "P1 – ..." gibi zengin etiket taşıyabilir.
  // Bu yüzden önce id içinden, olmazsa name/display_name içinden P\d+ yakalayıp sıralıyoruz.
  const _parcelNum = (p)=>{
    const cand = [p?.id, p?.name, p?.display_name, p?.label].filter(Boolean).map(x=>String(x));
    for(const s of cand){
      // Prefer the leading parcel code (P1, P2, ...). Avoid "grab all digits" because
      // labels like "P2 – K10.2 ..." would become 2102 and break ordering.
      const m1 = s.match(/(^|\s)P\s*(\d+)\b/i);
      if(m1) return parseInt(m1[2], 10);
      const m2 = s.match(/^P\s*(\d+)$/i);
      if(m2) return parseInt(m2[1], 10);
    }
    return Number.POSITIVE_INFINITY;
  };

  const sorted = [...parcelData].sort((a, b) => {
    const an = _parcelNum(a);
    const bn = _parcelNum(b);
    if(an !== bn) return an - bn;
    const ax = String(a?.id || a?.name || "");
    const bx = String(b?.id || b?.name || "");
    return ax.localeCompare(bx, "tr");
  });

  sorted.forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p.id;
    const name = (p.name || p.display_name || p.label || "").trim();
    const v = (p.village || "").trim();
    const d = (p.district || "").trim();

    // Prefer a rich label if available; otherwise fall back to id + location.
    if (name && name !== p.id) {
      opt.textContent = name;
    } else if (v && d) {
      opt.textContent = `${p.id} – ${v} (${d})`;
    } else if (v) {
      opt.textContent = `${p.id} – ${v}`;
    } else {
      opt.textContent = p.id;
    }
    parcelSelectEl.appendChild(opt);
  });

  // mümkünse önceki seçimi koru
  if (current && parcelData.some((p) => p.id === current)) {
    parcelSelectEl.value = current;
  }
}


// Parsel özeti yaz
// UI'da seçili parsel kartlarını/özetini güncellemek için tek giriş noktası.
// Bazı sürümlerde event handler'lar refreshParcelInfoCards() çağırıyor.
// Bu fonksiyon tanımlı olmazsa tüm script çalışması durduğu için boş ekran oluşur.
function refreshParcelInfoCards(){
  try{
    if(typeof renderParcelSummary === 'function') renderParcelSummary();
  }catch(e){
    // sessiz geç: veri daha yüklenmemiş olabilir
  }
}

// -------------------------
// Parsel özeti: toprak kodu çözümleyici (harita lejantına göre)
// Kod örneği: "B11.3 K IVes" (eğim–bünye–derinlik + büyük toprak grubu + arazi kabiliyeti)
// -------------------------

const SOIL_GROUPS = {
  // (Lejanttaki büyük toprak grupları / sık kullanılanlar)
  P: 'Kırmızı Sarı Podzolik Topraklar',
  G: 'Gri Kahverengi Podzolik Topraklar',
  M: 'Kahverengi Orman Toprakları',
  N: 'Kireçsiz Kahverengi Orman Toprakları',
  C: 'Kestanerengi Topraklar',
  D: 'Kırmızımsı Kestanerengi Topraklar',
  T: 'Kırmızı Akdeniz Toprakları',
  E: 'Kırmızı Kahverengi Akdeniz Toprakları',
  B: 'Kahverengi Topraklar',
  U: 'Kireçsiz Kahverengi Topraklar (diğer)',
  F: 'Kırmızımsı Kahverengi Topraklar',
  R: 'Rendzinalar',
  V: 'Vertisoller',
  Z: 'Sierozemler',
  L: 'Regosoller',
  X: 'Bazaltik Topraklar',
  Y: 'Yüksek Dağ Çayır Toprakları',
  // (Lejantta ayrıca geçen özel gruplar)
  H: 'Hidromorfik Alüvyal Topraklar',
  S: 'Alüvyal Sahil Bataklıkları',
  K: 'Kolüvyal Topraklar',
  Ç: 'Tuzlu–Alkali ve Tuzlu–Alkali Karışık Topraklar',
  O: 'Organik Topraklar'
};

const SLOPE_CLASSES = {
  A: '0–2% (düz / çok az eğimli)',
  B: '2–6% (hafif eğimli)',
  C: '6–12% (orta eğimli)',
  D: '12–20% (eğimli)',
  E: '20–30% (çok eğimli)',
  F: '30%+ (dik)'
};

const DEPTH_CLASSES = {
  derin: 'Derin (90+ cm)',
  orta: 'Orta derin (50–90 cm)',
  sig: 'Sığ (20–50 cm)',
  coksig: 'Çok sığ (0–20 cm)',
  lito: 'Litozolik (anakaya çok yakın)'
};

// Eğim–bünye–derinlik kombinasyon tablosundan (lejant görselindeki numaralar)
function decodeEbdCode(n){
  const num = Number(String(n||'').replace(/[^0-9]/g,''));
  if(!Number.isFinite(num) || num<=0) return null;

  // 1–27: A/B/C eğim + (ince/orta/kaba) + (derin/orta/sığ)
  // 28–31: D eğim (%12–20) + "çeşitli" + (derin/orta/sığ/çok sığ)
  // 32–35: litozolik (A/B/C/D)
  if(num >= 1 && num <= 27){
    const block = Math.floor((num-1)/9); // 0:A, 1:B, 2:C
    const within = (num-1)%9;            // 0..8
    const texBlock = Math.floor(within/3); // 0:ince,1:orta,2:kaba
    const depthIdx = within%3;             // 0:derin,1:orta,2:sığ

    const slope = ['A','B','C'][block];
    const texture = ['İnce','Orta','Kaba'][texBlock];
    const depthKey = ['derin','orta','sig'][depthIdx];
    return {
      code: num,
      slope,
      slopeText: SLOPE_CLASSES[slope] || String(slope),
      texture,
      depthText: DEPTH_CLASSES[depthKey]
    };
  }

  if(num >= 28 && num <= 31){
    const depthKey = ['derin','orta','sig','coksig'][num-28];
    return {
      code: num,
      slope: 'D',
      slopeText: SLOPE_CLASSES.D,
      texture: 'Çeşitli',
      depthText: DEPTH_CLASSES[depthKey]
    };
  }

  if(num >= 32 && num <= 35){
    const slope = ['A','B','C','D'][num-32];
    return {
      code: num,
      slope,
      slopeText: SLOPE_CLASSES[slope] || String(slope),
      texture: '—',
      depthText: DEPTH_CLASSES.lito
    };
  }
  return { code: num, slope: '—', slopeText: '—', texture: '—', depthText: '—' };
}

const EROSION_WATER = {
  1: 'Hiç veya çok az',
  2: 'Orta',
  3: 'Şiddetli',
  4: 'Çok şiddetli'
};

const SOIL_OTHER = {
  h: 'Hafif tuzlu',
  s: 'Tuzlu',
  a: 'Alkali',
  k: 'Hafif tuzlu‑alkali',
  v: 'Tuzlu‑alkali',
  t: 'Taşlı',
  r: 'Kayalı',
  y: 'Yetersiz drenaj',
  f: 'Kötü drenajlı'
};

const LAND_CAP_SUB = {
  e: 'Erozyon sınırlayıcı',
  w: 'Islaklık / drenaj sınırlayıcı',
  s: 'Toprak (derinlik‑bünye‑taşlılık vb.) sınırlayıcı',
  c: 'İklim / iklimsel sınırlayıcı'
};

function decodeLandCapability(token){
  const raw = String(token||'').trim();
  const m = raw.match(/^([IVX]{1,4})([a-zA-Z]*)$/);
  if(!m) return null;
  const cls = m[1];
  const subs = (m[2]||'').toLowerCase().split('').filter(Boolean);
  const subText = subs.map(s=>LAND_CAP_SUB[s]).filter(Boolean);
  return { cls, subs, subText };
}

function decodeSoilCode(rawCode){
  const raw = String(rawCode||'').trim();
  if(!raw) return null;

  const tokens = raw.replace(/\s+/g,' ').split(' ').filter(Boolean);
  // 1) Eğim‑bünye‑derinlik + erozyon (ör: B11.3)
  let ebdTok = tokens.find(t=>/^[A-F][0-9]{1,2}(\.[0-9])?$/.test(t)) || null;
  const ebd = ebdTok ? {
    slope: ebdTok[0],
    code: Number((ebdTok.match(/^[A-F]([0-9]{1,2})/)||[])[1] || NaN),
    erosion: Number((ebdTok.match(/\.(\d)$/)||[])[1] || NaN)
  } : null;
  const ebdDetail = ebd ? decodeEbdCode(ebd.code) : null;

  // 2) Büyük toprak grubu: tek harf (ör: K)
  const groupTok = tokens.find(t=>/^[A-ZÇĞİÖŞÜ]$/.test(t) && SOIL_GROUPS[t]) || null;

  // 3) Arazi kullanma kabiliyeti: Roma rakamı + alt sınıf (örn IVes)
  const capTok = tokens.find(t=>/^[IVX]{1,4}[A-Za-z]*$/.test(t)) || null;
  const cap = capTok ? decodeLandCapability(capTok) : null;

  // 4) Diğer toprak özellikleri: kod içinde tek harflerle geçebilir (h, s, a, k, v, t, r, y, f)
  // (Örn: "M 11 t.2" gibi desenler görülebiliyor; buradan sadece harfleri yakalıyoruz.)
  const otherLetters = Array.from(new Set((raw.match(/[hsakvtryf]/gi) || []).map(x=>x.toLowerCase())));
  const other = otherLetters.map(k=>({ k, text: SOIL_OTHER[k] })).filter(x=>x.text);

  return {
    raw,
    ebdTok,
    slope: ebd?.slope || (ebdDetail?.slope),
    slopeText: SLOPE_CLASSES[ebd?.slope] || ebdDetail?.slopeText || null,
    ebdDetail,
    erosionDeg: Number.isFinite(ebd?.erosion) ? ebd.erosion : null,
    erosionText: Number.isFinite(ebd?.erosion) ? (EROSION_WATER[ebd.erosion] || String(ebd.erosion)) : null,
    groupTok,
    groupText: groupTok ? SOIL_GROUPS[groupTok] : null,
    capTok,
    cap,
    other
  };
}

function renderParcelSummary() {
  const p = parcelData.find((x) => x.id === selectedParcelId);
  if (!p) return;

  // İklim alanlarında bazen undefined gelebiliyor. UI'da "undefined" yazması yerine
  // Türkçe ve anlaşılır bir ifade kullanalım.
  const climateRaw = p.climate || {};
  const climate = {
    rain_mm: (climateRaw.rain_mm ?? climateRaw.rain ?? climateRaw.rainfall_mm ?? '—'),
    eto_mm:  (climateRaw.eto_mm  ?? climateRaw.eto  ?? climateRaw.eto_total_mm ?? '—'),
    t_avg:   (climateRaw.t_avg   ?? climateRaw.tavg ?? climateRaw.t_mean_c),
    frost:   (climateRaw.frost   ?? climateRaw.frost_risk ?? climateRaw.don_riski ?? 'Bilinmiyor'),
    season:  (climateRaw.season  ?? climateRaw.growing_season ?? climateRaw.buyume_sezonu ?? 'Bilinmiyor'),
  };
  const soilCode = (p.soil && (p.soil.code || p.soil.soilCode)) ? String(p.soil.code || p.soil.soilCode).trim() : '';
  const decoded = decodeSoilCode(soilCode);

  const topLines = [];
  if(decoded?.groupTok && decoded.groupText) topLines.push(`<div><span class="label">Büyük toprak grubu:</span> <span class="value"><b>${decoded.groupTok}</b> – ${decoded.groupText}</span></div>`);
  if(decoded?.slope && decoded.slopeText) topLines.push(`<div><span class="label">Eğim sınıfı:</span> <span class="value"><b>${decoded.slope}</b> – ${decoded.slopeText}</span></div>`);
  if(decoded?.ebdDetail){
    topLines.push(`<div><span class="label">Bünye & derinlik:</span> <span class="value">${decoded.ebdDetail.texture} bünye • ${decoded.ebdDetail.depthText} <span class="muted">(Kombinasyon: ${decoded.ebdDetail.code})</span></span></div>`);
  }
  if(decoded?.erosionDeg){
    topLines.push(`<div><span class="label">Su erozyonu derecesi:</span> <span class="value"><b>${decoded.erosionDeg}</b> – ${decoded.erosionText}</span></div>`);
  }
  if(decoded?.capTok && decoded?.cap){
    const sub = (decoded.cap.subText && decoded.cap.subText.length) ? decoded.cap.subText.join(' • ') : 'Alt sınıf yok';
    topLines.push(`<div><span class="label">Arazi kabiliyeti:</span> <span class="value"><b>${decoded.capTok}</b> <span class="muted">(Sınıf: ${decoded.cap.cls}; Alt sınıf: ${sub})</span></span></div>`);
  }
  if(decoded?.other && decoded.other.length){
    topLines.push(`<div><span class="label">Diğer özellikler:</span> <span class="value">${decoded.other.map(x=>`<b>${x.k}</b>: ${x.text}`).join(' • ')}</span></div>`);
  }

  const explainHtml = decoded ? `
    <details class="mini-details" style="margin-top:10px;">
      <summary>Kod çözümü (harita lejantına göre)</summary>
      <div class="small muted" style="margin-top:6px;">Kod: <code>${escapeHtml(decoded.raw)}</code></div>
      <ul class="small" style="margin:8px 0 0 18px;">
        ${decoded.ebdTok ? `<li><b>${escapeHtml(decoded.ebdTok)}</b>: eğim‑bünye‑derinlik kombinasyonu + (varsa) <b>.erozyon</b> derecesi</li>` : ``}
        ${decoded.groupTok ? `<li><b>${decoded.groupTok}</b>: büyük toprak grubu</li>` : ``}
        ${decoded.capTok ? `<li><b>${escapeHtml(decoded.capTok)}</b>: arazi kullanma kabiliyeti sınıfı + alt sınıf(lar)</li>` : ``}
      </ul>
    </details>
  ` : `
    <div class="small muted" style="margin-top:8px;">Toprak kodu okunamadı / bulunamadı.</div>
  `;

  parcelSummaryBody.innerHTML = `
    <div><span class="label">Parsel:</span> <span class="value">${escapeHtml(p.name || p.id)}</span></div>
    <div><span class="label">Köy:</span> <span class="value">${escapeHtml(p.village||'—')}</span> – <span class="label">İlçe:</span> <span class="value">${escapeHtml(p.district||'—')}</span></div>
    <div><span class="label">Toplam alan:</span> <span class="value">${(p.area_da||0).toLocaleString("tr-TR")} da</span></div>
    <div><span class="label">Yıllık su tüketimi (mevcut):</span> <span class="value">${(p.water_m3||0).toLocaleString("tr-TR")} m³</span></div>
    <div><span class="label">Yıllık net kâr (mevcut):</span> <span class="value">${(p.profit_tl||0).toLocaleString("tr-TR")} TL</span></div>
    <hr />
    <div><strong>— Toprak Özeti</strong></div>
    ${soilCode ? `<div class="small muted">Toprak kodu: <code>${escapeHtml(soilCode)}</code></div>` : `<div class="small muted">Toprak kodu: —</div>`}
    ${topLines.join('')}
    ${explainHtml}
    <div style="margin-top:10px;"><strong>— İklim Özeti</strong></div>
    <div>Yıllık yağış: ${climate.rain_mm} mm, ETo: ${climate.eto_mm} mm</div>
    <div>Ortalama sıcaklık: ${Number.isFinite(climate.t_avg)? climate.t_avg.toFixed(1) : '—'} °C</div>
    <div>Don riski: ${escapeHtml(String(climate.frost ?? 'Bilinmiyor'))}</div>
    <div>Büyüme sezonu: ${escapeHtml(String(climate.season ?? 'Bilinmiyor'))}</div>
  `;
}

// Mevcut / önerilen tabloları doldur

// -------------------------
// Optimizasyon motoru (GA / ABC / ACO)
// Amaç: senaryoya göre (su_tasarruf / maks_kar) parsel alanını ürünler arasında paylaştırmak
// Not: Bu demo sürümünde 8–11 ürün arasından optimizasyon yapılır. İleride gerçek ürün-çeşit veri seti ile genişletilir.
// -------------------------

function clamp(v, a, b){ return Math.max(a, Math.min(b, v)); }

// Türkçe yerel ayarlarda ondalık ayırıcı virgül olabildiği için güvenli sayı ayrıştırma
function parseNumFlex(v, fallback){
  if(v===undefined || v===null) return fallback;
  const s = String(v).trim().replace(',', '.');
  const n = Number(s);
  return Number.isFinite(n) ? n : fallback;
}

function normalizeVec(x){
  const s = x.reduce((acc,v)=>acc+Math.max(0,v),0);
  if(!s) return x.map(()=>1/x.length);
  return x.map(v=>Math.max(0,v)/s);
}

function vecToRows(areaDa, crops, x){
  // x: proportions
  const xN = normalizeVec(x);
  // area rounding
  let rows = crops.map((c,i)=>({
    name: c.name,
    area: +(areaDa * xN[i]).toFixed(1),
    waterPerDa: c.waterPerDa,
    profitPerDa: c.profitPerDa,
  }));
  // Fix rounding so sum equals areaDa
  const sumArea = rows.reduce((a,r)=>a+r.area,0);
  const diff = +(areaDa - sumArea).toFixed(1);
  if(Math.abs(diff) >= 0.1){
    // adjust largest area crop
    let j = 0;
    for(let i=1;i<rows.length;i++) if(rows[i].area > rows[j].area) j=i;
    rows[j].area = +(rows[j].area + diff).toFixed(1);
  }
  rows = rows.filter(r=>r.area > 0.0);
  rows.forEach(r=>{
    r.totalWater = r.area * r.waterPerDa;
    r.totalProfit = r.area * r.profitPerDa;
  });
  return rows;
}

function sumMetrics(rows){
  const totalArea = rows.reduce((a,r)=>a+r.area,0);
  const totalWater = rows.reduce((a,r)=>a+r.totalWater,0);
  const totalProfit = rows.reduce((a,r)=>a+r.totalProfit,0);
  return { area: totalArea, water: totalWater, profit: totalProfit, totalArea, totalWater, totalProfit };
}

// --- v54: Sulama randımanı (yöntem bazlı) ---
// Basit varsayımlar: yüzey/karık düşük, yağmurlama orta, damla yüksek.
const IRR_EFF = { surface:0.55, sprinkler:0.70, drip:0.90, pivot:0.80, rainfed:1.00 };
function deliveredWaterPerDa(baseWaterPerDa, irrKey){
  // Koruma: ölçek hatasıyla gelen aşırı büyük değerleri UI'da patlatma.
  const w = clamp(safeNum(baseWaterPerDa), 0, 3000);
  const k = irrKey || 'sprinkler';
  if(k === 'rainfed') return w * 0.20; // destek sulaması varsayımı
  const eff = IRR_EFF[k] || (STATE.irrigEfficiency ?? 0.62);
  return w / Math.max(0.35, eff);
}

// Öneri sulama yöntemi: karık/salma -> damla (sebzede), kuru tahıl -> yağmurlama (destek),
// pivot/yağmurlama -> damla (yüksek su tasarrufu hedefinde)
function recommendedIrrKeyForCrop(cropName, currentKey){
  const nm = (cropName||'').toLowerCase();
  if(currentKey === 'rainfed') return 'sprinkler';
  if(nm.includes('buğday') || nm.includes('arpa') || nm.includes('çavdar')) return currentKey === 'rainfed' ? 'sprinkler' : 'sprinkler';
  // sebze/endüstri bitkilerinde damla hedef
  if(currentKey === 'surface' || currentKey === 'sprinkler' || currentKey === 'pivot') return 'drip';
  return 'drip';
}

function irrigationLabel(key){
  if(key==='drip') return 'Damla';
  if(key==='sprinkler') return 'Yağmurlama';
  if(key==='surface') return 'Karık/Salma';
  if(key==='pivot') return 'Pivot/Lineer';
  if(key==='rainfed') return 'Yağışa bağlı';
  return String(key||'—');
}

// Crop -> irrigation mapping (from backend meta: data/crop_irrigation_map.json)
// In the "Önerilen Ürün Deseni" table we show only the best (improved) irrigation suggestion
// compared to the current/default method. We intentionally do not expose all irrigation
// methods as a dropdown.

function _normIrrLookupKeys(cropName){
  const raw = String(cropName||'');
  const k1 = raw;
  const k2 = normCropName(raw);
  const k3 = normCropKey(raw);
  const k4 = normCropKey(raw).replace(/[()]/g,' ').replace(/\s+/g,' ').trim();
  const k5 = normCropKey(raw).replace(/[()]/g,' ').replace(/\s+/g,'_').trim();
  const k6 = normCropKey(raw).replace(/[()]/g,'_').replace(/\s+/g,'_').trim();
  // also try internal style: spaces->underscore
  const k7 = k2.replace(/\s+/g,'_');
  return [k1,k2,k3,k4,k5,k6,k7].filter(Boolean);
}

function irrigationKeysForCrop(cropName){
  const m = STATE.cropIrrigationMap || {};
  let rec = null;
  for(const k of _normIrrLookupKeys(cropName)){
    if(m && m[k]){ rec = m[k]; break; }
  }
  const currentKey = rec?.current || 'sprinkler';
  const suggestedKey = rec?.recommended || recommendedIrrKeyForCrop(cropName, currentKey);
  return { currentKey, suggestedKey };
}

function objectiveFitness(areaDa, crops, x, scenarioKey, currentTotals, parcel){
  // minimize: lower is better
  const xN = normalizeVec(x);

  const water = areaDa * xN.reduce((acc,xi,i)=>acc + xi*crops[i].waterPerDa, 0);

  // temel kâr
  let profit = areaDa * xN.reduce((acc,xi,i)=>acc + xi*crops[i].profitPerDa, 0);

  // köy/ilçe desen uyumu bonusu (TL)
  if(STATE.villagePatterns && STATE.districtPatterns && parcel){
    const bonus = areaDa * xN.reduce((acc,xi,i)=>{
      const cNorm = normCropName(crops[i].name);
      return acc + xi * contextBonusTlPerDa(parcel, cNorm);
    }, 0);
    profit += bonus;
  }

  // toprak/erozyon uygunluğu: bazı ürün tiplerine küçük ceza/bonus
  if(parcel && parcel.soil){
    const soilAdj = areaDa * xN.reduce((acc,xi,i)=>{
      const t = crops[i].type || cropTypeFromCategory(crops[i].category);
      return acc + xi * soilSuitabilityTlPerDa(parcel.soil, t);
    },0);
    profit += soilAdj;
  }

  // Constraints (soft penalties)
  let penalty = 0;

  // (A) Mutlak su bütçesi kısıtı (yaklaşık: alan oranına göre parsel bütçesi)
  const wBudget = parcelWaterBudget(areaDa);
  if(water > wBudget){
    const over = (water - wBudget) / Math.max(1, wBudget);
    penalty += over * 50.0; // güçlü ceza
  }

  // (A2) Kuraklık riski: su yoğun seçimlere ek ceza
  const r = clamp(STATE.droughtRisk ?? 0, 0, 1);
  penalty += r * (water / Math.max(1, wBudget)) * 2.5;

  // (B) Senaryo kısıtları (mevcut desene göre)
  // NOTE: UI/back-end may send scenario keys in different forms.
  // Normalize so optimization behaves consistently.
  const sk = normalizeScenarioKey(scenarioKey);
  const curW = safeNum(currentTotals?.totalWater ?? currentTotals?.water);
  const curP = safeNum(currentTotals?.totalProfit ?? currentTotals?.profit);

  if(sk === "water_saving"){
    // Farmer-first constraint: keep production profitable (allow some drop, but avoid collapse)
    const minProfit = curP * 0.85;
    if(curP > 0 && profit < minProfit) penalty += (minProfit - profit) / Math.max(1, minProfit) * 12.0;
    // Strongly discourage increasing water compared to current (drought reality)
    if(curW > 0 && water > curW) penalty += ((water - curW) / Math.max(1, curW)) * 30.0;
    // objective: reduce water
    return (water / Math.max(1, curW || wBudget)) + penalty;
  }

  if(sk === "max_profit"){
    // Still respect water reality: don't exceed current too much
    const maxWater = curW * 1.10;
    if(curW > 0 && water > maxWater) penalty += (water - maxWater) / Math.max(1, maxWater) * 10.0;
    return (-(profit / Math.max(1, curP || 1))) + penalty;
  }

  if(sk === "balanced"){
    // Balanced: prefer less water while keeping profit reasonable
    const minProfit = curP * 0.75;
    if(curP > 0 && profit < minProfit) penalty += (minProfit - profit) / Math.max(1, minProfit) * 8.0;
    // weighted tradeoff
    return (water / Math.max(1, curW || wBudget)) - 0.25 * (profit / Math.max(1, curP || 1)) + penalty;
  }

  // current: no optimization, just feasibility penalties
  return 0 + penalty;
}

// GA: continuous proportions
function runGA(areaDa, crops, scenarioKey, currentTotals, parcel, opts={}){
  const n = crops.length;
  const popSize = opts.popSize ?? 40;
  const gens = opts.gens ?? 60;
  const elite = opts.elite ?? 4;
  const mutRate = opts.mutRate ?? 0.18;

  function randVec(){
    const x = Array.from({length:n}, ()=>Math.random());
    return normalizeVec(x);
  }

  function crossover(a,b){
    // blend crossover
    const child = a.map((v,i)=>{
      const t = Math.random();
      return t*v + (1-t)*b[i];
    });
    return normalizeVec(child);
  }

  function mutate(x){
    const y = x.slice();
    for(let i=0;i<n;i++){
      if(Math.random() < mutRate){
        y[i] = clamp(y[i] + (Math.random()-0.5)*0.35, 0, 1);
      }
    }
    return normalizeVec(y);
  }

  let pop = Array.from({length:popSize}, randVec);

  for(let g=0; g<gens; g++){
    const scored = pop.map(x=>({x, f: objectiveFitness(areaDa,crops,x,scenarioKey,currentTotals,parcel)}))
                      .sort((a,b)=>a.f-b.f);
    const next = scored.slice(0,elite).map(s=>s.x);
    while(next.length < popSize){
      // tournament selection
      const a = scored[Math.floor(Math.random()*Math.min(popSize,12))].x;
      const b = scored[Math.floor(Math.random()*Math.min(popSize,12))].x;
      let child = crossover(a,b);
      child = mutate(child);
      next.push(child);
    }
    pop = next;
  }

  const best = pop.map(x=>({x, f: objectiveFitness(areaDa,crops,x,scenarioKey,currentTotals,parcel)}))
                  .sort((a,b)=>a.f-b.f)[0].x;
  return best;
}

// ABC: Artificial Bee Colony (simplified for proportions)
function runABC(areaDa, crops, scenarioKey, currentTotals, parcel, opts={}){
  const n = crops.length;
  const foodCount = opts.foodCount ?? 25;
  const iters = opts.iters ?? 80;
  const limit = opts.limit ?? 20;

  function randVec(){ return normalizeVec(Array.from({length:n}, ()=>Math.random())); }

  let foods = Array.from({length:foodCount}, randVec);
  let trials = Array.from({length:foodCount}, ()=>0);

  function neighbor(x){
    const y = x.slice();
    const i = Math.floor(Math.random()*n);
    const k = Math.floor(Math.random()*n);
    const phi = (Math.random()*2 - 1); // [-1,1]
    y[i] = clamp(y[i] + phi*(y[i] - y[k]), 0, 1);
    return normalizeVec(y);
  }

  function fitnessVal(x){ return objectiveFitness(areaDa,crops,x,scenarioKey,currentTotals,parcel); }

  for(let t=0; t<iters; t++){
    // employed bees
    for(let j=0;j<foodCount;j++){
      const v = neighbor(foods[j]);
      if(fitnessVal(v) < fitnessVal(foods[j])){
        foods[j] = v; trials[j]=0;
      }else trials[j]++;
    }

    // onlooker selection (roulette on inverse fitness)
    const fits = foods.map(fitnessVal);
    const inv = fits.map(f=> 1/(1e-6 + Math.max(0, f + 1))); // keep positive
    const sumInv = inv.reduce((a,b)=>a+b,0);

    for(let o=0;o<foodCount;o++){
      let r = Math.random()*sumInv, pick=0;
      for(let j=0;j<foodCount;j++){ r -= inv[j]; if(r<=0){ pick=j; break; } }
      const v = neighbor(foods[pick]);
      if(fitnessVal(v) < fits[pick]){
        foods[pick] = v; trials[pick]=0;
      }else trials[pick]++;
    }

    // scout
    for(let j=0;j<foodCount;j++){
      if(trials[j] >= limit){
        foods[j] = randVec();
        trials[j] = 0;
      }
    }
  }

  let best = foods[0], bestF = fitnessVal(best);
  for(const x of foods){
    const f = fitnessVal(x);
    if(f < bestF){ best=x; bestF=f; }
  }
  return best;
}

// ACO: Ant Colony (discrete allocations with 20 units = 5% each)
function runACO(areaDa, crops, scenarioKey, currentTotals, parcel, opts={}){
  const n = crops.length;
  const ants = opts.ants ?? 30;
  const iters = opts.iters ?? 60;
  const units = opts.units ?? 20; // 5% resolution
  const evap = opts.evap ?? 0.15;

  // pheromone for each crop choice per unit position
  let tau = Array.from({length:units}, ()=>Array.from({length:n}, ()=>1.0));

  function heuristic(i){
    // scenario-dependent desirability
    if(scenarioKey === "su_tasarruf"){
      return 1/(1 + crops[i].waterPerDa); // less water better
    }
    if(scenarioKey === "maks_kar"){
      return 1 + crops[i].profitPerDa/10000; // more profit better
    }
    // balanced (not used here)
    return 1;
  }
  const eta = crops.map((_,i)=>heuristic(i));

  function construct(){
    const counts = Array.from({length:n}, ()=>0);
    for(let u=0;u<units;u++){
      // probability proportional to tau^a * eta^b
      const a=1.0,b=2.0;
      const weights = tau[u].map((t,i)=>Math.pow(t,a)*Math.pow(eta[i],b));
      const sumW = weights.reduce((x,y)=>x+y,0);
      let r = Math.random()*sumW, pick=0;
      for(let i=0;i<n;i++){ r -= weights[i]; if(r<=0){ pick=i; break; } }
      counts[pick] += 1;
    }
    // proportions
    const x = counts.map(c=>c/units);
    return normalizeVec(x);
  }

  function fit(x){ return objectiveFitness(areaDa,crops,x,scenarioKey,currentTotals,parcel); }

  let globalBest = null, globalBestF = Infinity;

  for(let it=0; it<iters; it++){
    const solutions = [];
    for(let a=0;a<ants;a++){
      const x = construct();
      const f = fit(x);
      solutions.push({x,f});
      if(f < globalBestF){ globalBestF=f; globalBest=x; }
    }

    // evaporate
    for(let u=0;u<units;u++){
      for(let i=0;i<n;i++){
        tau[u][i] *= (1-evap);
        tau[u][i] = Math.max(0.01, tau[u][i]);
      }
    }

    // reinforce best few
    solutions.sort((a,b)=>a.f-b.f);
    const topK = Math.max(1, Math.floor(ants*0.15));
    for(let k=0;k<topK;k++){
      const x = solutions[k].x;
      const delta = 1/(1e-6 + Math.max(0, solutions[k].f + 1));
      for(let u=0;u<units;u++){
        for(let i=0;i<n;i++){
          tau[u][i] += delta * x[i];
        }
      }
    }
  }

  return globalBest ?? normalizeVec(Array.from({length:n}, ()=>1/n));
}


function getCandidateCropsForParcel(p){
  // Senaryo kaynağı önemlidir: Senaryo-2 seçildiğinde, sezon dosyalarında
  // bazı parsel/yıl kombinasyonları eksik olsa bile "anlaşılan ürün havuzu"
  // mutlaka adaylar içinde bulunmalıdır.
  const seasonSource = (document.getElementById('seasonSourceSel')?.value) || STATE.seasonSource || 's1';

  // Senaryo-2: aday havuzu sadece mutabık ürünlerden oluşsun.
  // Sezon dosyası farklı ürünler içerebildiği için (domates/biber vs.)
  // bu modda "candidatesByParcel" kullanmıyoruz.
  if(seasonSource === 's2'){
    ensureScenario2Catalog();
    const catalog = STATE.cropCatalog || {};
    return (STATE.S2_PRIMARY_POOL || S2_PRIMARY_POOL || [])
      .filter(Boolean)
      .map(k=>({
        name: k,
        waterPerDa: clamp(safeNum(catalog[k]?.waterPerDa, S2_DEFAULT_PARAMS[k]?.waterPerDa || 0), 0, 3000),
        profitPerDa: clamp(safeNum(catalog[k]?.profitPerDa, S2_DEFAULT_PARAMS[k]?.profitPerDa || 0), -50000, 50000)
      }))
      .filter(c=>isFinite(c.waterPerDa) && isFinite(c.profitPerDa) && c.waterPerDa>=0);
  }

  // PRIMARY: use enhanced season candidates for this parcel *and selected year* (real data).
  // This makes parcel switching and year switching actually change recommendations.
  const pid = p?.id;
  const y = +STATE.selectedWaterYear;

  // 1) Year-specific candidates
  let m = null;
  if(STATE.candidatesByParcelYear && isFinite(y) && pid){
    const byParcel = STATE.candidatesByParcelYear.get(y);
    m = byParcel ? byParcel.get(pid) : null;
  }

  // 2) Fallback: all-years candidates
  if((!m || !m.size) && STATE.candidatesByParcel && pid){
    m = STATE.candidatesByParcel.get(pid);
  }
  if(m && m.size){
    const arr = [];
    for(const [ck,a] of m.entries()){
      const area = a.area || 1;
      const waterPerDa = a.water / area;
      const profitPerDa = a.profit / area;
      arr.push({ name: ck, waterPerDa, profitPerDa });
    }
    // Crop catalog parametreleri (Kc, ekonomi vb.)
    if(STATE.cropCatalog){
      for(const c of arr){
        const cat = STATE.cropCatalog[normCropName(c.name)];
        if(!cat) continue;

        // Su/da: eksikse katalogdan doldur
        // Only overwrite missing/invalid values. Do NOT treat 0 as invalid (dryland).
        if((!isFinite(c.waterPerDa) || c.waterPerDa<0) && isFinite(cat.waterPerDa) && cat.waterPerDa>=0){
          c.waterPerDa = cat.waterPerDa;
        }

        // Kâr/da: fiyat/teşvik yüklenmişse (override) katalogdaki kârı tercih et
        if(STATE.marketOverridesActive && cat._profit_overridden && isFinite(cat.profitPerDa)){
          c.profitPerDa = cat.profitPerDa;
        }else if((!isFinite(c.profitPerDa)) && isFinite(cat.profitPerDa)){
          c.profitPerDa = cat.profitPerDa;
        }

        // Dinamik meteoroloji aktifse: ET0/yağış + Kc ile sezonluk sulama ihtiyacını hesapla
        if(STATE.dynamicIrrigation){
          const irr = computeSeasonIrrigation(p, c.name);
          if(irr && irr.mode !== "none" && isFinite(irr.sumGross) && irr.sumGross>0){
            // sumGross (mm) ≈ m3/da
            const dyn = irr.sumGross;
            // çok sert sıçramaları azaltmak için harmanla
            const base = (isFinite(c.waterPerDa) && c.waterPerDa>0) ? c.waterPerDa : dyn;
            c.waterPerDa = 0.4*base + 0.6*dyn;
          }
        }
      }
    }
    // Senaryo-2: ürün havuzunu garanti et (meyve + tarla bitkileri)
    if(seasonSource === 's2'){
      const catalog = STATE.cropCatalog || {};
      const must = (STATE.S2_PRIMARY_POOL || []).filter(Boolean);
      const have = new Set(arr.map(x=>normCropName(x.name)));
      for(const ck of must){
        if(have.has(ck)) continue;
        const cat = catalog[ck];
        if(cat && isFinite(cat.waterPerDa) && isFinite(cat.profitPerDa)){
          arr.push({ name: ck, waterPerDa: cat.waterPerDa, profitPerDa: cat.profitPerDa });
        }
      }
    }

    // Allow dryland / rainfed candidates (waterPerDa can be 0).
    // Previously we filtered out waterPerDa==0 which removed cereals/legumes that can be grown
    // with minimal irrigation, leading to empty candidate sets and "0" results.
    return arr
      .map(c=>({
        ...c,
        // Aşırı uç değerleri (ölçek hataları) UI'da patlatmasın diye yumuşak tavan
        waterPerDa: clamp(safeNum(c.waterPerDa,0), 0, 3000),
        profitPerDa: clamp(safeNum(c.profitPerDa,0), -50000, 50000)
      }))
      .filter(c=>isFinite(c.waterPerDa) && isFinite(c.profitPerDa) && c.waterPerDa>=0);
  }

  // FALLBACK (should rarely happen): use global catalog
  let candidates = cropCatalog.slice();
  if(STATE.cropCatalog){
    candidates = candidates.map(c=>{
      const cat = STATE.cropCatalog[normCropName(c.name)];
      return cat ? { ...c, waterPerDa: cat.waterPerDa, profitPerDa: cat.profitPerDa } : c;
    });
  }
  return candidates.filter(c=>isFinite(c.waterPerDa) && isFinite(c.profitPerDa) && c.waterPerDa>=0);
}

// Senaryo-2 bahçe/perennial kısıtı: meyve bahçesi olan parselde ürün değişmez;
// bunun yerine su tasarrufu senaryolarında sulama planı (kısıntılı damla) önerilir.
const PERENNIAL_SET = new Set([
  // Senaryo-2: çok yıllık ürünler (bahçe + bağ + yonca)
  // Not: burada anahtarlar normCropName() çıktısı ile aynı olmalı.
  normCropName('ELMA'),
  normCropName('KİRAZ'),
  normCropName('BAĞ (ÜZÜM)'),
  normCropName('CEVİZ'),
  normCropName('ARMUT'),
  normCropName('ŞEFTALİ'),
  normCropName('NEKTARİN'),
  normCropName('KAYISI'),
  normCropName('VİŞNE'),
  normCropName('ERİK'),
  normCropName('YONCA (YEŞİLOT)')
]);

function isPerennialCropName(name){
  const k = normCropName(name);
  return PERENNIAL_SET.has(k);
}

function dominantCropNameForParcel(p){
  // currentRows üzerinden en büyük alanlı ürünü al
  let best = null;
  for(const c of (p.cropCurrent||[])){
    if(!best || (c.area||0) > (best.area||0)) best = c;
  }
  return best ? best.name : null;
}

function s2IrrigationAdjust(scenarioKey){
  if(scenarioKey === 'su_tasarruf') return {
    wmul:0.80,
    pmul:0.92,
    label:'Damla sulama + kontrollü kısıntı (%20). Öneri: gece/erken sabah sulama, haftalık-2/3 periyot, toprak nem takibi ve malç ile buharlaşma azaltımı.'
  };
  if(scenarioKey === 'maks_kar') return {
    wmul:1.00,
    pmul:1.00,
    label:'Standart sulama (verim odaklı). Öneri: damla/yağmurlama bakım-onarım, filtre temizliği, basınç kontrolü, kritik fenolojik dönemlerde su stresi yaratmama.'
  };
  return {
    wmul:0.90,
    pmul:0.96,
    label:'Damla sulama + hafif kısıntı (%10). Öneri: sulama zamanlamasını ETo/iklime göre ayarla, basınç-regülatör kullan, sızdırmazlık kontrolü yap.'
  };
}



function pairingForCrop(name){
  const raw = String(name||'').trim();
  const candidates = [];
  if(raw) candidates.push(raw);
  if(raw && raw.includes('_')) candidates.push(raw.replace(/_/g,' '));
  if(raw) candidates.push(prettyCropName(raw));
  if(raw && raw.includes('_')) candidates.push(prettyCropName(raw).replace(/_/g,' '));
  // direct match
  for(const c of candidates){
    if(S1_PAIRING[c]) return S1_PAIRING[c];
  }
  // case-insensitive match (space/underscore normalized)
  const target = raw.replace(/_/g,' ').toUpperCase();
  for(const k in S1_PAIRING){
    if(String(k).replace(/_/g,' ').toUpperCase()===target) return S1_PAIRING[k];
  }
  return null;
}

function runOptimization(p, scenarioKey, algoKey){
  // Defensive: async UI flows may call this before parcels are fully
  // hydrated. Make sure we never crash the whole UI.
  if(!p){
    return {
      scenarioKey,
      algoKey,
      currentRows: [],
      currentTotals: { totalWater:0, totalProfit:0, waterPerDa:0, profitPerDa:0 },
      bestRows: [],
      bestTotals: { totalWater:0, totalProfit:0, waterPerDa:0, profitPerDa:0 },
      note: 'parcel undefined'
    };
  }

  // Guarantee a baseline crop breakdown exists.
  ensureBaselineCropCurrent(p);

  if(!Array.isArray(p.cropCurrent)) p.cropCurrent = [];
  if(!p.cropCurrent.length){
    // Still nothing: return a safe empty result.
    return {
      scenarioKey,
      algoKey,
      currentRows: [],
      currentTotals: { totalWater:0, totalProfit:0, waterPerDa:0, profitPerDa:0 },
      bestRows: [],
      bestTotals: { totalWater:0, totalProfit:0, waterPerDa:0, profitPerDa:0 },
      note: 'cropCurrent missing'
    };
  }

  const currentRows = p.cropCurrent.map(c=>({
    name: c.name,
    area: c.area,
    season: c.season || '—',
    irrigationCurrentKey: c.irrigationCurrentKey || irrKeyFromText(c.irrigationCurrentText),
    irrigationCurrentText: c.irrigationCurrentText || '—',
    // tabloda gösterilecek su: yönteme göre teslim edilen (gross) su
    waterPerDa: deliveredWaterPerDa(c.waterPerDa, c.irrigationCurrentKey || irrKeyFromText(c.irrigationCurrentText)),
    profitPerDa: c.profitPerDa,
    totalWater: c.area*deliveredWaterPerDa(c.waterPerDa, c.irrigationCurrentKey || irrKeyFromText(c.irrigationCurrentText)),
    totalProfit: c.area*c.profitPerDa
  }));
  const currentTotals = sumMetrics(currentRows);

  // Senaryo-2: meyve bahçesi/perennial parselde ürün değişmez.
  // Su tasarruf / dengeli senaryolarda sulama planı ile su azaltımı uygulanır.
  const seasonSource = (document.getElementById('seasonSourceSel')?.value) || STATE.seasonSource || 's1';
  const domName = dominantCropNameForParcel(p);
  if(seasonSource === 's2' && domName && isPerennialCropName(domName) && scenarioKey !== 'mevcut'){
    const adj = s2IrrigationAdjust(scenarioKey);
    const rows = currentRows.map(r=>{
      const waterPerDa = r.waterPerDa * adj.wmul;
      const profitPerDa = r.profitPerDa * adj.pmul;
      return {
        ...r,
        waterPerDa,
        profitPerDa,
        totalWater: r.area * waterPerDa,
        totalProfit: r.area * profitPerDa,
      };
    });
    const totals = sumMetrics(rows);
    const waterSaving = safeNum(currentTotals.water) - safeNum(totals.water);
    return {
      rows,
      totals,
      cropsUsed: [domName],
      irrigationPlan: adj.label,
      lockedCrop: domName,
      waterSavingM3: Math.round(waterSaving),
      profitDeltaTL: Math.round(safeNum(totals.profit) - safeNum(currentTotals.profit))
    };
  }

  if(scenarioKey === "mevcut"){
    return { rows: currentRows.map(r=>({ ...r })), totals: currentTotals };
  }

  // --- v54: Maksimum 2 ürünlü ayrık arama (1. ürün + (uygunsa) 2. ürün) ---
  // Amaç: suyu azaltırken çiftçinin kârını korumak (alt sınır: mevcut kârın %90'ı)
  const profitMin = currentTotals.profit * 0.90;

  // Robust crop meta lookup:
  // Some sources use underscores (NOHUT_KURU) while catalog keys use spaces/parentheses.
  // If we fail here, recommended rows show 0 water/profit and look "empty".
  function cropMeta(name){
    const cat = STATE.cropCatalog || {};
    const raw = String(name||'').trim();
    const variants = [];
    if(raw) variants.push(raw);
    if(raw && raw.includes('_')) variants.push(raw.replace(/_/g,' '));
    const pretty = prettyCropName(raw);
    if(pretty && pretty !== raw) variants.push(pretty);
    if(pretty && pretty.includes('_')) variants.push(pretty.replace(/_/g,' '));

    // Try several normalized keys (uppercased, diacritics-stripped).
    for(const v of variants){
      const k = normCropName(v);
      if(cat[k]){
        let wNet = safeNum(cat[k].waterPerDa);
        let pr = safeNum(cat[k].profitPerDa);
        // If water is missing/zero, try season-derived net water (year-specific)
        if(!(isFinite(wNet) && wNet>0)){
          const ws = getNetM3PerDaFromSeasons(STATE.selectedWaterYear, k);
          if(isFinite(ws) && ws>0) wNet = ws;
        }
        return { waterNet: wNet, profit: pr };
      }
    }
    // Last resort: scan for close match by space/underscore normalization.
    const target = normCropName(raw).replace(/_/g,' ');
    for(const k in cat){
      if(normCropName(k).replace(/_/g,' ') === target){
        let wNet = safeNum(cat[k].waterPerDa);
        let pr = safeNum(cat[k].profitPerDa);
        if(!(isFinite(wNet) && wNet>0)){
          const ws = getNetM3PerDaFromSeasons(STATE.selectedWaterYear, normCropName(k));
          if(isFinite(ws) && ws>0) wNet = ws;
        }
        return { waterNet: wNet, profit: pr };
      }
    }
    return { waterNet: 0, profit: 0 };
  }

  function buildPlanRows(c1, c2){
    const A = safeNum(p.area_da);
    const pair = pairingForCrop(c1) || {season1:'—', irr1:'—', secondary:'—', season2:'—', irr2:'—'};
    const c2Resolved = c2 || null;
    const s1 = pair.season1 || '—';
    const s2 = pair.season2 || '—';

    // --- Alan kuralı ---
    // Eğer 1. ve 2. ürün farklı sezonlardaysa (rotasyon), aynı parsel alanında ardışık ekilir.
    // Bu durumda HER sezonun alan toplamı parsel alanına eşit olmalı; alanı 70/30 bölmeyiz.
    // Eğer aynı sezon (veya belirsiz) ise, çeşitlendirme varsayımı ile 70/30 bölünmüş alan kullanılabilir.
    const isRotation = c2Resolved && (String(s1).toLowerCase() !== String(s2).toLowerCase()) && s1 !== '—' && s2 !== '—';
    let a1, a2;
    if (isRotation) {
      a1 = +A.toFixed(1);
      a2 = +A.toFixed(1);
    } else {
      // 0.1 da hassasiyet: tabloda gösterilen alan ile toplamların tutarlı kalması için alanı burada da yuvarlıyoruz.
      const a1Raw = A * 0.7;
      const a2Raw = Math.max(0, A - a1Raw);
      a1 = +a1Raw.toFixed(1);
      a2 = +a2Raw.toFixed(1);
      // Yuvarlama sonrası küçük sapmalar olursa (ör. 40.6 yerine 40.5), toplamı tekrar A'ya oturt.
      const sumA = a1 + a2;
      if (A > 0 && sumA > 0 && Math.abs(sumA - A) > 0.05) {
        const k = A / sumA;
        a1 = +(a1 * k).toFixed(1);
        a2 = +(Math.max(0, A - a1)).toFixed(1);
      }
    }

    const m1 = cropMeta(c1);
    const m2 = c2Resolved ? cropMeta(c2Resolved) : {waterNet:0, profit:0};

    const irr1CurKey = irrKeyFromText(pair.irr1);
    const irr2CurKey = c2Resolved ? irrKeyFromText(pair.irr2) : 'rainfed';
    const irr1RecKey = recommendedIrrKeyForCrop(c1, irr1CurKey);
    const irr2RecKey = c2Resolved ? recommendedIrrKeyForCrop(c2Resolved, irr2CurKey) : 'rainfed';

    // Sulama yükseltme maliyeti (çok kaba): damlaya geçişte da başına küçük yatırım bedeli
    const upgradeCostDa = (from,to)=>{
      if(from===to) return 0;
      if(to==='drip') return 250; // damla dönüşüm
      if(to==='sprinkler' && from==='surface') return 150;
      return 50;
    };

    const p1 = m1.profit - upgradeCostDa(irr1CurKey, irr1RecKey);
    const p2 = c2Resolved ? (m2.profit - upgradeCostDa(irr2CurKey, irr2RecKey)) : 0;

    const w1 = deliveredWaterPerDa(m1.waterNet, irr1RecKey);
    const w2 = c2Resolved ? deliveredWaterPerDa(m2.waterNet, irr2RecKey) : 0;

    const rows = [];
    rows.push({
      name: prettyCropName(c1),
      season: s1,
      irrigationSuggested: irrigationLabel(irr1RecKey),
      // Keep NET (field) water requirement so the UI can compute delivered (gross) water
      // consistently based on the shown irrigation method.
      _baseWaterPerDa: safeNum(m1.waterNet, 0),
      area: +a1.toFixed(1),
      waterPerDa: +w1.toFixed(3),
      profitPerDa: +p1.toFixed(3),
      totalWater: a1*w1,
      totalProfit: a1*p1
    });
    if(c2Resolved){
      rows.push({
        name: prettyCropName(c2Resolved),
        season: s2,
        irrigationSuggested: irrigationLabel(irr2RecKey),
        _baseWaterPerDa: safeNum(m2.waterNet, 0),
        area: +a2.toFixed(1),
        waterPerDa: +w2.toFixed(3),
        profitPerDa: +p2.toFixed(3),
        totalWater: a2*w2,
        totalProfit: a2*p2
      });
    }
    return rows;
  }

  // --- Aday havuzları (sezon veri setine göre) ---
  // Senaryo-1: 15 ana ürün + geniş 2. ürün havuzu
  // Senaryo-2: mutabık kalınan ürün listesi (meyve + tarla) ve sadece sınırlı 2. ürün
  //            (nadas gibi). Böylece "Senaryo-2 seçili ama ürünler değişmiyor" sorunu çözülür.
  let primaryCandidates = S1_PRIMARY_CROPS.slice();
  let secondaryPool = Array.from(new Set([
    ...S1_SECONDARY_CROPS,
    'Buğday (Dane)','Arpa (Dane)','Silajlık Mısır','Fiğ (Yeşilot)','Yem Bezelyesi',
    'Ayçiçeği','Ayçiçeği (Yağlık)','Marul','Ispanak','Fasulye (Taze)','Kabak (Çerezlik)'
  ]));
  if(seasonSource === 's2'){
    primaryCandidates = S2_PRIMARY_RAW.slice();
    // Senaryo-2'de 2. ürün seçeneklerini sade tutuyoruz.
    secondaryPool = ['NADAS'];

    // ✅ KRİTİK KURAL: Bahçe/bağ parseli DEĞİLSE (B/Bs/V/Vs yoksa)
    // meyve/bağ gibi çok yıllık bahçe ürünlerini ÖNERME.
    // (Tarla parselinde kiraz/elma önermek gerçekçi değil.)
    const lu = landUseCodeFromSoilUnit(p.soil_unit_code || '');
    const allowFruitVine = !!lu;
    if(!allowFruitVine){
      primaryCandidates = primaryCandidates.filter(c=>!isS2FruitVine(c));
    }
  }

  // Uyum kuralı: aynı familyadan kaçın
  const fam = (STATE && STATE.cropFamilyMap) ? STATE.cropFamilyMap : {};
  const sameFam = (a,b)=>{ const fa=fam[prettyCropName(a)]||fam[a]||fam[normCropName(a)]; const fb=fam[prettyCropName(b)]||fam[b]||fam[normCropName(b)]; return fa && fb && fa===fb; };

  const scorePlan = (rows)=>{
    const t = sumMetrics(rows);
    // senaryoya göre skor: su tasarruf => su ağırlık, max_kar => kâr ağırlık, dengeli => ikisi
    const water = t.water;
    const profit = t.profit;
    if(profit < profitMin) return { ok:false, score: Number.POSITIVE_INFINITY, totals:t };
    let score;
    if(scenarioKey === 'su_tasarruf') score = water - 0.10*profit;
    else if(scenarioKey === 'maks_kar') score = -profit + 0.05*water;
    else score = water - 0.05*profit;
    return { ok:true, score, totals:t };
  };

  let best = null;
  // Su tasarrufu senaryosu için ayrıca "en düşük su" adayını takip et
  // (kâr eşiği sağlansa da sağlanmasa da), böylece su artışı gibi
  // çiftçiyi şaşırtan sonuçlar engellenir.
  let bestMinWater = null;
  const seed = _hashInt(String(algoKey||'ga')) + _hashInt(p.id||'P');
  for(const c1 of primaryCandidates){
    // Ön tanımlı eşleşme (Senaryo-1 için). Senaryo-2'de geniş eşleşme
    // kurallarını kullanmıyoruz; yalnızca sınırlı 2. ürün (ör. nadas)
    // denenir.
    const defPair = (seasonSource === 's2') ? null : (S1_PAIRING[c1] ? S1_PAIRING[c1].secondary : null);
    const defOpts = [];
    if(defPair && defPair !== '–' && defPair !== '-'){
      if(defPair.includes('/')) defOpts.push(...defPair.split('/').map(x=>x.trim()).filter(Boolean));
      else defOpts.push(defPair);
    }
    const c2Candidates = [...new Set([
      null,
      ...defOpts,
      ...secondaryPool
    ])].filter(c2=>!c2 || !sameFam(c1,c2));

    for(const c2 of c2Candidates){
      const rows = buildPlanRows(c1, c2);
      const res = scorePlan(rows);
      if(!res.ok) continue;
      if(!best || res.score < best.score || (res.score===best.score && ((seed%2)===0))){
        best = { rows, totals: res.totals, score: res.score, c1, c2 };
      }

      // min-water tracker (only meaningful for su_tasarruf)
      if(scenarioKey === 'su_tasarruf'){
        if(!bestMinWater || res.totals.water < bestMinWater.totals.water){
          bestMinWater = { rows, totals: res.totals, score: res.score, c1, c2 };
        }
      }
    }
  }

  if(!best){
    // Güvenli fallback: mevcut desen
    return { rows: currentRows.map(r=>({ ...r })), totals: currentTotals, irrigationPlan: 'Mevcut (kâr eşiği sağlanamadı)' };
  }

  // --- Sert su tasarrufu kuralı ---
  // Kullanıcı beklentisi: "Su tasarrufu" seçiliyken öneri, mevcut desenden
  // DAHA FAZLA su tüketmemeli. Eğer skor en iyisi suyu artırıyorsa,
  // eldeki adaylar içindeki en düşük su planına geri dön.
  if(scenarioKey === 'su_tasarruf'){
    const curW = safeNum(currentTotals.water, 0);
    const bestW = safeNum(best.totals?.water, 0);
    const minW  = safeNum(bestMinWater?.totals?.water, Number.POSITIVE_INFINITY);

    // 1) Her zaman en düşük su planını tercih et (kâr eşiği sağlandıktan sonra).
    if(bestMinWater && isFinite(minW) && minW <= bestW){
      best = { ...bestMinWater, note: 'Su tasarrufu: en düşük su planı seçildi' };
    }

    // 2) Su tasarrufu hedefinde su artışına izin verme.
    // Eğer en düşük su planı bile mevcut desenden fazla su istiyorsa, mevcut deseni koru.
    const finalW = safeNum(best?.totals?.water, 0);
    if(curW > 0 && finalW > curW + 1e-6){
      return { rows: currentRows.map(r=>({ ...r })), totals: currentTotals, irrigationPlan: 'Su tasarrufu: öneri suyu artırdığı için mevcut desen korundu' };
    }
  }

  const irrigationPlan = 'Sulama önerisi: ' + best.rows.map(r=>`${r.name} → ${r.irrigationSuggested}`).join(' | ');
  return { rows: best.rows, totals: best.totals, cropsUsed: [best.c1, best.c2].filter(Boolean), irrigationPlan };
}

function getOptimizationResult(parcelId, scenarioKey, algoKey){
  optimizationCache[parcelId] ??= {};
  optimizationCache[parcelId][scenarioKey] ??= {};
  if(!optimizationCache[parcelId][scenarioKey][algoKey]){
    const p = parcelData.find(x=>x.id===parcelId);
    optimizationCache[parcelId][scenarioKey][algoKey] = runOptimization(p, scenarioKey, algoKey);
  }
  return optimizationCache[parcelId][scenarioKey][algoKey];
}


function computeCropData(p, scenarioKey, algoKey) {
  // Mevcut desen: her zaman runOptimization içindeki su/da (sulama randımanı dahil) ile hesapla
  const curRes = runOptimization(p, 'mevcut', algoKey);
  const current = (curRes.rows || []).map(r=>({ ...r, irrigationSuggested: undefined }));

  // Önerilen: küresel su bütçesi uygulanmış havza planından çek
  const basin = computeBasinPlan(scenarioKey, algoKey);
  const opt = basin.plan[p.id] || getOptimizationResult(p.id, scenarioKey, algoKey);
  const pid = String(p.id);

  const recommended = (opt.rows || []).map((r) => {
    const name = r.name;
    const area = safeNum(r.area, 0);
    // Some producers already store delivered (gross) water in r.waterPerDa.
    // Prefer explicit NET base water if available to avoid double-adjusting.
    const baseWaterPerDa = safeNum((r._baseWaterPerDa ?? r.baseWaterPerDa ?? r.waterPerDa), 0);
    const profitPerDa = safeNum(r.profitPerDa, 0);
    const keys = irrigationKeysForCrop(name);
    const cropKey = (_normIrrLookupKeys(name)[1] || String(name||''));

    // UI shows gross water (m3/da) under the (single) suggested irrigation method.
    // We intentionally do NOT offer every possible method here; the farmer sees only
    // the improved suggestion (if any) relative to the current/default method.
    const suggestedKey = keys.suggestedKey;
    const waterPerDa = deliveredWaterPerDa(baseWaterPerDa, suggestedKey);
    const totalWater = area * waterPerDa;
    const totalProfit = area * profitPerDa;

    // Season may be missing for some sources (e.g., NOHUT_KURU).
    // Try to infer from the pairing catalog; otherwise keep as "—".
    let season = (String(r.season||'').trim() || '—');
    if(!season || season === '—'){
      const pair = pairingForCrop(name);
      if(pair && pair.season1) season = pair.season1;
      // Lightweight heuristic fallback for common dryland crops
      if((!season || season === '—')){
        const nn = normCropName(name).replace(/_/g,' ');
        if(nn.includes('NOHUT')) season = 'Yazlık';
        else if(nn.includes('BUGDAY') || nn.includes('ARPA') || nn.includes('CAVDAR')) season = 'Kışlık';
      }
    }

    return {
      name,
      area,
      season,
      // irrigation
      irrigationCurrentKey: keys.currentKey,
      irrigationSuggestedKey: suggestedKey,
      irrigationSuggestedText: irrigationLabel(suggestedKey),
      // keep baseline for savings calc
      _baseWaterPerDa: baseWaterPerDa,
      waterPerDa,
      profitPerDa,
      totalWater,
      totalProfit,
      _cropKey: cropKey,
    };
  });

  // Recompute recommended totals (because irrigation method can be changed in the UI)
  const recTotalsAdj = sumMetrics(recommended);
  // Baseline: what if farmer kept CURRENT irrigation methods for the recommended crops?
  const recWaterCurrentIrr = recommended.reduce((acc, rr) => {
    const w = deliveredWaterPerDa(safeNum(rr._baseWaterPerDa, rr.waterPerDa), rr.irrigationCurrentKey);
    return acc + safeNum(rr.area,0) * w;
  }, 0);

  return {
    current,
    currentTotals: sumMetrics(current),
    rec: recommended,
    recTotals: {
      water: recTotalsAdj.water,
      profit: recTotalsAdj.profit,
      water_eff: recTotalsAdj.water > 0 ? (recTotalsAdj.profit / recTotalsAdj.water) : 0,
      water_current_irrig: recWaterCurrentIrr,
      water_saving_m3: Math.max(0, recWaterCurrentIrr - recTotalsAdj.water),
      water_saving_pct: recWaterCurrentIrr > 0 ? (Math.max(0, recWaterCurrentIrr - recTotalsAdj.water) / recWaterCurrentIrr) : 0,
    },
    recMeta: { irrigationPlan: opt.irrigationPlan || null, lockedCrop: opt.lockedCrop || null },
  };
}

function renderTables() {
  const p = parcelData.find((x) => x.id === selectedParcelId);
  let { current, currentTotals, rec, recTotals, recMeta } = computeCropData(p, selectedScenario, selectedAlgo);

  // --- SEZON / ROTASYON ALAN TUTARLILIĞI ---
  // Rotasyon (örn. Yazlık + Kışlık) aynı parsel alanında ardışık yapılır.
  // Bu durumda her sezonun toplam alanı parsel alanına eşit olmalıdır (yıllık toplam alana bölünmez).
  // Daha önceki sürümlerde öneri/mecut satır alanları tüm satırlar toplamı parsel alanına eşitlenecek
  // şekilde ölçekleniyordu; bu da rotasyonda "alan bölünmüş" gibi yanlış bir görüntü oluşturuyordu.
  const targetAreaDa = safeNum(p && p.area_da, 0);
  const scaleAreasToParcelBySeason = (rows) => {
    if (!Array.isArray(rows) || !rows.length || !(targetAreaDa > 0)) return rows;
    const groups = new Map(); // season -> rows
    for (const r of rows) {
      const s = String(r.season || '—');
      if (!groups.has(s)) groups.set(s, []);
      groups.get(s).push(r);
    }
    // Eğer tek sezon varsa eski davranışı koru (çeşitlendirme / aynı sezonda iki ürün).
    if (groups.size <= 1) return rows;

    const out = rows.map((r) => ({ ...r }));
    // index by object identity position
    const idxMap = new Map();
    rows.forEach((r, i) => idxMap.set(r, i));

    for (const [season, rs] of groups.entries()) {
      const sumA = rs.reduce((a, x) => a + safeNum(x.area, 0), 0);
      if (!(sumA > 0)) continue;
      const relDiff = Math.abs(sumA - targetAreaDa) / Math.max(targetAreaDa, 1e-9);
      // Sezon toplamı parsel alanından sapıyorsa, o sezon satırlarını parsel alanına ölçekle
      if (relDiff > 0.005) {
        const k = targetAreaDa / sumA;
        for (const r of rs) {
          const i = idxMap.get(r);
          if (i == null) continue;
          const area = safeNum(r.area, 0) * k;
          const waterPerDa = safeNum(r.waterPerDa, 0);
          const profitPerDa = safeNum(r.profitPerDa, 0);
          out[i].area = area;
          out[i].totalWater = waterPerDa * area;
          out[i].totalProfit = profitPerDa * area;
        }
      }
    }
    return out;
  };

  // Uygula: Hem mevcut hem öneri satırlarında sezon bazlı alan ölçekleme
  if (targetAreaDa > 0) {
    current = scaleAreasToParcelBySeason(current);
    currentTotals = sumMetrics(current);
    if (Array.isArray(rec) && rec.length) {
      rec = scaleAreasToParcelBySeason(rec);
      if (recTotals) {
        const recWater = rec.reduce((a, r) => a + safeNum(r.totalWater, 0), 0);
        const recProfit = rec.reduce((a, r) => a + safeNum(r.totalProfit, 0), 0);
        // Baseline: recommended crops under CURRENT irrigation methods
        const recWaterCurIrr = rec.reduce((acc, rr) => {
          const w = deliveredWaterPerDa(safeNum(rr._baseWaterPerDa, rr.waterPerDa), rr.irrigationCurrentKey);
          return acc + safeNum(rr.area, 0) * w;
        }, 0);
        recTotals = {
          ...recTotals,
          water: recWater,
          profit: recProfit,
          water_eff: recWater > 0 ? (recProfit / recWater) : 0,
          water_current_irrig: recWaterCurIrr,
          water_saving_m3: Math.max(0, recWaterCurIrr - recWater),
          water_saving_pct: recWaterCurIrr > 0 ? (Math.max(0, recWaterCurIrr - recWater) / recWaterCurIrr) : 0,
        };
      }
    }
  }

  // --- v57b: Önerilen desen alanlarını sezonsal mantıkla parsel alanına normalize et ---
  // Bazı algoritma çıktılarında (özellikle GA/ABC/ACO) alanlar yanlış ölçeklenebiliyor (örn. 5.8 da parselde 40.6 da).
  // Çiftçi arayüzünde bunu asla göstermemeliyiz; her sezon parsel alanı kadar kullanılır.
  if (Array.isArray(rec) && rec.length && targetAreaDa > 0) {
    rec = normalizeRowsBySeasonToParcelArea(targetAreaDa, rec);
    const recWater = rec.reduce((a, r) => a + safeNum(r.totalWater, 0), 0);
    const recProfit = rec.reduce((a, r) => a + safeNum(r.totalProfit, 0), 0);
    recTotals = { ...(recTotals || {}), water: recWater, profit: recProfit, water_eff: recWater > 0 ? recProfit / recWater : 0 };
    recMeta = { ...(recMeta || {}), area_normalized_to_parcel: true };
  }

  // --- Alan tutarlılığı (gösterim + toplamlar) ---
  // Not: Rotasyonlu planlarda alanlar sezon bazında ölçeklenir (yukarıda). Bu nedenle
  // burada "tüm satırlar toplamını" parsel alanına zorla eşitlemiyoruz.
  // Tek sezonlu (aynı sezonda çeşitlendirme) durumda alanlar zaten parsel alanına yakın olmalıdır.
  // Eğer çok küçük yuvarlama sapmaları varsa, tek sezon durumunda hafif ölçekle.
  if (Array.isArray(rec) && rec.length && targetAreaDa > 0) {
    const seasons = new Set(rec.map(r => String(r.season || '—')));
    if (seasons.size <= 1) {
      const sumRec = rec.reduce((a, r) => a + safeNum(r.area, 0), 0);
      if (sumRec > 0) {
        const relDiff = Math.abs(sumRec - targetAreaDa) / Math.max(targetAreaDa, 1e-9);
        if (relDiff > 0.005) {
          const k = targetAreaDa / sumRec;
          rec = rec.map((r) => {
            const area = safeNum(r.area, 0) * k;
            const waterPerDa = safeNum(r.waterPerDa, 0);
            const profitPerDa = safeNum(r.profitPerDa, 0);
            return {
              ...r,
              area,
              totalWater: waterPerDa * area,
              totalProfit: profitPerDa * area,
            };
          });
          const recWater = rec.reduce((a, r) => a + safeNum(r.totalWater, 0), 0);
          const recProfit = rec.reduce((a, r) => a + safeNum(r.totalProfit, 0), 0);
          recTotals = {
            ...(recTotals || {}),
            water: recWater,
            profit: recProfit,
            water_eff: recWater > 0 ? recProfit / recWater : 0,
          };
          recMeta = { ...(recMeta || {}), area_scaled: true, area_scale_factor: k };
        }
      }
    }
  }

  // Kullanıcı "Optimizasyonu Çalıştır" demeden, önceki parsel/senaryodan kalan
  // öneri desenini göstermeyelim.
  const canShowOpt = (selectedScenario === "mevcut") || canShowOptimizedForCurrentSelection();
  if (!canShowOpt) {
    rec = [];
    recTotals = null;
  }

  const tbodyCur = document.querySelector("#tblCurrent tbody");
  const tbodyRec = document.querySelector("#tblRecommended tbody");
  tbodyCur.innerHTML = "";
  tbodyRec.innerHTML = "";

  if (!canShowOpt) {
    tbodyRec.innerHTML = `
      <tr>
        <td colspan="8" style="text-align:center; padding:14px; color:#6b7280;">
          Bu parsel için önerilen deseni görmek için <b>Optimizasyonu Çalıştır</b> butonuna basın.
        </td>
      </tr>
    `;
  }

  const makeRow = (r, mode) => {
    const irr = (mode==='cur')
      ? (r.irrigationCurrentText || irrigationLabel(r.irrigationCurrentKey) || r.irrigationCurrent || '—')
      : null;

    const irrCell = (mode==='cur')
      ? irr
      : (()=>{
          const curK = String(r.irrigationCurrentKey||'');
          const sugK = String(r.irrigationSuggestedKey||'');
          const sugLbl = irrigationLabel(sugK) || r.irrigationSuggestedText || '—';
          const curLbl = irrigationLabel(curK) || '—';
          // Only show an "improved" suggestion. If the suggested method is the same as current,
          // just show it as a plain label (no dropdown).
          if(!sugK || sugK === curK){
            return `<div class="irr-cell"><div>${escapeHtml(sugLbl)}</div></div>`;
          }
          return `<div class="irr-cell"><div>${escapeHtml(sugLbl)}</div><div class="irr-hint">Mevcut: ${escapeHtml(curLbl)}</div></div>`;
        })();
    return `
    <tr>
      <td>${r.name}</td>
      <td>${r.season || '—'}</td>
      <td>${irrCell}</td>
      <td>${r.area.toFixed(1)}</td>
      <td>${r.waterPerDa.toLocaleString("tr-TR")}</td>
      <td>${Math.round(r.totalWater).toLocaleString("tr-TR")}</td>
      <td>${r.profitPerDa.toLocaleString("tr-TR")}</td>
      <td>${Math.round(r.totalProfit).toLocaleString("tr-TR")}</td>
    </tr>
  `;
  };

  current.forEach((r) => (tbodyCur.innerHTML += makeRow(r,'cur')));
  if (canShowOpt) {
    rec.forEach((r) => (tbodyRec.innerHTML += makeRow(r,'rec')));
  }

  const footerCur = document.getElementById("tblCurrentFooter");
  const footerRec = document.getElementById("tblRecommendedFooter");

  const effCur = currentTotals.profit / Math.max(1e-9, currentTotals.water);
  // Not: Optimizasyon çalıştırılmadıysa recTotals null olabilir.
  // Bu durumda öneri tablosu/özetleri kırmadan "Optimizasyonu çalıştırın" uyarısı gösterilir.
  const effRec = (recTotals && recTotals.water != null && recTotals.profit != null)
    ? (recTotals.profit / Math.max(1e-9, recTotals.water))
    : 0;
  const fmtEff = (v)=>{
    if(!isFinite(v)) return "0";
    if(v < 0) return v.toFixed(2);
    if(v < 1) return v.toFixed(3);
    return v.toFixed(1);
  };

  // Başlık: kapsamı kullanıcıya net göster
  const titleEl = document.getElementById('metricsTitle');
  if(titleEl){
    titleEl.textContent = (selectedParcelId === '__ALL__')
      ? 'Senaryo Özeti (15 parsel toplamı)'
      : `Senaryo Özeti (Seçili parsel: ${selectedParcelId})`;
  }

  footerCur.textContent = `Mevcut toplam su: ${Math.round(
    currentTotals.water
  ).toLocaleString("tr-TR")} m³ | Mevcut toplam net kâr: ${Math.round(
    currentTotals.profit
  ).toLocaleString("tr-TR")} TL | Su verimliliği: ${fmtEff(effCur)} TL/m³`;

  // Öneri footer ve açıklanabilirlik kutuları sadece optimizasyon sonucu varsa hesaplanmalı.
  if (!canShowOpt || !recTotals) {
    if (footerRec) {
      footerRec.textContent = "Bu parsel için önerilen deseni görmek için 'Optimizasyonu Çalıştır' butonuna basın.";
    }
    const explainBox = document.getElementById("explainBox");
    if (explainBox) {
      explainBox.innerHTML = `<div style="opacity:.9">Öneriler ve kısıt değerlendirmesi, optimizasyon çalıştırıldıktan sonra gösterilir.</div>`;
    }
    // Diğer kutular da boş kalmasın
    const deliveryBox = document.getElementById("deliveryBox");
    if (deliveryBox) {
      deliveryBox.innerHTML = `<div style="opacity:.9">Aylık kapasite kontrolü için önce optimizasyon sonucunu üretin.</div>`;
    }
    const irrigPlanBox = document.getElementById("irrigPlanBox");
    if (irrigPlanBox) {
      irrigPlanBox.innerHTML = `<div style="opacity:.9">Sulama planı, önerilen desen oluştuğunda hesaplanır.</div>`;
    }
    const rotationBox = document.getElementById("rotationBox");
    if (rotationBox) {
      rotationBox.innerHTML = `<div style="opacity:.9">Rotasyon / 2. ürün önerisi, optimizasyon sonucuna göre güncellenir.</div>`;
    }
    // Opt sonuç yokken aşağıdaki hesaplara girmeyelim
    return;
  }

  let recFooter = `Senaryo toplam su: ${Math.round(
    recTotals.water
  ).toLocaleString("tr-TR")} m³ | Senaryo toplam net kâr: ${Math.round(
    recTotals.profit
  ).toLocaleString("tr-TR")} TL | Su verimliliği: ${fmtEff(effRec)} TL/m³`;

  // Irrigation-method savings within the recommended plan (current->selected)
  if(isFinite(recTotals.water_saving_m3) && recTotals.water_saving_m3 > 0){
    recFooter += ` | Sulama yöntemi tasarrufu: ${Math.round(recTotals.water_saving_m3).toLocaleString("tr-TR")} m³ (${(recTotals.water_saving_pct*100).toFixed(1)}%)`;
  }

  if(recMeta && recMeta.irrigationPlan){
    recFooter += ` | Sulama planı: ${recMeta.irrigationPlan}`;
  }

  if (footerRec) footerRec.textContent = recFooter;

  // --- Açıklanabilirlik kutusu (seçili parsel) ---
  const explainBox = document.getElementById("explainBox");
  if(explainBox){
    const basin = computeBasinPlan(selectedScenario, selectedAlgo);
    const pBudget = parcelWaterBudget(p.area_da);
    const margin = pBudget - recTotals.water;
    const risk = clamp(STATE.droughtRisk ?? 0, 0, 1);
  explainBox.innerHTML = `
      <div><strong>Kısıt:</strong> Küresel su bütçesi: <strong>${Math.round(basin.budget).toLocaleString("tr-TR")} m³</strong> (seçili yıl: ${STATE.selectedWaterYear}, senaryo: ${STATE.selectedProjScenario})</div>
      <div><strong>Seçili parsel bütçesi:</strong> ~${Math.round(pBudget).toLocaleString("tr-TR")} m³ (alan payı + kuraklık riski)</div>
      <div><strong>Seçili parsel kullanımı:</strong> ${Math.round(recTotals.water).toLocaleString("tr-TR")} m³  | <strong>Durum:</strong> ${margin>=0 ? "Uygun" : "Aşım"} (${Math.round(Math.abs(margin)).toLocaleString("tr-TR")} m³)</div>
      <div><strong>Kuraklık riski (0–1):</strong> ${risk.toFixed(2)}  | <strong>Sulama randımanı varsayımı:</strong> ${Math.round((STATE.irrigEfficiency ?? 0.62)*100)}%</div>
      <div style="margin-top:6px; opacity:0.9;">Not: Aşım varsa, sistem havza genelinde en yüksek su yoğun ürünlerden daha düşük su yoğun ürünlere küçük alan kaydırmaları yaparak bütçeyi sağlamaya çalışır (greedy düzeltme; iterasyon: ${basin.iterations}).</div>
    `;
  }

  // Parsel seviyesinde (alan dağılımı / sulama planı) kullanılacak satırlar:
  // - "Mevcut desen" seçiliyken (selectedScenario='mevcut') öneri boş olabileceği için mevcut desene düş.
  // - Öneri boş dönerse yine mevcut desen.
  const rowsUsed = (String(selectedScenario).toLowerCase() === 'mevcut' || !rec || rec.length === 0) ? current : rec;

  // --- Aylık dağıtım kapasitesi (backend raporu) ---
  const deliveryBox = document.getElementById("deliveryBox");
  if(deliveryBox){
    const basin = computeBasinPlan(selectedScenario, selectedAlgo);
    const rep = basin && basin.deliveryReport;
    if(rep && Array.isArray(rep.months) && Array.isArray(rep.demand_m3) && Array.isArray(rep.cap_m3)){
      const rows = rep.months.map((m, idx)=>{
        const dem = rep.demand_m3[idx] || 0;
        const cap = rep.cap_m3[idx] || 0;
        const exc = Math.max(0, dem - cap);
        const ok = exc <= 1e-6;
        return `<tr>
          <td>${m}</td>
          <td>${Math.round(dem).toLocaleString("tr-TR")}</td>
          <td>${Math.round(cap).toLocaleString("tr-TR")}</td>
          <td>${Math.round(exc).toLocaleString("tr-TR")}</td>
          <td>${ok ? "✓" : "⚠"}</td>
        </tr>`;
      }).join("");
      const worst = rep.worst_month ? `En kritik ay: <strong>${rep.worst_month}</strong> (aşım: ${Math.round(rep.worst_exceed_m3||0).toLocaleString("tr-TR")} m³)` : "";
      deliveryBox.innerHTML = `
        <div style="margin-bottom:6px;"><strong>Durum:</strong> ${rep.feasible_monthly ? "Uygun" : "Aylık kapasite aşılıyor"} ${worst ? " | " + worst : ""}</div>
        <table class="data-table" style="margin-top:6px;">
          <thead><tr><th>Ay</th><th>Talep (m³)</th><th>Kapasite (m³)</th><th>Aşım (m³)</th><th>Durum</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
        <div class="small muted" style="margin-top:6px;">Not: Aylık talep, mümkünse FAO-56 aylık ETc tahmini (ETo×Kc - efektif yağış) ile; aksi halde toplam suyun aylık ağırlıklara göre dağıtılmasıyla hesaplanır.</div>
      `;
    }else{
      // Fallback: Kapasite bilinmiyorsa bile seçili desen için aylık talebi AKTİF hesapla.
      // 1) İklim/ET0 verisi varsa ürün bazlı (ETo×Kc) aylık brüt sulama (mm) -> m³
      // 2) Veri yoksa toplam suyu mevsim ağırlıklarıyla dağıt.

      const months = ["Oca","Şub","Mar","Nis","May","Haz","Tem","Ağu","Eyl","Eki","Kas","Ara"];
      const demandByMonth = new Array(12).fill(0);

      // Ürün bazlı aylık hesap (varsa)
      let usedEtcMonthly = false;
      for(const r of rowsUsed){
        const areaDa = safeNum(r.area);
        if(areaDa <= 0) continue;
        try{
          const calc = computeSeasonIrrigation(p, r.name);
          if(calc && Array.isArray(calc.monthly) && calc.monthly.length){
            usedEtcMonthly = true;
            for(const m of calc.monthly){
              const idx = months.indexOf(m.month);
              if(idx>=0){
                // m.gross: mm ≈ m³/da
                demandByMonth[idx] += safeNum(m.gross) * areaDa;
              }
            }
          }
        }catch(_){ /* no-op */ }
      }

      // Not: JS'de True yok; yukarıdaki satırı düzeltmek için aşağıda güvenli şekilde yeniden ayarla.
      // (Bu blok python-patch ile eklendiği için, aşağıda True -> true dönüşümü yapılacak)

      // Toplam su (m³) - tablo satırlarından
      const totalWater = rowsUsed.reduce((s,r)=>s + safeNum(r.totalWater ?? r.water_m3 ?? r.water_m3_total ?? 0), 0);

      // Eğer ürün bazlı aylık hesap üretilemediyse mevsim ağırlıklarıyla dağıt
      if(!usedEtcMonthly){
        // Niğde/İç Anadolu için basit sulama sezonu ağırlıkları (toplam=1)
        const w = [0.02,0.02,0.04,0.10,0.14,0.18,0.18,0.14,0.10,0.06,0.01,0.01];
        for(let i=0;i<12;i++) demandByMonth[i] = totalWater * w[i];
      }

      // Kapasite bilinmiyorsa: parsel su bütçesini ay bazında yaklaşık dağıt (kontrol amaçlı)
      const pBudgetM3 = parcelWaterBudget(p.area_da);
      const totalDem = demandByMonth.reduce((a,b)=>a+(+b||0),0) || 0;
      const capByMonth = demandByMonth.map((dem,i)=>{
        if(totalDem>0) return pBudgetM3 * (dem/totalDem);
        return pBudgetM3/12;
      });

      const body = months.map((m,idx)=>{
        const dem = demandByMonth[idx] || 0;
        const cap = capByMonth[idx] || 0;
        const exc = Math.max(0, dem - cap);
        const ok = exc <= 1e-6;
        return `<tr>
          <td>${m}</td>
          <td>${Math.round(dem).toLocaleString("tr-TR")}</td>
          <td>${Math.round(cap).toLocaleString("tr-TR")}</td>
          <td>${Math.round(exc).toLocaleString("tr-TR")}</td>
          <td>${ok ? '<span class="pill ok">Uygun</span>' : '<span class="pill bad">Aşım</span>'}</td>
        </tr>`;
      }).join("");

      const note = usedEtcMonthly
        ? 'Aylık talep, seçili desenin ürün takvimi (ETo×Kc) üzerinden yaklaşık hesaplandı (hızlı tahmin).'
        : 'Aylık talep, toplam suyun mevsim ağırlıklarıyla yaklaşık dağıtımıdır (iklim verisi/kc takvimi yok).';

      deliveryBox.innerHTML = `
        <div class="muted">Aylık kapasite verisi bulunamadı. Kapasite, <b>parsel su bütçesinin</b> ay bazında yaklaşık dağıtımıyla tahmin edildi (kontrol amaçlı).</div>
        <table class="data-table" style="margin-top:8px;">
          <thead><tr><th>Ay</th><th>Talep (m³)</th><th>Kapasite (m³)</th><th>Aşım (m³)</th><th>Durum</th></tr></thead>
          <tbody>${body}</tbody>
        </table>
        <div class="small muted" style="margin-top:6px;">${note}</div>
      `;
    }
  }
 
  // --- Rotasyon / 2. ürün önerisi ---
  const rotationBox = document.getElementById("rotationBox");
  if(rotationBox){
    const main = [...rowsUsed].sort((a,b)=>b.area-a.area)[0]?.name;
    const rot = makeRotationSuggestions(main);
    rotationBox.innerHTML = `<div><strong>${rot.title}:</strong></div><ul style="margin:6px 0 0 18px;">${rot.items.map(x=>`<li>${x}</li>`).join("")}</ul>`;
  }

  // --- Sulama planı (ETo×Kc) ---
  renderIrrigationPlan(p, rowsUsed);
}

// Senaryo özet metrikleri (15 parsel toplamı – hesaplanan)
function renderMetrics() {
  renderAllScenarioSummaries();
}


function totalsAllParcels(scenarioKey, algoKey){
  // IMPORTANT:
  // The "Senaryo Özeti (15 parsel toplamı)" box must compare metrics that are computed
  // with the SAME accounting model (same crop water/profit intensities and the same
  // per-parcel composition logic). Otherwise, a backend-provided baseline (often built
  // from legacy summaries) can be in different units/assumptions than the frontend
  // optimization model, which incorrectly makes "Su tasarrufu" appear as a water increase.
  //
  // Therefore we ALWAYS compute totals via computeBasinPlan() for consistency.
  // If the app is running without enough data to compute a basin plan, computeBasinPlan
  // will throw and the caller can show diagnostics.
  const basin = computeBasinPlan(scenarioKey, algoKey);
  return { ...basin.totals, budget: basin.budget, feasible: basin.feasible, iterations: basin.iterations };
}

function renderAllScenarioSummaries(){
  // 15 parsel toplamı (gerçek hesap: her parseldeki tablo toplamlarından)
  // UI seçimleri değişmiş olsa bile, yeni optimizasyon bitene kadar son geçerli sonucu göster.
  const viewCtx = (
    (!STATE.isOptimizing && canShowOptimizedForCurrentSelection())
      ? { scenario: selectedScenario, algo: selectedAlgo }
      : (lastOptimizeContext ? { scenario: lastOptimizeContext.scenario, algo: lastOptimizeContext.algo } : { scenario: selectedScenario, algo: selectedAlgo })
  );

  // --- v73: Kapsamı doğru hesapla (parsel vs havza) ---
  // Not: Kullanıcı tek parsel seçtiğinde 15 parsel toplamını göstermek, "0" ve aşırı büyük
  // değerler üreterek yanıltıyordu. Artık metrikler seçili kapsama göre hesaplanır.
  function totalsForScope(scenarioKey, algoKey){
    if(selectedParcelId === '__ALL__'){
      return totalsAllParcels(scenarioKey, algoKey);
    }
    const pid = String(selectedParcelId || '').trim();
    const p = parcelData.find(x=>String(x.id)===pid);
    if(!p){
      return { water:0, profit:0, eff:0, budget:0, feasible:true, iterations:0 };
    }
    if(String(scenarioKey).toLowerCase() === 'mevcut'){
      const cur = runOptimization(p, 'mevcut', algoKey);
      const t = cur?.totals || { water:0, profit:0 };
      return { ...t, budget: computeGlobalBudgetM3(), feasible:true, iterations:0, eff: (t.water>0 ? (t.profit/t.water) : 0) };
    }
    // Senaryo: küresel su bütçesi uygulanmış havza planından parsel payını çek
    const basin = computeBasinPlan(scenarioKey, algoKey);
    const pt = basin?.plan?.[pid]?.totals || { water:0, profit:0, area: safeNum(p.area_da,0) };
    return { ...pt, budget: basin.budget, feasible: basin.feasible, iterations: basin.iterations, eff: (pt.water>0 ? (pt.profit/pt.water) : 0) };
  }

  const base = totalsForScope('mevcut', viewCtx.algo);
  const scen = totalsForScope(viewCtx.scenario, viewCtx.algo);

  // Küresel su bütçesi rozetleri
  const globalBudgetBadge = document.getElementById("globalBudgetBadge");
  const globalBudgetStatus = document.getElementById("globalBudgetStatus");
  if(globalBudgetBadge){
    globalBudgetBadge.textContent = `Küresel su bütçesi: ${Math.round(scen.budget).toLocaleString("tr-TR")} m³`;
  }
  if(globalBudgetStatus){
    const over = scen.water - scen.budget;
    if(scen.feasible === false){
      globalBudgetStatus.textContent = `bütçe durumu: UYGUN DEĞİL (aşım: ${Math.round(Math.max(0,over)).toLocaleString("tr-TR")} m³)`;
      globalBudgetStatus.className = "badge badge-warn";
    } else if(over <= 0){
      globalBudgetStatus.textContent = `bütçe durumu: UYGUN (${Math.round(Math.abs(over)).toLocaleString("tr-TR")} m³ boş)`;
      globalBudgetStatus.className = "badge badge-ok";
    } else {
      globalBudgetStatus.textContent = `bütçe durumu: AŞIM (${Math.round(over).toLocaleString("tr-TR")} m³)`;
      globalBudgetStatus.className = "badge badge-warn";
    }
  }

  const fmt = (v) => Math.round(v).toLocaleString("tr-TR");
  const baseEff = safeNum(base.eff, (base.water>0 ? (base.profit/base.water) : 0));
  const scenEff = safeNum(scen.eff, (scen.water>0 ? (scen.profit/scen.water) : 0));
  const fmtEff = (v)=>{
    if(!isFinite(v)) return "0";
    if(v < 0) return v.toFixed(2);
    if(v < 1) return v.toFixed(3);
    return v.toFixed(1);
  };

  // Başlık: kapsamı kullanıcıya net göster
  const titleEl = document.getElementById('metricsTitle');
  if(titleEl){
    titleEl.textContent = (selectedParcelId === '__ALL__')
      ? 'Senaryo Özeti (15 parsel toplamı)'
      : `Senaryo Özeti (${selectedParcelId} parseli)`;
  }

  const mWaterCurrent = document.getElementById("mWaterCurrent");
  const mWaterScenario = document.getElementById("mWaterScenario");
  const mProfitCurrent = document.getElementById("mProfitCurrent");
  const mProfitScenario = document.getElementById("mProfitScenario");
  const mEffCurrent = document.getElementById("mEffCurrent");
  const mEffScenario = document.getElementById("mEffScenario");

  if(mWaterCurrent) mWaterCurrent.textContent = fmt(base.water);
  if(mWaterScenario) mWaterScenario.textContent = fmt(scen.water);
  if(mProfitCurrent) mProfitCurrent.textContent = fmt(base.profit);
  if(mProfitScenario) mProfitScenario.textContent = fmt(scen.profit);
  if(mEffCurrent) mEffCurrent.textContent = fmtEff(baseEff);
  if(mEffScenario) mEffScenario.textContent = fmtEff(scenEff);

  const waterDiffEl = document.getElementById("mWaterDiff");
  const profitDiffEl = document.getElementById("mProfitDiff");
  const effDiffEl = document.getElementById("mEffDiff");

  const fmtSigned = (n)=>{
    const s = (n>=0?'+':'');
    return s + Math.round(n).toLocaleString("tr-TR");
  };

  const dWater = scen.water - base.water;
  const dProfit = scen.profit - base.profit;
  const dEff = scenEff - baseEff;

  // Yüzde gösterimi sadece anlamlı olduğunda (payda > 0) kullan
  const pct = (num, den)=> (den>0 ? (num/den)*100 : NaN);
  const fmtPct = (x)=> `${x>=0?'+':''}${x.toFixed(1)} %`;

  // Hedefe göre (su tasarrufu / maks kâr) doğru yönde mi? rozetle
  const objective = String(viewCtx.scenario || '').toLowerCase();
  const waterIsGood = (objective === 'su_tasarruf') ? (dWater <= 0) : true;

  if(waterDiffEl){
    const pw = pct(dWater, base.water);
    waterDiffEl.textContent = isFinite(pw) ? fmtPct(pw) : (`Δ ${fmtSigned(dWater)} m³`);
    waterDiffEl.className = 'badge ' + (waterIsGood ? 'badge-ok' : 'badge-warn');
  }
  if(profitDiffEl){
    const pp = pct(dProfit, base.profit);
    profitDiffEl.textContent = isFinite(pp) ? fmtPct(pp) : (`Δ ${fmtSigned(dProfit)} TL`);
  }
  if(effDiffEl){
    const pe = pct(dEff, baseEff);
    effDiffEl.textContent = isFinite(pe) ? fmtPct(pe) : (`Δ ${dEff>=0?'+':''}${dEff.toFixed(1)} TL/m³`);
  }

  // Seçim değişti ama yeni sonuç alınmadıysa kullanıcıyı uyar
  if(globalBudgetStatus && STATE.selectionDirty && !STATE.isOptimizing && !canShowOptimizedForCurrentSelection()){
    globalBudgetStatus.textContent = (globalBudgetStatus.textContent || '') + ' • (Yeni seçim için optimizasyonu çalıştırın)';
  }

  // v72: Çalışma meta bilgisi + karar gerekçesi
  try{
    const metaEl = document.getElementById('runMetaBox');
    const ratEl = document.getElementById('decisionRationale');
    const key = basinCacheKey(viewCtx.scenario, viewCtx.algo);
    const cached = basinPlanCache[key] || null;
    const rp = (cached && cached.meta && (cached.meta.run_params || cached.meta.runParams)) ? (cached.meta.run_params || cached.meta.runParams) : null;
    const seed = (rp && (rp.seed !== undefined)) ? rp.seed : (cached && cached.meta ? cached.meta.seed : 42);
    const year = (cached && cached.year) ? cached.year : (STATE.selectedWaterYear || '—');
    const scope = (selectedParcelId === '__ALL__') ? 'Havza (tüm parseller)' : `Parsel ${selectedParcelId}`;
    const algoName2 = viewCtx.algo === 'ga' ? 'GA' : (viewCtx.algo === 'abc' ? 'ABC' : 'ACO');
    const scenName = (viewCtx.scenario || '').toString();

    if(metaEl){
      if(!cached){
        metaEl.style.display = 'none';
        metaEl.innerHTML = '';
      }else{
        metaEl.style.display = 'block';

        const DEFAULT_RUN_PARAMS = {
          ga:  { stop: 'İyileşme durunca', iterations: 120, generations: 120, pop: 60 },
          abc: { stop: 'İyileşme durunca', iterations: 200, colony: 40 },
          aco: { stop: 'İyileşme durunca', iterations: 200, ants: 40 }
        };

        const def = DEFAULT_RUN_PARAMS[viewCtx.algo] || DEFAULT_RUN_PARAMS.ga;
        const iterVal = (rp && (rp.iterations ?? rp.cycles ?? rp.maxIter)) ?? def.iterations;
        const genVal  = (rp && (rp.generations ?? rp.maxGen)) ?? def.generations;
        const popVal  = (rp && (rp.popSize ?? rp.population ?? rp.nPop)) ?? def.pop;
        const antsVal = (rp && (rp.ants ?? rp.antCount)) ?? def.ants;
        const colonyVal = (rp && (rp.colonySize ?? rp.beeCount ?? rp.bees)) ?? def.colony;
        const stopVal = (rp && (rp.stopEarly !== undefined ? (rp.stopEarly ? 'İyileşme durunca' : 'Sabit iterasyon') : null)) || def.stop;

        // Seed'i adil karşılaştırma rozetinde göster (kullanıcı "seed=..." bilgisini arada kaybetmesin)
        const reproducible = `Rastgelelik sabit (Seed: ${seed})`;

        const kv = [];
        kv.push({k:'Durdurma', v: stopVal});

        // Algoritma bazlı, anlamlı parametreleri göster; "—" satırı üretme
        if(viewCtx.algo === 'ga'){
          kv.push({k:'Nesil', v: genVal});
          kv.push({k:'Popülasyon', v: popVal});
          kv.push({k:'Iterasyon', v: iterVal});
        }else if(viewCtx.algo === 'abc'){
          kv.push({k:'Iterasyon', v: iterVal});
          kv.push({k:'Koloni (arı) sayısı', v: colonyVal});
        }else if(viewCtx.algo === 'aco'){
          kv.push({k:'Iterasyon', v: iterVal});
          kv.push({k:'Karınca sayısı', v: antsVal});
        }else{
          kv.push({k:'Iterasyon', v: iterVal});
        }

        metaEl.innerHTML = `
          <div class="runmeta-title">Koşullar (Adil Karşılaştırma)</div>
          <div class="runmeta-tags">
            <span class="runmeta-tag"><span class="runmeta-ic">📍</span><b>${scope}</b></span>
            <span class="runmeta-tag"><span class="runmeta-ic">🤖</span><b>${algoName2}</b></span>
            <span class="runmeta-tag"><span class="runmeta-ic">💧</span><b>Su tasarrufu</b></span>
            <span class="runmeta-tag"><span class="runmeta-ic">📅</span><b>${year}</b></span>
            <span class="runmeta-tag"><span class="runmeta-ic">⚖️</span><b>${reproducible}</b></span>
          </div>

          <details class="runmeta-details">
            <summary>Optimizasyon parametreleri</summary>
            <div class="runmeta-kv">
              ${kv.map(x=>`<div><span class="k">${escapeHtml(String(x.k))}</span><span class="v">${escapeHtml(String(x.v))}</span></div>`).join('')}
            </div>
            <div class="small muted" style="margin-top:8px;">Not: Seed, rastgele başlangıcı sabitleyerek aynı koşullarda aynı sonuçların üretilebilmesini sağlar.</div>
          </details>
        `;
      }
    }

    if(ratEl){
      ratEl.style.display = cached ? 'block' : 'none';
      if(!cached){ ratEl.innerHTML = ''; }
      const betterWater = dWater <= 0;
      const betterProfit = dProfit >= 0;
      const title = 'Karar Gerekçesi (Mevcut desen ile kıyas)';
      const msg = (
        (betterWater && betterProfit)
          ? 'Önerilen desen <b>daha az su</b> ile <b>daha yüksek kâr</b> üretiyor.'
          : (betterWater && !betterProfit)
            ? 'Önerilen desen <b>su tasarrufu</b> sağlıyor. Kâr düşebilir; ancak hedef, kârın <b>pozitif</b> kalması ve çiftçinin gelirinin tamamen kaybolmamasıdır.'
            : (!betterWater && betterProfit)
              ? 'Kâr artıyor; fakat su kullanımı da artıyor. <b>Bu proje hedefi su tasarrufu olduğu için</b> bu tür çözümler önerilmez.'
              : 'Hem su hem kâr tarafında olumsuzluk var; bu durumda senaryo/parametreler gözden geçirilmeli.'
      );
      // v73: Aynı sayfada zaten sayısal KPI kartları var. Burada tekrar etmek yerine
      // sadece "neden" kısmını kısa ve anlaşılır şekilde söylüyoruz.
      ratEl.innerHTML = `
        <div class="rationale-title">${title}</div>
        <div class="rationale-text">${msg}</div>
        <div class="small muted" style="margin-top:6px;">Not: Sayısal farklar yukarıdaki kartlarda gösterilir.</div>
      `;
    }
  }catch(_e){ /* noop */ }

  // Bar chart güncelle
  // ÖNEMLİ: Grafikler, üstteki metrik kartlarıyla AYNI kapsamı (seçili parsel veya havza)
  // ve AYNI birimleri (m³ / TL) kullanmalı. Aksi hâlde kullanıcıya tutarsız görünür.
  const scenKey = (viewCtx.scenario || 'su_tasarruf').toString();
  const scenLabel = (k=>{
    const s = (k||'').toString();
    if(s === 'mevcut') return 'Mevcut';
    if(s === 'su_tasarruf') return 'Su tasarrufu';
    if(s === 'maks_kar') return 'Maks. kâr';
    return 'Seçili senaryo';
  })(scenKey);

  if(waterChart){
    const w0 = totalsForScope('mevcut', viewCtx.algo).water;
    const w1 = totalsForScope(scenKey, viewCtx.algo).water;
    waterChart.data.labels = ["Mevcut", scenLabel];
    waterChart.data.datasets[0].data = [w0, w1];
    waterChart.update();
  }
  if(profitChart){
    // Negatif net kârı da gösterebilmek için kırpma YOK.
    const p0 = totalsForScope('mevcut', viewCtx.algo).profit;
    const p1 = totalsForScope(scenKey, viewCtx.algo).profit;
    profitChart.data.labels = ["Mevcut", scenLabel];
    profitChart.data.datasets[0].data = [p0, p1];
    profitChart.update();
  }
}

// --- Compat shim: some code paths call refreshGlobalSummary()
function refreshGlobalSummary() {
  try {
    renderAllScenarioSummaries();
  } catch (e) {
    console.warn('refreshGlobalSummary failed', e);
  }
}




async function refreshTimeSeriesFromBackend(){
  try{
    const sel = (parcelData||[]).map(p=>p.id).join(",");
    const r = await fetch('/api/timeseries?selected='+encodeURIComponent(sel));
    const j = await r.json();
    if(!j || !j.series) return;
    STATE.backendSeries = j.series;
    // If there is a chart dedicated to basin budget / time series, update storageHistoryChart as proxy
    // storageHistoryChart uses historical reservoir storage; keep existing. This helper ensures the "one blank line" issue for scenario chart is avoided by backfilling.
    backfillProjectionSeries();
  }catch(e){ console.warn(e); }
}


function normalizeScenarioKey(v){
  const raw = String(v ?? "").trim().toLowerCase();
  if(!raw) return "";
  // Turkish-specific normalization
  const trMap = { "ı":"i", "ğ":"g", "ü":"u", "ş":"s", "ö":"o", "ç":"c" };
  const norm = raw.replace(/[ığüşöç]/g, ch=>trMap[ch]||ch)
                  .replace(/\s+/g," ")
                  .replace(/[-\s]+/g,"_");
  // Map common labels to canonical keys used in charts
  if(norm.includes("mevcut")) return "mevcut";
  if(norm.includes("iyi") && norm.includes("adapt")) return "iyi_adaptasyon";
  if(norm.includes("kotu") && norm.includes("kurak")) return "kotu_kuraklik";
  return norm;
}

function backfillProjectionSeries(){
  // Ensure STATE.projSeries has all scenarios; if missing, derive from 'mevcut' curve
  const base = (STATE.projSeries||[]).filter(x=>x.senaryo==='mevcut');
  if(!base.length) return;
  const have = new Set((STATE.projSeries||[]).map(x=>x.senaryo));
  const mk = (name, mul)=> base.map(x=>({yil:x.yil, senaryo:name, doluluk: clamp((x.doluluk||0)*mul,0,100)}));
  let out = STATE.projSeries||[];
  if(!have.has('iyi_adaptasyon')) out = out.concat(mk('iyi_adaptasyon', 1.08));
  if(!have.has('kotu_kuraklik')) out = out.concat(mk('kotu_kuraklik', 0.85));
  STATE.projSeries = out;
  // If scenario chart exists, refresh its datasets
  if(storageScenarioChart){
    const scenYears = Array.from({ length: 26 }, (_, i) => 2025 + i);
    const seriesFor = (sen)=>{
    if(fallbackProj && fallbackProj[sen]) return fallbackProj[sen];
    return scenYears.map(y=>{
      const r = (STATE.projSeries||[]).find(x=>x.yil===y && x.senaryo===sen);
      return r ? r.doluluk : null;
    });
  };
    storageScenarioChart.data.labels = scenYears;
    storageScenarioChart.data.datasets[0].data = seriesFor('mevcut');
    storageScenarioChart.data.datasets[1].data = seriesFor('iyi_adaptasyon');
    storageScenarioChart.data.datasets[2].data = seriesFor('kotu_kuraklik');
    storageScenarioChart.update();
  }
}

// Chart.js grafikleri
let waterChart, profitChart; // areaChart removed (replaced by product cards)
let districtAreaChart, districtIrrigChart, provinceShareChart;
let storageHistoryChart, storageScenarioChart;
let benchmarkProfitChart, benchmarkWaterChart, benchmarkEffChart;

function initCharts() {
  const waterCtx = document.getElementById("waterChart").getContext("2d");
  const profitCtx = document.getElementById("profitChart").getContext("2d");

  waterChart = new Chart(waterCtx, {
    type: "bar",
    data: {
      labels: ["Mevcut", "Seçili senaryo"],
      datasets: [
        {
          label: "Su kullanımı (m³)",
          data: [0, 0],
        },
      ],
    },
    options: chartBarOptions("m³"),
  });

  profitChart = new Chart(profitCtx, {
    type: "bar",
    data: {
      labels: ["Mevcut", "Seçili senaryo"],
      datasets: [
        {
          label: "Net kâr (TL)",
          data: [0, 0],
        },
      ],
    },
    options: chartBarOptions("TL"),
  });

  // areaChart removed (donut yerine ürün kartları)

  // İlçe / il demo grafikleri
  const dAreaCtx = document.getElementById("districtAreaChart").getContext("2d");
  const dIrrigCtx = document.getElementById("districtIrrigChart").getContext("2d");
  const provCtx = document.getElementById("provinceShareChart").getContext("2d");

  districtAreaChart = new Chart(dAreaCtx, {
    type: "bar",
    data: {
      labels: ["Merkez", "Altunhisar", "Bor", "Çamardı", "Çiftlik", "Ulukışla"],
      datasets: [
        { label: "Tarla", data: [42, 18, 35, 12, 15, 20] },
        { label: "Sebze", data: [8, 2, 5, 1, 3, 4] },
        { label: "Meyve", data: [12, 4, 10, 6, 5, 7] },
      ],
    },
    options: chartBarOptions("Bin da"),
  });

  districtIrrigChart = new Chart(dIrrigCtx, {
    type: "bar",
    data: {
      labels: ["Merkez", "Altunhisar", "Bor", "Çamardı", "Çiftlik", "Ulukışla"],
      datasets: [
        { label: "Sulanan", data: [65, 55, 60, 45, 50, 52] },
        { label: "Nadas / sulanmayan", data: [35, 45, 40, 55, 50, 48] },
      ],
    },
    options: chartBarOptions("%"),
  });

  provinceShareChart = new Chart(provCtx, {
    type: "doughnut",
    data: {
      labels: ["Tarla", "Sebze", "Meyve"],
      datasets: [
        {
          data: [68, 9, 23],
          backgroundColor: ["#4dabf7", "#69db7c", "#ffa94d"],
        },
      ],
    },
    options: {
      plugins: {
        legend: {
          position: "bottom",
          labels: { boxWidth: 10, font: { size: 11 } },
        },
      },
      cutout: "55%",
    },
  });

  // Su bütçesi grafikleri
  const histCtx = document.getElementById("storageHistoryChart").getContext("2d");
  const scenCtx = document.getElementById("storageScenarioChart").getContext("2d");

  // 2000–2025: veri paketinden (clean CSV)
  const histYears = (STATE.barajSeries||[]).map(r=>r.yil);
  const histSeries = (STATE.barajSeries||[]).map(r=>r.doluluk);
  // New (optional): average & minimum fullness (%) from updated table
  const histAvg = (STATE.barajSeries||[]).map(r=>isFinite(+r.ortalama_pct) ? +r.ortalama_pct : null);
  const histMin = (STATE.barajSeries||[]).map(r=>isFinite(+r.min_pct) ? +r.min_pct : null);
  const hasAvg = histAvg.some(v=>v!==null);
  const hasMin = histMin.some(v=>v!==null);


  // --- Görsel vurgu: kritik eşik çizgileri ve min/max etiketleri (Chart.js plugin) ---
  const thresholdLinesPlugin = {
    id: "thresholdLinesPlugin",
    afterDraw(chart, args, pluginOptions){
      const opts = pluginOptions || {};
      const ys = Array.isArray(opts.levels) ? opts.levels : [10, 20];
      const yScale = chart.scales.y;
      const xScale = chart.scales.x;
      if(!yScale || !xScale) return;
      const ctx = chart.ctx;
      ctx.save();
      ctx.setLineDash([6, 4]);
      ctx.lineWidth = 1;
      ctx.globalAlpha = 0.6;
      for(const v of ys){
        if(!isFinite(v)) continue;
        const y = yScale.getPixelForValue(v);
        ctx.beginPath();
        ctx.moveTo(xScale.left, y);
        ctx.lineTo(xScale.right, y);
        ctx.stroke();
        // label
        ctx.setLineDash([]);
        ctx.globalAlpha = 0.75;
        ctx.font = "12px system-ui, -apple-system, Segoe UI, Roboto, Arial";
        ctx.fillText(`%${v} eşik`, xScale.left + 6, y - 4);
        ctx.setLineDash([6, 4]);
        ctx.globalAlpha = 0.6;
      }
      ctx.restore();
    }
  };

  const extremaLabelsPlugin = {
    id: "extremaLabelsPlugin",
    afterDatasetsDraw(chart, args, pluginOptions){
      const opts = pluginOptions || {};
      const only = Array.isArray(opts.onlyLabels) ? opts.onlyLabels : ["Yıl içi minimum doluluk (%)", "Yıllık ortalama doluluk (%)"];
      const ctx = chart.ctx;
      ctx.save();
      ctx.font = "12px system-ui, -apple-system, Segoe UI, Roboto, Arial";
      ctx.globalAlpha = 0.9;

      chart.data.datasets.forEach((ds, dsIndex)=>{
        if(!ds || !only.includes(ds.label)) return;
        const meta = chart.getDatasetMeta(dsIndex);
        if(!meta || meta.hidden) return;
        const data = (ds.data||[]).map(v => (isFinite(v) ? +v : null));
        const points = meta.data || [];
        if(!data.length || !points.length) return;

        let minVal=Infinity, maxVal=-Infinity, minI=-1, maxI=-1;
        for(let i=0;i<data.length;i++){
          const v=data[i];
          if(v===null) continue;
          if(v<minVal){ minVal=v; minI=i; }
          if(v>maxVal){ maxVal=v; maxI=i; }
        }
        const drawLabel=(i,val,tag)=>{
          if(i<0 || !points[i]) return;
          const pt=points[i];
          const x=pt.x, y=pt.y;
          const text=`${tag}: ${val.toFixed(1)}%`;
          // background pill
          const padX=6, padY=4;
          const w=ctx.measureText(text).width + padX*2;
          const h=18;
          const bx=x - w/2;
          const by=y - h - 8;
          ctx.globalAlpha = 0.85;
          ctx.fillRect(bx, by, w, h);
          ctx.globalAlpha = 0.95;
          ctx.fillStyle = "#fff";
          ctx.fillText(text, bx+padX, by+13);
          ctx.fillStyle = "#000";
        };
        // Use dark overlay background for visibility
        ctx.fillStyle = "rgba(0,0,0,0.55)";
        drawLabel(minI, minVal, "Min");
        drawLabel(maxI, maxVal, "Maks");
      });
      ctx.restore();
    }
  };

  // Not: Bu grafikte değerler hover/tooltip ile zaten görülebildiği için
  // okunurluğu bozabilecek kalıcı yazı/etiket eklentilerini KAPATIYORUZ.
  storageHistoryChart = new Chart(histCtx, {
    type: "line",
    data: {
      labels: histYears.length ? histYears : Array.from({length:25},(_,i)=>2000+i),
      datasets: [
        {
          label: "Tarımsal stres endeksi (0–100)",
          data: histYears.length ? histSeries : Array.from({length:25},(_,i)=>75-i*0.3),
          tension: 0.2,
        },
        ...(hasAvg ? [{
          label: "Yıllık ortalama doluluk (%)",
          data: histYears.length ? histAvg : Array.from({length:25},(_,i)=>60-i*0.2),
          tension: 0.2,
        }] : []),
        ...(hasMin ? [{
          label: "Yıl içi minimum doluluk (%)",
          data: histYears.length ? histMin : Array.from({length:25},(_,i)=>20-i*0.1),
          tension: 0.2,
        }] : []),
      ],
    },
    // Kalıcı yazı/etiket çizimleri kaldırıldı.
    plugins: [],
    options: (() => {
      const o = chartLineOptions("Göstergeler (endeks / %)");
      // Eğer eski ayarlardan plugin opsiyonları kaldıysa temizle
      if(o.plugins){
        delete o.plugins.thresholdLinesPlugin;
        delete o.plugins.extremaLabelsPlugin;
      }
      return o;
    })(),
  });

  // 2025–2050: projeksiyon (3 senaryo)
  const scenYears = Array.from({ length: 26 }, (_, i) => 2025 + i);

  function buildFallbackProjection(){
    const hs = (STATE.barajSeries||[]).map(r=>+r.doluluk).filter(x=>isFinite(x));
    if(!hs.length) return null;
    const last = hs[hs.length-1];
    const back = hs.length>11 ? hs[hs.length-11] : hs[0];
    const slope = (last - back) / (hs.length>11 ? 10 : Math.max(1, hs.length-1));
    const clamp = (v)=>Math.max(0, Math.min(100, v));
    const years = scenYears;
    const make = (mult, uplift)=>years.map((y,i)=>{
      const v = last + slope*mult*(i+1) + uplift;
      return +clamp(v).toFixed(1);
    });
    return {
      mevcut: make(1.0, 0),
      iyi_adaptasyon: make(0.6, 3),
      kotu_kuraklik: make(1.4, -3),
    };
  }

  const fallbackProj = (!STATE.projSeries || !STATE.projSeries.length) ? buildFallbackProjection() : null;

  const seriesFor = (sen)=>{
    if(fallbackProj && fallbackProj[sen]) return fallbackProj[sen];
    return scenYears.map(y=>{
      const r = (STATE.projSeries||[]).find(x=>x.yil===y && x.senaryo===sen);
      return r ? r.doluluk : null;
    });
  };

  storageScenarioChart = new Chart(scenCtx, {
    type: "line",
    data: {
      labels: scenYears,
      datasets: [
        { label: "Mevcut gidişat", data: seriesFor("mevcut"), tension: 0.2 },
        { label: "İyi adaptasyon", data: seriesFor("iyi_adaptasyon"), tension: 0.2 },
        { label: "Kötü kuraklık", data: seriesFor("kotu_kuraklik"), tension: 0.2 },
      ],
    },
    options: chartLineOptions("Göstergeler (endeks / %)"),
  });
}

function initBenchmarkCharts() {
  const pEl = document.getElementById("benchmarkProfitChart");
  const wEl = document.getElementById("benchmarkWaterChart");
  const eEl = document.getElementById("benchmarkEffChart");
  if (!pEl || !wEl || !eEl) return;

  const pCtx = pEl.getContext("2d");
  const wCtx = wEl.getContext("2d");
  const eCtx = eEl.getContext("2d");

  const empty = { labels: [], datasets: [{ label: "", data: [] }] };

  benchmarkProfitChart = new Chart(pCtx, { type: "bar", data: structuredClone(empty), options: chartBarOptions("TL") });
  benchmarkWaterChart = new Chart(wCtx, { type: "bar", data: structuredClone(empty), options: chartBarOptions("m³") });
  benchmarkEffChart = new Chart(eCtx, { type: "bar", data: structuredClone(empty), options: chartBarOptions("TL/m³") });
}

function chartBarOptions(yLabel) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        enabled: true,
        callbacks: {
          label: (ctx) => {
            const v = (ctx && ctx.parsed && typeof ctx.parsed.y !== 'undefined') ? ctx.parsed.y : (ctx.raw||0);
            const name = (ctx.dataset && ctx.dataset.label) ? ctx.dataset.label : '';
            return (name ? (name+': ') : '') + fmtNum(v, 2);
          }
        }
      },
    },
    scales: {
      x: {
        ticks: { font: { size: 11 } },
        grid: { display: false },
      },
      y: {
        ticks: { font: { size: 10 } },
        grid: { color: "#edf2ff" },
        title: { display: !!yLabel, text: yLabel, font: { size: 10 } },
      },
    },
  };
}

function chartLineOptions(yLabel) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { position: "bottom", labels: { font: { size: 11 } } },
      tooltip: {
        enabled: true,
        callbacks: {
          label: (ctx) => {
            const v = (ctx && ctx.parsed && typeof ctx.parsed.y !== 'undefined') ? ctx.parsed.y : (ctx.raw||0);
            const ds = ctx.dataset ? (ctx.dataset.label||'') : '';
            return (ds ? (ds+': ') : '') + fmtNum(v, 2);
          }
        }
      }
    },
    scales: {
      x: { ticks: { font: { size: 9 }, maxRotation: 60, minRotation: 0, autoSkip: true }, grid: { display: false } },
      y: {
        ticks: { font: { size: 9 } },
        grid: { color: "#edf2ff" },
        title: { display: !!yLabel, text: yLabel, font: { size: 10 } },
      },
    },
  };
}

// Seçili parsel için "önerilen ürün" şeridini güncelle (grafik yerine)
function updateProductCards(){
  const box = document.getElementById('productCards');
  if(!box) return;

  const p = parcelData.find((x) => x.id === selectedParcelId);
  const { current, rec } = computeCropData(p, selectedScenario, selectedAlgo);

  // "Mevcut" seçiliyse -> mevcut; diğerlerinde optimizasyon çalışmadıysa -> mevcut
  const canShowOpt = (selectedScenario === 'mevcut') || canShowOptimizedForCurrentSelection();
  let rows = (selectedScenario === 'mevcut') ? current : (canShowOpt ? rec : current);
  if(!Array.isArray(rows) || rows.length === 0) rows = current;

  const topRows = [...rows]
    .filter(r => safeNum(r.area,0) > 0)
    .sort((a,b)=> safeNum(b.area,0) - safeNum(a.area,0))
    .slice(0, 6);

  if(!topRows.length){
    box.innerHTML = `<div class="product-empty">Ürün önerisi henüz oluşmadı. Optimizasyonu çalıştırın.</div>`;
    return;
  }

  const emojiFor = (name)=>{
    const n = String(name||'').toLowerCase();
    if(n.includes('bugday') || n.includes('arpa') || n.includes('cavdar')) return '🌾';
    if(n.includes('misir')) return '🌽';
    if(n.includes('patates')) return '🥔';
    if(n.includes('sogan')) return '🧅';
    if(n.includes('nohut') || n.includes('mercimek') || n.includes('fasulye') || n.includes('fiy')) return '🫘';
    if(n.includes('aycicegi')) return '🌻';
    if(n.includes('kabak')) return '🎃';
    if(n.includes('pancar')) return '🍠';
    if(n.includes('marul') || n.includes('ispanak') || n.includes('lahana')) return '🥬';
    if(n.includes('biber')) return '🌶️';
    if(n.includes('turp')) return '🥕';
    if(n.includes('bag') || n.includes('uzum')) return '🍇';
    if(n.includes('yonca') || n.includes('fig')) return '🌿';
    if(n.includes('nadas')) return '🟫';
    return '🌱';
  };

  const pills = topRows.map((r, idx)=>{
    const name = escapeHtml(r.name);
    const season = escapeHtml(r.season || '');
    const label = season && season !== '—' ? `${name} <span class="pill-season">${season}</span>` : name;
    const sep = (idx < topRows.length-1) ? `<span class="crop-sep">/</span>` : '';
    return `<span class="crop-pill"><span class="crop-emoji">${emojiFor(r.name)}</span><span class="pill-name">${label}</span></span>${sep}`;
  }).join('');

  box.innerHTML = `
    <div class="crop-strip">${pills}</div>
    <div class="crop-note">Aynı parsel alanı yıl içinde farklı ekim dönemlerinde (rotasyon/2. ürün) ardışık kullanılır.</div>
  `;
}

// Leaflet haritası
let map;
let parcelLayer;

// Harita başlatma (GeoJSON yüklemek için async)
async function initMap() {
  map = L.map("map", {
    zoomControl: true,
  }).setView([37.957776, 34.353984], 15); // Niğde civarı

  // Baz harita katmanı:
  // - Eğer Esri Leaflet eklentisi yüklüyse uydu katmanı
  // - Değilse (CDN engeli/offline) OSM fallback
  try{
    if(window.L && L.esri && typeof L.esri.basemapLayer === 'function'){
      L.esri.basemapLayer("Imagery").addTo(map);
    }else{
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 20,
        attribution: '&copy; OpenStreetMap'
      }).addTo(map);
    }
  }catch(_e){
    // If even the fallback fails, keep going; we will still draw parcel polygons.
  }

// ✅ GeoJSON'lar artık gömülü değil; data/geojson_yeni_klasor4 içinden yüklenir.
  // Bu sayede: (1) zip ile gelen yeni parsel poligonları otomatik kullanılır, (2) kod boyutu düşer.
  const GEOJSON_FOLDER = 'data/geojson_yeni_klasor4';
  const GEOJSON_FILES = [
    'explorer-aoi (13).geojson',
    'explorer-aoi (14).geojson',
    'explorer-aoi (15).geojson',
    'explorer-aoi (16).geojson',
    'explorer-aoi (17).geojson',
    'explorer-aoi (18).geojson',
    'explorer-aoi (19).geojson',
    'explorer-aoi (20).geojson',
    'explorer-aoi (21).geojson',
    'explorer-aoi (22).geojson',
    'explorer-aoi (23).geojson',
    'explorer-aoi (24).geojson',
    'explorer-aoi (25).geojson',
    'explorer-aoi (26).geojson',
    'explorer-aoi (27).geojson'
  ];

  // Parsel çizim stili ve tıklama davranışı
  const style = (feature) => {
    const fid = feature?.properties?.id || feature?.properties?.name;
    const isSel = (fid && String(fid) === String(selectedParcelId));
    return {
      color: isSel ? '#0b74c4' : '#2b2b2b',
      weight: isSel ? 3 : 2,
      opacity: 0.9,
      fillColor: isSel ? '#3aa0ff' : '#9bb7d1',
      fillOpacity: isSel ? 0.35 : 0.18
    };
  };

  // Parcel area lookup (da). Used for hover popups.
  const parcelAreaDaById = (()=>{
    const m = {};
    (parcelData||[]).forEach(p=>{
      const id = (p?.id ?? '').toString();
      if(!id) return;
      // Common schema: area_da; fallback to area_ha*10.
      let a = Number(p.area_da);
      if(!Number.isFinite(a)) a = Number(p.area);
      if(!Number.isFinite(a)){
        const ha = Number(p.area_ha);
        if(Number.isFinite(ha)) a = ha * 10;
      }
      if(Number.isFinite(a)) m[id] = a;
    });
    return m;
  })();

  const fmtDa = (x)=>{
    const v = Number(x);
    if(!Number.isFinite(v)) return '—';
    return (Math.round(v*10)/10).toFixed(1);
  };

  const onEachFeature = (feature, layer) => {
    const fid = feature?.properties?.id || feature?.properties?.name;
    if(fid){
      // Parsel etiketlerini sabit göster (hover beklemesin)
      layer.bindTooltip(String(fid), {
        permanent: true,
        direction: 'center',
        className: 'parcel-label',
        opacity: 0.95,
        sticky: false
      });
      layer.on('click', () => {
        // dropdown + global seçim güncelle
        selectedParcelId = String(fid);
        const sel = document.getElementById('parcelSelect');
        if(sel) sel.value = String(fid);
        if(window._updateParcelStyles) window._updateParcelStyles();
        refreshUI();
      });

      // Hover popup: show parcel id + area (da)
      const areaDa = parcelAreaDaById[String(fid)];
      const popHtml = `<div class="parcel-pop"><div class="t">${escapeHtml(String(fid))}</div><div class="s">Alan: <b>${escapeHtml(fmtDa(areaDa))}</b> da</div></div>`;
      layer.bindPopup(popHtml, {closeButton:false, autoClose:false, closeOnClick:false, autoPan:false, className:'parcel-popup'});
      layer.on('mouseover', (e)=>{
        try{ layer.openPopup(e?.latlng); }catch(_e){ try{ layer.openPopup(); }catch(__){} }
      });
      layer.on('mouseout', ()=>{
        try{ layer.closePopup(); }catch(_e){}
      });
    }
  };

  async function loadParcelsGeojson(){
    const parcelIds = (Array.isArray(parcelData) && parcelData.length)
      ? parcelData.slice(0, 15).map(p => p.id)
      : Array.from({length: 15}, (_,i)=>`P${i+1}`);

    const out = { type:'FeatureCollection', features: [] };

    for(let i=0;i<Math.min(parcelIds.length, GEOJSON_FILES.length);i++){
      const pid = parcelIds[i];
      const fn = GEOJSON_FILES[i];
      const url = `${GEOJSON_FOLDER}/${encodeURIComponent(fn)}`;
      try{
        const gj = await (await fetch(url)).json();
        const feat = (gj && gj.features && gj.features[0]) ? gj.features[0] : null;
        if(!feat) continue;
        feat.properties = feat.properties || {};
        feat.properties.id = pid;
        feat.properties.name = pid;
        out.features.push(feat);
      }catch(e){
        console.warn('GeoJSON yüklenemedi:', url, e);
      }
    }
    return out;
  }

  const geojson = await loadParcelsGeojson();
  parcelLayer = L.geoJSON(geojson, {
    style,
    onEachFeature,
  }).addTo(map);

  map.fitBounds(parcelLayer.getBounds().pad(0.3));

  // Seçim değiştiğinde stilleri güncelle
  function updateStyles() {
    parcelLayer.setStyle(style);
  }

  // Parsel seçilince haritada odaklan + alan bilgisini göster
  function focusParcel(pid){
    try{
      if(!map || !parcelLayer) return;
      let targetLayer = null;
      parcelLayer.eachLayer((ly)=>{
        const fid = ly?.feature?.properties?.id || ly?.feature?.properties?.name;
        if(String(fid) === String(pid)) targetLayer = ly;
      });
      if(targetLayer){
        const b = targetLayer.getBounds();
        if(b && b.isValid()) map.fitBounds(b.pad(0.35), { animate:true });
        // show popup with area
        try{ targetLayer.openPopup(); }catch(_){ }
      }
    }catch(_){ }
  }

  // Küçük bir hack: global erişim
  window._updateParcelStyles = updateStyles;
  window._focusParcel = focusParcel;
}

// Sekmeler
function initTabs() {
  const tabButtons = document.querySelectorAll(".tab");
  const panels = {
    parcel: document.getElementById("tab-parcel"),
    district: document.getElementById("tab-district"),
    official: document.getElementById("tab-official"),
    water: document.getElementById("tab-water"),
    drought: document.getElementById("tab-drought"),
    benchmark: document.getElementById("tab-benchmark"),
    impact: document.getElementById("tab-impact"),
    plan5: document.getElementById("tab-plan5"),
  };

  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      Object.values(panels).forEach((p) => { if(p) p.classList.remove("active"); });
      const key = btn.dataset.tab;
      // Bazı sekmeler DOM'da bulunmazsa (geliştirme sırasında) uygulama çökmesin.
      if (panels[key]) {
        panels[key].classList.add("active");
      }

      // Hidden tab canvases may render with zero size. Force a resize after activation.
      if(key === 'official'){
        setTimeout(()=>{
          try{ renderOfficialTables(); }catch(_e){}
          try{ renderOfficialSummary(); }catch(_e){}
        }, 30);
      }
      if(key === 'water'){
        setTimeout(()=>{
          try{ renderWaterBudgetCharts(); }catch(_e){}
          try{ storageHistoryChart?.resize(); }catch(_e){}
          try{ storageScenarioChart?.resize(); }catch(_e){}
        }, 50);
      }



      if(key === 'drought'){
        setTimeout(()=>{
          try{ ensureDroughtSeriesChart(); }catch(_e){}
          try{ droughtSeriesChart?.resize(); }catch(_e){}
        }, 60);
      }
      if(key === 'benchmark'){
        setTimeout(()=>{
          try{ benchmarkProfitChart?.resize(); }catch(_e){}
          try{ benchmarkWaterChart?.resize(); }catch(_e){}
          try{ benchmarkEffChart?.resize(); }catch(_e){}
          // boş görünüyorsa kullanıcıya ipucu ver
          const box = document.getElementById('benchmarkResults');
          if(box && !box.innerHTML.trim()){
            box.innerHTML = '<div class="badge badge-info">Karşılaştırmayı başlatmak için <b>Karşılaştırmayı Çalıştır</b> butonuna basın.</div>';
          }
        }, 60);
      }

      if(key === 'impact'){
        // Sekme ilk kez açıldığında boş görünmesin
        setTimeout(()=>{
          const box = document.getElementById('impact15ySummary');
          const box2 = document.getElementById('profit15ySummary');
          if(box && !box.innerHTML.trim()){
            box.innerHTML = '<div class="badge badge-info">15 yıllık etkiyi görmek için <b>15Y Su Tasarrufu</b> veya <b>15Y Ortalama Kâr</b> butonuna basın.</div>';
          }
          if(box2 && !box2.innerHTML.trim()){
            box2.innerHTML = '<div class="badge badge-info">Kâr projeksiyonu için üstteki butonu kullanın.</div>';
          }
        }, 60);
      }
    });
  });
}

function renderPlan5(){
  const panel = document.getElementById("tab-plan5");
  if(!panel) return;

  const tbl = document.getElementById("plan5Table");
  const tbody = tbl ? tbl.querySelector("tbody") : null;
  if(!tbody) return;

  // Dropdown (Parsel/Tümü)
  const sel = document.getElementById("plan5ParcelSelect");
  if(sel && sel.options.length===0){
    const optAll = document.createElement("option");
    optAll.value = "__ALL__";
    optAll.textContent = "Tümü (Genel Özet)";
    sel.appendChild(optAll);
    for(const p of parcelData){
      const o = document.createElement("option");
      o.value = p.id;
      o.textContent = `${p.id}`;
      sel.appendChild(o);
    }
    sel.value = "__ALL__";
    sel.addEventListener("change", ()=>renderPlan5());
  }

  const selectedParcelId = (sel && sel.value) ? sel.value : "__ALL__";

  // Seçili senaryo & algoritmanın havza planı (Yıl-1 için kaynak)
  const basin = computeBasinPlan(selectedScenario, selectedAlgo);

  // Baseline (mevcut) – 5 yıl aynı kalsaydı (yaklaşık)
  const baseWaterAll5 = parcelData.reduce((a,p)=> a + (+p.water_m3||0)*5, 0);
  const baseProfitAll5 = parcelData.reduce((a,p)=> a + (+p.profit_tl||0)*5, 0);

  // Crop katalogundan su/kâr (TL/da) çek
  // Not: urun_parametreleri_demo.csv 'urun_adi, su_tuketimi_m3_da, beklenen_verim_kg_da, fiyat_tl_kg, maliyet_tl_da' içerir.
  const cropRows = ((window.__CROPS_ROWS__ && window.__CROPS_ROWS__.length) ? window.__CROPS_ROWS__ : ((STATE && STATE.cropCatalog) ? Object.values(STATE.cropCatalog).map(v=>({urun_adi:v.name, su_tuketimi_m3_da:v.waterPerDa, profitPerDa:v.profitPerDa})) : []));
  const keyOf = (s)=>{
    return (s||"").toString().trim()
      .toUpperCase()
      .replaceAll("İ","I").replaceAll("İ","I")
      .replaceAll("Ş","S").replaceAll("Ğ","G").replaceAll("Ü","U").replaceAll("Ö","O").replaceAll("Ç","C")
      .replaceAll("("," ").replaceAll(")"," ").replaceAll("/"," ").replaceAll("-"," ")
      .replace(/\s+/g,"_")
      .replace(/__+/g,"_")
      .replace(/^_+|_+$/g,"");
  };

  // Katalog map
  const cropMap = new Map();
  for(const r of cropRows){
    const name = r.urun_adi || r.name || r.crop || r.urun || "";
    if(!name) continue;
    const k = keyOf(name);
    const water = +r.su_tuketimi_m3_da || +r.waterPerDa || +r.su || 0;
    const yieldKg = +r.beklenen_verim_kg_da || +r.yieldKgDa || +r.verim || 0;
    const price = +r.fiyat_tl_kg || +r.price || 0;
    const cost = +r.maliyet_tl_da || +r.cost || 0;
    // Bazı kod yollarında (STATE.cropCatalog) direkt profitPerDa taşınır.
    // Bu durumda beklenen_verim/fiyat/maliyet alanları gelmeyebilir; 0'a düşmemesi için önce profitPerDa'yı kullan.
    const directProfit = (r.profitPerDa!==undefined && r.profitPerDa!==null) ? +r.profitPerDa : NaN;
    const profit = isFinite(directProfit) ? directProfit : ((yieldKg*price) - cost);
    cropMap.set(k, {displayName:name, waterPerDa:water, profitPerDa:profit});
  }

  const isFallow = (n)=> keyOf(n) === "NADAS";

  const familyOf = (n)=>{
    const k = keyOf(n);
    if(k==="NADAS") return "FALLOW";
    if(k.includes("NOHUT") || k.includes("MERCIMEK") || k.includes("FASULYE") || k.includes("BEZELYE") ) return "LEGUME";
    if(k.includes("FIG") || k.includes("KORUNGA") || k.includes("YONCA") || k.includes("VETCH") ) return "COVER";
    if(k.includes("BUGDAY") || k.includes("ARPA") || k.includes("TRITIKALE") || k.includes("MISIR") || k.includes("YULAF") ) return "CEREAL";
    if(k.includes("ASPIR") || k.includes("KANOLA") || k.includes("AYCICEGI")) return "OILSEED";
    if(k.includes("SOGAN") || k.includes("DOMATES") || k.includes("BIBER") || k.includes("PATATES")) return "VEG";
    return "OTHER";
  };

  // Family median fallback (katalogdan)
  const famStats = {};
  for(const [k,v] of cropMap.entries()){
    const fam = familyOf(v.displayName);
    if(!famStats[fam]) famStats[fam] = {w:[], p:[]};
    if(v.waterPerDa>0) famStats[fam].w.push(v.waterPerDa);
    if(v.profitPerDa!==0) famStats[fam].p.push(v.profitPerDa);
  }
  const median = (arr)=> {
    if(!arr || arr.length===0) return 0;
    const a=[...arr].sort((x,y)=>x-y);
    const mid=Math.floor(a.length/2);
    return a.length%2 ? a[mid] : (a[mid-1]+a[mid])/2;
  };
  const famMedian = {};
  for(const fam of Object.keys(famStats)){
    famMedian[fam] = {waterPerDa: median(famStats[fam].w), profitPerDa: median(famStats[fam].p)};
  }

  // Param çekimi: (1) katalog (2) yıl-1 mevcut parsel bazlı fallback (3) family median
  const getCropParams = (cropName, parcel, yearIndex)=>{
    const k = keyOf(cropName);
    const cp = cropMap.get(k);
    if(cp) return cp;

    // Yıl-1 için, mevcut su/kârı tamamen 0 göstermemek adına parselden türet
    if(yearIndex===1 && parcel){
      const area = +parcel.area_da || 0;
      if(area>0){
        const w = (+parcel.water_m3||0)/area;
        const pr = (+parcel.profit_tl||0)/area;
        // Eğer parsel verisi de 0 ise, family median'a düş
        if((w>0 || pr!==0) && !isFallow(cropName)){
          return {displayName: cropName, waterPerDa: Math.max(0,w), profitPerDa: pr};
        }
      }
    }

    const fam = familyOf(cropName);
    if(famMedian[fam] && !isFallow(cropName)){
      return {displayName: cropName, ...famMedian[fam]};
    }
    return {displayName: cropName, waterPerDa: 0, profitPerDa: 0};
  };

  // Katalogta olmayan ürünü zorlamayı engelle: sonraki yıllarda katalogtan seç
  const allowedKeys = new Set([...cropMap.keys()]);
  const ensureCatalogCrop = (name, fallbackName)=>{
    const k = keyOf(name);
    if(allowedKeys.has(k) || k==="NADAS") return name;
    // fallback'ı da katalogtan değilse düşük-su tahıl/baklagil
    const fb = fallbackName || "NOHUT";
    if(allowedKeys.has(keyOf(fb))) return fb;
    // son çare: katalogtaki en düşük su ürün
    let best = null;
    for(const v of cropMap.values()){
      if(v.waterPerDa<=0) continue;
      if(!best || v.waterPerDa < best.waterPerDa) best = v;
    }
    return best ? best.displayName : "NADAS";
  };

  // Aday seçim (katalogla sınırlı)
  const pickCandidate = (prevFam, wantLegume, phase, lastCrop, waterNeedFactor)=>{
    // Faz mantığı:
    // - DUSUK_SU: baklagil/tahıl/yağlı tohum (VEG hariç)
    // - DENGELI: düşük su + sınırlı VEG
    // - YUKSEK_KAR: kâr odaklı, VEG dahil (ama aynı ürün üst üste gelmesin)

    const famPool = (()=>{
      if(phase==='DUSUK_SU') return wantLegume ? ['LEGUME'] : ['LEGUME','CEREAL','OILSEED'];
      if(phase==='YUKSEK_KAR') return wantLegume ? ['LEGUME','VEG'] : ['VEG','LEGUME','CEREAL','OILSEED'];
      // DENGELI
      return wantLegume ? ['LEGUME','CEREAL'] : ['LEGUME','CEREAL','OILSEED','VEG'];
    })();

    const cand = [];
    for(const v of cropMap.values()){
      const fam = familyOf(v.displayName);
      if(!famPool.includes(fam)) continue;
      if(fam===prevFam && prevFam!=='FALLOW') continue; // münavebe
      if(lastCrop && keyOf(v.displayName)===keyOf(lastCrop)) continue; // tekrar engeli

      // Negatif/0 kârlı ürünleri (özellikle sebzede) planın "refah" bölümünde dışla
      if((phase==='YUKSEK_KAR' || phase==='DENGELI') && (v.profitPerDa||0) <= 0) continue;
      cand.push(v);
    }

    // Sıralama:
    // - DUSUK_SU: su düşük, sonra kâr
    // - DENGELI: kâr/m3 yüksek, sonra su
    // - YUKSEK_KAR: kâr yüksek, sonra su verimliliği
    const score = (v)=>{
      const w = Math.max(1e-6, (v.waterPerDa||0) * (waterNeedFactor||1));
      const p = (v.profitPerDa||0);
      if(phase==='DUSUK_SU') return (w*1000) - p; // minimize
      if(phase==='YUKSEK_KAR') return -(p) + (w*0.05);
      return -(p/w) + (w*0.002);
    };
    cand.sort((a,b)=> score(a)-score(b));
    return cand[0]?.displayName || 'NADAS';
  };

  // 2. ürün seçimi:
  // - Eğer Yıl-1'de 2. ürün NADAS değilse, sonraki yıllarda aynı ailede (ama aynı ürün üst üste olmayacak şekilde) çeşitlendir.
  // - Eğer Yıl-1'de 2. ürün NADAS ise: "örtü/yeşil gübre" (COVER) varsa onu, yoksa düşük su baklagil/tahıl (VEG hariç) seç.
  // Not: Kullanıcıların gördüğü "algoritma karşılaştırması" çıktısıyla paralellik için Yıl-1 ikinci ürünü referans alır.
  const pickSecondCrop = (yearIndex, baseSecondCrop, lastSecondCrop, firstFam, phase, waterNeedFactor)=>{
    const baseK = keyOf(baseSecondCrop);
    const lastK = keyOf(lastSecondCrop);
    const baseFam = (baseK && baseK!=="NADAS") ? familyOf(baseSecondCrop) : "";

    // Katalogtaki ürünlerden, hedef aileye göre aday üret
    const pickFromFamilies = (families)=>{
      const cand = [];
      for(const v of cropMap.values()){
        const fam = familyOf(v.displayName);
        if(!families.includes(fam)) continue;
        // 2. üründe sebze (VEG) suyu çok şişirebilir; sadece "refah" fazında izin ver
        if(fam==="VEG" && phase!=="YUKSEK_KAR") continue;
        // 1. ürünle aynı aile olmasın (münavebe)
        if(fam===firstFam && fam!=="FALLOW") continue;

        // Negatif/0 kârlı ürünleri dengele/refah fazında dışla
        if((phase==="YUKSEK_KAR" || phase==="DENGELI") && (v.profitPerDa||0) <= 0) continue;
        cand.push(v);
      }
      cand.sort((a,b)=>{
        const wa=(a.waterPerDa||0)*(waterNeedFactor||1), wb=(b.waterPerDa||0)*(waterNeedFactor||1);
        if(wa!==wb) return wa-wb;
        return (b.profitPerDa||0)-(a.profitPerDa||0);
      });
      // Aynı 2. ürünü üst üste verme
      for(const v of cand){
        if(keyOf(v.displayName)===lastK) continue;
        return v.displayName;
      }
      return cand[0]?.displayName || "NADAS";
    };

    // Yıl-1 ikinci ürün varsa: aynı ailede çeşitlendirme
    if(baseFam && baseFam!=="FALLOW"){
      return pickFromFamilies([baseFam, "COVER", "LEGUME", "CEREAL"]);
    }

    // Yıl-1 NADAS ise: önce COVER dene
    const coverPick = pickFromFamilies(["COVER"]);
    if(keyOf(coverPick)!=="NADAS") return coverPick;

    // COVER yoksa: düşük su baklagil/tahıl/yağlı tohum
    return pickFromFamilies(["LEGUME","CEREAL","OILSEED"]);
  };

  // Not: Önceki sürümde 2. ürün için "FIG" bulunamazsa katalogtaki en düşük su ürününe (çoğu zaman ISPANAK) düşüyordu.
  // Artık 2. ürün seçimi pickSecondCrop() ile yapılır (Yıl-1 ikinci ürün referansı + çeşitlendirme + VEG'leri varsayılan dışlama).

  // Toprak skoru: açıklanabilir, parsel bazlı
  // +2: baklagil, +1: örtü bitkisi, +1: family değişimi, -2: üst üste aynı family, -3: nadas (erozyon/OM kaybı)
  const soilDelta = (prevFam, fam, isPrevLegume)=>{
    let d = 0;
    if(fam==="LEGUME") d += 2;
    if(fam==="COVER") d += 1;
    if(fam==="FALLOW") d -= 3;
    if(fam!==prevFam && prevFam!=="FALLOW" && fam!=="FALLOW") d += 1;
    if(fam===prevFam && fam!=="FALLOW") d -= 2;
    // baklagil sonrası tahıl bonusu
    if(isPrevLegume && fam==="CEREAL") d += 1;
    return d;
  };

  // Planı üret (tüm parseller için)
  const rows = [];
  const parcelAgg = {}; // parsel bazlı özet

  // 5 yıllık plan başlangıç yılı: seçili su yılı varsa onu kullan, yoksa mevcut yıl.
  const startYear = (+STATE.selectedWaterYear || (new Date()).getFullYear());
  const baseGlobalBudget = computeGlobalBudgetM3();

  // Seçili projeksiyon senaryosuna göre yıl bazlı "kullanılabilir su" ve bütçe hesabı (STATE'i bozmadan)
  const _scaledIndex = (idx)=>{
    let v = +idx;
    if(isFinite(v) && v > 0 && v <= 1.2) v = v * 100;
    if(!isFinite(v)) v = 60;
    return v;
  };

  const getWaterIndexForYear = (y)=>{
    if(y<=2024){
      const r = (STATE.barajSeries||[]).find(x=>x.yil===y);
      return _scaledIndex(r ? r.doluluk : null);
    }
    const r = (STATE.projSeries||[]).find(x=>x.yil===y && x.senaryo===STATE.selectedProjScenario);
    return _scaledIndex(r ? r.doluluk : null);
  };

  const globalBudgetForYear = (y)=>{
    // applyWaterScenarioFromUI() mantığının saf versiyonu
    const idx = getWaterIndexForYear(y);
    const avail = Math.round((idx/100) * (STATE.maxCapacityM3 || (STATE.availableWaterM3||0) || 1));

    // computeGlobalBudgetM3()'deki "çok küçük" koruması aynı şekilde burada da olsun
    const totalA = Math.max(1, STATE.totalAreaAllParcels || 1);
    let currentNeed = 0;
    if(Array.isArray(STATE.parcels) && STATE.parcels.length){
      currentNeed = STATE.parcels.reduce((a,p)=> a + (+p.water_m3 || 0), 0);
    }
    if(!isFinite(currentNeed) || currentNeed<=0) currentNeed = totalA * 600;

    let base = avail;
    const fallbackBase = Math.max(currentNeed, totalA*600);
    if(!isFinite(base) || base<=0 || base < 0.20*currentNeed) base = fallbackBase;

    const risk = clamp(computeDroughtRiskForYear(y, idx), 0, 1);
    const factor = clamp(1 - 0.35*risk, 0.55, 1);
    return { budget: base*factor, risk, idx };
  };

  const phaseOf = (ratio, risk)=>{
    // çiftçiye anlatılabilir "faz" mantığı
    if(ratio < 0.95 || risk > 0.55) return 'DUSUK_SU';
    if(ratio > 1.12 && risk < 0.40) return 'YUKSEK_KAR';
    return 'DENGELI';
  };
  for(const p of parcelData){
    const area = +p.area_da || 0;

    const yr1 = (basin && basin.plan && basin.plan[p.id]) ? basin.plan[p.id].rows : null;
    let y1c1 = (yr1 && yr1[0] && yr1[0].name) ? yr1[0].name : (p.cropCurrent?.[0]?.name || "NADAS");
    let y1c2 = (yr1 && yr1[1] && yr1[1].name) ? yr1[1].name : "NADAS";

    // Yıl-1'de mevcut ürün adı katalogta olmayabilir: tablo 0 göstermesin diye parsel bazlı fallback var,
    // ama sonraki yıllarda katalogtan seçelim.
    y1c1 = ensureCatalogCrop(y1c1, "NOHUT");
    y1c2 = ensureCatalogCrop(y1c2, "NADAS");

    let prevFam = familyOf(y1c1);
    let lastWasLegume = (prevFam==="LEGUME");
    let soilScore = 0;
    let planWater5 = 0;
    let planProfit5 = 0;
    let fallowAreaYearSum = 0; // nadas alan payı (2 ürün de nadas olursa alanın tamamı sayılır, 1'i nadas olursa yarım gibi yaklaşım)

    let lastC1 = ""; // 1. ürün tekrarını azalt
    let lastC2 = ""; // 2. ürünün üst üste aynı gelmesini engellemek için
    const phaseCount = {DUSUK_SU:0, DENGELI:0, YUKSEK_KAR:0};
    let firstProsperYear = null;
    for(let y=1; y<=5; y++){
      const year = startYear + (y-1);
      const by = globalBudgetForYear(year);
      const ratio = by.budget / Math.max(1e-6, baseGlobalBudget);
      const phase = phaseOf(ratio, by.risk);
      phaseCount[phase] = (phaseCount[phase]||0) + 1;
      if(!firstProsperYear && phase==='YUKSEK_KAR') firstProsperYear = year;

      // Kurak yılda bitkinin su ihtiyacı artar (ET0 ↑), su bütçesi azalır.
      const waterNeedFactor = 1 + 0.35*clamp(by.risk,0,1);

      let c1, c2;
      if(y===1){
        c1 = y1c1;
        c2 = y1c2;
      }else{
        const wantLegume = (!lastWasLegume);
        c1 = pickCandidate(prevFam, wantLegume, phase, lastC1, waterNeedFactor);
        // 2. ürün: yıl-1'de algoritmanın verdiği 2. ürünü referans al (benchmark ile paralel),
        // sonraki yıllarda aynı ürünü sürekli tekrarlama ve "FIG bulunamadı => ISPANAK" bug'ına düşme.
        const baseSecond = y1c2 || "NADAS";
        c2 = pickSecondCrop(y, baseSecond, lastC2, familyOf(c1), phase, waterNeedFactor);
      }

      const fam1 = familyOf(c1);
      const fam2 = familyOf(c2);

      const p1 = getCropParams(c1, p, y);
      const p2 = getCropParams(c2, p, y);

      const waterYear = area * ((p1.waterPerDa||0) + (p2.waterPerDa||0)) * waterNeedFactor;
      const profitYear = area * ((p1.profitPerDa||0) + (p2.profitPerDa||0));

      planWater5 += waterYear;
      planProfit5 += profitYear;

      // nadas alan yaklaşımı: iki sezondan biri nadas ise %50, ikisi ise %100
      const fallowShare = (isFallow(c1)?0.5:0) + (isFallow(c2)?0.5:0);
      fallowAreaYearSum += (area * Math.min(1, fallowShare));

      // toprak skoru
      soilScore += soilDelta(prevFam, fam1, lastWasLegume);
      // 2. ürünün toprak etkisi (cover bonusu vb.)
      soilScore += soilDelta(fam1, fam2, fam1==="LEGUME");

      // güncelle
      prevFam = fam1;
      lastWasLegume = (fam1==="LEGUME");
      lastC1 = c1;
      lastC2 = c2;

      const soilLabel = (soilScore>=8) ? "Çok iyi" : (soilScore>=3) ? "İyi" : (soilScore>=-2) ? "Nötr" : "Riskli";

      rows.push({
        parcel: p.id,
        year,
        crop1: c1,
        crop2: c2,
        water: waterYear,
        profit: profitYear,
        soil: soilLabel
      });
    }

    const baseW5 = (+p.water_m3||0)*5;
    const baseP5 = (+p.profit_tl||0)*5;
    parcelAgg[p.id] = {
      baseW5, baseP5,
      planW5: planWater5, planP5: planProfit5,
      soilScore,
      fallowPct: (area>0) ? (fallowAreaYearSum/(area*5))*100 : 0,
      phaseCount,
      firstProsperYear
    };
  }

  // Filtre: parsel seçiliyse sadece o parseli göster
  const viewRows = (selectedParcelId==="__ALL__") ? rows : rows.filter(r=>r.parcel===selectedParcelId);

  
  const fmtSigned = (v, digits=1)=>{
    const n = Number(v);
    if(!isFinite(n)) return "0";
    const sign = (n>0) ? "+" : "";
    return sign + formatNumber(n, digits);
  };
// KPI hedefleri (genel ya da parsel)
  const kWater = document.getElementById("plan5WaterKpi");
  const kWaterSub = document.getElementById("plan5WaterKpiSub");
  const kSoil = document.getElementById("plan5SoilKpi");
  const kSoilSub = document.getElementById("plan5SoilKpiSub");
  const kNadas = document.getElementById("plan5NadasKpi");
  const kProfit = document.getElementById("plan5ProfitKpi");
  const kProfitSub = document.getElementById("plan5ProfitKpiSub");
  const kNadas2 = document.getElementById("plan5NadasKpi2");
  const kNadas2Sub = document.getElementById("plan5NadasKpi2Sub");
  const kSoilExplain = document.getElementById("plan5SoilExplain");
  const kProsper = document.getElementById("plan5ProsperKpi");
  const kProsperSub = document.getElementById("plan5ProsperKpiSub");
  const kShift = document.getElementById("plan5ShiftKpi");
  const kShiftSub = document.getElementById("plan5ShiftKpiSub");

  let baseW5 = baseWaterAll5, baseP5 = baseProfitAll5;
  let planW5 = 0, planP5 = 0, soilScore = 0, fallowPct = 0;
  let phaseCount = {DUSUK_SU:0, DENGELI:0, YUKSEK_KAR:0};
  let firstProsperYear = null;

  if(selectedParcelId!=="__ALL__" && parcelAgg[selectedParcelId]){
    const a = parcelAgg[selectedParcelId];
    baseW5 = a.baseW5; baseP5 = a.baseP5;
    planW5 = a.planW5; planP5 = a.planP5;
    soilScore = a.soilScore; fallowPct = a.fallowPct;
    phaseCount = a.phaseCount || phaseCount;
    firstProsperYear = a.firstProsperYear || null;
    if(kWaterSub) kWaterSub.textContent = "Seçili parselin mevcut desenine göre";
    if(kProfitSub) kProfitSub.textContent = "Seçili parselin mevcut desenine göre";
    if(kSoilSub) kSoilSub.textContent = "Bu parselde münavebe + baklagil + örtü bitkisi etkisi";
  }else{
    // genel: tabloda gördüğümüz satırlardan topla (rows zaten 5 yıl/parsel)
    planW5 = rows.reduce((a,r)=>a+(+r.water||0),0);
    planP5 = rows.reduce((a,r)=>a+(+r.profit||0),0);
    // genel toprak skorunu parsel skorlarının toplamı gibi göster
    soilScore = Object.values(parcelAgg).reduce((a,v)=>a+(+v.soilScore||0),0);
    phaseCount = Object.values(parcelAgg).reduce((acc,v)=>{
      const pc = v.phaseCount || {};
      acc.DUSUK_SU += (+pc.DUSUK_SU||0);
      acc.DENGELI  += (+pc.DENGELI||0);
      acc.YUKSEK_KAR += (+pc.YUKSEK_KAR||0);
      return acc;
    }, {DUSUK_SU:0, DENGELI:0, YUKSEK_KAR:0});
    // Genelde "refaha geçiş" yılı: en erken parsel refah yılı
    const years = Object.values(parcelAgg).map(v=>v.firstProsperYear).filter(Boolean).sort();
    firstProsperYear = years.length ? years[0] : null;
    // genel nadas oranı
    const totalArea = parcelData.reduce((a,p)=>a+(+p.area_da||0),0);
    const totalFallowAreaYears = parcelData.reduce((a,p)=> a + ((parcelAgg[p.id]?.fallowPct||0)/100)*(+p.area_da||0)*5, 0);
    fallowPct = (totalArea>0) ? (totalFallowAreaYears/(totalArea*5))*100 : 0;
    if(kWaterSub) kWaterSub.textContent = "Mevcut desene göre (tüm parseller)";
    if(kProfitSub) kProfitSub.textContent = "Mevcut desene göre (tüm parseller)";
    if(kSoilSub) kSoilSub.textContent = "Münavebe + baklagil + örtü bitkisi (tüm parseller)";
  }

  const waterDelta = planW5 - baseW5;
  const waterPct = (baseW5>0) ? (waterDelta/baseW5)*100 : null;
  const profitDelta = planP5 - baseP5;
  const profitPct = (baseP5>0) ? (profitDelta/baseP5)*100 : null;

  if(kWater) kWater.textContent = `${fmtSigned(waterDelta)} m³ (${waterPct==null?"—":fmtSigned(waterPct)}%)`;
  if(kProfit) kProfit.textContent = `${fmtSigned(profitDelta)} TL (${profitPct==null?"—":fmtSigned(profitPct)}%)`;
  if(kSoil) kSoil.textContent = `${soilScore>=0?"+":""}${Math.round(soilScore)} puan`;
  if(kNadas) kNadas.textContent = `${Math.max(0,Math.min(100,fallowPct)).toFixed(1)}%`;
  if(kNadas2) kNadas2.textContent = `${Math.max(0,Math.min(100,fallowPct)).toFixed(1)}%`;
  if(kSoilExplain) kSoilExplain.textContent = "Baklagil (+2), örtü (+1), rotasyon (+1), tekdüze (-2), nadas (-3)";

  // Refaha geçiş & desen değişimi
  if(kProsper){
    kProsper.textContent = firstProsperYear ? String(firstProsperYear) : "Belirsiz";
  }
  if(kProsperSub){
    kProsperSub.textContent = firstProsperYear
      ? "Bu yıldan itibaren su bütçesi izin verdiğinde yüksek kârlı ürünlere kademeli geçiş önerilir"
      : "Mevcut projeksiyonda su bütçesi sıkı; öncelik düşük su + toprak toparlama";
  }
  if(kShift){
    const tot = (phaseCount.DUSUK_SU||0) + (phaseCount.DENGELI||0) + (phaseCount.YUKSEK_KAR||0);
    const y = (selectedParcelId!=="__ALL__") ? 5 : (parcelData.length*5);
    // tot y ile eşleşmezse de gösterimi bozmayalım
    kShift.textContent = `${phaseCount.DUSUK_SU||0}↓ / ${phaseCount.DENGELI||0}≈ / ${phaseCount.YUKSEK_KAR||0}↑`;
    if(kShiftSub) kShiftSub.textContent = "↓ düşük su, ≈ dengeli, ↑ yüksek kâr (plan ufku boyunca)";
  }

  // Tabloyu bas
  tbody.innerHTML = "";
  for(const r of viewRows){
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${r.parcel}</td>
      <td>${r.year}</td>
      <td>${(r.crop1||"").toString()}</td>
      <td>${(r.crop2||"").toString()}</td>
      <td>${formatNumber(r.water||0,0)}</td>
      <td>${formatNumber(r.profit||0,0)}</td>
      <td>${r.soil||"—"}</td>
    `;
    tbody.appendChild(tr);
  }
}


function refreshUI() {
  try{ const p = parcelData.find(x=>String(x.id)===String(selectedParcelId)); if(p) ensureCurrentPattern(p); }catch(e){}

  renderParcelSummary();
  renderTables();
  renderMetrics();
  try{ renderPlan5(); }catch(_e){}
  // Resmî tablolar sekmesi: rapora hazır özet tablolar
  renderOfficialTables();
  try{ renderOfficialSummary(); }catch(_e){}

  const st = document.getElementById("algoStatus");
  if (st) {
    // Hesaplama sırasında durum metnini koru (yanıltıcı yeniden yazma olmasın)
    if(!STATE.isOptimizing){
      const ctx = lastOptimizeContext || { algo: selectedAlgo, scenario: selectedScenario };
      const algoName = ctx.algo === "ga" ? "GA" : (ctx.algo === "abc" ? "ABC" : "ACO");
      const baseTxt = (ctx.scenario === "mevcut")
        ? ("Hazır • " + algoName)
        : ("Hazır • " + algoName + " • " + ctx.scenario);
      st.textContent = baseTxt + (STATE.selectionDirty ? " • seçim değişti" : "");
    }
  }

  updateProductCards();
  if (window._updateParcelStyles) window._updateParcelStyles();
  updateStaleUI();
}

function canShowOptimizedForCurrentSelection(){
  return !!(
    lastOptimizeContext &&
    lastOptimizeContext.parcelId === selectedParcelId &&
    lastOptimizeContext.scenario === selectedScenario &&
    lastOptimizeContext.algo === selectedAlgo
  );
}

// v72: Make it impossible for the UI to "silently" show results for a different
// parcel/senaryo/algoritma. We keep old results visible (so screen doesn't jump),
// but we clearly mark them as stale.
function updateStaleUI(){
  const stale = (!!lastOptimizeContext) && (!STATE.isOptimizing) && (!canShowOptimizedForCurrentSelection()) && !!STATE.selectionDirty;
  document.body.classList.toggle('stale-results', !!stale);
  const banner = document.getElementById('staleBanner');
  if(banner) banner.style.display = stale ? 'block' : 'none';
}


// Algoritma seçimi
// Event listeners + Başlatma (güvenli)
window.addEventListener("DOMContentLoaded", async () => {
  // DOM referansları
  parcelSelectEl = document.getElementById("parcelSelect");
  parcelSummaryBody = document.querySelector("#parcelSummary .parcel-summary-body");

  // Veri setini backend'den yükle (tek kaynak)
  try {
    await loadEnhancedDataset();
    await loadMetaAndScenarioRules();

    // Su bütçesi grafikleri için baraj + projeksiyon serilerini yükle
    await loadWaterBudgetSeries();
    // If backend is running, show which CSVs it uses; otherwise show local CSV mode.
    await fetchBackendMeta();
    if(STATE.backendMeta){
      setDataBadge(true, "Backend (Python)");
    }else{
      setDataBadge(true, "Projeden CSV");
    }
    renderActiveFiles();


	  // loadEnhancedDataset() zaten parcelData'yı oluşturup doldurur.
	  if (!selectedParcelId && parcelData.length) selectedParcelId = parcelData[0].id;
  } catch (e) {
    console.error("ENHANCED veri seti yüklenemedi:", e);
    setDataBadge(false, "Veri yüklenemedi");
  }

  // Parsel dropdown'ını doldur (P1, P2, ... P10 doğal sıralama)
  if(parcelSelectEl){
    refreshParcelSelect();
    if(selectedParcelId) parcelSelectEl.value = selectedParcelId;
    parcelSelectEl.addEventListener("change", () => {
      selectedParcelId = parcelSelectEl.value;
      try{ if(window._updateParcelStyles) window._updateParcelStyles(); }catch(_){ }
      try{ if(window._focusParcel) window._focusParcel(selectedParcelId); }catch(_){ }
      // v72 UX: Parsel/senaryo/algoritma değiştiğinde önceki geçerli sonuçlar ekranda kalsın;
      // ancak "eski sonuç" olduğu açıkça belirtilsin ve paneller görsel olarak soluklaşsın.
      // Kullanıcı Optimizasyonu Çalıştır dediğinde yeni sonuçlar gelir.
      STATE.selectionDirty = true;
      refreshUI();
    });
  }else{
    console.error("parcelSelect bulunamadı. HTML'de id='parcelSelect' olmalı.");
  }

  document.querySelectorAll('input[name="scenario"]').forEach((radio) => {
    radio.addEventListener("change", () => {
      selectedScenario = radio.value;
      STATE.selectionDirty = true;
      refreshUI();
    });
  });

  // Algoritma seçimi
  const algoSelectEl = document.getElementById("algoSelect");
  if (algoSelectEl) {
    selectedAlgo = algoSelectEl.value || "ga";
    algoSelectEl.addEventListener("change", () => {
      selectedAlgo = algoSelectEl.value || "ga";
      STATE.selectionDirty = true;
      refreshUI();
    });
  }

  // Optimizasyonu çalıştır
  const runBtn = document.getElementById("runOptBtn");
  if (runBtn) {
    runBtn.addEventListener("click", async () => {
      const st = document.getElementById("algoStatus");
      const prevContext = lastOptimizeContext ? { ...lastOptimizeContext } : null;
      const pendingContext = { parcelId: selectedParcelId, scenario: selectedScenario, algo: selectedAlgo };
      // Aynı anda birden fazla optimize isteğini engelle (Network: canceled/pending sorunlarını önler)
      if (runBtn.disabled) return;
      runBtn.disabled = true;
      runBtn.classList.add("btn-disabled");
      STATE.isOptimizing = true;
      if (st) st.textContent = `Hesaplanıyor… (Python) • ${pendingContext.algo.toUpperCase()} • ${pendingContext.scenario}`;

      // Hesaplama bitene kadar ekranda SON geçerli sonuçlar kalsın (yanıltıcı ara görünüm olmasın)
      // refreshUI() çağırmıyoruz; sadece durum metni güncellenir.

      try{
        const out = await fetchAndCacheBasinPlanPython(selectedScenario, selectedAlgo);

        if(!out){
          if (st) st.textContent = "Yanıt yok / reddedildi";
          return;
        }

        lastOptimizeContext = pendingContext;
        STATE.selectionDirty = false;
        refreshUI();
        if (st) st.textContent = "Güncellendi";
      }catch(e){
        console.warn("Python optimizasyon hatası. Tarayıcı içi algoritmalar kullanılacak.", e);
        // Hata durumunda: önceki geçerli sonuçlar ekranda kalır.
        lastOptimizeContext = prevContext;
        STATE.selectionDirty = true;
        if (st) st.textContent = "Hata: Önceki sonuçlar gösteriliyor";
      } finally {
        STATE.isOptimizing = false;
        runBtn.disabled = false;
        runBtn.classList.remove("btn-disabled");
      }
    });

  }

  // Algoritma karşılaştırma (benchmark)
  const benchBtn = document.getElementById('runBenchmarkBtn');
  if(benchBtn){
    benchBtn.addEventListener('click', async ()=>{
      const st = document.getElementById('benchmarkStatus');
      if(benchBtn.disabled) return;
      benchBtn.disabled = true;
      benchBtn.classList.add('btn-disabled');
      if(st) st.textContent = 'Çalışıyor…';

      try{
        // Benchmark artık "Sezon veri seti" seçimine göre çalışır.
        // Sol paneldeki hedef senaryo (Mevcut / Su Tasarruf / Maks Kâr) ile birlikte,
        // kullanıcı isterse Senaryo-1, Senaryo-2 veya Birleşik aday havuzunu seçebilir.

        const getObjectiveScenario = ()=>{
          const el = document.querySelector('input[name="scenario"]:checked');
          return (el?.value || 'su_tasarruf').toString();
        };

        const selModeEl = document.getElementById('benchmarkSeasonSourceSel');
        const mode = normalizeSeasonSource(selModeEl?.value || 'use_selected');
        const uiSeasonSel = document.getElementById('seasonSourceSel');
        const selectedSeasonSource = normalizeSeasonSource(uiSeasonSel?.value || STATE.seasonSource || 's1');

        const objective = getObjectiveScenario();

        // Not: 'Mevcut' bir optimizasyon hedefi değildir; bu seçimde benchmark anlamlı olmaz.
        if(objective === 'mevcut'){
          const box = document.getElementById('benchmarkResults');
          if(box) box.innerHTML = '<div class="callout callout-warn"><b>Uyarı:</b> Benchmark karşılaştırması için sol panelden <b>Su tasarrufu</b> hedefini seçin ("Mevcut desen" sadece referans içindir).</div>';
          if(st) st.textContent = 'Uyarı';
          return;
        }


        const labelFor = (src)=>{
          if(src === 's1') return 'Senaryo-1 (tek başına)';
          if(src === 's2') return 'Senaryo-2 (tek başına)';
                    return String(src);
        };

        const sources = (mode === 'all') ? ['s1','s2'] : [ (mode === 'use_selected') ? selectedSeasonSource : mode ];

	        const box = document.getElementById('benchmarkResults');
	        const patBox = document.getElementById('benchmarkPatterns');
	        if(box) box.innerHTML = '';
	        if(patBox) patBox.innerHTML = '';

	        // Tek kaynak seçiliyse (en yaygın kullanım): sonuçları yalnızca 1 kez göster (tekrarlı başlık oluşmasın)
	        if(sources.length === 1){
	          const src = sources[0];
	          let j;
	          try{
	            j = await fetchBenchmarkPython(objective, src);
	          }catch(e){
	            // Yedek: tarayıcı içi benchmark
	            console.warn('Benchmark Python erişilemedi, tarayıcı içi benchmark kullanılacak:', e);
	            j = runBenchmarkInBrowser(objective, src);
	            j._note = 'Python benchmark erişilemedi; tarayıcı içi benchmark kullanıldı.';
	          }
	          // box'a küçük bir etiket basıp normal render fonksiyonunu kullan
	          if(box){
	            const note = j? (j._note ? `<div class="badge badge-warn" style="margin-bottom:8px;">${escapeHtml(String(j._note))}</div>` : '') : '';
	            box.innerHTML = `<div class="badge badge-ok" style="margin-bottom:8px;">${labelFor(src)} • Hedef: ${objective.replace('_',' ')}</div>` +
	                            note +
	                            `<div id="_benchSingle"></div>`;
	            const single = document.getElementById('_benchSingle');
	            renderBenchmarkResultsTo(j, single, patBox, true);
	          }else{
	            renderBenchmarkResultsTo(j, null, patBox, true);
	          }
	        }else{
	          // Çoklu senaryo çalıştırmada her birini ayrı kartta göster.
	          const wrap = document.createElement('div');
	          wrap.style.display = 'grid';
	          wrap.style.gridTemplateColumns = 'repeat(auto-fit, minmax(320px, 1fr))';
	          wrap.style.gap = '12px';
	          if(box) box.appendChild(wrap);

	          let lastOk = null;
	          for(const src of sources){
	            let j;
	            try{
	              j = await fetchBenchmarkPython(objective, src);
	            }catch(e){
	              console.warn('Benchmark Python erişilemedi, tarayıcı içi benchmark kullanılacak:', e);
	              j = runBenchmarkInBrowser(objective, src);
	              j._note = 'Python benchmark erişilemedi; tarayıcı içi benchmark kullanıldı.';
	            }
	            if(j && j.status === 'OK') lastOk = j;

	            const card = document.createElement('div');
	            card.className = 'card';
	            card.style.background = '#ffffff';
	            card.style.padding = '10px';
	            const note = j? (j._note ? `<div class="badge badge-warn" style="margin-bottom:8px;">${escapeHtml(String(j._note))}</div>` : '') : '';
	            card.innerHTML = `<div class="badge badge-ok" style="margin-bottom:8px;">${labelFor(src)} • Hedef: ${objective.replace('_',' ')}</div>`+
	                             note+
	                             `<div class="_benchRes"></div><div class="_benchPat" style="margin-top:10px;"></div>`;
	            wrap.appendChild(card);
	            const resEl = card.querySelector('div._benchRes');
	            const patEl = card.querySelector('div._benchPat');
	            renderBenchmarkResultsTo(j, resEl, patEl, false);
	          }

	          // Çoklu modda grafikler tek set: en son başarılı sonuçla güncelle; ayrıca alttaki "benchmarkPatterns" alanını boş bırakıyoruz
	          if(lastOk){
	            const dummy = document.createElement('div');
	            renderBenchmarkResultsTo(lastOk, dummy, null, true);
	          }
	        }

        if(st) st.textContent = (sources.length>1) ? 'Tamamlandı (seçili sezon senaryoları)' : 'Tamamlandı';
      }catch(e){
        console.warn('Benchmark hata:', e);
        const box = document.getElementById('benchmarkResults');
        if(box) box.innerHTML = '<div class="badge badge-warn">Benchmark hata: '+String(e?.message||e)+'</div>';
        if(st) st.textContent = 'Hata';
      }finally{
        benchBtn.disabled = false;
        benchBtn.classList.remove('btn-disabled');
      }
    });
  }
  // 15 Yıllık su tasarrufu (GA/ACO/ABC ayrı + ortalama)
  const impactBtn = document.getElementById('runImpact15yBtn');
  if(impactBtn){
    impactBtn.addEventListener('click', async ()=>{
      const st = document.getElementById('impact15yStatus');
      const box = document.getElementById('impact15ySummary');
      if(impactBtn.disabled) return;
      impactBtn.disabled = true;
      impactBtn.classList.add('btn-disabled');
      if(st) st.textContent = 'Hesaplanıyor…';
      if(box) box.innerHTML = '';

      try{
        const objective = (()=>{
          const el = document.querySelector('input[name="scenario"]:checked');
          return (el?.value || 'su_tasarruf').toString();
        })();

        const scenarioMap = {
          mevcut: 'mevcut',
          su_tasarruf: 'su_tasarruf',
          maks_kar: 'maks_kar',
          balanced: 'balanced',
          recommended: 'recommended'
        };

        const uiSeasonSel = document.getElementById('seasonSourceSel');
        const selectedSeasonSource = normalizeSeasonSource(uiSeasonSel?.value || STATE.seasonSource || 's1');

        const horizonEl = document.getElementById('impactHorizonYears');
        const horizonYears = Math.max(1, Math.min(30, parseInt(horizonEl?.value || '15',10)));

        // 15y etki sekmesi: use_selected / s1 / s2 / both
        const selModeEl = document.getElementById('impactSeasonSourceSel');
        const mode = normalizeSeasonSource(selModeEl?.value || 'use_selected');
        const sources = [ (mode === 'use_selected') ? selectedSeasonSource : mode ];

        const labelFor = (src)=>{
          if(src === 's1') return 'Senaryo-1 (tek başına)';
          if(src === 's2') return 'Senaryo-2 (tek başına)';
          if(false) return 'Senaryo-1';
          return String(src);
        };

        const rows = [];
        let lastOkOut = null;
        for(const src of sources){
          const payload = {
            selectedParcelIds: getSelectedParcelIdsForRun(),
            scenario: scenarioMap[objective] || 'su_tasarruf',
            year: STATE.selectedWaterYear || null,
            waterBudgetRatio: budgetRatioForScenarioKey(scenarioMap[objective] || objective),
            seasonSource: src,
            horizonYears,
            algorithms: ['GA','ABC','ACO'],
            repeats: Math.max(1, Math.min(30, parseInt((document.getElementById('impactRepeats')?.value || '8'),10))),
            maxSeconds: 120
          };

          if(impactAbortCtrl){ try{ impactAbortCtrl.abort(); }catch(e){} }
          impactAbortCtrl = new AbortController();
          const out = await apiPostJSON('/api/impact15y', payload, {timeoutMs: 600000, signal: impactAbortCtrl.signal});
          if(out?.status !== 'OK'){
            rows.push(`<div class="callout callout-warn"><b>${labelFor(src)}</b>: Hesaplama başarısız: ${escapeHtml(out?.message || 'Bilinmeyen hata')}</div>`);
            continue;
          }

          lastOkOut = out;

          const totals = out.totals || {};
          const fmt = (x)=> formatNumber(x,0);
          const pct = (x)=> (Number.isFinite(+x)? (+x).toFixed(2): '0.00');

          const mkLine = (name, t)=> {
            if(!t || t.status==='ERROR') return `<div class="small muted">${name}: -</div>`;
            return `<div class="small"><b>${name}</b>: 15y tasarruf <b>${fmt(t.saving_15y_m3)}</b> m³ — yıllık <b>${fmt(t.annual_saving_m3)}</b> m³ — <b>${pct(t.saving_pct)}</b>%</div>`;
          };

          rows.push(`
            <div class="card" style="padding:10px; margin-bottom:10px;">
              <div style="display:flex; justify-content:space-between; gap:8px; align-items:center;">
                <div><b>15 Yıllık Su Tasarrufu — ${escapeHtml(labelFor(src))}</b></div>
                <button class="btn-secondary btn-sm" data-impact-download="${escapeHtml(JSON.stringify(out.geojson||{}))}">GeoJSON indir</button>
              </div>
              <div class="small muted">Hesap: mevcut_su_m3 (parsel_su_kar_ozet) − öneri deseni suyu (urun_parametreleri su_tuketimi_m3_da × alan); NADAS=0; 15y = yıllık × ${horizonYears}</div>
              <div style="margin-top:6px;">
                ${mkLine('GA', totals.GA)}
                ${mkLine('ACO', totals.ACO)}
                ${mkLine('ABC', totals.ABC)}
                <div style="margin-top:6px; padding-top:6px; border-top:1px solid rgba(0,0,0,0.08);">
                  ${mkLine('ORTALAMA (GA+ACO+ABC)', totals.AVG)}
                </div>
              </div>
            </div>
          `);
        }

        if(box){
          box.innerHTML = rows.join('\n') || '<div class="small muted">Sonuç yok.</div>';

          // download handlers
          box.querySelectorAll('button[data-impact-download]').forEach(btn=>{
            btn.addEventListener('click', ()=>{
              try{
                const txt = btn.getAttribute('data-impact-download') || '{}';
                const gj = JSON.parse(txt);
                const blob = new Blob([JSON.stringify(gj, null, 2)], {type:'application/geo+json'});
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `water_saving_15y_${Date.now()}.geojson`;
                document.body.appendChild(a);
                a.click();
                a.remove();
                setTimeout(()=> URL.revokeObjectURL(url), 2000);
              }catch(e){
                alert('İndirme başarısız: '+e);
              }
            });
          });
        }

        // Charts: use the last successful run (single-source in this tab)
        if(lastOkOut) renderImpactWater15Chart(lastOkOut);

        if(st) st.textContent = 'Hazır';
      }catch(err){
        if(err && err.name === 'AbortError'){
          // User-initiated cancel or a new run started; don't show as error
          if(st) st.textContent = 'İptal';
          return;
        }
        console.error(err);
        if(st) st.textContent = 'Hata';
        if(box) box.innerHTML = `<div class="callout callout-warn">Hata: ${escapeHtml(String(err))}</div>`;
      }finally{
        impactBtn.disabled = false;
        impactBtn.classList.remove('btn-disabled');
      }
    });
  }

  // 15 Yıllık ortalama kâr projeksiyonu (GA/ACO/ABC ayrı + ortalama)
  const profit15Btn = document.getElementById('runProfit15yBtn');
  if(profit15Btn){
    profit15Btn.addEventListener('click', async ()=>{
      const st = document.getElementById('impact15yStatus');
      const box = document.getElementById('profit15ySummary');
      if(profit15Btn.disabled) return;
      profit15Btn.disabled = true;
      profit15Btn.classList.add('btn-disabled');
      if(st) st.textContent = 'Hesaplanıyor…';
      if(box) box.innerHTML = '';

      try{
        const objective = (()=>{
          const el = document.querySelector('input[name="scenario"]:checked');
          return (el?.value || 'su_tasarruf').toString();
        })();

        const scenarioMap = {
          mevcut: 'mevcut',
          su_tasarruf: 'su_tasarruf',
          maks_kar: 'maks_kar',
          balanced: 'balanced',
          recommended: 'recommended'
        };

        const uiSeasonSel = document.getElementById('seasonSourceSel');
        const selectedSeasonSource = normalizeSeasonSource(uiSeasonSel?.value || STATE.seasonSource || 's1');

        const horizonEl = document.getElementById('impactHorizonYears');
        const horizonYears = Math.max(1, Math.min(30, parseInt(horizonEl?.value || '15',10)));

        const repEl = document.getElementById('impactRepeats');
        const repeats = Math.max(1, Math.min(30, parseInt(repEl?.value || '8', 10)));

        const selModeEl = document.getElementById('impactSeasonSourceSel');
        const mode = normalizeSeasonSource(selModeEl?.value || 'use_selected');
        const src = (mode === 'use_selected') ? selectedSeasonSource : mode;

        const labelFor = (s)=>{
          if(s === 's1') return 'Senaryo-1 (tek başına)';
          if(s === 's2') return 'Senaryo-2 (tek başına)';
          if(false) return 'Senaryo-1';
          return String(s);
        };

        const payload = {
          selectedParcelIds: getSelectedParcelIdsForRun(),
          scenario: scenarioMap[objective] || 'su_tasarruf',
          year: STATE.selectedWaterYear || null,
          waterBudgetRatio: budgetRatioForScenarioKey(scenarioMap[objective] || objective),
          seasonSource: src,
          horizonYears,
          algorithms: ['GA','ABC','ACO'],
          repeats,
          maxSeconds: 120
        };

        if(profitAbortCtrl){ try{ profitAbortCtrl.abort(); }catch(e){} }
        profitAbortCtrl = new AbortController();
        const out = await apiPostJSON('/api/profit15y', payload, {timeoutMs: 600000, signal: profitAbortCtrl.signal});
        if(out?.status !== 'OK'){
          if(box) box.innerHTML = `<div class="callout callout-warn">Hesaplama başarısız: ${escapeHtml(out?.message || 'Bilinmeyen hata')}</div>`;
          if(st) st.textContent = 'Hata';
          return;
        }

        const totals = out.totals || {};
        const fmt = (x)=> formatNumber(x,0);

        const mkLine = (name, t)=>{
          if(!t || t.status==='ERROR') return `<div class="small muted">${name}: -</div>`;
          const base = safeNum(t.total_base_tl);
          const opt  = safeNum(t.total_opt_tl);
          const dA   = safeNum(t.delta_annual_tl);
          const d15  = safeNum(t.delta_15y_tl);
          return `<div class="small"><b>${name}</b>: Ortalama yıllık kâr <b>${fmt(opt)}</b> TL (mevcut: ${fmt(base)} TL) — yıllık fark <b>${fmt(dA)}</b> TL — 15y fark <b>${fmt(d15)}</b> TL</div>`;
        };

        const html = `
          <div class="card" style="padding:10px; margin-bottom:10px;">
            <div style="display:flex; justify-content:space-between; gap:8px; align-items:center;">
              <div><b>15 Yıllık Kâr Projeksiyonu — ${escapeHtml(labelFor(src))}</b></div>
              <button class="btn-secondary btn-sm" data-profit-download="${escapeHtml(JSON.stringify(out.geojson||{}))}">GeoJSON indir</button>
            </div>
            <div class="small muted">Hesap: mevcut_kar_tl (parsel_su_kar_ozet) vs öneri desen kârı (beklenen_verim_kg_da×fiyat_tl_kg − maliyet_tl_da)×alan; NADAS=0; 15y fark = yıllık fark × ${horizonYears}</div>
            <div style="margin-top:6px;">
              ${mkLine('GA', totals.GA)}
              ${mkLine('ACO', totals.ACO)}
              ${mkLine('ABC', totals.ABC)}
              <div style="margin-top:6px; padding-top:6px; border-top:1px solid rgba(0,0,0,0.08);">
                ${mkLine('ORTALAMA (GA+ACO+ABC)', totals.AVG)}
              </div>
            </div>
          </div>
        `;

        if(box){
          box.innerHTML = html;
          const btn = box.querySelector('button[data-profit-download]');
          if(btn){
            btn.addEventListener('click', ()=>{
              try{
                const txt = btn.getAttribute('data-profit-download') || '{}';
                const gj = JSON.parse(txt);
                const blob = new Blob([JSON.stringify(gj, null, 2)], {type:'application/geo+json'});
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `profit_15y_${Date.now()}.geojson`;
                document.body.appendChild(a);
                a.click();
                a.remove();
                setTimeout(()=> URL.revokeObjectURL(url), 2000);
              }catch(e){
                alert('İndirme başarısız: '+e);
              }
            });
          }
        }

        // Update profit chart
        renderImpactProfit15Chart(out);

        if(st) st.textContent = 'Hazır';
      }catch(err){
        if(err && err.name === 'AbortError'){
          // User-initiated cancel or a new run started; don't show as error
          if(st) st.textContent = 'İptal';
          return;
        }
        console.error(err);
        if(st) st.textContent = 'Hata';
        if(box) box.innerHTML = `<div class="callout callout-warn">Hata: ${escapeHtml(String(err))}</div>`;
      }finally{
        profit15Btn.disabled = false;
        profit15Btn.classList.remove('btn-disabled');
      }
    });
  }


  // Harita + grafikler: CDN yoksa uygulama tamamen durmasın
  if(typeof window.L !== "undefined"){
    // initMap async olduğu için hataları Promise üzerinden yakala
    initMap().catch((e)=>{
      console.error("initMap hata:", e);
      const mapBox = document.getElementById("map");
      if(mapBox) mapBox.innerHTML = '<div style="padding:12px;color:#667;">Harita başlatılamadı. (Leaflet/Esri eklentileri yüklenememiş olabilir)</div>';
    });
  }else{
    const mapBox = document.getElementById("map");
    if(mapBox) mapBox.innerHTML = '<div style="padding:12px;color:#667;">Harita yüklenemedi (Leaflet CDN erişimi yok).</div>';
  }

  if(typeof window.Chart !== "undefined"){
    // Daha net grafikler ve daha tutarlı tooltip davranışı
    try{
      Chart.defaults.devicePixelRatio = Math.max(2, (window.devicePixelRatio||1));
      Chart.defaults.animation = false;
      Chart.defaults.interaction = { mode: 'nearest', intersect: false };
      Chart.defaults.plugins = Chart.defaults.plugins || {};
      Chart.defaults.plugins.tooltip = Object.assign({ enabled: true }, (Chart.defaults.plugins.tooltip||{}));
    }catch(_e){}
    try{ initCharts(); }catch(e){ console.error("initCharts hata:", e); }
    try{ initBenchmarkCharts(); }catch(e){ console.error("initBenchmarkCharts hata:", e); }
  }else{
    console.warn("Chart.js yüklenemedi. Grafikler devre dışı.");
  }

  initTabs();
  initDataBinding();

  // Açılışta projeksiyon senaryosu seçimine bakmadan kuraklık kartı ve metrikler dolu gelsin
  try{ applyWaterScenarioFromUI(false); }catch(_e){}
  try{ updateDroughtAnalytics(); }catch(_e){}
  try{ updateDroughtAlarmCard(); }catch(_e){}

  // Açılışta: veri yüklendikten sonra kuraklık kartı ve metrikler dolu gelsin
  try{ applyWaterScenarioFromUI(false); }catch(_e){}
  try{ updateDroughtAnalytics(); }catch(_e){}
  try{ updateDroughtAlarmCard(); }catch(_e){}

  // İlk render
  refreshUI();
});