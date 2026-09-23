# Water result reconciliation

Verified results retain `optimizer_water_m3` as the accepted engine’s internal aggregate and `verified_profile_water_m3` as exact calendar-profile accounting. `authoritative_water_m3` and the canonical `total_water_m3` use the verified profile for institutional reporting. Efficiency is recomputed against that authoritative total.

`water_reconciliation` reports both quantities, signed difference, percentage, tolerance `max(1 m3, 0.1% of verified total)`, status, and explanation. Material differences use `DIFFERENT_DEFINITIONS`, not a false pass. Reference results retain their historical total and report `NOT_APPLICABLE` for verified-profile reconciliation.
