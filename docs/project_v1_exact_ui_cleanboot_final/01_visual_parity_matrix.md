# PROJECT_DATA / AKKAYA_REFERENCE visual parity matrix

Corrective baseline: `629f1f46ca14f674fcac7c9971acbbefc525d5b0`

The comparison uses the same V1 document, controls, cards, tabs, charts and map grammar for both providers. Provider-specific values remain authoritative to their own source.

| Surface | AKKAYA_REFERENCE | PROJECT_DATA | Classification | Result |
|---|---|---|---|---|
| Header and provider control | Reference identity | Exact project identity and synthetic authority | EXPECTED_PROVIDER_DIFFERENCE | PASS |
| Left setup panel | P1-P179 | KDS-001-KDS-024 | EXPECTED_PROVIDER_DIFFERENCE | PASS |
| Map | 179 accepted reference parcels | 24 imported project geometries | EXPECTED_PROVIDER_DIFFERENCE | PASS |
| Map labels and popup | Parcel identity and reference values | Unit identity, project values and stored-run recommendation | EXPECTED_PROVIDER_DIFFERENCE | PASS |
| Top summary | Reference scenario | Project, revision and stored-run scenario | EXPECTED_PROVIDER_DIFFERENCE | PASS |
| Result hierarchy | Native V1 cards | The same native V1 cards, tables, charts and tabs | BUG_FIXED | PASS |
| Result scrolling | Normal page flow | Normal page flow; only wide tables scroll horizontally | BUG_FIXED | PASS |
| Metric readability | Native V1 | Values wrap safely; table cells do not split words | BUG_FIXED | PASS |
| Map proportions | Native V1 map | 520 px desktop, 460 px compact desktop, 420 px mobile | BUG_FIXED | PASS |
| Tabs | Shared V1 tab set | Same shared V1 tab set with provider-correct terminology | BUG_FIXED | PASS |
| Drought | Accepted 2000-2025 reference series | `SAĞLANMADI / NOT PROVIDED` | EXPECTED_PROVIDER_DIFFERENCE | PASS |
| District/official tables | Reference aggregates | Backend project aggregates and explicit project authority | EXPECTED_PROVIDER_DIFFERENCE | PASS |
| Current pattern | Reference current state | Backend-authoritative project current state | EXPECTED_PROVIDER_DIFFERENCE | PASS |
| Recommended pattern | Reference result | Immutable project run | EXPECTED_PROVIDER_DIFFERENCE | PASS |
| Algorithm comparison | Reference benchmark | Immutable PROJECT_DATA run history | EXPECTED_PROVIDER_DIFFERENCE | PASS |
| Provenance | Reference files | Project revision, selection hash and run ID | EXPECTED_PROVIDER_DIFFERENCE | PASS |

Responsive checks passed at 1280x720, 1366x768, 1366x900, 1536x864, 1920x1080 and 390x844. Zoom checks passed at 80%, 100% and 125%. The document had no page-level horizontal overflow, the project map stayed within its provider-specific V1-compatible bounds, and result cards had no clipped values. The paired 1366x900 full-page captures use the same active native parcel/analysis-unit tab. PROJECT_DATA measured 4385 px high and AKKAYA_REFERENCE measured 4100 px; the remaining 285 px reflects project authority/provenance text and provider-specific content rather than a second result hierarchy.

`PARALLEL_RESULT_WORKSPACE = ABSENT`

`UNEXPLAINED_VISUAL_BUGS = 0`
