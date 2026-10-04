# Provider contract

| Provider | Identity | Unit source | Result source | Failure behavior |
|---|---|---|---|---|
| `AKKAYA_REFERENCE` | Explicit query/provider state | Accepted reference endpoints and 179 parcels | Existing V1 reference path | Reference behavior retained |
| `PROJECT_DATA` | Exact project ID, optional exact run ID | Project decision-context | Pinned preview and immutable stored run | Fail closed; no default project and no reference fallback |

PROJECT_DATA does not call `/api/parcels` or `/api/optimize`. Its URL keeps exact project/run/unit state. Reload reopens only the exact `run_id`. Switching projects clears foreign run, unit, geometry, result, and provenance. Missing backend values remain explicitly unavailable.
