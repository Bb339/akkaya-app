# Project-to-V1 context contract

Canonical deep link:

`/?provider=PROJECT_DATA&project_id=<canonical-id>[&run_id=<id>][&unit=<analysis-unit-id>]`

`provider` and `project_id` must occur exactly once. `run_id` and `unit` may occur at most once. Project IDs accept only ASCII letters, digits, `_` and `-`, begin with an alphanumeric character and have at most 128 characters. A stored run is resolved inside the exact project.

Unit selection and new run creation update the query with `history.pushState`. Reload restores project, unit and run. Query-changing back/forward navigation reloads from the canonical backend context. V1 hash-only navigation such as `#panel` does not reload or discard provider state.

Switching to the reference provider uses `/`; switching projects constructs a fresh URL containing only the new project identity. This discards incompatible unit, preview and run state.

