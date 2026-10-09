# Data Crosswalk

| V1 source field | Source module/file | Project Data file | Project Data column | Unit | Transformation | Validation rule |
|---|---|---|---|---|---|---|
| parcel id | `parsel_su_kar_ozet.csv` | `analysis_units.csv` | `external_id` | - | direct | unique/non-null; 179 |
| area | source summary + accepted overrides | `analysis_units.csv` | `area_da` | da | direct | positive; total 134,919 da |
| current crop | `parsel_su_kar_ozet.csv` | `analysis_units.csv` | `current_crop` | - | canonical catalog label | crop exists in catalog |
| current water/profit | `parsel_su_kar_ozet.csv` | `scientific_s1.csv` | `unit_parameters.*` | m3, TRY | typed long-form | totals match V1 invariants |
| crop catalog | `urun_parametreleri_demo.csv` | `crops.csv` | `crop_name` | - | direct | 58 unique crops |
| crop economics | `urun_parametreleri_demo.csv` | economics and crop economic tables | typed economic columns | TRY, ton | unit-preserving projection | unknown DUT yield stays unavailable |
| candidate matrix | `excel_derived/combined_parcel_candidate_matrix_2024.csv` | `candidates.csv` | candidate fields | m3/da, TRY/da | direct/canonical crop label | 6,859 unique unit-crop rows |
| scenario S1 resources | accepted V1 loaders/registries | `scientific_s1.csv` | section/record/field/value | source-specific | deterministic long-form | atomic section import |
| scenario S2 resources | enhanced dataset CSV resources | `scientific_s2.csv` | section/record/field/value | source-specific | deterministic long-form | one atomic 52,762-row import |
| annual modeled demand | current-pattern source total | `annual_water_supply.csv` | `amount` | m3/year | calculated reference | 100,700,080.81; not official allocation |
| monthly reservoir context | `akkaya_reservoir_monthly_backend.csv` | `monthly_water_supply.csv` | `amount` | m3/month | direct year filter | 12 months; distinct from demand |
| delivery capacity | `delivery_capacity_monthly_assumed.csv` | `delivery_capacity.csv` | `capacity` | m3/month | direct year filter | 12 months; proxy authority |
| crop water | `crop_params_assumed.csv` | `crop_water_parameters.csv` | Kc/stage fields | coefficient/days or fraction | mode derived from source total | 58 crops; assumed authority |
| phenology rule | `s1_crop_calendar_rules.json` | `crop_phenology.csv` | `mode`, `notes` | - | `REFERENCE_RULE`; no dates invented | label-only proxy semantics |
| analysis-unit geometry | `geojson_yeni_klasor4/*.geojson` + registry | `geometries.geojson` | `properties.external_id`, geometry | WGS84 | source geometry only | 178 exact IDs; P138 explicitly absent |
