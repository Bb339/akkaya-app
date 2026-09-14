# Official water data import

1. İlgili XLSX şablonunu doldurun; ham kaynak değer ve birimi koruyun.
2. `authority_class` seçin ve kurum/reference metadata’sını ekleyin.
3. `/projects` içindeki mevcut upload formundan data type ve dosyayı gönderin.
4. Canonical mapping, validation issue’ları, `SYNTHETIC` etiketi ve replacement preview’ı inceleyin.
5. Eski/yeni authority, toplam, fark, aylar ve etkilenen analizleri kontrol edin.
6. Uyarıları kabul edip explicit confirm verin. Authority düşürülüyorsa ayrı override acknowledgement ve gerekçe girin.
7. Confirm sonrası readiness içindeki active dataset id, authority, version, source ve confirmation zamanını doğrulayın.

## Unit handling

`m³` yazımı `m3` olarak ve ISO tarihleri `YYYY-MM` calendar month olarak güvenle normalize edilir. `hm3 → m3`, `m3/s → m3/month` ve `mm → m3/da` fiziksel dönüşümleri yalnız tanımlı contract ile yapılır ve conversion trace kayda girer.

`m3/s → m3/month` için `operating_hours_per_day` ve `operating_days_in_month` zorunludur. Bu bilgi yoksa import reddedilir. Uygulama çalışma süresi varsaymaz.

## Current integration boundary

Active pointer future integration için saklanır. GA, ACO, ABC ve S2 supply computation bu dataset’leri henüz okumaz. Gerçek verified veri geldiğinde ayrı Scientific Integration milestone’unda engine bağlantısı kurulmalıdır.
