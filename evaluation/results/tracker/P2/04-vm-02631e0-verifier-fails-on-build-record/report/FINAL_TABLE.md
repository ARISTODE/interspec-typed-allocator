# Memcached end-to-end overhead matrix
Not publication-ready. Incidental rates are retained for provenance, not controlled-host overhead evidence.

Measurement: count-only; latency fields describe this run only. Count-only latency is unavailable; sampled quantiles describe selected responses, not every response.

Workload generator: independent-v1; seed: 20261109. Independent mode uses a target GET probability, not an exact finite-sample ratio. Do not pool with legacy results.

Positive deltas mean lower throughput. Values are medians; overheads are medians of paired per-repetition ratios.

| Scenario | Practical intent | Native Kops/s | RLBox Kops/s (Δ native) | InterSpec Kops/s (Δ native) | InterSpec Δ vs RLBox | p99 N/R/I (µs) | Loss-free |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| balanced_1c | low-concurrency balanced cache traffic; preserves the paper's 1-client, 1:1, pipeline-10 shape | 199.8 | 201.0 (-0.16%) | 199.4 (+1.57%) | +0.17% | unavailable/unavailable/unavailable | yes |
| balanced_8c | higher-concurrency balanced cache traffic; preserves the paper's 8-client, 1:1, pipeline-10 shape | 731.0 | 709.3 (+2.80%) | 701.9 (+4.80%) | +0.68% | unavailable/unavailable/unavailable | yes |
| read_heavy_1k | read-mostly object-cache scenario with 1 KiB values | 995.2 | 967.7 (+3.14%) | 946.6 (+7.46%) | +2.62% | unavailable/unavailable/unavailable | yes |
| write_heavy | mutation-heavy scenario stressing SET paths and asynchronous LRU activity | 544.5 | 517.4 (+0.77%) | 519.7 (+4.14%) | +1.61% | unavailable/unavailable/unavailable | yes |
| watch_light | lossless active-observability scenario with a live watcher | 28.1 | 27.9 (+0.04%) | 27.4 (+2.37%) | +2.02% | unavailable/unavailable/unavailable | yes |
| watch_moderate | moderate active-observability load with worker and watcher queues exercised continuously | 86.0 | 84.5 (+1.82%) | 84.0 (+3.14%) | +1.37% | unavailable/unavailable/unavailable | yes |

## Allocation tracking decomposition

All four variants are collected in the same paired experiment. Percentages describe throughput loss; these paired medians must not be added.

| Scenario | Tracking Kops/s | Tracking loss vs RLBox | InterSpec loss vs tracking | Tracking p99 µs | Lossless across all variants |
| --- | ---: | ---: | ---: | ---: | --- |
| balanced_1c | 201.5 | +0.58% | -0.68% | unavailable | yes |
| balanced_8c | 709.8 | -0.65% | +1.33% | unavailable | yes |
| read_heavy_1k | 963.5 | +1.52% | +1.16% | unavailable | yes |
| write_heavy | 519.9 | +0.90% | +1.73% | unavailable | yes |
| watch_light | 27.7 | +1.93% | +0.30% | unavailable | yes |
| watch_moderate | 85.3 | +0.42% | +0.93% | unavailable | yes |

The balanced 1-client and 8-client scenarios preserve the original InterSpec memcached/bipbuffer target workload shape of 50% GET / 50% SET with pipeline depth 10 while making value size and working-set size explicit.
Watcher scenarios are accepted for the main table only when every timed run has zero logger and LRU drops. A lossy run is retained as raw evidence but must not be interpreted as an overhead result.
