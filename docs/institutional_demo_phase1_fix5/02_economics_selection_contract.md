# Economics readiness contract

The economics domain alone receives the narrow, backward-compatible completeness fields. Other domains retain the Fix4 state contract.

- `dataset_selected`: at least one active economics pointer resolves to a stored resource.
- `selection_complete`: every scenario-required economics type is selected.
- `selected_dataset_types`: sorted selected type names.
- `required_dataset_types`: `crop_net_profit` for S1; `crop_net_profit` and `seasonal_economics` for S2.
- `missing_required_datasets`: sorted required types absent from selection.
- `dataset_valid`: true only after the unchanged strict resolver validates the complete required set.
- `consumer_available`: remains true for the implemented economics consumer.
- `engine_connected`: true only after strict resolution succeeds.

Partial selection is visible and non-executable. A non-empty `datasets` list implies `dataset_selected=true`; `dataset_selected=false` implies an empty list.
