# Crop identity and parameter identity contract

## Purpose and boundary

Runtime crop identity and scientific parameter identity are separate concepts. A runtime crop keeps its project-facing canonical id; a reviewed relation may select a differently named parameter record without renaming or merging the runtime crop. This contract does not change the candidate universe, optimizer, production crop catalog, or scientific calculations.

`CropIdentity` can record `canonical_crop_id`, `display_name`, `normalized_key`, `crop_form`, `annual_perennial`, and metadata. `IdentityRelation` records both ids, relation type, review status, evidence, source, and review note. The allowed relation types are `EXACT`, `REVIEWED_ALIAS`, `SPELLING_EQUIVALENT`, `UNICODE_EQUIVALENT`, `WORD_ORDER_EQUIVALENT`, `GRANULARITY_PARENT`, `UNRESOLVED`, and `UNSAFE_AUTO_MERGE`.

## Resolution rules

Resolution is deterministic and ordered: exact parameter identity, an explicit reviewed relation whose target exists, an explicit ambiguous granularity relation, then missing. Resolution output includes the resolved identity, method, evidence, review status, authority, pilot verification, legacy fallback status, engine connection state, and relation revision.

Nine relations are reviewed: KIMYON/KİMYON, TRTIKALEDANE/TRITIKALEDANE, SALCALIKDOMATES/DOMATESSALCALIK, SOFRALIKDOMATES/DOMATESSOFRALIK, SIVRIBIBER/BIBERSIVRI, SALCALIKBIBER/BIBERSALCALIK, SILAJLIKMISIR/MISIRSILAJLIK, KAYSI/KAYISI, and NEKTAR/NEKTARIN. Word-order matches are explicit records; the resolver never sorts arbitrary tokens.

Unicode normalization is limited to textual-equivalence checks. It normalizes encoding and combining marks but does not alter global production identities. This safely recognizes `KİMYON` and `Ki̇myon` as textual forms while preserving semantic crop variants.

KABAKBAL, KABAKCEREZLIK, and KABAKSAKIZ are explicitly ambiguous against generic KABAK and cannot be verified without crop-form-specific evidence. SOGANTAZE is `MISSING` because no defensible parameter counterpart exists. The 14 parameter-only identities remain historical parameter scope and are not added to the 58-crop runtime catalog.

The initial 58-crop result is 45 exact, 9 reviewed aliases, 3 ambiguous, and 1 missing. The reviewed layer therefore resolves 9 of the 13 historical direct-lookup failures while leaving 4 unresolved.

Future `AnalysisRun` provenance may snapshot `crop_parameter_dataset_id`, `crop_parameter_version`, `phenology_dataset_id`, `phenology_version`, and `identity_resolution_revision`. Phase 7 does not mutate existing runs.
