# V2 Scientific Pre-Pilot Freeze

## Frozen scientific reference

The immutable scientific source/data baseline is `bb0c6ff516a7d995c2894ee66285ebf124ac9340`, accepted by annotated tag `v2-crop-identity-phenology-contract-complete`. This package adds reproducibility and publication-boundary evidence only. It does not change the optimizer, scientific engine, candidate matrix, crop values, water values, economics values or phenology values.

## Accepted lineage and fixes

The Git lineage in `scientific_lineage.csv` resolves every accepted tag to a full commit and verifies ancestry. It records perennial-lock authority, the calendar-month correction, water/economics authority contracts, Turp diagnosis, 58/69 catalog reconciliation, and Phase 7 agricultural season semantics with fail-closed readiness.

## Reference and readiness

The frozen Akkaya state contains 179 analysis units, 134919 da, 6859 candidate rows and 58 crops. Current calculated demand is 100700080.81 m³ and current calculated profit is 1041499119.212 TL. Status remains `DEMO_READY` and `PILOT_DATA_NOT_READY`.

## Reproducibility scope

GA, ACO and ABC have seeded frozen artifacts for a three-unit regression fixture containing P1, P23 and P149. These artifacts cover S1/S2 and seeds 123/456/789, and are reproducibility evidence only; they are not basin-level or 179-unit performance evidence. The separate 24-unit synthetic project demonstrates software and architectural generalization for S1/S2 without Akkaya sources. Neither fixture establishes external agronomic field validation. No robustness or sensitivity experiment was run in this milestone.

## Evidence provenance schema

Manifest schema v1.1 and `publication_evidence_inventory.csv` distinguish `scientific_source_commit` (the accepted frozen scientific source/data baseline) from `artifact_introduction_commit` (the first Git commit containing that evidence artifact). The inventory also records population type, analysis-unit count and publication scope.

## Publication use

Use `claim_boundary.md`, the reviewer and limitation matrices, and `publication_evidence_inventory.csv` when designing the next experiment or manuscript. Proxy, assumed and missing inputs must retain their authority labels.
