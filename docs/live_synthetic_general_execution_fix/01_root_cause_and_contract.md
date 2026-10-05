# Live synthetic general execution corrective fix

Baseline: `91d07d9e1ffa65d56772c85993fe2f9285b80110`

## Root cause

The `/projects` form submits `data_source_notes=synthetic_test_fixture` for the exact visible choice **Sentetik genel proje**. Project persistence previously attached the canonical synthetic-demo metadata only when `data_source_notes` exactly equalled `synthetic not_official institutional integration fixture`. The overview layer separately recognized the shorter UI value, so the banner looked synthetic while readiness treated the project as an ordinary institutional project and rejected every synthetic authority input.

## Corrected boundary

Project creation now recognizes exactly two explicit synthetic-demo classifications: the pre-existing canonical fixture string and the exact UI value `synthetic_test_fixture`. Either exact value persists the existing canonical metadata:

```json
{
  "synthetic_institutional_test": true,
  "not_official": true,
  "display_labels": ["SYNTHETIC", "NOT_OFFICIAL"]
}
```

Similar free text is not recognized. `user_provided` projects remain ordinary institutional projects. Readiness, optimization, scientific calculations, datasets, reference values, and rendering are unchanged.

For a synthetic project, the visible PROJECT_DATA authority label is exactly `SYNTHETIC / NOT_OFFICIAL`; it does not append the internal adapter execution-profile name. The technical execution profile remains available in provenance and does not change the result authority or classification.

## Existing projects

No migration is performed. A project created before this fix with `data_source_notes=synthetic_test_fixture` but without the canonical metadata remains fail-closed. It must be recreated after deployment with the exact **Sentetik genel proje** choice. This avoids silently reclassifying an institutional project.
