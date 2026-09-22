# Publication tables

All tables are frozen-model evidence classified **SAFE WITH LIMITATION**.

## Table 1. Experimental design

| Population | Scenarios | Algorithms | Seeds | Scientific runs |
|---|---|---|---|---:|
| 179 units / 134,919 da | S1, S2 | GA, ACO, ABC | 101, 211, 307, 401, 503 | 54 |

## Table 2. Water-budget sensitivity

| Scenario | First tested annual-feasible multiplier | Engine feasibility at that row |
|---|---:|---|
| S1 | 1.0 | True |
| S2 | 2.5 | False |

## Table 3. Algorithm agreement

| Scenario | Mean weighted Jaccard | Top-1 agreement rate | Feasibility agreement rate |
|---|---:|---:|---:|
| S1 | 0.865201 | 1.000000 | 1.000000 |
| S2 | 0.247579 | 0.333333 | 1.000000 |

## Table 4. Seed variability

| Scenario | Algorithm | Water CV | Profit CV | HHI CV |
|---|---|---:|---:|---:|
| S1 | ABC | 0.00164492 | 0.00174515 | 0.0231027 |
| S1 | ACO | 0 | 0 | 0 |
| S1 | GA | 0.00837819 | 0.0106084 | 0.0968241 |
| S2 | ABC | 0.0742885 | 0.0988571 | 0.089799 |
| S2 | ACO | 0.0217705 | 0.0357461 | 0.0813244 |
| S2 | GA | 0.00381203 | 0.00243575 | 0.00782539 |

## Table 5. Economic robustness

| Scenario | Profit at -20% | Profit at baseline | Profit at +20% | Composition response |
|---|---:|---:|---:|---|
| S1 | 1226517731.380 | 1533147164.226 | 1839776597.071 | UNIFORM_SHOCK_INVARIANT_OBSERVED |
| S2 | 179059328.541 | 220400129.901 | 261739051.398 | UNIFORM_SHOCK_INVARIANT_OBSERVED |

## Table 6. Crop-pattern stability

| Scenario | Mean algorithm weighted Jaccard | Mean algorithm Bray-Curtis | Mean top-3 Jaccard |
|---|---:|---:|---:|
| S1 | 0.865201 | 0.075188 | 1.000000 |
| S2 | 0.247579 | 0.605066 | 0.300000 |

See the CSV files for complete precision and every run. Values are frozen-model outputs within the claim boundary.
