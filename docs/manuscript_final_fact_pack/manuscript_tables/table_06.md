# Table 6. Accepted S1 repeated-run robustness summary

| algorithm | seeds | total_water_m3_mean | total_water_m3_sd | total_water_m3_cv  | total_profit_tl_mean | total_profit_tl_sd | total_profit_tl_cv | efficiency_tl_per_m3_mean | efficiency_tl_per_m3_cv | hhi_mean           | hhi_cv             | claim_classification | active_runs | feasible_rate | runtime_mean_s     | runtime_median_s   |
| --------- | ----- | ------------------- | ----------------- | ------------------ | -------------------- | ------------------ | ------------------ | ------------------------- | ----------------------- | ------------------ | ------------------ | -------------------- | ----------- | ------------- | ------------------ | ------------------ |
| ABC       | 5     | 58142014.10940417   | 95638.83879496562 | 0.0016449178835635 | 774485014.6902525    | 1351595.5978449949 | 0.0017451539696808 | 13.320602478941543        | 0.0023735916337925      | 0.4222876984764152 | 0.0231026972798116 | SAFE WITH LIMITATION | 5           | 1.0           | 113.79004197999966 | 103.29407419999916 |
| ACO       | 5     | 58072827.74940417   | 0.0               | 0.0                | 774601807.8502525    | 0.0                | 0.0                | 13.338455141065523        | 0.0                     | 0.4293054102683873 | 0.0                | SAFE WITH LIMITATION | 5           | 1.0           | 121.93475791999882 | 116.22776739999972 |
| GA        | 5     | 59834391.05995408   | 501303.6472979396 | 0.0083781858295446 | 785215496.4384137    | 8329882.623584908  | 0.0106084032490031 | 13.12358177573405         | 0.011214897062345       | 0.3127167776960943 | 0.096824127358629  | SAFE WITH LIMITATION | 4           | 1.0           | 106.42356774999917 | 104.89306860000033 |

**Source lineage:** robustness/seed_variability.csv; run_level_results.csv

**Interpretive boundary:** CV is fractional; computational stability is not field uncertainty.
