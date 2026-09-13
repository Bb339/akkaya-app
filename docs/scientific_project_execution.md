# Projeden bilimsel analize

Bu katman mevcut `app.py` bilimsel motorunu kullanır. S1 ve S2 ayrı aday,
kısıt ve algoritma akışlarını korur. GA/ACO/ABC formülleri, katsayıları ve
tez arayüzü yeniden yazılmamıştır.

## Yerel çalıştırma

V2 worktree içinde, ayrı bir yerel portta:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
py -B -m flask --app app run --host 127.0.0.1 --port 5052 --no-reload
```

Proje arayüzü: `http://127.0.0.1:5052/projects`.
V1 endpointleri ve ana arayüz mevcut yollarında kalır. Bu komut production
deployment veya remote push değildir.

Store yolu `kds.config.project_store_path()` tarafından belirlenir.
`KDS_PROJECT_STORE` override'ı desteklenir. Windows varsayılanı
`%LOCALAPPDATA%/CropKDS/projects` olur. Yükleme, analiz kaydı ve sonuçlar
kaynak ağacına yazılmaz. Testlerin tamamı geçici store kullanır.

## Girdi sözleşmesi ve sağlayıcılar

`ScientificInputBundle` frozen dataclass'tır. Birimler, ürün parametreleri,
ekonomi, bütçe, aday seçenekleri, sulama, iklim, toprak/uygunluk, rotasyon,
hedef, algoritma ayarları ve provenance içerir. İç içe değerler immutable
JSON temsili `FrozenValue` ile saklanır. DataFrame, tuple anahtarlı map ve
sayısal tipler kayıpsız taşınır. Her execution kendi mutable engine
görünümlerini bir kez oluşturur; bunlar başka execution veya bundle ile
paylaşılmaz. Aynı çalışma içindeki okumalar legacy cache davranışını korur.
Bundle Flask, HTML veya `Path` nesnesi taşımaz.

`@source` dekoratörleri yalnız veri yükleyicilerindedir. `optional_reference`
gömülü JSON/CSV okumalarını, referans aday genişletme verisini ve mevcut
S2 varsayılan ürün parametrelerini sağlayıcı sınırına taşır. Algoritmalar
içine proje kimliğine göre dallanma eklenmemiştir.

- `LegacyReferenceProvider`: mevcut yükleyici davranışını korur.
- `ProjectDataProvider`: bundle kaynaklarını okur; eksik kaynakta hata verir.
- `scientific_reference`: eski dosya adları ve ek tez kaynakları burada kalır.
- `project_science`: Project Store kayıtlarını canonical adaylar ve engine
  görünümlerine çevirir.

`tests/fixtures/data_boundary_changes.json` yalnız izin verilen veri erişimi
değişikliklerini kaydeder. Kaynak koruma testleri bunları geri eşledikten
sonra 171 eski fonksiyon/sınıfı ve modül AST'sini ilk milestone'un sabit
manifestiyle karşılaştırır. Eski manifest yenisiyle değiştirilmemiştir.

## Referans ve davranış eşitliği

İlk 104 test, uygulamaya başlanmadan önce geçti: 205.94 saniye.
Ardından **7d47d296acbc89d9f172e7113e3bdc2ef1ab6ca0** durumundan fixture
üretildi. Altı dosya S1/S2 × GA/ACO/ABC kombinasyonlarını, her biri
123, 456, 789 seed'lerini içerir. Seçili birimler P1, P23, P149'dur.
Bu, bütün 179 birim üzerinde exhaustive benchmark iddiası değildir.

Çağrı sınırı tek `optimize` çalışmasıdır. HTTP benchmark'ın çoklu tekrar
ve algoritmaya göre seed offset'leri uygulanmaz. Seed doğrudan kaydedilir.
Hedef `water_saving`, yıl 2024, bütçe oranı 1.0'dır. Parametreler ve bütün
ek CSV/JSON kaynak hash'leri metadata'dadır. Hızlı test ilk seed'i,
extended test üç seed'i karşılaştırır.

Kimlikler, ürün seçimi, listelerin sırası, boolean kısıtlar ve metinler
exact karşılaştırılır. Alan, su, kâr, verimlilik, skor ve çeşitlilik dahil
floating alanlarda `rel=1e-10, abs=1e-7` kullanılır. Çalışma süresi ve
`generated_at` gibi duvar saati alanları karşılaştırmaya dahil edilmez.
Sonuçlardaki ham plan, detaylar ve deterministik metrikler korunur.

S2 ham motor çıktısı son fitness skorunu döndürmez; sonuç özetindeki
`score=null` bunu açıkça belirtir. Yeni skor icat edilmez. S1 `bestScore`
ve mevcut çeşitlilik metrikleri doğrudan kullanılır. S2 seçili referans
koşullarında `feasible=false` üretebilir; bu sonuçlar değiştirilmez.

Motorun mevcut alt/üst algoritma parametre sınırları da korunur. Örneğin
S1 GA popSize=8/generations=4 isterse etkin değerler 12/10 olabilir.
İstenen ayarlar ve motorun döndürdüğü etkin ayarlar ayrı kaydedilir;
sınır uygulaması sonuç uyarısında görünür. UI başlangıç değerleri bu
alt sınırlarla uyumludur.

## Akkaya köprüsü

Projenin birim, ürün, ekonomi ve bütçe kayıtları, sabit tez kaynaklarıyla
eşit olmalıdır. Ek bilimsel kaynakların hash'leri doğrulanır. Değişmiş
referans proje sessizce eski ek veriyle çalıştırılmaz; açık bilimsel
girdi yüklenmesi istenir. 2024 dışındaki referans yıl engellenir.

Korunan değerler:

| Alan | Değer |
|---|---:|
| Analiz birimi | 179 |
| Alan | 134919 da |
| Calculated reference su | 100700080.81 m³ |
| Mevcut desen kârı | 1041499119.212 TL |
| Ham aday satırı | 6859 |
| Ham kota bayrağı | 3673 |
| Çalışan ürün kataloğu | 58 |

3673, nihai uygun aday sayısı değildir. `CandidateOption.quota_compatible`
ham bayrağın anlamını korur. Referans adayın `allowed/rotation/suitability`
alanlarına kaynakta bulunmayan doğruluk iddiaları eklenmez; tam satır
metadata'da korunur. Nihai kısıtları mevcut motor değerlendirir.

Tezin mevcut bölgesel genişletme, varsayılan aday, proxy toprak/Kc/iklim ve
eksik sezon tamamlama kuralları **referans yolunda açık uyarıyla** korunur.
Bu, genel projelerin eksik girdilerini doldurmak için kullanılmaz.
S2'nin aylık rezervuar serisi ve çevresel akış hesabı, proje ekranındaki
hesaplanmış mevcut talep referansından farklı bir analiz bütçesi üretir.
Uygulanan bütçe ayrıca sonuçta gösterilir.

## Genel proje hazırlığı

Her senaryo READY / READY_WITH_WARNINGS / NOT_READY üretir. Kontroller:
birimler ve pozitif alan, mevcut ürün/katalog eşleşmesi, yıl bazlı ekonomi,
TRY para birimi, miktarı/türü belirli bütçe, Kc/fenoloji, sulama randımanı,
mevcut su/kâr, toprak sınıfı, adaylar ve ilgili sezon tablolarıdır.
Geometri opsiyoneldir. Katalog Kc kapsamı, kaynak güven sınıfları ve ek
referans parametre katmanı arayüzde birbirinden ayırt edilir.

Motorun mevcut ürün grubu kurallarında tanınmayan adlar NOT_READY olur.
Bu milestone yeni agronomik ürün sınıflandırıcısı eklemez. TRY dışı para
birimini TL olarak etiketlemez veya kur dönüşümü uydurmaz.

S1 açık adayları kullanır. Her birimde mevcut ürünün onaylı seçeneği
bulunmalıdır. Sparse aday listesi kabul edilir; bölgesel genişletme kaynağı
boştur. `allowed=false` satırlar engine tablosuna girmez. Kandidat su/kâr
ve verim değerleri pozitif/sonlu, kaynak kısıt durumları açık olmalıdır.
Mevcut su/kâr eksikse alan×500 veya alan×5000 dalına geçilmeden durulur.

S2 için ayrıca her birim/ürün/sezonun açık gözlemi, geçerli tarihler,
sulama randımanı, 12 aylık rezervuar/iletim/su kalitesi, birim başına
12 aylık iklim, tam toprak/ürün uygunluğu, ürün aileleri ve önceki yıl
ürün geçmişi gerekir. Rezervuar toplamı proje bütçesiyle eşleşmelidir.
S2 varsayılan ürün havuzu genel projede boştur. Nadasın sıfır su/kâr
güvenlik seçeneği ve mevcut bilimsel kısıt/ceza formülleri korunur.
Calib su ve none risk modu bu milestone'un desteklenen açık politikasıdır.
Mevcut EC toleransları, kâr gerçekçilik sınırlaması ve diğer model kuralları
tez motorunun kurallarıdır; yeni saha doğrulaması iddia edilmez.

## API ve runtime kayıtları

| Metot | Yol |
|---|---|
| GET | `/api/v2/projects/<id>/readiness` |
| POST | `/api/v2/projects/<id>/analyses` |
| GET | `/api/v2/projects/<id>/analyses/<run_id>` |
| GET/POST | `/api/v2/projects/<id>/scientific-inputs` |
| POST | `/api/v2/projects/<id>/water-budget` |

Mevcut proje/import endpointleri korunur. POST analyses açık `scenario`,
`algorithm`, `seed`, `objective`, `water_budget_ratio`, `config` ister.
`selected_ids` opsiyoneldir; boş/yoksa bütün proje birimleri seçilir.

```json
{
  "scenario": "S1", "algorithm": "GA", "seed": 123,
  "objective": "water_saving", "water_budget_ratio": 1.0,
  "config": {"popSize": 12, "generations": 10, "cxRate": 0.7, "mutRate": 0.08}
}
```

ACO: ants/iterations/rho/q. ABC: foodSources/cycles/limit.
AUTO, eksik config, belirsiz seed ve yabancı birim kimlikleri reddedilir.
Çalışmalar senkron HTTP çağrısı altında yürütülür; kalıcı iş kuyruğu yoktur.

`AnalysisRun` id, project_id, data_version, scenario, algorithm, seed,
configuration, başlangıç/bitiş, durum, ham sonuç, özet, hata ve provenance
saklar. Hatalı çalışmalara başarılı sonuç yazılmaz. Başarılı çalışma
`completed`, bilimsel olarak uygun olmayan plan ise ayrıca `feasible=false`
taşır. UI bu ayrımı gösterir. Projeler arası run kimliğiyle erişim yoktur.

## RNG, cache ve izolasyon

Her analiz Windows spawn ile ayrı süreçte çalışır. Legacy Python/NumPy RNG
ve hesaplama cache'i o süreçte kalır. Seed davranışı değiştirilmez. Tez
verisinin ilk yüklenmesi bile ayrı süreçtedir; eski JSON yükleyicisinin
yerinde normalizasyonu web sürecinin cache'ini değiştiremez.

Yalnız immutable referans kaynakları, bütün girdi hash'leri + motor hash'i
ile önbelleğe alınabilir. Kullanıcı projesi için global mutable cache yoktur.
Analiz kimlik anahtarı project_id, data hash, year, scenario, objective,
algorithm ve seed/config hash'ini kapsar. Projeler arasında sonuç cache'i
yeniden kullanılmaz. Her kayıt gerçek bir çalışmadır.

## Test komutları

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
py -B -m pytest -q -p no:cacheprovider --ignore=tests/test_decision_pipeline.py --ignore=tests/test_defense_datasets.py --ignore=tests/test_scientific_execution.py
py -B -m pytest -q -p no:cacheprovider
$env:KDS_EXTENDED='1'
py -B -m pytest tests/test_scientific_execution.py -q -p no:cacheprovider
Remove-Item Env:KDS_EXTENDED
```

Hızlı komut eski ağır bilimsel senaryo testlerini içermez; tam komut
önceki 104 testin tamamını içerir. Chromium smoke testi Playwright ve
kurulu Chromium gerektirir. Tarayıcı testi gerçek proje oluşturma,
CSV önizleme/eşleştirme/onay, readiness, analiz ve sonuç kaydını doğrular.
Test verileri sentetiktir ve gerçek kullanıcı AppData store'una yazılmaz.

## Açık sınırlar ve sonraki işler

- 58/69 ürün farkı `scientific_data_quality_backlog.md` dosyasındadır.
- Yeni ürün taksonomisi, para birimi dönüşümü ve otomatik agronomik aday
  üretimi eklenmemiştir; eksik sözleşmede NOT_READY döner.
- UI ilk doğrulama akışıdır; kimlik doğrulama/çok kullanıcılı production
  sistemi değildir. Bu milestone production'a yayımlanmaz.
- S2 fitness tanı alanının motor tarafından dışarı verilmesi ve geniş
  saha veri şemalarının doğrulanması ayrı bilimsel regresyon gerektirir.
- Tam 179 birim × çok sayıda seed performans benchmark'ı, hızlı fixture
  setinden ayrı bir çalışma olarak planlanmalıdır.

## Milestone kapanış doğrulaması — 13 Eylül 2026

- Başlangıç: 104 test geçti (205.94 s).
- Standart koleksiyon: 141 test = önceki 104 + yeni 37.
- Son kodda `KDS_EXTENDED=1` ile tam koleksiyon: **153 passed in 570.46s**.
  Bu, standart 141 testin tamamını ve iki ek seed için 12 bilimsel
  regresyon vakasını kapsar; bilimsel modül toplamı 20 testtir.
- Önceki hızlı kontrol: 100 geçti. Son tam paket bu kontrolleri de kapsar.
- Tam 179 birimde ek S1–GA/seed 123 karşılaştırması, arşivlenmiş başlangıç
  `7d47d29` legacy motoruyla eşleşti: 50228 sayısal, 105493 diğer değer.
  Su 59806864.00387305 m3; net kâr 789031097.6189687 TL; feasible=true.
  Son proje kaydı: `run-4139fb8043f449389a6fb5dc57a6a6de`.
- Dört XLSX şablonu mevcut ve ZIP CRC kontrolleri başarılı; değiştirilmedi.
- V1 HEAD/etiket a49daac1ae6d15d83428565c388bfafb4b6da08a korundu.
  Production yayını ve remote push yapılmadı.
