# Bulk Import Flow

1. The user selects one or more CSV/XLSX/GeoJSON files on `/projects`.
2. `POST /api/v2/projects/{project_id}/bulk-imports` analyzes every file and returns a row with detected domain, year, scope, row count, mapping, authority, confidence and state.
3. Only `AUTO_MATCHED` rows receive an unconfirmed import batch. Project revision and active datasets remain unchanged.
4. The UI enables **Açıkça onayla ve projeye uygula** only when every row is auto matched.
5. On explicit confirmation, batches are remapped and confirmed in dependency order: catalog and units, core economics/water, candidates/current pattern, water authority tables, economics tables, crop parameter tables, then geometry.
6. The existing import service validates every batch and creates versioned active pointers. A failure stops the sequence and remains visible.

The prepared package contains 20 input files. Initial detection is 20/20 `AUTO_MATCHED`; upload alone leaves `data_revision=0`, empty analysis units and no active water dataset. Only the explicit confirmation step applies them.
