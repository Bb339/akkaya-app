# Decision Screen Bridge Contract

The route `/projects/decision` accepts exactly three context values: `project_id`, `run_id`, and `execution_profile=VERIFIED_INSTITUTIONAL`.

The page retrieves the named project and the immutable stored run through `/api/v2/projects/{project_id}/analyses/{run_id}`. It verifies that returned project, run and profile identities exactly match the URL context before rendering. KPIs, water accounting, crop shares, unit results, map markers and provenance come from the backend presentation adapter; JavaScript does not recompute scientific results.

Missing or mismatched context fails closed with an explicit message. There is no call to `/api/optimize`, no read from frozen Akkaya files and no reference fallback. Synthetic institutional runs retain `SYNTHETIC TEST DATA · NOT OFFICIAL`; the provider remains `VERIFIED INSTITUTIONAL`.

The accepted V1 `index.html` remains byte unchanged to preserve its scientific freeze. The project-page registration layer adds a single `Projeler / Kurumsal veri` link to the served `/` response. Cross-navigation is also provided from the project workspace to `AKKAYA REFERENCE`, from a stored project result to `KARAR EKRANINDA AÇ`, and from the decision screen back to both project and reference contexts. No scientific or legacy V1 script is modified.
