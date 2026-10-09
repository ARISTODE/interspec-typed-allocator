# Memcached performance evaluation plan

This study separates three questions that should not be collapsed into one number.

1. What does deploying RLBox cost relative to native memcached?
2. What does full InterSpec cost relative to native memcached and relative to RLBox-only?
3. Can the end-to-end InterSpec delta be related to the cost and frequency of the individual SP3 metadata checks?

## End-to-end variants

The main paper table uses exactly three timed release builds:

* `native`: pinned upstream memcached with no library sandbox.
* `rlbox-only`: the same memcached deployment with bipbuffer isolated through RLBox wasm2c, but no typed-allocation tracking and no SP3 metadata checks.
* `interspec`: the same RLBox deployment with typed allocation metadata and SP3 checks enabled.

`tracked-no-check` remains available only as an optional decomposition experiment. It is useful for attributing tracking cost, but it is not required in the main three-way table.

All variants use the same memcached revision, compiler optimization level, server worker count, keys, values, client traffic, queue sizes, and application-level log/LRU validation appropriate to the sandboxed deployment. Timed release binaries exclude diagnostic tracing and fault injection.

## Workload matrix

The matrix intentionally spans concurrency, read/write mix, value size, and whether the protected watcher path is active.

| Scenario | Clients | Pipeline | GET/SET | Value | Keys | Protected-path intent |
| --- | ---: | ---: | --- | ---: | ---: | --- |
| `balanced_1c` | 1 | 10 | 50/50 | 256 B | 10,000 | low-concurrency balanced baseline |
| `balanced_8c` | 8 | 10 | 50/50 | 256 B | 10,000 | higher-concurrency balanced baseline |
| `read_heavy_1k` | 8 | 16 | 95/5 | 1 KiB | 10,000 | practical read-mostly object cache |
| `write_heavy` | 8 | 8 | 10/90 | 256 B | 10,000 | mutation and asynchronous LRU stress |
| `watch_light` | 1 | 1 | 50/50 | 256 B | 10,000 | active watcher, deliberately light enough to remain lossless |
| `watch_moderate` | 2 | 2 | 50/50 | 256 B | 10,000 | continuous worker/watcher queue activity |

The first two scenarios preserve the original InterSpec memcached/bipbuffer benchmark shape of a 1:1 GET/SET mix with pipeline depth 10 at 1 and 8 clients, while making value and working-set sizes explicit. The additional scenarios avoid drawing conclusions from one synthetic operating point.

A watcher result is valid only when all timed runs have zero logger drops, watcher skips, and LRU bump drops. Lossy results are retained as stress evidence but are excluded from overhead claims.

## Measurement protocol

Publication runs use the `paper` preset: 5 s warm-up, 30 s measurement, and 15 paired repetitions per scenario and variant. Variant order is randomized reproducibly within each repetition.

For controlled-host measurements, pin server and client/load-generator CPUs to disjoint sets and record CPU model, frequency policy, cgroup quota, memory limit, compiler, binary hashes, and raw run-level samples. The client validates every response.

The main table reports median throughput, paired throughput loss versus native, paired InterSpec loss versus RLBox-only, and p99 response latency. CPU time per operation and RSS are retained for secondary tables.

## Microbenchmark

The runtime microbenchmark measures the exact production `Runtime::check` and also isolates the primitives that compose it:

* shared metadata lock
* ordered allocation lookup and containment test
* expected-type hash comparison
* offset/remaining-byte bounds check
* full live-object check
* interior-pointer check
* typed allocation from an inferred site
* metadata release

Population 2 is the primary memcached point because a normal queue sandbox has two tracked allocations: the real `bipbuf_t` allocation and one persistent input-copy allocation. Larger populations are retained to show scalability rather than to imply that memcached normally has thousands of live objects per queue.

Primitive timings are explanatory and are not summed to predict the full check. The full `check_live` timing is the direct per-check cost.

## Check-frequency correlation

A separate diagnostic build runs a fixed number of validated client operations. Preload and watcher setup are excluded from the counted interval. Successful SP3 checks are tagged by the actual bridge operation that requested them, such as `request`, `push`, `offer_input`, `peek`, `peek_all`, and `poll`.

For each scenario we report:

`checks per client operation = successful Runtime::check calls / completed client operations`

and

`estimated direct metadata-check time per client operation = checks/op × median check_live ns`.

This estimate is intentionally narrower than the end-to-end slowdown. RLBox transitions, copies, queue synchronization, batching, cache effects, logging, and LRU work are measured only by the end-to-end experiment.

## Commands

Hosted-CI smoke validation:

```sh
python3 tools/benchmark_memcached_matrix.py \
  --out results/matrix --preset smoke \
  --correctness-summary results/correctness/summary.json

python3 tools/profile_memcached_checks.py \
  --out results/checks --operations 5000 \
  --correctness-summary results/correctness/summary.json

python3 tools/run_runtime_microbench.py \
  --out results/microbench --repetitions 9 --iterations 1000000
```

Controlled publication run:

```sh
python3 tools/benchmark_memcached_matrix.py \
  --out results/paper-matrix --preset paper \
  --server-cpus 0-3 --client-cpus 4-7 \
  --correctness-summary results/correctness/summary.json
```

Finally, join the evidence:

```sh
python3 tools/render_memcached_overhead_study.py \
  --matrix results/paper-matrix/final-summary.json \
  --checks results/checks/check-frequency.json \
  --microbench results/microbench/summary.json \
  --output results/MEMCACHED_PERFORMANCE_STUDY.md
```


## Remaining data collection TODO

Current completeness audit: [EVALUATION_READINESS.md](EVALUATION_READINESS.md).
The retained six-scenario smoke matrix has Native, RLBox-only, and InterSpec
samples. Its tracking-only cells still need collection using
`--include-tracking`; tracking numbers from the separate two-workload pilot
must not be substituted. The 39-configuration runtime microbenchmark reference
has five raw repetitions per configuration and has been independently
recomputed from its archived samples.

### Priority 1: explain Native → RLBox overhead

Add dedicated boundary microbenchmarks on the same controlled host used for final application measurements:

* empty native call vs. empty RLBox/wasm2c invocation,
* wrapper mutex lock/unlock,
* RLBox pointer-confinement operations,
* T → U and U → T copies at 64 B, 256 B, 1 KiB, and 4 KiB,
* complete `request + push`, `offer`, `peek_all`, and `poll` operations under Native, RLBox, and InterSpec.

Report **ns/op** or **ns/call** with repeated measurements and raw samples.

### Priority 2: measure boundary frequency in real workloads

Extend the fixed-operation profiler to record, per client operation:

* RLBox sandbox invocations,
* T → U bytes copied,
* U → T bytes copied,
* SP3 checks by wrapper operation.

This allows direct correlation between microbenchmark cost and end-to-end overhead.

### Priority 3: fix write-heavy coverage

The current short `write_heavy` profile observes no protected LRU operation. Increase the profiling duration/operation count or adjust the workload until LRU activity is observed and verified by counters. Do not use this workload in the check-frequency correlation until the protected path is demonstrably exercised. The selected timed reference already records nonzero `moves_to_warm` deltas (29, 121, and 21) in its three InterSpec write-heavy measurements with zero LRU drops. Those application counters do not replace direct SP3 counts in the separate profiling window.

### Priority 4: controlled end-to-end publication run

Run the six workload scenarios with:

* 5 s warmup,
* 30 s measured interval,
* 15 paired repetitions,
* disjoint server/client CPU affinity,
* fixed host configuration,
* zero logger/watcher/LRU drops,
* raw throughput, p99 latency, CPU/op, and RSS samples.

Report paired overheads and run-level variation; add confidence intervals if the controlled data supports them.

### Priority 5: repeat microbenchmarks on the publication host

Rerun the InterSpec runtime microbenchmarks and new RLBox/copy microbenchmarks on the same machine as the end-to-end experiment. The paper should correlate numbers collected under one hardware/software environment.

### Completed follow-up: additional complete applications

Rsync/popt now has matched Native, RLBox-only, tracking-only and Extended-SP3
results for option parsing, local dry-run and 194 MiB transfers. YAML/libyaml
and nginx/PCRE also have complete application integrations and reference
measurements. Their controlled-hardware publication runs remain outstanding.
