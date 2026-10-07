(function () {
  'use strict';

  const STORAGE_KEY = 'crop_kds_paper_language';
  const supported = new Set(['tr', 'en']);
  const originalText = new WeakMap();
  const originalAttributes = new WeakMap();
  const originalCharts = new WeakMap();
  let language = 'tr';
  let observer = null;

  const exact = new Map(Object.entries({
    'Tarımsal Karar Destek Sistemi': 'Agricultural Decision Support System',
    'Yapay Zekâ Destekli': 'Artificial Intelligence-Assisted',
    'Optimum Bitki Deseni Sistemi': 'Optimal Cropping Pattern System',
    'Kurumsal Karar Merkezi': 'Institutional Decision Center',
    'Bilimsel tarımsal planlama': 'Scientific agricultural planning',
    'Kurumsal tarımsal karar akışı': 'Institutional Agricultural Decision Workflow',
    'Proje seçimi ve oluşturma': 'Project Selection and Creation',
    'Yeni proje oluştur': 'Create New Project',
    'Proje oluştur': 'Create Project',
    'Proje kimliği': 'Project ID',
    'Proje adı': 'Project Name',
    'Kurum / kuruluş': 'Institution / Organization',
    'Planlama yılı': 'Planning Year',
    'İl / bölge': 'Province / Region',
    'Coğrafi kapsam / havza': 'Geographic Scope / Basin',
    'Açıklama': 'Description',
    'Veri sınıfı': 'Data Classification',
    'Başlangıç su bütçesi (m³)': 'Initial Water Budget (m³)',
    'Kurum tarafından sağlanan veri': 'Institution-Provided Data',
    'Sentetik genel proje': 'Synthetic General Project',
    'Aktif proje': 'Active Project',
    'Proje seçilmedi': 'No Project Selected',
    'Başlamak için aşağıdan bir proje seçin.': 'Select a project below to begin.',
    'Profil seçimi proje değiştirildiğinde korunur.': 'The execution profile is preserved when the project changes.',
    'Henüz proje yok. Yeni proje oluşturarak başlayın.': 'No projects are available. Create a project to begin.',
    'Kurumsal veri merkezi': 'Institutional Data Center',
    'Veri Yönetimi': 'Data Management',
    'Hazırlık': 'Readiness',
    'Analiz': 'Analysis',
    'Sonuçlar': 'Results',
    'Kaynak & Provenance': 'Sources & Provenance',
    'Referans Demo': 'Reference Demo',
    'İŞ AKIŞI': 'WORKFLOW',
    'PROJE PORTFÖYÜ': 'PROJECT PORTFOLIO',
    'PROJE': 'PROJECT',
    'AKTİF PROJE': 'ACTIVE PROJECT',
    'VERİ YÖNETİMİ': 'DATA MANAGEMENT',
    'HAZIRLIK / READINESS': 'READINESS',
    'ANALİZ': 'ANALYSIS',
    'SONUÇLAR': 'RESULTS',
    'KAYNAK & PROVENANCE': 'SOURCES & PROVENANCE',
    'REFERANS DEMO': 'REFERENCE DEMO',
    'SÜRÜM GEÇMİŞİ': 'RUN HISTORY',
    'Ana içeriğe geç': 'Skip to Main Content',
    'Referans Akkaya Demosunu Aç': 'Open Akkaya Reference Demo',
    'Karar Sisteminde Aç': 'Open in Decision System',
    'KARAR EKRANINDA AÇ': 'OPEN DECISION SCREEN',
    'Projeye geri dön': 'Return to Project',
    'Tez Karar Destek Ekranı': 'Research Decision Support Screen',
    'PROJE / RUN KARAR SUNUMU': 'PROJECT / RUN DECISION PRESENTATION',
    'Karar ekranı yükleniyor': 'Loading Decision Screen',
    'Bağlam doğrulanıyor.': 'Validating context.',
    'Aktif sağlayıcı': 'Active Provider',
    'Run bekleniyor': 'Waiting for Run',
    'Yönetici özeti': 'Executive Summary',
    'Veri ve Hesaplama Kaynakları': 'Data and Computation Sources',
    'Değiştirilemez analiz kayıtları': 'Immutable Analysis Records',
    'Daha fazla çalışma': 'More Runs',
    'Analiz hazırlık denetimi': 'Analysis Readiness Assessment',
    'Yapılandırma ve doğrulanmış önizleme': 'Configuration and Verified Preview',
    'Çalışma modu': 'Execution Profile',
    'Senaryo': 'Scenario',
    'Algoritma': 'Algorithm',
    'Hedef': 'Objective',
    'Su bütçe oranı': 'Water-Budget Ratio',
    'Algoritma parametreleri': 'Algorithm Parameters',
    'Önizleme oluştur': 'Create Preview',
    'Analizi çalıştır ve kaydet': 'Run and Store Analysis',
    'Çalıştırma öncesi kanıt özeti': 'Pre-Run Evidence Summary',
    'Revizyon, selection hash ve teknik ayrıntılar': 'Revision, Selection Hash, and Technical Details',
    'Teknik provenance ve hash ayrıntıları': 'Technical Provenance and Hash Details',
    'Doğrulanmış su sonuçları': 'Verified Water Results',
    'Aylık talep, arz ve teslim kapasitesi': 'Monthly Water Demand, Supply, and Delivery Capacity',
    'Ürün deseni ve yoğunlaşma': 'Cropping Pattern and Concentration',
    'Kanonik tam ürün payları': 'Canonical Complete Crop Shares',
    'Harita ve analiz birimi keşfi': 'Map and Analysis Unit Explorer',
    'Harita seçimi ↔ birim detayı': 'Map Selection ↔ Analysis Unit Detail',
    'Bir analiz birimi seçin.': 'Select an analysis unit.',
    'Ekonomik sonuçlar': 'Economic Results',
    'Analiz birimi': 'Analysis Unit',
    'Analiz birimleri': 'Analysis Units',
    'Analiz birimi seç': 'Select Analysis Unit',
    'Analiz Birimleri Haritası': 'Analysis Unit Map',
    'Analiz Birimi Karar Özeti': 'Analysis Unit Decision Summary',
    'Analiz Birimi Su-Kâr Metrikleri': 'Analysis Unit Water–Profit Metrics',
    'Optimizasyonu Çalıştır': 'Run Optimization',
    'Optimizasyon algoritması': 'Optimization Algorithm',
    'Hedef ve plan modu': 'Objective and Planning Mode',
    'Mevcut görünüm': 'Current Baseline',
    'Mevcut görünüm (referans)': 'Current Baseline (Reference)',
    'Mevcut': 'Current',
    'Su tasarrufu': 'Water Saving',
    'Kâr odaklı': 'Profit Maximization',
    'Su etkin kullanım': 'Water-Use Efficiency',
    'Su kullanımı (m³)': 'Water Use (m³)',
    'Net kâr (TL)': 'Net Profit (TRY)',
    'Mevcut su (m³)': 'Current Water (m³)',
    'Önerilen su (m³)': 'Recommended Water (m³)',
    'Mevcut net kâr (TL)': 'Current Net Profit (TRY)',
    'Önerilen net kâr (TL)': 'Recommended Net Profit (TRY)',
    'Ortalama': 'Mean',
    'Maks': 'Max',
    'Süre (sn)': 'Runtime (s)',
    'Desen çeşitliliği': 'Pattern Diversity',
    'Su tasarrufu hedefi': 'Water-Saving Objective',
    'Kâr odaklı hedef': 'Profit-Maximization Objective',
    'Su etkin kullanım hedefi': 'Water-Use Efficiency Objective',
    'Proje Özeti': 'Project Summary',
    'Mevcut toplam su': 'Current Total Water Use',
    'Seçili senaryo su': 'Selected Scenario Water Use',
    'Mevcut toplam net kâr': 'Current Total Net Profit',
    'Seçili senaryo net kâr': 'Selected Scenario Net Profit',
    'Mevcut su verimliliği': 'Current Water Productivity',
    'Seçili senaryo su verimliliği': 'Selected Scenario Water Productivity',
    'Mevcut Ürün Deseni': 'Current Cropping Pattern',
    'Önerilen Ürün Deseni': 'Recommended Cropping Pattern',
    'Karar açıklaması ve nedenleri': 'Decision Rationale',
    'Rotasyon / 2. Ürün Önerisi': 'Rotation / Secondary-Crop Recommendation',
    'Sulama yöntemi karşılaştırması': 'Irrigation Method Comparison',
    'Ekonomik dayanak': 'Economic Basis',
    'Aylık su kapasitesi ve kritik aylar': 'Monthly Water Capacity and Critical Months',
    'Seçili analiz birimi için sulama planı': 'Irrigation Schedule for the Selected Analysis Unit',
    'Kuraklık göstergeleri': 'Drought Indicators',
    'Proje verisi sağlanmadı': 'Project Data Not Provided',
    'SAĞLANMADI / NOT PROVIDED': 'NOT PROVIDED',
    'HESAPLANMADI / NOT CALCULATED': 'NOT CALCULATED',
    'UYGULANAMAZ / NOT APPLICABLE': 'NOT APPLICABLE',
    'Algoritma karşılaştırması': 'Algorithm Comparison',
    'İlçe / il düzeyi özet': 'District / Province Summary',
    'Resmî tablolar (özet)': 'Official Summary Tables',
    'Kullanıcı yönetimi': 'User Management',
    'Kullanıcı Yönetimi': 'User Management',
    'Mesajlar / gelen talepler': 'Messages / Incoming Requests',
    'Analiz birimi düzeyi desen': 'Analysis Unit Cropping Pattern',
    'Analiz birimi geometrisi / bilgi atama': 'Analysis Unit Geometry / Attribute Assignment',
    'Analiz birimi geometrisi ve bilgi atama': 'Analysis Unit Geometry / Attribute Assignment',
    'Kurumsal yönetim paneli': 'Institutional Management Panel',
    'Kullanıcı değiştir': 'Switch User',
    'Veri Kaynağı': 'Data Source',
    'VERİ KAYNAĞI': 'DATA SOURCE',
    'Aktif veri kaynakları': 'Active Data Sources',
    'Doğrulanmış önizleme': 'Verified Preview',
    'Önizleme gerekli': 'Preview Required',
    'Veri yeterliliği ve gereksinimler': 'Data Sufficiency and Requirements',
    'Proje analiz geçmişi': 'Project Analysis History',
    'Proje verilerini yönet': 'Manage Project Data',
    'Kurumsal proje seç': 'Select Institutional Project',
    'Kurumsal iş akışı': 'Institutional Workflow',
    'Bilimsel sınır': 'Scientific Boundary',
    'Temel proje verileri': 'Core Project Data',
    'Su yönetimi': 'Water Management',
    'Ekonomik kanıt': 'Economic Evidence',
    'Agronomi': 'Agronomy',
    'Su bütçesi': 'Water Budget',
    'Yıllık tahsis': 'Annual Allocation',
    'Aylık arz': 'Monthly Supply',
    'Teslim kapasitesi': 'Delivery Capacity',
    'Çevresel akış': 'Environmental Release',
    'İletim randımanı': 'Conveyance Efficiency',
    'Çok yıllık bitki suyu': 'Perennial-Crop Water Requirement',
    'Ürün verimi': 'Crop Yield',
    'Satış fiyatı': 'Sale Price',
    'Destek ödemesi': 'Support Payment',
    'Maliyet bileşenleri': 'Cost Components',
    'Net kâr': 'Net Profit',
    'Birim ekonomisi': 'Analysis Unit Economics',
    'Mevsimsel ekonomi': 'Seasonal Economics',
    'Ürün su parametreleri': 'Crop Water Parameters',
    'Fenoloji': 'Phenology',
    'Aday matrisi': 'Candidate Crop Matrix',
    'Mevcut desen': 'Current Cropping Pattern',
    'Aylık su': 'Monthly Water',
    'Yıllık su': 'Annual Water',
    'İklim': 'Climate',
    'Geometri': 'Geometry',
    'Ürün kataloğu': 'Crop Catalog',
    'Genel ekonomi': 'General Economics',
    'Toplam alan': 'Total Area',
    'Aday satırı': 'Candidate Rows',
    'Ürün': 'Crop',
    'Referans su': 'Reference Water',
    'Katalog türevi kâr': 'Catalog-Derived Profit',
    'Su muhasebesi': 'Water Accounting',
    'SU MUHASEBESİ': 'WATER ACCOUNTING',
    'OPTİMİZER SUYU': 'OPTIMIZER WATER',
    'DOĞRULANMIŞ TAM SEZON': 'VERIFIED FULL-SEASON WATER',
    'PLANLAMA YILI': 'PLANNING-YEAR WATER',
    'OTORİTATİF DEĞER': 'AUTHORITATIVE WATER',
    'TOPLAM NET KÂR': 'TOTAL NET PROFIT',
    'SU VERİMLİLİĞİ': 'WATER PRODUCTIVITY',
    'AKTİF ALAN': 'ACTIVE AREA',
    'NADAS / BOŞ': 'FALLOW / UNALLOCATED',
    'UYGUNLUK': 'FEASIBILITY',
    'Uyarılar': 'Warnings',
    'Çalışma kimliği': 'Run ID',
    'Proje kimliği': 'Project ID',
    'Başlangıç': 'Started',
    'Tamamlanma': 'Completed',
    'Plan farkı': 'Plan Difference',
    'Skor': 'Score',
    'Birim': 'Analysis Unit',
    'Alan (da)': 'Area (da)',
    'Mevcut ürün': 'Current Crop',
    'Seçili / önerilen ürün': 'Selected / Recommended Crop',
    'Otoritatif birim suyu (m³)': 'Authoritative Unit Water (m³)',
    'Su otoritesi': 'Water Authority',
    'Birim net kârı (TL)': 'Unit Net Profit (TRY)',
    'Durum': 'Status',
    'Uyarılar': 'Warnings',
    'Haritada mevcut': 'Available on Map',
    'Hazır': 'Ready',
    'Veri yok': 'No Data',
    'Yok / sağlanmadı': 'None / Not Provided',
    'Giriş yap': 'Sign In',
    'Panele giriş yap': 'Sign In to Dashboard',
    'Erişim akışı': 'Access Workflow',
    'KULLANICI ADI': 'USERNAME',
    'ŞİFRE': 'PASSWORD',
    'SİSTEME ERİŞİM': 'SYSTEM ACCESS',
    'Bilgilendirme': 'Information',
    'Hazırlayan': 'Prepared by',
    'Danışman': 'Supervisor',
    'Eş danışman': 'Co-Supervisor',
    'Çiftçi paneli': 'Farmer Dashboard',
    'Kurum paneli': 'Institutional Dashboard',
    'Karar çıktıları': 'Decision Outputs',
    'PANEL': 'DASHBOARD',
    'KULLANICI': 'USER',
    'Analiz kurulumu': 'Analysis Setup',
    'Veri kaynağı, algoritma ve senaryo ayarları': 'Data source, algorithm, and scenario settings',
    'Analiz birimi özeti': 'Analysis Unit Summary',
    'Seçili analiz birimi için hızlı durum görünümü': 'Quick status view for the selected analysis unit',
    'Kurumsal yönetim görünümü': 'Institutional Management View',
    'GENEL GÖRÜNÜM': 'OVERVIEW',
    'SEÇİLİ DETAY': 'SELECTED UNIT',
    'Referans durum': 'Baseline',
    'Referans kâr': 'Baseline Profit',
    'Mevcut desen': 'Current Cropping Pattern',
    'Mevsim': 'Season',
    'Sulama (Mevcut)': 'Irrigation (Current)',
    'Sulama (Öneri)': 'Irrigation (Recommended)',
    'Ekim Alanı (da - sezon)': 'Planted Area (da – season)',
    'Su (m³/da)': 'Water (m³/da)',
    'Toplam Su': 'Total Water',
    'Kâr (TL/da)': 'Profit (TRY/da)',
    'Toplam Kâr': 'Total Profit',
    'Mevsim / Oran': 'Season / Share',
    'SAĞLANMADI': 'NOT PROVIDED',
    'HESAPLANMADI': 'NOT CALCULATED',
    'UYGULANAMAZ': 'NOT APPLICABLE'
  }));

  const replacements = [
    [/Analiz Birimi Karar Özeti/g, 'Analysis Unit Decision Summary'],
    [/Analiz Birimi Su-Kâr Metrikleri/g, 'Analysis Unit Water–Profit Metrics'],
    [/Analiz Birimleri Haritası/g, 'Analysis Unit Map'],
    [/Seçili Analiz birimi - Önerilen Ürünler \(Rotasyon\)/g, 'Selected Analysis Unit – Recommended Crops (Rotation)'],
    [/Önerilen Ürün Deseni \(Senaryo \+ Algoritma\)/g, 'Recommended Cropping Pattern (Scenario + Algorithm)'],
    [/Rotasyon \/ 2\. Ürün Önerisi \(basit kurallar\)/g, 'Rotation / Secondary-Crop Recommendation (Rule-Based)'],
    [/Ekonomik dayanak \([^)]*\)/g, 'Economic Basis'],
    [/Seçili analiz birimi için sulama planı \([^)]*\)/g, 'Irrigation Schedule for the Selected Analysis Unit'],
    [/Kuraklık göstergeleri · proje verisi sağlanmadı/g, 'Drought Indicators · Project Data Not Provided'],
    [/Proje verisi sağlanmadı/gi, 'Project Data Not Provided'],
    [/SAĞLANMADI \/ NOT PROVIDED/g, 'NOT PROVIDED'],
    [/HESAPLANMADI \/ NOT CALCULATED/g, 'NOT CALCULATED'],
    [/UYGULANAMAZ \/ NOT APPLICABLE/g, 'NOT APPLICABLE'],
    [/Mevcut toplam su/g, 'Current Total Water Use'],
    [/Seçili senaryo su/g, 'Selected Scenario Water Use'],
    [/Mevcut toplam net kâr/g, 'Current Total Net Profit'],
    [/Seçili senaryo net kâr/g, 'Selected Scenario Net Profit'],
    [/Mevcut su verimliliği/g, 'Current Water Productivity'],
    [/Seçili senaryo su verimliliği/g, 'Selected Scenario Water Productivity'],
    [/analiz birimi/gi, match => match[0] === 'A' ? 'Analysis Unit' : 'analysis unit'],
    [/parsel/gi, match => match[0] === 'P' ? 'Parcel' : 'parcel'],
    [/REVİZYON/g, 'REVISION'],
    [/Revizyon/g, 'Revision'],
    [/Seçili:/g, 'Selected:'],
    [/Gerekli:/g, 'Required:'],
    [/Eksik:/g, 'Missing:'],
    [/seçili: evet/g, 'selected: yes'],
    [/seçili: hayır/g, 'selected: no'],
    [/geçerli: evet/g, 'valid: yes'],
    [/geçerli: hayır/g, 'valid: no'],
    [/tüketici: evet/g, 'consumer: yes'],
    [/motor: evet/g, 'engine: yes'],
    [/motor: hayır/g, 'engine: no'],
    [/bütünlük:/g, 'integrity:'],
    [/Engelleyici bulgu yok\./g, 'No blocking findings.'],
    [/Henüz analiz çalışması yok\./g, 'No analysis runs yet.'],
    [/Henüz kayıtlı analiz seçilmedi\./g, 'No stored analysis selected.'],
    [/Stored run yükleniyor\./g, 'Loading stored run.'],
    [/Bu proje yalnız otomatik kabul ve demonstrasyon geliştirmesi içindir\./g, 'This project is intended only for automated acceptance and demonstration development.'],
    [/Bu ekran yalnız seçili projenin değiştirilemez stored run kaydını gösterir\./g, 'This screen displays only the selected project’s immutable stored run.'],
    [/Bu çıktı karar önerisi olarak kullanılmamalıdır\./g, 'This output must not be used as an operational recommendation.'],
    [/Akkaya kabul edilmiş referans modeli/g, 'Accepted Akkaya Reference Model'],
    [/Resmî kurum verileri gelmeden önce eğitim, ekran görüntüsü ve bilimsel model gösterimi için kullanılabilir\./g, 'May be used for training, screenshots, and scientific model demonstration before official institutional data are available.'],
    [/RESMÎ SU TAHSİSİ VEYA SAHA DOĞRULAMASI DEĞİLDİR\./g, 'NOT AN OFFICIAL WATER ALLOCATION OR FIELD VALIDATION.'],
    [/Doğrulanmış veri, açık hazırlık denetimi ve sürümlenmiş analiz sonuçları için tek çalışma alanı\./g, 'A unified workspace for verified data, transparent readiness assessment, and versioned analysis results.']
  ];

  function translate(value) {
    if (typeof value !== 'string' || !value.trim()) return value;
    const leading = value.match(/^\s*/)[0];
    const trailing = value.match(/\s*$/)[0];
    const core = value.slice(leading.length, value.length - trailing.length);
    let result = exact.get(core) || core;
    if (result === core) replacements.forEach(([pattern, replacement]) => { result = result.replace(pattern, replacement); });
    return leading + result + trailing;
  }

  function rememberAttributes(element, refresh) {
    const names = ['aria-label', 'title', 'placeholder'];
    let values = originalAttributes.get(element);
    if (!values) {
      values = {};
      originalAttributes.set(element, values);
    }
    names.forEach(name => {
      if (!element.hasAttribute?.(name)) return;
      if (refresh || !(name in values)) values[name] = element.getAttribute(name);
      element.setAttribute(name, language === 'en' ? translate(values[name]) : values[name]);
    });
  }

  function applyNode(root, refresh = false) {
    if (!root) return;
    const nodes = [];
    if (root.nodeType === Node.TEXT_NODE) nodes.push(root);
    else if (root.nodeType === Node.ELEMENT_NODE || root.nodeType === Node.DOCUMENT_NODE) {
      if (root.nodeType === Node.ELEMENT_NODE) rememberAttributes(root, refresh);
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
      let node;
      while ((node = walker.nextNode())) {
        if (node.nodeType === Node.ELEMENT_NODE) rememberAttributes(node, refresh);
        else nodes.push(node);
      }
    }
    nodes.forEach(node => {
      const parent = node.parentElement;
      if (!parent || /^(SCRIPT|STYLE|PRE|CODE)$/.test(parent.tagName)) return;
      if (refresh || !originalText.has(node)) originalText.set(node, node.data);
      const source = originalText.get(node);
      node.data = language === 'en' ? translate(source) : source;
    });
  }

  function applyCharts() {
    if (!window.Chart?.getChart) return;
    document.querySelectorAll('canvas').forEach(canvas => {
      const chart = window.Chart.getChart(canvas);
      if (!chart?.data) return;
      if (!originalCharts.has(chart)) {
        originalCharts.set(chart, {
          labels: Array.isArray(chart.data.labels) ? [...chart.data.labels] : null,
          datasets: (chart.data.datasets || []).map(dataset => dataset.label)
        });
      }
      const source = originalCharts.get(chart);
      if (source.labels) {
        chart.data.labels = source.labels.map(label =>
          language === 'en' && typeof label === 'string' ? translate(label) : label
        );
      }
      (chart.data.datasets || []).forEach((dataset, index) => {
        const label = source.datasets[index];
        if (typeof label === 'string') dataset.label = language === 'en' ? translate(label) : label;
      });
      chart.update('none');
    });
  }

  function installSwitch() {
    if (document.querySelector('.paper-language-switch')) return;
    const wrapper = document.createElement('div');
    wrapper.className = 'paper-language-switch';
    wrapper.setAttribute('role', 'group');
    wrapper.setAttribute('aria-label', 'Interface language');
    wrapper.innerHTML = '<button type="button" data-paper-lang="tr">TR</button><button type="button" data-paper-lang="en">EN</button>';
    wrapper.addEventListener('click', event => {
      const selected = event.target.closest('[data-paper-lang]')?.dataset.paperLang;
      if (supported.has(selected)) setLanguage(selected);
    });
    document.body.append(wrapper);
  }

  function updateSwitch() {
    document.querySelectorAll('[data-paper-lang]').forEach(button => {
      const active = button.dataset.paperLang === language;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', String(active));
    });
  }

  function setLanguage(next) {
    language = supported.has(next) ? next : 'tr';
    localStorage.setItem(STORAGE_KEY, language);
    document.documentElement.lang = language;
    observer?.disconnect();
    applyNode(document);
    applyCharts();
    document.title = language === 'en' ? translate(document.title) : (originalTitle || document.title);
    updateSwitch();
    observer?.observe(document.documentElement, {subtree:true, childList:true, characterData:true, attributes:true, attributeFilter:['aria-label','title','placeholder']});
    window.dispatchEvent(new CustomEvent('cropkds:languagechange', {detail:{language}}));
  }

  const originalTitle = document.title;
  const queryLanguage = new URLSearchParams(location.search).get('lang');
  language = supported.has(queryLanguage) ? queryLanguage : (supported.has(localStorage.getItem(STORAGE_KEY)) ? localStorage.getItem(STORAGE_KEY) : 'tr');
  installSwitch();
  const style = document.createElement('style');
  style.textContent = '.paper-language-switch{position:fixed;right:14px;top:12px;z-index:4000;display:inline-flex;gap:2px;padding:3px;border:1px solid rgba(255,255,255,.45);border-radius:999px;background:#102f28;box-shadow:0 4px 16px rgba(0,0,0,.18)}.paper-language-switch button{min-height:28px;padding:3px 9px;border:0;border-radius:999px;background:transparent;color:#dcebe5;font:700 12px/1.2 Inter,"Segoe UI",Arial,sans-serif;cursor:pointer}.paper-language-switch button.active{background:#fff;color:#164f40}.paper-language-switch button:focus-visible{outline:3px solid #7cc7ff;outline-offset:2px}@media print{.paper-language-switch{display:none!important}}';
  document.head.append(style);
  observer = new MutationObserver(mutations => {
    observer.disconnect();
    mutations.forEach(mutation => {
      if (mutation.type === 'characterData') applyNode(mutation.target, true);
      else if (mutation.type === 'attributes') rememberAttributes(mutation.target, true);
      else mutation.addedNodes.forEach(node => applyNode(node));
    });
    updateSwitch();
    observer.observe(document.documentElement, {subtree:true, childList:true, characterData:true, attributes:true, attributeFilter:['aria-label','title','placeholder']});
  });
  setLanguage(language);
  window.__CROP_KDS_I18N__ = Object.freeze({get language(){return language;}, setLanguage, translate, applyCharts});
})();
