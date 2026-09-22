# Experimental data-flow audit

+| Factor | Source value | Runtime consumer | Transformation | Objective effect | Result field | Connected |
+|---|---|---|---|---|---|---|
+| Annual water budget | Project water budget / frozen reservoir delivery resources | `configuration` → frozen optimizer budget handling | Explicit `water_budget_ratio` | Feasibility penalties and guards | `water_budget_m3`, `feasible`, total water | true |
+| Net profit per da | `candidate_options.profit_tl_da`; seasonal `environment.s1/s2.profit_tl` | S1 candidate matrix; S2 seasonal candidate matrix | In-memory uniform multiplier on copied immutable bundle | Profit score and reported profit | `total_profit_tl`, TL/m3, crop composition | true |
+| Sale price | Frozen descriptive candidate/seasonal columns | No independent consumer on accepted execution path | none | none | none | false |
+| Yield | Frozen descriptive candidate/seasonal columns | No independent consumer on accepted execution path | none | none | none | false |
+| Cost | Embedded upstream in catalog-derived direct net profit | No independent runtime cost perturbation consumer | none | none | none | false |
+
+S1 reports the current-pattern calculated gross-demand budget (100,700,080.81 m3 at ratio 1.0), whereas S2 reports the reservoir-derived engine scenario budget (10,401,986.556 m3 at ratio 1.0). The protected-perennial critical multiplier therefore applies to the S2 annual-budget boundary.
+