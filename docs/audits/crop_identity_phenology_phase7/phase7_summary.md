# V2 Scientific Phase 7 — Crop identity and phenology contract

## Resolution result

The frozen 58-crop Akkaya runtime catalog resolves to **45 exact**, **9 reviewed alias**, **3 ambiguous**, and **1 missing** parameter identities. The reviewed layer safely resolves 9 of the 13 historical direct-lookup failures. The three Kabak forms remain ambiguous against generic `KABAK`; `SOGANTAZE` remains missing. None of the 13 crops using the unchanged legacy generic engine fallback is verified for pilot use.

## Phenology and pilot status

The frozen Akkaya runtime/project source data contains no sourced planting or harvest values. Verified phenology coverage is therefore **0/58**, and status is **PILOT_DATA_NOT_READY** while the existing demo remains **DEMO_READY**. Schema support and actual source coverage are reported separately.

## Scientific boundary

The `crop_water_parameters` and `crop_phenology` contracts support validated, versioned, explicitly confirmed project imports. They remain disconnected from the scientific engine (`engine_connected=false`). No Kc value, date, crop, candidate row, optimizer rule, or production source was changed. KIMYON candidate coverage, DUT economic completeness, Phase 5 rotation exposure 7/81 versus applied Turp options 6/32, and the inherited S2 test remain backlog items.
