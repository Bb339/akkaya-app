# Independent general project fixture

**Synthetic test project / Sentetik test verisi.** Every number, geometry and
source record is invented for software acceptance. No scientific field claim or
real-world recommendation is made. These files are never seeded automatically
into the user's project store.

24 units GX-001..GX-024, 258 da, three test settlements, eight crop names,
annual crops and established orchards, three irrigation methods, 192 explicit
candidates, a 120000 m3 scenario budget and 12 optional geometries. Standard crop
names express the existing engine taxonomy; no reference crop records or IDs are
copied. Imported record IDs are generated from the new project identity.

`generate.py` deterministically generates CSV/GeoJSON and project creation
metadata without reading any reference file. `crops.xlsx` contains the same eight
records as crops.csv; it is an explicit-value single-sheet workbook, verified by
rendering and by the real XLSX import parser. crop_matrix.json is its typed build
input. No formula-based Excel cells are needed.

Public setup order:

1. POST project.json to `/api/v2/projects` (project creation metadata only).
2. Upload/map/preview/confirm crops.xlsx (crops), analysis_units.csv
   (analysis_units), economics.csv (economics), water_budget.csv (water_budget).
3. Confirm candidates.csv (candidates), then scientific_s1.csv (scientific_inputs).
   S1 is READY_WITH_WARNINGS for missing geometry; S2 is NOT_READY.
4. Confirm scientific_s2.csv (scientific_inputs). Both scenarios are ready with
   the optional geometry warning.
5. Confirm geometry_partial.geojson, or geometry_all.geojson for full coverage.
   Complete geometry yields READY; geometry is never required to optimize.

All science uses the typed CSV contract documented in docs/upload_format.md;
no direct store writes or scientific JSON API shortcuts are used in acceptance.

Economics.csv includes a low positive margin of 5 TL/da. The separate
economics_negative.csv stress import
contains -50 TL/da and verifies faithful storage of losses. The ready optimization
fixture uses the base economics. Existing readiness still rejects non-positive
calibrated candidate/season profits: expanding that model domain is separate
scientific work, not an excuse to replace losses with positive values.

S2 rows are explicit synthetic calibrated observations with all required seasonal,
climate, delivery, soil, crop-family and rotation tables. Their completeness proves
software routing and validation, not agronomic correctness.
