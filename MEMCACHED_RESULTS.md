# Memcached deployment results

The complete cache-server deployment passes **50/50** local cases. Performance results below are a **shared-container pilot**, not publication overhead estimates.

Implementation and measured binaries: `5112d9ccc3d7b73439b1d7f42525e40d0d612c38`.

The fresh-build [memcached deployment CI run](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/36977024146) passed its build, 50-case correctness gate, and performance-collection step at this implementation revision.

The [implementation guide](MEMCACHED_DEPLOYMENT.md) documents the boundary, source edits, threat scope, build, tests, and collection commands. [PR #16](https://github.com/ARISTODE/interspec-typed-allocator/pull/16) is stacked on the SP3 diagnostics work in #15.

## What now runs

* The actual pinned memcached 1.6.45 cache server runs with bipbuffer in RLBox wasm2c.
* All three uses are covered: worker logs, watcher output, and asynchronous LRU item bumps.
* T checks U pointer type, extent, and live allocation metadata before accessing bytes. It then works on stable T snapshots.
* The logger validates record structure and parser indexes. LRU queues carry one-use handles; T retains native item pointers and verifies their lock hashes before use.
* Native, RLBox-only, tracking-only, full SP3, and diagnostic builds execute the normal-operation suite. Release builds exclude trace/fault code.

The LRU handle protection is a material addition discovered during deployment: an outer buffer check alone would leave the native pointers inside LRU records exposed to corruption. Those pointers now stay in T.

## Correctness and enforcement

| Evidence | Result |
| --- | --- |
| Normal-operation groups | 5 variants × 16 checks pass |
| Pointer corruption | 36/36 reject: 3 queue roles × 3 paths × 4 errors |
| Same-type substitutions | 3/3 accepted, as expected from SP3 scope |
| Application validation controls | 4/4 reject: invalid log event, forged LRU handle, wrong item hash, split LRU record |
| Upstream watcher tests | 47/47 assertions for native; 47/47 for SP3 |
| Core runtime regression suite | 20/20 CTest tests pass |

These suites overlap; their counts are not independent security guarantees. The 50 top-level cases comprise 5 normal groups, 36 pointer attacks, 7 scope/application controls, and 2 upstream suites.

Normal checks include asynchronous LRU bumps, set/get flags, add/replace, CAS, append/prepend, counters, a 256 KiB binary value, multiget, touch/delete, fragmented requests, invalid commands, expiry, flush, watcher contents, 2,000 operations from four concurrent clients, and 25 watcher reconnects. The upstream test assertions are unchanged; their copied launcher selects loopback TCP.

Representative actual rejection messages:

```text
INTERSPEC_REJECT boundary=memcached_bipbuffer operation=peek_all reason=wrong_type
INTERSPEC_REJECT boundary=memcached_bipbuffer operation=peek_all reason=untracked
INTERSPEC_REJECT boundary=memcached_bipbuffer operation=peek_all reason=out_of_bounds
INTERSPEC_REJECT boundary=memcached_logger reason=malformed_record
INTERSPEC_REJECT boundary=memcached_bipbuffer operation=lru_take reason=unknown_handle
INTERSPEC_REJECT boundary=memcached_bipbuffer operation=lru_take reason=wrong_item_hash
INTERSPEC_REJECT boundary=memcached_bipbuffer operation=lru_extent reason=malformed_record
```

An ordinary untracked pointer and a released tracked pointer both produce `untracked`; the latter has a preceding successful metadata release. Invalid pointers terminate with SIGABRT. Same-type substitution controls preserve valid contents and demonstrate the limit of the allocation check.

## Allocator trace evidence

The diagnostic normal run created 74 tracked allocations across 37 sandbox instances: 7 worker loggers, 4 LRU queues, and 26 watcher instances including churn.

It recorded 436 allocation checks, 52 releases, and 128 / 128 trusted LRU handle creations / consumptions. Event counts reflect this workload and scheduling, not a universal operation cost.

| Allocation site | Size (bytes) | Count |
| --- | ---: | ---: |
| 1048578 | 131072 | 4 |
| 1048577 | 131092 | 4 |
| 1048578 | 262144 | 26 |
| 1048577 | 262164 | 26 |
| 1048578 | 65536 | 7 |
| 1048577 | 65556 | 7 |

Site 1048577 is the real `bipbuf_t` allocation, including its 20-byte Wasm header. Site 1048578 is the persistent character input buffer. T staging, handle maps, backend memory, and native item allocations are additional memory and are reflected in process RSS.

## Performance pilot

Configuration: 2 loopback clients, pipeline depth 1, four server workers, 1024 keys, 256-byte values, 50% GETs, 1.0-second warmup, 3.0-second measurement, 5 paired repetitions per variant/workload. Variant order is shuffled reproducibly. The worker/watcher buffers are 1 MiB / 4 MiB for every variant.

CPU quota: `800000 100000`. Memory limit: `8589934592` bytes. CPU governor: `unavailable`. Server/client affinity was not pinned for this pilot. Both run in the same shared environment.

| Workload | Variant | Median ops/s | Min–max ops/s | Median run p99 (µs) | Median CPU µs/op | Median RSS (MiB) | No log/LRU losses in all runs |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| cache_only | native | 83,248 | 76,241–89,022 | 68.16 | 11.80 | 3.70 | yes |
| cache_only | rlbox-only | 79,032 | 72,663–87,329 | 68.60 | 12.45 | 20.08 | yes |
| cache_only | tracked-no-check | 81,189 | 74,487–92,541 | 64.83 | 11.86 | 20.01 | yes |
| cache_only | interspec | 82,057 | 72,751–98,407 | 64.73 | 11.88 | 20.01 | yes |
| watch_active | native | 80,858 | 78,098–89,724 | 66.08 | 13.06 | 4.55 | yes |
| watch_active | rlbox-only | 84,169 | 78,643–88,380 | 65.95 | 12.65 | 29.05 | yes |
| watch_active | tracked-no-check | 81,934 | 71,827–87,722 | 70.56 | 13.28 | 29.12 | yes |
| watch_active | interspec | 77,973 | 72,647–87,339 | 70.91 | 13.75 | 28.80 | yes |

| Workload | SP3 throughput loss vs native | vs RLBox-only | vs tracking-only |
| --- | ---: | ---: | ---: |
| cache_only | 0.41% | -5.77% | -6.34% |
| watch_active | 0.75% | 7.22% | 4.83% |

Percentages are medians of paired per-repetition ratios, `100 × (1 − SP3 throughput / baseline throughput)`. Negative values do not establish a speedup. These short, unpinned measurements can vary with scheduling and background load. The components have different denominators and are not additive.

The client validates every response. Response latency includes pipelining and is a closed-loop measurement. CPU counters include final deferred logger work; RSS is sampled after the run. `cache_only` can exercise LRU queues; `watch_active` additionally exercises logging. Logs and LRU drops must be considered when comparing throughput. Earlier high-load development pilots showed log drops and are not used as paper overhead evidence.

The four timed release binary hashes match the correctness gate. Upstream tests use separate debug builds; their exact tested hashes are retained in the correctness summary. Recompiling coverage-enabled debug objects can change their build hashes without changing the source.

## Remaining paper evaluation

* Run repeated longer measurements on controlled hardware, with disjoint CPU affinity and a client-capacity check; retain raw run-level samples and uncertainty.
* Sweep concurrency, pipeline depth, value size, working-set size, and read/write mix, including active watchers and LRU activity. Report log/LRU loss alongside throughput and latency.
* Measure longer-term watcher churn, memory growth, startup, and sustained queue pressure. Evaluate saturation with a separate load generator where appropriate.
* Extend deployment to any additional configurations claimed in the paper, including extstore/proxy/TLS/SASL if in scope; nginx and YAML applications remain separate work.
* Review and merge the implementation PRs after their CI gates. A passing test suite is experimental evidence for these cases, not a formal proof or exhaustive compatibility claim.

## Reproducibility artifacts

* [Correctness cases and tested binary hashes](evaluation/results/memcached-deployment/correctness-summary.json)
* [Raw performance samples](evaluation/results/memcached-deployment/samples.csv)
* [Performance summary](evaluation/results/memcached-deployment/performance-summary.json)
* [Build provenance](evaluation/results/memcached-deployment/build-manifest.json)
* [Host and workload parameters](evaluation/results/memcached-deployment/environment.json)
* [Tracking summary](evaluation/results/memcached-deployment/tracking-summary.json)
* [Complete raw evidence archive](evaluation/results/memcached-deployment/evidence.tar.gz), including per-case stderr/stdout, watcher records, upstream outputs, per-run stats, build logs, generated policy, and SHA-256 manifest.

Regenerate this report with `python3 tools/render_memcached_results.py --results evaluation/results/memcached-deployment --output MEMCACHED_RESULTS.md`.
