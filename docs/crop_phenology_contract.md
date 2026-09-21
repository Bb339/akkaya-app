# Crop phenology contract

`crop_phenology` stores project-scoped planting and harvest evidence separately from Kc stage durations. Every row identifies a runtime crop, applicable year, geographic scope, season, mode, authority class, source, source reference, and optional notes.

Two modes are supported:

- `YEAR_SPECIFIC` requires full ISO dates (`YYYY-MM-DD`). `applicable_year` is the planning/harvest-season year: harvest must occur in that year, while planting may occur in that year or the immediately preceding year. Planting must precede harvest.
- `CLIMATOLOGICAL_WINDOW` requires separate month-day (`MM-DD`) start and end values for planting and harvest windows. Each window must be internally ordered. A spring-to-autumn sequence is `SAME_CALENDAR_YEAR`; an autumn-to-next-summer sequence is `CROSSES_CALENDAR_YEAR`. Overlapping/interleaved windows are invalid.

Mode-specific fields cannot be mixed and are rejected rather than ignored. Every normalized and persisted record carries `season_year_semantics` as `SAME_CALENDAR_YEAR` or `CROSSES_CALENDAR_YEAR`. The crop must exist in the project's runtime catalog, the scope must be present, the season must be explicit, and source plus source reference are mandatory. Invalid dates are errors. `OFFICIAL`, `LOCAL_INSTITUTIONAL`, `PEER_REVIEWED`, and `EXPERT_VALIDATED` can qualify as verified evidence; `ASSUMED`, `UNKNOWN`, synthetic, and `not_official` records cannot.

The frozen Akkaya runtime/project source data contains no sourced planting or harvest values. Current verified completeness is therefore 0/58. The schema's ability to import dates does not imply that those values currently exist.

Confirmed versions retain dataset id, version, status, authority, valid-from/to years, upload and confirmation timestamps, predecessor/successor links, file hash, source reference, and normalized records. Activation sets `requires_reanalysis=true` but does not trigger recomputation. The scientific engine remains disconnected in Phase 7.
