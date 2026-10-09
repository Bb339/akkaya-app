# V1 Reference Dataset

**REFERENCE / DEMO DATA — NOT AN OFFICIAL WATER ALLOCATION OR FIELD VALIDATION.**

This deterministic 21-file package reconstructs the inputs used by the V1 thesis-model reference workflow. Create project `v1-reference-demo` (`V1 Reference Dataset`, planning year 2024, data classification `reference_demo`), upload all CSV/GeoJSON data files through Bulk Data Upload, and explicitly confirm them in package order. The resulting active revision is 21.

P138 intentionally has no fabricated geometry. Its scientific inputs remain executable and its map state is explicitly `Geometry not provided`. The Esri/Leaflet basemap is a visualization layer and is not PROJECT_DATA.

After import:

- Projects: `/projects#project=v1-reference-demo&section=readiness`
- V1: `/?provider=PROJECT_DATA&project_id=v1-reference-demo&revision=21&seed=123`
