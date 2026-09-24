# Veri yönetimi arayüzü

Veri merkezi temel proje, su, ekonomi ve agronomi alanlarını gruplar. Her satır genel durumu ve varsa aktif dataset sürümü, otoritesi, planlama yılı ve kapsamını gösterir. Sürüm geçmişi dataset kimliği, aktif/geçmiş durumu, onay zamanı ve kayıt sayısını listeler.

Yükleme akışı ImportService sözleşmesini aynen izler: dosya yükle, sütun eşleştir, doğrula, önizle, açıkça onayla, aktif sürüm. Upload tek başına veri etkinleştirmez. Uyarı ve daha düşük otorite override onayları ayrı kontrollerdir. Şablonlar `/projects/templates/<filename>` allowlist rotasıyla indirilir ve resmî veri olmadığı açıkça belirtilir. Rota bilimsel içerik üretmez.
