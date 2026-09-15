# Phase 5 — Turp Dominance Root-Cause Audit

## Scope

Diagnosis only. Production data, Turp values, candidate matrix, optimizer, objectives, rotation, diversity and market constraints were not changed.

## Quantitative result

- Production identity is `TURP (KIRMIZI)` → `TURPKIRMIZI`. Plain `TURP` and `KIRMIZI TURP` remain distinct identities and are absent from the candidate matrix.
- Raw coverage is 43 units and 35036 da, entirely from Bor İlçe Merkezi / Bor. All 43 raw rows have the quota flag; the raw matrix has no `allowed` or suitability field.
- Raw unit coverage rank is 50-55/57; runtime unit coverage rank is 1-14/50.
- S1 runtime expansion reaches 127 units and 95433 da: +84 units, 2.953× unit coverage and 2.724× area coverage.
- The net +84 units consists of 94 new regional options and 33 retained local options; 10 raw Turp rows belong to perennial-locked units and are removed from Turp opportunity.
- Turp water is 298.87 m³/da, rank 1/37 and 100.00 best-percentile. It is 0.485× the annual-crop median.
- Turp equals the annual minimum (minimum ratio 1.000). The next-lowest crop is `MARUL` at 345.73 m³/da, or 0.864× that requirement.
- Turp profit is 4,000 TL/da, tied rank range 23-24/37 (2-way tie) and 38.89 best-percentile at the leading tie rank. It is 0.889× the annual-crop median. High absolute profit is not supported as a driver.
- The top annual profit is `SALÇALIK DOMATES` at 15992 TL/da; Turp is 0.250× that value.
- Turp efficiency is 13.383745 TL/m³, rank 3/37 and 94.44 best-percentile.
- Frozen S1 fixtures select Turp on P1 and P23 for GA, ACO and ABC at seeds 123, 456 and 789. Frozen S2 fixtures never select Turp.
- S2 has Turp primary evidence/fallback for 101 units (72 after the perennial lock), no secondary Turp, and transforms 4,000 TL/da to 1,870 TL/da through default suitability 0.85 and profit-realism 0.55.
- Perennial lock excludes 52 units / 39486 da. It lowers basin-wide opportunity while concentrating S1 Turp availability over the remaining 127 units / 95433 da.
- Turp is locally first under the water-saving ranker on 84/127 unlocked units. P1/P23 have 18, 17 retained candidates and 6, 6 competitors within 0.10 score of their local leader; the frozen global choice therefore cannot be reduced to a local greedy rank.
- At the frozen S1 Turp share (42.4114%), Turp contributes 0.179873 to HHI. The equal-four-other-crop diagnostic produces diversity penalty 0.035668 and matrix score deduction 0.004280; this is a diagnostic decomposition, not a proposed crop mix.

## Root cause

The primary drivers are the lowest water requirement in the 37 comparable annual crops, third-highest TL/m³, and a regional median expansion rule that converts 43 local observations into availability on every non-perennial unit. The 4,000 TL/da profit is below the annual median rank and does not explain dominance by itself. Identical S1 choices across algorithms and seeds support a model-space explanation rather than a GA/ACO/ABC-specific search bias.

Market demand, sales capacity, processing/storage capacity, regional production ceilings and a crop-specific maximum area are absent from the active scientific decision path. Existing concentration controls are soft: repair is disabled and the matrix score subtracts only `0.12 × diversity_penalty`.

The unresolved 58/69 catalog difference does not change this result because `TURP (KIRMIZI)` is present in the active 58-crop catalog. It remains a separate backlog item.

## S1 and S2

S1 combines raw candidate economics with basin-wide annual candidate expansion. S2 uses seasonal records, district fallback, suitability, profit realism, rotation and a two-crop structure. Turp has no secondary-season record and its effective S2 profit is 1,870 TL/da, explaining why the frozen S2 results favor other low-water crops.

## Classification

No software defect was demonstrated. Dominance is produced by expected optimization response to low water/high TL-per-m³, amplified by a broad expansion assumption and missing market-cap evidence. The expansion rule and missing raw `allowed`/suitability fields are model/provenance issues requiring scientific review before intervention.
