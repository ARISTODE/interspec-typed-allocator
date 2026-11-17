# Memcached end-to-end overhead matrix
Not publication-ready. Incidental rates are retained for provenance, not controlled-host overhead evidence.

Measurement: count-only; latency fields describe this run only. Count-only latency is unavailable; sampled quantiles describe selected responses, not every response.

Workload generator: independent-v1; seed: 20261109. Independent mode uses a target GET probability, not an exact finite-sample ratio. Do not pool with legacy results.

Positive deltas mean lower throughput. Values are medians; overheads are medians of paired per-repetition ratios.

| Scenario | Practical intent | Native Kops/s | RLBox Kops/s (Δ native) | InterSpec Kops/s (Δ native) | InterSpec Δ vs RLBox | p99 N/R/I (µs) | Loss-free |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| balanced_1c | low-concurrency balanced cache traffic; preserves the paper's 1-client, 1:1, pipeline-10 shape | 204.2 | 196.5 (+2.86%) | 196.6 (+3.21%) | +0.40% | unavailable/unavailable/unavailable | yes |
| balanced_8c | higher-concurrency balanced cache traffic; preserves the paper's 8-client, 1:1, pipeline-10 shape | 725.6 | 703.6 (+7.00%) | 691.0 (+3.22%) | -0.26% | unavailable/unavailable/unavailable | yes |
| read_heavy_1k | read-mostly object-cache scenario with 1 KiB values | 1041.5 | 989.3 (+5.06%) | 961.2 (+7.88%) | +2.37% | unavailable/unavailable/unavailable | yes |
| write_heavy | mutation-heavy scenario stressing SET paths and asynchronous LRU activity | 547.8 | 510.4 (+3.69%) | 520.6 (+3.14%) | -2.04% | unavailable/unavailable/unavailable | yes |
| watch_light | lossless active-observability scenario with a live watcher | 28.9 | 28.6 (+1.27%) | 28.3 (+2.02%) | +0.68% | unavailable/unavailable/unavailable | yes |
| watch_moderate | moderate active-observability load with worker and watcher queues exercised continuously | 99.8 | 97.3 (+1.52%) | 96.3 (+2.27%) | +0.73% | unavailable/unavailable/unavailable | yes |

## Allocation tracking decomposition

All four variants are collected in the same paired experiment. Percentages describe throughput loss; these paired medians must not be added.

| Scenario | Tracking Kops/s | Tracking loss vs RLBox | InterSpec loss vs tracking | Tracking p99 µs | Lossless across all variants |
| --- | ---: | ---: | ---: | ---: | --- |
| balanced_1c | 200.8 | -2.70% | +1.26% | unavailable | yes |
| balanced_8c | 692.1 | +0.68% | -1.84% | unavailable | yes |
| read_heavy_1k | 972.4 | -0.54% | +1.30% | unavailable | yes |
| write_heavy | 519.1 | -1.09% | -0.74% | unavailable | yes |
| watch_light | 28.5 | -0.42% | +0.95% | unavailable | yes |
| watch_moderate | 98.7 | +0.93% | +0.15% | unavailable | yes |

The balanced 1-client and 8-client scenarios preserve the original InterSpec memcached/bipbuffer target workload shape of 50% GET / 50% SET with pipeline depth 10 while making value size and working-set size explicit.
Watcher scenarios are accepted for the main table only when every timed run has zero logger and LRU drops. A lossy run is retained as raw evidence but must not be interpreted as an overhead result.
