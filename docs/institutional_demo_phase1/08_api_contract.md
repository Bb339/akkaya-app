# API contract

- `GET /api/v2/projects/{project_id}/readiness` returns both execution profiles, domains and reanalysis state.
- `POST /api/v2/projects/{project_id}/analysis-preview` performs a dry-run selection without executing the engine.
- `POST /api/v2/projects/{project_id}/analyses` executes the selected profile and stores a pinned run.
- `GET /api/v2/projects/{project_id}/analyses/{run_id}` returns the immutable stored run.
- `GET /api/v2/projects/{project_id}/analyses/{run_id}/provenance` returns its input and engine provenance.

The existing import endpoints remain the sole upload, mapping, validation, preview and confirmation path.
