# Current data-to-engine gap

Audit baseline: `028f231eb774eafb53a9a76db370b663d561ce1b`.

The repository already has one upload, mapping, validation, preview and explicit-confirm pipeline. Water, economic, crop-parameter and phenology imports retain historical versions and active pointers. Before this phase those versioned contract datasets were intentionally exposed only as readiness/provenance facts and were not materialized into the scientific bundle. The existing generic engine path instead consumed `water_budget`, project catalog/economics and `scientific_inputs` directly. Institutional integration must join those layers without changing `kds/science/` or creating a second import store.

| data_type | contract_exists | upload_exists | validate_exists | preview_exists | confirm_exists | active_pointer_exists | readiness_exists | engine_connected_currently | current_engine_source | required_engine_source | integration_gap | risk |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|
| annual_water_supply | yes | yes | yes | yes | yes | yes | authority-only | no | `water_budget` | active confirmed project-year water dataset | selection and adapter absent | critical |
| monthly_water_supply | yes | yes | yes, 12 months | yes | yes | yes | authority-only | no | reference/generic seasonal resources | active confirmed 12-month dataset | selection and adapter absent | critical for S2 |
| delivery_capacity | yes | yes | yes, 12 months | yes | yes | yes | authority-only | no | `seasonal_resources.delivery` | verified capacity dataset | adapter absent | critical for S2 |
| environmental_release | yes | yes | yes | yes | yes | yes | authority-only | no | configured legacy ratio | verified ratio or physical release | adapter absent | critical |
| conveyance_efficiency | yes | yes | yes | yes | yes | yes | authority-only | no | irrigation/default context | verified scoped efficiency | adapter absent | critical |
| perennial_irrigation_requirement | yes | yes | yes | yes | yes | yes | authority-only | no | seasonal S2 observations | verified crop/unit requirement | adapter absent | critical for S2 |
| crop_yield | yes | yes | yes | yes | yes | yes, scoped | authority-only | no | project economics/candidate inputs | active verified project-year economics | resolver absent | critical dependency |
| crop_sale_price | yes | yes | yes | yes | yes | yes, scoped | authority-only | no | project economics/candidate inputs | active verified project-year economics | resolver absent | critical dependency |
| crop_support_payment | yes | yes | yes | yes | yes | yes, scoped | authority-only | no | none/legacy values | active verified optional support | resolver absent | optional |
| crop_cost_components | yes | yes | yes | yes | yes | yes, scoped | authority-only | no | project economics/candidate inputs | active verified project-year economics | resolver absent | critical dependency |
| crop_net_profit | yes | yes | dependency-aware | yes | yes | yes, scoped | authority-only | no | project economics/candidate inputs | active verified net profit | resolver and adapter absent | critical |
| analysis_unit_economics | yes | yes | yes | yes | yes | yes, scoped | authority-only | no | `unit_parameters.current_profit` | active verified unit economics | resolver absent | critical when used |
| seasonal_economics | yes | yes | yes | yes | yes | yes, scoped | authority-only | no | `seasonal_resources.s2.profit_tl` | active verified seasonal economics | resolver absent | critical for S2 |
| crop_water_parameters | yes | yes | identity-aware | yes | yes | yes, year/scope | explicit disconnected readiness | no | crop catalog/legacy resource | active verified exact/reviewed identity | adapter absent | critical |
| crop_phenology | yes | yes | season-year aware | yes | yes | yes, year/scope | explicit disconnected readiness | no | crop catalog/seasonal resources | active verified year/scope/season records | adapter absent | critical |
| candidates | yes | yes | yes | yes | yes | applied project state | generic readiness | yes for generic path | `scientific_inputs.candidates` | confirmed project candidates with import provenance | version pin/provenance incomplete | critical |
| current_pattern | yes | yes | yes | yes | yes | applied project state | generic readiness | yes | analysis units + unit parameters | confirmed project state with import provenance | snapshot metadata incomplete | critical |

Engine-disconnected before Phase 1: every versioned water dataset, every versioned economic dataset, `crop_water_parameters`, and `crop_phenology`. Candidate and current-pattern inputs already reach the generic engine, but their selected import evidence was not pinned in an analysis-run snapshot.

The integration design therefore resolves active pointers once, validates year/scope/authority/status/coverage, materializes a copied project document for `build_bundle`, records every selected dataset version, and never mutates stored source datasets. `REFERENCE_DEMO` continues to use the accepted reference path. `VERIFIED_INSTITUTIONAL` has no reference fallback.
