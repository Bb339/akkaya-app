# Unit Presentation Contract

- Implementation commit: `f26020c9aabdefd2c0a200ec2e8ca05bcee6c8cd`
- Previous evidence HEAD: `6ee38399c55ea242919e7f3586810435b604f746`
- Previous evidence packaging commit: `6ee38399c55ea242919e7f3586810435b604f746`
- Rejected parent: `0eab17ef37a2fdb7e5806be35ebf38d88971023c`
- Phase 1 baseline: `04a4bce0db31db41813cfcfd253d9c6794f252bc`
- Robustness baseline: `028f231eb774eafb53a9a76db370b663d561ce1b`

`kds.application.result_presentation` creates a disposable API presentation view. It never mutates stored/scientific results.

| Field family | Authority |
|---|---|
| Verified unit water and selected crops | `run.result.unit_results` |
| Optimizer plan and unit profit | `run.result.details` |
| Current crop, coordinates and geometry | `project.analysis_units` |

The merge uses canonical unit IDs, is order-independent, sorts output deterministically and rejects duplicate conflicting identities. Project metadata only enriches units already present in the scientific/optimizer result. Missing optional presentation values are listed in `missing_presentation_metadata`; no coordinate, crop, profit, status or warning is fabricated.
