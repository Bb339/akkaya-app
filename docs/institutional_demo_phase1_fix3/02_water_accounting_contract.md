# Water accounting contract

- `optimizer_water_m3`: frozen optimizer aggregate.
- `planning_year_profile_water_m3`: verified demand in planning-year January through December; equals annual validation demand.
- `verified_profile_water_m3`: complete selected-season verified profile across actual calendar months.
- `authoritative_water_m3`: complete verified profile for institutional reporting.
- `total_water_m3`: authoritative presentation alias in verified mode.

The full monthly aggregation must equal the sum of unit full-profile totals within `max(1e-6 m3, full total × 1e-9)`. Reconciliation compares optimizer water with the full selected-season verified total. Institutional `efficiency_tl_per_m3` uses authoritative full-season water.
