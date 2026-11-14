# Paired throughput loss with ranges

Computed from `timing/samples.csv` (120 rows: 2 thread counts, 4 variants, 15 repetitions).
For each repetition the loss of X against B is 1 - requests_per_s(X) / requests_per_s(B),
both from the same repetition. A cell gives the median over the 15 repetitions and, in
brackets, the smallest and largest value. Positive means X is slower. The medians equal
those in `timing/summary.json`.

## Throughput (requests/s), loss

| Client threads | Median: native, RLBox-only, tracking without check, InterSpec | rlbox-only against native | interspec against native | tracked-no-check against rlbox-only | interspec against tracked-no-check | interspec against rlbox-only |
|---:|---|---:|---:|---:|---:|---:|
| 4 | 89,794, 72,164, 71,977, 69,108 | +19.98% (+13.84 to +28.71) | +24.38% (+19.73 to +28.60) | +1.03% (-9.82 to +9.48) | +4.18% (-6.21 to +13.08) | +5.03% (-4.12 to +12.05) |
| 8 | 79,399, 65,469, 67,048, 61,499 | +18.56% (+11.06 to +34.04) | +22.56% (+16.31 to +26.89) | -1.47% (-22.73 to +2.87) | +7.68% (-4.23 to +11.56) | +4.87% (-11.54 to +12.27) |

## Server CPU time per request (microseconds), increase

| Client threads | Median: native, RLBox-only, tracking without check, InterSpec | rlbox-only against native | interspec against native | tracked-no-check against rlbox-only | interspec against tracked-no-check | interspec against rlbox-only |
|---:|---|---:|---:|---:|---:|---:|
| 4 | 11.03, 13.76, 13.78, 14.33 | +25.04% (+15.85 to +40.41) | +32.34% (+24.31 to +40.02) | +0.64% (-9.13 to +10.79) | +4.10% (-6.10 to +14.90) | +5.19% (-4.24 to +13.72) |
| 8 | 12.50, 15.18, 14.81, 16.13 | +23.09% (+12.37 to +52.58) | +29.37% (+19.83 to +37.19) | -1.09% (-18.87 to +3.09) | +8.28% (-4.22 to +13.62) | +5.10% (-10.44 to +14.77) |
