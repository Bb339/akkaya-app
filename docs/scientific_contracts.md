# V2 scientific data and result contracts

This document defines the authority boundaries used by the V2 project workflow.
The contract version introduced in Scientific Fix Phase 1 is
`scientific-result-v2`.

## Input roles

| Term | Authoritative source | Meaning | Permitted use |
|---|---|---|---|
| Observed/current crop | `AnalysisUnit.current_crop`, mapped to the engine unit record by `ProjectDataProvider` | Crop observed as already present on the analysis unit | Baseline context and perennial/orchard protection |
| Candidate crop | Project `scientific_inputs.candidates` | An approved decision alternative for an analysis unit | Construction of optimizer choices |
| Seasonal alternative | Project `scientific_inputs.seasonal_resources.s2` | A crop/season combination that may be evaluated | Water, profit, season and rotation inputs for S2 |
| Perennial lock | Canonicalized observed/current crop membership in `PERENNIAL_CROPS` | Protection of an established perennial crop | Locks only the observed perennial crop |

A candidate or seasonal-alternative row is never evidence that a crop is
currently planted. `parcel_type` is descriptive metadata; an observed
perennial remains protected even if that label says `field`. If the observed
crop is perennial but the canonical crop is absent from the scientific
candidate matrix, execution fails clearly instead of silently removing the
protection.

## S2 result roles

The scientific engine keeps its existing internal output. The V2 application
service projects that output into two explicit stages:

| Field | Authority and purpose |
|---|---|
| `raw_optimizer_plan` | Immutable copy of the optimizer's S2 choice rows, raw water/profit aggregation, selected unit identifiers and effective run parameters. Its `feasibility_status` is `not_validated`; the final engine feasibility flag is not relabeled as a raw-plan verdict. |
| `validated_final_plan` | The engine's existing post-guard parcel recommendations, projected into one primary and an optional non-fallow secondary crop per unit. It includes final metrics and bounded validation metadata. |
| `final_metrics` | Metrics recomputed from the same final rows: water, profit, TL/m³, physical active/fallow area and seasonal crop distribution. |
| Top-level `details`, water, profit, TL/m³ and `feasible` | Compatibility view of the validated final plan. These are the defaults consumed by the API summary and V2 UI. |
| `parcels` | Existing detailed post-guard engine recommendations, retained for compatibility and traceability. |

Physical active area counts each analysis unit at most once. Crop distribution
is seasonal cropped area, so land with two crops can contribute twice. A
fallow secondary season is represented by `secondary: null`; it is not shown
as a planted crop.

## Validation scope

`validated_final_plan` means that the result has passed through the engine's
existing post-optimizer guards and has been projected from one authoritative
final row set. It does not claim independent scientific validation of every
constraint.

The contract reports:

- the existing engine `feasible` flag;
- whether final annual water is within the reported annual budget;
- whether the engine supplied a monthly delivery report;
- whether the engine's reported final totals match the recomputed final rows.

When no delivery report is supplied, monthly feasibility is explicitly marked
as not evaluated. This phase does not alter the known monthly dictionary
capacity conversion issue (BUG-01).

## Compatibility and history

S1 results pass through as independent copies without schema or value changes.
The internal engine transport in `kds.science.execution.execute` remains
unchanged. New S2 application runs persist `scientific-result-v2`. Older
stored S2 runs are projected on a deep copy during GET, history and overview
reads; the project store is not migrated or mutated by a read.

The legacy `/#panel` assets are outside this contract. The V2 `/projects`
screen renders `validated_final_plan` when present and uses per-season area
from that plan.
