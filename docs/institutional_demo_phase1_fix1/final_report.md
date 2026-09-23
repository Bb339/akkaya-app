# V2 Institutional Demo Integration Phase 1 — Corrective Phase 1

## A. BASELINE
Rejected baseline is `d0d79482be47a6554ad7878ac9bba237c40bc414`; robustness parent is `028f231eb774eafb53a9a76db370b663d561ce1b`.

## B. FIX WORKTREE
Worktree `crop-kds-v2-institutional-demo-phase1-fix1`, branch `v2-institutional-demo-integration-phase1-fix1`; the rejected worktree remains unchanged.

## C. COMMITS
The corrective work is split into scientific consumer, integration, result compatibility, audit guard, regression-test, and evidence commits.

## D. ROOT CAUSES
Verified datasets stopped at metadata/materialization, scope was incomplete, execution could reselect after preview, and result/provenance contracts omitted required distinctions.

## E. PROFILE CONTRACT
Institutional API calls require explicit `REFERENCE_DEMO` or `VERIFIED_INSTITUTIONAL`; verified failures never fall back to reference execution.

## F. WATER SCOPE
Selection enforces planning year, geographic scope, active/confirmed status, authority, and staleness; wrong scope fails closed.

## G. ANNUAL WATER
Annual supply drives the verified usable optimizer budget and annual validation.

## H. MONTHLY SUPPLY
Twelve monthly values drive a distinct monthly-supply validation and overall feasibility.

## I. DELIVERY
Monthly delivery capacity drives its own validation; a 1 m3/month perturbation fails feasibility.

## J. ENVIRONMENTAL RELEASE
Ratio release is deducted once from annual/monthly availability. Physical-release form is reported `NOT_EXECUTABLE_WITH_CURRENT_MODE` and fails closed.

## K. CONVEYANCE
Efficiency converts net crop demand to gross demand; 0.83 to 0.45 increases verified water demand.

## L. ECONOMICS
Verified net profit reaches candidate `profit_per_da` and the optimizer objective.

## M. CROP PARAMETERS
Verified Kc/stage records drive the provider-bound FAO56 monthly demand consumer.

## N. PHENOLOGY
Year-specific and climatological dates drive temporal water distribution; previous-autumn/planning-year-harvest semantics are preserved.

## O. PERENNIAL
Exact analysis-unit requirement takes precedence over crop default; duplicate equal-specificity records fail closed.

## P. VERIFIED S1 E2E
Create through provenance passed with synthetic, project-scoped imports and a pinned preview.

## Q. VERIFIED S2 E2E
Primary/secondary phenology, seasonal economics, perennial overrides, monthly constraints, result, and provenance passed end to end.

## R. READINESS TRUTH TABLE
Every domain reports status, connection state, execution scope, consumer, dataset/version, warnings, and blockers. Unsupported physical release is not marked connected.

## S. PREVIEW REVISION
Preview emits token, project revision, and selection hash; stale or changed selection is rejected as `STALE_PREVIEW / REVISION_CONFLICT`.

## T. VERSION PINNING
Runs retain selected dataset ids/versions and immutable snapshots; replacement marks reanalysis and does not mutate old runs.

## U. RESULT CONTRACT
The stable result includes identity/configuration, totals, HHI/distribution, unit results, annual/monthly/delivery validations, overall feasibility, warnings, and provenance.

## V. PROVENANCE
Current-pattern provenance is separate from candidate provenance and carries batch, hash, revision, filename, unit count, year, and scope.

## W. SYNTHETIC SAFETY
All corrective fixtures are explicitly `SYNTHETIC / NOT_OFFICIAL`; no official or field-validated claim is made.

## X. REFERENCE PARITY
Reference values remain 179 units, 134919 da, 6859 candidates, 58 crops, 100700080.81 m3, and 1041499119.212 TL.

## Y. CONTROLLED EFFECT MATRIX
See `controlled_effect_matrix.md`, `.json`, and `.csv` for nine verified-input A/B effects.

## Z. TESTS
Phase 1: 18 passed. Final broad run: 362 passed, 8 deselected. The extra deselection is the separately reproduced inherited S2 backlog; no new failure remains.

## AA. SOURCE GUARD
`app.py`, `data/`, candidate matrix, existing scientific files, and GA/ACO/ABC implementation are unchanged. The only new scientific file and its five functions are recorded in `source_guard.json`.

## AB. PRODUCTION / REMOTE / TAG STATUS
No deployment, remote push, publication work, or completion tag was performed.

## AC. READY FOR INDEPENDENT REVALIDATION?
READY FOR INDEPENDENT REVALIDATION
