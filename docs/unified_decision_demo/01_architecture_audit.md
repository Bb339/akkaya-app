# Unified Decision Demo Architecture Audit

## Baseline and audit boundary

- Accepted source tag: `v2-ministry-final-demo-presentation-freeze-complete`
- Accepted source commit: `a6d36d099544776d0610b3c868a3675b12da5b0e`
- New branch: `v2-unified-decision-screen-smart-import`
- This audit was completed before implementation.
- Scientific engines, scoring, objectives, readiness rules, frozen Akkaya inputs, reference values, and robustness evidence are outside the allowed mutation boundary.

## Current UI paths

### Thesis / V1 decision experience

- Entry point: `/`, served from `index.html` by `app.py:index`.
- Frontend: root `script.js` and `style.css`.
- Primary APIs include `/api/meta`, `/api/parcels`, `/api/geojson_bundle`, `/api/optimize`, `/api/benchmark`, water-allocation/data-quality endpoints, and static files under `/data/**`.
- The screen contains its own authentication/demo state, parcel selector, map, scenario and algorithm controls, optimization/result tables, economic and water presentation, charts, and comparison panels.
- Its runtime and client state are tightly coupled to the frozen Akkaya/reference datasets and legacy thesis page assumptions.
- `script.js` also contains legacy client-side objective and optimizer helpers. Those functions must not be used to construct or reinterpret a verified institutional stored run.

### Institutional project workspace

- Entry point: `/projects`, registered by `kds.ui.register_project_pages`.
- Frontend: `kds/ui/templates/projects.html` plus ES modules under `kds/ui/static/`.
- API boundary: `/api/v2/projects/**`, registered by `kds.api.register_project_api`.
- Imports use upload → parse → proposed mapping → validation preview → explicit confirmation → versioned activation.
- Analysis uses readiness → pinned preview token/revision/selection hash → run → immutable stored result → provenance.
- Stored result presentation is composed by `kds.application.result_presentation.present_run_for_ui`; it enriches an immutable scientific result without modifying it.

## Result contracts

### V1 result contract

The V1 page consumes `/api/optimize` and legacy metadata/parcel endpoints. Its result rendering assumes Akkaya parcel/candidate context and the root page's client state. It is not a safe provider contract for arbitrary institutional projects.

### Project-run result contract

`GET /api/v2/projects/{project_id}/analyses/{run_id}` returns the stored run through `present_run_for_ui`. The authoritative contract contains:

- run identity, profile, scenario, algorithm, objective, seed, status and warnings;
- backend result KPIs and feasibility;
- authoritative water views, validation summaries and monthly rows;
- backend `crop_shares`, canonical HHI, details and top crops;
- ID-joined `presentation_units` for list/map/unit detail;
- stored provenance, input snapshot, selection hash and engine commit;
- presentation revision context and reanalysis relationship.

The adapter joins geometry/current-crop display metadata by canonical analysis-unit identity. It never creates result units from project metadata and never mutates the stored result.

## Reusable presentation components

Safe reuse:

- V1 visual language: header treatment, cards, KPI hierarchy, map/table layout, warning bands and navigation cues.
- V2 backend-authoritative result renderer concepts: KPI, water validation, monthly table/chart, crop shares, unit list/map/detail and provenance.
- `present_run_for_ui` as the only project/run presentation adapter.
- Existing project API, immutable run lookup and explicit profile labels.

Unsafe reuse:

- V1 data loaders tied to root `/data/**` files.
- V1 parcel/candidate state and Akkaya-specific defaults.
- V1 client-side optimizer/objective helpers or any JavaScript recomputation of stored scientific results.
- Any fallback from an institutional project/run lookup to frozen Akkaya files or reference values.

## Akkaya-specific logic and data

The root page's dataset loaders, parcel identities, candidate matrices, reference totals and parts of its optimization rendering are Akkaya-specific. The accepted reference values remain owned by the frozen reference provider:

- 179 analysis units
- 134,919 da
- 6,859 raw candidate rows
- 58 crops
- 100,700,080.81 m³ calculated reference water
- 1,041,499,119.212 TL catalog-derived reference profit

They must not be copied into an institutional project or used as a fallback.

## Safe bridge design

The bridge will inject only immutable context identifiers:

- `project_id`
- `run_id`
- `execution_profile`

For an institutional run, a dedicated decision-presentation route will load the run through `/api/v2/projects/{project_id}/analyses/{run_id}` and render backend-authoritative fields. It will reuse the accepted project result contract and V1 visual language, without calling `/api/optimize`, reading frozen candidate matrices, or recalculating scientific values in JavaScript.

For Akkaya Reference Demo, `/` and its frozen reference provider remain unchanged. Navigation will make the provider boundary explicit:

- Akkaya: `AKKAYA REFERENCE` and `REFERENCE MODEL / DEMO DATA`
- Project run: `VERIFIED INSTITUTIONAL`
- Synthetic project run: `SYNTHETIC TEST DATA · NOT OFFICIAL`

If the project, run or profile context is missing, mismatched or not stored, the bridge must fail closed. It must never substitute Akkaya/reference content.

## Import architecture gap

The accepted importer already parses CSV, XLSX and GeoJSON, suggests canonical mappings for a caller-selected data type, validates rows, and requires explicit confirmation. The remaining gaps are:

- deterministic data-type inference before upload;
- XLSX sheet inventory and selected-sheet evidence;
- confidence/state reporting (`AUTO_MATCHED`, `REVIEW_REQUIRED`, `AMBIGUOUS`, `UNSUPPORTED`, `INVALID`);
- multiple-file upload orchestration and a detected-file table;
- a prepared, source-traceable synthetic demo package.

The implementation may add import-assistance metadata and bulk orchestration around the accepted contracts. It must continue to activate each dataset only through the existing confirmed import path.

