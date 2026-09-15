# Economics data contract

This milestone defines future, versioned economic inputs. It does not replace any packaged Akkaya value and no dataset in `economic_data` is read by GA, ACO, ABC, S1 or S2. The public Upload → Parse → Mapping → Validate → Preview → Confirm → Save pipeline is the only write path.

## Canonical datasets

| Data type | Record identity | Canonical value/unit | Meaning |
|---|---|---|---|
| `crop_yield` | crop | `yield_ton_da`, ton/da | observed or sourced crop yield |
| `crop_sale_price` | crop + price date/period | `price_tl_ton`, TL/ton | sale price; never profit per area |
| `crop_support_payment` | crop + support type | `amount_tl_da`, TL/da | separately identified support |
| `crop_cost_components` | crop + cost category | `amount_tl_da`, TL/da | itemized cost without invented allocation |
| `crop_net_profit` | crop | `net_profit_per_da`, TL/da | direct or documented calculation |
| `analysis_unit_economics` | analysis unit + crop | explicit TL fields | farm/parcel/accounting values |
| `seasonal_economics` | optional unit + crop + PRIMARY/SECONDARY | explicit mixed fields | future S2 economic observations |

All records carry planning and observation year, authority, provenance, geographic and crop scope, currency and units. One upload has one authority, planning year, geographic scope and crop scope. The active pointer key is `data_type|planning_year|geographic_scope|crop_scope`.

Yield accepts kg/da and ton/da. kg/da is divided by 1,000 with a stored conversion trace. Price accepts TL/kg and TL/ton. TL/kg is multiplied by 1,000 with a trace. TL/da is rejected as a price unit, so 6 TL/kg can never become 6,000 TL/da profit.

Support remains separate. Cost categories are `seed`, `fertilizer`, `pesticide`, `labor`, `energy`, `irrigation`, `machinery`, `harvest`, `transport`, `storage`, `marketing`, `rent`, and `other`. Missing categories remain listed as missing; a total is never distributed into invented components.

Net-profit methods are `DIRECT_SOURCE`, `GROSS_MINUS_TOTAL_COST`, `GROSS_PLUS_SUPPORT_MINUS_TOTAL_COST`, and `OTHER_DOCUMENTED_METHOD`. Calculated methods require dependency dataset IDs and store their formula. Yield × price is valid only for matching crop, year and TRY inputs; cross-year combinations require a later explicit scenario contract.

## Phase 4 source mapping

| Phase 4 source layer | Canonical future type | Current authority interpretation | Current engine status |
|---|---|---|---|
| catalog `beklenen_verim_kg_da` | `crop_yield` | DERIVED_PROXY | unchanged |
| catalog `satis_fiyati_tl_kg` | `crop_sale_price` | DERIVED_PROXY | unchanged |
| catalog support fields, when explicit | `crop_support_payment` | source-specific | unchanged |
| catalog/itemized costs | `crop_cost_components` | DERIVED_PROXY / UNKNOWN | unchanged; 50 mismatches and DUT gap retained |
| catalog `net_kar_tl_da` | `crop_net_profit` | DERIVED_PROXY | unchanged; Turp remains 4,000 TL/da |
| analysis-unit current profit | `analysis_unit_economics` | CALCULATED_REFERENCE | unchanged |
| S1 candidate matrix profit | `crop_net_profit` or future unit candidate contract | DERIVED_PROXY | unchanged |
| S2 seasonal `profit_tl` | `seasonal_economics` | DERIVED_PROXY | unchanged |
| nine S2 fallback parameters | future fallback provenance | FALLBACK | unchanged |

Crop identity uses the existing project catalog and exact normalized matching. Unknown or ambiguous identities are blocked. TURP, KIRMIZI TURP, TURP (KIRMIZI), dry/irrigated, and grain/silage variants remain distinct.

The planned result provenance fields are `economic_source_type`, `economic_dataset_id`, `economic_version`, `fallback_used`, `fallback_source`, `raw_profit_per_da`, `suitability_multiplier`, `profit_realism_multiplier`, `effective_profit_per_da`, and `transformations`. These fields are a future integration contract only.
