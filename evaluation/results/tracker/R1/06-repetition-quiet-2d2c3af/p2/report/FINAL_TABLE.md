# Memcached end-to-end overhead matrix
Not publication-ready. Incidental rates are retained for provenance, not controlled-host overhead evidence.

Measurement: count-only; latency fields describe this run only. Count-only latency is unavailable; sampled quantiles describe selected responses, not every response.

Workload generator: independent-v1; seed: 20261109. Independent mode uses a target GET probability, not an exact finite-sample ratio. Do not pool with legacy results.

Positive deltas mean lower throughput. Values are medians; overheads are medians of paired per-repetition ratios.

| Scenario | Practical intent | Native Kops/s | RLBox Kops/s (Δ native) | InterSpec Kops/s (Δ native) | InterSpec Δ vs RLBox | p99 N/R/I (µs) | Loss-free |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| balanced_1c | low-concurrency balanced cache traffic; preserves the paper's 1-client, 1:1, pipeline-10 shape | 221.2 | 217.4 (+1.86%) | 217.7 (+1.60%) | -0.05% | unavailable/unavailable/unavailable | yes |
| balanced_8c | higher-concurrency balanced cache traffic; preserves the paper's 8-client, 1:1, pipeline-10 shape | 782.3 | 760.8 (+3.44%) | 758.0 (+4.35%) | +0.23% | unavailable/unavailable/unavailable | yes |
| read_heavy_1k | read-mostly object-cache scenario with 1 KiB values | 1100.0 | 1025.9 (+6.91%) | 1017.3 (+8.66%) | +0.79% | unavailable/unavailable/unavailable | yes |
| write_heavy | mutation-heavy scenario stressing SET paths and asynchronous LRU activity | 595.8 | 580.4 (+2.99%) | 578.4 (+2.09%) | +0.55% | unavailable/unavailable/unavailable | yes |
| watch_light | lossless active-observability scenario with a live watcher | 29.9 | 29.5 (+0.52%) | 29.1 (+2.11%) | +1.70% | unavailable/unavailable/unavailable | yes |
| watch_moderate | moderate active-observability load with worker and watcher queues exercised continuously | 98.9 | 100.9 (+1.15%) | 99.8 (+2.91%) | +1.10% | unavailable/unavailable/unavailable | yes |

## Allocation tracking decomposition

All four variants are collected in the same paired experiment. Percentages describe throughput loss; these paired medians must not be added.

| Scenario | Tracking Kops/s | Tracking loss vs RLBox | InterSpec loss vs tracking | Tracking p99 µs | Lossless across all variants |
| --- | ---: | ---: | ---: | ---: | --- |
| balanced_1c | 217.5 | -0.51% | +0.37% | unavailable | yes |
| balanced_8c | 759.3 | -0.48% | +0.82% | unavailable | yes |
| read_heavy_1k | 1025.8 | -0.04% | +1.62% | unavailable | yes |
| write_heavy | 581.0 | -0.18% | -0.43% | unavailable | yes |
| watch_light | 29.7 | -0.34% | +0.62% | unavailable | yes |
| watch_moderate | 101.2 | -0.25% | +1.65% | unavailable | yes |

The balanced 1-client and 8-client scenarios preserve the original InterSpec memcached/bipbuffer target workload shape of 50% GET / 50% SET with pipeline depth 10 while making value size and working-set size explicit.
Watcher scenarios are accepted for the main table only when every timed run has zero logger and LRU drops. A lossy run is retained as raw evidence but must not be interpreted as an overhead result.
