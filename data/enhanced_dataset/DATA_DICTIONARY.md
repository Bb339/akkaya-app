# Akkaya Dataset – Data Dictionary (Enhanced)

### csv/parcel_assumptions.csv
- Purpose: Parcel-level static attributes used for spatial selection, soil class linkage and default irrigation efficiency.
- Key columns: parcel_id, soil_unit_code, soil_group, land_capability_class, village, lat_deg, lon_deg, irrig_efficiency_default

### csv/soil_params_assumed.csv
- Purpose: Soil parameter table (assumed) used for water holding capacity and infiltration proxies.
- Key columns: soil_group, awc_mm_per_m, root_depth_default_m, infiltration_mm_h, field_capacity_frac, assumed_texture

### csv/crop_params_assumed.csv
- Purpose: Crop parameter table (assumed) used for ETc computation (Kc stages) and phenology lengths.
- Key columns: crop, kc_ini, kc_mid, kc_end, p_ini, p_dev, p_mid, p_late, gdd_base_c

### csv/monthly_climate_all_parcels.csv
- Purpose: Monthly climate per parcel (2000–2025) used for ET0/ETc, effective rainfall, stress indices.
- Key columns: month, parcel_id, tavg_c, tmin_c, tmax_c, rh_avg, wind_ms, rain_mm, eto_mm, sun_h

### csv/akkaya_reservoir_monthly_backend.csv
- Purpose: Reservoir monthly storage and derived irrigation demand summaries used as water constraint.
- Key columns: month, storage_m3, fill_pct, evap_m3_est, irrigation_m3_baseline, total_demand_m3_sen1, total_demand_m3_sen2

### csv/senaryo1_backend_seasons.csv
- Purpose: Scenario-1 candidate parcel-season-crop options with computed water and economics metrics (ready for optimization).
- Key columns: year, parcel_id, season, crop, area_da, profit_tl, water_m3_calib_gross, water_m3_calib_net, etc_mm_sum, peff_mm_sum, nir_mm_sum

### csv/senaryo2_backend_seasons.csv
- Purpose: Scenario-2 candidate options (same schema as Scenario-1) with different constraints/assumptions.
- Key columns: year, parcel_id, season, crop, area_da, profit_tl, water_m3_calib_gross, water_m3_calib_net

### csv/delivery_capacity_monthly_assumed.csv
- Purpose: (NEW) Assumed monthly delivery/pumping capacity for realistic water distribution constraints.
- Key columns: month, max_delivery_m3_assumed

### csv/irrigation_methods_assumed.csv
- Purpose: (NEW) Assumed irrigation method efficiencies and rough cost parameters (for scenario analysis).
- Key columns: method, application_efficiency, conveyance_efficiency, typical_total_efficiency, capex_tl_per_da, opex_tl_per_da

### csv/water_quality_monthly_assumed.csv
- Purpose: (NEW) Proxy water quality time series (EC) to enable salinity-risk constraints.
- Key columns: month, ec_dS_m_assumed, water_quality_class_assumed

### csv/crop_suitability_assumed.csv
- Purpose: (NEW) Proxy crop suitability by land capability class (LCC).
- Key columns: land_capability_class, crop, suitability_score_assumed

### csv/rotation_rules_default.csv
- Purpose: (NEW) Default crop-rotation rules, can be implemented as hard constraints or penalties.
- Key columns: rule_id, type, description, penalty_weight

### csv/crop_family_map.csv
- Purpose: (NEW) Mapping from crop to crop family used by rotation rules.
- Key columns: crop, crop_family

### csv/objective_weight_sets.csv
- Purpose: (NEW) Predefined weight sets for multi-objective optimization (water vs profit).
- Key columns: weight_set, alpha_water, beta_profit

### csv/crop_economics_history_TEMPLATE.csv
- Purpose: (NEW, TEMPLATE) Crop economics history table to support time-varying prices/costs and deflation.
- Key columns: year, crop, yield_ton_per_ha, farmgate_price_tl_per_ton, variable_cost_tl_per_ha

### csv/price_deflators_TEMPLATE.csv
- Purpose: (NEW, TEMPLATE) Deflator indices to convert nominal TL to real TL (e.g., 2025=100).
- Key columns: year, gdp_deflator_index_2025_100, cpi_index_2025_100

### csv/validation_observations_TEMPLATE.csv
- Purpose: (NEW, TEMPLATE) Field validation observations for 2–3 parcels and 1–2 seasons.
- Key columns: year, parcel_id, crop, observed_irrigation_m3, observed_yield_ton, observed_profit_tl

