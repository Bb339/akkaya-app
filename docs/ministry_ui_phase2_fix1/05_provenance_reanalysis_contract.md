# Provenance and Reanalysis Contract

- Implementation commit: `f26020c9aabdefd2c0a200ec2e8ca05bcee6c8cd`
- Previous evidence HEAD: `6ee38399c55ea242919e7f3586810435b604f746`
- Previous evidence packaging commit: `6ee38399c55ea242919e7f3586810435b604f746`
- Rejected parent: `0eab17ef37a2fdb7e5806be35ebf38d88971023c`
- Phase 1 baseline: `04a4bce0db31db41813cfcfd253d9c6794f252bc`
- Robustness baseline: `028f231eb774eafb53a9a76db370b663d561ce1b`

The API supplies `presentation_context` from current project state and the stored input snapshot: `requires_reanalysis`, `pinned_to_older_input_snapshot`, current project revision, run revision, revision relationship and latest run ID. The UI displays these values in the provenance summary and technical JSON. It does not reconstruct revision claims in JavaScript.
