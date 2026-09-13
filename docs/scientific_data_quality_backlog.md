# Bilimsel veri kalitesi backlog

## Çalışan 58 ürün / tezdeki 69 ürün

Çalışan V1 ve Akkaya demo kataloğu 58 üründür. Tezde anılan 69 ürünlük
Kc/fenoloji kapsamıyla fark bu milestone'da giderilmemiştir. Hiçbir katalog
ürünü eklenmemiş veya silinmemiştir. S2'nin zaten mevcut varsayılan aday
parametrelerini sağlayıcıya taşımak katalog kapsamını değiştirmez.

Sonraki veri incelemesi: 69 ürünün kaynak listesini doğrula; isim/çeşit/
sezon alias'larını ayır; eksik 11 kaydın hangi veri katmanına ait olduğunu
belirle; Kc evreleri, tarih, kaynak ve güven düzeylerini doğrula; ancak
ayrı onaylı bilimsel baseline sonrasında katalog değişikliğini değerlendir.

## Diğer kayıtlı sınırlar

- Referans proxy/varsayım katmanları gerçek ölçüm gibi etiketlenmemeli.
- 3673 ham su-kota bayrağı nihai agronomik uygunluk sayısı değildir.
- `calculated_reference` miktarı resmî su tahsisi değildir.
- Tez motorunun S2 EC toleransı, kâr gerçekçilik kuralı, bölgesel/sezon
  tamamlama davranışları saha doğrulaması gerektirir. Genel projelerde
  varsayılan aday/su/kâr tamamlama kaynakları devre dışıdır.
- S2 ham sonuçta son fitness alanı yoktur; null skor yeni bir formülle
  tamamlanmamalıdır.
- Yeni ürün adları mevcut sınıflandırma kurallarının kapsamı dışındaysa
  NOT_READY döndürülür; isim benzerliğinden bilimsel parametre türetilmez.
