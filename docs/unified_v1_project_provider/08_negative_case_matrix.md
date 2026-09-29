# Negative-case matrix

| Case | Expected behavior |
|---|---|
| Missing/duplicate/malformed project query | Visible fail-closed error; no reference fallback |
| Unknown project/run | API error bound to exact project; execution disabled |
| Duplicate analysis-unit identity | Projection rejected |
| Missing required dataset | Readiness blocks preview/run |
| Real project with synthetic fixture authority | `VERIFIED_INSTITUTIONAL` remains blocked |
| Wrong explicit year/scope | `REVIEW_REQUIRED` |
| Missing required column or malformed numeric | `REVIEW_REQUIRED` |
| Equal type/sheet evidence | `AMBIGUOUS` |
| Unsupported PDF/DOCX | `UNSUPPORTED` |
| Invalid GeoJSON | `INVALID` |
| Partial/no geometry | Analysis remains available; explicit map status; no fabrication |
| Provider/project switch | Old preview, run and unit state discarded |

