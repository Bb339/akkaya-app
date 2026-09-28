# Project Context Restore Contract

`/projects#project=<project_id>` is now an executable navigation contract.

After the project list loads, the client parses the hash with `URLSearchParams`, requires an exact project identity match, marks that card active, opens the detail workspace and refreshes only that project's API context. User selection writes the same canonical hash without causing a duplicate hashchange cycle.

Hash changes are handled with the same rules. If the identity does not exist, the current project is cleared, active styling is removed, project/result detail is hidden, and an explicit error is shown. No other project is selected and no reference provider is used.

The decision screen keeps `project_id` and immutable `run_id` separate. Returning restores the project; the user may reopen the same stored run from project history and return to the identical decision URL.
