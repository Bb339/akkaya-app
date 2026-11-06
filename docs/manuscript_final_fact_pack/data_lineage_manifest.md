# Data lineage manifest

Derived artifacts are direct, read-only transformations. No source file was modified.

| Source | Used for |
|---|---|
| data/parcel_master.csv | Tables 1, 5, 8; Figures 5, 9 |
| data/urun_parametreleri_demo.csv | Table 2; Figure 4 |
| data/excel_derived/combined_parcel_candidate_matrix_2024.csv | candidate counts/model fields |
| data/water_context.csv | current-demand reference |
| docs/audits/water_supply_phase3/annual_water_reconciliation.json | budget/authority facts |
| docs/audits/water_supply_phase3/monthly_water_reconciliation.csv | Table 7; Figure 7 |
| docs/experiments/robustness_sensitivity/experiment_manifest.json | baseline/run design |
| docs/experiments/robustness_sensitivity/seed_variability.csv | Tables 5–6; Figures 5–6 |
| docs/experiments/robustness_sensitivity/run_level_results.csv | feasible rates; Figure 9 |
| docs/v1_native_project_integration_fix2/05_full_visual_demo_manifest.csv | 21-file synthetic package |
| data/_geojson_index.json and listed GeoJSON | Figure 1 |

**Transformations:** settlement/crop group sums; percentage change from accepted current baseline; TL/m³ as profit/water; accepted mean/SD/CV copied from summaries; feasible rate counted from active rows; direct polygon rendering. No interpolation or smoothing.

**Generation method:** one-off Python 3.11 using pandas 2.3.1, NumPy, and Matplotlib 3.10.7. It read the named sources and wrote only below this fact-pack folder. Figure 9 uses immutable run \`53e613e87b8565ad884a\`.

## SHA-256

- `data/parcel_master.csv`: `1bf0f15d55f722ace2e5604039b1fb98bc576984485f6846eb79cf80e4b54c01`
- `data/urun_parametreleri_demo.csv`: `42e8c0711b1f16abe2e36c5ed28e971bd21e05c1e9a3ab98e672cd68bb583c19`
- `data/excel_derived/combined_parcel_candidate_matrix_2024.csv`: `022669d634b29ed551ed6e6344c212c1e60e47db1efc41a157c4073c4424df6b`
- `data/water_context.csv`: `322d982476952186a2389e6408494be4c93404144ec94834c992a1353fe1bc67`
- `docs/audits/water_supply_phase3/annual_water_reconciliation.json`: `93a86c4dd28faf9dd48f09c279e3490e932748c3e13537ee2e2cf8f7310f2b54`
- `docs/audits/water_supply_phase3/monthly_water_reconciliation.csv`: `308923ee8fb5de52b0434929d29bfd777f9ab62c39fd5bb4683b4bdcf034e658`
- `docs/experiments/robustness_sensitivity/experiment_manifest.json`: `673c6563e108e359675046b0b88a004dfa8e5fea69c6d695ee1609830f6ea711`
- `docs/experiments/robustness_sensitivity/seed_variability.csv`: `4b6d284ac8d81a5c344a5470a1bd9902b011995f0228dffee39ac6d3117092d9`
- `docs/experiments/robustness_sensitivity/run_level_results.csv`: `8c8b746300b834bf63db8261e708b93bc96e78941e015dd510b5628fb65c8208`
- `docs/v1_native_project_integration_fix2/05_full_visual_demo_manifest.csv`: `295ca1d16ee5905790c739a7300004b0c791850e54f73a16148a782b5e0f8f21`
- `data/_geojson_index.json`: `8a8cdf61054dd0e3f5e4264345ffe282a85585ceec456b90d5b811a78715f536`

Additional Table 2 identity/parameter sources:
- `data/enhanced_dataset/csv/crop_params_assumed.csv`: `dc6bacdc142aee6e01e867b42baa74043597a2b4843638935fba1d1068b81ead`
- `docs/audits/crop_identity_phenology_phase7/runtime_parameter_resolution.csv`: `3ea8c858705b8fa0d26875bc793239dfa02605ab94497b94879df977db807f51`
