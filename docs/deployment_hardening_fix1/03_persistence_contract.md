# Persistence contract

Private staging requires `KDS_PROJECT_STORE`. `render.yaml` maps it to `/var/data/crop-kds/projects` under the attached persistent disk at `/var/data/crop-kds`. Missing or unwritable staging storage fails readiness and blocks protected routes. The application does not silently accept an ephemeral staging fallback.

Each project remains a locked, atomically replaced JSON document. A restart with the same disk retains projects, normalized imports, runs, results, and provenance. This design is limited to one instance and does not provide database concurrency, distributed locking, backup, or cross-region recovery.

Startup diagnostics retain the effective path in the application operational extension and log it. `/healthz` exposes only configured/existing/writable/ready booleans and an error code, never the absolute path.

`ORIGINAL_UPLOAD_ARCHIVE = NOT PROVIDED`

The store retains filename, SHA-256 file hash, parsed/mapped rows, validation history, and normalized confirmed data. It does not retain the exact original CSV/XLSX/GeoJSON byte stream, workbook formatting, formulas, or unused workbook content.

