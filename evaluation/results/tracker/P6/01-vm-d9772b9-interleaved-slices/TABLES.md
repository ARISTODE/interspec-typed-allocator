### rsync_popt, option_parse

15 paired repetitions of 100 interleaved slices each; unit ns. Cost is the relative increase in time per unit of work.

| Configuration | Median of the repetitions | Cost against all policies off: median (range) | Cost against RLBox-only: median (range) |
|---|---:|---:|---:|
| rlbox-only | 375.4 ms | -2.0% (-5.0 to +1.3) |  |
| interspec-all-off | 382.2 ms |  | +2.1% (-1.3 to +5.3) |
| interspec-sp1 | 378.4 ms | -0.7% (-4.9 to +1.6) | +1.7% (-3.1 to +4.0) |
| interspec-sp2 | 376.1 ms | -1.3% (-3.0 to +2.3) | +0.9% (-1.1 to +3.9) |
| interspec-sp3 | 383.3 ms | -0.0% (-3.6 to +3.9) | +2.0% (-1.6 to +6.3) |
| interspec-all-on | 382.7 ms | -0.4% (-2.8 to +5.4) | +1.6% (-0.8 to +7.4) |

### rsync_popt, file_sync_194mb

15 paired repetitions of 8 interleaved slices each; unit ns. Cost is the relative increase in time per unit of work.

| Configuration | Median of the repetitions | Cost against all policies off: median (range) | Cost against RLBox-only: median (range) |
|---|---:|---:|---:|
| rlbox-only | 10098.6 ms | +0.1% (-0.8 to +2.2) |  |
| interspec-all-off | 10072.4 ms |  | -0.1% (-2.2 to +0.8) |
| interspec-sp1 | 10052.8 ms | +0.1% (-2.1 to +2.7) | -0.5% (-2.1 to +1.4) |
| interspec-sp2 | 10036.7 ms | -0.6% (-2.6 to +2.8) | -0.3% (-2.8 to +2.6) |
| interspec-sp3 | 10044.3 ms | +0.0% (-1.9 to +2.5) | -0.1% (-1.4 to +2.4) |
| interspec-all-on | 10068.6 ms | +0.1% (-2.1 to +3.2) | +0.1% (-2.6 to +1.9) |

### yaml_libyaml, yaml_parse_1mb

15 paired repetitions of 30 interleaved slices each; unit ns. Cost is the relative increase in time per unit of work.

| Configuration | Median of the repetitions | Cost against all policies off: median (range) | Cost against RLBox-only: median (range) |
|---|---:|---:|---:|
| rlbox-only | 3639.3 ms | +2.7% (-3.4 to +12.6) |  |
| interspec-all-off | 3535.7 ms |  | -2.6% (-11.2 to +3.5) |
| interspec-sp2 | 3475.9 ms | -0.7% (-6.0 to +9.5) | -3.3% (-8.5 to +4.8) |
| interspec-sp3 | 3512.2 ms | -0.9% (-7.4 to +9.0) | -3.5% (-11.3 to +2.6) |
| interspec-all-on | 3498.3 ms | -0.7% (-5.3 to +6.4) | -2.7% (-8.8 to +1.9) |

### memcached_bipbuffer, watch_moderate

15 paired repetitions of 6 interleaved windows each; unit operations_per_s. Cost is the relative increase in time per unit of work.

| Configuration | Median of the repetitions | Cost against all policies off: median (range) | Cost against RLBox-only: median (range) |
|---|---:|---:|---:|
| rlbox-only | 101,686 | -0.2% (-3.9 to +5.7) |  |
| interspec-all-off | 102,406 |  | +0.2% (-5.4 to +4.1) |
| interspec-sp1 | 99,441 | +2.1% (-4.6 to +6.2) | +1.7% (-3.3 to +6.2) |
| interspec-sp2 | 100,722 | +0.8% (-5.0 to +3.4) | +0.6% (-3.4 to +3.2) |
| interspec-sp3 | 100,425 | +2.4% (-4.4 to +5.6) | +1.6% (-2.6 to +5.6) |
| interspec-all-on | 99,736 | +1.7% (-2.9 to +7.0) | +1.8% (-2.3 to +5.4) |

### nginx_libpcre, regex_location_4_threads

15 paired repetitions of 6 interleaved windows each; unit requests_per_s. Cost is the relative increase in time per unit of work.

| Configuration | Median of the repetitions | Cost against all policies off: median (range) | Cost against RLBox-only: median (range) |
|---|---:|---:|---:|
| rlbox-only | 68,775 | -3.6% (-12.2 to +4.7) |  |
| interspec-all-off | 66,337 |  | +3.8% (-4.5 to +13.9) |
| interspec-sp1 | 67,976 | -2.4% (-12.9 to +8.9) | +2.9% (-6.2 to +13.0) |
| interspec-sp2 | 68,775 | -3.7% (-10.3 to +8.5) | +1.4% (-5.6 to +11.8) |
| interspec-sp3 | 61,053 | +9.8% (-4.4 to +18.6) | +11.3% (+4.5 to +22.3) |
| interspec-all-on | 66,221 | +0.5% (-6.8 to +9.1) | +5.5% (-1.7 to +11.8) |

