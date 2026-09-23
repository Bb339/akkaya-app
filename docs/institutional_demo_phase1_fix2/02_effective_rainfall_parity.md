# Effective rainfall parity

`kds.science.institutional_water.effective_rain_scs_mm` delegates directly to the accepted `app._effective_rain_scs_mm` USDA-SCS implementation. No institutional coefficient or forked approximation remains.

Exact parity is tested at 25, 100, 250, 251, and 400 mm. Crop demand applies the accepted monthly effective rainfall across the actual days in each calendar month. Conveyance is applied afterward as `gross = net / efficiency`.
