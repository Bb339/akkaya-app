# Phase 4 — Scientific Economics Provenance & Identity Audit

## Scope and result

This is a diagnosis-only audit of commit `5018bde15d659e415a106b7b1bae949dc011ccbc`. No economic value, optimizer, catalog, water value, or production source was changed.

## Main findings

- The 179 unit baseline profit independently sums to **1,041,499,119.212 TL** and every row equals `area_da × catalog net_profit_per_da` within 0.01 TL/da. It is therefore a derived baseline, not independent unit accounting evidence.
- The 58-crop catalog is complete internally, but its economics are proxy/old-catalog values. A `2024` filename is not proof of official authority.
- S1 production uses `combined_parcel_candidate_matrix_2024.csv`: `profit_tl_da × feasible_area_da` enters the objective. Project Economics records do not replace it.
- S2 uses seasonal `profit_tl / area_da`, then applies suitability and profit-realism model transforms, and finally multiplies once by planned area. No double area scaling was found.
- The reported approximately 45 crop/profit mismatches were **not reproduced**. Numeric conflicts: **0**. Across 232 catalog-to-source identity comparisons: 214 exact, 12 normalized spacing matches, 6 missing-right records.
- Cost reconciliation has **7 matches, 50 formula mismatches, and 1 missing cost rule (DUT)** at 0.01 TL/da. Cost shares are proxy allocation rules and cannot repair this provenance gap.
- Turp is consistently **4,000 TL/da** in catalog, matrix, S1 seasonal, S2 primary, and current P110. No 6,000 TL/da Turp profit was found. The adjacent value is **6 TL/kg sale price**; treating it as 6,000 TL/da is a unit/interpretation error.
- Turp ranks at the 29.8th profit percentile and 87.7th TL/m³ percentile among matrix crops, with 43 raw candidate units. S1 may copy the regional median row to other compatible annual parcels, so runtime availability can exceed raw coverage. Its economic contribution is material but the source remains proxy.

## Unit and year checks

- All 6,859 matrix rows satisfy `profit_tl_total = profit_tl_da × area_da`, `production_ton = yield_ton_da × area_da`, and `yield_kg_da_model / 1000 = yield_ton_da` within stated numeric tolerances. No ton/kg, per-da/total, double-area, TRY/TL, or hidden foreign-currency conversion defect was found.
- The catalog, matrix, S1, and S2 economic layers are labeled 2024. The repository also contains 2023 district crop-pattern context, but it is not the profit source used by these optimizer paths. Fallback profit parameters have unknown year.
- No inflation normalization is applied. Treating all packaged nominal values as a common 2024 price basis is an assumption until the underlying workbooks and dates are verified.

## Current versus candidate economics

`current_profit` is stored as a unit total, but all 179 totals are mechanically equal to unit area times the same crop-level catalog rate. Candidate profit is a projected crop-level TL/da copied into unit-crop matrix rows. The values are arithmetically comparable because they share rates, yet neither side is independent observed farm-account evidence.

## S1 versus S2

Raw source rates agree wherever both sources contain a crop. S1 matrix optimization retains the raw candidate TL/da. S2 derives TL/da from seasonal totals and then applies suitability plus profit-realism discounts; the difference between raw S1 and effective S2 values is expected model behavior. Secondary economics exist for only four crop identities, so most missing secondary cells become infeasible or use one of nine explicit fallback parameters.

## Identity method

The catalog was used as the 58-product anchor. Raw names and Unicode/spacing/punctuation-normalized keys were retained. Candidate matrix, cost rules, S1 seasonal, and S2 seasonal sets were compared independently. Numeric identity used catalog TL/da versus matrix TL/da and seasonal `profit_tl / area_da`, tolerance 0.01 TL/da.

## Finding classification

- **DATA QUALITY ISSUE / SOURCE-PROVENANCE GAP:** proxy catalog rates, undocumented net-profit methodology, sparse S2 secondary coverage.
- **DATA IDENTITY ISSUE:** `KİMYON` absent from matrix and seasonal sources; `DUT` absent from cost and seasonal sources; three harmless spacing variants.
- **UNIT ISSUE:** possible confusion of Turp 6 TL/kg with 6,000 TL/da; no computation path makes that conversion.
- **MODEL ASSUMPTION:** S2 suitability and profit-realism discounts change source profit before objective use.
- **DOCUMENTATION GAP:** fallback-selected cells and transformed effective economic authority are not row-visible.
- **SOFTWARE BUG:** no new economics software defect proven by this audit.

## Scientific boundary

The optimizer may be described as finding Turp economically attractive under the packaged 2024-labeled proxy assumptions. The audit does not support a claim that Turp is truly the most profitable market crop or that projected basin profit is realizable.

## Verification

- Audit determinism/source-mutation guard: `1 passed in 10.39s` (latest run).
- Full repository suite: `237 passed, 1 failed, 7 deselected in 972.75s`.
- The only failure is `test_s2_high_budget_can_return_feasible_two_crop_plan`: expected `ok`, observed `no_feasible_two_crop_plan`. It is an **INHERITED BASELINE FAILURE** previously reproduced unchanged at the Phase 3 and Water Contract baselines; it is outside this audit's scope.
