### ffmpeg_libvpx, variants

Workload: 352 288 12 per slice; 15 paired repetitions of 30 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against native: median (range) | Against rlbox-only: median (range) |
|---|---:|---:|---:|---:|
| native | 3718.1 | 0 |  | -9.6% (-17.9 to -2.5) |
| rlbox-only | 3993.7 | 0 | +10.7% (+2.6 to +21.7) |  |
| tracked-no-check | 4140.6 | 0 | +11.9% (+5.6 to +25.2) | +0.9% (-1.9 to +8.2) |
| interspec | 4073.9 | 48 | +13.0% (+5.1 to +21.6) | +1.9% (-4.9 to +9.9) |

### magick_libpng, variants

Workload: evaluation/parity/png/basn4a16.png 700 per slice; 15 paired repetitions of 30 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against native: median (range) | Against rlbox-only: median (range) |
|---|---:|---:|---:|---:|
| native | 4100.4 | 0 |  | +3.4% (-6.4 to +7.1) |
| rlbox-only | 3940.0 | 0 | -3.3% (-6.7 to +6.9) |  |
| tracked-no-check | 4151.9 | 0 | +1.8% (-4.2 to +11.0) | +5.4% (-6.2 to +17.9) |
| interspec | 4291.1 | 1,400 | +5.5% (+0.1 to +12.2) | +7.3% (+3.7 to +14.1) |

### memcached_hash, variants

Workload: 10000 8000000 per slice; 15 paired repetitions of 30 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against native: median (range) | Against rlbox-only: median (range) |
|---|---:|---:|---:|---:|
| native | 2219.4 | 0 |  | -60.9% (-62.1 to -59.1) |
| rlbox-only | 5559.8 | 0 | +155.7% (+144.7 to +163.8) |  |
| interspec | 5198.2 | 0 | +136.8% (+124.5 to +146.1) | -7.5% (-9.7 to -4.1) |

### memcached_hash (memcached_assoc), variants

Workload: 20000 400000 per slice; 15 paired repetitions of 30 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against native: median (range) | Against rlbox-only: median (range) |
|---|---:|---:|---:|---:|
| native | 2242.7 | 0 |  | -21.6% (-23.9 to -18.6) |
| rlbox-only | 2854.4 | 0 | +27.6% (+22.8 to +31.4) |  |
| tracked-no-check | 4630.0 | 0 | +106.2% (+96.8 to +112.6) | +61.7% (+57.6 to +65.9) |
| interspec | 7073.2 | 277,994 | +212.6% (+204.7 to +222.3) | +146.7% (+135.7 to +153.3) |

### nginx_openssl, variants

Workload: 512 4096 1500 per slice; 15 paired repetitions of 30 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against native: median (range) | Against rlbox-only: median (range) |
|---|---:|---:|---:|---:|
| native | 781.0 | 0 |  | -83.4% (-84.5 to -82.9) |
| rlbox-only | 4783.2 | 0 | +504.2% (+485.0 to +543.8) |  |
| tracked-no-check | 4770.0 | 0 | +506.8% (+470.7 to +538.7) | +0.1% (-5.7 to +4.8) |
| interspec | 4766.2 | 1,500 | +510.5% (+494.3 to +539.8) | -0.4% (-1.9 to +3.2) |

### ucl_libucl, variants

Workload: server.name logging.level 20000 per slice; 15 paired repetitions of 30 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against native: median (range) | Against rlbox-only: median (range) |
|---|---:|---:|---:|---:|
| native | 3049.6 | 0 |  | -18.2% (-26.2 to -14.8) |
| rlbox-only | 3726.6 | 0 | +22.3% (+17.4 to +35.5) |  |
| tracked-no-check | 3934.6 | 0 | +29.3% (+22.5 to +36.5) | +5.2% (-0.3 to +8.2) |
| interspec | 4009.3 | 60,000 | +30.6% (+19.8 to +48.2) | +7.4% (-0.8 to +12.3) |

### zip_libzip, variants

Workload: evaluation/parity/zip/test-cp437.zip 1000000 per slice; 15 paired repetitions of 30 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against native: median (range) | Against rlbox-only: median (range) |
|---|---:|---:|---:|---:|
| native | 2523.7 | 0 |  | -30.5% (-33.6 to -27.1) |
| rlbox-only | 3616.3 | 0 | +43.8% (+37.1 to +50.5) |  |
| tracked-no-check | 3552.2 | 0 | +40.9% (+38.8 to +57.1) | -1.7% (-6.9 to +4.6) |
| interspec | 5095.1 | 2,000,000 | +104.2% (+95.2 to +120.5) | +42.9% (+35.1 to +52.7) |

