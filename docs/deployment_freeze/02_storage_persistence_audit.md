# Storage and persistence audit

## Project and run storage

The V2 project repository is `FileProjectStore`. It stores one UTF-8 JSON document per project:

`<KDS_PROJECT_STORE>/<project-id>/state.json`

The same document contains project metadata, data revision, imports, confirmed normalized datasets, analysis state and immutable run records/results/provenance. Writes use a temporary file in the project directory, `fsync`, and `os.replace` for atomic replacement. Updates use an OS-backed per-project lock file.

Store path resolution is:

1. `KDS_PROJECT_STORE`, if explicitly set;
2. `%LOCALAPPDATA%/CropKDS/projects` on the documented Windows setup;
3. `$XDG_DATA_HOME/CropKDS/projects` when `XDG_DATA_HOME` exists;
4. `~/.local/share/CropKDS/projects` otherwise.

The API rejects a configured store inside the application's public source tree.

## Restart behavior

| Event | Observed design behavior |
|---|---|
| Flask/Gunicorn process restart on the same local machine and same store path | Project/import/run JSON survives and is re-read. |
| Local machine reboot with the same user profile/disk | Files survive under the default local store. |
| Restart while an analysis request is running | The initially persisted run can remain permanently in `running` state; there is no startup reconciliation, resume mechanism or job queue. |
| Render-like service restart/redeploy using only the instance root filesystem | Store is ephemeral and project/import/run state can be lost. |
| Multiple WSGI processes sharing one local filesystem | Updates are serialized per project with OS file locks; all workers must resolve the exact same store root. |
| Multiple instances without a shared disk | Each instance has independent, divergent project state. |

## Uploaded-file persistence

- Multipart content is read into memory with a 10 MiB per-file and aggregate bulk-request limit.
- Raw uploaded CSV/XLSX/GeoJSON files are **not** retained as original files.
- The project JSON retains the secured filename, SHA-256 file hash, detected columns, parsed rows, mapping, options, validation issues/summary, status and transition history.
- After explicit confirmation, normalized active data and revision history are stored in the same project document.
- Therefore uploads can be reconstructed only from persisted parsed/normalized records and metadata, not from the original byte stream. Original workbook formatting, formulas and unselected workbook content are not an archival artifact.
- All of this evidence is lost with the project JSON if the filesystem is ephemeral.

## Other persistence surfaces

The legacy V1 UI also uses browser `localStorage`/`sessionStorage` for demo users, custom parcels, overrides, messages and UI preferences. That state is browser/profile-specific, is not shared institutional server state and is unaffected by `KDS_PROJECT_STORE`. Clearing browser storage or changing browser/device loses it.

## Persistent disk / database status

- Persistent disk declaration: **ABSENT**.
- `KDS_PROJECT_STORE` deployment value: **NOT CONFIGURED**.
- SQL/NoSQL database: **ABSENT**.
- Object storage for uploads: **ABSENT**.
- Backup/restore policy: **ABSENT**.
- Storage migration/versioning mechanism: **ABSENT** beyond the document's internal data revision.

## Storage blockers

1. **PERSISTENCE BLOCKER:** a Render-like deployment without an attached persistent disk loses projects, confirmed imports, stored runs and their provenance across replacement/redeploy.
2. **MULTI-INSTANCE BLOCKER:** the filesystem repository cannot provide shared consistent state across instances unless they share the same supported persistent filesystem; no database is configured.
3. **INTERRUPTED-RUN BLOCKER:** process termination can leave a run recorded as `running` indefinitely, with no recovery or reconciliation path.
4. **UPLOAD ARCHIVE LIMITATION:** original uploaded bytes are intentionally not retained. If institutional audit requirements require exact source-file retrieval, a separate immutable upload archive is necessary.

## Runtime modification assessment

- A single-instance, local-only run on a stable local disk does not require a storage code change; the current filesystem store survives ordinary process restart.
- Staging requires at minimum deployment configuration: attach a persistent disk, set `KDS_PROJECT_STORE` to its mount, define backup/restore expectations and prohibit scale-out against independent local stores.
- Runtime modification appears necessary before reliable staging for interrupted-run reconciliation and for any multi-instance/database-backed design.
- Runtime or access-layer modification is also necessary if staging is publicly reachable, because the current project/import/analysis API has no authentication.

These blockers stop the deployment-freeze milestone at Part 1. No deployment was attempted.
