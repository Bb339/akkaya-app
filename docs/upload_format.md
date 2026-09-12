# Upload contract

## Supported formats and limits

CSV: UTF-8 (BOM supported), comma/semicolon/tab detection or explicit delimiter.
XLSX: first worksheet unless options.sheet names another; row 1 contains headers.
Formula cells are rejected: upload explicit values. GeoJSON: FeatureCollection.
Limits: 10 MiB/file, 20,000 rows/features, 100 columns, 50 MiB expanded XLSX.
Bounded in-memory parsing means no raw upload directory or executable files.
Sanitized filename, hash and parsed rows are stored outside the source tree.

| data_type | Required columns |
|---|---|
| analysis_units | external_id, settlement, area_da, current_crop |
| crops | crop_name |
| economics | crop_name, year, yield_per_da, net_profit_per_da |
| geometries | external_id, geometry |

Optional fields match domain models. AnalysisUnit also accepts notes; Economics
accepts yield_unit. Candidate-rule template is a schema draft only, not an active
rule importer. Separate water-budget import is deferred; Project creation accepts
an explicit annual budget/unit.

## Mapping and units

Mapping direction: canonical field → original column. Turkish/English aliases
include parsel_id/unit_id → external_id, köy/village → settlement,
alan (da)/dekar → area_da, ürün/crop → current_crop, ürün adı → crop_name,
yıl → year, net_kar_tl_da → net_profit_per_da, kaynak → source.

Ambiguous matches are not automatically selected. Generic area requires explicit
options.area_unit="da"; no hectare conversion is guessed. Decimal separator defaults
to a dot. Set options.decimal_separator="," for 1234,50 or 1.234,50. Invalid or
nonfinite values are errors. Typed Excel numbers do not depend on display locale.
Optional blanks stay null; missing currency is never silently replaced with TRY.

## API workflow

1. POST /api/v2/projects with JSON:
   {"id":"example","name":"Example","planning_year":2024,
    "annual_water_budget":1000,"water_budget_unit":"m3"}.
2. POST /api/v2/projects/example/imports using multipart fields file, data_type,
   and optional options (JSON object). Content-Length is required.
3. Inspect response: batch id/status, columns, suggested/actual mapping,
   ambiguities, row_count, first 20 raw/normalized rows, issue details and counts.
4. POST .../imports/<batch_id>/mapping with {"mapping":{...},"options":{...}}.
   Mapping replaces the full mapping. Only area_unit/decimal_separator may change
   after parsing; sheet/delimiter changes need a new upload.
5. GET .../imports/<batch_id>. If stale=true, resubmit mapping to refresh validation.
6. POST .../imports/<batch_id>/confirm with
   {"confirm":true,"acknowledge_warnings":true}.
7. GET .../analysis-units, .../crops, .../economics. Pagination offset>=0,
   limit 1–1000, default 200. GET /api/v2/projects lists projects; GET a project
   returns counts, revision, water budget and metadata.

Bad input: 400; missing records: 404; duplicate/stale/unready operation: 409;
oversize HTTP file: 413. Malformed supported files yield a 201 response containing
an invalid batch and ERROR report, never a successful active import.

## Validation and activation

All ERRORs block: required mapping/value missing, duplicate identity, invalid area,
number/Kc, malformed file/geometry, unmatched feature external_id. All WARNINGs
require explicit acknowledgment: unknown crop; missing geometry/source/confidence/
Kc/currency/yield unit; unusual Kc; removed referenced catalog crops. INFO never
blocks. Acknowledgment does not fill missing fields.

CSV/XLSX import REPLACES the entire selected collection. Preview declares
replacement_policy. Geometry-only import merges existing external ids and
preserves other units. No active data changes before confirm. Confirmation
revalidates and writes atomically; repeat confirm is idempotent. Applied batches
cannot be remapped. Duplicate hash/type/options returns existing batch id in a
409 error. Different projects remain isolated.

## GeoJSON

Require FeatureCollection, Feature objects and properties, mapping external_id
from properties or aliases. Geometry-only imports must match existing unit ids.
Duplicate ids and exact duplicate geometry objects are errors. Support Point,
MultiPoint, LineString, MultiLineString, Polygon, MultiPolygon. Check coordinates,
WGS84 bounds, nesting, minimum position counts and ring closure. No advanced
topology or spatial-equivalence engine. CRS declarations are rejected; no reprojection.
Analysis-unit geometry may be absent; geometry-only uploads require geometry.

## Templates

docs/data_templates contains four XLSX files. Import Data, read Guide, replace
the fictional example row. Examples are neither Akkaya requirements nor agronomic
recommendations. candidate_rules_template is documentation only in this milestone.
