# Fix4 summary

Fix4 preserves the active pointer/resource fact before strict readiness validation. Selected stale economics, ambiguous crop parameters, and wrong-scope annual water now remain `dataset_selected=true` while reporting `dataset_valid=false` and `engine_connected=false`. Truly missing annual water, economics, and crop-parameter resources remain `dataset_selected=false`.

Every readiness domain now exposes an explicit validity axis alongside selection, consumer availability, and engine connectivity. Selected dataset metadata remains visible on validation failures. Physical environmental release keeps the accepted selected/valid/not-executable state.

Strict execution resolvers are unchanged, so selected invalid institutional data still fails closed. Fix3 cross-year water accounting, climate readiness, scenario-specific requirements, preview pinning, reference outputs, scientific formulas, optimizer implementations, and accepted robustness evidence are unchanged.

Targeted validation recorded 59 passing tests across the Fix4, Fix3 non-regression, Phase 1, and final climate/water groups. The broad suite recorded 402 passed, 1 failed, 7 deselected, and 0 skipped in 2130.35 seconds. The sole S2 high-budget failure reproduced with the identical assertion and result on Fix3 and Fix4 and is classified `INHERITED_UNCHANGED`.

This corrective result is prepared for independent revalidation. No completion tag, push, deployment, Ministry UI Phase 2 work, or manuscript work is included.
