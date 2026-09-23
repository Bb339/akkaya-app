# Kc and stage parity

The verified calculator delegates to `app._kc_curve_daily`. This preserves accepted DAYS/FRACTIONS scaling, integer rounding, drift assignment, development and late interpolation, and final clipping/padding.

Exact-list parity covers DAYS 20/30/40/20, FRACTIONS 0.2/0.3/0.3/0.2, 7-day and 730-day seasons, zero stages, and the adversarial 273-day season. Stored Phase 7 `stage_value_mode` provenance remains unchanged.
