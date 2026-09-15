# V2 Scientific Phase 6 — Crop catalog reconciliation

## Finding

**58 and 69 count different contracts.** The 58 are rows and unique identities in `urun_parametreleri_demo.csv`, the economic/project runtime catalog copied by `akkaya_demo.build_demo`. The 69 are rows and unique identities in `crop_params_assumed.csv`, an assumed Kc and stage-fraction table. Both retain their counts after production canonicalization, but only 47 identities intersect. Therefore `69 - 58 = 11` does not prove eleven missing products.

The production-canonical symmetric difference contains 33 identity rows. Reconciliation finds seven paired naming relations (14 rows), a four-row Kabak granularity group, 14 parameter-only identities, and one genuine runtime parameter gap: **SOĞAN TAZE**. Production code was not changed, and unsafe form/variant merges were not proposed.

## Runtime effects

- Direct Kc/stage lookup succeeds for 45/58 runtime crops and silently uses the generic Kc fallback for 13/58.
- The source tree contains no planting or harvest date fields. Stage fractions exist for the same direct 45 matches; calendar rules provide season labels, not dates.
- Economics are complete for 57/58. DUT lacks yield and gross revenue while retaining price, cost, net profit, and calibrated water.
- The frozen candidate matrix has 57 identities and omits only KIMYON from the runtime catalog. S1 and S2 primary each have 56 identities; S2 secondary has 4: ARPAYESILOT, FIGYESILOT, SILAJLIKMISIR, YONCAYESILOT.
- Project catalog (58), parameter catalog (69), candidate universe (57), seasonal universe (56), and observed runtime option universe (50) are separate concepts.

## Impact boundaries

TURP (KIRMIZI) is present in the runtime catalog, parameter table, candidate matrix, S1, S2 primary, and family map. The Phase 5 dominance conclusion is not materially changed by the 58/69 discrepancy. The Phase 5 rotation reporting distinction remains backlog only: exposure 7/81 versus applied Turp-option counts 6/32.

All observed protected perennial current crops remain covered by the runtime catalog/candidate sources used by the Phase 3 water floor. Five names in the broader code-level perennial registry (FINDIK, FISTIK, INCIR, NAR, ZEYTIN) are not observed Project Crop records and do not enter that frozen audit population.
