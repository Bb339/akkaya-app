(function () {
  'use strict';

  const STORAGE_KEY = 'crop_kds_paper_language';
  const supported = new Set(['tr', 'en']);
  const originalText = new WeakMap();
  const originalAttributes = new WeakMap();
  const originalCharts = new WeakMap();
  let language = 'tr';
  let observer = null;
  let placementObserver = null;

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
    'Otoritatif değer': 'Authoritative Value',
    'PROJECT DATA · BAĞLAM GEÇERSİZ': 'PROJECT DATA · INVALID CONTEXT',
    'CSV bağlanmadı': 'CSV Not Connected',
    'Genel Baraj ve Havza Özeti': 'Overall Reservoir and Basin Summary',
    'Analysis Unit Özeti': 'Analysis Unit Summary',
    'Selected analysis unitin özeti': 'Selected Analysis Unit Summary',
    'KRİTİK': 'CRITICAL',
    'Akkaya Sulama Alanı Kuraklık ve Su Bütçesi Göstergeleri (2000-2025)': 'Akkaya Irrigation Area Drought and Water-Budget Indicators (2000–2025)',
    'Grafik üzerinde gezerek yıllık değerleri görebilirsiniz. Selected "Su yılı" vurgulanır; kritik yıllarda panel dikkat çekici biçimde öne çıkar.': 'Hover over the chart to view annual values. The selected water year is highlighted; the panel is emphasized in critical years.',
    'Kuraklık Alarmı': 'Drought Alert',
    'İpucu: Grafikteki noktalara gelerek yıllık değerleri görebilirsiniz.': 'Tip: Hover over chart points to view annual values.',
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
    'Lisansüstü tez prototipi': 'Graduate Thesis Prototype',
    'Disiplinlerarası Dijital Tarım Anabilim Dalı': 'Interdisciplinary Digital Agriculture Graduate Program',
    'Bir havzada yıllık su miktarına göre optimum bitki deseni sisteminin geliştirilmesi': 'Development of an Optimal Cropping Pattern System Based on Annual Water Availability in a Basin',
    'Bu giriş paneli, tez kapsamında geliştirilen karar destek sistemini akademik, kurumsal ve anlaşılır bir arayüzle sunar. Sistem; çiftçi kullanıcıları için parsel bazlı öneri ekranlarına, kurum kullanıcıları için ise havza ölçeğinde analiz, karşılaştırma ve izleme panellerine dönüşür.': 'This sign-in page presents the decision support system developed as part of the thesis through a clear academic and institutional interface. The system provides parcel-level recommendation views for farmers and basin-scale analysis, comparison, and monitoring dashboards for institutional users.',
    'Çiftçi paneli': 'Farmer Dashboard',
    'Kurum paneli': 'Institutional Dashboard',
    'Karar çıktıları': 'Decision Outputs',
    'Kendi parselleri, mevcut ürün bilgisi, önerilen desen, su tasarrufu ve gelir etkisi.': 'Their own parcels, current crop information, recommended pattern, water savings, and income impact.',
    'Havza geneli harita, senaryo karşılaştırması, su bütçesi ve uzun vadeli etki analizleri.': 'Basin-wide map, scenario comparison, water budget, and long-term impact analyses.',
    'Su kısıtı altında optimum bitki deseni, ekonomik etki ve uygulanabilir önerilerin birlikte sunulması.': 'A combined presentation of the optimal cropping pattern under water constraints, its economic impact, and actionable recommendations.',
    'Sisteme erişim': 'System Access',
    'Yönetim tarafından açılan hesabınızla giriş yapın': 'Sign in with the account created by the administration',
    'Bu prototipte açık kayıt yerine': 'This prototype uses',
    'kurumsal ön kayıt': 'institutional preregistration',
    'akışı kullanılır. Çiftçi hesapları yönetim panelinde açılır; kullanıcı ilk girişte bilgi tamamlama adımını tamamlayarak kendi paneline geçer.': 'instead of open registration. Farmer accounts are created in the administration dashboard; on first sign-in, the user completes the required profile information before entering their dashboard.',
    'Giriş ve bilgilendirme sekmeleri': 'Sign-in and information tabs',
    'Çiftçi demo (aktif)': 'Farmer Demo (Active)',
    'Çiftçi demo (ilk kurulum)': 'Farmer Demo (Initial Setup)',
    'Her girişte doğrulama ekranı yeniden açılır': 'The verification screen opens again at every sign-in',
    'Kurum demo (yönetici)': 'Institution Demo (Administrator)',
    'Kurum demo (uzman)': 'Institution Demo (Specialist)',
    'Kullanıcı adı': 'Username',
    'Örn. betul.demir': 'e.g., betul.demir',
    'Şifre': 'Password',
    'Bu sürümde açık kayıt yok': 'Open registration is unavailable in this version',
    'Çiftçi hesapları yönetim tarafından tek tek açılır. Böylece her kullanıcı için önceden kullanıcı adı, geçici şifre, varsa resmi parseller ve yetkiler tanımlanabilir.': 'Farmer accounts are created individually by the administration. This allows a username, temporary password, official parcels when available, and permissions to be defined in advance for each user.',
    '1. Yönetim ön kayıt açar': '1. Administration creates a preregistration',
    'Çiftçi bilgileri, kullanıcı adı, geçici şifre ve varsa çizili arazi kaydı tanımlanır.': 'Farmer details, username, temporary password, and any mapped land records are defined.',
    '2. Çiftçi ilk giriş yapar': '2. Farmer signs in for the first time',
    'Kullanıcı kendisine verilen bilgilerle giriş yapar ve ana panele geçmeden önce bilgi tamamlama ekranını görür.': 'The user signs in with the credentials provided and sees the profile completion screen before entering the main dashboard.',
    '3. Bilgi tamamlama yapılır': '3. Required information is completed',
    'Çiftçi iletişim bilgilerini doğrular; eksikse parsel yükler, haritada çizer veya mevcut kayıtlarını kontrol eder.': 'The farmer verifies their contact details and, if needed, uploads parcels, draws them on the map, or reviews existing records.',
    '4. Çiftçi paneli aktif olur': '4. Farmer dashboard is activated',
    'Kurulum tamamlanınca kullanıcı kendi bitki deseni planı, su ve kâr karşılaştırmalarını görür.': 'After setup is complete, the user can view their cropping pattern plan and water and profit comparisons.',
    'Bu ekran tez sunumu için hazırlanmış prototip girişidir. Açık kayıt yerine yönetim ön kayıt + çiftçi ilk kurulum + rol bazlı parsel yetkilendirme mantığı gösterilmektedir.': 'This is a prototype sign-in screen prepared for the thesis presentation. It demonstrates administration-led preregistration, farmer initial setup, and role-based parcel authorization instead of open registration.',
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
    ,'Aday kapsamı': 'Candidate Coverage'
    ,'Aç / kapa': 'Expand / Collapse'
    ,'Tamamlandı': 'Completed'
    ,'Manuel yüklenen CSV/GeoJSON dosyaları bu oturumda aktif analize alınır ve optimizasyon yerel hesap motoruyla yeniden çalışır. Kalıcı kurumsal kullanım ve Python backend çıktısı için aynı dosyalar backend/data klasörüne aktarılmalıdır.': 'Manually uploaded CSV/GeoJSON files are included in the active analysis for this session, and optimization is rerun with the local computation engine. For persistent institutional use and Python backend output, transfer the same files to the backend/data directory.'
    ,'Henüz manuel dosya seçilmedi.': 'No manual files have been selected.'
    ,'Dosya seçildiğinde satır, kolon, parsel eşleşmesi ve aktif analize katılım durumu burada gösterilir.': 'After a file is selected, its rows, columns, parcel matching, and active-analysis inclusion status are shown here.'
    ,'Dosya seçildiğinde satır, kolon, analiz birimi eşleşmesi ve aktif analize katılım durumu burada gösterilir.': 'After a file is selected, its rows, columns, analysis-unit matching, and active-analysis inclusion status are shown here.'
    ,'Yapay Arı Kolonisi Algoritması (ABC)': 'Artificial Bee Colony Algorithm (ABC)'
    ,'Karınca Koloni Optimizasyonu (ACO)': 'Ant Colony Optimization (ACO)'
    ,'Senaryo 1 - Tek ürünlü parsel (en iyi 1-2 ürün + alternatifler)': 'Scenario 1 – Single-Crop Parcel (Best 1–2 Crops + Alternatives)'
    ,'Senaryo 2 - Çift ürünlü / desen bazlı parsel (1+1 ürün / bahçede sıra arası)': 'Scenario 2 – Two-Crop / Pattern-Based Parcel (1+1 Crop / Orchard Inter-Row)'
    ,'Senaryo 1 - Tek ürünlü analiz birimi (en iyi 1-2 ürün + alternatifler)': 'Scenario 1 – Single-Crop Analysis Unit (Best 1–2 Crops + Alternatives)'
    ,'Senaryo 2 - Çift ürünlü / desen bazlı analiz birimi (1+1 ürün / bahçede sıra arası)': 'Scenario 2 – Two-Crop / Pattern-Based Analysis Unit (1+1 Crop / Orchard Inter-Row)'
    ,'Plan yılı': 'Planning Year'
    ,'Korundu; çizim modunda ayrı sekmeden açılır': 'Retained; opens in a separate tab in drawing mode'
    ,'İlçe': 'District'
    ,'Çiftçi': 'Farmer'
    ,'bütçe durumu: -': 'budget status: –'
    ,'Havza genel referansı': 'Basin-Wide Reference'
    ,'Rotasyon / 2. Ürün Önerisi (basit kurallar)': 'Rotation / Secondary-Crop Recommendation (Rule-Based)'
    ,'Suyunu koruyamayan bir tarım, toprağını; toprağını koruyamayan bir millet, geleceğini kaybeder.': 'Agriculture that cannot protect its water loses its soil; a nation that cannot protect its soil loses its future.'
    ,'Hazırlayan: Betül Demir • Yüksek Lisans Tezi': 'Prepared by: Betül Demir • Master’s Thesis'
    ,'Ziraat Marşı': 'Agricultural March'
    ,'GENEL': 'GENERAL'
    ,'GÖRÜNÜM': 'OVERVIEW'
    ,'Genel görünüm': 'Overview'
    ,'tamamlayıcı': 'Complementary Crop'
    ,'tamamlayıcı · SECONDARY': 'Complementary Crop · SECONDARY'
    ,'Arayüz yalnız backend sözleşmelerini gösterir; bilimsel değerleri yeniden hesaplamaz.': 'The interface only presents backend contracts; it does not recalculate scientific values.'
    ,'Kurum belirtilmedi': 'Institution Not Specified'
    ,'Bölge belirtilmedi': 'Region Not Specified'
    ,'Proje açıklaması girilmedi.': 'No project description was provided.'
    ,'Bütçe türü': 'Budget Type'
    ,'Ekonomi kapsamı': 'Economics Coverage'
    ,'Aday birim kapsamı': 'Candidate-Unit Coverage'
    ,'Seçim, bütünlük, geçerlilik ve motor bağlantısı ayrı değerlendirilir.': 'Selection, integrity, validity, and engine connectivity are assessed separately.'
    ,'Aktif sürüm seçilmedi': 'No Active Version Selected'
    ,'CSV / XLSX / GeoJSON dosyaları': 'CSV / XLSX / GeoJSON Files'
    ,'Doğrula ve önizle': 'Validate and Preview'
    ,'Dosya yükle': 'Upload File'
    ,'Sütun eşleştir': 'Map Columns'
    ,'Doğrula': 'Validate'
    ,'Önizle': 'Preview'
    ,'Aktif sürüm': 'Active Version'
    ,'Açık bilimsel aday ve sezon girdileri': 'Explicit Scientific Candidate and Seasonal Inputs'
    ,'Aktarım kayıtları': 'Import Records'
    ,'Ekonomi': 'Economics'
    ,'Senaryo ve makine durumları': 'Scenario and Machine Statuses'
    ,'REFERENCE DEMO · model gösterimi': 'REFERENCE DEMO · model demonstration'
    ,'REFERENCE DEMO — model gösterimi': 'REFERENCE DEMO — model demonstration'
    ,'Resmî kurum verileri gelmeden önce eğitim, ekran görüntüsü ve bilimsel model gösterimi için kullanılabilir.': 'May be used for training, screenshots, and scientific model demonstration before official institutional data are available.'
    ,'ACO · Karınca Kolonisi Optimizasyonu': 'ACO · Ant Colony Optimization'
    ,'ACO — Karınca Kolonisi Optimizasyonu': 'ACO — Ant Colony Optimization'
    ,'ABC · Yapay Arı Kolonisi': 'ABC · Artificial Bee Colony'
    ,'ABC — Yapay Arı Kolonisi': 'ABC — Artificial Bee Colony'
    ,'Üretilmedi': 'Not Produced'
    ,'yıl yok': 'year unavailable'
    ,'kapsam yok': 'scope unavailable'
    ,'otorite yok': 'authority unavailable'
    ,'yok': 'none'
    ,'Motor bu metrik için değer üretmedi': 'The engine did not produce a value for this metric'
    ,'DIAGNOSTIC / UYGULANABİLİR PLAN DEĞİL': 'DIAGNOSTIC / NOT A FEASIBLE PLAN'
    ,'HHI 0,221 · ORTA YOĞUNLAŞMA': 'HHI 0.221 · MODERATE CONCENTRATION'
    ,'TEŞHİS': 'DIAGNOSTIC'
    ,'DIAGNOSTIC / ÖNERİ DEĞİL': 'DIAGNOSTIC / NOT A RECOMMENDATION'
    ,'İkinci': 'Secondary'
    ,'DIAGNOSTIC / UYGULANABİLİR ÖNERİ DEĞİL': 'DIAGNOSTIC / NOT A FEASIBLE RECOMMENDATION'
    ,'Eksik sunum metadatası': 'Missing Presentation Metadata'
    ,'Eski input snapshotına sabitlenmiş': 'Pinned to an Older Input Snapshot'
    ,'Revision ilişkisi': 'Revision Relationship'
    ,'Sınıflandırma': 'Classification'
    ,'Analiz birimleri / analiz birimleri': 'Analysis Units / Analysis Units'
    ,'REQUIRED · Analiz birimleri sağlandı.': 'REQUIRED · Analysis units provided.'
    ,'REQUIRED · Veri doğrulandı ve yürütme sözleşmesine bağlı.': 'REQUIRED · Data validated and bound to the execution contract.'
    ,'Aylık teslim kapasitesi': 'Monthly Delivery Capacity'
    ,'OPTIONAL · Bu veri seçilen senaryoda zorunlu değil.': 'OPTIONAL · This dataset is not required for the selected scenario.'
    ,'Mevcut crop deseni': 'Current Cropping Pattern'
    ,'Harita geometrisi': 'Map Geometry'
    ,'OPTIONAL · Harita geometrisi sağlandı.': 'OPTIONAL · Map geometry provided.'
    ,'Kaçın / azalt': 'Avoid / Reduce'
    ,'NOT PROVIDED · proje paketi kuraklık gösterge serisi içermiyor; Akkaya reference verisi kullanılmadı.': 'NOT PROVIDED · The project package does not include a drought-indicator series; Akkaya reference data were not used.'
    ,'NOT PROVIDED — proje paketi kuraklık gösterge serisi içermiyor; Akkaya reference verisi kullanılmadı.': 'NOT PROVIDED — The project package does not include a drought-indicator series; Akkaya reference data were not used.'
    ,'Tarayıcınız ses oynatmayı desteklemiyor.': 'Your browser does not support audio playback.'
    ,'Parcel seç': 'Select Parcel'
    ,'Parcel Haritası': 'Parcel Map'
    ,'Parcel çizim ve bilgi atama': 'Parcel Geometry and Information Assignment'
    ,'Parcel özeti': 'Parcel Summary'
    ,'Tercih et': 'Prefer'
    ,'Henüz sürümlenmiş kurumsal veri yok.': 'No versioned institutional data are available yet.'
    ,'Henüz sürümlenmiş kurumsal veri none.': 'No versioned institutional data are available yet.'
    ,'Tür': 'Type'
    ,'Dosya': 'File'
    ,'Algılanan alan': 'Detected Domain'
    ,'Yıl': 'Year'
    ,'Kapsam': 'Scope'
    ,'Satır': 'Rows'
    ,'Eşleşme': 'Match'
    ,'Doğrulama': 'Validation'
    ,'Dosya önizlemesi': 'File Preview'
    ,'Seçilen sayfa': 'Selected Sheet'
    ,'Sayfalar': 'Sheets'
    ,'Sütunlar': 'Columns'
    ,'İlk satırlar': 'First Rows'
    ,'Önerilen eşleşme': 'Suggested Mapping'
    ,'Recommended eşleşme': 'Suggested Mapping'
    ,'Türkçe kullanıcı yönlendirmesi': 'User Guidance'
    ,'Dosya otomatik olarak uygulanamadı.': 'The file could not be applied automatically.'
    ,'Teknik ayrıntıdaki hata kodunu inceleyin ve dosyayı onaylamadan önce düzeltin.': 'Review the error code in the technical details and correct the file before approval.'
    ,'Teknik ayrıntı': 'Technical Details'
    ,'Ham önizleme JSON': 'Raw Preview JSON'
    ,'Açıkça onayla ve projeye uygula': 'Explicitly Confirm and Apply to Project'
    ,'Birim × ürün adayları, iklim ve mevcut desen girdileri. Yalnız proje kapsamındaki doğrulanmış JSON kullanılmalıdır.': 'Analysis-unit × crop candidates, climate data, and current-pattern inputs. Use only verified JSON within the project scope.'
    ,'Analiz birimi bulunmuyor; alan ve mevcut ürün verisi yükleyin.': 'No analysis units are available; upload analysis-unit area and current-crop data.'
    ,'Miktarı ve türü belirlenmiş su bütçesi gerekli.': 'A water budget with a specified amount and type is required.'
    ,'Birim × ürün düzeyinde açık aday su/kâr verileri gerekli; otomatik değer üretilmez.': 'Explicit candidate water/profit data are required at analysis-unit × crop level; values are not generated automatically.'
    ,'S2 için ürün aileleri ve rotasyon kısıtları gerekli.': 'Crop families and rotation constraints are required for S2.'
    ,'Veri hazırlık rehberi': 'Data Readiness Guide'
    ,'Durumlar backend readiness raporundan türetilir. Geometri analiz için isteğe bağlı, proje haritası için önerilir.': 'Statuses are derived from the backend readiness report. Geometry is optional for analysis and recommended for the project map.'
    ,'Beklenen: İlgili veri şablonundaki zorunlu alanlar': 'Expected: Required fields from the relevant data template'
    ,'Henüz analiz çalışması yok.': 'No analysis runs yet.'
    ,'Harita geometrisindeki birim kimliği proje analiz birimleriyle eşleşmiyor.': 'A unit identifier in the map geometry does not match the project analysis units.'
    ,'Geometri dosyasındaki kimlikleri analiz birimi dosyasıyla karşılaştırın.': 'Compare the identifiers in the geometry file with the analysis-unit file.'
    ,'Yıllık su arzı': 'Annual Water Supply'
    ,'Sürüm': 'Version'
    ,'Seçim': 'Selection'
    ,'Kayıt': 'Record'
    ,'AKTİF': 'ACTIVE'
    ,'Virgül/nokta biçimini ve sayı alanlarında metin içeren hücreleri kontrol edin.': 'Check decimal separators and cells containing text in numeric fields.'
    ,'Yıl değerini 2025 gibi dört haneli bir sayı olarak girin.': 'Enter the year as a four-digit number such as 2025.'
    ,'Doğru planlama yılına ait dosyayı yükleyin veya proje yılını doğrulayın.': 'Upload the file for the correct planning year or verify the project year.'
    ,'Dosya kapsamını proje/bölge kimliğiyle aynı olacak şekilde kontrol edin.': 'Ensure the file scope matches the project/region identifier.'
    ,'Önerilen sütun eşleştirmelerini inceleyip doğru canonical alanı seçin.': 'Review the suggested column mappings and select the correct canonical field.'
    ,'Sistem bu dosyanın hangi veri türüne ait olduğunu güvenle belirleyemedi.': 'The system could not reliably determine the data type of this file.'
    ,'Çalışma kitabında aynı derecede uygun birden fazla sayfa bulundu.': 'Multiple equally suitable sheets were found in the workbook.'
    ,'Bu dosya türü desteklenmiyor.': 'This file type is not supported.'
    ,'Desteklenen biçimler: CSV, XLSX, GeoJSON.': 'Supported formats: CSV, XLSX, and GeoJSON.'
    ,'Dosya güvenli biçimde okunamadı.': 'The file could not be read safely.'
    ,'GeoJSON geometrilerini ve analysis_unit_id eşleşmesini kontrol edin.': 'Check the GeoJSON geometries and analysis_unit_id matching.'
    ,'Dosya biçimini, karakter kodlamasını ve tablo yapısını kontrol edin.': 'Check the file format, character encoding, and table structure.'
    ,'Bu dosyada desteklenen bir veri alanına ait güvenilir yapısal kanıt bulunmadı.': 'No reliable structural evidence for a supported data domain was found in this file.'
    ,'Dosya projeye uygulanmadı ve eksiksiz bir paketin aktivasyonunu engellemez. Dosya aslında proje verisiyse doğru şablonu ve zorunlu sütunları kullanın.': 'The file was not applied to the project and does not block activation of a complete package. If it is project data, use the correct template and required columns.'
    ,'Coğrafi veri geometrisi geçersiz.': 'The geospatial geometry is invalid.'
    ,'GeoJSON koordinatlarını, geometri tipini ve kapalı poligon halkalarını kontrol edin.': 'Check the GeoJSON coordinates, geometry type, and closed polygon rings.'
    ,'Aynı geometri birden fazla analiz birimine atanmış.': 'The same geometry is assigned to multiple analysis units.'
    ,'Her geometrinin tek bir analysis_unit_id ile eşleştiğini doğrulayın.': 'Verify that each geometry matches exactly one analysis_unit_id.'
    ,'Miktar (m³)': 'Amount (m³)'
    ,'Kaydet': 'Save'
    ,'Onayla': 'Approve'
    ,'Dosyaları Seç': 'Choose Files'
    ,'Dosya Seç': 'Choose File'
    ,'Dosya seçilmedi': 'No file selected'
    ,'Dosya Önizlemesi': 'File Preview'
    ,'Otomatik eşleşti; açık onay bekleniyor.': 'Automatically matched; explicit confirmation is pending.'
    ,'Uzman ve kurum yazışma akışı': 'Expert and Institutional Correspondence'
    ,'Çiftçi alternatif talepleri, yazışmalar, onay/revizyon/iptal kararları bu sekmede tutulur.': 'Farmer alternative requests, correspondence, and approval/revision/cancellation decisions are managed in this tab.'
    ,'Kurum gelen talepler / yazışma': 'Incoming Institutional Requests / Correspondence'
    ,'Görülenleri okundu say': 'Mark Viewed as Read'
    ,'Okunan bildirimleri temizle': 'Clear Read Notifications'
    ,'Tüm bildirimleri temizle': 'Clear All Notifications'
    ,'Gelen mesajlar / yazışma': 'Incoming Messages / Correspondence'
    ,'Seçilen alternatif:': 'Selected Alternative:'
    ,'Revizyon iste': 'Request Revision'
    ,'İptal / reddet': 'Cancel / Reject'
    ,'Sil': 'Delete'
    ,'Mesaj gönder': 'Send Message'
    ,'Bekleyen talep yok.': 'No Pending Requests.'
    ,'Gelen mesaj yok.': 'No Incoming Messages.'
    ,'Bu konuşma için mesaj geçmişi yok.': 'No message history exists for this conversation.'
    ,'Detayı görmek için talep veya mesaj seçin.': 'Select a request or message to view details.'
    ,'Çiftçiye yanıt / revizyon açıklaması yazın': 'Write a reply / revision explanation to the farmer'
    ,'Alternatif talebi': 'Alternative Request'
    ,'Mesaj': 'Message'
    ,'Sistem': 'System'
    ,'Kullanıcı': 'User'
    ,'çiftçi': 'farmer'
    ,'Çiftçi': 'Farmer'
    ,'Parsel bildirimi': 'Parcel Notification'
    ,'Parsel düzeltme / çizim talebi': 'Parcel Correction / Drawing Request'
    ,'Çiftçiden gelen alternatif onay talebi': 'Alternative Approval Request from Farmer'
    ,'Çiftçi bu alternatifi uzman onayı için seçti.': 'The farmer selected this alternative for expert approval.'
    ,'PROJECT DATA geometrileri yüklenen proje dosyalarından gelir. Bu çalışma alanı geometriyi değiştirmeden gösterir; ekleme veya düzeltme için Projeler → Veri Yönetimi alanını kullanın.': 'PROJECT DATA geometries are loaded from the uploaded project files. This run view displays the geometry without modifying it; use Projects → Data Management to add or correct geometry.'
    ,'Resmî parsel kaydını seçip sınır çizimi, GeoJSON/KML yükleme, çiftçi ataması ve seçilen alternatif desen kaydını bu çalışma alanından yönetin. Sol panel yalnız analiz kurulumu ve hızlı özet için sade bırakıldı.': 'Select the official parcel record to manage boundary drawing, GeoJSON/KML upload, farmer assignment, and the selected alternative cropping-pattern record. The left panel remains simplified for analysis setup and quick summary.'
    ,'İlçe / köy düzeyi karar özeti': 'District / Village-Level Decision Summary'
    ,'Bu bölüm artık temsili sabit grafik yerine seçili kapsamdan hesaplanan gerçek özetleri gösterir. Amaç; hangi köyde ne kadar alan, mevcut ve önerilen su/kâr farkı ve su tahsis baskısı olduğunu ilk bakışta anlaşılır biçimde sunmaktır.': 'This section presents actual summaries calculated from the selected scope instead of representative fixed charts. It shows each village’s area, current and recommended water/profit differences, and water-allocation pressure at a glance.'
    ,'Köy bazında toplam alan ve parsel sayısı': 'Total Area and Parcel Count by Village'
    ,'Köy bazında mevcut ve önerilen toplam su': 'Current and Recommended Total Water by Village'
    ,'Köy bazında mevcut ve önerilen net kâr': 'Current and Recommended Net Profit by Village'
    ,'Havza Su Bütçesi - Resmî Özet': 'Basin Water Budget — Official Summary'
    ,'Planlama su bütçesi, 2024 mevcut ürün deseninden hesaplanan toplam sulama suyu talebi referans alınarak tanımlanmıştır. Su yılı seçimi kuraklık ve gösterge panellerinde bağlamsal analiz için kullanılır.': 'The planning water budget is defined using total irrigation-water demand calculated from the 2024 current cropping pattern. The water-year selection provides context for drought and indicator panels.'
    ,'Gösterge': 'Indicator'
    ,'Değer': 'Value'
    ,'Birim': 'Unit'
    ,'CSV indir': 'Download CSV'
    ,'Seçili Senaryoya Göre Optimum Bitki Deseni - Resmî': 'Optimal Crop Pattern for the Selected Scenario — Official'
    ,'Seçili kapsam / 5 köy parselleri için ürün bazında ekim alanı (sezon/dönem bazında), su ve kâr toplulaştırması. Rotasyon/2. ürün varsa aynı parsel alanı yıl içinde birden fazla ürünle değerlendirilebilir.': 'Crop-level planted-area, water, and profit aggregation by season/period for the selected scope across five villages. With rotation/secondary crops, the same parcel area may support more than one crop during the year.'
    ,'Ekim Alanı (da - sezon)': 'Planted Area (da – season)'
    ,'Toplam Su (m³)': 'Total Water (m³)'
    ,'Toplam Kâr (TL)': 'Total Net Profit (TRY)'
    ,'Su Verimliliği (TL/m³)': 'Water Productivity (TRY/m³)'
    ,'Parsel Bazlı Özet - Resmî': 'Parcel Summary — Official'
    ,'Her parsel için seçili senaryo+algoritma sonucunun su/kâr özeti (küresel su bütçesi sonrası).': 'Water/profit summary of the selected scenario and algorithm result for each parcel after the global water budget is applied.'
    ,'Not: Bu tablolar, rapora doğrudan eklenebilir/Excel\'e aktarılabilir formatta üretilir.': 'Note: These tables are produced in a format suitable for direct report inclusion or Excel export.'
    ,'Tüm Parseller - Mevcut vs Önerilen (Şeffaf Karşılaştırma)': 'All Parcels — Current vs Recommended (Transparent Comparison)'
    ,'Çiftçi için: Her parselde mevcut ekim deseni ile seçili senaryo+algoritma sonucu önerilen desen yan yana. Her parsel satırında "Kıyasla" ile alternatif ürünlerin su/kâr karşılaştırması görülebilir.': 'For farmers: the current cropping pattern and the pattern recommended by the selected scenario and algorithm are shown side by side for each parcel. Use Compare in each row to view water/profit comparisons for alternative crops.'
    ,'Not: Öneriler, son "Optimizasyonu Çalıştır" sonucuyla senkron tutulur.': 'Note: Recommendations remain synchronized with the latest Run Optimization result.'
    ,'Mevcut Desen (mevsim)': 'Current Pattern (season)'
    ,'Mevcut Su (m³)': 'Current Water (m³)'
    ,'Mevcut Kâr (TL)': 'Current Net Profit (TRY)'
    ,'Önerilen Desen (mevsim)': 'Recommended Pattern (season)'
    ,'Öneri Su (m³)': 'Recommended Water (m³)'
    ,'Öneri Kâr (TL)': 'Recommended Net Profit (TRY)'
    ,'Neden?': 'Why?'
    ,'Köy / İlçe bazlı resmî ekim desenleri (paketten özet)': 'Official Village / District Cropping Patterns (Package Summary)'
    ,'Bu bölüm, veri paketindeki Excel tablolarından türetilen özetleri gösterir (kullanılan bonuslar buradan gelir).': 'This section presents summaries derived from the Excel tables in the data package; the applied bonuses originate here.'
    ,'Benchmark sekmesi yüklendi.': 'Benchmark Tab Loaded.'
    ,'Bu bölüm yalnızca backend benchmark sonucunu kullanır. Aynı veri, aynı su bütçesi ve aynı tekrar sayısı altında GA/ABC/ACO algoritmalarının ortalama-medyan-min/max-oynaklık-uygulanabilir çözüm oranı ve süre metrikleri birlikte raporlanır.': 'This section uses only the backend benchmark result. Under the same data, water budget, and repeat count, it jointly reports mean, median, minimum/maximum, variability, feasible-solution rate, and runtime metrics for GA/ABC/ACO.'
    ,'Karşılaştırma senaryosu': 'Comparison Scenario'
    ,'Seçili (soldaki Sezon veri seti)': 'Selected (Season Dataset on the Left)'
    ,'Senaryo-1 (tek ürün)': 'Scenario 1 (Single Crop)'
    ,'Senaryo-2 (çift ürün / desen)': 'Scenario 2 (Two Crops / Pattern)'
    ,'İkisini de çalıştır (karşılaştır)': 'Run Both (Compare)'
    ,'Benchmark modu': 'Benchmark Mode'
    ,'Detaylı / akademik karşılaştırma': 'Detailed / Academic Comparison'
    ,'Hızlı ön izleme': 'Quick Preview'
    ,'Tekrar sayısı': 'Repeat Count'
    ,'Seed (opsiyonel)': 'Seed (Optional)'
    ,'boş = rastgele': 'blank = random'
    ,'Karşılaştırmayı Çalıştır': 'Run Comparison'
    ,'Tekrar sayısı kararlılık analizi': 'Repeat-Count Stability Analysis'
    ,'En uygun tekrar sayısı yalnızca en yüksek tekil sonuca göre değil; çözüm kararlılığı, uygulanabilirlik oranı, marjinal iyileşme ve çalışma süresi birlikte değerlendirilerek seçilir.': 'The most suitable repeat count is selected by jointly evaluating solution stability, feasibility rate, marginal improvement, and runtime rather than only the highest single result.'
    ,'GA, ACO ve ABC stokastik/sezgisel algoritmalar olduğundan tek koşu yerine bağımsız tekrarlar üzerinden değerlendirilmiştir. Varsayılan 30 koşu, ortalama performans ve kararlılık göstergelerinin hesaplanabilmesi için kullanılır. 50 ve 100 koşu seçenekleri ek kararlılık analizi amacı taşır.': 'Because GA, ACO, and ABC are stochastic/heuristic algorithms, they are evaluated over independent repeats instead of a single run. The default 30 runs support calculation of average performance and stability indicators; 50 and 100 runs provide additional stability analysis.'
    ,'Kurum görünümünde hedef modu × algoritma karşılaştırma özeti burada gösterilir.': 'The objective-mode × algorithm comparison summary is shown here in the institutional view.'
    ,'Net kâr dağılımı (ort / min / max)': 'Net Profit Distribution (mean / min / max)'
    ,'Toplam su dağılımı (ort / min / max)': 'Total Water Distribution (mean / min / max)'
    ,'Algoritma kalite profili (TL/m³ - uygulanabilirlik - plan farkı)': 'Algorithm Quality Profile (TRY/m³ – feasibility – plan difference)'
    ,'Sure - oynaklik - desen cesitliligi profili': 'Runtime – Variability – Pattern Diversity Profile'
    ,'UYGULANAMAZ / NOT APPLICABLE — S1 tek sezon bağlamı.': 'NOT APPLICABLE — S1 single-season context.'
    ,'Analiz Birimi Özeti - Resmî': 'Analysis-Unit Summary — Official'
    ,'Tüm seçili parseller': 'All Selected Parcels'
    ,'Tüm seçili analiz birimleri': 'All Selected Analysis Units'
    ,'Seçili kapsam:': 'Selected Scope:'
    ,'Hedef:': 'Objective:'
    ,'Köy özeti': 'Village Summary'
    ,'İlçe özeti': 'District Summary'
    ,'Not': 'Note'
    ,'Bu tablolar yalnızca seçili kapsamdan hesaplanır. Tek parsel seçiliyse tüm ilçe toplamı değil, o parselin ait olduğu kapsam görünür. Böylece NaN ve yanıltıcı toplamlar oluşmaz.': 'These tables are calculated only from the selected scope. When one parcel is selected, its scope is shown instead of the entire district total, preventing NaN values and misleading totals.'
    ,'Bu tablolar yalnızca seçili kapsamdan hesaplanır. Tek analiz birimi seçiliyse tüm ilçe toplamı değil, o analiz biriminin ait olduğu kapsam görünür. Böylece NaN ve yanıltıcı toplamlar oluşmaz.': 'These tables are calculated only from the selected scope. When one analysis unit is selected, its scope is shown instead of the entire district total, preventing NaN values and misleading totals.'
    ,'Bilinmeyen köy': 'Unknown Village'
    ,'Seçili köy': 'Selected Villages'
    ,'Kapsamda özetlenen yerleşim adedi': 'Settlements Summarized in Scope'
    ,'Toplam alan': 'Total Area'
    ,'Seçili kapsamın toplam ekili alanı': 'Total Planted Area in the Selected Scope'
    ,'Öneri su farkı': 'Recommended Water Difference'
    ,'Mevcut desene göre toplam fark': 'Total Difference from Current Pattern'
    ,'Karar özeti:': 'Decision Summary:'
    ,'Kapsam': 'Scope'
    ,'Seçili plan yılı': 'Selected Planning Year'
    ,'Kapsam kullanılabilir su': 'Available Water for Scope'
    ,'Önerilen toplam talep': 'Total Recommended Demand'
    ,'Su dengesi (kalan / açık)': 'Water Balance (remaining / deficit)'
    ,'Su durumu': 'Water Status'
    ,'Uygun': 'Compliant'
    ,'Aşım': 'Exceeded'
    ,'yıl': 'year'
    ,'Toplam:': 'Total:'
    ,'alan': 'area'
    ,'su': 'water'
    ,'kâr': 'net profit'
    ,'Mevcut desen': 'Current Pattern'
    ,'Su Tasarrufu': 'Water Saving'
    ,'Kâr': 'Profit'
    ,'Su Etkin Kullanım': 'Water-Use Efficiency'
    ,'Hazır': 'Ready'
    ,'NOT APPLICABLE — S1 tek sezon bağlamı': 'NOT APPLICABLE — S1 single-season context'
    ,'UYGULANMAZ': 'NOT APPLICABLE'
    ,'Bilimsel girdileri kaydet': 'Save Scientific Inputs'
    ,'Algoritma karşılaştırması (Benchmark)': 'Algorithm Comparison (Benchmark)'
    ,'Bu bölüm yalnızca': 'This section uses only the'
    ,'Proje planning-year water': 'Project Planning-Year Water'
    ,'Proje su bütçesi': 'Project Water Budget'
    ,'Mevcut desen suyu': 'Current Cropping-Pattern Water'
    ,'Yıllık bütçe durumu': 'Annual Budget Status'
    ,'durum': 'status'
    ,'PROJECT DATA · backend-authoritative proje ve saklanmış run değerleri': 'PROJECT DATA · Backend-Authoritative Project and Stored-Run Values'
  }));

  function isProjectDataProvider() {
    return window.__V1_PROJECT_PROVIDER__?.provider === 'PROJECT_DATA' ||
      new URLSearchParams(location.search).get('provider') === 'PROJECT_DATA';
  }

  const providerNoun = (parcelText, unitText) => isProjectDataProvider() ? unitText : parcelText;

  // Canonical application labels that are generated by the V1 renderers at runtime.
  // Unicode escapes keep these keys stable across Windows source encodings.
  [
    ['Senaryo, su b\u00fct\u00e7esi ve etki analizi odakl\u0131 kurumsal g\u00f6r\u00fcn\u00fcm', 'Institutional view focused on scenarios, water budgets, and impact analysis'],
    ['Kurumsal analiz paneli', 'Institutional Analysis Panel'],
    ['Aktif hedef: Su etkin kullan\u0131m', 'Active objective: Water-Use Efficiency'],
    ['Aktif hedef: K\u00e2r odakl\u0131', 'Active objective: Profit Maximization'],
    ['Fark:', 'Difference:'],
    ['Genetik Algoritma (GA)', 'Genetic Algorithm (GA)'],
    ['Yapay Ar\u0131 Kolonisi Algoritmas\u0131 (ABC)', 'Artificial Bee Colony Algorithm (ABC)'],
    ['Kar\u0131nca Koloni Optimizasyonu (ACO)', 'Ant Colony Optimization (ACO)'],
    ['Senaryo tipi', 'Scenario Type'],
    ['Profil / Senaryo', 'Profile / Scenario'],
    ['Profil', 'Profile'],
    ['Engeller', 'Blocking Issues'],
    ['Senaryo ve makine durumlar\u0131', 'Scenario and Engine Status'],
    ['S1 \u2014 Tek \u00dcr\u00fcn Deseni', 'S1 \u2014 Single-Crop Pattern'],
    ['S2 \u2014 Mevsimsel / \u00c7oklu \u00dcr\u00fcn Senaryosu', 'S2 \u2014 Seasonal / Multi-Crop Scenario'],
    ['GA \u2014 Genetik Algoritma', 'GA \u2014 Genetic Algorithm'],
    ['ACO \u2014 Kar\u0131nca Kolonisi Optimizasyonu', 'ACO \u2014 Ant Colony Optimization'],
    ['ABC \u2014 Yapay Ar\u0131 Kolonisi', 'ABC \u2014 Artificial Bee Colony'],
    ['Senaryo de\u011fi\u015fti; yeni \u00f6nizleme gerekli.', 'Scenario changed; a new preview is required.'],
    ['\u00d6nerilen \u00dcr\u00fcn Deseni (Senaryo + Algoritma)', 'Recommended Cropping Pattern (Scenario + Algorithm)'],
    ['Otorite', 'Authority'],
    ['doluluk', 'storage level'],
    ['doluluk: -', 'storage level: -'],
    ['Min doluluk', 'Minimum Storage Level']
  ].forEach(([source, target]) => exact.set(source, target));

  const replacements = [
    [/^Across the region, (\d+) analysis unit i\u00e7in il\u00e7e \u00f6zeti, su b\u00fct\u00e7esi, algoritma kar\u015f\u0131la\u015ft\u0131rmalar\u0131 ve uzun vadeli etki ekranlar\u0131 \u00f6ne \u00e7\u0131kar\. Kullan\u0131c\u0131 a\u00e7ma \/ pasife alma gibi i\u015flemler y\u00f6netici hesab\u0131nda tutulur\.$/g, 'Across the region, $1 analysis units support district summaries, water-budget assessment, algorithm comparisons, and long-term impact views. User activation and deactivation remain under the administrator account.'],
    [/^B\u00f6lge genelindeki (\d+) analiz birimi i\u00e7in il\u00e7e \u00f6zeti, su b\u00fct\u00e7esi, algoritma kar\u015f\u0131la\u015ft\u0131rmalar\u0131 ve uzun vadeli etki ekranlar\u0131 \u00f6ne \u00e7\u0131kar\. Kullan\u0131c\u0131 a\u00e7ma \/ pasife alma gibi i\u015flemler y\u00f6netici hesab\u0131nda tutulur\.$/g, 'Across the region, $1 analysis units support district summaries, water-budget assessment, algorithm comparisons, and long-term impact views. User activation and deactivation remain under the administrator account.'],
    [/^Aktif hedef: K\u00e2r odakl\u0131$/g, 'Active objective: Profit Maximization'],
    [/^Aktif hedef: Su etkin kullan\u0131m$/g, 'Active objective: Water-Use Efficiency'],
    [/^Aktif hedef: (Su tasarrufu|K\u00e2r odakl\u0131|Su etkin kullan\u0131m) \u2022 Beklemede$/g, (_match, objective) => `Active objective: ${{'Su tasarrufu':'Water Saving','K\u00e2r odakl\u0131':'Profit Maximization','Su etkin kullan\u0131m':'Water-Use Efficiency'}[objective]} \u2022 Pending`],
    [/^Fark:\s*/g, 'Difference: '],
    [/(GA|ACO|ABC), (water_saving|max_profit|water_efficiency) hedefi alt\u0131nda project candidate matrix kullan\u0131larak \u00e7al\u0131\u015ft\u0131r\u0131ld\u0131\./g, (_match, algorithm, objective) => `${algorithm} was run using the project candidate matrix under the ${{water_saving:'Water Saving',max_profit:'Profit Maximization',water_efficiency:'Water-Use Efficiency'}[objective]} objective.`],
    [/^doluluk: (.+) \| baraj riski: (.+) \| plan riski: (.+)$/g, 'storage level: $1 | reservoir risk: $2 | plan risk: $3'],
    [/^doluluk:\s*(.+)$/g, 'storage level: $1'],
    [/^Ne oldu\? /g, 'What happened? '],
    [/^Ne yapmalısınız\? /g, 'What should you do? '],
    [/Zorunlu sütun bulunamadı/g, 'Required columns are missing'],
    [/Dosyanızdaki parsel\/birim kimliği ve diğer zorunlu sütunları kontrol edin veya sütun eşleştirme adımından doğru alanları seçin\./g, 'Check the parcel/unit identifier and other required columns in your file, or select the correct fields in the column-mapping step.'],
    [/Sayısal olması gereken (.+) okunamayan değer bulundu/g, 'An unreadable value was found in $1, which must be numeric'],
    [/Planlama yılı okunamadı/g, 'The planning year could not be read'],
    [/Dosyadaki planlama yılı proje yılıyla uyuşmuyor\. Proje yılı: (.+); dosya yılı: (.+)\./g, 'The planning year in the file does not match the project year. Project year: $1; file year: $2.'],
    [/Dosyanın coğrafi kapsamı projeyle uyuşmuyor: (.+)\./g, 'The geographic scope in the file does not match the project: $1.'],
    [/Bazı sütunlar birden fazla alana eşleşebilir/g, 'Some columns may match more than one field'],
    [/Olası türleri kontrol edin: (.+)\. İlgisiz ek dosyayı paketten çıkarın veya doğru veri dosyasını yükleyin\./g, 'Check the possible types: $1. Remove an unrelated attachment from the package or upload the correct data file.'],
    [/Doğru veri sayfasını seçin: (.+)\./g, 'Select the correct data sheet: $1.'],
    [/Harita geometrisindeki birim kimliği proje analiz birimleriyle eşleşmiyor\./g, 'A unit identifier in the map geometry does not match the project analysis units.'],
    [/Geometri dosyasındaki kimlikleri (?:analiz birimi|analysis unit) dosyasıyla karşılaştırın\./g, 'Compare the identifiers in the geometry file with the analysis-unit file.'],
    [/Dosya otomatik olarak uygulanamadı\./g, 'The file could not be applied automatically.'],
    [/Teknik ayrıntıdaki hata kodunu inceleyin ve dosyayı onaylamadan önce düzeltin\./g, 'Review the error code in the technical details and correct the file before approval.'],
    [/(\d+) dosya otomatik eşleştirildi; (\d+) açıkça ilgisiz dosya uygulanmadan (?:yok|none) sayıldı\. Bağımlı doğrulamalar açık onay sırasında güvenli sırayla yenilenir\./g, '$1 files were automatically matched; $2 explicitly irrelevant files were ignored without being applied. Dependent validations are safely refreshed during explicit confirmation.'],
    [/Analiz (?:birimi|Unit) bulunmuyor; alan ve mevcut (?:ürün|crop) verisi yükleyin\./g, 'No analysis units are available; upload analysis-unit area and current-crop data.'],
    [/Mevcut (?:ürün|crop)\/katalog eşleşmesi eksik:([^·]*)/g, 'Current crop/catalog matching is incomplete:$1'],
    [/Planlama yılı ekonomik verisi eksik:([^·]*)/g, 'Planning-year economic data are missing:$1'],
    [/Miktarı ve türü belirlenmiş su bütçesi gerekli\./g, 'A water budget with a specified amount and type is required.'],
    [/Birim\s*[×x]\s*(?:ürün|crop) düzeyinde açık aday su\/(?:kâr|profit) verileri gerekli; otomatik değer üretilmez\./g, 'Explicit candidate water/profit data are required at analysis-unit × crop level; values are not generated automatically.'],
    [/S2 için ([A-Za-z0-9_]+) bilimsel tablosu gerekli\./g, 'The $1 scientific table is required for S2.'],
    [/S2 için (?:ürün|crop) aileleri ve rotasyon kısıtları gerekli\./g, 'Crop families and rotation constraints are required for S2.'],
    [/([A-Za-z0-9_.]+): planlama yılına ait 12 benzersiz ay ve pozitif ([A-Za-z0-9_]+) gerekli\./g, '$1: 12 unique months for the planning year and positive $2 values are required.'],
    [/([A-Za-z0-9_.]+): birim ([A-Za-z0-9_/]+) ve (?:dönem|periods) calendar_month olmalıdır\./g, '$1: the unit must be $2 and the period must be calendar_month.'],
    [/integrity: hayır/g, 'integrity: no'],
    [/Henüz analiz (?:çalışması|runsı) (?:yok|none)\./g, 'No analysis runs yet.'],
    [/Beklenen: İlgili veri şablonundaki zorunlu alanlar/g, 'Expected: Required fields from the relevant data template'],
    [/NADAS \/ BOŞ/gi, 'FALLOW / UNALLOCATED'],
    [/Mevcut crop deseni/g, 'Current Cropping Pattern'],
    [/NOT PROVIDED\s*[—–·•-]\s*proje paketi kuraklık gösterge serisi içermiyor; Akkaya reference verisi kullanılmadı\./g, 'NOT PROVIDED — The project package does not include a drought-indicator series; Akkaya reference data were not used.'],
    [/Motor bu metrik için değer üretmedi/g, 'The engine did not produce a value for this metric'],
    [/DIAGNOSTIC \/ UYGULANABİLİR PLAN DEĞİL/g, 'DIAGNOSTIC / NOT A FEASIBLE PLAN'],
    [/DIAGNOSTIC \/ UYGULANABİLİR ÖNERİ DEĞİL/g, 'DIAGNOSTIC / NOT A FEASIBLE RECOMMENDATION'],
    [/DIAGNOSTIC \/ ÖNERİ DEĞİL/g, 'DIAGNOSTIC / NOT A RECOMMENDATION'],
    [/OTORİTATİF DEĞER/gi, 'AUTHORITATIVE VALUE'],
    [/YÜKSEK YOĞUNLAŞMA/g, 'HIGH CONCENTRATION'],
    [/ORTA YOĞUNLAŞMA/g, 'MODERATE CONCENTRATION'],
    [/DAĞITILMIŞ/g, 'DIVERSIFIED'],
    [/ÜRETİLMEDİ/g, 'NOT PRODUCED'],
    [/TEŞHİS/g, 'DIAGNOSTIC'],
    [/\bPay:/g, 'Share:'],
    [/\bİkinci\b/g, 'Secondary'],
    [/Eksik sunum metadatası/g, 'Missing Presentation Metadata'],
    [/Eski input snapshotına sabitlenmiş/g, 'Pinned to an Older Input Snapshot'],
    [/Revision ilişkisi/g, 'Revision Relationship'],
    [/Sınıflandırma/g, 'Classification'],
    [/Kurum belirtilmedi/g, 'Institution Not Specified'],
    [/Bölge belirtilmedi/g, 'Region Not Specified'],
    [/Aktif sürüm seçilmedi/g, 'No Active Version Selected'],
    [/\byıl yok\b/g, 'year unavailable'],
    [/\bkapsam yok\b/g, 'scope unavailable'],
    [/\botorite yok\b/g, 'authority unavailable'],
    [/\byok\b/g, 'none'],
    [/Üretilmedi/g, 'Not Produced'],
    [/model gösterimi/g, 'model demonstration'],
    [/^Tamamlandı · ([A-Z]+) · (.+)$/g, 'Completed · $1 · $2'],
    [/^bütçe durumu: (.+)$/g, 'budget status: $1'],
    [/^Immutable (.+) · PROJECT DATA önerisi$/g, 'Immutable $1 · PROJECT DATA recommendation'],
    [/^Secondary Crop \/ tamamlayıcı\s*[·•]\s*SECONDARY$/g, 'Secondary / Complementary Crop · SECONDARY'],
    [/^Rotation \/ Secondary Crop önerisi \(basit kurallar\)$/g, 'Rotation / Secondary-Crop Recommendation (Rule-Based)'],
    [/^Backend birim net profitı: (.+) TL · Otoritatif birim suyu: (.+) m³$/g, 'Backend Unit Net Profit: $1 TRY · Authoritative Unit Water: $2 m³'],
    [/^Backend birim net kârı: (.+) TL · Otoritatif birim suyu: (.+) m³$/g, 'Backend Unit Net Profit: $1 TRY · Authoritative Unit Water: $2 m³'],
    [/Senaryo 1 - Tek croplü analysis unit \(en iyi 1-2 crop \+ alternatifler\)/g, 'Scenario 1 – Single-Crop Analysis Unit (Best 1–2 Crops + Alternatives)'],
    [/Senaryo 2 - Çift croplü \/ desen bazlı analysis unit \(1\+1 crop \/ bahçede sıra arası\)/g, 'Scenario 2 – Two-Crop / Pattern-Based Analysis Unit (1+1 Crop / Orchard Inter-Row)'],
    [/GENEL GÖRÜNÜM/g, 'OVERVIEW'],
    [/Suyunu koruyamayan bir tarım, toprağını; toprağını koruyamayan bir millet, geleceğini[\s\u00a0]*kaybeder\./g, 'Agriculture that cannot protect its water loses its soil; a nation that cannot protect its soil loses its future.'],
    [/Hazırlayan: Betül Demir · Yüksek Lisans Tezi/g, 'Prepared by: Betül Demir · Master’s Thesis'],
    [/Hazırlayan: Betül Demir • Yüksek Lisans Tezi/g, 'Prepared by: Betül Demir • Master’s Thesis'],
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
    [/tamamlayıcı/g, 'complementary crop'],
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
    [/\bKIMYON\b/g, 'CUMIN'],
    [/\bDANE\b/g, 'GRAIN'],
    [/\bSu Tasarrufu\b/g, 'Water Saving'],
    [/\bTL\b/g, 'TRY'],
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
    [/^Not: Bu plan, .*ETc hesabıyla üretilir\..*çalışır\.$/g, 'Note: This schedule uses an approximate ETc calculation based on the selected unit’s climate series and crop calendar. It uses daily meteorology when available and monthly climate averages otherwise.'],
    [/^Parcel seç$/g, 'Select Parcel'],
    [/^Analysis Unit Özeti$/g, 'Analysis Unit Summary'],
    [/^Selected analysis unitin özeti$/g, 'Selected Analysis Unit Summary'],
    [/^Parcel Bazlı Özet$/g, 'Parcel-Based Summary'],
    [/^Selected parcelin [Öö]zeti$/g, 'Selected Parcel Summary'],
    [/^Hazır ([·•]) (.+)$/g, 'Ready $1 $2'],
    [/^CSV bağlandı$/g, 'CSV Connected'],
    [/^Projeden CSV yükle$/g, 'Load CSV from Project'],
    [/^Önbelleği temizle$/g, 'Clear Cache'],
    [/^15 Alan Denge SuluKirac$/g, '15 Irrigated/Rainfed Area Balance'],
    [/^16 Aylik Kayip Analizi$/g, '16 Monthly Loss Analysis'],
    [/^4 Urun Aylik SuButcesi$/g, '4 Monthly Crop Water Budget'],
    [/^8 Karma Sulama Senaryo$/g, '8 Mixed Irrigation Scenario'],
    [/^ARAZİ DAĞILIMI$/g, 'LAND DISTRIBUTION'],
    [/^HAYVAN VARLIĞI$/g, 'LIVESTOCK INVENTORY'],
    [/^MEYVE cropsİ$/g, 'FRUIT CROPS'],
    [/^SEBZE cropsİ$/g, 'VEGETABLE CROPS'],
    [/^TARIMSAL ARAÇ VARLIĞI$/g, 'AGRICULTURAL MACHINERY INVENTORY'],
    [/^TARLA BİTKİLERİ$/g, 'FIELD CROPS'],
    [/^Yerleşim düzeyindeki toplulaştırılmış hayvan varlığını göstermek\.$/g, 'Shows aggregated livestock inventory at settlement level.'],
    [/^Yerleşim düzeyindeki toplulaştırılmış mekanizasyon kapasitesini göstermek\.$/g, 'Shows aggregated mechanization capacity at settlement level.'],
    [/^Sürüm: (.+)$/g, 'Version: $1'],
    [/^(\d+) aday parcel: (\d+)$/g, '$1 candidate parcels: $2'],
    [/^Haritada yalnızca yüklenmiş gerçek GeoJSON sınırları gösterilir\..*üretilmez\.$/g, 'Only uploaded real GeoJSON boundaries are shown on the map. Other village/parcel records in Excel are used in numerical analysis; no representative rectangle is generated without a real GeoJSON boundary.'],
    [/^doluluk: (.+) \| baraj riski: (.+) \| plan riski: (.+)$/g, 'occupancy: $1 | reservoir risk: $2 | plan risk: $3'],
    [/\byüksek\b/g, 'high'],
    [/\bdüşük\b/g, 'low'],
    [/^Ana kota modeli: Dekar bazlı adil kota$/g, 'Primary Quota Model: Fair Per-Decare Quota'],
    [/^(\d+) köy ([·•]) (\d+) parcels ([·•]) (.+)$/g, '$1 villages $2 $3 parcels $4 $5'],
    [/^Optimizasyonda kullanılacak kota modeli$/g, 'Quota Model Used in Optimization'],
    [/^Karşılaştırma: eşit köy$/g, 'Comparison: Equal Village'],
    [/^(.*) m³\/köy$/g, '$1 m³/village'],
    [/^Eşit köyde en fazla artan$/g, 'Largest Increase under Equal-Village Model'],
    [/^Eşit köyde en fazla azalan$/g, 'Largest Decrease under Equal-Village Model'],
    [/^Current Total Water Use önce toplam alana bölünür ve (.+) genel hakkı hesaplanır\. Ana öneri bu değere göre yapılır\.$/g, 'Current total water use is first divided by total area to calculate the general entitlement of $1. The primary recommendation uses this value.'],
    [/^Baraj serisi bağlamı: (.+) ortalama çekiş, (.+) ortalama doluluk\.$/g, 'Reservoir-series context: $1 average withdrawal, $2 average occupancy.'],
    [/^Toplam köy alanı$/g, 'Total Village Area'],
    [/^Eşit köy payı$/g, 'Equal-Village Share'],
    [/^Dekar bazlı adil pay$/g, 'Fair Per-Decare Share'],
    [/^Eşit köy farkı: (.+)$/g, 'Equal-Village Difference: $1'],
    [/^Dekar bazlı fark: (.+)$/g, 'Per-Decare Difference: $1'],
    [/^Parcel özeti$/g, 'Parcel Summary'],
    [/^Parcel Haritası$/g, 'Parcel Map'],
    [/^GeoJSON yüklü \/ seçilebilir$/g, 'GeoJSON Loaded / Selectable'],
    [/^Çizim zemini$/g, 'Drawing Layer'],
    [/^Tüm parceller$/g, 'All Parcels'],
    [/^Köy sınırı$/g, 'Village Boundary'],
    [/^Baraj alanı$/g, 'Reservoir Area'],
    [/^Kuru tarım$/g, 'Rainfed Agriculture'],
    [/^Sulu tarım$/g, 'Irrigated Agriculture'],
    [/^Köy$/g, 'Village'],
    [/^Tüm parceller: (.+)$/g, 'All Parcels: $1'],
    [/yeniden çalıştırma gerekli/g, 'rerun required'],
    [/^Yeniden çalıştırma gerekli$/g, 'Rerun Required'],
    [/^Koşu bilgisi: Beklemede$/g, 'Run Information: Pending'],
    [/^Yeni seçim yapıldı\. Bu seçim için optimizasyon henüz çalıştırılmadı\.$/g, 'A new selection was made. Optimization has not yet run for this selection.'],
    [/^Yeni seçim yapıldı$/g, 'New Selection Made'],
    [/^Bu seçim için optimizasyon henüz çalıştırılmadı\..*beklemede tutulur\.$/g, 'Optimization has not yet run for this selection. The scenario result, budget, and feasibility fields in the right panel remain pending until a new backend result arrives.'],
    [/^Silajlık mısır$/g, 'Silage Maize'],
    [/^Şeker pancarı$/g, 'Sugar Beet'],
    [/^Yonca \(tam alan\)$/g, 'Alfalfa (Full Area)'],
    [/^Aşırı sulama isteyen sebzeler$/g, 'Vegetables Requiring Excessive Irrigation'],
    [/^Bağ \/ badem \(uygunsa\)$/g, 'Vineyard / Almond (If Suitable)'],
    [/^Nadas\/yeşil gübre rotasyonu$/g, 'Fallow / Green-Manure Rotation'],
    [/^Bu liste, optimizasyon sonucunu complementary crop bir karar destek notudur:.*ağırlık verin\.$/g, 'This list is a complementary-crop decision-support note for the optimization result: crops with high water demand carry more risk under drought. The crop pool may vary by parcel soil class and irrigation efficiency; because the objective is always water saving, prioritize low-water-use options.'],
    [/^Grafik üzerinde gezerek yıllık değerleri görebilirsiniz\..*öne çıkar\.$/g, 'Hover over the chart to view annual values. The selected water year is highlighted; the panel is emphasized in critical years.'],
    [/^Sulama sezonunda kritik minimumlar görülebilir .*$/g, 'Critical minimum levels may occur during the irrigation season (min < 10%). Water-intensive crops and surface irrigation carry high risk.'],
    [/^Kışlık \/ serin periods$/g, 'Winter / Cool-Season Period'],
    [/^Tek croplü senaryoda en iyi ana öneri ve diğer güçlü alternatifler listelenir\.$/g, 'The single-crop scenario lists the best primary recommendation and other strong alternatives.'],
    [/^Ana crop ([·•]) Kışlık \/ serin periods$/g, 'Primary Crop $1 Winter / Cool-Season Period'],
    [/\((\d+) gün\)$/g, '($1 days)'],
    [/^Parcel düzeyi desen$/g, 'Parcel-Level Pattern'],
    [/^Parcel çizim \/ bilgi atama$/g, 'Parcel Geometry and Information Assignment'],
    [/^Yağmurlama$/g, 'Sprinkler'],
    [/^Öneriler ve kısıt değerlendirmesi, optimizasyon çalıştırıldıktan sonra gösterilir\.$/g, 'Recommendations and constraint assessment are shown after optimization runs.'],
    [/(\d+) engelleyici bulgu:/g, '$1 blocking findings:'],
    [/^Engelleyici bulgu (?:yok|none)\.$/g, 'No blocking findings.'],
    [/^Kurumsal analiz görünümü aktif\.(.*)$/g, (_match, rest) => `Institutional Analysis View is active.${translate(rest)}`],
    [/^Kurumsal analiz görünümü$/g, 'Institutional Analysis View'],
    [/^(\d+) bekleyen talep ([·•]) (\d+) bildirim$/g, '$1 pending requests $2 $3 notifications'],
    [/^(\d+) konuşma$/g, '$1 conversations'],
    [/^(\d+) bildirim$/g, '$1 notifications'],
    [/^(\d+) mesaj$/g, '$1 messages'],
    [/^Seçili (talep|konuşma):/g, (_m, kind) => `Selected ${kind === 'talep' ? 'request' : 'conversation'}:`],
    [/^Parsel: (.+) ([·•]) (\d+) mesaj$/g, 'Parcel: $1 $2 $3 messages'],
    [/^(.+) (P[A-Za-z0-9_-]+) parseli için mesaj gönderdi\.$/g, '$1 sent a message for parcel $2.'],
    [/^(.+) (P[A-Za-z0-9_-]+) parcelsi için mesaj gönderdi\.$/g, '$1 sent a message for parcel $2.'],
    [/^(.+) (P[A-Za-z0-9_-]+) parseli için alternatif talebi gönderdi\.$/g, '$1 submitted an alternative request for parcel $2.'],
    [/^(.+) (P[A-Za-z0-9_-]+) parcelsi için alternatif talebi gönderdi\.$/g, '$1 submitted an alternative request for parcel $2.'],
    [/^Talebiniz uzman tarafından onaylandı\. (?:Seçilen|Selected) alternatif onaylı güncel plan sekmesine eklendi\.$/g, 'Your request was approved by the expert. The selected alternative was added to the approved current-plan tab.'],
    [/^Uzman\/kurum size bir mesaj gönderdi\.$/g, 'The expert/institution sent you a message.'],
    [/^Yönetici size bir mesaj gönderdi\.$/g, 'The administrator sent you a message.'],
    [/^(.+) yeni bir mesaj bıraktı\.$/g, '$1 left a new message.'],
    [/^(.+) sonra (.+) alternatifini seçmek istiyorum\. Su: (.+), net (?:kâr|profit): (.+)\. Uzman onayı rica ediyorum\.$/g, 'I would like to select $2 after $1. Water: $3, net profit: $4. Expert approval is requested.'],
    [/^(.+) tek ürün alternatifini talep ediyorum\. Hedef: (.+)\. Algoritma: (.+)\. Su: (.+), net kâr: (.+)\. Uzman onayı ve parselime atanmasını rica ediyorum\.$/g, 'I request the single-crop $1 alternative. Objective: $2. Algorithm: $3. Water: $4, net profit: $5. I request expert approval and assignment to my parcel.'],
    [/^(.+) tek crop alternatifini talep ediyorum\. Hedef: (.+)\. Algoritma: (.+)\. Su: (.+), net (?:kâr|profit): (.+)\. Uzman onayı ve parcelime atanmasını rica ediyorum\.$/g, 'I request the single-crop $1 alternative. Objective: $2. Algorithm: $3. Water: $4, net profit: $5. I request expert approval and assignment to my parcel.'],
    [/^PROJECT DATA geometrileri yüklenen proje dosyalarından gelir\..*kullanın\.$/g, 'PROJECT DATA geometries are loaded from the uploaded project files. This run view displays the geometry without modifying it; use Projects → Data Management to add or correct geometry.'],
    [/^Resmî (?:parsel|analiz birimi) kaydını seçip sınır çizimi, GeoJSON\/KML yükleme, çiftçi ataması ve seçilen alternatif desen kaydını bu çalışma alanından yönetin\..*$/g, 'Select the official analysis-unit record to manage boundary drawing, GeoJSON/KML upload, farmer assignment, and the selected alternative cropping-pattern record. The left panel remains simplified for analysis setup and quick summary.'],
    [/^Resmî (?:analysis unit|parsel|analiz birimi) kaydını seçip sınır çizimi, GeoJSON\/KML yükleme, çiftçi ataması ve seçilen alternatif desen kaydını bu (?:run|çalışma) alanından yönetin\..*$/g, 'Select the official analysis-unit record to manage boundary drawing, GeoJSON/KML upload, farmer assignment, and the selected alternative cropping-pattern record. The left panel remains simplified for analysis setup and quick summary.'],
    [/^Proje kapsamı (.+) Akkaya özeti kullanılmadı\.$/g, 'Project scope: $1. The Akkaya summary was not used.'],
    [/^(.+) ([·•]) backend karar bağlamından (\d+) (?:analysis unit|analiz birimi)\. Akkaya özeti kullanılmadı\.$/g, '$1 $2 $3 analysis units from the backend decision context. The Akkaya summary was not used.'],
    [/^Köy bazında toplam alan ve (?:analysis unit|parsel) sayısı$/g, 'Total Area and Analysis-Unit Count by Village'],
    [/^Seçili kapsamda özet üretilecek (?:parsel|analysis unit) bulunamadı\.$/g, 'No analysis units are available for a summary in the selected scope.'],
    [/^Seçili köy$/g, 'Selected Villages'],
    [/^Kapsamda özetlenen yerleşim adedi$/g, 'Settlements Summarized in Scope'],
    [/^Toplam (?:parsel|analysis unit)$/g, () => providerNoun('Total Parcels', 'Total Analysis Units')],
    [/^Analitik temsilde hesaba katılan (?:parseller|analysis units)$/g, () => providerNoun('Parcels Included in the Analytical Representation', 'Analysis Units Included in the Analytical Representation')],
    [/^Seçili kapsamın toplam ekili alanı$/g, 'Total Planted Area in the Selected Scope'],
    [/^Öneri su farkı$/g, 'Recommended Water Difference'],
    [/^Mevcut desene göre toplam fark$/g, 'Total Difference from Current Pattern'],
    [/^Karar özeti:$/g, 'Decision Summary:'],
    [/^Suda en güçlü değişim$/g, 'Strongest Water Change'],
    [/^Kâr etkisi en yüksek köy$/g, 'Village with the Highest Profit Impact'],
    [/^Baskın ürünler$/g, 'Dominant Crops'],
    [/^Mevcut su$/g, 'Current Water'],
    [/^Öneri su$/g, 'Recommended Water'],
    [/^Mevcut kâr$/g, 'Current Net Profit'],
    [/^Öneri kâr$/g, 'Recommended Net Profit'],
    [/^Seçili plan yılı$/g, 'Selected Planning Year'],
    [/^Kapsam kullanılabilir su$/g, 'Available Water for Scope'],
    [/^(?:Parsel|Analysis Unit) kullanılabilir su payı$/g, () => providerNoun('Available Parcel Water Share', 'Available Analysis-Unit Water Share')],
    [/^Önerilen toplam talep$/g, 'Total Recommended Demand'],
    [/^Su dengesi \(kalan \/ açık\)$/g, 'Water Balance (remaining / deficit)'],
    [/^Su durumu$/g, 'Water Status'],
    [/^Uygun$/g, 'Compliant'],
    [/^Aşım$/g, 'Exceeded'],
    [/^Toplam: alan (.+) da ([·•]) su (.+) m³ ([·•]) kâr (.+) TL$/g, 'Total: area $1 da $2 water $3 m³ $4 net profit $5 TRY'],
    [/^(.+) ([·•]) Hedef: (.+)\. Tekil (?:parsel|analysis unit)de su bütçesi havza toplamından değil, (?:parselin|analysis unitin) alan payı\/kotasından hesaplanır\.$/g, '$1 $2 Objective: $3. For a single analysis unit, the water budget is calculated from its area share/quota rather than the basin total.'],
    [/^Analiz Birimi Özeti - Resmî$/g, 'Analysis-Unit Summary — Official'],
    [/^Tüm Analiz birimleri - Mevcut vs Recommended \(Şeffaf Karşılaştırma\)$/g, 'All Analysis Units — Current vs Recommended (Transparent Comparison)'],
    [/^Selected kapsam \/ 5 köy analiz birimlerii için crop bazında ekim alanı .*$/g, 'Crop-level planted-area, water, and profit aggregation by season/period for the selected scope across five villages. With rotation/secondary crops, the same analysis-unit area may support more than one crop during the year.'],
    [/^Immutable run (run-[A-Za-z0-9]+) ([·•]) backend crop bazında su\/kâr dağılımı sağlamadığı için bu hücreler açıkça boş bırakıldı\.$/g, 'Immutable run $1 $2 These cells are explicitly left blank because the backend did not provide crop-level water/profit allocation.'],
    [/^Her analysis unit için seçili senaryo\+algoritma sonucunun su\/kâr özeti \(küresel su bütçesi sonrası\)\.$/g, 'Water/profit summary of the selected scenario and algorithm result for each analysis unit after the global water budget is applied.'],
    [/^Çiftçi için: Her analysis unitnde mevcut ekim deseni ile seçili senaryo\+algoritma sonucu önerilen desen yan yana\..*$/g, 'For farmers: the current cropping pattern and the pattern recommended by the selected scenario and algorithm are shown side by side for each analysis unit. Use Compare in each row to view water/profit comparisons for alternative crops.'],
    [/^Not: Öneriler, seçili senaryo \+ algoritma ile anlık üretilir \(henüz toplu optimizasyon çalıştırılmadı\)\.$/g, 'Note: Recommendations are generated live from the selected scenario and algorithm; batch optimization has not yet run.'],
    [/^Bu özet yalnız yüklenmiş PROJECT DATA, doğrulanmış revision ve seçili immutable run bağlamını kullanır\..*$/g, 'This summary uses only uploaded PROJECT DATA, the verified revision, and the selected immutable-run context. Because the package contains no separately published official table, it makes no separate official-authority claim.'],
    [/^NOT APPLICABLE — S1 tek sezon bağlamı\.$/g, 'NOT APPLICABLE — S1 single-season context.'],
    [/^Not: "Mevcut desen" seçiliyken algoritma kıyası anlamlı değildir; kıyas için (.+)$/g, 'Note: Algorithm comparison is not meaningful when Current Pattern is selected; choose one of $1 for comparison.'],
    [/^Note: Algorithm comparison is not meaningful when Current Pattern is selected;.*for comparison\.$/g, 'Note: Algorithm comparison is not meaningful when Current Pattern is selected; choose Water Saving, Profit Maximization, or Water-Use Efficiency for comparison.'],
    [/^sonucunu kullanır\. Aynı veri, aynı su bütçesi ve aynı tekrar sayısı altında.*$/g, 'result. Under the same data, water budget, and repeat count, it jointly reports mean, median, minimum/maximum, variability, feasible-solution rate, and runtime metrics for GA/ABC/ACO.'],
    [/^Aktif stored run: (.+)\. Diğer kombinasyonlar yalnız çalıştırılıp saklandığında karşılaştırılır\.$/g, 'Active stored run: $1. Other combinations are compared only after they are executed and stored.'],
    [/^Algoritma karşılaştırması için birden fazla PROJECT_DATA stored run gerekli; Akkaya benchmark değeri gösterilmedi\.$/g, 'Algorithm comparison requires multiple PROJECT_DATA stored runs; no Akkaya benchmark value is displayed.'],
    [/^Bu bölüm yalnızca backend benchmark sonucunu kullanır\.(.*)$/g, (_m, rest) => `This section uses only the backend benchmark result.${translate(rest)}`]
  ];

  function translate(value) {
    if (typeof value !== 'string' || !value.trim()) return value;
    const leading = value.match(/^\s*/)[0];
    const trailing = value.match(/\s*$/)[0];
    const core = value.slice(leading.length, value.length - trailing.length);
    if (/\.(?:xlsx|xls|csv|geojson|json)\b/i.test(core)) return leading + core + trailing;
    const normalizedCore = core.replace(/\s+/g, ' ');
    let result = exact.get(core) || exact.get(normalizedCore) || normalizedCore;
    for (let pass = 0; pass < 8; pass += 1) {
      const before = result;
      result = exact.get(result) || result;
      replacements.forEach(([pattern, replacement]) => { result = result.replace(pattern, replacement); });
      if (result === before) break;
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
      const current = element.getAttribute(name);
      const translatedEcho = refresh && language === 'en' && name in values &&
        translate(values[name]) === current;
      if ((!translatedEcho && refresh) || !(name in values)) values[name] = current;
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
      // Conversation bodies are historical/user-authored records. Translate the
      // surrounding controls and metadata, while preserving the authored text.
      if (parent.classList?.contains('request-msg-text') || parent.hasAttribute?.('data-i18n-user-text')) return;
      const translatedEcho = refresh && language === 'en' && originalText.has(node) &&
        translate(originalText.get(node)) === node.data;
      if ((!translatedEcho && refresh) || !originalText.has(node)) originalText.set(node, node.data);
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

  function refreshFileControl(input) {
    const control = input.nextElementSibling?.classList?.contains('paper-file-control')
      ? input.nextElementSibling : null;
    if (!control) return;
    const button = control.querySelector('.paper-file-button');
    const status = control.querySelector('.paper-file-status');
    const count = input.files?.length || 0;
    if (button) button.textContent = language === 'en'
      ? (input.multiple ? 'Choose Files' : 'Choose File')
      : (input.multiple ? 'Dosyaları Seç' : 'Dosya Seç');
    if (!status) return;
    if (!count) status.textContent = language === 'en' ? 'No file selected' : 'Dosya seçilmedi';
    else if (input.multiple) status.textContent = language === 'en'
      ? `${count} files selected` : `${count} dosya seçildi`;
    else status.textContent = input.files[0]?.name || (language === 'en' ? '1 file selected' : '1 dosya seçildi');
  }

  function installFileControls(root=document) {
    const inputs = [];
    if (root?.matches?.('input[type="file"]')) inputs.push(root);
    root?.querySelectorAll?.('input[type="file"]').forEach(input => inputs.push(input));
    inputs.forEach(input => {
      if (!input.classList.contains('paper-native-file-input')) {
        input.classList.add('paper-native-file-input');
        const control = document.createElement('span');
        control.className = 'paper-file-control';
        control.innerHTML = '<span class="paper-file-button"></span><span class="paper-file-status" aria-live="polite"></span>';
        input.insertAdjacentElement('afterend', control);
        input.addEventListener('change', () => refreshFileControl(input));
      }
      refreshFileControl(input);
    });
  }

  function switchHost() {
    if (document.body.classList.contains('auth-pending')) {
      return document.querySelector('.auth-card-head') || document.querySelector('.auth-card');
    }
    return document.querySelector('.topbar-actions') ||
      document.querySelector('.session-chip-row') ||
      document.querySelector('.app-header') ||
      document.body;
  }

  function installSwitch() {
    let wrapper = document.querySelector('.paper-language-switch');
    if (!wrapper) {
      wrapper = document.createElement('div');
      wrapper.className = 'paper-language-switch';
      wrapper.setAttribute('role', 'group');
      wrapper.setAttribute('aria-label', 'Interface language');
      wrapper.innerHTML = '<button type="button" data-paper-lang="tr">TR</button><button type="button" data-paper-lang="en">EN</button>';
      wrapper.addEventListener('click', event => {
        const selected = event.target.closest('[data-paper-lang]')?.dataset.paperLang;
        if (supported.has(selected)) setLanguage(selected);
      });
    }
    const host = switchHost();
    if (host && wrapper.parentElement !== host) host.append(wrapper);
    wrapper.classList.toggle('paper-language-switch--auth', Boolean(wrapper.closest('.auth-card')));
    wrapper.classList.toggle('paper-language-switch--topbar', Boolean(wrapper.closest('.topbar-actions')));
    wrapper.classList.toggle('paper-language-switch--v1', Boolean(wrapper.closest('.session-chip-row')));
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
    installFileControls(document);
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
  style.textContent = '.paper-language-switch{position:static;z-index:auto;display:inline-flex;flex:0 0 auto;align-items:center;align-self:center;gap:2px;min-width:max-content;padding:3px;border:1px solid rgba(255,255,255,.42);border-radius:999px;background:rgba(7,42,34,.72);box-shadow:0 3px 12px rgba(0,0,0,.14)}.paper-language-switch button{min-height:30px;min-width:38px;padding:4px 10px;border:0;border-radius:999px;background:transparent;color:#dcebe5;font:700 12px/1.2 Inter,"Segoe UI",Arial,sans-serif;cursor:pointer}.paper-language-switch button.active{background:#fff;color:#164f40}.paper-language-switch button:focus-visible{outline:3px solid #7cc7ff;outline-offset:2px}.paper-language-switch--auth{align-self:flex-start;margin-top:12px;background:#102f28}.paper-language-switch--v1{height:44px;margin-left:2px}.topbar-actions{flex-wrap:wrap}.paper-language-switch--topbar{order:3}.paper-native-file-input{position:absolute!important;width:1px!important;height:1px!important;padding:0!important;margin:-1px!important;overflow:hidden!important;clip-path:inset(50%)!important;white-space:nowrap!important;border:0!important}.paper-file-control{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:6px}.paper-file-button{display:inline-flex;align-items:center;min-height:38px;padding:7px 12px;border:1px solid #9fb7ae;border-radius:8px;background:#f7fbf9;color:#164f40;font-weight:700;cursor:pointer}.paper-file-status{color:#52645e;font-size:13px;font-weight:500}@media(max-width:1050px){.paper-language-switch button{min-width:36px;padding-inline:8px}.paper-language-switch--v1{margin-left:0}}@media(max-width:650px){.paper-language-switch--topbar{justify-self:end}.paper-language-switch--auth{margin-top:10px}}@media print{.paper-language-switch{display:none!important}}';
  document.head.append(style);
  placementObserver = new MutationObserver(installSwitch);
  placementObserver.observe(document.body, {attributes:true, attributeFilter:['class']});
  observer = new MutationObserver(mutations => {
    observer.disconnect();
    mutations.forEach(mutation => {
      if (mutation.type === 'characterData') applyNode(mutation.target, true);
      else if (mutation.type === 'attributes') rememberAttributes(mutation.target, true);
      else mutation.addedNodes.forEach(node => { applyNode(node); installFileControls(node); });
    });
    installSwitch();
    updateSwitch();
    requestAnimationFrame(applyCharts);
    observer.observe(document.documentElement, {subtree:true, childList:true, characterData:true, attributes:true, attributeFilter:['aria-label','title','placeholder']});
  });
  setLanguage(language);
  window.__CROP_KDS_I18N__ = Object.freeze({get language(){return language;}, setLanguage, translate, applyCharts});
})();
