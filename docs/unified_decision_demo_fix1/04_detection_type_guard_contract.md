# Detection Structural Type Guard Contract

`AUTO_MATCHED` means **structurally recognized with deterministic evidence**. It does not mean scientifically valid, officially approved, field validated, Ministry data, or trusted without explicit confirmation.

The guard applies only to canonical required fields whose contracts make a numeric representation unambiguous. It checks area, explicit year fields, amounts/capacities, generic economic quantities, candidate water/profit/yield quantities, efficiency and crop-parameter numeric fields. The generic `value` field is checked only for `environmental_release` and `perennial_irrigation_requirement`; mixed-type `scientific_inputs.value` is deliberately excluded.

Rules:

- an explicit required year field with populated values but no parseable numeric year produces `explicit_year_not_parseable`;
- a required numeric field whose populated values are at least half unparseable produces `required_numeric_field_not_parseable`;
- these issues produce `REVIEW_REQUIRED`;
- decimal strings using a dot or a single comma are structurally parseable;
- no range, agronomic threshold, authority inference, unit conversion or scientific truth test is performed.

Existing missing, ambiguous, wrong-year, wrong-scope, unsupported and invalid precedence remains fail closed. Upload creates only an unconfirmed batch; explicit confirmation remains mandatory.
