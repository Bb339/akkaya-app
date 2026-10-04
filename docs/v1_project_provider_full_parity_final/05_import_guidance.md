# Smart Import guidance

Focused regressions verify Turkish primary guidance and fail-closed handling for missing required columns, malformed numeric/year values, wrong planning year/scope, ambiguous mapping/type/workbook sheet, unsupported files, invalid or duplicate GeoJSON, unknown geometry IDs, and geometry/unit mismatch. BOM CSV, semicolon CSV, Turkish aliases, harmless extra columns, and column-order differences are deterministic.

Raw detector codes remain secondary technical detail. Irrelevant zero-evidence files become `IGNORED_NOT_RELEVANT`; ambiguous or invalid domain data cannot be confirmed. Geometry remains optional for science while its visual availability is reported separately.
