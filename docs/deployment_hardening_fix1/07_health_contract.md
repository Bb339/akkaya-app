# Health and readiness contract

`GET /healthz` is unauthenticated for platform monitoring and returns non-sensitive JSON:

- `alive`
- `ready`
- deployment-mode label
- project-store configured/existing/writable/ready flags and an operational error code
- supported execution-profile names
- authentication required/configured booleans

It never returns project content, credentials, environment values, source paths, or the effective absolute store path. A staging configuration with missing credentials, missing explicit storage, or unwritable storage returns HTTP 503 and `ready=false`. A ready profile returns HTTP 200.

