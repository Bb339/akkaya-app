# Crop water parameter contract

`crop_water_parameters` is a project-scoped, versioned import contract for Kc and stage values. A row contains crop identity, applicable year, geographic scope, `kc_ini`, `kc_mid`, `kc_end`, `stage_value_mode`, `p_ini`, `p_dev`, `p_mid`, `p_late`, authority class, source, source reference, and optional notes.

Kc values must be finite and nonnegative. The frozen source currently ranges from 0.0 to 1.26. Values above 2.0 through 3.0 require warning acknowledgement; values above 3.0 are rejected to match the legacy Crop domain boundary. Source authority and provenance remain mandatory.

The frozen `crop_params_assumed.csv` uses stage **day durations** (15–30, 25–60, 40–120, and 20–60 days), even though older audit wording called them fractions. The contract therefore requires `stage_value_mode`:

- `DAYS`: all four values are finite and nonnegative and are preserved exactly. No sum-to-one rule applies.
- `FRACTIONS`: all four values are finite and nonnegative and must sum to 1.0 within floating-point tolerance.

The importer never silently normalizes either representation. `ASSUMED` and `UNKNOWN` inputs remain unverified; synthetic or `not_official` inputs remain unverified regardless of their declared authority.

Upload creates a preview only. It reports old and new resolution, authority, Kc/stage values including `stage_value_mode` and `stage_total`, affected crop and scenarios, and `requires_reanalysis=true`. Explicit confirmation creates a new active version, marks the old version inactive, links `supersedes`/`superseded_by`, retains file hash and timestamps, and does not recompute analysis.

Phase 7 stores this data but does not connect it to the scientific engine. `engine_connected=false` is part of every preview, saved dataset, readiness result, and authority snapshot.
