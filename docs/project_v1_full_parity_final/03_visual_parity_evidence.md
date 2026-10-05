# Visual parity evidence

All captures were produced by `test_full_native_project_workspace_clickability_and_e2e` with a fresh filesystem store and real headless Chromium. The accepted desktop package was uploaded through `/projects`, detected 21/21, explicitly confirmed to revision 21 and opened through the PROJECT_DATA provider.

| Evidence | Viewport / purpose | Assertions represented |
|---|---|---|
| `evidence/project_data_before_run_1366x900.png` | 1366×900, PROJECT_DATA before optimization | 24 imported units, 24 polygons and labels, current project water/profit/efficiency, shared V1 layout, explicit missing optimized state |
| `evidence/project_data_after_run_1366x900.png` | 1366×900, PROJECT_DATA after immutable runs | stored result, current/recommended distinction, full run/result modules, bounded map and no page-wide horizontal overflow |
| `evidence/akkaya_reference_restored.png` | 1366×900, paired reference capture | same V1 product surface restored with canonical 179-parcel reference provider terminology |
| `evidence/project_data_after_run_1920x1080.png` | 1920×1080 | desktop scaling, bounded map, independent result growth, no document overflow |
| `evidence/project_data_after_run_390x844.png` | 390×844 | narrow responsive layout, local table scrolling and no document overflow |
| `evidence/project_map_unit.png` / `evidence/reference_map_1366x900.png` and `evidence/reference_map_unit.png` | paired map and selected popup | exact KDS-009 project geometry, selected style and authority versus the unchanged native reference map and selected-parcel popup |
| `evidence/project_summary_1366x900.png` / `evidence/reference_summary_1366x900.png` | paired summary | backend project aggregation versus selected reference-parcel summary |
| `evidence/project_current_recommended_1366x900.png` / `evidence/reference_current_recommended_1366x900.png` | paired current/recommended pattern | provider-correct identities and values in the shared V1 tab |
| `evidence/project_drought_1366x900.png` / `evidence/reference_drought_1366x900.png` | paired drought module | explicit project unavailability versus reference drought content |
| `evidence/project_tabs_1366x900.png` / `evidence/reference_tabs_1366x900.png` | paired tab set | shared visible navigation without provider-based hiding |
| `evidence/project_algorithm_comparison_1366x900.png` / `evidence/reference_algorithm_comparison_1366x900.png` | paired algorithm comparison | immutable project-run history versus native reference comparison |
| `evidence/project_monthly_water.png` / `evidence/reference_monthly_water_context_1366x900.png` | paired monthly water | immutable project run accounting versus native reference context |
| `evidence/project_provenance.png` / `evidence/reference_provenance_context_1366x900.png` | paired provenance | project/revision/run/selection identity versus native reference source identity |
| `evidence/project_crop_recommendation.png` | result detail | immutable backend crop composition and HHI |

## Chromium journey

- Fresh project classified as `SYNTHETIC / NOT_OFFICIAL`.
- 21 files produced 21 `AUTO_MATCHED` rows and revision 21.
- Units KDS-001, KDS-008, KDS-016 and KDS-024 displayed backend-projected current water, profit and efficiency.
- Map click selected KDS-009 and its popup used project geometry and values.
- Stored runs executed with seed 123 for GA/S1/water_saving, ACO/S1/max_profit and ABC/S1/water_efficiency. S2 was READY, so GA/S2/water_saving was also executed.
- Algorithm comparison showed all three objective/algorithm combinations from immutable project history.
- Users, geometry, district, official, drought and benchmark tabs remained visible. District and official values were re-projected after tab activation so legacy reference refresh could not overwrite project state.
- Drought and unsupported schedule/method domains stayed visible with explicit unavailable states.
- Reload reopened only the explicit run ID; returning from AKKAYA_REFERENCE to the project without a run ID did not restore a run implicitly.
- No PROJECT_DATA request reached `/api/parcels` or `/api/optimize`.

## Layout result

The PROJECT_DATA map is capped at 620 px on desktop and 420 px on narrow screens. Long result content scrolls within its result surface on desktop; tables scroll locally. Chromium asserted `document.documentElement.scrollWidth <= window.innerWidth` at 1280×720, 1366×768, 1366×900, 1536×864, 1920×1080 and 390×844, plus CSS zoom equivalents of 80%, 100% and 125%.

## Difference classification

| Difference | Classification | Reason |
|---|---|---|
| P1–P179 versus KDS-001–KDS-024 | EXPECTED PROVIDER DIFFERENCE | Exact provider identities are authoritative and must not be renamed. |
| 179 reference parcels versus 24 project analysis units | EXPECTED PROVIDER DIFFERENCE | Separate reference and uploaded project datasets. |
| Reference drought history versus explicit unavailable project state | EXPECTED PROVIDER DIFFERENCE | The 21-file package has no drought-index time series; no fallback is allowed. |
| Reference official publication tables versus PROJECT DATA/run tables with authority note | EXPECTED PROVIDER DIFFERENCE | The package supplies project inputs and results, not an external published official-table dataset. |
| Project geometry is managed through `/projects` data management | EXPECTED PROVIDER DIFFERENCE | Project GeoJSON is confirmed import data; legacy reference parcel editing cannot mutate it safely. |
| Project comparison uses immutable stored runs | EXPECTED PROVIDER DIFFERENCE | Reference benchmark and project run history are not mixed. |

Remaining unexplained visual differences classified as BUG: **none**.
