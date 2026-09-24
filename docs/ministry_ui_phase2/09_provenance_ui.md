# Provenance arayüzü

Her kayıtlı çalışma için bir özet ve genişletilebilir teknik kayıt bulunur. Özet: run ID, project ID, profil, veri revizyonu, selection hash, engine commit, sınıflandırma, kaynak etiketi ve tamamlanma zamanını gösterir. Teknik bölüm immutable run provenance, input snapshot, result provenance ve input provenance alanlarını gösterir.

Çalışma geçmişi run kimliği üzerinden kayıtlı sonucu yeniden açar; yeni veri geldiğinde eski run değiştirilmez. Veri geçmişi aktif/geçmiş dataset ayrımını korur. `requires_reanalysis` true olduğunda önceki sonucu görme ve güncel veriyle yeni önizleme hazırlama eylemleri gösterilir.
