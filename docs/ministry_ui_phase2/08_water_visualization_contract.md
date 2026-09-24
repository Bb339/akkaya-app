# Su görselleştirme sözleşmesi

Dört değer ayrı KPI olarak sunulur: `optimizer_water_m3`, `verified_profile_water_m3`, `planning_year_profile_water_m3`, `authoritative_water_m3`. TL/m³ paydası `efficiency_tl_per_m3_denominator` alanından aynen gösterilir. Tam sezon ile planlama takvim yılı birleştirilmez.

Yıllık bütçe, aylık arz, aylık teslim ve su uzlaştırma doğrulamaları ayrı kartlardır. Aylık grafik backend `demand_m3`, `usable_supply_m3` ve `capacity_m3` serilerini biçimlendirir. `violating_months` listesi “ARZ AŞILDI” veya “TESLİM KAPASİTESİ AŞILDI” olarak tabloda görünür. Panel, bunun post-run doğrulama olduğunu ve optimizer kısıtı gibi sunulmadığını belirtir.
