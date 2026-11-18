# Memcached end-to-end overhead matrix
Not publication-ready. Incidental rates are retained for provenance, not controlled-host overhead evidence.

Measurement: count-only; latency fields describe this run only. Count-only latency is unavailable; sampled quantiles describe selected responses, not every response.

Workload generator: independent-v1; seed: 20261109. Independent mode uses a target GET probability, not an exact finite-sample ratio. Do not pool with legacy results.

Positive deltas mean lower throughput. Values are medians; overheads are medians of paired per-repetition ratios.

| Scenario | Practical intent | Native Kops/s | RLBox Kops/s (Δ native) | InterSpec Kops/s (Δ native) | InterSpec Δ vs RLBox | p99 N/R/I (µs) | Loss-free |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| balanced_1c | low-concurrency balanced cache traffic; preserves the paper's 1-client, 1:1, pipeline-10 shape | 178.3 | 176.5 (+1.36%) | 177.8 (+3.14%) | +0.40% | unavailable/unavailable/unavailable | yes |
| balanced_8c | higher-concurrency balanced cache traffic; preserves the paper's 8-client, 1:1, pipeline-10 shape | 648.1 | 611.9 (+5.35%) | 608.1 (+6.43%) | +0.22% | unavailable/unavailable/unavailable | yes |
| read_heavy_1k | read-mostly object-cache scenario with 1 KiB values | 906.6 | 816.7 (+8.68%) | 803.6 (+10.48%) | +0.59% | unavailable/unavailable/unavailable | yes |
| write_heavy | mutation-heavy scenario stressing SET paths and asynchronous LRU activity | 482.1 | 466.6 (+3.68%) | 457.8 (+6.61%) | +2.98% | unavailable/unavailable/unavailable | yes |
| watch_light | lossless active-observability scenario with a live watcher | 25.5 | 25.2 (-0.96%) | 24.6 (+2.32%) | +3.24% | unavailable/unavailable/unavailable | yes |
| watch_moderate | moderate active-observability load with worker and watcher queues exercised continuously | 83.9 | 83.4 (-1.11%) | 80.4 (+2.74%) | +3.59% | unavailable/unavailable/unavailable | yes |

## Allocation tracking decomposition

All four variants are collected in the same paired experiment. Percentages describe throughput loss; these paired medians must not be added.

| Scenario | Tracking Kops/s | Tracking loss vs RLBox | InterSpec loss vs tracking | Tracking p99 µs | Lossless across all variants |
| --- | ---: | ---: | ---: | ---: | --- |
| balanced_1c | 178.9 | -2.31% | +2.11% | unavailable | yes |
| balanced_8c | 608.2 | +0.84% | -3.81% | unavailable | yes |
| read_heavy_1k | 818.6 | +0.53% | +2.06% | unavailable | yes |
| write_heavy | 466.9 | +0.74% | +2.04% | unavailable | yes |
| watch_light | 24.9 | +2.44% | +0.24% | unavailable | yes |
| watch_moderate | 81.7 | +1.65% | +1.51% | unavailable | yes |

The balanced 1-client and 8-client scenarios preserve the original InterSpec memcached/bipbuffer target workload shape of 50% GET / 50% SET with pipeline depth 10 while making value size and working-set size explicit.
Watcher scenarios are accepted for the main table only when every timed run has zero logger and LRU drops. A lossy run is retained as raw evidence but must not be interpreted as an overhead result.
