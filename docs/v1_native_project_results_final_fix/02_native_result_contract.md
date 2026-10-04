# Native result contract

For PROJECT_DATA, `#v1-project-result` is emptied, hidden, and marked `aria-hidden=true`. Its former summary, water, budget, warning, monthly, crop, unit and provenance children are never result targets.

The sole project result presentation is `#v1-native-project-results`, inserted into the existing visible V1 metrics card after the basin summary. It renders backend-owned stored-run values for:

- run identity, algorithm, objective, scenario, seed, authority and feasibility;
- optimizer, authoritative, planning-year and full-season water, plus reconciliation;
- annual budget demand, available budget, status and backend reason;
- monthly demand, supply, delivery capacity and status;
- backend warnings;
- crop shares and HHI;
- selected analysis-unit crop, water, profit, warnings and geometry status;
- project/run provenance and selection hash.

Missing values use explicit `SAĞLANMADI / NOT PROVIDED`, `HESAPLANMADI / NOT CALCULATED`, or `UYGULANAMAZ / NOT APPLICABLE` states. The browser performs formatting and presentation only.
