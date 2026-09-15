# Economic dependency contract

Derived economics store `dependency_dataset_ids`. The intended chain is:

```text
crop_yield + crop_sale_price + crop_support_payment + crop_cost_components
    -> gross_revenue_per_da
    -> crop_net_profit
    -> future TL/m3 and optimization provenance
```

Gross revenue uses canonical ton/da × TL/ton = TL/da. Support is added only by the explicit support method. Costs are summed from supplied components without filling missing categories. A calculated profit records input dataset IDs, explicit role IDs, formula, method, authority and canonical unit. `GROSS_MINUS_TOTAL_COST` requires exactly one `yield_dataset_id`, `price_dataset_id`, and `cost_dataset_id`; `GROSS_PLUS_SUPPORT_MINUS_TOTAL_COST` additionally requires one `support_dataset_id`. A generic lineage list remains supported only when each role can be resolved uniquely by canonical data type. Wrong-type, missing, extra or ambiguous role dependencies are rejected.

Every required input must be confirmed, active, `CURRENT`, free of a recalculation requirement, verified-authority, same planning year, same crop, same geographic/crop scope, and TRY. Gross revenue must equal referenced yield × referenced price, total cost must equal the referenced component sum, and support must equal the referenced support sum. Missing support is not zero; explicit zero is valid. Analysis-unit and seasonal dependency IDs receive the narrower existence, active/current and compatible-year checks in this phase.

Verified calculated economics require scope-compatible evidence. Every yield, price, cost-component and optional support record in one calculation must resolve to an identical `geographic_scope` and `crop_scope`; no cross-region hierarchy, alias or automatic scope synthesis is applied. Missing, blank and whitespace-only scope values use the existing canonical defaults: `geographic_scope=project` and `crop_scope=catalog`. The calculated output preserves this common scope pair.

When confirmation supersedes an upstream dataset, every active direct or transitive dependent is marked `derivation_status=STALE`, `requires_recalculation=true`, with a reason linking the change to the replacement dataset. The project `economic_data.reanalysis` record identifies the trigger, superseded dataset, stale datasets, affected S1/S2 scenarios, timestamp and retained AnalysisRun IDs.

Staleness does not recalculate, activate a derived replacement, mutate old runs or change optimizer inputs. Recalculation must be an explicit future operation followed by the same preview and confirm workflow. Verified engine adoption belongs to the later scientific integration milestone.

Seasonal replacement preview reads canonical `net_profit_tl_da` and uses the `canonical_units.net_profit` value, `TL/da`.

Future S2 result rows must expose raw profit, suitability multiplier, profit-realism multiplier and effective profit. Fallback use must expose the fallback flag and source. This milestone preserves the current nine fallback values and S2 transformations unchanged.
