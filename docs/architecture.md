# Project/data milestone

V2 adds a project data foundation to Flask. The scientific engine and main UI
retain their existing inputs. Imported projects are inspectable via V2 services
and API; they are **not yet inputs to the legacy optimizer**.

## Responsibilities

- `kds/domain`: validated, site-independent records and shared invariants.
- `kds/data/repositories.py`: repository protocol; application services know no paths.
- `kds/data/project_store.py`: OS-locked, atomic UTF-8 JSON persistence.
- `kds/imports`: bounded parsing, aliases, normalization, geometry validation, preview.
- `kds/application`: project and import lifecycle use cases.
- `kds/adapters/akkaya_demo.py`: thesis source conversion and provenance.
- `kds/api.py`: Flask blueprint, registered by a small call in app.py.

Dependency flow: HTTP → application → domain/repository interface. The composition
root injects persistence. No new module imports app or reimplements the scientific
engine. No database, ORM or new frontend framework is introduced.

## Store and transactions

Default Windows root: `%LOCALAPPDATA%/CropKDS/projects`. Other systems use
`$XDG_DATA_HOME/CropKDS/projects` or `~/.local/share/CropKDS/projects`.
`KDS_PROJECT_STORE` overrides this centralized root. Flask rejects a store inside
its public source tree. Prefer a local, non-synchronized disk.

Each `<root>/<project_id>/state.json` contains project, water budget, analysis
units, crops, economics, metadata, import batches and data_revision. A project OS
lock lives at `<root>/.<project_id>.lock`. Combining data and batch state in one
document gives confirmation a single atomic commit point.

Under an exclusive lock: read latest document → mutate in memory → encode strict
JSON → write/fsync a same-directory temporary file → os.replace. Failure before
replacement leaves active data intact. Temporary files are removed on handled
failures. Abrupt termination may leave an unreferenced `.write-*` file; it is never
active data. Readers see complete versions. Locks cover worker processes, but this
is a bounded local store, not a distributed or network-filesystem transaction system.

## Import consistency

Raw uploaded executables/files are never persisted: only sanitized names, hashes,
parsed rows and audit records are saved. Duplicate project/type/hash/options
uploads return 409 and identify the existing batch. Different projects are isolated.

Confirmation revalidates under the project lock. Stale base_revision returns 409;
resubmit mapping to refresh the preview. All ERRORs block; every WARNING requires
explicit acknowledgment. Active data, confirmed/applied events and revision are
committed together. Repeated confirmation is idempotent; applied mapping is immutable.

Tabular imports replace the selected collection in full. Geometry imports merge by
existing external_id. Other collections stay unchanged. A replacement catalog
that omits referenced crops raises warnings.

## Security boundary and remaining technical debt

Authentication is not implemented. Use locally: persistence isolation is not
authorization. Production was not changed. Legacy broad static-file serving and
write-capable GET routes remain existing debt; runtime data is outside that tree.

Deferred work:

1. Call graph + browser tests before removing parallel frontend calculations.
2. Expose matrix fallback reasons without changing fallback mathematics.
3. Project-scope the scientific cache and RNG when adapting optimization inputs.
4. Capture seeded S1/S2 golden outputs before engine integration.
5. Version scientific policies separately: profit caps, default coefficients,
   effective rain, zero-denominator conventions and scoring weights.
6. Add project authorization and narrow static routes before hosted use.
7. Add retention/backup and database persistence when audit history grows.
8. Add topology, overlap and reprojection only in a later GIS milestone.
