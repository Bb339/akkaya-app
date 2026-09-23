# Institutional data template index

Existing files under `docs/data_templates/` remain authoritative examples.

| Domain | Data types | Required canonical content | Canonical units | Accepted units | Authority / year rule |
|---|---|---|---|---|---|
| Water | annual/monthly supply | year, amount; month for monthly | m3/year, m3/month | m3, hm3 and documented conversions | verified water authority; project year |
| Water | delivery | month, capacity, basis | m3/month | m3/month, hm3/month, documented m3/s | verified authority; 12 months |
| Water | environmental release | ratio or 12 physical releases | ratio or m3/month | explicit contract units | verified authority; executable engine requires one annual ratio |
| Water | conveyance | period, scope, efficiency | ratio | ratio | one unambiguous project record |
| Water | perennial requirement | crop/unit/month/value | m3/da | m3/da or mm | verified authority; project year |
| Economics | yield, price, support, costs | crop, value, unit, source | ton/da, TL/ton, TL/da | documented kg/da and TL/kg conversions | verified authority; current project year/scope |
| Economics | net profit | crop and direct or dependency-backed calculation | TL/da | TL/da | complete crop coverage; dependencies current |
| Economics | unit/seasonal | unit, crop, season and values | TL or TL/da | contract units | project IDs, current year/scope |
| Crop parameters | crop water parameters | resolved identity, Kc and stage values | ratio and days/fractions | canonical contract | exact/reviewed identity; verified authority |
| Phenology | crop phenology | crop, season, dates or windows | ISO date or MM-DD | canonical contract | project year/scope; S2 primary+secondary |
| Candidates/current pattern | candidates, scientific inputs, units, crops | explicit unit×crop candidates and current state | m3/da, TL/da, da | existing import aliases/mapping | applied import provenance required |

Column aliases are suggested by the existing mapping layer. Ambiguous mappings require explicit user selection; manual conversion to internal CSV headers is not required.
