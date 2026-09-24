# Analiz önizleme arayüzü

Önizleme proje, profil, senaryo, algoritma, hedef, seed, planlama yılı, coğrafi kapsam, aday ve birim sayılarını gösterir. Seçilen datasetler kimlik, sürüm, otorite ve tüketim rolüyle listelenir. İklim, çevresel akış, iletim randımanı, mevcut desen ve aday kaynağı backend yanıtında bulunduğu ölçüde gösterilir.

`preview_token`, `preview_revision` ve `selection_hash` teknik ayrıntılarda saklanır ve VERIFIED_INSTITUTIONAL çalıştırmasına aynen geri gönderilir. Form, profil, senaryo veya veri değişikliği kanıtı geçersiz kılar. Backend stale/revision/selection reddi özel stale uyarısını açar ve yeniden önizleme gerektirir.
