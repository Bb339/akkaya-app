# Hazırlık arayüzü

Hazırlık verisi doğrudan kabul edilmiş readiness yanıtından okunur. UI bilimsel hazırlık hesabı yapmaz. S1/S2 genel durumu ile VERIFIED_INSTITUTIONAL engel listesi ayrı gösterilir.

Her domain için `dataset_selected`, `selection_complete`, `dataset_valid`, `consumer_available`, `engine_connected` ve `connection_state` ayrı eksenlerdir. Makine durumu ayrıntıda korunur; engel nedeni Türkçe iş akışında görünür. Ekonomi kartı `selected_dataset_types`, `required_dataset_types` ve `missing_required_datasets` alanlarını ayrıca sunar. Verified run düğmesi hazır olmayan senaryoda kapalı kalır.
