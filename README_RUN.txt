Akkaya Panel UI + Python Backend (Veri Paketi A ile otomatik okuma)

Bu paket artık "script.js içine gömülü demo parseller" yerine, varsa data/ klasöründeki dosyalardan otomatik okur.

1) Kurulum (Windows)
   cd akkaya
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt

2) Çalıştır
   python app.py

3) Tarayıcı
   http://127.0.0.1:5000

Veri otomatik nereden okunuyor?
- Parseller: data/parsel_su_kar_ozet.csv   (ayraç: ';')
- Ürün kataloğu: data/urun_parametreleri_demo.csv (ayraç: ',')
- Köy/ilçe ürün desenleri: data/village_crop_patterns.json, data/district_crop_patterns.json
- Frontend, bu dosyaları "data/" altından fetch eder; backend ise /api/optimize içinde aynı dosyaları okur.

Önemli:
- Eğer parsel_su_kar_ozet.csv içinde 3 parsel varsa harita/seçim listesi 3 parsel gösterir.
  15 parsel görmek istiyorsanız bu CSV'ye 15 parsel satırı koymanız gerekir.
- Backend çalışırken 'Optimizasyonu Çalıştır' butonu /api/optimize çağırır (URL artık relative).
