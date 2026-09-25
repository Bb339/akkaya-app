# Execution State Contract

- Implementation commit: `f26020c9aabdefd2c0a200ec2e8ca05bcee6c8cd`
- Previous evidence HEAD: `6ee38399c55ea242919e7f3586810435b604f746`
- Previous evidence packaging commit: `6ee38399c55ea242919e7f3586810435b604f746`
- Rejected parent: `0eab17ef37a2fdb7e5806be35ebf38d88971023c`
- Phase 1 baseline: `04a4bce0db31db41813cfcfd253d9c6794f252bc`
- Robustness baseline: `028f231eb774eafb53a9a76db370b663d561ce1b`

Readiness and run lifecycle are separate. Readiness may write `READY/BLOCKED` only when no stronger active or terminal lifecycle state exists. `PREVIEWING`, `RUNNING`, `COMPLETED`, `COMPLETED WITH WARNINGS`, `FAILED` and `STALE PREVIEW` survive refresh/finally processing. A successful new preview resets stale state; a pinned preview invalidated by configuration or data change becomes `STALE PREVIEW`.
