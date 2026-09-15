# Economic authority policy

Economic authority is independent of the water authority enum. From highest to lowest it is:

1. `MEASURED_FARM_RECORD`
2. `OFFICIAL_MARKET_RECORD`
3. `LOCAL_INSTITUTIONAL_SOURCE`
4. `OFFICIAL_STATISTICS`
5. `DOCUMENTED_COMMERCIAL_SOURCE`
6. `CALCULATED_FROM_VERIFIED_INPUTS`
7. `CALCULATED_REFERENCE`
8. `DERIVED_PROXY`
9. `ASSUMED`
10. `FALLBACK`
11. `UNKNOWN`

`SCENARIO` is rejected because it describes modelling context, not source authority. Measured, official and local institutional claims require an institution and a reference or document.

`CALCULATED_FROM_VERIFIED_INPUTS` is derived authority, not a user-selectable promotion. It is available only when every required upstream dataset has one of these authorities: `MEASURED_FARM_RECORD`, `OFFICIAL_MARKET_RECORD`, `LOCAL_INSTITUTIONAL_SOURCE`, `OFFICIAL_STATISTICS`, `DOCUMENTED_COMMERCIAL_SOURCE`, or `CALCULATED_FROM_VERIFIED_INPUTS`. `CALCULATED_REFERENCE`, `DERIVED_PROXY`, `ASSUMED`, `FALLBACK`, and `UNKNOWN` are not verified inputs. A standard calculated profit claiming measured, official, or another direct-source authority is rejected. `DIRECT_SOURCE` remains separate and may retain the authority documented by its own source.

Authority, specificity and time freshness remain separate policy dimensions. An analysis-unit record has greater spatial specificity than a crop-level record, and a dated price has greater temporal specificity than a generic-year record. Those dimensions do not silently override authority. A future integration policy must choose and report each dimension explicitly.

Incoming lower-authority data cannot replace an active higher-authority dataset without explicit acknowledgement and a non-empty reason. Equal authority produces a conflict flag in preview. Higher authority also requires normal explicit confirmation. No upload changes the active pointer.

Coverage policy is literal. Missing KİMYON, DUT, secondary-season or cost-component records remain missing. The importer blocks unknown crop identities; it does not borrow a different crop's value. Readiness and UI expose missing/active state without inventing data.
