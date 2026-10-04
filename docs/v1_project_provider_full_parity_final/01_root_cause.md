# Root cause

At baseline `81ad486e3bbd049b1c98f53eeef1384d464029c9`, the PROJECT_DATA backend path already produced a pinned preview and immutable stored run, but the V1 presentation pipeline still expected reference-era `parcelData`, `basinPlanCache`, `/api/parcels`, `/api/optimize`, and Akkaya-oriented chart inputs. The project provider rendered some stored values in a provider-specific section, while native water, profit, monthly-water, benchmark, map popup, unit, rationale, and metadata surfaces remained empty or reference-shaped.

The fix keeps the accepted backend and science intact. `v1-provider.js` now adapts backend-authoritative decision-context and stored-run values into the existing V1 DOM and Chart.js surfaces. It never derives scientific values in the browser and never falls back to Akkaya in PROJECT_DATA mode.
