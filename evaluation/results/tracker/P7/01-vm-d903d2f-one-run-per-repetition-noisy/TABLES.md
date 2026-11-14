### ffmpeg_libvpx, variants

Workload: 352 288 90 per slice; 15 paired repetitions of 1 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against native: median (range) | Against rlbox-only: median (range) |
|---|---:|---:|---:|---:|
| native | 840.5 | 0 |  | -6.8% (-30.3 to +11.4) |
| rlbox-only | 876.7 | 0 | +7.4% (-10.2 to +43.4) |  |
| tracked-no-check | 884.3 | 0 | +4.0% (-9.4 to +22.4) | -0.7% (-19.7 to +13.2) |
| interspec | 850.3 | 360 | +3.0% (-16.2 to +24.6) | +1.8% (-34.5 to +19.3) |

### magick_libpng, variants

Workload: evaluation/parity/png/basn4a16.png 5000 per slice; 15 paired repetitions of 1 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against native: median (range) | Against rlbox-only: median (range) |
|---|---:|---:|---:|---:|
| native | 948.3 | 0 |  | +16.7% (-32.8 to +50.8) |
| rlbox-only | 832.8 | 0 | -14.3% (-33.7 to +48.8) |  |
| tracked-no-check | 938.1 | 0 | -4.7% (-33.9 to +49.2) | +6.0% (-14.7 to +30.6) |
| interspec | 897.5 | 10,000 | +2.6% (-36.6 to +26.5) | +17.1% (-25.7 to +44.7) |

### memcached_hash, variants

Workload: 10000 50000000 per slice; 15 paired repetitions of 1 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against native: median (range) | Against rlbox-only: median (range) |
|---|---:|---:|---:|---:|
| native | 367.9 | 0 |  | -60.7% (-66.1 to -42.9) |
| rlbox-only | 936.7 | 0 | +154.6% (+75.0 to +195.2) |  |
| interspec | 941.9 | 0 | +146.1% (+97.7 to +180.9) | -3.3% (-18.5 to +13.0) |

### memcached_hash (memcached_assoc), variants

Workload: 20000 3000000 per slice; 15 paired repetitions of 1 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against native: median (range) | Against rlbox-only: median (range) |
|---|---:|---:|---:|---:|
| native | 519.2 | 0 |  | -11.8% (-29.4 to +7.4) |
| rlbox-only | 583.5 | 0 | +13.4% (-6.9 to +41.6) |  |
| interspec | 1737.5 | 2,228,228 | +239.7% (+187.9 to +275.7) | +195.9% (+160.5 to +278.5) |

### nginx_openssl, variants

Workload: 512 4096 5000 per slice; 15 paired repetitions of 1 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against native: median (range) | Against rlbox-only: median (range) |
|---|---:|---:|---:|---:|
| native | 78.1 | 0 |  | -84.2% (-87.0 to -76.8) |
| rlbox-only | 463.7 | 0 | +532.3% (+330.9 to +670.4) |  |
| interspec | 497.2 | 5,000 | +502.6% (+394.2 to +696.4) | +3.6% (-19.6 to +24.1) |

### ucl_libucl, variants

Workload: server.name logging.level 150000 per slice; 15 paired repetitions of 1 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against native: median (range) | Against rlbox-only: median (range) |
|---|---:|---:|---:|---:|
| native | 710.0 | 0 |  | -20.9% (-40.2 to +16.3) |
| rlbox-only | 954.1 | 0 | +26.4% (-14.0 to +67.3) |  |
| tracked-no-check | 940.0 | 0 | +28.1% (-28.3 to +135.7) | +5.0% (-24.9 to +88.4) |
| interspec | 972.2 | 450,000 | +36.7% (-7.1 to +87.0) | +9.1% (-31.0 to +59.0) |

### zip_libzip, variants

Workload: evaluation/parity/zip/test-cp437.zip 6000000 per slice; 15 paired repetitions of 1 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against native: median (range) | Against rlbox-only: median (range) |
|---|---:|---:|---:|---:|
| native | 517.7 | 0 |  | -29.0% (-41.7 to +1.8) |
| rlbox-only | 710.1 | 0 | +40.9% (-1.7 to +71.6) |  |
| tracked-no-check | 722.5 | 0 | +37.5% (+5.7 to +70.5) | +1.2% (-26.5 to +38.7) |
| interspec | 1002.5 | 12,000,000 | +94.2% (+39.8 to +198.1) | +42.8% (+8.9 to +100.2) |

