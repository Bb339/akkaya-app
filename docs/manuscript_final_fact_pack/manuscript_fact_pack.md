# Final manuscript scientific fact pack

**Frozen product HEAD:** \`7d5152f99aaa400a739d6a2e4234b96d1f314271\`  
**Purpose:** evidence-constrained manuscript support for the *Journal of Agricultural Sciences / Tarım Bilimleri Dergisi*.  
**Rule:** every numerical statement below is tied to a repository source. Missing evidence is reported as **NOT ESTABLISHED**. The 24-unit institutional package is synthetic software/data-ingestion validation and is never treated as Akkaya field evidence.

## A. Study area facts

The accepted reference case represents the Akkaya irrigation planning area in Niğde, Türkiye, for planning year 2024. The active dataset contains **179 representative analysis units**, **134,919 da**, and five attributed settlements: **Sazlıca, Bahçeli, Kemerhisar, Kaynarca, and Bor Merkez**. The calculated current-pattern gross irrigation demand is **100,700,080.81 m³** and the catalog-derived current-pattern net profit is **1,041,499,119.212 TL**.

| Value | Unit | Source/key | Role | Classification |
|---|---|---|---|---|
| 179 | analysis units | \`parcel_master.csv\`, row count | spatial decisions | DERIVED |
| 134,919 | da | \`parcel_master.csv.area_da\`, sum | modeled area | DERIVED |
| 100,700,080.81 | m³ | \`water_context.csv\`, planning_reference_current_crop_pattern | current-demand planning reference | CALCULATED |
| 1,041,499,119.212 | TL | \`experiment_manifest.json.baseline_reproduction\` | catalog-derived baseline | CALCULATED |
| 5 | settlements | \`parcel_master.csv.village\` | spatial strata | DERIVED |
| 2024 | year | accepted reference files | planning year | DERIVED |

The reservoir series contains 2000–2025 descriptive records, but its authority is not established. Reservoir storage must not be substituted for the optimization budget. The accepted engine annual S2 scenario budget is **10,401,986.556 m³** after an assumed 10% environmental-flow reserve; this is a **SCENARIO** value, not an official allocation. Official annual allocation and measured delivery are **NOT ESTABLISHED**.

Settlement totals, crop-area distributions, current demand, and current catalog profit are in Table 1. Exact irrigated-area separate from total modeled area is **NOT ESTABLISHED** as a distinct authoritative measure.

## B. Data sources

Primary repository evidence comprises the 2024-labelled parcel/crop matrices, CROPWAT/FAO-56-referenced climate and crop-water inputs, crop and economic catalogs, candidate matrix, reservoir/delivery scenario files, accepted audits, and immutable robustness outputs. Important authority boundaries:

- Parcel area, current crop, and current summary fields are Excel-derived project records.
- ETo values are CROPWAT/FAO-56 Penman–Monteith reference or Excel-synchronized inputs. The software does **not** independently derive the full FAO-56 Penman–Monteith equation from raw meteorological observations on the accepted path.
- Some missing crop, Kc, soil, water, geometry, and economic values use documented proxies.
- Economic values are 2024-labelled proxy/old-catalog values. They are not audited farm accounts.
- Monthly delivery capacity is a derived proxy.
- Official DSİ allocation, measured withdrawals, and official ecological-release evidence are **NOT ESTABLISHED**.

Table 9 is the concise authority matrix; \`data_lineage_manifest.md\` records hashes and roles.

## C. Water methodology

The implemented chain is a CROPWAT/FAO-56-style accounting workflow using precomputed/synchronized ETo inputs:

1. **Crop evapotranspiration:** \`ETc,d = Kc,d × ET0,d\`, where ET0 and ETc are mm d⁻¹ and Kc is dimensionless. Daily Kc is constructed from initial, development, mid-season, and late-season stages. Stage inputs may be days or fractions; \`_kc_curve_daily\` rescales them to season length.
2. **Monthly USDA-SCS effective precipitation:** \`Peff=P(125−0.2P)/125\` for 0<P≤250 mm; \`Peff=125+0.1P\` above 250 mm, bounded to [0,P]. The monthly value is distributed across days.
3. **Net irrigation requirement:** \`NIRd=max(0,ETc,d−Peff,d)\`.
4. **Gross irrigation requirement:** \`GIRd=NIRd/η\`, where η is total irrigation efficiency constrained by implementation to 0.35–0.95.
5. **Volume conversion:** 1 mm over 1 da = 1 m³; seasonal unit volume is gross mm × area in da.

Implementation: \`app.py:_effective_rain_scs_mm\`, \`_kc_curve_daily\`, and \`compute_fao56_monthly_irrigation_mm\`. Inputs: \`monthly_climate_all_parcels.csv\`, \`crop_params_assumed.csv\`, irrigation-method files, and candidate matrices. Classification: ETo **CROPWAT/FAO-56-referenced / derived**, Kc mixed **LITERATURE/ASSUMED/PROXY**, and ETc/NIR/GIR **CALCULATED**.

Perennials are locked in S2 where the accepted current-state contract requires it. Second crops require explicit seasonal/candidate evidence. Cross-year phenology is supported by explicit season-year semantics. Planting/harvest dates are incomplete for Akkaya crops; 13/58 direct Kc lookups use a generic fallback and only 45/58 runtime identities have direct stage matches.

## D. Economic methodology

For crop c and area A: \`GrossRevenue = Yield (kg da⁻¹) × Price (TL kg⁻¹)\`; \`NetProfit = GrossRevenue − Cost\`; \`TotalProfit = Σ A × NetProfit\`; and \`WaterProductivity = TotalProfit / TotalWater\` in TL m⁻³.

The accepted current-unit profit totals mechanically equal area × catalog net profit per da. Candidate totals satisfy profit/area, yield/area, and kg/ton identities across all 6,859 rows. S1 consumes candidate \`profit_tl_da\`; S2 consumes seasonal profit per area and applies accepted suitability/profit-realism transforms. Negative or missing economics may make candidates infeasible. Independent price and yield sensitivity are not executable on the frozen path; the performed economic sensitivity scales connected direct net-profit inputs.

Economic authority is **DERIVED/ASSUMED proxy**. Total profit must not be described as realized income.

## E. Current baseline

**Thesis baseline:** NOT ESTABLISHED as a distinct, fully traceable table in the accepted evidence inspected here.  
**Current accepted scientific baseline:** 179 units, 134,919 da, 58-crop runtime catalog, 6,859 candidate rows, 100,700,080.81 m³ current calculated gross demand, and 1,041,499,119.212 TL catalog-derived profit.  
**Recommended manuscript baseline:** the current accepted baseline because it is hashed, reproduced, and used by the accepted robustness experiment. Do not average it with older thesis values.

## F. S1 formulation

Let U be analysis units and Cᵤ the allowed candidate set. Binary xᵤc=1 selects candidate c for unit u. The one-crop rule is \`Σc∈Cᵤ xᵤc = 1\` for every u. Water is \`Σ Aᵤwᵤcxᵤc\` and profit is \`Σ Aᵤπᵤcxᵤc\`.

Candidate generation applies crop identity, suitability, rotation/calendar, perennial, water, and economics contracts. Area is conserved because the selected option covers the unit area. Annual water is validated against the selected planning budget; monthly delivery is reported when supported. The 6,859-row matrix is the accepted raw universe. Counts 3,673 and 129 are **NOT ESTABLISHED** as current accepted subset counts and must not be used.

## G. S2 formulation

S2 permits a primary crop plus only an explicitly supported secondary crop. Protected perennial primary states remain fixed. Primary and secondary identities must differ; the secondary must have compatible seasonal timing, explicit water/economic evidence, and pass suitability/rotation/feasibility checks. Water and profit aggregate both seasons over the same unit area without duplicating area ownership.

The accepted full-project S2 outputs are **DIAGNOSTIC ONLY**: annual feasibility first appears at tested multiplier 2.5, while monthly delivery remains violated and overall feasibility is false. The invalid-second-crop guard is the conjunction of explicit seasonal eligibility, same-crop prohibition, and accepted second-season water/economic records.

## H. Objective functions

The application exposes three **selectable single-objective modes**, one per run. It is not simultaneous multi-objective optimization.

With P=total profit (TL), W=total water (m³), and E=P/max(W,1) (TL m⁻³), implementation score terms are:

- \`water_saving\`: \`350000E + 0.18P − 1.35(500W)\`
- \`water_efficiency\`: \`1600000E + 1.00P − 0.55(500W)\`
- \`max_profit\`: \`250000E + 1.35P − 0.35(500W)\`

The optimizer maximizes the chosen scalar score while feasibility guards/penalties handle constraints. Exact tie-breaking beyond deterministic seeded implementation order is **NOT ESTABLISHED** as a separate scientific rule.

## I. Candidate matrix

The accepted Akkaya matrix has 179 units, 6,859 rows, and 57 candidate identities; the runtime catalog has 58 crops, with KİMYON absent from the matrix. Rows contain area, crop group, gross/net water per da and total, yield, profit per da and total, current-crop flag, quota feasibility, efficiency, peak month, soil proxy, and quota references. Suitability, perennial locks, rotation/calendar, water, economics, and scenario filters reduce options at runtime. Annual/monthly feasibility is validated after complete-plan construction.


## J. GA settings

Accepted robustness settings: population 12, generations 10, crossover 0.70, mutation 0.08, seeds 101/211/307/401/503. Initialization includes greedy, profit, and water seeds plus mixed assignments. Selection is a four-way tournament; crossover is one-point; mutation randomly reassigns unlocked units; the best two solutions are retained. The fixed 10 generations are the stopping rule.

## K. ACO settings

Accepted settings: 10 ants, 10 iterations, evaporation 0.25, q=1.0, with the same seed set. The choice weight is pheromone^1.0 × localUtility^2.1. Pheromone starts at 1, evaporates by rho=0.25, is clipped to [10⁻⁶,10⁶], and the iteration-best assignment receives q-scaled deposit. The fixed 10 iterations are the stopping rule.

## L. ABC settings

Accepted settings: 10 food sources, 10 cycles, abandonment limit 4, same seed set. Food sources begin with greedy, profit, water, and mixed assignments. Employed and onlooker phases try 1–4 unlocked-unit neighbor moves; fitness-proportional onlooker choice is used; a source reaching limit 4 is replaced by a mixed scout solution. The fixed 10 cycles are the stopping rule.

## M. Benchmark design

The accepted publication robustness design contains 54 active result runs, five predetermined seeds, three algorithms, S1/S2, annual-water threshold scenarios, and ±20/±10/0% direct net-profit shocks. Pilot median runtime was 64.011 s; projected ten-seed core time was 3,840.66 s, so five seeds were preregistered.

The older 10/15/30/50/100 repeat choices are **not established as accepted result-bearing manuscript experiments**. A 30-repeat policy test exists in software tests but is not scientific evidence. Publication should use the accepted five-seed experiment and disclose its computational decision rule. S1 accepted active runs have 100% feasibility. S1 water CV is 0.00838 (GA), 0 (ACO), and 0.00164 (ABC). The repository does not establish feasible rate ≥95% and CV ≤5% as universal scientific laws; report observed statistics.

## N. Final optimization results

Table 5 reports the current baseline and S1 \`water_saving\` summaries. Mean total water is approximately 59.83 million m³ (GA), 58.07 million m³ (ACO), and 58.14 million m³ (ABC), versus 100.70 million m³ current calculated demand. Mean catalog/model profit is approximately 785.22, 774.60, and 774.49 million TL. These are frozen-model outputs under proxy economic and water assumptions.

S2 GA/ACO/ABC values exist only as infeasible-search diagnostics and must not appear in a recommended-solution table. Accepted result-bearing combinations for every objective × algorithm × scenario are **NOT ESTABLISHED**; do not populate missing cells.

## O. Monthly water validation

Table 7 and Figure 7 use the accepted 12-month reconciliation. The full S2 GA seed-123 diagnostic demand exceeds effective proxy delivery capacity in all months. June has the largest modeled deficit and is the accepted critical/worst month for this diagnostic. Annual budget, monthly capacity, and overall feasibility must be reported separately. Environmental release ratio 0.10 is an **ASSUMED** scenario parameter. Official monthly supply is **NOT ESTABLISHED**.

## P. Sensitivity and robustness

Evidence-backed analyses:

- Annual water-budget multipliers: 1.0, 1.5, 2.0, 2.055859, 2.164062, 2.272265, 2.5, 3.0.
- GA/ACO/ABC seed robustness over five preregistered seeds.
- Connected direct net-profit shocks: −20%, −10%, 0%, +10%, +20%.
- Crop-pattern agreement: weighted Jaccard, Bray–Curtis, top-1/top-3 agreement, HHI.
- Same-seed determinism after excluding timestamp/runtime metadata.

Independent price sensitivity, yield sensitivity, full algorithm-parameter sensitivity, multi-year climate variability, climate-change projections, and external field sensitivity are **FUTURE WORK — NOT PERFORMED**.

## Q. Five-settlement results

Table 1 provides parcel counts, area, current crop structure, calculated demand, and catalog-derived current profit for all five settlements. Settlement-level optimized water/profit/crop recommendations are **NOT ESTABLISHED**. Figure 8 was therefore not generated.

## R. General PROJECT_DATA architecture

The system separates \`AKKAYA_REFERENCE\` from \`PROJECT_DATA\`. Files are structurally detected, reviewed, explicitly confirmed, written to a numbered project revision, transformed into a decision context, pinned by revision/selection hash, executed by GA/ACO/ABC, stored as an immutable run, and presented through map/table/chart/provenance views. Missing or ambiguous identity fails closed. Flask/Python provides the backend; HTML/CSS/JavaScript, Leaflet, and Chart.js provide presentation. The project store is filesystem-based. This architecture supports traceable ingestion; it does not prove agronomic generalization.


## S. 21-file package

The exact filenames, detector types, and SHA-256 hashes are in \`docs/v1_native_project_integration_fix2/05_full_visual_demo_manifest.csv\`. Accepted facts: 21/21 \`AUTO_MATCHED\`, explicit confirmation, revision 21, planning year 2025, 24 analysis units, 24 geometries, 24/24 candidate coverage, and 8 crops. Every file is **SYNTHETIC_DEMO / NOT OFFICIAL**. Its purpose is generalized ingestion and workflow validation.

## T. Synthetic / derived data disclosure

Table 9 is the principal disclosure matrix. Synthetic values are used only for platform demonstration and never presented as Akkaya observations. Akkaya also contains derived/proxy elements; these are disclosed by the water, economics, and crop audits.

## U. System architecture

Agriculturally relevant chain: Python/Flask → provider-specific project store → detector/import confirmation → project revision → scientific readiness → decision context → pinned preview → subprocess-isolated optimizer (300 s limit) → immutable stored run → Leaflet map, tables, Chart.js plots, and provenance. Providers are explicit and PROJECT_DATA cannot fall back to reference data. TR/EN presentation changes language without changing scientific state.

## V. Validation taxonomy

A. **Agronomic/scientific case evidence:** internally reconciled Akkaya 2024 planning model and spatial units; not external field validation.  
B. **Software verification:** API/browser/source guards, contracts, provider isolation, stored-run reload.  
C. **Computational reproducibility/robustness:** hashes, seeds, immutable runs, repeated summaries, sensitivity grids.  
D. **Synthetic generalization/data-ingestion validation:** 21-file, 24-unit project; not independent agronomic validation.

## W. Previous reviewer concerns

| Concern | Classification | Evidence now available | Safe response | What not to claim |
|---|---|---|---|---|
| Technological novelty | PARTIALLY ADDRESSED | traceable integrated pipeline | novelty lies in integration | novel GA/ACO/ABC |
| Methodological novelty | PARTIALLY ADDRESSED | coupled water/economics/constraints/spatial outputs | integrated DSS contribution | new metaheuristic theory |
| Single-year analysis | STILL A LIMITATION | 2024 planning year | single-year demonstration | multi-year validation |
| Field validation | STILL A LIMITATION | none independent | computational case study | field validated |
| Algorithm rationale | RESOLVED | discrete constrained assignment and three search mechanisms | comparative heuristic search | universal superiority |
| Parameter sensitivity | PARTIALLY ADDRESSED | seeds, water budget, profit shock | bounded robustness evidence | exhaustive sensitivity |
| Reservoir constraint | PARTIALLY ADDRESSED | reconciled scenario budget/proxy capacity | scenario constraint with authority caveat | official allocation |
| Climate variability | STILL A LIMITATION | no multi-year experiment | future work | climate resilient |
| Remote sensing | STILL A LIMITATION | not integrated | potential future input | RS-validated |
| Soil information | STILL A LIMITATION | proxy suitability | heuristic filter | official soil map |
| Expert validation | STILL A LIMITATION | NOT ESTABLISHED | planned validation | expert validated |
| Generalization | PARTIALLY ADDRESSED | synthetic ingestion path | schema-driven ingestion demonstrated | external agronomic generalization |
| Reproducibility | RESOLVED computationally | hashes, seeds, manifests, immutable runs | reproducible under frozen inputs | real-world repeatability |
| Robustness | PARTIALLY ADDRESSED | accepted S1 experiment | robustness under tested factors | comprehensive uncertainty |

## X. Claim-boundary matrix

| Term | Classification | Recommended wording |
|---|---|---|
| AI-based | DO NOT CLAIM | — |
| AI-assisted | NEEDS QUALIFICATION | “metaheuristic-assisted decision support” |
| metaheuristic optimization | SAFE TO CLAIM | “GA-, ACO-, and ABC-based selectable search modes” |
| generalized/generalizable | NEEDS QUALIFICATION | “schema-driven project-data ingestion demonstrated on synthetic data” |
| institution-ready | NEEDS QUALIFICATION | “institution-oriented import and provenance workflow” |
| field validated / externally validated | DO NOT CLAIM | — |
| real-time | DO NOT CLAIM | “interactive after computation” |
| multi-objective | DO NOT CLAIM | “selectable single-objective modes” |
| climate resilient | DO NOT CLAIM | — |
| sustainable | NEEDS QUALIFICATION | “supports water-constrained crop-pattern assessment” |
| decision support | SAFE TO CLAIM | “traceable agricultural decision-support framework” |
| automated data ingestion | NEEDS QUALIFICATION | “automated structural detection followed by explicit confirmation” |
| automatically adaptable | DO NOT CLAIM | “accepts data satisfying explicit contracts” |
| reproducible | SAFE WITH SCOPE | “computationally reproducible under frozen inputs and seeds” |
| explainable | SAFE WITH SCOPE | “reports objectives, constraints, selections, and provenance” |
| traceable | SAFE TO CLAIM | “revision-, preview-, run-, and source-traceable” |

## Y. Manuscript tables

Nine supported tables are supplied as CSV and Markdown in \`manuscript_tables/\`. Recommended placement: Methods—Tables 1–4 and 9; Results—Tables 5–7; Results/Discussion limitations—Table 8. Move the full 58-row Table 2 to supplementary material if required by journal length.

## Z. Manuscript figures

Eight programmatic figures are supplied in PNG at 350 dpi and SVG:

1. Study-area parcel/reservoir geometry.
2. Methodological workflow.
3. Institutional data-to-decision architecture.
4. Crop water–economic trade-off.
5. Baseline vs S1 water-saving results.
6. S1 repeated-run robustness.
7. Monthly water diagnostic.
9. Current vs representative ACO S1 seed-101 crop composition.

Figure 8 is unsupported because settlement-level optimized outputs are absent. Figure 10 requires a manual/live valid English screenshot. A Projects/readiness screenshot is optional supplementary material.

Recommended order: Introduction—Figure 1; Methods—Figures 2–3 and Tables 1–4/9; Results—Figures 4–7 and 9 with Tables 5–7; Discussion—Table 8 and limitations; system-generalization subsection or supplement—manual Figure 10.

Do not include debug/provenance screenshots, synthetic project result plots as agricultural results, duplicate dashboards, or figures that mix synthetic values with Akkaya science.

## AA. References and data sources

Repository evidence explicitly supports **FAO-56 / CROPWAT** and a **Doorenbos–Kassam-style** yield-response concept. Complete bibliographic metadata for Allen et al., CROPWAT manuals, Doorenbos–Kassam, Holland/GA, Dorigo/ACO, Karaboga/ABC, crop-pattern optimization, agricultural DSS, and water scarcity is **NOT ESTABLISHED in repository evidence**. Verify primary publications before submission; do not invent years, editions, DOIs, or page numbers.

Primary/authoritative repository evidence consists of accepted source-data lineage, canonical project files, manifests, and algorithm implementation. Secondary literature is referenced by method labels but lacks a frozen bibliography.

## AB. Data/code availability draft

**Data availability.** Results use repository-packaged, partly derived/proxy Akkaya planning data. Underlying private or institutional workbooks may be restricted. The synthetic 21-file package is not official data and is only a workflow demonstration. State availability according to the owner’s release decision.

**Code availability.** Do not state that code is public without owner confirmation. A frozen commit hash and dependency manifest support controlled reproducibility.

**Reproducibility.** Runs record input hashes, scenario identity, algorithm, seed, run ID, and immutable output. Reproduction establishes software/model repeatability under frozen inputs, not field validity.

## AC. NOT ESTABLISHED items

See \`unresolved_items.md\`. The material gaps are official water allocation/delivery, independent field validation, multi-year optimization, complete bibliography, authoritative Kc/economics for all crops, settlement-level optimized results, soil/remote-sensing evidence, expert validation, and a live English manuscript screenshot.

## Final quality boundary

No synthetic value is represented as an Akkaya observation; software tests are not field validation; no algorithm novelty, simultaneous multi-objective, real-time, external-validation, or climate-resilience claim is made. Every generated chart has units and traceable sources. S2 remains diagnostic.

