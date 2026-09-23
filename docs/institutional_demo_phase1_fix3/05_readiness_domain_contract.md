# Readiness domain contract

Each domain is evaluated independently and exposes status, selection, consumer availability, engine connection, connection state, role, scope, consumer, blockers, and source facts.

Required domains are annual water, monthly supply, delivery, release, conveyance, economics, crop parameters, phenology, climate, candidates, and current pattern. Perennial requirement is `NOT_REQUIRED_FOR_SCENARIO`/`NOT_CONNECTED` in S1 and required in S2. A selected physical release is reported selected but `NOT_EXECUTABLE_WITH_CURRENT_MODE`.

Climate reports mode, source, geographic scope, coverage, and applied imports. YEAR_SPECIFIC coverage is checked against scenario phenology; climatological coverage requires months 1..12 for every unit.
