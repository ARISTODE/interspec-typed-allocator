# Memcached end-to-end overhead matrix
Not publication-ready. Incidental rates are retained for provenance, not controlled-host overhead evidence.

Measurement: count-only; latency fields describe this run only. Count-only latency is unavailable; sampled quantiles describe selected responses, not every response.

Workload generator: independent-v1; seed: 20261109. Independent mode uses a target GET probability, not an exact finite-sample ratio. Do not pool with legacy results.

Positive deltas mean lower throughput. Values are medians; overheads are medians of paired per-repetition ratios.

| Scenario | Practical intent | Native Kops/s | RLBox Kops/s (Δ native) | InterSpec Kops/s (Δ native) | InterSpec Δ vs RLBox | p99 N/R/I (µs) | Loss-free |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| balanced_1c | low-concurrency balanced cache traffic; preserves the paper's 1-client, 1:1, pipeline-10 shape | 184.6 | 179.1 (+3.20%) | 178.5 (+2.41%) | -0.90% | unavailable/unavailable/unavailable | yes |
| balanced_8c | higher-concurrency balanced cache traffic; preserves the paper's 8-client, 1:1, pipeline-10 shape | 645.4 | 610.1 (+4.58%) | 609.2 (+4.25%) | +1.91% | unavailable/unavailable/unavailable | yes |
| read_heavy_1k | read-mostly object-cache scenario with 1 KiB values | 947.9 | 887.4 (+6.32%) | 879.2 (+7.75%) | +1.94% | unavailable/unavailable/unavailable | yes |
| write_heavy | mutation-heavy scenario stressing SET paths and asynchronous LRU activity | 488.8 | 467.2 (+3.61%) | 472.8 (+3.22%) | +0.30% | unavailable/unavailable/unavailable | yes |
| watch_light | lossless active-observability scenario with a live watcher | 24.9 | 24.8 (-0.12%) | 24.7 (+1.68%) | +0.28% | unavailable/unavailable/unavailable | yes |
| watch_moderate | moderate active-observability load with worker and watcher queues exercised continuously | 87.1 | 88.0 (+1.05%) | 85.1 (+3.02%) | +1.29% | unavailable/unavailable/unavailable | yes |

## Allocation tracking decomposition

All four variants are collected in the same paired experiment. Percentages describe throughput loss; these paired medians must not be added.

| Scenario | Tracking Kops/s | Tracking loss vs RLBox | InterSpec loss vs tracking | Tracking p99 µs | Lossless across all variants |
| --- | ---: | ---: | ---: | ---: | --- |
| balanced_1c | 181.7 | -1.31% | -0.38% | unavailable | yes |
| balanced_8c | 620.3 | -0.13% | +1.39% | unavailable | yes |
| read_heavy_1k | 889.3 | +0.23% | +1.68% | unavailable | yes |
| write_heavy | 474.6 | +0.27% | +0.74% | unavailable | yes |
| watch_light | 24.6 | +0.56% | -0.19% | unavailable | yes |
| watch_moderate | 86.4 | +1.22% | +0.54% | unavailable | yes |

The balanced 1-client and 8-client scenarios preserve the original InterSpec memcached/bipbuffer target workload shape of 50% GET / 50% SET with pipeline depth 10 while making value size and working-set size explicit.
Watcher scenarios are accepted for the main table only when every timed run has zero logger and LRU drops. A lossy run is retained as raw evidence but must not be interpreted as an overhead result.
