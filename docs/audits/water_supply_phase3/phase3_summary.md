# Scientific Phase 3 — verified water supply and protected perennial demand floor

## Sonuç

Mevcut model girdileri altında yapısal infeasibility doğrulandı; real-world infeasibility doğrulanmadı. Kullanılan reservoir ve delivery serilerinin resmî/ölçülmüş arz olduğuna dair kaynak yoktur.

| Kavram | Değer | Authority |
|---|---:|---|
| Current-pattern calculated gross demand | 100,700,080.810 m³ | CALCULATED_REFERENCE |
| Reservoir irrigation baseline sum | 11,557,762.840 m³ | UNKNOWN |
| Engine annual budget after 10% reserve | 10,401,986.556 m³ | SCENARIO |
| Raw monthly delivery sum | 13,291,427.000 m³ | DERIVED_PROXY |
| Effective delivery sum | 11,962,284.300 m³ | SCENARIO |
| Protected perennial current reference | 31,264,646.990 m³ | CALCULATED_REFERENCE |
| Protected perennial current-model floor | 22,510,545.833 m³ | SCENARIO |
| Full S2 GA seed123 plan | 23,933,291.203 m³ | SCENARIO |

## Protected set and floor

- 52 observed-current perennial units, `39,486.0 da`.
- Current reference sum: `31,264,646.990 m³`.
- Existing engine water_saving floor: primary calibrated current-crop demand × `0.72` = `22,510,545.833 m³`.
- This is objective-dependent model demand. It is not observed use, independently validated agronomic minimum, or survival water.
- Active calibrated S2 rows have no planting/harvest dates, so a defensible crop-specific monthly perennial floor cannot be produced.

## Necessary feasibility condition

- Annual model floor minus engine budget: `12,108,559.277 m³`.
- Minimum diagnostic factor relative to engine budget: `2.164062`.
- Minimum diagnostic factor relative to effective delivery sum: `1.881793`.
- These are lower-bound ratios, not recommended budgets or capacity multipliers.

## Source conclusions

- The 179 analysis-unit current water fields reproduce `100,700,080.81 m³` exactly within floating tolerance.
- The 12 reservoir irrigation-baseline rows reproduce `11,557,762.840 m³` and match the 2024 `cekis_su_hacmi_hm3` annual field within `0.001 m³`. The header/unit conflict, absent generator and absent official citation leave authority UNKNOWN; the numerical match only establishes an internal lineage link.
- All 12 delivery ratios are approximately `1.15`; the source note calls the capacity assumed. It is DERIVED_PROXY.
- `envFlowRatio=0.10` is an existing configurable model assumption; no local official ecological-release evidence was supplied.

No optimizer, production source, scientific input, ProjectStore, budget, lock, delivery value or UI code was changed.
