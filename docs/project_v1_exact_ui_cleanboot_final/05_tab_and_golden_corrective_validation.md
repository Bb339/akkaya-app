# Final tab and golden-evidence corrective validation

Baseline: `edf0ca0dde63401ab926cb639e804b8f89a84b52`

## Product correction

`kds/ui/static/v1-provider.js` no longer injects a PROJECT_DATA-only drought tab. It only refreshes project-backed native tab content after an existing shared V1 tab is selected. Both providers therefore expose the same seven native tabs in the same normalized order. The shared drought content card was not removed.

The removed parallel result architecture remains absent: `#v1-native-project-results`, `ensureNativeResultSurface`, and `.v1-native-results` are not active runtime constructs.

## Test maintenance

- The unified demo browser journey now follows the accepted native root URL with exact `provider`, `project_id`, and `run_id` state instead of the obsolete `/projects/decision` surface.
- The native result title assertion uses the real project name; classification remains authority metadata rather than a fabricated title.
- Reference-boundary browser tests use an isolated temporary project store so stale external or junction state cannot affect fail-closed behavior.
- Reference popup evidence waits for reference loading to become idle, selects P1 through the native selector/focus path, asserts the visible popup contains P1, and captures the map itself.

## Verified gates

- 21/21 files: `AUTO_MATCHED`; revision 21.
- 24 analysis units, 24 geometries, 24/24 candidate coverage, 8 crops.
- PROJECT_DATA → AKKAYA_REFERENCE → PROJECT_DATA: 24 → 179 → 24.
- PROJECT_DATA visible tabs: 7; AKKAYA_REFERENCE visible tabs: 7; normalized order equal.
- PROJECT_DATA drought navigation tab: absent; drought content: visible, `SAĞLANMADI / NOT PROVIDED`.
- Clean PROJECT_DATA boot makes no `/api/parcels` or `/api/optimize` request and produces no reference initialization error.
- Responsive viewports 1280×720, 1366×768, 1366×900, 1536×864, 1920×1080, and 390×844 pass without page-level horizontal overflow; 80%, 100%, and 125% zoom checks pass.
- Protected scientific, data, reference, deployment, and frozen V1 objects are unchanged from the corrective baseline.

`REFERENCE_PROVENANCE_PARSE_ISSUE = INHERITED`

`PROTECTED_DIFF = NONE`

`UNEXPLAINED_VISUAL_BUGS = 0`
