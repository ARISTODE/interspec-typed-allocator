### ffmpeg_libvpx, variants

Workload: 352 288 12 per slice; 15 paired repetitions of 30 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against native: median (range) | Against rlbox-only: median (range) |
|---|---:|---:|---:|---:|
| native | 3182.1 | 0 |  | -9.0% (-12.4 to -2.6) |
| rlbox-only | 3398.5 | 0 | +9.9% (+2.7 to +14.2) |  |
| tracked-no-check | 3511.7 | 0 | +9.9% (+2.2 to +18.8) | +0.5% (-8.2 to +6.6) |
| interspec | 3573.3 | 48 | +12.4% (-0.6 to +21.9) | +3.0% (-10.7 to +12.3) |

### magick_libpng, variants

Workload: evaluation/parity/png/basn4a16.png 700 per slice; 15 paired repetitions of 30 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against native: median (range) | Against rlbox-only: median (range) |
|---|---:|---:|---:|---:|
| native | 3735.1 | 0 |  | +3.2% (-2.7 to +8.2) |
| rlbox-only | 3605.9 | 0 | -3.1% (-7.6 to +2.8) |  |
| tracked-no-check | 3829.5 | 0 | +3.0% (-8.3 to +7.3) | +7.0% (-9.1 to +14.4) |
| interspec | 3850.1 | 1,400 | +5.2% (-0.6 to +8.8) | +7.2% (-1.6 to +15.0) |

### memcached_hash, variants

Workload: 10000 8000000 per slice; 15 paired repetitions of 30 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against native: median (range) | Against rlbox-only: median (range) |
|---|---:|---:|---:|---:|
| native | 2161.9 | 0 |  | -56.8% (-58.9 to -54.2) |
| rlbox-only | 5025.8 | 0 | +131.7% (+118.3 to +143.2) |  |
| interspec | 4864.7 | 0 | +129.0% (+121.7 to +152.0) | +0.3% (-3.5 to +5.0) |

### memcached_hash (memcached_assoc), variants

Workload: 20000 400000 per slice; 15 paired repetitions of 30 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against native: median (range) | Against rlbox-only: median (range) |
|---|---:|---:|---:|---:|
| native | 2140.8 | 0 |  | -15.0% (-16.9 to -10.5) |
| rlbox-only | 2474.8 | 0 | +17.7% (+11.7 to +20.4) |  |
| interspec | 6781.8 | 277,994 | +213.7% (+204.6 to +225.5) | +167.2% (+153.9 to +183.5) |

### nginx_openssl, variants

Workload: 512 4096 1500 per slice; 15 paired repetitions of 30 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against native: median (range) | Against rlbox-only: median (range) |
|---|---:|---:|---:|---:|
| native | 740.9 | 0 |  | -83.2% (-83.9 to -82.6) |
| rlbox-only | 4523.0 | 0 | +496.7% (+475.6 to +523.1) |  |
| interspec | 4572.1 | 1,500 | +505.6% (+485.7 to +534.5) | +0.8% (-1.6 to +6.4) |

### ucl_libucl, variants

Workload: server.name logging.level 20000 per slice; 15 paired repetitions of 30 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against native: median (range) | Against rlbox-only: median (range) |
|---|---:|---:|---:|---:|
| native | 3023.5 | 0 |  | -17.1% (-20.7 to -12.0) |
| rlbox-only | 3623.8 | 0 | +20.6% (+13.6 to +26.1) |  |
| tracked-no-check | 3780.4 | 0 | +27.5% (+19.3 to +34.3) | +4.5% (+0.5 to +11.4) |
| interspec | 3797.3 | 60,000 | +27.9% (+19.8 to +37.2) | +4.1% (-1.8 to +18.2) |

### zip_libzip, variants

Workload: evaluation/parity/zip/test-cp437.zip 1000000 per slice; 15 paired repetitions of 30 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against native: median (range) | Against rlbox-only: median (range) |
|---|---:|---:|---:|---:|
| native | 2356.7 | 0 |  | -30.7% (-34.2 to -26.6) |
| rlbox-only | 3403.1 | 0 | +44.3% (+36.3 to +52.0) |  |
| tracked-no-check | 3328.6 | 0 | +42.1% (+31.4 to +47.8) | -2.5% (-6.5 to +5.3) |
| interspec | 4762.4 | 2,000,000 | +99.1% (+89.8 to +117.7) | +41.2% (+33.1 to +46.5) |

