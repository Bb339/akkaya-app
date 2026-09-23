# Readiness contract

Readiness reports project ID, planning year, profile availability and per-domain engine connection state.

`REFERENCE_DEMO.available` follows existing scenario readiness and includes a demo-data warning. `VERIFIED_INSTITUTIONAL.ready` is reported separately for S1 and S2. Verified readiness resolves the same datasets used at execution; it does not use a weaker display-only check.

Domains are water, economics, crop parameters, phenology, candidates and current pattern. Each ready domain exposes selected dataset facts or applied-import provenance. A missing/inactive/wrong-year/wrong-scope/stale/unverified/ambiguous input produces a blocking reason. Project-level `requires_reanalysis` is also returned.
