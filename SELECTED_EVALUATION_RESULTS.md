# Selected application evaluation results

All four selected Extended-SP3 applications have reference measurements. These are hosted or shared-environment results. Final controlled-hardware publication measurements remain outstanding.

[EVALUATION_READINESS.md](EVALUATION_READINESS.md) audits these application results together with runtime and boundary microbenchmarks, and lists every outstanding result class.

## Verified reference numbers

Values are medians of individual runs. Deltas and ranges are computed from paired runs, so they need not equal ratios of the displayed medians.

| Application | Workload | Unit | Native | RLBox | Tracking | InterSpec | Paired delta vs RLBox | Paired range | Repetitions |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| rsync/popt | file_sync_194mb | ms | 613.280 | 613.998 | 614.371 | 616.161 | +0.37% | -5.04% to +1.92% | 15 |
| rsync/popt | local_dry_run | ms | 41.678 | 42.504 | 42.556 | 42.558 | +0.06% | -3.66% to +1.62% | 15 |
| rsync/popt | option_parse | ms | 0.648 | 1.174 | 1.369 | 1.128 | -6.25% | -16.47% to +25.43% | 15 |
| YAML/libyaml | 1 MiB document, 1000 parses | ms | 4287.155 | 5813.376 | 5766.793 | 5810.707 | +0.01% | -6.44% to +4.66% | 15 |
| memcached/bipbuffer | balanced_1c | Kops/s | 143.672 | 138.205 | not collected | 141.157 | -2.14% | -4.57% to -0.41% | 3 |
| memcached/bipbuffer | balanced_8c | Kops/s | 650.720 | 662.782 | not collected | 641.496 | +1.22% | -1.44% to +10.24% | 3 |
| memcached/bipbuffer | read_heavy_1k | Kops/s | 897.296 | 839.284 | not collected | 809.626 | +0.02% | -1.06% to +5.05% | 3 |
| memcached/bipbuffer | write_heavy | Kops/s | 565.665 | 576.090 | not collected | 558.804 | +3.00% | +2.29% to +3.20% | 3 |
| memcached/bipbuffer | watch_light | Kops/s | 18.339 | 18.385 | not collected | 18.365 | +0.11% | -0.79% to +4.69% | 3 |
| memcached/bipbuffer | watch_moderate | Kops/s | 75.117 | 72.331 | not collected | 73.365 | +0.85% | -1.92% to +1.37% | 3 |
| nginx/PCRE | 4 wrk threads | Kreq/s | 62.724 | 54.895 | 55.161 | 54.881 | -0.58% | -2.71% to +5.74% | 5 |
| nginx/PCRE | 8 wrk threads | Kreq/s | 60.305 | 53.672 | 54.611 | 54.518 | -0.77% | -2.24% to +1.56% | 5 |

For rsync and YAML, a positive delta means increased runtime: 100 × (InterSpec / RLBox − 1). For memcached and nginx, a positive delta means lost throughput: 100 × (1 − InterSpec / RLBox). The CSV also provides paired inverse-throughput overhead for conversions; it is not measured request latency. No geometric mean mixes these two definitions.

Small and negative differences in these environments do not establish speedups. The rsync option-parse case is especially sensitive to process startup and timing noise.

## Measurement and validation scope

* Rsync: 15 paired repetitions per workload; the main workload is a 194 MiB local transfer. Application corruption validation rejects 12 invalid pointers. The remaining two workloads are secondary checks.
* YAML: the selected newer hosted run uses an exactly 1 MiB document and 1,000 parses per timed run, with 15 paired repetitions and two warmups. Outputs match across all four variants. Four invalid pointer controls reject and the same-type substitution control is accepted as expected.
* Memcached: all 50 deployment cases pass. The six-scenario table uses the existing smoke protocol: one-second measurements, 0.3-second warmups, and three paired repetitions. Every timed run is free of client errors and logger/LRU drops. These rows do not satisfy the planned 30-second, 15-repetition publication protocol. Tracking-only is absent from this six-scenario matrix; do not substitute values from a different run.
* Memcached's timed write-heavy InterSpec runs record moves_to_warm counter deltas of 29, 121, 21, all with zero LRU drops. These application counters establish LRU activity but are not direct counts of SP3 validations. The separate short diagnostic profile still has zero checks and remains unsuitable for check-cost correlation.
* Nginx: all 24 application cases pass, including two-worker operation and two graceful reloads for Native and InterSpec. The performance matrix has 100 connections, 30-second windows, three-second warmups, five paired repetitions, and four/eight wrk client threads. Performance uses one nginx event loop, not four/eight nginx workers. Every response passes validation and every timed binary matches the correctness gate.

## Source datasets

* [evaluation/results/rsync-popt/rsync-performance.csv](evaluation/results/rsync-popt/rsync-performance.csv)
* [evaluation/results/yaml-libyaml/hosted-37593628736/yaml-performance.csv](evaluation/results/yaml-libyaml/hosted-37593628736/yaml-performance.csv)
* [evaluation/results/memcached-overhead/hosted-37593628863/overhead-matrix/all-samples.csv](evaluation/results/memcached-overhead/hosted-37593628863/overhead-matrix/all-samples.csv)
* [evaluation/results/nginx-pcre/hosted-37835791042/performance/samples.csv](evaluation/results/nginx-pcre/hosted-37835791042/performance/samples.csv)

Source SHA-256 values and the machine-readable table are under `evaluation/results/selected/`. Original artifacts and per-run provenance are retained alongside the source CSVs. Older reference runs remain separately identified.

## Remaining publication work

1. Run the selected workloads on controlled hardware with recorded CPU affinity and power policy, sufficient repetitions, and load-generator capacity checks. Memcached especially needs its longer planned measurement protocol.
2. Extend the memcached write-heavy diagnostic profile until counters demonstrate protected LRU activity. Its current 1,000-operation profile observes zero checks and is excluded from check-cost correlation.
3. Collect the memcached Native-to-RLBox boundary-cost breakdown. Existing primitive measurements do not separately quantify transitions, copies, or wrapper synchronization.
4. Review and merge the draft implementation stack. These measurements cover the selected Extended-SP3 integrations, not all ten manuscript boundaries or a fresh evaluation of all original policies.
