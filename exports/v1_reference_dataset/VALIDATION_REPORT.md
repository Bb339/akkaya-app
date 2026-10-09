# Validation Report

All files were processed through ImportService upload, validation and explicit confirmation.

| filename | domain | row_count | key_count | required_columns | missing_columns | duplicate_keys | unit_validation | authority_class | status |
|---|---:|---:|---:|---|---|---:|---|---|---|
| crops.csv | crops | 58 | 58 | crop_name | NONE | 0 | PASS | source-declared; preserved | APPLIED r1 |
| analysis_units.csv | analysis_units | 179 | 179 | external_id, settlement, area_da, current_crop | NONE | 0 | PASS | source-declared; preserved | APPLIED r2 |
| economics.csv | economics | 58 | 58 | crop_name, year, yield_per_da, net_profit_per_da | NONE | 0 | PASS | source-declared; preserved | APPLIED r3 |
| water_budget.csv | water_budget | 1 | 1 | amount, unit, kind, source | NONE | 0 | PASS | source-declared; preserved | APPLIED r4 |
| candidates.csv | candidates | 6859 | 6859 | analysis_unit_id, crop, water_requirement_m3_da, profit_per_da, yield_ton_da, allowed, rotation_status, suitability, source | NONE | 0 | PASS | source-declared; preserved | APPLIED r5 |
| scientific_s1.csv | scientific_inputs | 890 | 890 | section, record_id, field, value_type, value, source | NONE | 0 | PASS | source-declared; preserved | APPLIED r6 |
| scientific_s2.csv | scientific_inputs | 52762 | 52762 | section, record_id, field, value_type, value, source | NONE | 0 | PASS | source-declared; preserved | APPLIED r7 |
| annual_water_supply.csv | annual_water_supply | 1 | 1 | planning_year, amount, unit, authority_class | NONE | 0 | PASS | source-declared; preserved | APPLIED r8 |
| monthly_water_supply.csv | monthly_water_supply | 12 | 12 | planning_year, month, amount, unit, authority_class | NONE | 0 | PASS | source-declared; preserved | APPLIED r9 |
| delivery_capacity.csv | delivery_capacity | 12 | 12 | planning_year, month, capacity, source_unit, canonical_unit, capacity_basis, authority_class | NONE | 0 | PASS | source-declared; preserved | APPLIED r10 |
| environmental_release.csv | environmental_release | 1 | 1 | planning_year, release_form, value, source_unit, canonical_unit, authority_class | NONE | 0 | PASS | source-declared; preserved | APPLIED r11 |
| conveyance_efficiency.csv | conveyance_efficiency | 1 | 1 | planning_year, period, efficiency, scope, authority_class | NONE | 0 | PASS | source-declared; preserved | APPLIED r12 |
| perennial_irrigation_requirement.csv | perennial_irrigation_requirement | 14 | 14 | planning_year, crop, value, source_unit, canonical_unit, confidence, method, authority_class | NONE | 0 | PASS | source-declared; preserved | APPLIED r13 |
| crop_yield.csv | crop_yield | 57 | 57 | crop, planning_year, observation_year, authority_class, currency, yield_value, yield_unit | NONE | 0 | PASS | source-declared; preserved | APPLIED r14 |
| crop_sale_price.csv | crop_sale_price | 58 | 58 | crop, planning_year, observation_year, authority_class, currency, price, price_unit | NONE | 0 | PASS | source-declared; preserved | APPLIED r15 |
| crop_cost_components.csv | crop_cost_components | 58 | 58 | crop, planning_year, observation_year, authority_class, currency, cost_category, amount, unit | NONE | 0 | PASS | source-declared; preserved | APPLIED r16 |
| crop_net_profit.csv | crop_net_profit | 58 | 58 | crop, planning_year, observation_year, authority_class, currency, calculation_method | NONE | 0 | PASS | source-declared; preserved | APPLIED r17 |
| seasonal_economics.csv | seasonal_economics | 306 | 306 | crop, planning_year, observation_year, authority_class, currency, season, yield_unit, price_unit, cost_unit, net_profit_unit | NONE | 0 | PASS | source-declared; preserved | APPLIED r18 |
| crop_water_parameters.csv | crop_water_parameters | 58 | 58 | crop_identity, applicable_year, geographic_scope, kc_ini, kc_mid, kc_end, stage_value_mode, p_ini, p_dev, p_mid, p_late, authority_class, source, source_reference | NONE | 0 | PASS | source-declared; preserved | APPLIED r19 |
| crop_phenology.csv | crop_phenology | 58 | 58 | crop_identity, applicable_year, geographic_scope, season, mode, authority_class, source, source_reference | NONE | 0 | PASS | source-declared; preserved | APPLIED r20 |
| geometries.geojson | geometries | 178 | 178 | external_id, geometry | NONE | 0 | PASS | source-declared; preserved | APPLIED r21 |

- Active revision: **21**
- REFERENCE_DEMO / S1: **READY_WITH_WARNINGS**
- REFERENCE_DEMO / S2: **READY_WITH_WARNINGS**
- Geometry: **178/179**; P138 is explicitly NOT_PROVIDED and non-blocking.
