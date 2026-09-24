# Readiness selection semantics

Fix4 records selection before strict validation. A selected resource remains selected when it is stale, out of scope, for the wrong year, ambiguous, incomplete, unsupported by the current execution mode, or otherwise invalid.

The four readiness axes are independent:

- `dataset_selected`: an active pointer resolves to a project dataset/resource.
- `dataset_valid`: that selected resource passes the applicable contract checks.
- `consumer_available`: the application has a consumer for the domain.
- `engine_connected`: the resource is valid, required for the scenario, and connected to the current execution path.

Missing or dangling pointers produce `dataset_selected=false`. Selection alone never authorizes execution; strict resolvers remain unchanged and verified execution continues to fail closed.

