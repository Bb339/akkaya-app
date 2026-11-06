# Figure manifest

All programmatic figures use DejaVu Sans, a white background, colorblind-safe Okabe–Ito colors, English labels, PNG at 350 dpi, and SVG vector export. Generation used Python 3.11, pandas 2.3.1, NumPy, and Matplotlib 3.10.7 in direct read-only transformations.

## Figure 1 — Location and spatial structure of the Akkaya irrigation study area

**Caption:** Accepted parcel polygons attributed to Sazlıca, Bahçeli, Kemerhisar, Kaynarca, and Bor Merkez, together with the Akkaya reservoir geometry. Colors identify settlement attribution; administrative boundaries are not inferred. Coordinates are degrees.  
**Placement:** Main manuscript, Study area.  
**Data/files used:** \`data/_geojson_index.json\`; listed \`data/geojson_yeni_klasor4/*.geojson\`.  
**Transformation:** Direct polygon rendering without smoothing.  
**Generated files:** \`figure_01_study_area.png/.svg\`.  
**Reviewer question:** spatial scope and five-zone coverage.  
**Limitation:** exact five-settlement administrative boundaries are not all supplied.

## Figure 2 — Data-to-decision methodological workflow

**Caption:** Evidence-supported sequence from climate, crop, economic, water, and spatial inputs through CROPWAT/FAO-56-style accounting, scenario construction, selectable single-objective search, constraint validation, and traceable outputs. S2 is diagnostic under accepted constraints.  
**Placement:** Main manuscript, Methods.  
**Data/source:** implementation and accepted contracts.  
**Method:** Programmatic vector diagram.  
**Generated files:** \`figure_02_methodological_workflow.png/.svg\`.

## Figure 3 — Generalized institutional data-to-decision architecture

**Caption:** Provider-separated ingestion architecture. AKKAYA_REFERENCE supplies the scientific case; PROJECT_DATA demonstrates schema detection, explicit confirmation, revision pinning, optimization, immutable storage, and presentation using synthetic—not field—validation data.  
**Placement:** Main manuscript, Generalization subsection.  
**Generated files:** \`figure_03_project_architecture.png/.svg\`.

## Figure 4 — Packaged crop water–economic trade-off

**Caption:** Gross irrigation requirement (m³ da⁻¹) versus catalog net profit (TL da⁻¹) for 58 runtime crops. Selected extremes are labeled. Values are planning proxies, not observed farm accounts.  
**Placement:** Main manuscript, Data/Methods.  
**Data:** \`data/urun_parametreleri_demo.csv\`.  
**Transformation:** Direct scatter; no smoothing.  
**Generated files:** \`figure_04_crop_water_economic_tradeoff.png/.svg\`.

## Figure 5 — Current baseline versus accepted S1 water-saving results

**Caption:** Current calculated gross demand and catalog-derived profit compared with mean S1 water-saving outputs for GA, ACO, and ABC. Panels report million m³, million TL, and TL m⁻³. Algorithm values are frozen-model repeated-seed summaries.  
**Placement:** Main manuscript, Results.  
**Data:** \`data/parcel_master.csv\`; \`seed_variability.csv\`.  
**Generated files:** \`figure_05_baseline_vs_optimized.png/.svg\`.

## Figure 6 — S1 algorithm robustness

**Caption:** Mean ± standard deviation of total water and observed feasible-run rate for accepted active S1 water-saving runs. CV annotations are fractional water CV. Summary statistics are shown; no distribution is fabricated.  
**Placement:** Main manuscript, Robustness.  
**Data:** \`seed_variability.csv\`; \`run_level_results.csv\`.  
**Generated files:** \`figure_06_algorithm_robustness.png/.svg\`.

## Figure 7 — Monthly demand and capacity diagnostic

**Caption:** Full S2 GA seed-123 modeled monthly demand, reservoir irrigation baseline of unknown authority, and effective delivery-capacity proxy. Shading denotes modeled violations; June has the largest deficit. This is not official supply evidence.  
**Placement:** Main manuscript, Results/Water validation.  
**Data:** \`docs/audits/water_supply_phase3/monthly_water_reconciliation.csv\`.  
**Generated files:** \`figure_07_monthly_water_validation.png/.svg\`.

## Figure 8 — NOT SUPPORTED

Settlement-level optimized water/profit values are not established. No figure generated. Use Table 1 plus Figure 1 until accepted settlement-level optimization evidence exists.

## Figure 9 — Current versus representative recommended crop pattern

**Caption:** Major crop-area shares in the current 2024-labelled pattern and representative accepted ACO S1 water-saving run, seed 101. The recommendation is a frozen-model output under proxy water/economic assumptions.  
**Placement:** Main manuscript, Results.  
**Data:** \`data/parcel_master.csv\`; immutable run \`53e613e87b8565ad884a\` in \`run_level_results.csv\`.  
**Generated files:** \`figure_09_crop_pattern_comparison.png/.svg\`.

## Figure 10 — Manual screenshot required

**Screenshot instructions:** language EN; provider PROJECT_DATA; valid accepted 21-file synthetic project; exact stored run; unit KDS-001; S1; water_saving; GA; seed 123; viewport 1366×900. Show map, polygon, native badge, selected-unit summary, current water/profit, recommended crop, recommendation card, authority label, and seven-tab hierarchy. Hide developer tools, debug/upload controls, and unrelated panels. Drought must read NOT PROVIDED; no Turkish application text may be visible.  
**Placement:** Supplementary or short generalization subsection, never as field evidence.

## Optional Projects/readiness screenshot

Manual only. Capture EN Projects after 21 files are confirmed: project identity, revision 21, datasets, 24/24 unit and geometry coverage, 24/24 candidate coverage, and readiness. Recommended for supplementary material.

