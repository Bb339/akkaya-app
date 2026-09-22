# Scientific robustness and sensitivity experimental protocol

Status: **PREREGISTERED — no result-bearing experiment has been executed**

## Frozen baseline and population

- Baseline tag: `refs/tags/v2-scientific-prepilot-freeze`
- Baseline commit: `ac02f4dc9e984438696f7da31b8d2a5841711c9e`
- Scientific-source commit: `bb0c6ff516a7d995c2894ee66285ebf124ac9340`
- Population label: `FULL_REFERENCE_PROJECT_EXPERIMENT`
- Population: 179 analysis units, 134,919 da
- Planning year: 2024
- Current-pattern calculated gross irrigation demand: 100,700,080.81 m3
- Current-pattern catalog-derived profit: 1,041,499,119.212 TL
- Engine annual scenario budget at multiplier 1.0: 10,401,986.556 m3
- Protected-perennial current-model demand floor: 22,510,545.8328 m3
- Critical annual-budget multiplier: 2.164062192506452

The 3-unit and 24-unit fixtures are test populations and are excluded from scientific results.

## Research questions

1. At which annual-budget multiplier does annual water feasibility change under the frozen model?
2. How stable are crop shares, total water, total profit and concentration across algorithms and random seeds?
3. How sensitive is the frozen engine to uncertainty in its connected direct net-profit input?
4. Which conclusions remain descriptive model-output statements, and which claims are unsupported by the frozen evidence?

## Data-flow audit and factor eligibility

`kds.application.optimization.configuration` creates the accepted configuration; `kds.adapters.project_science.build_bundle` creates immutable scientific inputs; `kds.science.execution.execute` supplies them to the unchanged frozen optimizer through `ProjectDataProvider`; `kds.science.results.project_result` is the final S2 result authority.

The water multiplier is connected to the engine annual budget and is executable. S1 consumes `candidate_options.profit_tl_da` directly. S2 consumes seasonal direct profit values from the frozen environment resources. Net profit per da is therefore the primary executable economic factor. Price and yield columns are not independent decision inputs on this frozen execution path; they will be reported as `PRICE_SENSITIVITY_NOT_EXECUTABLE_ON_FROZEN_ENGINE` and `YIELD_SENSITIVITY_NOT_EXECUTABLE_ON_FROZEN_ENGINE`. No synthetic price-to-profit or yield-to-profit formula will be invented.

## Fixed scenario families

### A. Annual water-budget threshold

Use objective `water_saving`, algorithm `GA`, and the first selected seed for both S1 and S2. Execute the normalized, sorted multipliers:

`1.0, 1.5, 2.0, 2.055859082881130, 2.164062192506452, 2.272265302131775, 2.5, 3.0`

The three non-round values are 0.95, 1.00 and 1.05 times the protected-perennial critical multiplier. Duplicate scenario identities are forbidden. Report engine feasibility, annual-budget feasibility and monthly-delivery status separately. A change in annual-budget feasibility is a structural model threshold, not a statement about real-world water availability.

### B. Algorithm and seed robustness

At multiplier 1.0, objective `water_saving`, execute GA, ACO and ABC for S1 and S2 over the selected seed set. The pilot decision rule below selects five or ten seeds. The algorithms are compared on identical scenario, objective, population and seed identities.

### C. Economic sensitivity

Use the connected direct net-profit factor at shocks `-20%, -10%, 0%, +10%, +20%`, objective `max_profit`, algorithm `GA`, and the first selected seed, for S1 and S2. Scale every direct candidate/seasonal profit value used by the frozen execution path by the same factor while leaving water, areas, suitability and constraints unchanged. If a scenario's objective is provably scale-invariant, record the analytical invariance and avoid redundant optimizer calls; otherwise execute it. Any executed overlay is stored in a new immutable bundle and never written into source data.

### D. Combined stress

No combined-stress family is preregistered for this milestone. It may be designed only after families A–C are complete and requires a new preregistration. This prevents post-result scenario selection.

## Pilot and seed-count decision

The computational pilot consists of one S1 baseline scenario, objective `water_saving`, seed 101, once for each of GA, ACO and ABC, plus one same-input repeat of GA seed 101 for determinism. Pilot outputs are timing/determinism evidence and are excluded from scientific summaries.

Candidate seeds are fixed in advance as `101, 211, 307, 401, 503, 601, 701, 809, 907, 1009`. Let `T` be the median elapsed seconds of the three algorithm pilot runs. Use ten seeds when the projected algorithm/seed core (`3 algorithms × 2 scenarios × 10 seeds × T`) is at most 3,600 seconds; otherwise use the first five seeds. The selected count and pilot evidence must be committed to this protocol before result-bearing runs.

Accepted algorithm controls are fixed:

- GA: population 12, generations 10, crossover 0.70, mutation 0.08
- ACO: ants 10, iterations 10, evaporation 0.25, q 1.0
- ABC: food sources 10, cycles 10, limit 4

Every run receives a fresh process. Failed and timed-out runs remain in the manifest and are never silently replaced.

## Metrics and stability formulas

For every executed scientific run record scenario family and identifier, S1/S2, objective, algorithm, seed, feasibility, annual-budget feasibility, monthly-delivery status, total water, total profit, TL/m3, HHI, top-1 and top-3 shares/identities, crop counts/shares, runtime, run ID, scenario hash and input-overlay hash.

For crop share vectors `p` and `q` over the union of crop identities:

- L1 distance: `sum(|p_i-q_i|)`
- Bray–Curtis dissimilarity: `sum(|a_i-b_i|) / sum(a_i+b_i)` using crop areas
- Weighted Jaccard similarity: `sum(min(a_i,b_i)) / sum(max(a_i,b_i))`
- HHI: `sum(p_i^2)`
- Top identity agreement: exact top-1 crop equality
- Top-3 agreement: Jaccard similarity of the top-three crop sets

Seed variability is summarized per scenario/algorithm with mean, standard deviation, coefficient of variation, minimum and maximum for water, profit, TL/m3 and HHI. Algorithm agreement compares matched seeds pairwise. All denominators and zero cases are handled explicitly.

## Raw evidence, identity and immutability

Each raw output is stored once at `docs/experiments/robustness_sensitivity/raw_runs/<run_id>.json`. `run_id` is a deterministic digest of scenario identity, algorithm, seed and overlay identity. Existing raw files may be verified but never overwritten. Each file contains a UTC execution timestamp and elapsed runtime; reproducibility comparisons exclude only timestamp/runtime metadata.

`scenario_hash` hashes the normalized scenario definition. `input_overlay_hash` hashes the canonical overlay definition. The scenario-grid hash, dataset/resource hashes, candidate hash, software versions, exclusions and failures are recorded in `experiment_manifest.json`.

## Exclusions and publication boundary

- Protected source/runtime files are read-only for this milestone.
- No new scientific constants, datasets, objective functions or optimizer behavior may be introduced.
- The only primary optimization objectives are `water_saving` for water/robustness and `max_profit` for the economic family. `water_efficiency` is excluded to limit the planned experiment family and prevent a post-hoc objective search.
- Price and yield sensitivity are non-executable unless the audit discovers a direct frozen-engine dependency before result execution; such a discovery requires a protocol amendment committed before results.
- Results describe the frozen model and frozen reference inputs. They do not establish official allocation, measured use, reservoir availability, real farm profitability, market capacity or policy recommendations.
- No robustness-completion tag will be created in this task.

## Planned outputs

The result package is rooted at `docs/experiments/robustness_sensitivity/` and includes the protocol copy, manifest, scenario grid, run-level results, scenario summaries, algorithm agreement, seed variability, crop-share stability, water-threshold analysis, economic sensitivity, claim boundary, publication tables, publication figure manifest, source guard, test report and immutable raw-run files. Minor inherited freeze follow-ups are documented separately and do not change scientific behavior.
