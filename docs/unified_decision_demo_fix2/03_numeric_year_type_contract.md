# Strict structural numeric and year contract

For every required canonical field explicitly classified as structural numeric, every populated value must parse with the existing numeric parser. One malformed value produces required_numeric_field_not_parseable and REVIEW_REQUIRED. For explicit year fields, the corresponding code is explicit_year_not_parseable.

Evidence contains field, source column, populated, parseable, unparseable, and at most five unique truncated invalid examples. Empty values remain governed by existing required/import contracts. This guard does not infer scientific ranges, units, authority, agronomic plausibility, or corrections. Numeric values such as -5, 999999, and 2025.0 remain structurally parseable.
