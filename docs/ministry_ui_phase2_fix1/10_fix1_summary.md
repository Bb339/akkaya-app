# Ministry UI Phase 2 Fix1 Summary

- Corrective final HEAD / evidence commit: `refs/heads/v2-institutional-demo-ministry-ui-phase2-fix1`
- Rejected parent: `0eab17ef37a2fdb7e5806be35ebf38d88971023c`
- Phase 1 baseline: `04a4bce0db31db41813cfcfd253d9c6794f252bc`
- Robustness baseline: `028f231eb774eafb53a9a76db370b663d561ce1b`
- Implementation commit: `f26020c9aabdefd2c0a200ec2e8ca05bcee6c8cd`

Fix1 adds an ID-based presentation-only unit view, functional Verified marker/list synchronization, truthful missing-geometry behavior, durable lifecycle states, full canonical crop-share display and backend-supplied reanalysis provenance. Reference, synthetic, S2 diagnostic, monthly/cross-year water, readiness, preview/version, template/import and legacy water-authority contracts remain covered.

Targeted validation: `137 passed, 1 deselected in 869.48s`.

Fresh broad validation on the implementation commit: `436 passed, 1 failed, 7 deselected in 2519.79s`. The sole failure was independently reproduced on rejected parent and corrective code with the same assertion and observed value and is classified `INHERITED_UNCHANGED`.

The corrective phase does not self-ACCEPT. No tag, push or deployment is included.
