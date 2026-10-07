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
    'Arpa': 'Barley',
    'ARPA': 'BARLEY',
    'Nohut': 'Chickpea',
    'NOHUT': 'CHICKPEA',
    'Mercimek': 'Lentil',
    'MERCIMEK': 'LENTIL',
    'Ayçiçeği': 'Sunflower',
    'AYCICEGI': 'SUNFLOWER',
    'Mısır': 'Maize',
    'MISIR': 'MAIZE',
    'Buğday': 'Wheat',
    'BUĞDAY': 'WHEAT',
    'BUGDAY': 'WHEAT',
    'Elma': 'Apple',
    'ELMA': 'APPLE',
    'Armut': 'Pear',
    'ARMUT': 'PEAR',
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
    'Kullanıcı': 'User',
    'Kullanıcı yönetimi + bölgesel analiz görünümü': 'User management and regional analysis view',
    'Projeler / Kurumsal veri': 'Projects / Institutional Data',
    'Proje': 'Project',
    'KULLANICI': 'USER',
    'Veri kaynağı:': 'Data source:',
    'Çalışma provenance ayrıntıları': 'Run provenance details',
    'Test amaçlı manuel veri yükleme': 'Manual data upload for testing',
    'Veri doğrulama sonucu': 'Data validation result',
    'Senaryo 1 - Tek ürünlü parsel (en iyi 1-2 ürün + alternatifler)': 'Scenario 1 – Single-crop analysis unit (best 1–2 crops and alternatives)',
    'Senaryo 2 - Çift ürünlü / desen bazlı parsel (1+1 ürün / bahçede sıra arası)': 'Scenario 2 – Double-crop / pattern-based analysis unit (1+1 crop / orchard inter-row)',
    'Kullanılabilir su:': 'Available water:',
    'Su dağıtım mantığı yükleniyor...': 'Loading water-allocation logic...',
    'Yalnızca kurum/uzman veri giriş ekranı': 'Institutional / specialist data-entry screen only',
    'Harita üzerindeki parseller tıklanarak da seçilebilir.': 'Analysis units may also be selected directly on the map.',
    'Alan': 'Area',
    'Alan (m²)': 'Area (m²)',
    'Kaynak': 'Source',
    'Sulama': 'Irrigation',
    'Mevcut su': 'Current Water Use',
    'Mevcut net kâr': 'Current Net Profit',
    'Otoritatif su': 'Authoritative Water',
    'Su verimliliği': 'Water Productivity',
    'Aktif alan': 'Active Area',
    'Doğrulanmış tam sezon': 'Verified Full-Season Water',
    'Yıllık bütçe': 'Annual Budget',
    'Aylık teslim': 'Monthly Delivery',
    'Su uzlaştırma': 'Water Reconciliation',
    'Talep': 'Demand',
    'Kullanılabilir': 'Available',
    'Ay': 'Month',
    'Talep (m³)': 'Demand (m³)',
    'Kullanılabilir arz (m³)': 'Available Supply (m³)',
    'Teslim kapasitesi (m³)': 'Delivery Capacity (m³)',
    'ARZ AŞILDI': 'SUPPLY EXCEEDED',
    'TESLİM KAPASİTESİ AŞILDI': 'DELIVERY CAPACITY EXCEEDED',
    'Alan (da, sağlandıysa)': 'Area (da, if provided)',
    'Kanonik pay': 'Canonical Share',
    'Karar durumu': 'Decision Status',
    'Run veri revizyonu': 'Run Data Revision',
    'Güncel proje revizyonu': 'Current Project Revision',
    'Yeniden analiz gerekli': 'Reanalysis Required',
    'Kaynak etiketi': 'Source Label',
    'Önerilen': 'Recommended',
    'Optimize su': 'Optimized Water Use',
    'Optimize net kâr': 'Optimized Net Profit',
    'SEÇİLİ DETAY': 'SELECTED UNIT',
    'Seçili detay': 'Selected Unit',
    'Ana ürün': 'Primary Crop',
    'Ana Ürün': 'Primary Crop',
    '2. ürün / tamamlayıcı': 'Secondary / Complementary Crop',
    '2. Ürün / tamamlayıcı': 'Secondary / Complementary Crop',
    'Su Kullanımı (Mevcut)': 'Water Use (Current)',
    'Su Kullanımı (Seçili senaryo)': 'Water Use (Selected Scenario)',
    'Toplam Net Kâr (Mevcut)': 'Total Net Profit (Current)',
    'Toplam Net Kâr (Seçili senaryo)': 'Total Net Profit (Selected Scenario)',
    'Su Verimliliği (TL/m³ - Mevcut)': 'Water Productivity (TRY/m³ – Current)',
    'Su Verimliliği (TL/m³ - Seçili senaryo)': 'Water Productivity (TRY/m³ – Selected Scenario)',
    'Kuraklık notu (yardımcı kontrol)': 'Drought Note (Supporting Check)',
    'PROJECT DATA · Su muhasebesi karşılaştırması': 'PROJECT DATA · Water Accounting Comparison',
    'PROJECT DATA · Optimize net kâr': 'PROJECT DATA · Optimized Net Profit',
    'Ana Ürün · PRIMARY': 'Primary Crop · PRIMARY',
    '2. Ürün / tamamlayıcı · SECONDARY': 'Secondary / Complementary Crop · SECONDARY',
    'Toplam su': 'Total Water Use',
    'Proje mevcut ürün deseni': 'Current Project Cropping Pattern',
    'Sonuç bölümünü açmak için kayıtlı bir çalışma seçin veya yeni analiz çalıştırın.': 'Select a stored run or execute a new analysis to open the results section.',
    'Havza / sulama alanı': 'Basin / Irrigation Area',
    'Toplam alan (da)': 'Total Area (da)',
    'Geometri kapsamı': 'Geometry Coverage',
    'Veri revizyonu': 'Data Revision',
    'Mevcut desen / iklim': 'Current Pattern / Climate',
    'Veri sürüm geçmişi': 'Data Version History',
    'Su bütçesini tanımla': 'Define Water Budget',
    'Toplu veri yükle': 'Bulk Data Upload',
    'Sistem dosya yapısını ve kolon semantiğini otomatik analiz ederek veri türünü ve alan eşleştirmelerini belirler. Belirsiz veya eksik eşleşmeler fail-closed kalır.': 'The system automatically analyzes file structure and column semantics to determine data type and field mappings. Ambiguous or incomplete mappings remain fail-closed.',
    'Doğrulanmış veri yükleme': 'Verified Data Upload',
    'Veri türü': 'Data Type',
    'Yıllık su tahsisi': 'Annual Water Allocation',
    'Aylık su arzı': 'Monthly Water Supply',
    'Çok yıllık bitki su ihtiyacı': 'Perennial-Crop Water Requirement',
    'Veri şablonları': 'Data Templates',
    'ÖRNEK / ŞABLON VERİ · RESMÎ VERİ DEĞİLDİR': 'SAMPLE / TEMPLATE DATA · NOT OFFICIAL DATA',
    'ÖRNEK / ŞABLON VERİ — RESMÎ VERİ DEĞİLDİR': 'SAMPLE / TEMPLATE DATA — NOT OFFICIAL DATA',
    'Seçili senaryo için engelleyici bulgu yok. Uyarılar ve veri otoritesi yine de incelenmelidir.': 'No blocking findings exist for the selected scenario. Warnings and data authority must still be reviewed.',
    'Çok yıllık ürün suyu': 'Perennial-Crop Water Requirement',
    'VERIFIED INSTITUTIONAL · doğrulanmış proje verisi': 'VERIFIED INSTITUTIONAL · verified project data',
    'VERIFIED INSTITUTIONAL — doğrulanmış proje verisi': 'VERIFIED INSTITUTIONAL — verified project data',
    'S1 · Tek Ürün Deseni': 'S1 · Single-Crop Pattern',
    'S1 — Tek Ürün Deseni': 'S1 — Single-Crop Pattern',
    'S2 · Mevsimsel / Çoklu Ürün Senaryosu': 'S2 · Seasonal / Multi-Crop Scenario',
    'S2 — Mevsimsel / Çoklu Ürün Senaryosu': 'S2 — Seasonal / Multi-Crop Scenario',
    'Su Tasarrufu': 'Water Saving',
    'Kâr Odaklı': 'Profit Maximization',
    'Su Etkin Kullanım': 'Water-Use Efficiency',
    'Kayıtlı bir analiz seçildiğinde kaynak özeti burada gösterilir.': 'The source summary appears here when a stored analysis is selected.',
    'Çalışma': 'Run',
    'çalışma': 'run',
    'ZAMAN': 'TIME',
    'Zaman': 'Time',
    'SU (M³)': 'WATER (M³)',
    'Su (m³)': 'Water (m³)',
    'ÖRNEK / ŞABLON VERİ': 'SAMPLE / TEMPLATE DATA',
    'RESMÎ VERİ DEĞİLDİR': 'NOT OFFICIAL DATA',
    'doğrulanmış proje verisi': 'verified project data',
    'Tek Ürün Deseni': 'Single-Crop Pattern',
    'Mevsimsel / Çoklu Ürün Senaryosu': 'Seasonal / Multi-Crop Scenario',
    'Bu bölüm, sistemde kullanılan parsel, ürün, su bütçesi, sulama yöntemi ve harita verilerinin aktif durumunu gösterir. Manuel yüklenen dosyalar bu tarayıcı oturumunda veri kontrolü ve senaryo testi için hesaba katılır; kalıcı ve raporlanabilir Python backend çalışması için dosyalar backend/data altında güncellenmelidir.': 'This section shows the active status of analysis-unit, crop, water-budget, irrigation-method, and map data. Manually uploaded files are considered for data checks and scenario testing in this browser session; files must be updated under backend/data for persistent and reportable Python backend runs.',
    'Seçili parsel, hedef modu ve senaryo ayarlarıyla backend optimizasyonunu çalıştırır.': 'Runs backend optimization for the selected analysis unit, objective, and scenario settings.',
    'Not: Senaryo 1, her parseli esasen tek ürünlü kabul eder; sistem en iyi ana öneriyi ve diğer güçlü alternatifleri sıralar. Senaryo 2, parselde 1+1 ürün / desen yaklaşımını dener; bahçe-çok yıllık parsellerde ana ürün korunur, fark sıra arası ve sulama yönetiminden gelir.': 'Note: Scenario 1 treats each analysis unit primarily as single-crop and ranks the main recommendation with strong alternatives. Scenario 2 evaluates a 1+1 crop/pattern approach; for orchards and perennial units, the main crop is retained and differences arise from inter-row cropping and irrigation management.',
    'Not: Bu sürümde mevcut toplam su talebi önce toplam alana bölünerek genel m³/da değeri hesaplanır. Varsayılan planlama dekar bazlı adil kotadır; eşit köy payı karşılaştırma senaryosu olarak ayrıca gösterilir.': 'Note: In this version, total current water demand is divided by total area to calculate the overall m³/da value. The default plan uses a fair per-decare quota; equal village shares are shown separately as a comparison scenario.',
    'Seçilen hedef modu (su verimliliği / kâr) ile plan modu (S1 / S2) birlikte çalışır. Su hedefi en az suyu değil, mevcut suyu daha verimli kullanmayı; kâr hedefi ise su bütçesi altında geliri büyütmeyi öne çıkarır.': 'The selected objective (water productivity / profit) and planning mode (S1 / S2) operate together. The water objective prioritizes more productive use of available water, while the profit objective prioritizes income growth within the water budget.',
    'Aşağıdaki kartlar yalnızca seçili parselin backend-authoritative değerlerini gösterir.': 'The cards below show only backend-authoritative values for the selected analysis unit.',
    'Bu grafik, seçili senaryo tipi altında mevcut desen ve backend tarafından dönen hedef modu sonucunu m³ birimiyle karşılaştırır.': 'This chart compares the current pattern with the backend objective result under the selected scenario in m³.',
    'Bu grafik, seçili senaryo tipi altında mevcut desen ve backend tarafından dönen hedef modu sonucunu TL birimiyle karşılaştırır.': 'This chart compares the current pattern with the backend objective result under the selected scenario in TRY.',
    'Seçili parselde mevcut durumdaki desen ve referans değerler.': 'Current cropping pattern and reference values for the selected analysis unit.',
    'Seçili senaryo ve algoritmaya göre eşit su kotası altında önerilen desen.': 'Recommended cropping pattern under an equal water quota for the selected scenario and algorithm.',
    'Mevcut kayıtlı yöntem, optimizasyonun önerdiği yöntem ve diğer sulama seçenekleri aynı tabloda otomatik karşılaştırılır. Ayrı manuel seçim kaldırılmıştır.': 'The recorded current method, the optimization recommendation, and other irrigation options are compared automatically in one table. Separate manual selection has been removed.',
    'NOT PROVIDED · proje sonucu sulama yöntemi karşılaştırması sağlamadı.': 'NOT PROVIDED · The project result did not provide an irrigation-method comparison.',
    '2024 ürün fiyatı, verim, toplam üretim, toplam su, sulama işletme gideri ve toplam gider kalemleri aynı yerde gösterilir. Böylece kâr değeri yalnız tek bir sayı olarak değil, dayanağıyla birlikte okunur.': 'The 2024 crop price, yield, total production, total water use, irrigation operating cost, and total cost items are presented together, so net profit can be interpreted with its supporting basis.',
    'İletim kapasitesi varsa, seçili desenin aylık su talebi ile karşılaştırılır. CROPWAT/FAO-56 referanslı aylık ETc/ETo verisi mevcutsa onunla; yoksa ay-ağırlık yaklaşımıyla hesaplanır.': 'When delivery capacity is available, it is compared with monthly water demand for the selected pattern. Calculations use monthly CROPWAT/FAO-56-referenced ETc/ETo data when available, otherwise a monthly-weighting approach is used.',
    'Not: Bu plan, seçili parselin iklim serisi ve ürün takvimi üzerinden yaklaşık ETc hesabıyla üretilir. Günlük meteoroloji açıksa daha hassas, kapalıyken aylık iklim ortalamalarıyla çalışır.': 'Note: This schedule uses an approximate ETc calculation based on the selected analysis unit’s climate series and crop calendar. It uses daily meteorology when available and monthly climate averages otherwise.',
    'NOT PROVIDED · backend birim düzeyinde sulama takvimi sağlamadı.': 'NOT PROVIDED · The backend did not provide an analysis-unit irrigation schedule.',
    'Tarımsal Karar Destek Sistemi · Çiftçi ve kurum için rol bazlı tez prototipi': 'Agricultural Decision Support System · Role-based research prototype for farmers and institutions',
    'Kurumsal TL/m³ paydası: AUTHORITATIVE_VERIFIED_FULL_SEASON_WATER. Tam sezon ve planlama takvim yılı değerleri birleştirilmez.': 'Institutional TRY/m³ denominator: AUTHORITATIVE_VERIFIED_FULL_SEASON_WATER. Full-season and planning-calendar-year values are not combined.',
    'Kurumsal TL/m³ paydası:': 'Institutional TRY/m³ denominator:',
    '. Tam sezon ve planlama takvim yılı değerleri birleştirilmez.': '. Full-season and planning-calendar-year values are not combined.',
    'Mesajlar / gelen talepler': 'Messages / Incoming Requests',
    'Analiz birimi düzeyi desen': 'Analysis Unit Cropping Pattern',
    'Analiz birimi geometrisi / bilgi atama': 'Analysis Unit Geometry / Attribute Assignment',
    'Analiz birimi geometrisi ve bilgi atama': 'Analysis Unit Geometry / Attribute Assignment',
    'Kurumsal yönetim paneli': 'Institutional Management Panel',
    'Kullanıcı değiştir': 'Switch User',
    'Veri Kaynağı': 'Data Source',
    'Veri': 'Data',
    'Su': 'Water Use',
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
    [/(\d+) parsel/g, '$1 parcels'],
    [/KULLANICI/g, 'USER'],
    [/SEÇ[Iİ]L[Iİ] DETAY/g, 'SELECTED UNIT'],
    [/Resmî su tahsisi, saha doğrulaması veya Bakanlık onaylı öneri değildir\./g, 'This is not an official water allocation, field validation, or Ministry-approved recommendation.'],
    [/([^·]+) · türetilmiş su modeli/g, '$1 · derived water model'],
    [/([^·]+) · ham toplulaştırılmış kayıt/g, '$1 · raw aggregated record'],
    [/türetilmiş su modeli/g, 'derived water model'],
    [/ham toplulaştırılmış kayıt/g, 'raw aggregated record'],
    [/Su bütçesinin iklim girdilerini göstermek\./g, 'Shows the climate inputs of the water budget.'],
    [/Kaynak modeldeki alternatif desen\/sulama senaryolarını savunmada izlenebilir kılmak\./g, 'Makes alternative cropping-pattern and irrigation scenarios in the source model traceable for review.'],
    [/Kaynak dosyada kayıtlı değer; yeniden hesaplanmadı veya elle özetlenmedi\./g, 'Value recorded in the source file; it was neither recalculated nor manually summarized.'],
    [/Kaynak modelin toplulaştırılmış su göstergelerini göstermek\./g, 'Shows aggregated water indicators from the source model.'],
    [/Kaynak modelin yöntem, katsayı veya teknik destek tablosunu göstermek\./g, 'Shows the method, coefficient, or technical support table from the source model.'],
    [/Ürün alanı, üretim, verim ve su ihtiyacı referanslarını göstermek\./g, 'Shows reference values for crop area, production, yield, and water requirement.'],
    [/Ürün bazlı aylık su bütçesini göstermek\./g, 'Shows the monthly crop-level water budget.'],
    [/Gerçek kadastro parseli olmayan temsilî ürün-alan proxy kayıtlarını göstermek\./g, 'Shows representative crop-area proxy records that are not cadastral parcels.'],
    [/Arazi kullanımı ve sulanan\/kıraç alan yapısını göstermek\./g, 'Shows land use and irrigated/rainfed area structure.'],
    [/Meyve ürünlerinin alan ve üretim desenini göstermek\./g, 'Shows the area and production pattern of fruit crops.'],
    [/Sebze ürünlerinin alan ve üretim desenini göstermek\./g, 'Shows the area and production pattern of vegetable crops.'],
    [/Tarla ürünlerinin alan ve üretim desenini göstermek\./g, 'Shows the area and production pattern of field crops.'],
    [/Senaryo-2: ikinci ürün satırları var/g, 'Scenario 2: secondary-crop rows are available'],
    [/Kartlar, kişisel veri içermeyen ve savunmada anlamlı bulunan kaynak tablolardan gelir\./g, 'Cards are sourced from tables that contain no personal data and are relevant to the study review.'],
    [/Öneri ürün grubu/g, 'Recommended Crop Group'],
    [/Mevcut kategoriye yakın öner/g, 'Recommend Near the Current Category'],
    [/Bahçe \/ çok yıllık ürünler/g, 'Orchard / Perennial Crops'],
    [/2024 \(mevcut plan yılı\)/g, '2024 (current planning year)'],
    [/Tez mantığı için ana model sabitlendi: mevcut toplam su alana bölünür, her parsel alanı kadar adil su hakkı alır\. Diğer modeller yalnızca rapor\/karşılaştırma notu olarak tutulur\./g, 'The primary study model is fixed: current total water is divided by area, and each parcel receives a fair water entitlement proportional to its area. Other models are retained only for reporting and comparison.'],
    [/(\d+) köy mevcut toplam su/g, '$1 villages — current total water'],
    [/Mevcut genel yoğunluk/g, 'Current Overall Intensity'],
    [/Her parsel: alan/g, 'Each parcel: area'],
    [/Alan bazlı en fazla artan/g, 'Largest Area-Based Increase'],
    [/Alan bazlı en fazla azalan/g, 'Largest Area-Based Decrease'],
    [/Eşit köy modeli kaldırılmadı; hangi köyün mevcut duruma göre fazla avantaj\/kısıt aldığını göstermek için karşılaştırma olarak tutuldu\./g, 'The equal-village model is retained as a comparison to show which village receives more benefit or constraint relative to the current state.'],
    [/Alan bazlı kota mevcut talebe YAKIN/g, 'Area-based quota is CLOSE TO current demand'],
    [/Alan bazlı kota mevcut talebi ALTINDA/g, 'Area-based quota is BELOW current demand'],
    [/Alan bazlı kota mevcut talebi ÜSTÜNDE/g, 'Area-based quota is ABOVE current demand'],
    [/Planlama kuralı: 2024\/mevcut desende kullanılan toplam su, planlanabilir su varlığı kabul edilir\..*karşılaştırma\/adillik analizi için tutulur\./g, 'Planning rule: total water used under the 2024/current pattern is treated as the plannable water resource. It is first divided by total area to calculate a fair per-decare entitlement; each parcel receives a quota proportional to its area. The equal-village model is retained only for comparison and equity analysis.'],
    [/Planlama kuralı:.*karşılaştırma\/adillik analizi için tutulur\./g, 'Planning rule: total water used under the 2024/current pattern is treated as the plannable water resource. It is first divided by total area to calculate a fair per-decare entitlement; each parcel receives a quota proportional to its area. The equal-village model is retained only for comparison and equity analysis.'],
    [/Planlama kuralı:/g, 'Planning rule:'],
    [/mevcut desende kullanılan toplam su, planlanabilir su varlığı kabul edilir\./g, 'total water used under the current pattern is treated as the plannable water resource.'],
    [/Bu su önce toplam alana bölünerek dekar bazlı adil hak hesaplanır; her parcel kendi alanı oranında su kotası alır\./g, 'This water is divided by total area to calculate a fair per-decare entitlement; each parcel receives a quota proportional to its area.'],
    [/Eşit köy modeli yalnızca karşılaştırma\/adillik analizi için tutulur\./g, 'The equal-village model is retained only for comparison and equity analysis.'],
    [/Seçili parsel için hızlı durum görünümü/g, 'Quick Status View for the Selected Parcel'],
    [/Mevcut desen \/ Excel referansı/g, 'Current Pattern / Excel Reference'],
    [/Parsel Karar Özeti/g, 'Parcel Decision Summary'],
    [/Aktif hedef: Su tasarrufu odaklı/g, 'Active objective: Water Saving'],
    [/Su tasarrufu odaklı/g, 'Water Saving'],
    [/Parsel su kotası durumu:/g, 'Parcel Water-Quota Status:'],
    [/Parsel Su-Kâr Metrikleri/g, 'Parcel Water–Profit Metrics'],
    [/Aşağıdaki kartlar yalnızca seçili parselin değerlerini gösterir\./g, 'The cards below show values only for the selected parcel.'],
    [/Mevcut parsel su\/kâr değerleri referans olarak gösterilmeye devam eder\./g, 'Current parcel water/profit values remain visible as the reference.'],
    [/Kuraklık göstergeleri \(2000-2025\) - Detay/g, 'Drought Indicators (2000–2025) — Detail'],
    [/Hedef Modlarına Göre Toplam Su Kullanımı/g, 'Total Water Use by Objective'],
    [/Hedef Modlarına Göre Toplam Net Kâr/g, 'Total Net Profit by Objective'],
    [/Seçili Parsel - Önerilen Ürünler \(Rotasyon\)/g, 'Selected Parcel – Recommended Crops (Rotation)'],
    [/Mevcut toplam net kâr/g, 'Current Total Net Profit'],
    [/Su verimliliği/g, 'Water Productivity'],
    [/Bu parsel için önerilen deseni görmek için (?:Run Optimization|Optimizasyonu Çalıştır) butonuna basın\./g, 'Select Run Optimization to view the recommended pattern for this parcel.'],
    [/Bu parcel için önerilen deseni görmek için/g, 'To view the recommended pattern for this parcel,'],
    [/Optimizasyonu Çalıştır/g, 'Run Optimization'],
    [/butonuna basın\./g, 'select the button.'],
    [/Rotasyon \/ 2\. Ürün önerisi, optimizasyon sonucuna göre güncellenir\./g, 'The rotation / secondary-crop recommendation is updated from the optimization result.'],
    [/Rotasyon \/ 2\. Ürün/g, 'Rotation / Secondary Crop'],
    [/Rotasyon/g, 'Rotation'],
    [/2\. Ürün/g, 'Secondary Crop'],
    [/Seçili/g, 'Selected'],
    [/Önerilen/g, 'Recommended'],
    [/Ürünler/g, 'Crops'],
    [/Ürün/g, 'Crop'],
    [/ürünler/gi, 'crops'],
    [/ürün/gi, 'crop'],
    [/2\. crop/gi, 'Secondary Crop'],
    [/Rotation \/ 2\. \u00dcr\u00fcn/g, 'Rotation / Secondary Crop'],
    [/Selected parcel i\u00e7in sulama plan\u0131 \(ayl\u0131k \/ haftal\u0131k \/ g\u00fcnl\u00fck rehber\)/g, 'Irrigation Schedule for the Selected Parcel (Monthly / Weekly / Daily Guidance)'],
    [/Selected analysis unit, hedef modu ve senaryo ayarlar\u0131yla backend optimizasyonunu \u00e7al\u0131\u015ft\u0131r\u0131r\./g, 'Runs backend optimization for the selected analysis unit, objective, and scenario settings.'],
    [/Selected analysis unitde mevcut durumdaki desen ve referans de\u011ferler\./g, 'Current cropping pattern and reference values for the selected analysis unit.'],
    [/Selected analysis unit i\u00e7in sulama plan\u0131 \(ayl\u0131k \/ haftal\u0131k \/ g\u00fcnl\u00fck rehber\)/g, 'Irrigation Schedule for the Selected Analysis Unit (Monthly / Weekly / Daily Guidance)'],
    [/önerisi, optimizasyon sonucuna göre güncellenir\./g, 'recommendation is updated from the optimization result.'],
    [/Sulama yöntemi karşılaştırması için önce optimizasyon sonucunu üretin\./g, 'Run the optimization before viewing the irrigation-method comparison.'],
    [/Ekonomik dayanak tablosu, öneri sonucu oluştuğunda fiyat\/verim\/gider kırılımıyla doldurulur\./g, 'The economic-basis table is populated with price, yield, and cost details when a recommendation is available.'],
    [/Aylık kapasite kontrolü için önce optimizasyon sonucunu üretin\./g, 'Run the optimization before viewing the monthly capacity assessment.'],
    [/Seçili parsel için sulama planı \(aylık \/ haftalık \/ günlük rehber\)/g, 'Irrigation Schedule for the Selected Parcel (Monthly / Weekly / Daily Guidance)'],
    [/Sulama planı, önerilen desen oluştuğunda hesaplanır\./g, 'The irrigation schedule is calculated when a recommended pattern is available.'],
    [/^Bu bölüm, sistemde kullanılan parsel, ürün, su bütçesi, sulama yöntemi ve harita verilerinin aktif durumunu gösterir\..*backend\/data altında güncellenmelidir\.$/g, 'This section shows the active status of analysis-unit, crop, water-budget, irrigation-method, and map data. Manually uploaded files are considered for data checks and scenario testing in this browser session; files must be updated under backend/data for persistent and reportable Python backend runs.'],
    [/^Senaryo 1 - Tek ürünlü parsel \(en iyi 1-2 ürün \+ alternatifler\)$/g, 'Scenario 1 – Single-crop analysis unit (best 1–2 crops and alternatives)'],
    [/^Senaryo 2 - Çift ürünlü \/ desen bazlı parsel \(1\+1 ürün \/ bahçede sıra arası\)$/g, 'Scenario 2 – Double-crop / pattern-based analysis unit (1+1 crop / orchard inter-row)'],
    [/^Seçili parsel, hedef modu ve senaryo ayarlarıyla backend optimizasyonunu çalıştırır\.$/g, 'Runs backend optimization for the selected analysis unit, objective, and scenario settings.'],
    [/^Not: Senaryo 1, her parseli esasen tek ürünlü kabul eder;.*sulama yönetiminden gelir\.$/g, 'Note: Scenario 1 treats each analysis unit primarily as single-crop and ranks the main recommendation with strong alternatives. Scenario 2 evaluates a 1+1 crop/pattern approach; for orchards and perennial units, the main crop is retained and differences arise from inter-row cropping and irrigation management.'],
    [/^Institutional Management View aktif\. Bölge genelindeki (\d+) parsel için .*$/g, 'Institutional Management View is active. User management, official summary tables, water-budget assessment, and long-term impact views are available for all $1 analysis units.'],
    [/^Harita üzerindeki parseller tıklanarak da seçilebilir\.$/g, 'Analysis units may also be selected directly on the map.'],
    [/^Aşağıdaki kartlar yalnızca seçili analiz biriminin backend-authoritative değerlerini gösterir\.$/g, 'The cards below show only backend-authoritative values for the selected analysis unit.'],
    [/^Seçili parselde mevcut durumdaki desen ve referans değerler\.$/g, 'Current cropping pattern and reference values for the selected analysis unit.'],
    [/^SAĞLANMADI \/ NOT PROVIDED — proje sonucu sulama yöntemi karşılaştırması sağlamadı\.$/g, 'NOT PROVIDED — The project result did not provide an irrigation-method comparison.'],
    [/^Not: Bu plan, seçili parselin iklim serisi ve ürün takvimi üzerinden yaklaşık ETc hesabıyla üretilir\..*$/g, 'Note: This schedule uses an approximate ETc calculation based on the selected analysis unit’s climate series and crop calendar. It uses daily meteorology when available and monthly climate averages otherwise.'],
    [/^SAĞLANMADI \/ NOT PROVIDED — backend birim düzeyinde sulama takvimi sağlamadı\.$/g, 'NOT PROVIDED — The backend did not provide an analysis-unit irrigation schedule.'],
    [/^Tarımsal Karar Destek Sistemi · Çiftçi ve kurum için rol bazlı tez prototipi$/g, 'Agricultural Decision Support System · Role-based research prototype for farmers and institutions'],
    [/Ana Ürün · PRIMARY/g, 'Primary Crop · PRIMARY'],
    [/2\. Ürün \/ tamamlayıcı · SECONDARY/g, 'Secondary / Complementary Crop · SECONDARY'],
    [/^Bu bölüm, sistemde kullanılan analysis unit,.*backend\/data altında güncellenmelidir\.$/g, 'This section shows the active status of analysis-unit, crop, water-budget, irrigation-method, and map data. Manually uploaded files are considered for data checks and scenario testing in this browser session; files must be updated under backend/data for persistent and reportable Python backend runs.'],
    [/^Senaryo 1 - Tek ürünlü analysis unit \(en iyi 1-2 ürün \+ alternatifler\)$/g, 'Scenario 1 – Single-crop analysis unit (best 1–2 crops and alternatives)'],
    [/^Senaryo 2 - Çift ürünlü \/ desen bazlı analysis unit \(1\+1 ürün \/ bahçede sıra arası\)$/g, 'Scenario 2 – Double-crop / pattern-based analysis unit (1+1 crop / orchard inter-row)'],
    [/^Seçili analysis unit, hedef modu ve senaryo ayarlarıyla backend optimizasyonunu çalıştırır\.$/g, 'Runs backend optimization for the selected analysis unit, objective, and scenario settings.'],
    [/^Not: Senaryo 1, her analysis unitni esasen tek ürünlü kabul eder;.*sulama yönetiminden gelir\.$/g, 'Note: Scenario 1 treats each analysis unit primarily as single-crop and ranks the main recommendation with strong alternatives. Scenario 2 evaluates a 1+1 crop/pattern approach; for orchards and perennial units, the main crop is retained and differences arise from inter-row cropping and irrigation management.'],
    [/^Institutional Management View aktif\. Bölge genelindeki (\d+) analysis unit için .*$/g, 'Institutional Management View is active. User management, official summary tables, water-budget assessment, and long-term impact views are available for all $1 analysis units.'],
    [/^Harita üzerindeki analiz birimleri tıklanarak da seçilebilir\.$/g, 'Analysis units may also be selected directly on the map.'],
    [/^Seçili analysis unitde mevcut durumdaki desen ve referans değerler\.$/g, 'Current cropping pattern and reference values for the selected analysis unit.'],
    [/^Not: Bu plan, seçili analysis unitnin iklim serisi ve ürün takvimi üzerinden yaklaşık ETc hesabıyla üretilir\..*$/g, 'Note: This schedule uses an approximate ETc calculation based on the selected analysis unit’s climate series and crop calendar. It uses daily meteorology when available and monthly climate averages otherwise.'],
    [/optimizer su/g, 'optimizer water'],
    [/otoritatif su/g, 'authoritative water'],
    [/planlama yılı/g, 'planning-year water'],
    [/tam sezon/g, 'full-season water'],
    [/net kâr/g, 'net profit'],
    [/su verimliliği/g, 'water productivity'],
    [/ · fark /g, ' · difference '],
    [/Tarımsal Karar Destek Sistemi/g, 'Agricultural Decision Support System'],
    [/Çiftçi ve kurum için rol bazlı tez prototipi/g, 'Role-based research prototype for farmers and institutions'],
    [/proje planning-year water/g, 'project planning year'],
    [/Talep/g, 'Demand'],
    [/Kullanılabilir/g, 'Available'],
    [/Institutional Management View aktif\./g, 'Institutional Management View is active.'],
    [/aktif\./g, 'is active.'],
    [/Proje kapsamındaki analiz birimleri/g, 'Analysis units in the project'],
    [/Senaryo Özeti \(seçili kapsam\)/g, 'Scenario Summary (Selected Scope)'],
    [/Aktif hedef: Mevcut desen/g, 'Active objective: Current Pattern'],
    [/Akkaya Sulama Alanı toplamı/g, 'Total Akkaya Irrigation Area'],
    [/^aktif\.$/g, 'is active.'],
    [/Bölge genelindeki/g, 'Across the region,'],
    [/için kullanıcı yönetimi, resmi özet tablolar, su bütçesi ve uzun vadeli etki ekranları birlikte kullanılabilir\./g, 'support user management, official summary tables, water-budget assessment, and long-term impact views.'],
    [/Bölge genelindeki (\d+) analysis unit için kullanıcı yönetimi, resmi özet tablolar, su bütçesi ve uzun vadeli etki ekranları birlikte kullanılabilir\./g, 'User management, official summary tables, water-budget assessment, and long-term impact views are available for all $1 analysis units across the region.'],
    [/Ana ürün/g, 'Primary Crop'],
    [/Ana Ürün/g, 'Primary Crop'],
    [/2\. ürün \/ tamamlayıcı/g, 'Secondary / Complementary Crop'],
    [/2\. Ürün \/ tamamlayıcı/g, 'Secondary / Complementary Crop'],
    [/çalışma/g, 'run'],
    [/Doğrulanmış veri, açık hazırlık denetimi ve sürümlenmiş analiz sonuçları için tek run alanı\./g, 'A unified workspace for verified data, transparent readiness assessment, and versioned analysis results.'],
    [/^(\d+) birimin tamamında proje geometrisi mevcut\.$/g, '$1 project geometries are available for all analysis units.'],
    [/^Immutable run ([^·]+) · selection hash ([^·]+) · yüklenmiş proje veri setleri; Akkaya fallback kullanılmadı\.$/g, 'Immutable run $1 · selection hash $2 · loaded project datasets; no Akkaya fallback was used.'],
    [/^(\d{4}) · proje planlama yılı$/g, '$1 · project planning year'],
    [/^Institutional Management View aktif\. Bölge genelindeki (\d+) parsel için kullanıcı yönetimi, resmi özet tablolar, su bütçesi ve uzun vadeli etki ekranları birlikte kullanılabilir\.$/g, 'Institutional Management View is active. User management, official summary tables, water-budget assessment, and long-term impact views are available for all $1 analysis units.'],
    [/^Aktif hedef: Su tasarrufu$/g, 'Active objective: Water Saving'],
    [/^Toplam planlama su bütçesi: (.+)$/g, 'Total planning water budget: $1'],
    [/^Backend feasibility: (.+) · yıllık bütçe: (.+) · aylık arz: (.+) · aylık teslim: (.+)$/g, 'Backend feasibility: $1 · annual budget: $2 · monthly supply: $3 · monthly delivery: $4'],
    [/^(.+) · Proje Özeti$/g, '$1 · Project Summary'],
    [/^(\d{4}) proje toplamı · yalnız PROJECT_DATA$/g, '$1 project total · PROJECT_DATA only'],
    [/^Karar açıklaması: (.+)$/g, 'Decision rationale: $1'],
    [/^Karar durumu: (.+)$/g, 'Decision status: $1'],
    [/^(\d{4}) proje ekonomik dayanağı$/g, '$1 project economic basis'],
    [/^Backend aylık talep, kullanılabilir arz ve teslim kapasitesi · (.+)$/g, 'Backend monthly demand, available supply, and delivery capacity · $1'],
    [/Tarım Birimi/g, 'Agriculture Unit'],
    [/Kullanıcı yönetimi/g, 'User management'],
    [/Resmi özet tablolar/g, 'Official summary tables'],
    [/yıllık bütçe/g, 'annual budget'],
    [/aylık arz/g, 'monthly supply'],
    [/aylık teslim/g, 'monthly delivery'],
    [/Uyarılar:/g, 'Warnings:'],
    [/Motorun ürettiği plan mevcut bütçe\/kısıtlara uygun değil; tamamlanan çalışma uygulanabilir plan anlamına gelmez\./g, 'The engine-generated plan does not satisfy the current budget/constraints; a completed run does not imply a feasible plan.'],
    [/Motorun ürettiği plan mevcut bütçe\/kısıtlara uygun değil; tamamlanan run uygulanabilir plan anlamına gelmez\./g, 'The engine-generated plan does not satisfy the current budget/constraints; a completed run does not imply a feasible plan.'],
    [/dönem/g, 'periods'],
    [/ihlal:/g, 'violations:'],
    [/GA, (water_saving|max_profit|water_efficiency) hedefi altında project candidate matrix kullanılarak çalıştırıldı\./g, 'GA was run using the project candidate matrix under the $1 objective.'],
    [/Sonuç aylık\/teslim kısıtları nedeniyle diagnostic durumdadır; Akkaya fallback kullanılmadı\./g, 'The result is diagnostic because of monthly supply/delivery constraints; no Akkaya fallback was used.'],
    [/KISIT İHLALİ/g, 'CONSTRAINT VIOLATION'],
    [/Bu görünüm immutable (run-[A-Za-z0-9]+) backend sonucudur; tarayıcıda bilimsel yeniden hesaplama yapılmadı\./g, 'This view presents immutable backend result $1; no scientific recalculation was performed in the browser.'],
    [/\bARPA\b/g, 'BARLEY'],
    [/\bNOHUT\b/g, 'CHICKPEA'],
    [/\bMERCIMEK\b/g, 'LENTIL'],
    [/\bAYCICEGI\b/g, 'SUNFLOWER'],
    [/\bMISIR\b/g, 'MAIZE'],
    [/\bBUGDAY\b/g, 'WHEAT'],
    [/\bBUĞDAY\b/g, 'WHEAT'],
    [/\bELMA\b/g, 'APPLE'],
    [/\bARMUT\b/g, 'PEAR'],
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
    [/(\d+) parcel\b/g, '$1 parcels'],
    [/REVİZYON/g, 'REVISION'],
    [/Revizyon/g, 'Revision'],
    [/Buğday/g, 'Wheat'],
    [/Arpa/g, 'Barley'],
    [/Nohut/g, 'Chickpea'],
    [/Mercimek/g, 'Lentil'],
    [/Ayçiçeği/g, 'Sunflower'],
    [/Mısır/g, 'Maize'],
    [/Elma/g, 'Apple'],
    [/Armut/g, 'Pear'],
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
    [/Proje bağlamı açılamadı:/g, 'Project context could not be opened:'],
    [/Akkaya verisine otomatik geçiş yapılmadı\./g, 'No automatic switch to Akkaya data was made.'],
    [/Tek bir provider, project_id, run_id ve unit parametresi gerekir\./g, 'Exactly one provider, project_id, run_id, and unit parameter is required.'],
    [/project_id biçimi geçersiz\./g, 'The project_id format is invalid.'],
    [/Proje bulunamadı\./g, 'Project not found.'],
    [/Bu ekran yalnız seçili projenin değiştirilemez stored run kaydını gösterir\./g, 'This screen displays only the selected project’s immutable stored run.'],
    [/Bu çıktı karar önerisi olarak kullanılmamalıdır\./g, 'This output must not be used as an operational recommendation.'],
    [/Akkaya kabul edilmiş referans modeli/g, 'Accepted Akkaya Reference Model'],
    [/Resmî kurum verileri gelmeden önce eğitim, ekran görüntüsü ve bilimsel model gösterimi için kullanılabilir\./g, 'May be used for training, screenshots, and scientific model demonstration before official institutional data are available.'],
    [/RESMÎ SU TAHSİSİ VEYA SAHA DOĞRULAMASI DEĞİLDİR\./g, 'NOT AN OFFICIAL WATER ALLOCATION OR FIELD VALIDATION.'],
    [/Doğrulanmış veri, açık hazırlık denetimi ve sürümlenmiş analiz sonuçları için tek çalışma alanı\./g, 'A unified workspace for verified data, transparent readiness assessment, and versioned analysis results.'],
    [/^Not: Senaryo 1, her analysis unitni .*sulama yönetiminden gelir\.$/g, 'Note: Scenario 1 treats each analysis unit primarily as single-crop and ranks the main recommendation with strong alternatives. Scenario 2 evaluates a 1+1 crop/pattern approach; for orchards and perennial units, the main crop is retained and differences arise from inter-row cropping and irrigation management.'],
    [/^Not: Bu plan, seçili analysis unitnin .*çalışır\.$/g, 'Note: This schedule uses an approximate ETc calculation based on the selected analysis unit’s climate series and crop calendar. It uses daily meteorology when available and monthly climate averages otherwise.'],
    [/^Not: Bu plan, .*ETc hesabıyla üretilir\..*çalışır\.$/g, 'Note: This schedule uses an approximate ETc calculation based on the selected unit’s climate series and crop calendar. It uses daily meteorology when available and monthly climate averages otherwise.']
  ];

  function translate(value) {
    if (typeof value !== 'string' || !value.trim()) return value;
    const leading = value.match(/^\s*/)[0];
    const trailing = value.match(/\s*$/)[0];
    const core = value.slice(leading.length, value.length - trailing.length);
    let result = exact.get(core) || core;
    if (result === core) {
      for (let pass = 0; pass < 8; pass += 1) {
        const before = result;
        replacements.forEach(([pattern, replacement]) => { result = result.replace(pattern, replacement); });
        if (result === before) break;
      }
    }
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
      if (language === 'en' && parent.closest?.('#roleInfoBanner')) {
        const count = Number(parent.closest('#roleInfoBanner').textContent.match(/\b(\d+)\b/)?.[1]);
        if (Number.isFinite(count) && count !== 1) {
          node.data = node.data.replace(/\bparcel\b/g, 'parcels');
        }
      }
    });
  }

  function applyCharts() {
    if (!window.Chart?.getChart) return;
    document.querySelectorAll('canvas').forEach(canvas => {
      const chart = window.Chart.getChart(canvas);
      if (!chart?.data) return;
      if (!originalCharts.has(chart)) {
        const tooltipCallbacks = chart.options?.plugins?.tooltip?.callbacks || {};
        originalCharts.set(chart, {
          labels: Array.isArray(chart.data.labels) ? [...chart.data.labels] : null,
          datasets: (chart.data.datasets || []).map(dataset => dataset.label),
          title: chart.options?.plugins?.title?.text,
          axisTitles: Object.fromEntries(Object.entries(chart.options?.scales || {}).map(
            ([key, axis]) => [key, axis?.title?.text]
          )),
          tooltipCallbacks: Object.fromEntries(Object.entries(tooltipCallbacks).filter(
            ([, callback]) => typeof callback === 'function'
          ))
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
      if (chart.options?.plugins?.title && typeof source.title === 'string') {
        chart.options.plugins.title.text = language === 'en' ? translate(source.title) : source.title;
      }
      Object.entries(chart.options?.scales || {}).forEach(([key, axis]) => {
        const title = source.axisTitles[key];
        if (axis?.title && typeof title === 'string') {
          axis.title.text = language === 'en' ? translate(title) : title;
        }
      });
      const callbacks = chart.options?.plugins?.tooltip?.callbacks;
      if (callbacks) Object.entries(source.tooltipCallbacks).forEach(([key, callback]) => {
        callbacks[key] = function (...args) {
          const value = callback.apply(this, args);
          if (language !== 'en') return value;
          return Array.isArray(value) ? value.map(item => translate(item)) : translate(value);
        };
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
    installSwitch();
    updateSwitch();
    requestAnimationFrame(applyCharts);
    observer.observe(document.documentElement, {subtree:true, childList:true, characterData:true, attributes:true, attributeFilter:['aria-label','title','placeholder']});
  });
  setLanguage(language);
  window.__CROP_KDS_I18N__ = Object.freeze({get language(){return language;}, setLanguage, translate, applyCharts});
})();
