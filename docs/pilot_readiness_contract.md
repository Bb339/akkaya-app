# Pilot readiness contract

Readiness distinguishes demo reproducibility from real-pilot evidence. `DEMO_READY` means the frozen thesis behavior can still run. `PILOT_DATA_NOT_READY` means required verified input evidence is incomplete. `PILOT_READY` requires every runtime crop to have an unambiguous, verified parameter record and complete verified phenology.

`crop_parameter_readiness` reports runtime count, exact and reviewed identity counts, legacy generic fallback count, ambiguous and missing counts, verified parameter count, resolved identity count, and engine connection state. The unchanged legacy generic fallback uses Kc 0.6/1.0/0.8 and stage fractions 0.2/0.3/0.3/0.2. It is always labeled `LEGACY_GENERIC_FALLBACK`, never verified or official.

`phenology_readiness` reports runtime count, verified planting, verified harvest, verified complete, assumed, and missing counts. For frozen Akkaya data the result is 0/58 verified complete because the source contains no sourced planting or harvest values.

Pilot readiness fails closed when parameter resolution is ambiguous or missing, verified parameter coverage is incomplete, or verified phenology is incomplete. The current result is `PILOT_DATA_NOT_READY`, with 3 ambiguous Kabak forms, 1 missing SOGANTAZE parameter identity, 0 verified parameter records under the assumed legacy source, and 0/58 verified phenology records.

KIMYON's reviewed parameter relation does not repair its separate candidate-matrix gap. DUT's missing yield/gross-revenue evidence remains an economic-completeness warning. Phase 5 rotation exposure 7/81 versus applied Turp options 6/32 and the inherited S2 feasibility failure remain backlog.

Both new data types remain disconnected from science (`engine_connected=false`) until a separate integration milestone validates actual external data and calculation parity.
