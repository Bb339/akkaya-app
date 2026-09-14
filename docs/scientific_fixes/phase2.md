# Scientific Fix Phase 2

Date: 2026-09-14  
Scope: BUG-01 monthly delivery capacity contract and S2 monthly feasibility visibility

## A–I: freeze, cause and correction

**A — Phase 1 freeze.** Annotated tag
`v2-scientific-fix-phase1-complete` points exactly to
`8c77cd063ee592680e02bf01d6f83b17aaf030c2` with message
`Scientific Fix Phase 1 complete - observed perennial authority and S2 result contract`.

**B — Phase 2 workspace.** Branch `v2-scientific-fix-phase2`, worktree
`crop-kds-v2-scientific-fix2`, starting from the Phase 1 tag.

**C — BUG-01 before.** `basin_budget_and_delivery_caps` produced date-keyed
`YYYY-MM → m3/month` dictionaries. `compute_monthly_delivery_report`
called `np.array(list(dictionary), dtype=float)`, attempted to convert the
date keys, caught the resulting error and returned `None`.

**D — Root cause.** The defect was a key-representation conversion, not a
physical volume conversion. The FAO score path also attempted
`int("YYYY-MM")` and silently skipped the monthly penalty. The calibrated
proportional score path iterated key/value pairs and therefore already applied
its existing penalty.

**E — Source unit.** CSV notes define
`max_delivery_m3_assumed = 1.15 × irrigation_m3_baseline`. Both fields are
monthly physical volumes. The delivery values are assumptions, not measured
operating capacity.

**F — Engine unit.** Monthly capacity and demand are both `m3/month`.
Annual sums are `m3/year`. FAO monthly irrigation uses the dimensional
identity `1 mm × 1 da = 1 m3`, followed by one multiplication by area in da.

**G — Wrong conversion.** No evidence of a numerical `/1000`, da/ha,
second-area, daily, or `/12` error was found. The wrong operation was treating
dictionary keys as numeric capacity values. Silent exception handling then
removed the report and, in the FAO path, the constraint evaluation.

**H — Canonical contract.** Source rows are normalized once to
`{1..12: m3/month}`. Effective capacity is
`raw m3/month × selected-demand share × (1 - environmental reserve)`.
There is no other unit conversion.

**I — Code fix.** `_canonical_monthly_table_values` is the single period-key
boundary. It validates and normalizes reservoir/delivery tables.
`compute_monthly_delivery_report` consumes mappings or vectors in calendar
order and fails visibly on invalid input. Existing penalties, budgets and
repair behavior are unchanged.

## Unit trace

| variable | source file/table | source column | declared unit | actual numeric semantics | provider representation | engine representation | conversion | comparison unit | aggregation | notes |
|---|---|---|---|---|---|---|---|---|---|---|
| reservoir period | reservoir | `month` | calendar month | year-month label | scalar table cell/DataFrame column | integer month 1–12 | key normalization | n/a | 12 unique months | planning year only |
| reservoir baseline | `akkaya_reservoir_monthly_backend.csv` / reservoir | `irrigation_m3_baseline` | m3/month | monthly irrigation allocation | numeric DataFrame column | positive month map | none; dimensionless share/reserve later | m3/month | sum → m3/year | annual budget authority |
| delivery period | delivery | `month` | calendar month | year-month label | scalar table cell/DataFrame column | integer month 1–12 | key normalization | n/a | 12 unique months | BUG-01 occurred here |
| raw delivery capacity | `delivery_capacity_monthly_assumed.csv` / delivery | `max_delivery_m3_assumed` | m3/month | assumed basin-wide monthly physical capacity | numeric DataFrame column | positive month map | none | m3/month | sum → annual available volume | source note says 1.15× baseline |
| effective delivery capacity | engine boundary | derived | m3/month | selected-project capacity after reserve | n/a | month map | raw × selected share × (1-env) | m3/month | sum retained as diagnostic | no area scaling |
| reservoir month weight | reservoir baseline | derived | dimensionless | month share of annual baseline | n/a | month map | monthly / annual sum | dimensionless | weights sum to 1 | calibrated demand profile |
| calibrated monthly demand | final annual water | derived | m3/month | annual plan water distributed by reservoir profile | n/a | 12-value vector | annual m3 × dimensionless weight | m3/month | sum equals final annual water | existing approximation |
| FAO monthly intensity | monthly climate, crop calendar, Kc | derived | mm = m3/da | irrigation depth per crop/unit/month | matrices | `MU[P,C,12]` | rainfall/Kc model, then area once | m3/month after area | sum months → crop m3 | no da/ha factor |
| requested/applied demand | score/final report | derived | m3/month | plan request; capacity does not clip the plan | n/a | demand vector | none | m3/month | sum → final annual water | violation penalizes/marks infeasible |
| monthly comparison | engine | derived | m3/month | demand minus effective capacity | n/a | exceed vector | `max(0,demand-capacity)` | m3/month | violating-month count/max | existing constraint |
| water quality period | `water_quality_monthly_assumed.csv` / water_quality | `month` | calendar month | EC observation/assumption period | numeric table | monthly lookup | key/date matching | n/a | season average where dates exist | not a volume |
| water quality EC | water_quality | `ec_dS_m_assumed` | dS/m | electrical conductivity | numeric DataFrame column | float lookup | no volume conversion | dS/m | season average | thresholds unchanged |

## J–N: validation and evidence

**J — Monthly validation.** Readiness rejects missing/duplicate months,
non-numeric, non-finite, zero/negative capacity, conflicting unit and
non-calendar period. Legacy omitted metadata is interpreted through the
documented column contract without store mutation.

**K — BEFORE Akkaya.** S2/GA/seed 123: engine report `null`; independently
recomputed 12/12 months violated. Raw delivery sum 13,291,427.0 m3, effective
sum 11,962,284.3 m3, demand 23,933,291.2028 m3.

**L — AFTER Akkaya.** The engine emits `status=violation`,
`unit=m3/month`, 12 violating months and a maximum June violation of
2,077,209.3528 m3.

**M — Feasibility change.** None: `false → false`. Annual water
23,933,291.2028 m3, profit 188,154,778.3904635 TL and annual budget
10,401,986.556 m3 are unchanged.

**N — Raw/final plan status.** Raw hash
`5d0369a4260e4891871116b859381ea589cf3977af474da8c0fa32aafb79ec90`
and final hash
`12e4192e49023f980863d5e1f52929eaa5661585f78855ff5fc48aa4bb23e824`
are unchanged. The Phase 1 result contract remains authoritative.

## O–Z: regression and boundaries

**O — S1 regression.** GA, ACO and ABC frozen outputs passed exact parity.

**P/Q/R — Synthetic S2.** GA, ACO and ABC each passed once on the 24-unit
public-import fixture. All emitted a real 12-month report using the same unit
contract. Their raw/final plan hashes and final totals remained unchanged from
Phase 1.

**S — Perennial regression.** Six synthetic orchards and the 52-unit Akkaya
perennial set remain protected; unexpected synthetic field locks remain zero.

**T — Engine functions changed.** Only
`_canonical_monthly_table_values`, `_basin_month_profile`,
`basin_budget_and_delivery_caps`, `compute_monthly_delivery_report` and
the shared post-processor `_build_two_crop_recommendations` differ from
Phase 1. The last change preserves the frozen S1 report schema.

**U — Tests.** Monthly unit tests: 19 passed. Scientific source/perennial/result
suite: 39 passed. Frozen S1/S2 engine suite: 8 passed. Synthetic S2 algorithms:
3 passed. FAST: 152 passed, 27 deselected in 203.26 seconds.

**V — Files created.** Minimal unit fixture, Akkaya BEFORE/AFTER fixture,
Phase 2 source guard, monthly contract tests and this report. Full machine
snapshots are retained under external `outputs/scientific-fix-phase2`.

**W — V1 modified?** No. V1 remains at
`a49daac1ae6d15d83428565c388bfafb4b6da08a`; its existing untracked output
directories remain untouched.

**X — Main V2 / audit / Phase 1 modified?** No. They remain at
`3d12895a80bc6c964b72e81d65577dd502a5402c`,
`919842568f5461f03fb3a3f73295016b1e2eb51f`, and
`8c77cd063ee592680e02bf01d6f83b17aaf030c2`.

**Y — Production / remote?** No deployment, production write or remote push.

**Z — Next scientific phase.** Reconcile assumed reservoir/delivery supply
with verified operating data and the protected perennial demand floor. That
data-quality task is outside Phase 2.
