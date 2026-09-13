# Generalization acceptance

Scope: GENERALIZATION + ACCEPTANCE + UX. No solver, fitness formula, weight,
diversity penalty, Kc/catalog expansion, external data service or database was added.
Baseline branch `v2-general-platform`, commit `fdce34f`, clean working tree.
Before editing: standard **141 passed in 196.72s**. The earlier 153 count was
standard 141 plus 12 extra small-fixture seed cases, not a different standard suite.

## Independent public-import fixture

`tests/fixtures/general_project` is explicitly synthetic: 24 units, 258 da,
three settlements, eight crops, annual/perennial mix, 192 candidates, drip/sprinkler/
surface irrigation, scenario budget 120000 m3 and 12 optional point geometries.
Every source is synthetic_test_fixture. A complete 24-point variant tests READY.

`general_project_support.import_project` creates the project through POST and
passes every dataset through multipart upload, parser, mapping, validation,
preview, explicit warning acknowledgment and confirmation. Crops use XLSX;
units/economics/candidates/budget/scientific tables use CSV; geometry uses GeoJSON.
No direct Project Store seeding or scientific JSON POST is used for this fixture.

Economics includes a low margin; a separate negative-economics file is accepted
without changing -50 to zero or a profit. The ready fixture uses base economics.
Non-positive calibrated candidate/season profits remain outside current readiness.
This is a documented model boundary, not a fabricated positivity conversion.

## Independence evidence

The subprocess guard is installed before importing app. It rejects all file opens
under the reference data directory, LegacyReferenceProvider.read, reference
snapshot/read_optional and build_demo. Attempts are counted even if legacy code
catches exceptions. General readiness, bundle building and optimization run under
this guard; every S1/S2 x GA/ACO/ABC case runs twice with seed 2468.

Two actual dependencies were identified and removed from the general path:

1. Readiness crop classification now uses the uploaded catalog under its own
   provider scope; it previously could read the default reference crop catalog.
2. Result water-allocation explanation now crosses the provider boundary.
   app.py has exactly one additional data-provider decorator; its function body
   and scientific formulas are unchanged. General explanation metadata uses the
   project's budget/area/settlements. Reference explanation retains its old values.

Canonical settlement/name fields are used by the generic adapter. Reference
place names, matrix filename, 179-unit count, 134919-da area and 100700080.81-m3
budget are not inputs to the independent project. Standard crop taxonomy names
are supported model vocabulary; crop records and IDs are not copied from Akkaya.

## Readiness and isolation

READY: full geometry plus complete science. READY_WITH_WARNINGS: complete science
with missing/partial optional geometry. NOT_READY: required economics, Kc, budget,
water, candidates or scientific sections missing. S1 remains ready without S2
season/rotation data; S2 becomes ready only after those data are supplied.

Public invalid imports cannot mutate active data or data_revision. Uploaded
status does not imply confirmed data. General and reference project bundles are
compared across sequential and concurrent fresh-process execution. Reference
isolation uses the small P1/P23/P149 subset; Tier 2 separately covers all 179 units.

## User workflow

`/projects`: projects/new project -> data management -> readiness -> analysis ->
result -> history. Overview includes project/year/region, budget kind, unit/area/
crop/economics/candidate/geometry coverage, S1/S2 statuses and last import/run.
Each group displays Missing, Uploaded, Warning or Ready with readiness details.

History lists run ID, time, scenario, algorithm, seed, objective, status,
feasible, water, profit, TL/m3 and score. It fetches 25-row pages and opens stored
run detail after a page reload. New runs snapshot budget kind/source and project
source label so later budget edits cannot relabel the history.

Synthetic labels are visible in project and result sections. calculated_reference
is labeled calculated reference demand, never official allocation or measured
reservoir water. Missing plan difference is "Motor bu metrik için değer üretmedi";
missing historical metrics are not zero. Failed history keeps null metrics.

## Test tiers

Run commands from the V2 repository using the existing Python test environment:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
# FAST: no heavy scientific cases or browser
py -B -m pytest -q -p no:cacheprovider --ignore=tests/test_decision_pipeline.py --ignore=tests/test_defense_datasets.py -m 'not scientific_regression and not general_execution and not browser and not full_project'
# STANDARD: includes all prior standard tests, general project and browser
py -B -m pytest -q -p no:cacheprovider
# Tier 1: small fixtures, 3 seeds; plus scientific source guard
$env:KDS_EXTENDED='1'
py -B -m pytest tests/test_scientific_execution.py tests/test_scientific_source.py -q -p no:cacheprovider
Remove-Item Env:KDS_EXTENDED
# Tier 2: full 179 units, one seed for all six scenario/algorithm pairs
$env:KDS_FULL_PROJECT='1'
py -B -m pytest tests/test_full_project_acceptance.py -q -p no:cacheprovider
# Tier 3: manual/nightly profile, 3 seeds for all six full-project pairs
$env:KDS_NIGHTLY='1'
py -B -m pytest tests/test_full_project_acceptance.py -q -p no:cacheprovider
Remove-Item Env:KDS_NIGHTLY
Remove-Item Env:KDS_FULL_PROJECT
```

Tier 2/3 cases are deselected by default, so the standard suite does not pay their
execution cost. Tier 3 is a runnable profile, not an installed scheduler.
Tier 1 passed **23/23 in 399.25s** (20 science + 3 source tests).
Tier 2 passed **6/6 in 815.79s**, comparing all deterministic raw fields with
rel=1e-10 / abs=1e-7. Feasible=false remains a valid parity result, not a claim
of an implementable agricultural plan. Tier 3 was not run in this milestone.
Browser acceptance passed **2/2 in 50.64s** before the final compact history styling.
Final FAST/STANDARD results are recorded in the closing verification below.

## Remaining limits and next work

- Synthetic completeness and reproducibility do not establish agronomic validity.
- S2 final fitness is still unavailable in the raw engine output; no substitute score.
- 58/69 crop discrepancy remains the existing scientific data-quality backlog.
- Explicit scientific tables are a technical input contract; no automatic season,
  candidate or climate generation has been added.
- File store reads whole documents; synchronous HTTP, timeout and lack of project
  authorization remain architectural boundaries for later hosted operation.
- Next scientific milestone: independent real-field input review, negative/zero
  margin semantics, crop concentration and calibration against an approved baseline.
- Next architectural milestone: durable background jobs, history retention and
  authorization, keeping scientific engine behavior behind the same boundary.

V1 unchanged; no production deployment; no remote push.

## Closing verification — 13 September 2026

- FAST: **114 passed, 23 deselected in 232.47s**.
- STANDARD: **164 passed, 6 deselected in 1037.09s**. All 141 prior standard
  tests plus 23 new acceptance tests are included; only Tier 2 full-project cases
  are deselected. The test-only browser synchronization improvement was additionally
  verified by the final focused browser run below.
- Tier 1 EXTENDED: **23 passed in 399.25s**.
- Tier 2 EXTENDED: **6 passed in 815.79s**.
- Final focused Chromium workflow: **1 passed in 80.94s**, after compact history
  styling and explicit waiting for the overview API response on cold starts.
- Manual reference-label verification: real S1 GA, seed 123, three reference units,
  temporary store, calculated_reference visible in both provenance and Chromium UI.
- XLSX typed values equal the eight source records; no formula cells; visual review passed.
- Source check: restoring the single new provider decorator yields byte-normalized
  equality to fdce34f app.py; original function bodies and three legacy assets match.
- V1 HEAD/tag unchanged: a49daac1ae6d15d83428565c388bfafb4b6da08a.

Wall times were measured on this Windows host with overlapping validation workloads;
they are not isolated CI benchmarks. The observed standard run took 17 minutes:
CI runtime profiling remains a practical follow-up. Full-project multi-seed work
is not enabled in the default suite. No Tier 3 execution, production deployment,
remote push or persistent synthetic demo installation was performed.
