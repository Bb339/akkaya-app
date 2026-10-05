# V1 visual and functional parity matrix

Baseline: `eaad7597c4f420447b06befd09bebf65026e1520`. The audit compares the shared V1 DOM in `index.html`; provider differences are limited to the backend-authoritative data projected by `v1-provider.js`.

| Feature / V1 component | AKKAYA_REFERENCE behavior | PROJECT_DATA audit finding | Package / backend source | Corrective result |
|---|---|---|---|---|
| Provider control and project button | Reference badge and project drawer | Already functional and fail-closed | strict query state + project API | Preserved |
| User controls and alerts | V1 auth, role and alert UI | CSS hid user tab in project mode | V1 local product state | Tab remains available; no project-data substitution |
| Unit selector | 179 reference parcels | Correct 24 units | `analysis_units` via decision-context | Preserved; canonical IDs only |
| Optimize actions | Reference `/api/optimize` | Accepted project preview/run chain | pinned preview + `/api/v2/.../analyses` | Preserved; reference endpoints remain blocked |
| Data source / active datasets | Reference source labels | Project authority and revision available | readiness + requirements | Project identity, authority, revision and dataset states visible |
| Manual upload and validation | Reference file controls | Legacy controls unsafe in project mode | `/projects` data workflow | Project button routes to exact project data section |
| Algorithm, objective, scenario, year | V1 controls | GA/ACO/ABC, three objectives and ready scenarios available | decision-context capabilities | Preserved; preview invalidates on change |
| Water budget / quota | Reference budget | Run annual validation already available | project budget + stored result | Current and optimized values shown; no fallback |
| Geometry assignment | V1 drawing workflow | Tab was hidden; project geometry is import-managed | confirmed GeoJSON | Tab visible with explicit project-safe management guidance |
| User management | V1 product module | Tab was hidden by provider CSS | V1 user product state | Tab visible |
| Messages / requests | V1 product module | Present | V1 communication state | Preserved |
| Map base layer | Leaflet V1 map | Present | V1 map | Preserved |
| Unit rendering, labels and popup | Styled parcel polygons and labels | Geometry existed, labels/styles were reduced | confirmed `geometries` + units | Styled project polygons, permanent ID labels, project popup |
| Map selection synchronization | Selector and map synchronized | Already functional | canonical unit ID | Preserved and selected style retained |
| Map sizing | Fixed V1 visual region | Long result column could stretch map | presentation CSS | Independent bounded map height; local overflow only |
| Basin/project summary | Reference aggregate | Optimized values present; current values incorrectly unavailable | `scientific_inputs.unit_parameters` | Backend joins exact unit IDs and publishes complete aggregate |
| Selected-unit summary | Reference current and optimized metrics | Current values existed but were not wired | same unit parameters + stored result | Current water, profit, TL/m³ and per-da values visible |
| Feasibility, budget, warnings, provenance | Reference results | Already rendered from immutable project run | stored run presentation | Preserved |
| Drought indicators | Reference historical series | No project drought series; tab hidden | none in package | Module and tab visible with explicit NOT PROVIDED, no fallback |
| Water/profit charts | Reference comparison | Project stored-run charts present | immutable run | Preserved |
| Current and recommended pattern | Reference tables | Current per-da values blank despite package values | backend provider + stored run | Current and recommended tables populated where authoritative |
| Rationale and rotation | Reference explanations | Project-safe stored-run rationale present | stored run | Preserved; S1/S2 semantics explicit |
| Irrigation comparison and schedule | Reference-specific calculations | No project result contract | absent | Visible explicit NOT PROVIDED state |
| Economic basis | Reference basis | Unit backend totals present | project economics + run | Visible; no client-side scientific reconstruction |
| Monthly capacity / critical months | Reference series | Project run supplies verified monthly series | stored result | Table and chart preserved |
| District / province summary | Reference computed scope | Entire tab hidden | backend geographic summary | Visible backend-derived settlement/project summary |
| Official tables | Reference official summaries | Entire tab hidden | project + immutable run; no published official dataset | Visible PROJECT DATA tables with authority limitation stated |
| Algorithm comparison | Reference benchmark runner | Project history table existed; charts/pattern text hidden | immutable project run history | Existing runs compared; reference benchmark execution controls isolated |
| Extra V1 tabs | Parcel, communication, users, drawing, district, official, benchmark | Provider CSS removed several tabs | shared V1 product DOM | No provider-based tab removal remains |

## Safety conclusion

PROJECT_DATA retains the accepted chain `decision-context -> pinned preview -> analyses -> immutable run -> exact run_id reload`. The adapter blocks `/api/parcels`, `/api/optimize`, reference GeoJSON and `/data/` requests. Missing project domains remain visible and explicit; no Akkaya value, geometry or default selection is introduced.
