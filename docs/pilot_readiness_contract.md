# Pilot readiness contract

Readiness distinguishes demo reproducibility from real-pilot evidence. `DEMO_READY` means the frozen thesis behavior can still run. `PILOT_DATA_NOT_READY` means required verified input evidence is incomplete. `PILOT_READY` requires every runtime crop to have an unambiguous, verified parameter record and complete verified phenology.

`crop_parameter_readiness` reports runtime count, exact and reviewed identity counts, legacy generic fallback count, ambiguous and missing counts, verified parameter count, resolved identity count, and engine connection state. The unchanged legacy generic fallback uses Kc 0.6/1.0/0.8 and stage fractions 0.2/0.3/0.3/0.2. It is always labeled `LEGACY_GENERIC_FALLBACK`, never verified or official.

`phenology_readiness` reports runtime count, verified planting, verified harvest, verified complete, assumed, and missing counts. For frozen Akkaya data the result is 0/58 verified complete because the source contains no sourced planting or harvest values.

Pilot readiness fails closed when the runtime crop catalog is empty, parameter resolution is ambiguous or missing, verified parameter coverage is incomplete, verified phenology is incomplete, or the scientific engine is disconnected. Readiness selects active datasets by data type, project planning year, and pilot geographic scope. Without an explicit `metadata.pilot_geographic_scope`, only one scope may exist and it must be `project`; non-project or multiple scopes fail closed. Wrong-year datasets never contribute coverage.

Verified parameter evidence and pilot readiness are separate. `verified_parameter_evidence` means reviewed/exact identity plus verified, non-synthetic authority. `verified_parameter_ready` additionally requires the scientific execution path to use that evidence without legacy fallback. Thus an OFFICIAL reviewed KIMYON relation may have verified evidence while remaining unready when the legacy engine still uses generic fallback. The current result remains `PILOT_DATA_NOT_READY`, with 3 ambiguous Kabak forms, 1 missing SOGANTAZE parameter identity, 0 ready parameter records, and 0/58 verified phenology records.

KIMYON's reviewed parameter relation does not repair its separate candidate-matrix gap. DUT's missing yield/gross-revenue evidence remains an economic-completeness warning. Phase 5 rotation exposure 7/81 versus applied Turp options 6/32 and the inherited S2 feasibility failure remain backlog.

Both new data types remain disconnected from science (`engine_connected=false`) until a separate integration milestone validates actual external data and calculation parity.
