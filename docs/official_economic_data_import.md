# Official economic data import

Use the project data-management page or the `/api/v2/projects/{project_id}/imports` endpoints. Select one of the seven economic data types and upload CSV or XLSX. Formula cells are rejected; upload explicit values.

1. Start from the matching file in `docs/data_templates`.
2. Replace every `SYNTHETIC` / `not_official` example and cite the institution, document or reference.
3. Keep one planning year, authority, geographic scope and crop scope in a file.
4. Use an exact crop identity already present in the project catalog.
5. Review normalized units, conversion trace, old/new values, authority change, affected units/crops/scenarios and re-analysis impact.
6. Map columns again if active project data changed after preview.
7. Confirm explicitly. A lower-authority replacement additionally requires acknowledgement and a reason.

Required common fields are `planning_year`, `observation_year`, `authority_class`, `currency`, crop and type-specific fields. Recommended provenance fields are `source_institution`, `source_document`, `source_reference`, `source_date`, `price_date`, `price_period`, `price_basis`, `geographic_scope`, `crop_scope`, `measurement_method`, and `notes`. Confirmation adds `uploaded_filename`, SHA-256 `file_hash`, and `import_batch_id`.

TRY is canonical. USD, EUR or another currency is rejected in this milestone. A future FX conversion must carry source and target currency, rate, date and source. Inflation adjustment is not performed. Observation year may be retained as stale or future evidence and is flagged; it is never silently treated as the planning year. Mixed-year yield and price require a future explicit scenario and provenance design.

After confirmation, inspect `economic_data.datasets`, its scope-keyed `active` pointers and `reanalysis`. Existing AnalysisRun records are retained. The imported values remain disconnected from all optimization paths until a separate verified economics integration milestone.
