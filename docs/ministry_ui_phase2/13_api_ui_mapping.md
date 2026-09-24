# API–UI eşlemesi

| UI alanı | Endpoint | Kullanım |
|---|---|---|
| Proje portföyü | `GET /api/v2/projects` | Seçim kartları |
| Proje bağlamı | `GET /api/v2/projects/{id}` | Kimlik, bütçe, revizyon |
| Genel durum | `GET /api/v2/projects/{id}/overview` | Hazırlık ve özet |
| Veri/sürüm metadatası | `GET /api/v2/projects/{id}/data-catalog` | Sunum amaçlı dar metadata projection |
| Hazırlık | overview içindeki accepted readiness | Domain ve senaryo durumu |
| Upload/map/confirm | mevcut `/imports` rotaları | Açık onaylı ImportService akışı |
| Bilimsel girdi | mevcut `/scientific-inputs` | Proje kapsamlı veri |
| Önizleme | `POST .../analysis-preview` | Kanıt seçimi ve preview pinning |
| Çalıştırma | `POST .../analyses` | Accepted application service |
| Geçmiş | `GET .../analyses` | Sayfalı immutable run listesi |
| Kayıtlı sonuç | `GET .../analyses/{run_id}` | Sonuçları yeniden açma |
| Provenance | stored run response ve provenance endpoint | Teknik kanıt |
| XLSX şablonları | `GET /projects/templates/{filename}` | Allowlist dosya sunumu |

Yeni `data-catalog` endpoint'i bilimsel kayıtları veya hesapları döndürmez; yalnız proje kapsamlı dataset/import metadatasını projection olarak sunar. Şablon endpoint'i mevcut repository dosyalarını değişmeden indirir.
