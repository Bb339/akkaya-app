# Architecture audit

Baseline: `cfcc1f59c34847ee51c672ce766208bb1a8798ab`.

The existing V1 workspace is the frozen `index.html` plus `script.js`. It obtains the Akkaya parcel list and reference optimization from `/api/parcels` and `/api/optimize`; metadata, years and map layers come from `/api/meta`, `/api/years`, `/api/geojson_*` and `/data/*`. The parcel selector, map, GA/ACO/ABC selector, S1/S2 selector, objective radios, metric cards and charts are already in that workspace.

V2 stores projects in `FileProjectStore`. Confirmed imports populate project-scoped analysis units, crops, candidates, current pattern, water, economics, scientific inputs and optional geometry. Existing readiness, analysis preview, immutable run and result-presentation services remain authoritative.

The provider boundary is now immediately above the decision UI. `AKKAYA_REFERENCE` leaves the V1 request paths unchanged. `PROJECT_DATA` reads one backend projection at `/api/v2/projects/<id>/decision-context`; that projection joins project units, readiness, capabilities, optional stored run and provenance without calculating science. The browser adapter binds those values to existing V1 controls and blocks all reference data paths while project mode is active.

`/projects` remains the ingestion and data-management center. Its **Karar Sisteminde Aç** action enters `/` with explicit provider context. The frozen `index.html` is not edited; Flask injects the small provider control and adapter at response time.

