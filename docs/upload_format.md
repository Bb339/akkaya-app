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


## Explicit scientific inputs for project analyses

Use POST /api/v2/projects/<id>/scientific-inputs, or the JSON file control on
/projects. This replaces that project's scientific-input sections atomically
and increments data_revision. It does not activate CSV imports or fill missing
values. The returned per-scenario readiness report explains remaining gaps.

The top-level sections are:

- candidates: array with analysis_unit_id (external id), crop, water_requirement_m3_da,
  profit_per_da (TRY), yield_ton_da, allowed (boolean), suitability (0..1),
  rotation_status (source statement), optional risk. Every unit needs its
  approved current option. Other options may be sparse; no regional values
  are manufactured. All candidate amounts are explicit values.
- unit_parameters: object keyed by external id; each value includes
  current_water_m3, current_profit (TRY), soil_class, parcel_type
  (field/vegetable/orchard).
- irrigation: object keyed by crop name, with default method, recommended method
  and efficiency in (0,1].
- crop_families: crop-name to family-name map, required for S2.
- rotation_rules: array including type, from_family, to_family, penalty_weight;
  required for S2. Existing engine rule semantics are retained.
- calendar: optional presentation/calendar rule map.
- seasonal_resources: S2 tables, each an array of scalar row objects.

S2 seasonal_resources tables:

| Table | Required columns/coverage |
|---|---|
| s2 | parcel_id, crop, year, season (primary/secondary), area_da, water_m3_calib_gross, profit_tl, planting_date, harvest_date, yield_ton, price_tl_ton, variable_cost_tl, irrig_efficiency; complete unit/crop/season coverage |
| s1 | prior-year parcel_id, crop, year history for every unit |
| parcels | parcel_id, district, land_capability_class; every project unit |
| reservoir | month, irrigation_m3_baseline; 12 months, sum equals project water budget |
| delivery | month, max_delivery_m3_assumed; 12 explicit positive capacities |
| monthly_climate | parcel_id, month, et0_mm, precip_mm; 12 months per unit |
| water_quality | month, ec_dS_m_assumed; 12 months |
| crop_suitability | crop, land_capability_class, suitability_score; complete soil/crop coverage |
| irrigation_methods | method, typical_total_efficiency |
| crop_params | existing engine Kc parameter table, supplementary to project crop records |
| soil_params | explicit source soil-parameter rows |

Dates use ISO YYYY-MM-DD. Nonfinite numbers, nested table cells and unknown
sections are rejected. Structural validation does not assert agronomic
correctness. Valid but incomplete inputs remain NOT_READY. The current engine's
calib/none-risk policy and product classification scope are documented in
scientific_project_execution.md.

Budget type can be set through POST /api/v2/projects/<id>/water-budget with
amount, unit (m3/hm3), kind and source. The UI exposes the same operation.
The four existing XLSX template filenames are unchanged; candidate_rules_template
remains a rule-schema guide, not an automatic agronomic candidate generator.

## Public CSV/XLSX scientific imports

All paths below use the existing `/imports` upload -> mapping -> preview -> explicit
confirm transaction. JSON scientific-input POST remains supported for compatibility,
but the general acceptance fixture does not use it.

| data_type | Required columns | Confirmation policy |
|---|---|---|
| candidates | analysis_unit_id, crop, water_requirement_m3_da, profit_per_da, yield_ton_da, allowed, rotation_status, suitability, source | Replace candidates only; optional risk |
| scientific_inputs | section, record_id, field, value_type, value, source | Replace supplied scientific maps/tables; preserve omitted sections |
| water_budget | amount, unit, kind, source | Exactly one row; replace budget and project budget fields |

`scientific_inputs` is a typed long table. Rows with the same section/record_id
form one record; field is a column name inside that record. value_type is exactly
text, number, integer or boolean. Values must be explicit and finite. Duplicate
fields, unknown sections and inconsistent sources for one record are errors.
A blank value never silently becomes zero.

Sections:

- unit_parameters, irrigation, calendar: record_id is the unit/crop key.
- crop_families: record_id is crop name; field must be family and type text.
- rotation_rules: record_id identifies one rule; fields include type,
  from_family, to_family and penalty_weight.
- seasonal_resources.s1 / s2 / parcels / reservoir / delivery / crop_params /
  monthly_climate / water_quality / soil_params / crop_suitability /
  irrigation_methods: record_id groups the scalar columns of one table row.

Example (all values below are synthetic):

```csv
section,record_id,field,value_type,value,source
unit_parameters,GX-001,current_water_m3,number,880,synthetic_test_fixture
unit_parameters,GX-001,current_profit,number,5200,synthetic_test_fixture
unit_parameters,GX-001,soil_class,text,II,synthetic_test_fixture
unit_parameters,GX-001,parcel_type,text,field,synthetic_test_fixture
```

The scientific schema and completeness rules from the JSON section above still
apply after reconstruction. Successful parsing is not scientific readiness.
The per-record source is retained in scientific records and the original batch;
crop-family sources remain traceable through the imported rows and batch hash.

A synthetic project is declared using `data_source_notes=synthetic_test_fixture`
in project creation, or the corresponding UI source selector. All fixture row
sources have this value. Genuine user projects must use their actual sources.
A scenario budget is a user/test scenario; calculated_reference is calculated
reference demand and must not be labeled measured reservoir water or official allocation.
