# Scientific Fix Phase 1

Date: 2026-09-14  
Scope: BUG-02 and the directly related raw-versus-final V2 result contract

## A–F: baseline, branch and correction

**A — Source baseline.** The fix branch starts at V2 generalization baseline
`3d12895a80bc6c964b72e81d65577dd502a5402c`. The completed audit remains
frozen at `919842568f5461f03fb3a3f73295016b1e2eb51f` with annotated tag
`v2-scientific-audit-complete`. The original engine SHA-256 was
`acd242a0618b95fee1d5d8ff639e646f4940ff5669af029d6596b0ff3cca3bfa`.

**B — Fix workspace.** Work was isolated on branch
`v2-scientific-fix-phase1` in
`crop-kds-v2-scientific-fix1`. V1, the V2 baseline worktree and the audit
worktree were not edited.

**C — Working commits.**

- `3622163` — reproduce candidate-derived perennial locking;
- `975ea9c` — derive perennial locks from observed crops;
- `6f06741` — separate raw and validated S2 results;
- `dda3921` — exercise the contract with GA, ACO and ABC;
- `bd5984a` — add the single full Akkaya phase gate.

**D — BUG-02 before.** With an observed annual `BUGDAY` unit and equal-area
`ARPA`/`ARMUT` seasonal alternatives, the old helper selected `ARMUT`
from the alternative table and returned lock index 2. The frozen minimal
evidence is `tests/fixtures/scientific_fix_phase1/before_minimal.json`.

**E — Root cause.** `_compute_perennial_locks` grouped S2 alternatives by
unit and crop, selected a dominant alternative and treated a perennial
alternative as an observed current crop. Equal-area ties could be resolved by
row ordering, making a candidate pear row a false orchard lock.

**F — Correction.** The helper now reads only the unit's
`current_crop`/`crop`, canonicalizes it and locks it only when it belongs to
`PERENNIAL_CROPS`. It performs no candidate, season or environment read. A
missing candidate for an observed perennial raises a clear error. The current
engine SHA-256 is
`81471ebdf44f8757d9857b94c4ca9736a1f66ccce3bf19034c6d64ba0633515b`.

## G–J: source authority and lock acceptance

**G — Observed source.** `AnalysisUnit.current_crop` is the V2 authority. The
generic adapter already carried this value into provider-backed engine units;
no adapter fallback or regional reference read was added.

**H — Candidate source.** Candidate and S2 seasonal records remain decision
alternatives. They still supply optimizer choices and scientific values, but
cannot assert an existing orchard.

**I — Synthetic result.** The public import fixture has 24 units: 18 fields and
6 real orchards. After the fix there are exactly 6 locks, all six are the
observed orchards, and unexpected field locks equal zero. The post-fix minimal
evidence is `tests/fixtures/scientific_fix_phase1/after_minimal.json`.

**J — Akkaya regression.** The observed perennial lock set remains exactly the
52 unit identifiers recorded by the completed audit. The frozen identifier set
is `tests/fixtures/scientific_fix_phase1/akkaya_locks.json`.

## K–P: result and presentation contract

**K — Raw plan.** `raw_optimizer_plan` retains optimizer choices, its own
aggregated water/profit values, selection metadata and effective parameters.
Raw feasibility is deliberately `not_validated`.

**L — Final plan.** `validated_final_plan` is built from the existing
post-guard `parcels[].result.recommended` rows. No optimizer formula is
duplicated. A protected orchard has its observed perennial as primary and no
fabricated planted secondary.

**M — Raw/final evidence.** Seed 2468 public-fixture runs produced distinct raw
and final hashes for all three algorithms. GA changed from 67,440.4 to 62,674.0
m³; ACO from 62,001.4 to 57,559.0 m³; ABC from 78,338.2 to 75,559.0 m³. The
corresponding evidence files are under the external
`outputs/scientific-fix-phase1` test-artifact directory.

**N — Metric consistency.** Top-level water, profit and TL/m³ are recomputed
from the same final rows and equal `final_metrics`. Summary/history values
come from those defaults. The contract also reports whether prior
engine-reported totals agree.

**O — API and history.** New S2 application runs persist
`scientific-result-v2`. Old completed S2 records are projected on a deep copy
during GET/history; a read does not rewrite the store. Failed runs remain
unchanged.

**P — UI.** Only the V2 `/projects` analysis renderer changed. It selects the
validated final plan and displays per-season area. Legacy `/#panel` assets
were not modified.

## Q–Z: unchanged science and verification

**Q — Algorithms.** GA, ACO and ABC bodies and their fitness functions are
unchanged. The only `app.py` function changed against `3d12895` is
`_compute_perennial_locks`.

**R — S1.** Dated S1 reference cases for GA, ACO and ABC passed with all
deterministic fields unchanged: 3 passed.

**S — S2.** Public 24-unit S2 application runs passed once for each algorithm:
3 passed. The single permitted full Akkaya S2/GA/seed 123 run passed with 179
units, 52 protected orchards, 23,933,291.2028 m³ water,
188,154,778.3904635 TL profit and `feasible=false`.

**T — BUG-01.** Monthly dictionary capacity conversion was not changed. The
full Akkaya annual budget remains 10,401,986.556 m³ and the S2 plan remains
infeasible. Monthly delivery is not claimed when no report is present.

**U — Turp and other rules.** Turp, expansion, diversity, rotation
coefficients, crop parameters, environmental reserve, S2 objective and budgets
are unchanged.

**V — Targeted tests.** The combined contract, workflow, perennial and source
suite passed 48 tests. The three-algorithm synthetic acceptance passed 3 tests;
the full Akkaya gate passed 1 test.

**W — FAST.** The required FAST command passed: 131 passed, 27 deselected in
218.89 seconds. Baseline before implementation was 114 passed, 23 deselected.

**X — Frozen worktrees.** Final verification kept V1 at
`a49daac1ae6d15d83428565c388bfafb4b6da08a`, main V2 at
`3d12895a80bc6c964b72e81d65577dd502a5402c`, and the audit at
`919842568f5461f03fb3a3f73295016b1e2eb51f`. V1's pre-existing untracked
`audit_outputs/` and `outputs/` directories were left untouched.

**Y — External actions.** No production data, remote, deployment or push was
performed.

**Z — Recommended next phase.** Address BUG-01 as a separate milestone with an
explicit monthly-capacity unit contract and new validation evidence. It is not
implemented in this phase.
