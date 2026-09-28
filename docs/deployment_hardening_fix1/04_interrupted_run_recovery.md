# Interrupted-run recovery

On the first authenticated project/API request in each application process, the file repository scans persisted projects under per-project locks. Every stale `running` record becomes `interrupted` with:

- `interruption.code = PROCESS_RESTART_INTERRUPTED`
- a stable explanatory message
- `interruption.recovered_at`
- `error = PROCESS_RESTART_INTERRUPTED`

The original run ID and timestamps remain intact. `completed_at` remains unset, and no result is fabricated. Completed and failed records are unchanged. The recovery is idempotent and the UI history renders the literal `interrupted` status. A new analysis may be started normally.

Recovery is deliberately process-start scoped instead of being applied on every read, so an active synchronous run is not reclassified by another request. This contract depends on the configured one-worker, one-instance staging topology.

