### ffmpeg_libvpx, policies

Workload: 352 288 12 per slice; 15 paired repetitions of 30 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against rlbox-only: median (range) | Against interspec-all-off: median (range) |
|---|---:|---:|---:|---:|
| rlbox-only | 3574.6 | 0 |  | -1.3% (-6.4 to +10.0) |
| interspec-all-off | 3576.3 | 0 | +1.3% (-9.1 to +6.8) |  |
| interspec-sp1 | 3595.3 | 0 | +0.1% (-7.5 to +8.5) | +0.2% (-6.9 to +8.7) |
| interspec-sp2 | 3469.4 | 0 | +0.8% (-6.3 to +8.9) | +1.4% (-6.5 to +9.9) |
| interspec-sp3 | 3618.6 | 48 | +1.8% (-7.7 to +9.4) | +1.0% (-6.6 to +6.4) |
| interspec-all-on | 3492.5 | 48 | +0.1% (-9.8 to +6.3) | -1.4% (-5.3 to +7.2) |

### magick_libpng, policies

Workload: evaluation/parity/png/basn4a16.png 700 per slice; 15 paired repetitions of 30 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against rlbox-only: median (range) | Against interspec-all-off: median (range) |
|---|---:|---:|---:|---:|
| rlbox-only | 4171.9 | 0 |  | -6.2% (-11.9 to +1.5) |
| interspec-all-off | 4417.3 | 0 | +6.6% (-1.5 to +13.5) |  |
| interspec-sp1 | 4480.1 | 0 | +7.2% (-3.6 to +15.1) | -0.0% (-3.8 to +3.5) |
| interspec-sp2 | 4475.4 | 0 | +7.5% (-2.4 to +11.2) | -0.1% (-5.5 to +6.2) |
| interspec-sp3 | 4324.7 | 1,400 | +7.0% (-7.3 to +14.8) | -1.1% (-6.4 to +5.7) |
| interspec-all-on | 4386.0 | 1,400 | +4.7% (-3.2 to +11.5) | -1.8% (-4.6 to +4.7) |

### memcached_hash, policies

Workload: 10000 8000000 per slice; 15 paired repetitions of 30 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against rlbox-only: median (range) | Against interspec-all-off: median (range) |
|---|---:|---:|---:|---:|
| rlbox-only | 4792.2 | 0 |  | -8.2% (-11.2 to -3.0) |
| interspec-all-off | 5169.2 | 0 | +8.9% (+3.1 to +12.6) |  |
| interspec-sp1 | 5172.6 | 0 | +7.9% (+3.5 to +11.6) | -0.0% (-4.4 to +7.9) |
| interspec-sp2 | 4883.6 | 0 | -0.1% (-5.2 to +5.4) | -7.2% (-14.1 to -4.0) |
| interspec-sp3 | 5184.8 | 0 | +9.0% (+2.6 to +11.6) | +0.1% (-3.6 to +6.3) |
| interspec-all-on | 4798.9 | 0 | +0.5% (-2.4 to +3.0) | -6.3% (-13.3 to -2.8) |

### memcached_hash (memcached_assoc), policies

Workload: 20000 400000 per slice; 15 paired repetitions of 30 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against rlbox-only: median (range) | Against interspec-all-off: median (range) |
|---|---:|---:|---:|---:|
| rlbox-only | 2468.7 | 0 |  | -9.3% (-15.8 to -0.8) |
| interspec-all-off | 2730.3 | 0 | +10.3% (+0.8 to +18.8) |  |
| interspec-sp1 | 2560.1 | 0 | +3.3% (-2.7 to +9.0) | -6.2% (-12.7 to -1.0) |
| interspec-sp2 | 2658.5 | 0 | +7.6% (+0.2 to +15.4) | -1.8% (-6.7 to +3.8) |
| interspec-sp3 | 6865.7 | 277,994 | +183.3% (+154.0 to +193.9) | +155.8% (+144.5 to +163.2) |
| interspec-all-on | 6552.9 | 277,994 | +170.1% (+147.1 to +183.2) | +143.2% (+132.2 to +156.9) |

### nginx_openssl, policies

Workload: 512 4096 1500 per slice; 15 paired repetitions of 30 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against rlbox-only: median (range) | Against interspec-all-off: median (range) |
|---|---:|---:|---:|---:|
| rlbox-only | 4493.5 | 0 |  | -0.6% (-4.7 to +3.8) |
| interspec-all-off | 4522.9 | 0 | +0.6% (-3.6 to +4.9) |  |
| interspec-sp1 | 4564.8 | 0 | +1.2% (-2.0 to +4.5) | +1.1% (-2.7 to +3.5) |
| interspec-sp2 | 4533.5 | 0 | +0.7% (-2.9 to +4.9) | -0.1% (-2.9 to +6.3) |
| interspec-sp3 | 4525.8 | 1,500 | +0.5% (-2.1 to +3.3) | -0.0% (-4.3 to +2.9) |
| interspec-all-on | 4501.3 | 1,500 | +0.5% (-3.9 to +4.1) | -0.4% (-5.9 to +7.7) |

### ucl_libucl, policies

Workload: server.name logging.level 20000 per slice; 15 paired repetitions of 30 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against rlbox-only: median (range) | Against interspec-all-off: median (range) |
|---|---:|---:|---:|---:|
| rlbox-only | 3910.4 | 0 |  | -5.1% (-9.9 to +2.7) |
| interspec-all-off | 4148.3 | 0 | +5.4% (-2.6 to +10.9) |  |
| interspec-sp1 | 4097.3 | 0 | +5.0% (-8.1 to +14.8) | -2.2% (-6.5 to +9.8) |
| interspec-sp2 | 4037.9 | 0 | +3.4% (-4.6 to +10.9) | -2.7% (-10.1 to +6.5) |
| interspec-sp3 | 4073.2 | 60,000 | +6.8% (-8.0 to +10.9) | +0.6% (-10.0 to +5.5) |
| interspec-all-on | 4158.3 | 60,000 | +5.4% (-3.0 to +12.9) | +0.5% (-5.6 to +5.5) |

### zip_libzip, policies

Workload: evaluation/parity/zip/test-cp437.zip 1000000 per slice; 15 paired repetitions of 30 interleaved slices each; CPU 0.

| Configuration | Median time of a repetition (ms) | Checks per slice | Against rlbox-only: median (range) | Against interspec-all-off: median (range) |
|---|---:|---:|---:|---:|
| rlbox-only | 3532.4 | 0 |  | -9.9% (-14.9 to -6.8) |
| interspec-all-off | 3887.0 | 0 | +11.0% (+7.3 to +17.6) |  |
| interspec-sp1 | 3926.9 | 0 | +10.2% (+8.6 to +16.7) | +0.6% (-4.3 to +6.0) |
| interspec-sp2 | 3875.4 | 0 | +10.5% (+2.5 to +18.9) | -0.4% (-5.3 to +4.1) |
| interspec-sp3 | 5020.7 | 2,000,000 | +41.9% (+30.0 to +53.9) | +30.2% (+20.0 to +33.4) |
| interspec-all-on | 5005.0 | 2,000,000 | +42.0% (+36.9 to +51.0) | +27.7% (+20.4 to +35.5) |

