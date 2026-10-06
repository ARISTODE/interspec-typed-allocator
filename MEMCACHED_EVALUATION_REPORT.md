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


## 2. Threat Model and Implementation

### 2.1 Threat model

We model memcached as the trusted compartment \(T\) and bipbuffer as the untrusted compartment \(U\). We assume the RLBox sandbox correctly prevents U from directly reading or writing T memory. The trusted computing base includes memcached, RLBox and its wasm2c runtime, the InterSpec runtime and metadata, and the OS.

U may nevertheless be fully compromised by a memory-safety or concurrency bug and may execute arbitrary behavior within its sandbox. In particular, U may corrupt values returned across the interface, including pointers and lengths.

Our focus is therefore **interface safety after isolation has already succeeded**. A pointer can remain inside U's sandbox and still be unsafe for T to consume if it refers to:

* an untracked address,
* a freed allocation,
* an allocation of the wrong type, or
* a valid allocation with an extent that exceeds the object boundary.

Side channels, general control-flow integrity, and substitution between two simultaneously live objects of the same trusted type are outside the current SP3 guarantee.

### 2.2 RLBox wasm2c isolation and data transfer

We use RLBox's **wasm2c** backend. Bipbuffer is compiled to WebAssembly and executed in an isolated Wasm linear-memory region inside the memcached process. T invokes U only through the RLBox boundary; U cannot directly dereference native memcached pointers.

The deployment retains explicit copy-based data transfer:

* **T → U:** `bipbuf_request/push` uses a trusted `write_copy` staging buffer, and `bipbuf_offer` copies input into a sandbox allocation.
* **U → T:** `bipbuf_peek`, `bipbuf_peek_all`, and `bipbuf_poll` return a U pointer; T validates the pointer and copies the requested bytes into a trusted `read_copy` buffer before parsing them.
* **Object handle:** the `bipbuf_t *` visible to memcached is an opaque T-side handle. The actual `bipbuf_t` object resides inside the Wasm sandbox.

For example, a read from the isolated queue follows:

```text
bipbuf_peek_all() in U
        ↓
U-controlled pointer + length
        ↓
sandbox confinement check
        ↓
InterSpec allocation/type/extent check
        ↓
memcpy(U → T read_copy)
        ↓
memcached consumes stable T data
```

Copying prevents T from parsing data that U can modify concurrently after validation.

### 2.3 Why a trusted typed allocator is required

RLBox confinement establishes that a pointer belongs to sandbox memory, but not that it refers to the **intended live object**. A compromised U could redirect a pointer to another address in the same sandbox and still pass a sandbox-range check.

InterSpec therefore reserves a typed region inside U's Wasm memory and lets T manage suballocations. For every live allocation, T records trusted metadata:

```text
{ base, size, type_hash, allocation_site }
```

U may read and write the object bytes, but cannot modify this metadata.

Allocation types are not selected by U. Each authorized allocation site is assigned a trusted SiteId during policy generation. In the wasm2c backend, the site is represented by a dedicated direct Wasm import whose trusted host wrapper embeds that SiteId. U supplies the requested size; T maps the SiteId to the inferred type before creating the allocation record.

In the normal memcached queue, two persistent typed allocations are tracked:

* the `bipbuf_t` object, inferred from the upstream allocation site, and
* a persistent character buffer used for T → U input copying.

This keeps allocation/lifetime bookkeeping off the per-record hot path.

### 2.4 SP3 enforcement

Before T consumes a U-controlled pointer, the bridge performs two levels of validation.

1. **Sandbox confinement:** the pointer must refer to valid Wasm sandbox memory.
2. **InterSpec SP3:** the pointer must belong to a live tracked allocation of the expected type, and the complete requested byte range must remain inside that allocation.

The runtime therefore evaluates:

```text
check(pointer, requested_bytes, expected_type)
```

and returns one of `ok`, `untracked`, `wrong_type`, or `out_of_bounds`. A pointer to a released allocation becomes `untracked`.

| Corruption | Enforcement |
| --- | --- |
| Pointer outside sandbox | RLBox / bridge confinement |
| Pointer to ordinary untracked U memory | InterSpec: `untracked` |
| Pointer to allocation of another type | InterSpec: `wrong_type` |
| Pointer to released allocation | InterSpec: `untracked` |
| Valid pointer with excessive length | InterSpec: `out_of_bounds` |
| Different live object of the same type | Not prevented by current SP3 |

### 2.5 Native pointers in the LRU queue

Memcached's LRU bump records originally contain native `item *` pointers. Passing these T pointers directly through U would violate the isolation boundary and would not be made safe by checking only the outer bipbuffer.

Our deployment therefore keeps each native item pointer in T and passes a one-use integer handle through U. On return, T:

* resolves the handle in the originating queue,
* verifies the associated item hash,
* consumes the handle so it cannot be replayed, and
* only then recovers the native pointer.

This application-specific handling complements SP3: the generic allocator validates U-owned pointers, while native T pointers are never exposed to U in the first place.
