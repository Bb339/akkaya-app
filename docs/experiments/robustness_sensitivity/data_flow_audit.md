# Experimental data-flow audit

| Factor | Source value | Runtime consumer | Transformation | Objective effect | Result field | Connected |
|---|---|---|---|---|---|---|
| Annual water budget | Project budget and frozen reservoir-delivery resources | configuration and optimizer budget handling | explicit `water_budget_ratio` | feasibility penalties and guards | budget, feasibility, total water | true |
| Net profit per da | candidate, seasonal, catalog, fallback and unit profit fields | S1/S2 candidate matrices and final projection | one in-memory multiplier on copied bundle values | profit score and reported profit | total profit, TL/m3, composition | true |
| Sale price | descriptive source columns | no independent accepted-path consumer | none | none | none | false |
| Yield | descriptive source columns | no independent accepted-path consumer | none | none | none | false |

S1 reports the current-pattern calculated gross-demand budget (100,700,080.81 m3 at ratio 1.0), whereas S2 reports the reservoir-derived engine scenario budget (10,401,986.556 m3 at ratio 1.0). The protected-perennial critical multiplier therefore applies only to the S2 annual-budget boundary.
