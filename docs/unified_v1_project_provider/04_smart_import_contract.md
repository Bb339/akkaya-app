# Smart import contract

The supported structured formats are CSV, XLSX and GeoJSON. Upload is not activation. The sequence remains upload, detection, review, validation, preview, explicit confirmation, active version and data-revision change.

Detection reports filename, extension, type, sheet names, chosen sheet, row/column counts, five preview rows, year, scope, authority, mapping, confidence, warnings and blocking issues. Deterministic aliases are normalized for case, whitespace, Turkish characters and punctuation. Low-confidence or conflicting evidence is `REVIEW_REQUIRED` or `AMBIGUOUS`.

For XLSX, every nonempty tabular sheet is scored against the same declared contracts. Cover and empty sheets are skipped. A unique best sheet is selected with recorded evidence; equal best candidates fail closed as `AMBIGUOUS`. Unsupported formats remain `UNSUPPORTED`. No scientific value is inferred or fabricated.

Existing scientific-input contracts can carry supported climate fields. Soil and remote-sensing documents have no active optimizer contract in this milestone; they remain unsupported/auxiliary and cannot silently affect a run. A future extension can add a declared dataset type, validator, readiness connection and provenance record without changing provider identity.

