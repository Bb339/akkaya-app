# PROJECT_DATA Native V1 Map / Selected Unit Parity Audit

## Scope

- Baseline: `af62e044a6fae79b0d2f6ea4f21e80665db78f5d`
- Branch: `v2-project-data-v1-map-selected-unit-parity-final`
- Scope: presentation reuse, provider isolation, focused browser regression, and visual evidence.
- Scientific calculation, optimization, readiness, adapter, canonical data, candidate matrix, robustness evidence, frozen `index.html`, `app.py`, and `render.yaml` are unchanged.

## Native V1 renderer inventory and reuse

The accepted reference path had its presentation logic embedded in `script.js`. The smallest provider-neutral extraction exposes the same functions through immutable `window.NativeV1Presentation`:

| Native responsibility | Shared function | DOM family / target |
| --- | --- | --- |
| Unit badge, status dot, information icon | `nativeV1UnitBadgeHtml` | `.parcel-badge > .dot + .pid + .hint` |
| Popup field/value hierarchy | `nativeV1UnitPopupHtml` | `.parcel-pop > .t + .r` |
| Normal and selected polygon style | `nativeV1ParcelStyle` | Leaflet GeoJSON path |
| Crop icon resolution | `nativeV1CropIcon` | `.crop-emoji` |
| One recommendation detail card | `nativeV1ProductCardHtml` | `.crop-detail-card` |
| Recommendation strip and cards | `nativeV1ProductCardsHtml` | `#productCards`, `.crop-strip`, `.crop-pill` |

AKKAYA_REFERENCE calls these functions in its existing render path. PROJECT_DATA maps backend decision-context and immutable stored-run fields into the same functions. Strict PROJECT_DATA product rendering does not consult the reference crop catalog and uses `SAĞLANMADI / NOT PROVIDED` for absent fields.

The native selector/map synchronization remains `parcelSelect` → `focusGeometry` → Leaflet selected style/popup → `renderUnit` → `#parcelSummaryBlock`, `.metrics-grid`, current/recommended tables, and `#productCards`. Map sizing uses `ResizeObserver`, animation frames, `invalidateSize()`, and selected-unit refit after layout settlement. Provider-only desktop height caps were removed.

## Root causes and corrections

1. PROJECT_DATA created a separate simplified tooltip, popup, and recommendation presentation instead of adapting its values to the native V1 renderers. Both providers now call the same renderer functions.
2. PROJECT_DATA CSS imposed fixed/capped map heights. The map now follows the native V1 top-row grid rule. At wide desktop width the map and metrics cards have equal top and height; compact widths use the native stacked breakpoint.
3. A visible Leaflet popup could intercept a polygon click. In PROJECT_DATA it is informational and its popup pane has `pointer-events:none`, preserving polygon selection.
4. Native V1 renders the official tab asynchronously after activation. That render could overwrite the PROJECT_DATA projection. `observeProjectOfficialSurface` now observes the actual official-panel mutation lifecycle and reapplies the project projection without a new timeout or arbitrary delay.
5. Historical tests still expected the removed PROJECT_DATA badge class, plain popup markup, an obsolete title, and fixed 420/620 px height caps. Those assertions were updated to the native component and structural parity contract.

## Verification results

- Backend/provider focused regression: `12 passed` in `124.08s`.
- Full real Chromium native workspace journey: `1 passed` in `318.18s`.
- Dedicated map/UI parity Chromium journey: `1 passed` in `152.60s`.
- AKKAYA adapter invariant test: `1 passed` in `1.40s`.
- JavaScript syntax: `node --check script.js` and `node --check kds/ui/static/v1-provider.js` passed.
- Patch hygiene: `git diff --check` passed.

The Chromium coverage proves:

- 21/21 AUTO_MATCHED, revision 21, 24 units, 24 Polygon geometries, 24/24 candidate coverage, and 8 crops.
- GA, ACO, ABC; `water_saving`, `max_profit`, `water_efficiency`; S1 and S2; pinned previews; HTTP 201 stored runs; explicit `run_id` reload.
- KDS-001, KDS-005, KDS-009, and KDS-024 selector, polygon style, popup, selected summary, metrics, and recommendation synchronization.
- S1 one-crop and S2 primary/secondary native icon/card rendering.
- Seven-tab parity, no PROJECT_DATA drought tab, visible `SAĞLANMADI / NOT PROVIDED` drought content, and no parallel result workspace.
- 1280×720, 1366×768, 1366×900, 1536×864, 1920×1080, and 390×844; 80%, 100%, and 125% zoom; no document-wide horizontal overflow.
- Direct fresh PROJECT_DATA trace: `/api/parcels`, `/api/optimize`, `/api/meta`, reference GeoJSON, `/api/water_allocation_logic`, and `/data/` counters are all zero; page errors and blocked-reference errors are zero.
- Provider round trip remains 24 PROJECT_DATA units → 179 AKKAYA_REFERENCE parcels → 24 PROJECT_DATA units.
- AKKAYA invariant adapter values remain 179 parcels, 134919 da, 6859 candidate rows, 58 crops, 100700080.81 m³, and 1041499119.212 TL.

## Golden evidence

All evidence is under `docs/project_data_v1_map_selected_unit_parity_final/evidence/`:

1. `01_project_top_workspace_1366x900.png`
2. `02_project_selected_map_state.png`
3. `03_project_native_badge.png`
4. `04_project_native_popup.png`
5. `05_project_selected_summary.png`
6. `06_project_water_profit_metrics.png`
7. `07_project_recommendation_card.png`
8. `08_project_s2_recommendation_cards.png`
9. `09_reference_top_workspace_1366x900.png`
10. `10_reference_selected_map_state.png`
11. `11_reference_native_badge.png`
12. `12_reference_native_popup.png`
13. `13_reference_selected_summary.png`
14. `14_reference_water_profit_metrics.png`
15. `15_reference_recommendation_cards.png`

The permitted visual differences are identity, geometry, values, authority, and explicitly unavailable PROJECT_DATA fields. Badge, popup, selected-summary, metrics, and product-card DOM families are identical.

## Gates

```text
MAP_ROW_HEIGHT_PARITY = PASS
NATIVE_V1_UNIT_BADGES = PASS
NATIVE_V1_CROP_ICONS = PASS
NATIVE_V1_POPUP = PASS
NATIVE_V1_SELECTED_SUMMARY = PASS
NATIVE_V1_RECOMMENDATION_CARDS = PASS
FOUR_UNIT_SELECTION_SYNC = PASS
REFERENCE_TAB_COUNT = 7
PROJECT_TAB_COUNT = 7
TAB_HIERARCHY_PARITY = PASS
PROJECT_DROUGHT_NAV_TAB = ABSENT
PARALLEL_RESULT_WORKSPACE = ABSENT
VALID_PROJECT_BOOT = PASS
LOADING_OVERLAY_RELEASE = PASS
REFERENCE_INIT_ATTEMPTS_IN_PROJECT_DATA = 0
PROJECT_DATA_API_PARCELS_CALLS = 0
PROJECT_DATA_API_OPTIMIZE_CALLS = 0
PROJECT_DATA_API_META_CALLS = 0
PROJECT_DATA_REFERENCE_GEOJSON_CALLS = 0
PROJECT_DATA_REFERENCE_DATA_CALLS = 0
BLOCKED_REFERENCE_ERRORS_NORMAL_BOOT = 0
PAGEERROR = 0
AKKAYA_NON_REGRESSION = PASS
RESPONSIVE_MATRIX = PASS
DOCUMENT_HORIZONTAL_OVERFLOW = 0
PROTECTED_DIFF = NONE
UNEXPLAINED_VISUAL_BUGS = 0
```
