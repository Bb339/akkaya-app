# Remaining risks before launch completion

- Render account authentication and service creation are outstanding.
- Basic Auth secret values must be entered directly in Render and must not be copied into Git or evidence.
- The persistent disk must be attached at `/var/data/crop-kds` before launch.
- The real Render proxy-duration, memory, worker restart, and service restart behavior remain untested.
- One worker serializes long analysis requests.
- Multi-instance/horizontal scale, database, distributed queue, repository-managed backup, production IAM, and original upload-byte archival remain unsupported.
- Public production readiness is not claimed.

