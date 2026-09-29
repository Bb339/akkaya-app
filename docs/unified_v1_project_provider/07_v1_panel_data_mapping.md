# V1 panel data mapping

| V1 surface | Project source/state |
|---|---|
| Provider strip | project metadata, revision, classification, execution profile |
| Parcel selector/detail | confirmed `analysis_units`; current crop and area are input data |
| Map | project geometry/coordinates only |
| Scenario/algorithm/objective/seed | backend preview and analysis request |
| Requirement cards | readiness projection |
| Summary metrics | stored backend result and presentation summary |
| Crop composition and HHI | stored `crop_shares`/HHI, otherwise Not Provided |
| Monthly water | stored monthly supply/delivery/accounting, otherwise Not Provided |
| Unit result | stored `presentation_units`; distinct from current input crop |
| Provenance | project/revision/run/config/selection hash/engine commit/authority |
| History | immutable project run history |

Cards use available, not provided/not applicable, or blocked states. The adapter performs display formatting only.

