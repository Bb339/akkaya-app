# Result accounting contract

The V1 `PROJECT_DATA` surface reads the immutable stored backend result. It displays these values separately when present:

- `optimizer_water_m3`: **Optimizer su kullanımı**
- `authoritative_water_m3`: **Doğrulanmış / otoritatif su**
- `planning_year_profile_water_m3`: planning-year water
- `verified_profile_water_m3`: full-season water
- stored reconciliation difference and percentage

The UI explains that optimizer output and authoritative post-run accounting can differ by period and validation scope. It does not calculate or merge these values.

`annual_budget_validation` is rendered with backend demand, usable budget, status and backend reason/message. An absent object is shown as `SAĞLANMADI / NOT PROVIDED`.

Warnings are the de-duplicated union of the stored run and stored result warning arrays. No warning is synthesized.
