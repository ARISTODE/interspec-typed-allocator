### memcached_hash (memcached_assoc), variants

Workload: 20000 400000 per slice; 15 paired repetitions of 30 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against native: median (range) | Against rlbox-only: median (range) |
|---|---:|---:|---:|---:|
| native | 2101.1 | 0 |  | -14.8% (-20.9 to -11.5) |
| rlbox-only | 2482.4 | 0 | +17.4% (+12.9 to +26.5) |  |
| tracked-no-check | 4404.6 | 0 | +110.9% (+99.8 to +116.5) | +76.2% (+68.4 to +91.2) |
| interspec | 6610.9 | 277,994 | +211.9% (+204.0 to +225.2) | +168.5% (+140.4 to +174.8) |

### nginx_openssl, variants

Workload: 512 4096 1500 per slice; 15 paired repetitions of 30 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against native: median (range) | Against rlbox-only: median (range) |
|---|---:|---:|---:|---:|
| native | 700.7 | 0 |  | -83.7% (-84.3 to -82.9) |
| rlbox-only | 4302.0 | 0 | +512.8% (+485.5 to +535.9) |  |
| tracked-no-check | 4288.4 | 0 | +505.2% (+483.5 to +534.4) | -0.9% (-3.3 to +3.7) |
| interspec | 4317.3 | 1,500 | +512.3% (+484.9 to +554.5) | +0.5% (-2.8 to +4.3) |

