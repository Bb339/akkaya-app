# Economic overlay lineage

The Phase 2 overlay implements the original preregistered uniform direct-input net-profit shock. It changes copied values inside a disposable scientific bundle; production files and frozen sources remain byte-identical.

The economic family perturbs connected direct net-profit inputs while preserving the frozen engine unchanged. Each scaled bundle is passed directly to `kds.science.execution.execute`. The frozen `_apply_profit_realism` thresholds and caps receive the scaled inputs under normal production semantics. Output response is observed, not forced to be linear.

| Source object | Profit field | Frozen consumer | Overlay transformation | Result contribution |
|---|---|---|---|---|
| candidate_options / regional_candidate_options | profit_tl_da, profit_tl_total | S1 matrix and candidate selection | × (1 + shock) | objective profit and projected crop profit |
| environment.s1 / environment.s2 | profit_tl, profit_per_da, profit_tl_da | primary and secondary seasonal matrices | × (1 + shock) | seasonal objective and plan rows |
| crop_catalog | profitPerDa | S2 perennial locks, fallbacks and final-plan projection | × (1 + shock) | locked/final crop profit |
| fallback_crop_parameters | profit_per_da | missing seasonal-cell fallback | × (1 + shock) | fallback candidate profit |
| crop_table | direct net-profit aliases | catalog/table fallback paths | × (1 + shock) | fallback plan profit |
| units | profit_tl | scientific unit resource consumer | × (1 + shock) | connected unit profit input |
| unit_summary | mevcut_kar_tl | not consumed on the scientific decision path | not perturbed | none |
| ScientificInputBundle.candidates | CandidateOption.profit_per_da and derived water_productivity | canonical candidate consumer | × (1 + shock) | candidate objective inputs |

Price and yield remain disconnected from the independent perturbation contract:
`PRICE_SENSITIVITY_NOT_EXECUTABLE_ON_FROZEN_ENGINE` and
`YIELD_SENSITIVITY_NOT_EXECUTABLE_ON_FROZEN_ENGINE`.

## Superseded evidence

The five original S2 economic runs and the five Phase 1 monkeypatch runs remain immutable historical evidence. Phase 1 runs are classified `HISTORICAL_INVALID_FOR_ACTIVE_PUBLICATION`. Neither version contributes to active summaries, tables, or figures; the five Phase 2 frozen-engine executions replace the same logical scenarios.
