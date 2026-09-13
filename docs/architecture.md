# V2 architecture

V2 connects project-scoped inputs to the preserved thesis scientific engine.
The modular `/projects` page supports import, readiness, execution, stored results
and analysis history. The legacy main page remains separate.

## Responsibilities and boundaries

- `kds/domain`: project, unit, crop, economics, budget and AnalysisRun records.
- `kds/data`: OS-locked atomic JSON project store, outside the public source tree.
- `kds/imports`: bounded CSV/XLSX/GeoJSON parsing, mapping, validation and preview.
  `scientific_tables` handles explicit candidates, typed scientific tables and budgets.
- `kds/application`: project/import transactions, readiness, optimization, overview
  and bounded history projections.
- `kds/adapters`: project-to-engine translation; reference-only files are confined
  to the reference adapter. `project_catalog` scopes readiness classification to
  the uploaded crop catalog even before a complete scientific bundle exists.
- `kds/science`: immutable bundle, provider boundary and fresh process per run.
- `kds/api.py`: thin Flask routes; `kds/ui`: independent classic JS/CSS/template.

HTTP -> application -> domain/repository. Scientific calls additionally pass
through immutable bundle -> provider -> existing engine. There is no new solver,
formula, database or frontend framework.

## Three distinct data roles

1. Akkaya: demo/reference project, frozen thesis source provenance. Its
   `calculated_reference` budget is calculated demand, not an official allocation.
2. Synthetic fixture: tests only; `data_source_notes=synthetic_test_fixture`, with
   the visible bilingual watermark. It is never automatically seeded into user data.
3. General real project: user-provided data, explicit source/quality information.
   Missing required scientific data blocks execution; reference data is not substituted.

## Import transactions

A sanitized upload name, content hash, parsed rows, mapping, validation and state
history are persisted. Preview does not change active data. Confirmation revalidates
under the project lock and checks data_revision. ERROR blocks; WARNING requires
acknowledgment. Reconfirmation is idempotent; confirmed mappings cannot be edited.

Core tables replace their entire collection. Geometry merges by external_id.
Candidate imports replace only candidate options. Scientific imports replace only
supplied maps/tables, preserving omitted sections. Budget import is one explicit row.
All these changes and the applied import event share one atomic transaction.

## Execution and history

Each run receives an immutable data snapshot and a separate Windows spawn process.
Python/NumPy RNG and mutable engine views stay inside that run. Readiness uses a
project catalog scope, not the default legacy provider. Water allocation context
in the result is also supplied by the provider; only the reference project reads
reference explanatory files. This is presentation context, not an optimization rule.

AnalysisRun snapshots budget kind/source, project name and source classification.
Later budget edits do not relabel old results. Older records without that snapshot
show missing provenance explicitly. `GET .../analyses` sorts newest first, returns
summary projections and bounds pages to 200 rows. Details are fetched separately
within the project. Failed runs preserve missing metrics as null.

The UI uses 25-row history pages. Missing, Uploaded, Warning and Ready are data
management states; scenario readiness remains a separate scientific decision.
Uploaded means pending confirmation, not active imported data.

## Storage and operational limits

Default Windows store: `%LOCALAPPDATA%/CropKDS/projects`; `KDS_PROJECT_STORE`
overrides it. Per-project locks plus temp-write/fsync/replace protect commits.
This is local persistence isolation, not authentication or a distributed database.
History pagination bounds response size; the current store still loads a whole
project document. Execution is synchronous HTTP with a child-process timeout.

Before hosting: authentication/authorization, narrower legacy static routes,
background jobs, retention/backup and scalable history storage are separate work.
Scientific policy improvements and the 58/69 catalog discrepancy also remain separate.
See `generalization_acceptance.md` for executed acceptance tiers and limitations.
