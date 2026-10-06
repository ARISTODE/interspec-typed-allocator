# InterSpec Memcached Evaluation

This report uses memcached as a running case study to evaluate the cost and behavior of InterSpec. Additional applications will be added after matched end-to-end results are available.

## 1. Benchmark and Workloads

### 1.1 Memcached and the isolated module

We evaluate **memcached 1.6.45**. The trusted application is memcached \(T\), while its upstream **bipbuffer** implementation is isolated as the untrusted component \(U\) using the RLBox **wasm2c** backend.

Bipbuffer is used by memcached for:

* worker logging,
* watcher output, and
* asynchronous LRU item bump queues.

These paths make bipbuffer a useful compartment boundary because they exchange data with the main server during realistic cache workloads rather than through a synthetic test harness.

### 1.2 Isolation boundary

The upstream bipbuffer API exposes **13 C functions with 21 explicit parameters**.

| Property | Value |
| --- | ---: |
| Isolated module | `bipbuffer.c` |
| Isolation backend | RLBox `wasm2c` |
| Interface functions | 13 |
| Explicit parameters | 21 |
| Functions accepting a buffer handle | 12 |
| Functions returning pointers | 5 |
| Memcached uses | worker logs, watchers, LRU bumps |

Representative interface functions include:

* **Write path:** `bipbuf_request`, `bipbuf_push`, `bipbuf_offer`
* **Read path:** `bipbuf_peek`, `bipbuf_peek_all`, `bipbuf_poll`
* **State management:** `bipbuf_new`, `bipbuf_free`, `bipbuf_used`, `bipbuf_unused`

In the isolated deployment, the application-visible `bipbuf_t *` is an opaque trusted handle. The actual bipbuffer object and its data reside in U's Wasm memory.

### 1.3 Compared configurations

We compare three matched configurations:

* **Native:** ordinary memcached with the native bipbuffer implementation.
* **RLBox:** bipbuffer runs inside RLBox `wasm2c`; boundary marshalling and copying remain enabled, but InterSpec allocation tracking and SP3 checks are disabled.
* **InterSpec:** the same RLBox deployment with trusted typed allocation metadata and SP3 validation enabled.

This separates:

* the cost of compartment isolation, measured as **RLBox vs. Native**, and
* the incremental cost of InterSpec enforcement, measured as **InterSpec vs. RLBox**.

### 1.4 Primary workloads

We vary both application concurrency and protected-boundary activity. This distinction matters because high request throughput does not necessarily imply frequent interactions with U.

| Level | Clients | Pipeline | GET / SET | Value size | Boundary activity | Purpose |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| Light | 1 | 10 | 50 / 50 | 256 B | Low | Exposes fixed isolation costs with limited concurrency |
| Medium | 8 | 10 | 50 / 50 | 256 B | Moderate | Represents concurrent cache service under normal operation |
| Heavy | 2 | 2 | 50 / 50 | 256 B | High, watcher enabled | Continuously exercises protected worker and watcher queues |

**Light.** One client minimizes application parallelism, making fixed costs such as sandbox transitions and boundary handling easier to observe.

**Medium.** Eight clients preserve the same request mix while increasing concurrency, showing how isolation and validation costs behave under a more practical cache workload.

**Heavy.** The watcher subsystem remains active throughout the run, causing worker-log and watcher-output bipbuffers to be exercised continuously. We use moderate client pressure rather than maximum throughput so that the queue remains lossless.

### 1.5 Sensitivity workloads

We additionally use targeted workloads to test whether the result depends strongly on request composition:

* **Read heavy:** 8 clients, pipeline 16, 95% GET, 1 KiB values.
* **Write heavy:** 8 clients, pipeline 8, 90% SET, 256 B values.
* **Watcher light:** 1 client, pipeline 1, 50/50 GET/SET with an active watcher.

The primary light, medium, and heavy workloads form the main presentation. These sensitivity workloads are used to explain workload-specific behavior.

### 1.6 Validity and metrics

A watcher run is considered valid only when no protected work is silently dropped:

* `log_worker_dropped = 0`
* `log_watcher_skipped = 0`
* `lru_bumps_dropped = 0`

The primary metric is **throughput in Kops/s**. We additionally report:

* p99 response latency in **µs**,
* server CPU time in **µs/op**, and
* resident memory usage in **MiB**.

For final publication measurements, Native, RLBox, and InterSpec will be measured in paired repetitions on the same controlled host with identical workload parameters and disjoint server/client CPU affinity. Existing GitHub Actions results are treated as reference measurements for validating the experimental pipeline, not as final publication numbers.
