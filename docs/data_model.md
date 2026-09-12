# Project data model

## Project

Fields: id, name, description, country, province_or_region,
basin_or_irrigation_area, planning_year, annual_water_budget, water_budget_unit,
data_source_notes, status, created_at, updated_at, optional owner_id.

Ids: 1–64 lowercase ASCII letters/digits/hyphens; no traversal and no Windows
device names. Name is non-empty. Year is integer 1900–2200, water is finite and
nonnegative, unit explicitly m3/hm3. Status: draft/active/archived. Owner is metadata,
not authentication. Application and domain never know a JSON path.

## AnalysisUnit / Analiz Birimi

Fields: id, project_id, external_id, name_or_code, settlement, area_da,
current_crop, irrigation_method, latitude, longitude, geometry, metadata.
External ids are project-unique and case-sensitive. Internal ids are stable hashes
scoped to project identity. Area is >0; crop is non-empty. Coordinates/geometry are
optional. Coordinates are WGS84. Geometry implies neither cadastral status nor area.

## Crop

Fields: id, project_id, name, crop_group, perennial, kc_initial, kc_mid, kc_end,
stage_initial_days, stage_development_days, stage_mid_days, stage_late_days,
planting_date, harvest_date, source, confidence_level, active, metadata.
Catalog membership is project-scoped. Import duplicate matching normalizes
case/diacritics/spacing; display names and confidence labels retain source text.
If normalization conflates two real crops, resolve naming explicitly before import.

Missing Kc/fenology stays null. Negative Kc or Kc>3 is ERROR; Kc>2 is WARNING.
Stages are nonnegative days; dates use YYYY-MM-DD. No agronomic defaults are invented.

## Economics

Fields: project_id, crop_name, year, yield_per_da, net_profit_per_da, currency,
source, metadata. Import key: normalized crop name + year. Yield is nonnegative;
negative net profit is valid. Currency is uppercase three-letter text or null.
metadata.yield_unit carries declared units; missing units warn and no conversion
is guessed. Unmapped cost/source fields stay in metadata and can later become
typed sale-price, input, labor, energy, irrigation and machinery cost fields.

## WaterBudget

Fields: project_id, amount, unit, kind, period, source, metadata.
Kinds: measured, official_allocation, calculated_reference, scenario, unknown.
Period currently defaults to annual but is extensible. Project amount/unit and
initial WaterBudget are created together. Akkaya is calculated_reference, never
official allocation or available reservoir water.

## ImportBatch and provenance

Fields: id/project_id/data_type, sanitized filename, SHA-256, uploaded_at, status,
detected_columns, mapping, validation_summary, issues, rows, options, base_revision,
history and applied_revision. Issues carry severity/code/message/row/column/value.
CSV/XLSX line numbers include headers; GeoJSON feature numbers start at 1.

Numbers are JSON numbers. Exact thesis reference decimals and original source
strings remain in metadata for Decimal regression. Catalog profit rates must not
replace unit-level baseline totals. Confidence labels are not promoted to measurements.
