# Crop parameter and phenology import

The import lifecycle is `Upload → Parse → Mapping → Validate → Preview → Confirm → Save`. Upload and preview never replace the active dataset. Confirmation is explicit; warnings must be acknowledged, and an authority downgrade needs an explicit override. Versions are isolated by project, data type, applicable year, and geographic scope.

The importer accepts CSV and XLSX through the shared import service. Assisted mapping recognizes Turkish and English labels, including `ürün`, `crop`, `bitki`, `ekim tarihi`, `dikim tarihi`, `sowing date`, `planting date`, `hasat tarihi`, `harvest date`, and the planting/harvest window start and end fields. Ambiguous mappings are not auto-confirmed.

Identity resolution accepts an exact runtime id or one of the nine explicit reviewed parameter relations. Unknown crops and generic KABAK for the three runtime Kabak forms are rejected. Importing a parameter-only identity does not onboard it into the runtime catalog.

The templates are [crop_water_parameters_template.xlsx](data_templates/crop_water_parameters_template.xlsx) and [crop_phenology_template.xlsx](data_templates/crop_phenology_template.xlsx). Their sample rows are visibly marked `SYNTHETIC` and `not_official`, contain no formulas, and are importable by the production service. Replace every example value and provenance field with real institutional evidence before pilot assessment.

Saved versions include source file hash and provenance. A replacement preview compares records and authority, identifies affected S1/S2 scenarios, and marks analysis stale. No automatic calculation follows confirmation because Phase 7 only establishes the data contract.
