# Fix5 root cause

Fix4 correctly retained active economics resources in `datasets`, but `_selected_economic_datasets` returned the boolean `required_types <= selected_types` as though it meant `dataset_selected`. For S2, removing only `seasonal_economics` therefore produced a non-empty selected dataset list while reporting `dataset_selected=false`.

Fix5 explicitly acknowledges this Fix4 defect. It derives `dataset_selected` from whether any active economics pointer resolves to a resource, and derives `selection_complete` independently from the scenario-required type set. Strict resolution and execution remain unchanged.
