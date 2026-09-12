# Akkaya demo adaptation

Frozen source: v1.0.0-thesis-final at
a49daac1ae6d15d83428565c388bfafb4b6da08a. Work exclusively in V2.

From V2 root: `py -B -m kds seed-demo --source-dir data`.
This reads the V2 checkout's source CSVs and creates akkaya-2024-demo in the
configured runtime store. It does not copy the whole data folder or write to source
CSV files. No initialization occurs at module import or on GET requests. Repeating
with identical provenance returns the existing project without overwriting imports;
different provenance raises a conflict.

## Mapping and reference checks

Summary CSV produces AnalysisUnits with parsel_id → external_id. The catalog
produces 58 project Crops and 58 Economics records. Missing DUT yield stays null.
Original rows/confidence/source labels remain metadata, including old source
descriptions mentioning older scopes. Coordinates do not generate polygons.

| Reference | Value |
|---|---:|
| Analysis units | 179 |
| Area (da) | 134919 |
| Current water (m³) | 100700080.81 |
| Current profit (TL) | 1041499119.212 |
| Raw candidate rows | 6859 |
| Raw water-quota-flagged rows | 3673 |

Adapter validates these before creating a project. Water is calculated_reference,
not official allocation or available reservoir water. Exact current-profit/current-
water decimals are preserved on units and in reference metadata. Catalog rates are
distinct from unit-level baseline economics and must not replace them.

Raw candidates remain in the original file, identified by relative path and SHA-256.
3673 counts raw matrix quota flags, not final suitable candidates. No scientific
filters or algorithms are run by this adapter. Provenance records source tag/commit.

## Scientific boundary and rollback

Legacy optimization still uses its frozen dataset and existing endpoints. New
project data is exposed through the project layer. Project-scoped optimization
requires a later input adapter with seeded S1/S2 regression; this milestone changes
no formulas, fallback math, weights, GA/ACO/ABC, CV or plan-distance definitions.

Run `py -B -m pytest -p no:cacheprovider -q` with bytecode disabled. The existing
33 tests are retained. New tests cover import isolation, transaction failure,
concurrent confirmation, HTTP contracts and exact demo references. A frozen
AST/static-source manifest detects accidental scientific/frontend edits.

V2 changes can be reverted with normal Git commits. Runtime data is separate:
back up the store before future destructive changes. Git tags do not back up
browser localStorage or runtime project data. No browser state is inferred or
imported. No database migration, remote push or production change is performed.

## Verified milestone result

On 2026-09-12, Python 3.11.9: 104 tests passed in 219.54 seconds (33 existing,
71 new). Test command: `py -B -m pytest -p no:cacheprovider -q --tb=short`, with
PYTHONDONTWRITEBYTECODE=1 and PYTEST_DISABLE_PLUGIN_AUTOLOAD=1. All eight template
sheets were visually inspected; the three supported import templates were also
parsed and validated by the real pipeline.

The local demo was initialized at `%LOCALAPPDATA%/CropKDS/projects` and its API
returned 200 with 179 units, 58 crops, 58 economics records and calculated_reference
water. No project import or scientific input was applied to the legacy engine.
