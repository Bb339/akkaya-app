# Ministry UI Phase 2 — UI / API Architecture Audit

## Accepted baseline

The Phase 2 branch starts at annotated tag `v2-institutional-demo-integration-phase1-complete`, dereferenced to `04a4bce0db31db41813cfcfd253d9c6794f252bc`. The accepted Phase 1 scientific and institutional contracts are the implementation boundary.

## Current screens

Two distinct user surfaces exist:

1. `/` is the established V1 decision-support dashboard. It contains authentication/onboarding, Leaflet map and parcel selection, scenario/algorithm/objective controls, water and profit KPIs, recommendation cards, charts, drought panels, tables, notifications, and role-specific administration. Its visual logic is mature and must remain recognizable.
2. `/projects` is the existing V2 project workflow. It supports project creation/selection, imports, mapping and explicit confirmation, water budget/scientific input entry, readiness, preview, analysis execution, stored history, result facts, plan table, and provenance JSON. It is functional but visually sparse and exposes several institutional concepts as raw JSON.

## Current navigation

The V2 page has anchor navigation for projects, data management, readiness, analysis, results, and history. It lacks a persistent project header, a dedicated provenance destination, explicit Reference Demo entry, mode-safe navigation, version history, and Ministry-oriented workflow grouping.

## Reusable V1 panels and behavior

The following V1 strengths can be reused without copying scientific logic into the browser:

- Leaflet map and map-to-detail selection pattern.
- Parcel/unit selection and result synchronization.
- Algorithm, scenario, and objective terminology.
- Water/profit KPI hierarchy, recommendation cards, charts, notices, and Turkish labels.
- Responsive cards, tabular drill-downs, notification style, and warning treatments.

Phase 2 will keep `/` unchanged and apply these interaction patterns to `/projects` through its modular `kds/ui` assets.

## Existing V2 frontend modules

- `projects.js`: project selection, overview/readiness refresh, project facts, dataset status.
- `imports.js`: upload, mapping, warning acknowledgement, explicit confirmation.
- `analysis.js`: preview/run requests and stored result rendering.
- `history.js`: immutable stored-run list and run reopening.
- `api.js`: API boundary and text-only DOM helpers.
- `projects.css`: minimal responsive styling.

These modules already avoid scientific calculation. They should be extended as presentation/adaptation layers.

## Existing API endpoints

- `GET/POST /api/v2/projects`
- `GET /api/v2/projects/{project_id}`
- `GET /api/v2/projects/{project_id}/overview`
- `GET /api/v2/projects/{project_id}/readiness`
- `GET /api/v2/projects/{project_id}/analyses`
- `POST /api/v2/projects/{project_id}/analysis-preview`
- `POST /api/v2/projects/{project_id}/analyses`
- `GET /api/v2/projects/{project_id}/analyses/{run_id}`
- `GET /api/v2/projects/{project_id}/analyses/{run_id}/provenance`
- `GET/POST /api/v2/projects/{project_id}/scientific-inputs`
- `GET /api/v2/projects/{project_id}/economic-data`
- `POST /api/v2/projects/{project_id}/water-budget`
- `POST /api/v2/projects/{project_id}/imports`
- `GET /api/v2/projects/{project_id}/imports/{batch_id}`
- `POST /api/v2/projects/{project_id}/imports/{batch_id}/mapping`
- `POST /api/v2/projects/{project_id}/imports/{batch_id}/confirm`
- Paginated analysis-unit, crop, and economics collections.

The accepted endpoints already provide the required readiness, preview, run, history, and provenance contracts. No scientific API is missing.

## Existing import flow

`ImportService` already enforces the correct sequence: upload creates a non-active preview batch; mapping validates the proposed mapping; confirmation requires explicit `confirm=true`; only confirmation changes active project data and revision. Phase 2 must visualize this sequence without bypassing it.

## Missing frontend bindings

- Explicit, persistent execution-profile indicator and non-color mode distinction.
- Institution/project/revision/reanalysis header.
- Domain readiness matrix with independent selected/valid/consumer/connected axes.
- Economics completeness and missing-required-type display.
- Dataset identity, authority, scope, source, confirmation, and version display.
- Human-readable preview evidence, revision/hash details, and stale-preview recovery.
- Canonical full-season versus planning-year versus annual/monthly validation water views.
- Stored-run provenance drawer, dataset version history, and reanalysis warning.
- Institutional result KPIs, infeasible diagnostic presentation, crop distribution, unit explorer, and monthly chart.
- Permanent synthetic/non-official warning and explicit Reference Demo entry.
- Template directory surfaced with non-official labeling.
- Stable screenshot anchors for the ten requested states.

## Duplicated concepts to consolidate

Project facts, readiness summary, import state, execution profile, and source labels currently appear in separate raw blocks. Phase 2 should bind each concept once to a canonical visual component, while leaving advanced JSON only in expandable technical details.

## Additions required for the institutional workflow

- A Ministry shell with workflow navigation and sticky project context.
- Project portfolio and creation form with institution, scope, description, revision, readiness, and reanalysis state.
- Data-management domain cards and explicit upload stepper.
- Domain-specific readiness dashboard and ordered blocker list.
- Preview evidence review before enabled execution.
- Stored institutional result dashboard with water, crop, monthly, unit/map, economics, provenance, version, and reanalysis views.
- Reference Demo launch and warning experience.
- Browser acceptance coverage for mode labels, blocking, preview, stale state, diagnostics, provenance, map synchronization, and canonical water semantics.

## What must not change

- V1 `/` dashboard behavior or its scientific display logic.
- GA, ACO, ABC, objective/scoring, repair, or crop-selection logic.
- USDA-SCS, Kc, FAO56, phenology, economics resolution, readiness, fail-closed, or water-accounting semantics.
- Candidate matrix, frozen reference data/output, or robustness evidence.
- Import activation and confirmation rules.
- Stored-run immutability and version pinning.

The browser remains a formatter and workflow controller. It must never recompute scientific or authoritative values supplied by the backend.
