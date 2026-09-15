# Economic dependency contract

Derived economics store `dependency_dataset_ids`. The intended chain is:

```text
crop_yield + crop_sale_price + crop_support_payment + crop_cost_components
    -> gross_revenue_per_da
    -> crop_net_profit
    -> future TL/m3 and optimization provenance
```

Gross revenue uses canonical ton/da × TL/ton = TL/da. Support is added only by the explicit support method. Costs are summed from supplied components without filling missing categories. A calculated profit records input dataset IDs, formula, method, authority and canonical unit.

When confirmation supersedes an upstream dataset, every active direct or transitive dependent is marked `derivation_status=STALE`, `requires_recalculation=true`, with a reason linking the change to the replacement dataset. The project `economic_data.reanalysis` record identifies the trigger, superseded dataset, stale datasets, affected S1/S2 scenarios, timestamp and retained AnalysisRun IDs.

Staleness does not recalculate, activate a derived replacement, mutate old runs or change optimizer inputs. Recalculation must be an explicit future operation followed by the same preview and confirm workflow. Verified engine adoption belongs to the later scientific integration milestone.

Future S2 result rows must expose raw profit, suitability multiplier, profit-realism multiplier and effective profit. Fallback use must expose the fallback flag and source. This milestone preserves the current nine fallback values and S2 transformations unchanged.
