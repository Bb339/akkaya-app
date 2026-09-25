# Execution State Contract

- Corrective final HEAD / evidence commit: `refs/heads/v2-institutional-demo-ministry-ui-phase2-fix1`
- Rejected parent: `0eab17ef37a2fdb7e5806be35ebf38d88971023c`
- Phase 1 baseline: `04a4bce0db31db41813cfcfd253d9c6794f252bc`
- Robustness baseline: `028f231eb774eafb53a9a76db370b663d561ce1b`
- Implementation commit: `f26020c9aabdefd2c0a200ec2e8ca05bcee6c8cd`

Readiness and run lifecycle are separate. Readiness may write `READY/BLOCKED` only when no stronger active or terminal lifecycle state exists. `PREVIEWING`, `RUNNING`, `COMPLETED`, `COMPLETED WITH WARNINGS`, `FAILED` and `STALE PREVIEW` survive refresh/finally processing. A successful new preview resets stale state; a pinned preview invalidated by configuration or data change becomes `STALE PREVIEW`.
