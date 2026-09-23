# Climate authority contract

Verified execution requires one explicit mode for every selected climate row.

- `YEAR_SPECIFIC`: lookup uses exact `YYYY-MM`; readiness derives required periods from selected phenology and fails closed when any unit lacks one.
- `CLIMATOLOGICAL_NORMAL`: month-of-year reuse is permitted only with all months 1..12 for every analysis unit.

Every row requires a source and the project’s explicit geographic scope. Preview/run provenance records mode, sources, scope, coverage, and applied import facts. Synthetic fixtures state `CLIMATOLOGICAL_NORMAL` and remain `SYNTHETIC / NOT_OFFICIAL`.
