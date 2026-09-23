# Readiness truth table

| State | status | dataset_selected | engine_connected | connection_state |
|---|---|---:|---:|---|
| Valid selected executable domain | READY | true | true | CONNECTED |
| Missing/invalid/ambiguous/stale evidence | NOT_READY | false | false | INVALID_OR_UNAVAILABLE |
| Physical environmental release with current engine | NOT_READY | false | false | NOT_EXECUTABLE_WITH_CURRENT_MODE |

`consumer_available` and `consumer_role` are separate from current project connectivity. Guards cover missing annual water, missing phenology, stale economics, ambiguous crop parameters, unsupported physical release, and a complete project.
