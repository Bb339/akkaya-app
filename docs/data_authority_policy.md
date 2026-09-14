# Data authority policy

Canonical sınıflar:

`MEASURED > OFFICIAL_ALLOCATION > OFFICIAL_HISTORICAL > CALCULATED_REFERENCE > DERIVED_PROXY > ASSUMED > UNKNOWN`

`SCENARIO` bu sıralamanın dışında bir planning input sınıfıdır. Yüksek otorite anlamına gelmez ve sıralı karşılaştırmada otomatik üstünlük kazanmaz.

## Activation policy

1. Upload ve validation aktif dataset’i değiştirmez.
2. Preview eski/yeni authority, toplamlar, fark, etkilenen aylar, senaryolar ve re-analysis gereğini gösterir.
3. Genel explicit confirm olmadan hiçbir dataset etkinleşmez.
4. Daha yüksek authority confirm sonrasında etkinleşebilir; eski dataset history’de kalır.
5. Aynı authority aynı dönem için conflict preview üretir ve sessiz overwrite yapılmaz.
6. Daha düşük authority veya `SCENARIO`, otoriter aktif dataset’in yerine ancak özel acknowledgement ve boş olmayan gerekçeyle geçebilir.
7. Confirm atomik olarak yeni dataset’i active yapar, eski dataset’i inactive işaretler ve project `data_revision` değerini artırır.

`SYNTHETIC` kaynak işareti authority’den ayrıdır. Test fixture’ı `OFFICIAL_ALLOCATION` akışını sınayabilir; source içinde `synthetic_test_fixture` saklanır ve preview bunu `SYNTHETIC` olarak gösterir.
