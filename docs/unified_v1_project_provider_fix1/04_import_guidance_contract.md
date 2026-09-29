# Smart Import Turkish guidance contract

Detector states, codes and raw messages remain unchanged. `imports.js` maps known issue codes to deterministic presentation-only Turkish guidance with two primary prompts: **Ne oldu?** and **Ne yapmalısınız?**

Covered issues include missing required fields, malformed numeric/year values, wrong planning year/scope, ambiguous mapping/type/workbook sheet, unsupported extensions, invalid files/GeoJSON, invalid or duplicate geometry and unknown geometry unit IDs.

Each bulk row retains filename, detected domain, year, scope, row count, mapping coverage, authority and validation state. Expanded preview shows sheet selection, columns, the first five rows, proposed mapping, Turkish guidance and secondary technical JSON.

An irrelevant structured file is not assigned a new scientific type. The verified case remains `AMBIGUOUS` and blocks bulk confirmation. A definitive geometry/unit mismatch remains invalid and blocks confirmation.
