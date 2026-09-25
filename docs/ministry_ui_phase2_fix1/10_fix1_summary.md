# Ministry UI Phase 2 Fix1 Summary

- Implementation commit: `f26020c9aabdefd2c0a200ec2e8ca05bcee6c8cd`
- Previous evidence HEAD: `6ee38399c55ea242919e7f3586810435b604f746`
- Previous evidence packaging commit: `6ee38399c55ea242919e7f3586810435b604f746`
- Rejected parent: `0eab17ef37a2fdb7e5806be35ebf38d88971023c`
- Phase 1 baseline: `04a4bce0db31db41813cfcfd253d9c6794f252bc`
- Robustness baseline: `028f231eb774eafb53a9a76db370b663d561ce1b`

Fix1 adds an ID-based presentation-only unit view, functional Verified marker/list synchronization, truthful missing-geometry behavior, durable lifecycle states, full canonical crop-share display and backend-supplied reanalysis provenance. Reference, synthetic, S2 diagnostic, monthly/cross-year water, readiness, preview/version, template/import and legacy water-authority contracts remain covered.

Targeted validation: `137 passed, 1 deselected in 869.48s`.

Fresh broad validation on the implementation commit: `436 passed, 1 failed, 7 deselected in 2519.79s`. The sole failure was independently reproduced on rejected parent and corrective code with the same assertion and observed value and is classified `INHERITED_UNCHANGED`.

Fresh broad validation on the previous evidence HEAD / evidence packaging commit: `436 passed, 1 failed, 7 deselected in 2706.47s`. The same sole failure remained `tests/test_decision_pipeline.py::test_s2_high_budget_can_return_feasible_two_crop_plan`, with expected `ok` and observed `no_feasible_two_crop_plan`; its classification remains `INHERITED_UNCHANGED`.

The later provenance-normalization commit changes only this evidence directory. It is not represented as either broad suite's tested commit.

The corrective phase does not self-ACCEPT. No tag, push or deployment is included.
