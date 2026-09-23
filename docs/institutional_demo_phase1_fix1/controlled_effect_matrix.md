# Controlled effect matrix

All fixtures are SYNTHETIC / NOT_OFFICIAL. Evidence is asserted by tests/test_institutional_demo_phase1.py.

| Input | v1 -> v2 | Consumer | Observed result | Verdict |
|---|---|---|---|---|
| annual_supply | 20000 m3/year -> 60000 m3/year | materialize_verified_document annual usable-budget calculation | usable optimizer budget changed to 54000 m3 | CONNECTED |
| monthly_supply | 5000 m3/month -> 1 m3/month | validate_verified_result monthly supply constraint | validation object changed and insufficient months fail | CONNECTED |
| delivery_capacity | 5000 m3/month -> 1 m3/month | validate_verified_result delivery constraint | status became FAIL and overall_feasible false | CONNECTED |
| environmental_release | ratio 0.10 -> ratio 0.50 | materialize_verified_document single release deduction | budget became 30000 m3; deduction applied once | CONNECTED |
| conveyance_efficiency | 0.83 -> 0.45 | monthly_gross_demand_m3_da gross/net conversion | candidate water_requirement_m3_da increased | CONNECTED |
| net_profit | 1000..1700 TL/da -> 6000..6700 TL/da | verified candidate economics materialization and optimizer objective | first candidate profit_per_da changed | CONNECTED |
| crop_Kc_stage | Kc 0.4/1.0/0.5; days 20/30/40/20 -> Kc 0.9/1.4/0.8; same stages | monthly_gross_demand_m3_da and _kc | candidate water_requirement_m3_da changed | CONNECTED |
| phenology | 2025-03-01..2025-06-30 -> 2025-04-01..2025-08-31 | monthly_gross_demand_m3_da and _dates | candidate water_requirement_m3_da changed; cross-year 2024-10-01..2025-06-30 preserved in S2 | CONNECTED_FOR_S1_AND_S2 |
| perennial_requirement | ELMA crop default 120 m3/da -> GX-001 exact override 900 m3/da | select_perennial_requirement | GX-001 used 900 m3/da while another ELMA unit used 120 m3/da; duplicates rejected | CONNECTED_FOR_S2 |
