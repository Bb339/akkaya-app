# Canonical Crop Share Contract

- Corrective final HEAD / evidence commit: `refs/heads/v2-institutional-demo-ministry-ui-phase2-fix1`
- Rejected parent: `0eab17ef37a2fdb7e5806be35ebf38d88971023c`
- Phase 1 baseline: `04a4bce0db31db41813cfcfd253d9c6794f252bc`
- Robustness baseline: `028f231eb774eafb53a9a76db370b663d561ce1b`
- Implementation commit: `f26020c9aabdefd2c0a200ec2e8ca05bcee6c8cd`

The complete composition table consumes `result.crop_shares` directly and sorts by descending canonical share, then crop identity. `top_crops` remains an executive summary and supplies area only when the backend included it. HHI is displayed from backend `hhi/HHI`. Missing `crop_shares` produces an explicit not-produced message; the UI never derives shares from `top_crops`.

For infeasible S2, crop rows remain marked `DIAGNOSTIC / ÖNERİ DEĞİL`.
