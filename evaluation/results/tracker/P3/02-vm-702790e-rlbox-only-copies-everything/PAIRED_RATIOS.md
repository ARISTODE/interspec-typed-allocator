# Paired throughput loss with ranges

Computed from `timing/samples.csv` (120 rows: 2 thread counts, 4 variants, 15 repetitions) by `paired.py`.
For each repetition the loss of X against B is 1 - requests_per_s(X) / requests_per_s(B),
both from the same repetition. A cell gives the median over the repetitions and, in
brackets, the smallest and largest value. Positive means X is slower. Every window
passed the checks at the top of `paired.py`.

## Throughput (requests/s), loss

| Client threads | Median: native, RLBox-only, tracking without check, InterSpec | rlbox-only against native | interspec against native | tracked-no-check against rlbox-only | interspec against tracked-no-check | interspec against rlbox-only |
|---:|---|---:|---:|---:|---:|---:|
| 4 | 79,018, 63,952, 64,411, 62,566 | +19.93% (+15.99 to +26.26) | +22.86% (+12.71 to +29.12) | -0.47% (-10.82 to +8.19) | +2.25% (-3.81 to +11.17) | +3.29% (-9.25 to +9.91) |
| 8 | 79,585, 61,087, 63,015, 60,659 | +22.06% (+9.41 to +27.14) | +22.08% (+17.32 to +26.92) | -1.42% (-7.75 to +4.32) | +1.77% (-3.89 to +10.72) | +0.54% (-6.95 to +12.18) |

## Server CPU time per request (microseconds), increase

| Client threads | Median: native, RLBox-only, tracking without check, InterSpec | rlbox-only against native | interspec against native | tracked-no-check against rlbox-only | interspec against tracked-no-check | interspec against rlbox-only |
|---:|---|---:|---:|---:|---:|---:|
| 4 | 12.51, 15.52, 15.35, 15.88 | +24.82% (+18.99 to +36.00) | +29.78% (+14.17 to +41.57) | -0.39% (-9.60 to +8.93) | +2.96% (-4.00 to +12.81) | +3.14% (-8.53 to +11.45) |
| 8 | 12.49, 16.21, 15.78, 16.35 | +28.44% (+10.53 to +36.57) | +28.29% (+21.04 to +36.94) | -1.50% (-7.33 to +4.43) | +1.42% (-3.97 to +11.74) | -0.26% (-6.06 to +14.28) |

## Repetitions in which InterSpec is slower than RLBox-only

- 4 client threads: 9 of 15
- 8 client threads: 8 of 15
