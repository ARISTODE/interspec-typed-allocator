# Complete memcached deployment

This integration runs the actual memcached 1.6.45 server at revision
`2d51e364799bc9698bd4b11728ea978cea12da6e`. The cache server is T; its bundled
bipbuffer implementation is U, compiled into an RLBox wasm2c sandbox.
The deployment includes the cache server and asynchronous `watch` subsystem.
The supported build disables extstore and proxy; TLS and SASL are not enabled.

## Boundary and enforcement

Memcached uses bipbuffer for worker log queues and watcher output queues, not
for its ordinary key/value item storage. A GET/SET-only benchmark without an
active watcher is therefore a control workload with little boundary activity.
The `watch_active` workload exercises the protected path throughout the run.

Each queue has its own sandbox, typed arena, trusted metadata, mutex, and
separate T read/write staging buffers. Existing memcached locks still govern
its request/push and peek/poll sequences. The bridge serializes U execution
and copies returned bytes into T while holding its lock; the logger then
parses that stable snapshot. T never passes its host pointers into U.

| Operation | T bridge behavior |
| --- | --- |
| `bipbuf_new` | Creates a sandbox and returns an opaque T handle; registers the existing generated allocation policy |
| `bipbuf_request` / `bipbuf_push` | Checks the U destination range, exposes T staging memory to the caller, checks the destination again before copying and committing |
| `bipbuf_offer` | Copies T input into a persistent, checked character allocation in U |
| `bipbuf_peek_all` / `bipbuf_peek` / `bipbuf_poll` | Checks returned pointer type, live allocation membership, and requested extent before copying into T |
| `bipbuf_free` | Releases tracked metadata and destroys the queue's entire sandbox |

The normal path creates two tracked allocations per sandbox: the real
`bipbuf_t` allocation and a persistent input-copy allocation. It does not make
new typed allocations per log record. Watcher churn destroys whole arenas,
so it does not consume one process-global arena indefinitely. Per-arena
addresses remain unreused; this does not add a general-purpose reclaiming
allocator to the core runtime.

The byte-copy check alone does not validate log contents. `logger_validate.h`
checks record lengths, event indexes, key extents, string termination, and
indexes used by the existing parsers. It copies records to aligned T storage
before parsing. These application checks are shared by all sandboxed variants
and are distinct from the SP3 allocation checks. Valid same-type substitutions
and semantically false but structurally valid log entries remain outside SP3's
guarantee. Rejection aborts the server; availability against a malicious U is
not claimed.

This is a bridge for memcached's existing uses, including opaque handles
created through `bipbuf_new`. It is not a general binary-compatible substitute
for arbitrary callers that initialize a native `bipbuf_t` in their own memory.

## Build and validate

On Linux x86-64, install GCC/G++, Git, Python 3, CMake 3.30 or newer compatible
with the pinned backend, Autoconf, Automake, libevent development headers, Perl,
and the IO::Socket::INET6 Perl module. The script downloads pinned RLBox,
wasm2c, WASI SDK, and memcached dependencies.

```sh
bash scripts/build_memcached_deployment.sh
python3 tools/test_memcached_deployment.py --out results/memcached/correctness
```

`INTERSPEC_MEMCACHED_WORK` overrides the build directory; pass the same path as
`--work` to the Python tools. `INTERSPEC_WASM_DEPS` can reuse a prepared,
backend-patched P9/P10 checkout with the exact pinned dependency revisions.

The build produces native, RLBox-only, tracking-without-SP3-checks, full SP3,
and diagnostic servers, plus native/SP3 debug servers for upstream tests.
Release variants have neither trace logging nor fault injection compiled in.
The RLBox-only module uses ordinary U allocation, with no typed arena,
allocation registration, or typed allocation imports. All sandboxed variants
retain basic sandbox confinement, staging limits, and log-format validation.

The correctness matrix comprises:

* Five server variants, each checked against explicit expected cache results,
  binary values, CAS, expiry, malformed commands, watcher records, concurrent
  cache traffic, and watcher churn.
* Twenty-four source-injected pointer attacks: two queue roles, three actual
  server paths, and four errors per path.
* Two same-type substitution controls and one malformed log-record control.
* Upstream `watcher.t` and `watcher_connid.t` for native and SP3 debug servers.
  Their 47 assertions are unchanged; their copied launch helper selects
  loopback TCP so the suite also runs where Unix sockets are unavailable.

Raw stdout/stderr and machine-readable results are retained separately.
Each summary records the tested binary hashes. Performance collection refuses
an incomplete/failing correctness suite or binaries changed since validation.

## Inspect an injected rejection

The diagnostic binary accepts these environment variables, interpreted by T
only to configure the test. The corruption itself is compiled into U.

| Variable | Values |
| --- | --- |
| `INTERSPEC_TEST_ROLE` | `1` worker queue; `2` watcher queue |
| `INTERSPEC_TEST_TARGET` | `1` request/write; `2` peek/read; `3` poll/consume |
| `INTERSPEC_TEST_FAULT` | `1` wrong type; `2` untracked; `3` released; `4` excessive extent; `5` same-type control; `6` invalid event field |
| `INTERSPEC_TRACE` | `1` enables diagnostic metadata and copy events |

Modes 5 and 6 are evaluated on target 2; malformed event contents are evaluated
on the worker queue. The runner drives real socket traffic and verifies the
expected rejection and process exit. The diagnostic module and its export
never appear in the timed release binary.

## Performance collection

```sh
python3 tools/benchmark_memcached.py \
  --out results/memcached/performance \
  --correctness-summary results/memcached/correctness/summary.json \
  --seconds 30 --warmup 5 --repetitions 15 \
  --clients 4 --pipeline 8 --value-bytes 256 --keys 1024 --get-percent 50
```

The driver randomizes variant order reproducibly within each paired repetition,
starts fresh servers, preloads identical keys, warms up, and validates every
response. It records throughput, p50/p95/p99 response latency, server CPU time,
RSS/high-water RSS, startup readiness time, and logger loss counters. It runs
both `cache_only` and `watch_active`. Timed runs use equal worker/watcher buffer
sizes of 1 MiB / 4 MiB across variants. Raw samples, stats, binary hashes, host
details, CPU affinity/quota, and frequency-policy metadata accompany summaries.

Latency is measured from a pipelined batch send to each response's completion;
it includes client-observed queueing and is not an open-loop latency estimate.
CPU stats are sampled around the run and final logger drain, so CPU per operation
includes deferred logging. Readiness polling has 20 ms resolution. RSS is
sampled after the workload; `VmHWM` records its process high-water mark.

Positive paired throughput loss means slower throughput:
`100 * (1 - variant_ops_per_s / baseline_ops_per_s)`.
Compare SP3 against native for deployment cost, against RLBox-only for the
increment beyond the sandboxed bridge, and against tracking-only for the
increment from SP3 checks. Those components are not additive.

Shared-container and hosted-CI measurements are pilot/reference data. For
paper results, run on controlled hardware with disjoint server/client CPU
affinity (`--server-cpus`, `--client-cpus`), verify the client is not the
bottleneck, retain loss counters, and vary concurrency, value size, read/write
mix, and duration. Report run-level variation and uncertainty. Do not treat a
throughput gain caused by dropped log records as lower enforcement overhead.
Distributed-client saturation measurements and longer resource tests remain
additional evaluation work.
