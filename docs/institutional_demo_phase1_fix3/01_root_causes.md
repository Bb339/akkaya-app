# Root causes

Fix2 derived `verified_profile_water_m3` from `annual_budget_validation.demand_m3`. That annual value intentionally contains only planning-calendar-year months, so preceding-year demand disappeared from authoritative water and the TL/m3 denominator.

Fix2 readiness wrapped the complete execution plan in one `try/except`. Any one exception generated an identical false state for every domain, and climate had no domain entry.

Failing-before behavior was reproduced at baseline `c838a2f`; Fix3 tests assert the corrected distinctions directly.
