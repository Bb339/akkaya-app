# Provider contract

| Provider | Identity | Data paths | Execution | Fallback |
|---|---|---|---|---|
| `AKKAYA_REFERENCE` | Frozen P-units | Existing V1 endpoints/files | Existing V1 behavior | Not applicable |
| `PROJECT_DATA` | Exact confirmed project and GX/custom unit IDs | `/api/v2/projects/...` only | readiness → preview → pinned selection → stored analysis | Forbidden |

Project mode blocks `/api/parcels`, `/api/optimize`, `/api/meta`, `/api/years`, `/api/geojson_*` and `/data/*`. A missing, malformed, duplicated or unknown project context produces a visible failure and disables execution. It never changes provider automatically.

The backend projection publishes algorithms `GA`, `ACO`, `ABC`; objectives `water_saving`, `max_profit`, `water_efficiency`; S1/S2 readiness; canonical units; optional geometry; requirements; history; and an optional stored-run presentation. Scientific calculations remain in existing backend services.

