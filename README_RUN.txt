Tarımsal Karar Destek Sistemi + Python Backend

Bu paket, gömülü demo parseller yerine varsa `data/` klasöründeki güncel dosyaları otomatik okur.

V2 Project/Data milestone (v2-general-platform)
- Project/import API: /api/v2/projects
- CSV/XLSX/GeoJSON: staging, mapping, preview, validation ve açık confirm.
- Runtime depo: %LOCALAPPDATA%/CropKDS/projects; KDS_PROJECT_STORE ile ayarlanabilir.
- Demo oluşturma: py -B -m kds seed-demo --source-dir data
- Bilimsel motor ve ana UI değişmedi; yeni projeler henüz eski optimizer'a bağlanmaz.
- Dokümanlar: docs/architecture.md, docs/data_model.md, docs/upload_format.md,
  docs/migration_v1_to_v2.md. Şablonlar: docs/data_templates/ (Data sayfası).
- Authentication eklenmedi; API yerel geliştirme kapsamındadır.

1) Kurulum (Windows)
   `cd` ile bu klasöre girin
   `py -m venv .venv`
   `.venv\Scripts\activate`
   `pip install -r requirements.txt`

2) Çalıştır
   `py app.py`

3) Tarayıcı
   `http://127.0.0.1:5000`

Veri otomatik nereden okunuyor?
- Parseller: `data/parsel_su_kar_ozet.csv`
- Ürün kataloğu: `data/urun_parametreleri_demo.csv`
- Köy / ilçe ürün desenleri: `data/village_crop_patterns.json`, `data/district_crop_patterns.json`
- Frontend bu dosyaları `data/` altından fetch eder; backend ise `/api/optimize` içinde aynı dosyaları kullanır.

Önemli:
- `parsel_su_kar_ozet.csv` içinde kaç parsel varsa seçim listesi ve harita o kadar parsel gösterir.
- `Optimizasyonu Çalıştır` butonu backend açıkken relative `/api/optimize` çağrısı yapar.
- Paket başlığı ve API meta bilgisi `Tarımsal Karar Destek Sistemi` olarak senkronize edilmiştir.

Rol bazlı demo hesaplar
- Çiftçi demo (aktif): `betul.demir / demo123`
- Çiftçi demo (ilk kurulum): `ciftci.ayse / demo123`
- Kurum demo (yönetici): `kurum.nigde / demo123`
- Kurum demo (uzman): `uzman.nigde / demo123`

Not:
- Bu sürüm tez prototipi için örnek kullanıcı mantığı içerir.
- Çiftçi hesabında yalnızca tanımlı parseller görünür.
- Kurum hesabında bölge geneli analiz ve yönetim ekranları görünür.

Öne çıkan iş mantığı
- Çiftçi, resmî parseli doğrudan değiştirmez; düzeltme talebi oluşturur.
- Kurum tarafında yapılan resmî parsel güncellemeleri tarayıcıda kalıcı override olarak saklanır ve hesaplamalara dahil edilir.
- Kuraklık detay paneli varsayılan olarak kapalı açılır; çiftçi görünümünde karmaşık veri seti seçicileri gizlenir.
- Bu sürümde ana planlama yılı 2024 mevcut desen/kota referansıdır. İleri projeksiyon modülleri aktif karar ekranından çıkarılmıştır; sistem mevcut su kullanımı, parsel kotası, ürün deseni, su/kâr karşılaştırması, tarımsal uygulanabilirlik uyarıları ve algoritma benchmarkı üzerinden çalışır.
- Paket içinde proxy / assumed veri bulunan katmanlar vardır; bunlar savunma ve sunumda açıkça belirtilmelidir.
