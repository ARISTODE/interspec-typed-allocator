# Memcached performance overhead study

## End-to-end overhead

Positive percentages mean lower throughput. All overheads are paired by repetition. Lossy watcher runs are not valid overhead measurements.

| Scenario | Native Kops/s | RLBox Kops/s | RLBox Δ native | InterSpec Kops/s | InterSpec Δ native | InterSpec Δ RLBox | p99 N/R/I µs | Loss-free |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| balanced_1c | 143.7 | 138.2 | +3.24% | 141.2 | +1.34% | -2.14% | 82.4/85.7/84.4 | yes |
| balanced_8c | 650.7 | 662.8 | +0.20% | 641.5 | +1.42% | +1.22% | 304.6/314.1/328.6 | yes |
| read_heavy_1k | 897.3 | 839.3 | +6.47% | 809.6 | +10.00% | +0.02% | 448.7/491.6/507.5 | yes |
| write_heavy | 565.7 | 576.1 | -2.89% | 558.8 | -0.54% | +3.00% | 304.0/293.4/318.9 | yes |
| watch_light | 18.3 | 18.4 | -2.77% | 18.4 | -0.66% | +0.11% | 69.0/70.0/70.5 | yes |
| watch_moderate | 75.1 | 72.3 | +3.06% | 73.4 | +2.80% | +0.85% | 79.5/81.8/82.5 | yes |

## SP3 primitive microbenchmark

| Primitive | Population | Median ns/op | Min–max ns/op |
| --- | ---: | ---: | ---: |
| allocate_from_site | 16384 | 76.50 | 74.64–80.45 |
| bounds_check | 2 | 1.64 | 1.54–1.75 |
| check_interior | 2 | 11.94 | 11.89–12.01 |
| check_live | 2 | 11.66 | 11.55–11.80 |
| metadata_lookup | 2 | 4.45 | 4.32–4.48 |
| release | 16384 | 38.91 | 37.95–40.19 |
| remaining_bytes | 2 | 11.87 | 11.85–11.90 |
| shared_lock | 2 | 8.45 | 7.83–8.90 |
| type_compare | 2 | 1.54 | 1.54–1.65 |

## Correlating checks with application overhead

The direct production Runtime::check cost used below is 11.66 ns/check at population 2. The estimate is checks/op × this microbenchmark cost; it intentionally excludes RLBox transitions, byte copies, queue synchronization, and other application work.

| Scenario | Client ops profiled | SP3 checks | Checks/op | Checks/1k ops | Estimated direct check ns/client op |
| --- | ---: | ---: | ---: | ---: | ---: |
| balanced_1c | 1000 | 50 | 0.0500 | 50.0 | 0.58 |
| balanced_8c | 1000 | 56 | 0.0560 | 56.0 | 0.65 |
| read_heavy_1k | 1000 | 718 | 0.7180 | 718.0 | 8.37 |
| write_heavy | 1000 | 0 | 0.0000 | 0.0 | unavailable (path not observed) |
| watch_light | 1000 | 6081 | 6.0810 | 6081.0 | 70.90 |
| watch_moderate | 1000 | 6076 | 6.0760 | 6076.0 | 70.85 |

A zero observed check count is retained as a coverage gap and is excluded from the cost correlation. It does not establish zero enforcement cost for that workload.

Interpretation: the microbenchmark establishes the cost of one metadata validation, while the fixed-operation profiler establishes how frequently real memcached paths invoke it. The end-to-end table then measures the actual aggregate effect. The estimate should explain direction and scale, not exactly equal the throughput delta, because checks execute concurrently and interact with sandbox transitions, copies, locks, cache effects, batching, and background logger/LRU work.
