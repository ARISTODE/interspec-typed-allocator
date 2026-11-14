# Paired throughput loss with ranges

Computed from `report/all-samples.csv` (360 rows). For each repetition the loss of
configuration X against baseline B is 1 - ops_per_s(X) / ops_per_s(B), both from the
same repetition. A cell gives the median over the 15 repetitions and, in brackets,
the smallest and largest value. Positive means X is slower. The medians equal those
in `report/FINAL_TABLE.md`.

| Scenario | Median Kops/s: native, RLBox-only, tracking without check, InterSpec | rlbox-only against native | interspec against native | tracked-no-check against rlbox-only | interspec against rlbox-only |
|---|---|---:|---:|---:|---:|
| balanced_1c | 225.9, 228.3, 220.4, 227.1 | +1.24% (-11.38 to +10.01) | +1.40% (-10.76 to +10.49) | +1.22% (-8.25 to +10.69) | +0.54% (-5.24 to +4.73) |
| balanced_8c | 791.0, 774.9, 754.6, 765.9 | +2.48% (-3.75 to +12.76) | +3.78% (-2.08 to +6.91) | +1.89% (-9.30 to +6.39) | +0.28% (-8.39 to +8.01) |
| read_heavy_1k | 1184.2, 1125.2, 1109.8, 1095.6 | +5.68% (+0.55 to +10.54) | +7.43% (+3.72 to +12.02) | +1.78% (-7.88 to +9.56) | +1.66% (-5.40 to +8.34) |
| write_heavy | 614.0, 597.9, 593.9, 587.3 | +2.39% (-3.02 to +9.04) | +2.75% (-3.94 to +9.49) | +0.38% (-7.02 to +4.35) | +0.27% (-6.92 to +7.72) |
| watch_light | 30.4, 30.7, 30.1, 30.6 | -0.85% (-6.65 to +6.15) | -0.27% (-4.83 to +9.01) | +1.46% (-2.66 to +7.31) | +1.13% (-7.00 to +10.33) |
| watch_moderate | 106.0, 102.2, 101.3, 101.3 | +2.72% (-6.07 to +12.60) | +3.90% (-12.05 to +12.53) | -0.73% (-4.58 to +4.47) | +1.03% (-8.12 to +5.83) |
