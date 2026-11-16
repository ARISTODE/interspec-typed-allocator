# Paired throughput loss with ranges

Computed from `report/all-samples.csv` (360 rows) by `paired.py`. For each repetition the loss of
configuration X against baseline B is 1 - ops_per_s(X) / ops_per_s(B), both from the
same repetition. A cell gives the median over the 15 repetitions and, in brackets,
the smallest and largest value. Positive means X is slower. Every sample passed the
checks at the top of `paired.py`.

| Scenario | Median Kops/s: native, RLBox-only, tracking without check, InterSpec | rlbox-only against native | interspec against native | tracked-no-check against rlbox-only | interspec against rlbox-only |
|---|---|---:|---:|---:|---:|
| balanced_1c | 199.8, 201.0, 201.5, 199.4 | -0.16% (-5.87 to +6.45) | +1.57% (-8.05 to +5.98) | +0.58% (-3.98 to +8.70) | +0.17% (-6.06 to +8.90) |
| balanced_8c | 731.0, 709.3, 709.8, 701.9 | +2.80% (-1.34 to +9.43) | +4.80% (-0.26 to +6.76) | -0.65% (-3.95 to +7.54) | +0.68% (-5.43 to +5.65) |
| read_heavy_1k | 995.2, 967.7, 963.5, 946.6 | +3.14% (-2.62 to +13.02) | +7.46% (-2.75 to +9.95) | +1.52% (-6.08 to +3.46) | +2.62% (-4.89 to +8.67) |
| write_heavy | 544.5, 517.4, 519.9, 519.7 | +0.77% (-5.20 to +9.03) | +4.14% (-0.55 to +9.59) | +0.90% (-5.69 to +6.66) | +1.61% (-5.79 to +8.88) |
| watch_light | 28.1, 27.9, 27.7, 27.4 | +0.04% (-4.96 to +6.05) | +2.37% (-3.91 to +11.36) | +1.93% (-5.78 to +5.40) | +2.02% (-2.97 to +6.49) |
| watch_moderate | 86.0, 84.5, 85.3, 84.0 | +1.82% (-4.49 to +4.72) | +3.14% (-3.35 to +6.89) | +0.42% (-2.57 to +6.49) | +1.37% (-4.45 to +7.88) |
