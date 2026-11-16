# Paired throughput loss with ranges

Computed from `report/all-samples.csv` (360 rows) by `paired.py`. For each repetition the loss of
configuration X against baseline B is 1 - ops_per_s(X) / ops_per_s(B), both from the
same repetition. A cell gives the median over the 15 repetitions and, in brackets,
the smallest and largest value. Positive means X is slower. Every sample passed the
checks at the top of `paired.py`.

| Scenario | Median Kops/s: native, RLBox-only, tracking without check, InterSpec | rlbox-only against native | interspec against native | tracked-no-check against rlbox-only | interspec against rlbox-only |
|---|---|---:|---:|---:|---:|
| balanced_1c | 184.6, 179.1, 181.7, 178.5 | +3.20% (-1.46 to +8.34) | +2.41% (-3.83 to +6.03) | -1.31% (-9.56 to +3.70) | -0.90% (-6.79 to +5.98) |
| balanced_8c | 645.4, 610.1, 620.3, 609.2 | +4.58% (-3.84 to +10.42) | +4.25% (-2.03 to +12.82) | -0.13% (-4.41 to +3.96) | +1.91% (-5.12 to +5.95) |
| read_heavy_1k | 947.9, 887.4, 889.3, 879.2 | +6.32% (+1.30 to +10.56) | +7.75% (+3.67 to +12.29) | +0.23% (-5.97 to +6.47) | +1.94% (-6.68 to +5.00) |
| write_heavy | 488.8, 467.2, 474.6, 472.8 | +3.61% (-6.74 to +10.45) | +3.22% (-5.75 to +7.72) | +0.27% (-9.02 to +3.46) | +0.30% (-8.69 to +4.17) |
| watch_light | 24.9, 24.8, 24.6, 24.7 | -0.12% (-10.32 to +5.26) | +1.68% (-6.67 to +4.13) | +0.56% (-4.46 to +5.59) | +0.28% (-4.90 to +4.48) |
| watch_moderate | 87.1, 88.0, 86.4, 85.1 | +1.05% (-3.21 to +6.49) | +3.02% (-2.12 to +6.77) | +1.22% (-6.21 to +7.52) | +1.29% (-4.70 to +5.84) |
