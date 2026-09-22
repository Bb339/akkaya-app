# Publication tables

Classifications apply per scenario segment; infeasible S2 plan metrics are never presented as feasible recommendation evidence.

## Table 1. Experimental design

Classification: **SAFE WITH LIMITATION**.

| Population | Scenarios | Algorithms | Seeds | Active scientific runs |
|---|---|---|---|---:|
| 179 units / 134,919 da | S1, S2 | GA, ACO, ABC | 101, 211, 307, 401, 503 | 54 |

## Table 2. Water-budget sensitivity

| Scenario | First tested annual-feasible multiplier | Overall feasible at that row | Annual-threshold evidence | Plan-output classification |
|---|---:|---|---|---|
| S1 | 1.0 | True | SAFE WITH LIMITATION | SAFE WITH LIMITATION |
| S2 | 2.5 | False | SAFE WITH LIMITATION | DIAGNOSTIC ONLY |

S2 first becomes annually feasible at the tested 2.5 multiplier, while monthly delivery still violates constraints and overall feasibility remains false.

## Table 3. Algorithm agreement

| Scenario | Mean weighted Jaccard | Top-1 agreement rate | Feasibility agreement rate | Classification |
|---|---:|---:|---:|---|
| S1 | 0.865201 | 1.000000 | 1.000000 | SAFE WITH LIMITATION |
| S2 | 0.247579 | 0.333333 | 1.000000 | DIAGNOSTIC ONLY |

## Table 4. Seed variability

| Scenario | Algorithm | Water CV | Profit CV | HHI CV | Classification |
|---|---|---:|---:|---:|---|
| S1 | ABC | 0.00164492 | 0.00174515 | 0.0231027 | SAFE WITH LIMITATION |
| S1 | ACO | 0 | 0 | 0 | SAFE WITH LIMITATION |
| S1 | GA | 0.00837819 | 0.0106084 | 0.0968241 | SAFE WITH LIMITATION |
| S2 | ABC | 0.0742885 | 0.0988571 | 0.089799 | DIAGNOSTIC ONLY |
| S2 | ACO | 0.0217705 | 0.0357461 | 0.0813244 | DIAGNOSTIC ONLY |
| S2 | GA | 0.00381203 | 0.00243575 | 0.00782539 | DIAGNOSTIC ONLY |

## Table 5. Economic input-shock response

The economic family perturbs connected direct net-profit inputs while preserving the frozen engine unchanged. Output response is observed, not forced to be linear.

| Scenario | Profit at -20% | Profit at baseline | Profit at +20% | Composition response | Classification |
|---|---:|---:|---:|---|---|
| S1 | 1226517731.380 | 1533147164.226 | 1839776597.071 | UNIFORM_INPUT_SHOCK_COMPOSITION_INVARIANT_OBSERVED | SAFE WITH LIMITATION |
| S2 | 176330807.801 | 220400129.901 | 264467572.138 | UNIFORM_INPUT_SHOCK_COMPOSITION_INVARIANT_OBSERVED | DIAGNOSTIC ONLY |

S2 economic values show only the uniform profit-scale response of infeasible S2 search outputs.

## Table 6. Crop-pattern stability

| Scenario | Mean algorithm weighted Jaccard | Mean algorithm Bray-Curtis | Mean top-3 Jaccard | Classification |
|---|---:|---:|---:|---|
| S1 | 0.865201 | 0.075188 | 1.000000 | SAFE WITH LIMITATION |
| S2 | 0.247579 | 0.605066 | 0.300000 | DIAGNOSTIC ONLY |

See the CSV files for complete precision and every run. Values are frozen-model outputs within the claim boundary.
