# Stored-run to native V1 surface mapping

No PROJECT_DATA-only result workspace exists. Stored-run fields are projected into the frozen document's existing V1 destinations.

| Backend field | Existing V1 destination | Missing-value behavior |
|---|---|---|
| `total_profit_tl` | `bProfitScenario`, profit chart | `SAĞLANMADI / NOT PROVIDED` |
| `authoritative_water_m3` | `bWaterScenario`, water chart, official water table | `SAĞLANMADI / NOT PROVIDED` |
| `optimizer_water_m3` | water chart and `basinSummaryNote` | `SAĞLANMADI / NOT PROVIDED` |
| `planning_year_profile_water_m3` | water chart and `basinSummaryNote` | `SAĞLANMADI / NOT PROVIDED` |
| `verified_profile_water_m3` | water chart and `basinSummaryNote` | `SAĞLANMADI / NOT PROVIDED` |
| `efficiency_tl_per_m3` | `bEffScenario`, benchmark table/chart | `SAĞLANMADI / NOT PROVIDED` |
| `annual_budget_validation` | `globalBudgetBadge`, `globalBudgetStatus`, `riskSeparationBox`, official water table | Explicit unavailable status |
| monthly supply/delivery validation | existing `deliveryBox` monthly chart and `riskSeparationBox` | Explicit unavailable state |
| `crop_shares`, `top_crops`, `hhi` | recommended/current pattern, official scenario table, benchmark annotation | Explicit not-calculated cells |
| warnings | `deliveryBox`, `riskSeparationBox`, `decisionRationale` | “Backend uyarısı yok” |
| `presentation_units` | selected-unit metric cards, `productCards`, current/recommended tables, official unit tables | Explicit unavailable values |
| project/run provenance | `activeFilesBadges`, `buildMetaBox`, `activeFilesNote` | Explicit unavailable keys |
| selection hash and run id | existing expandable `buildMetaBox` provenance detail | `SAĞLANMADI / NOT PROVIDED` |
| algorithm/scenario/objective/seed | native summary/status surfaces plus provenance detail | Explicit unavailable values |
| authority/classification | provider badge and existing provenance surface | Explicit project authority |

The legacy hidden `v1-project-result` sink remains retired. `#v1-native-project-results` and every former child panel were removed rather than moved, renamed, collapsed or hidden.
