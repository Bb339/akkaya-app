# Crop parameter and phenology integration

Only `EXACT` and reviewed `REVIEWED_ALIAS` identities are eligible. Every runtime crop must be covered by one active project-year/scope dataset with verified authority. `AMBIGUOUS` and `MISSING` identities block execution; generic Kc is never substituted in verified mode.

Kc and day-stage values are copied into the project crop catalog and S2 crop-parameter resource. Verified phenology dates are copied into matching seasonal rows. `YEAR_SPECIFIC` and `CLIMATOLOGICAL_WINDOW` season-year semantics are retained. S2 requires both PRIMARY and SECONDARY phenology records per runtime crop, preventing one season from being silently reused for another.

The existing water-calculation and optimizer functions are reused. No parallel FAO calculator was introduced.
