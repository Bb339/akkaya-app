# Authentication contract

`KDS_DEPLOYMENT_MODE=local-development` explicitly disables authentication for local use. Every other mode is closed; private staging becomes ready only when mode, persistent store, username, and password are configured.

Private staging uses server-side HTTP Basic Auth with constant-time credential comparisons. Credentials come only from `KDS_BASIC_AUTH_USERNAME` and `KDS_BASIC_AUTH_PASSWORD`. They are neither committed nor included in health, logs, project state, or run provenance.

The gate covers `/projects`, `/projects/decision`, project assets/templates, and `/api/v2/*`, including import, upload, confirmation, preview, and analysis routes. Missing or invalid credentials disclose no project data. The V1 reference root remains available for static/reference navigation.

This is a minimal private-demo boundary. It does not provide users, roles, credential rotation, audit identity, rate limiting, CSRF protection for shared-browser threat models, or public-production access control.

