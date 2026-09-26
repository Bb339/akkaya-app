# Smart Import Detection Contract

Detection is deterministic assistance. It proposes a dataset type and mapping; it does not activate any record.

## Inputs and evidence

- Accepted formats: CSV, XLSX and GeoJSON.
- Evidence: normalized filename, XLSX sheet name, headers, required-field coverage, ambiguous header aliases, first 200 rows' value types, planning year, geographic scope and authority fields.
- Tie breaking is stable: score descending, then canonical dataset type ascending.
- XLSX evidence includes all sheet names and the selected sheet. The first sheet is selected only when the caller did not select one.

## States

| State | Meaning | Activation |
|---|---|---|
| `AUTO_MATCHED` | One type wins, required fields map, and year/scope agree | Creates an unconfirmed batch only |
| `REVIEW_REQUIRED` | Required fields are missing or year/scope differs | No batch |
| `AMBIGUOUS` | Dataset type, mapping, or package duplicate is ambiguous | No batch |
| `UNSUPPORTED` | Extension is outside CSV/XLSX/GeoJSON | No batch |
| `INVALID` | Supported container cannot be parsed | No batch |

`AUTO_MATCHED` is not approval. Data reaches active project state only through the existing mapping/preview and explicit `confirm=true` endpoint. Missing scientific values are never inferred.

## Safety boundaries

- At most 40 files per request.
- Each file and the aggregate request use the existing upload byte limit.
- Duplicate content hashes in the same package become `AMBIGUOUS`.
- Wrong planning year and geographic scope remain fail closed as `REVIEW_REQUIRED`.
- The detector does not modify scoring, optimization, readiness, water, economics, crop identity, or provenance semantics.
