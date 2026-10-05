# PROJECT_DATA clean-boot network evidence

The browser opened PROJECT_DATA directly in a fresh page without first visiting AKKAYA_REFERENCE. Shared authentication, tabs, charts and presentation wiring initialized; reference dataset, metadata, water, map, drawing-registry and data-binding loaders did not run.

Observed normal boot counters:

- `REFERENCE_INIT_ATTEMPTS_IN_PROJECT_DATA = 0`
- `BLOCKED_REFERENCE_ERRORS_NORMAL_BOOT = 0`
- `PROJECT_DATA_API_PARCELS_CALLS = 0`
- `PROJECT_DATA_API_OPTIMIZE_CALLS = 0`
- `PAGEERROR = 0`

The monitored forbidden patterns were `/api/parcels`, `/api/optimize`, `/api/meta`, `/api/geojson_files`, `/api/geojson_bundle`, `/api/water_allocation_logic` and `/data/`. None appeared during the direct PROJECT_DATA boot or project execution.

Project execution used the V2 project endpoints for decision context, preview pinning and immutable analyses. The accepted revision/selection-hash/run-id chain remained intact.

Defense in depth was tested separately: an intentional `fetch('/api/parcels')` in PROJECT_DATA was rejected with `PROJECT_DATA modunda reference endpoint engellendi: /api/parcels`, and the blocked-path registry recorded only that deliberate request. This message did not occur during ordinary boot.
