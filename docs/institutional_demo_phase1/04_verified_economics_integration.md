# Verified economics integration

Economic selection uses an exact `data_type|planning_year|geographic_scope|catalog` active pointer. Records must be confirmed, active, current and use an authority in the existing verified-input policy. `crop_net_profit` must cover every project crop. S2 additionally requires verified `seasonal_economics`.

Net profit is copied into candidate profit, current-pattern profit, project economics and matching seasonal rows before `build_bundle`. Optional analysis-unit economics overrides only the matching current-pattern unit. Calculated-profit dependency validation remains the responsibility of the existing import contract; stale dependencies cannot execute.

No proxy, assumed, fallback, stale or unknown value enters verified execution. Missing coverage blocks the run.
