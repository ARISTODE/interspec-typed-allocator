# Memcached performance overhead study

## End-to-end overhead

Positive percentages mean lower throughput. All overheads are paired by repetition. Lossy watcher runs are not valid overhead measurements.

| Scenario | Native Kops/s | RLBox Kops/s | RLBox Δ native | InterSpec Kops/s | InterSpec Δ native | InterSpec Δ RLBox | p99 N/R/I µs | Loss-free |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| balanced_1c | 144.9 | 147.9 | -2.93% | 143.4 | +0.51% | +1.47% | 82.3/82.7/83.4 | yes |
| balanced_8c | 689.1 | 692.4 | +1.15% | 675.0 | +2.10% | +2.45% | 293.0/315.7/312.0 | yes |
| read_heavy_1k | 880.9 | 866.2 | +1.68% | 840.4 | +4.50% | +2.77% | 468.5/477.4/467.9 | yes |
| write_heavy | 584.4 | 584.3 | +0.03% | 574.3 | +0.26% | +2.05% | 288.2/284.1/294.2 | yes |
| watch_light | 19.0 | 18.8 | +1.70% | 18.8 | +0.76% | -0.75% | 67.0/68.1/68.7 | yes |
| watch_moderate | 76.5 | 75.1 | +1.58% | 73.2 | +4.50% | +1.57% | 81.4/83.1/84.7 | yes |

## Allocation tracking decomposition

All variants share the same experiment and repetition pairing. Positive percentages mean lower throughput. These costs cannot be added.

| Scenario | Tracking Kops/s | Tracking loss vs RLBox | InterSpec loss vs tracking | Tracking p99 µs | Tracking CPU µs/op | Tracking RSS MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| balanced_1c | 145.1 | +2.65% | +0.98% | 82.6 | 3.854 | 26.13 |
| balanced_8c | 680.7 | +0.67% | +0.89% | 302.5 | 2.769 | 26.18 |
| read_heavy_1k | 861.9 | +0.92% | +1.73% | 474.7 | 2.226 | 34.50 |
| write_heavy | 581.2 | -0.16% | +1.18% | 292.5 | 3.358 | 26.13 |
| watch_light | 18.7 | -1.25% | -0.62% | 68.7 | 33.130 | 36.34 |
| watch_moderate | 74.4 | +0.73% | +1.16% | 83.8 | 16.287 | 36.77 |

## SP3 primitive microbenchmark

| Primitive | Population | Median ns/op | Min–max ns/op |
| --- | ---: | ---: | ---: |
| allocate_from_site | 16384 | 77.35 | 75.07–77.82 |
| bounds_check | 2 | 1.64 | 1.54–1.67 |
| check_interior | 2 | 11.98 | 11.94–12.02 |
| check_live | 2 | 11.72 | 11.59–11.75 |
| metadata_lookup | 2 | 4.41 | 4.40–4.42 |
| release | 16384 | 37.15 | 36.74–38.52 |
| remaining_bytes | 2 | 11.88 | 11.82–11.95 |
| shared_lock | 2 | 7.63 | 7.55–7.73 |
| type_compare | 2 | 1.54 | 1.54–1.55 |

## Correlating checks with application overhead

The direct production Runtime::check cost used below is 11.72 ns/check at population 2. The estimate is checks/op × this microbenchmark cost; it intentionally excludes RLBox transitions, byte copies, queue synchronization, and other application work.

| Scenario | Client ops profiled | SP3 checks | Checks/op | Checks/1k ops | Estimated direct check ns/client op |
| --- | ---: | ---: | ---: | ---: | ---: |
| balanced_1c | 5000 | 54 | 0.0108 | 10.8 | 0.13 |
| balanced_8c | 5000 | 60 | 0.0120 | 12.0 | 0.14 |
| read_heavy_1k | 5000 | 748 | 0.1496 | 149.6 | 1.75 |
| write_heavy | 200000 | 2070 | 0.0103 | 10.3 | 0.12 |
| watch_light | 5000 | 36164 | 7.2328 | 7232.8 | 84.77 |
| watch_moderate | 5000 | 31063 | 6.2126 | 6212.6 | 72.81 |

## Observed boundary activity

Counts come from a separate diagnostic build and include the declared asynchronous drain. They are not timing results. Profile key counts are shown because they can differ from the timing matrix.

| Scenario | Profile keys | Client ops | Sandbox calls/op | Bytes into U/op | Bytes from U/op | Protected coverage valid |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| balanced_1c | 512 | 5000 | 0.0414 | 0.0832 | 0.1664 | True |
| balanced_8c | 512 | 5000 | 0.0404 | 0.0832 | 0.1664 | True |
| read_heavy_1k | 512 | 5000 | 0.2468 | 1.1840 | 2.3680 | True |
| write_heavy | 10000 | 200000 | 0.1566 | 0.0800 | 0.1600 | True |
| watch_light | 512 | 5000 | 14.3126 | 245.3376 | 639.4750 | True |
| watch_moderate | 512 | 5000 | 9.5800 | 245.3176 | 639.4150 | True |

A zero observed check count is retained as a coverage gap and is excluded from the cost correlation. It does not establish zero enforcement cost for that workload.

Interpretation: the microbenchmark establishes the cost of one metadata validation, while the fixed-operation profiler establishes how frequently real memcached paths invoke it. The end-to-end table then measures the actual aggregate effect. The estimate should explain direction and scale, not exactly equal the throughput delta, because checks execute concurrently and interact with sandbox transitions, copies, locks, cache effects, batching, and background logger/LRU work.
