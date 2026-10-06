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

We model memcached as the trusted compartment \(T\) and bipbuffer as the untrusted compartment \(U\). We assume the sandbox correctly isolates U from T memory; memcached, RLBox/wasm2c, InterSpec metadata, and the OS are trusted.

U may nevertheless be fully compromised and execute arbitrary behavior inside its sandbox. In particular, U may corrupt interface values returned to T, including pointers and lengths.

Our focus is therefore **interface safety after isolation succeeds**. A U-controlled pointer is unsafe if it refers to:

* an untracked address,
* a released allocation,
* an allocation of the wrong type, or
* a range that exceeds the tracked object.

General control-flow integrity, side channels, and substitution between two simultaneously live objects of the same trusted type are outside the current SP3 guarantee.

### 2.2 RLBox wasm2c isolation

We isolate bipbuffer with RLBox's **wasm2c** backend. The build performs the following transformation:

```text
bipbuffer C source
      ↓  wasi-clang
WebAssembly module (.wasm)
      ↓  WABT wasm2c
generated C implementing the Wasm module
      ↓  host C/C++ compiler
memcached + RLBox wrapper + wasm2c runtime
```

The generated module executes **in the same process** as memcached, but its pointers are 32-bit offsets into a separate Wasm linear-memory region. Wasm memory accesses are translated by the wasm2c runtime to that region, so U cannot directly dereference native memcached addresses.

For example, native memcached normally calls:

```c
unsigned char *p = bipbuf_peek_all(buf, &len);
```

After isolation, the trusted wrapper instead invokes the exported Wasm function through RLBox. The returned value is treated as a pointer into U's linear memory rather than as an ordinary trusted C pointer.

### 2.3 Copy-based boundary wrapper

The memcached integration uses an explicit **boundary wrapper** to preserve the original bipbuffer API while preventing memcached from directly consuming mutable U memory.

For a U → T read, `bipbuf_peek_all` works as follows:

```text
1. wrapper invokes bipbuf_peek_all() in U
2. U returns {pointer, length}
3. wrapper validates the sandbox address
4. InterSpec validates live allocation + type + extent
5. wrapper memcpy's [pointer, pointer + length) into T read_copy
6. memcached receives the trusted snapshot
```

For example, if U returns a pointer to 128 bytes of queued log data, T does not parse those 128 bytes in U memory. The wrapper first validates that the complete 128-byte range belongs to the expected live `bipbuf_t` allocation, copies it into `read_copy`, and returns the T-owned copy.

The T → U write path is symmetric:

* `bipbuf_request(size)` reserves space in U but returns T's `write_copy` buffer to memcached.
* memcached writes into `write_copy`.
* `bipbuf_push(size)` validates the U destination, copies `write_copy` into U, and then commits the write.
* `bipbuf_offer(data, size)` copies `data` into a persistent checked U character buffer before invoking the U operation.

Thus, RLBox provides memory isolation, while the wrapper defines exactly where data is copied and where InterSpec validation executes. For copied queue records, T subsequently parses a stable T-owned snapshot rather than data U can modify after validation.

### 2.4 Trusted typed allocator

RLBox can establish that a pointer is inside sandbox memory, but that alone does not show that it belongs to a **live allocation of the expected type and extent**. InterSpec therefore adds a T-controlled typed allocator for U memory.

At sandbox creation, the wrapper:

* reserves one contiguous region inside U's Wasm linear memory,
* creates an InterSpec `Runtime` over that region, and
* registers the inferred allocation-site-to-type policy.

The object bytes remain in U memory, but allocation metadata is stored only in T:

```text
{ base, size, type_hash, site_id }
```

#### Allocation-site provenance

U is not allowed to choose its trusted type. Policy generation rewrites each authorized allocation site to a **site-specific direct Wasm import**.

For memcached, the generated policy contains:

| Allocation site | Trusted type | Runtime SiteId |
| --- | --- | ---: |
| `bipbuf_new` allocation | `bipbuf_t` | 1048577 |
| input-copy helper | `char` | 1048578 |

Conceptually, the original allocation:

```c
malloc(sizeof(bipbuf_t) + size)
```

becomes a direct call to the import assigned to that source site:

```text
interspec_wasm_alloc_memcached_site_1(size)
```

The Wasm call passes only the requested size. The corresponding trusted host function already contains the SiteId, which T maps to the inferred type before allocation. A compromised U therefore cannot request memory and falsely label it as another trusted type.

#### Allocation and lifetime tracking

The runtime suballocates the reserved region using an 8-byte-aligned bump pointer and records each allocation in a T-side ordered map. Normal memcached operation tracks two persistent allocations per queue: the `bipbuf_t` object and the character input buffer.

* **allocate:** create `{base, size, type, site}` metadata.
* **release:** remove the allocation from trusted metadata.
* **reallocate:** allocate a new tracked object with the same trusted type/site and invalidate the old record.
* **lookup:** use the ordered allocation map to locate the object containing a returned pointer, including interior pointers.

Released addresses are not immediately reused by this prototype, simplifying stale-pointer detection.

### 2.5 SP3 enforcement

Before T consumes a U-controlled pointer, the wrapper performs:

1. **Sandbox confinement:** the pointer must resolve to U's Wasm linear memory.
2. **SP3 validation:** the pointer must lie in a live tracked allocation of the expected type, and the complete requested range must remain inside that allocation.

The runtime evaluates:

```text
check(pointer, requested_bytes, expected_type)
```

and returns `ok`, `untracked`, `wrong_type`, or `out_of_bounds`. A pointer whose allocation has been released is no longer present in trusted metadata and is therefore rejected as `untracked`.

| Corruption | Enforcement |
| --- | --- |
| Pointer outside sandbox | RLBox / wrapper confinement |
| Pointer to ordinary untracked U memory | InterSpec: `untracked` |
| Pointer to allocation of another type | InterSpec: `wrong_type` |
| Pointer to released allocation | InterSpec: `untracked` |
| Valid pointer with excessive length | InterSpec: `out_of_bounds` |
| Different live object of the same type | Outside current SP3 guarantee |

### 2.6 Native pointers in the LRU queue

Memcached's LRU bump records originally contain native `item *` pointers. Passing these T pointers through U would expose trusted addresses and cannot be made safe by validating only the outer bipbuffer.

The wrapper therefore keeps each native item pointer in T and sends only a one-use integer handle through U. On return, T:

* resolves the handle in the originating queue,
* verifies the associated item hash,
* consumes the handle to prevent replay, and
* only then recovers the native pointer.

This handling complements SP3: U-owned pointers are checked against trusted allocation metadata, while native T pointers are never exposed to U.
