# Table 9. Data provenance and authority classification

| variable                        | value_or_range                                        | classification            | model_role                 | source                                                              |
| ------------------------------- | ----------------------------------------------------- | ------------------------- | -------------------------- | ------------------------------------------------------------------- |
| Analysis-unit area/current crop | 2024 parcel records                                   | DERIVED/Excel-sourced     | Akkaya baseline            | data/parcel_master.csv                                              |
| Current gross irrigation demand | 100,700,080.81 m3                                     | CALCULATED                | Planning reference         | data/water_context.csv                                              |
| Current catalog-derived profit  | 1,041,499,119.212 TL                                  | CALCULATED                | Planning reference         | robustness/experiment_manifest.json                                 |
| Crop coefficients/stages        | 69-row table; 47 identities intersect runtime catalog | ASSUMED/LITERATURE/PROXY  | Scientific input with gaps | data/enhanced_dataset/csv/crop_params_assumed.csv                   |
| Crop economics                  | 58-crop catalog                                       | DERIVED/ASSUMED           | Optimizer inputs           | data/urun_parametreleri_demo.csv                                    |
| Reservoir annual baseline       | 11,557,762.84 m3                                      | NOT_ESTABLISHED authority | Scenario context           | water_supply_phase3/annual_water_reconciliation.json                |
| Monthly delivery capacity       | 12-month proxy                                        | DERIVED                   | Constraint diagnostic      | water_supply_phase3/monthly_water_reconciliation.csv                |
| Institutional package           | 21 files; 24 units; 8 crops                           | SYNTHETIC_DEMO            | Ingestion validation only  | v1_native_project_integration_fix2/05_full_visual_demo_manifest.csv |

**Source lineage:** accepted contracts/audits

**Interpretive boundary:** Synthetic demo excluded from Akkaya agronomic claims.
