# Water data replacement contract

Bu sözleşme gelecekte kurumlardan alınacak su verilerini Project sistemi içinde doğrulamak, sürümlemek ve açık onayla etkinleştirmek içindir. Bu milestone’da kaydedilen dataset’ler bilimsel engine tarafından kullanılmaz.

## Ortak metadata

Her kayıt `authority_class` taşır. Desteklenen ek alanlar `source_authority`, `source_institution`, `source_reference`, `source_document`, `source_date`, `data_period`, `measurement_method` ve `notes` alanlarıdır. Uygulama confirm sırasında `uploaded_filename`, `file_hash` ve `import_batch_id` alanlarını ekler. `MEASURED`, `OFFICIAL_ALLOCATION` ve `OFFICIAL_HISTORICAL` kayıtları source institution ile source reference veya document olmadan geçersizdir.

## Dataset sözleşmeleri

| Import data type | Kimlik ve dönem | Canonical değer/birim | Bütünlük |
|---|---|---|---|
| `annual_water_supply` | `planning_year` | `amount_m3`, `m3/year` | Tek pozitif ve sonlu yıllık kayıt |
| `monthly_water_supply` | `planning_year`, `month` | `amount_m3`, `m3/month` | Aynı planlama yılında 12 benzersiz ay; sıfır fiziksel olarak kabul edilir |
| `delivery_capacity` | `planning_year`, `month` | `capacity_m3`, `m3/month` | 12 benzersiz ay ve açık `capacity_basis` |
| `environmental_release` | Yıllık/aylık ratio veya 12 aylık release | `ratio` ya da `release_m3` | Fiziksel release ile ratio aynı dataset’te karıştırılmaz |
| `conveyance_efficiency` | `planning_year`, `period`, `scope` | `efficiency`, ratio | `0 < efficiency <= 1` |
| `perennial_irrigation_requirement` | Crop; isteğe bağlı unit ve month | `gross_irrigation_m3_da`, `m3/da` | Crop zorunlu; monthly kayıt yoksa aylık değer türetilmez |

Perennial çözümleme önceliği analysis-unit kaydı, ardından crop kaydıdır. Aynı scope içinde istenen ayın açık kaydı yıllık kaydın önündedir. Unit-level yıllık kayıt crop-level aylık kaydın önündedir; böylece daha özgül saha kaydı korunur.

## Dataset version modeli

Her confirm işlemi yeni bir `dataset_id` ve artan `version` üretir. Dataset `status`, `authority_class`, `valid_from`, `valid_to`, `uploaded_at`, `confirmed_at`, `supersedes` ve `superseded_by` taşır. Bir data type için yalnız `active_dataset_id` niteliğindeki pointer etkindir. Eski dataset silinmez; `inactive` olarak korunur.

## Phase 3 request mapping

| Phase 3 requested variable | Canonical import |
|---|---|
| Official annual irrigation allocation | `annual_water_supply` |
| Official monthly allocation/release schedule | `monthly_water_supply` |
| Reservoir usable irrigation supply | Annual veya monthly supply; source metadata ile scope açıklanır |
| Canal design/operational capacity | `delivery_capacity`, uygun `capacity_basis` |
| Delivered-water/SCADA | `delivery_capacity`, `measured_delivery`, `MEASURED` |
| Environmental release obligation | `environmental_release` |
| Scheme conveyance loss/efficiency | `conveyance_efficiency` |
| Crop/orchard irrigation requirement | `perennial_irrigation_requirement` |

2024 `cekis_su_hacmi_hm3` anomalisi bu sözleşmeye kaynak olarak alınmaz ve `UNKNOWN` kalır.
