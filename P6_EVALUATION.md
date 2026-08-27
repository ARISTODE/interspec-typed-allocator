# P6 Evaluation

P6 evaluates the typed allocator as a security mechanism, a runtime data structure, and a reproducible research artifact. The evaluation is intentionally tied to the claims implemented by this repository. It does not claim complete memory safety for arbitrary sandboxed code.

## 1. Security evaluation

`evaluation/security_eval.cpp` emits one CSV row for each enforced property and exits nonzero if any observed result differs from the expected result.

The evaluated cases are:

• a tracked pointer with the expected type is accepted

• an interior pointer remains valid only while the requested access remains within the same tracked allocation

• a pointer to a different tracked type is rejected as `wrong_type`

• an access that crosses the allocation boundary is rejected as `out_of_bounds`

• a pointer with no trusted allocation record is rejected as `untracked`

• release requires the exact allocation base

• a released pointer is rejected

• successful reallocation invalidates the old pointer and preserves the trusted type on the replacement allocation

• failed reallocation leaves the old allocation live, preserving C realloc failure semantics

• unknown TypeIds and zero sized typed allocations are rejected

• duplicate TypeHash registration is rejected

• an arena whose address range wraps around is marked invalid and cannot allocate

The RLBox + NaCl CI job provides the end to end counterpart to this unit level matrix. It executes the real bundled popt parser as U while the complete rsync executable remains T. Returned U pointers are mediated by the same trusted allocation metadata before rsync consumes them.

## 2. Runtime performance evaluation

`evaluation/runtime_bench.cpp` reports CSV records with these fields:

```text
metric,population,threads,operations,total_ns,ns_per_op,ops_per_sec
```

It measures four read side operations across live allocation populations of 1, 16, 256, 4096, and 16384 objects:

• correct type pointer checks

• interior pointer checks

• wrong type rejection

• remaining allocation extent lookup

It also reports typed allocation cost for 16384 objects and read only check throughput with 1, 2, 4, and 8 trusted threads over a 4096 object metadata set.

The benchmark does not enforce a fixed latency threshold in CI because hosted runner timing is noisy and hardware dependent. CI verifies that the benchmark builds and completes. Numeric results are artifacts for comparison across controlled runs, not a pass or fail security condition.

The environment variable `INTERSPEC_BENCH_ITERATIONS` controls repetition count. The default is 200000 iterations for each single threaded lookup measurement.

## 3. Scalability claim

The runtime stores live allocations in `std::map<uintptr_t, Allocation>` and locates the containing allocation with `upper_bound`. The expected lookup complexity is therefore O(log n) in the number of live tracked allocations. The benchmark population sweep is intended to expose the practical constant factors and growth trend of that design.

P5 already includes a 10000 allocation correctness stress test and an eight thread concurrent metadata stress test. P6 keeps those tests in the required test suite and adds timing output rather than replacing correctness tests with benchmarks.

## 4. Application level evaluation

The required application regression remains the P4c rsync path:

```text
complete rsync as T
        ↓
InterSpec popt bridge
        ↓
real bundled popt as U
        ↓
RLBox + NaCl
        ↓
trusted typed allocation metadata
        ↓
validated pointer results returned to rsync
```

CI requires both representative option parsing and a normal local transfer startup path to complete successfully. This demonstrates compatibility with a real trusted application path while the parser executes in the sandbox.

This is not an exhaustive rsync evaluation. Daemon mode, remote shell mode, authentication paths, host popt configuration aliases, and every optional build feature remain outside the demonstrated scope.

## 5. Reproducible evaluation command

Run:

```bash
chmod +x scripts/run_p6_evaluation.sh
./scripts/run_p6_evaluation.sh
```

The command produces:

```text
p6-results/ctest.txt
p6-results/security.csv
p6-results/runtime.csv
p6-results/environment.txt
```

For the full RLBox + NaCl application path, also run:

```bash
chmod +x scripts/run_rlbox_nacl_poc.sh
./scripts/run_rlbox_nacl_poc.sh
```

## 6. Interpretation boundaries

The security result should be interpreted as evidence for the implemented Extended SP3 properties: trusted type provenance, allocation bounded spatial validation, and logical liveness while addresses are not reused.

The current pointer representation remains an ordinary raw sandbox pointer. The runtime intentionally avoids physical address reuse because reuse without a temporal tag can create an ABA style stale pointer problem. A future allocator that reclaims addresses would need a generation or tagged pointer mechanism before making the same temporal safety claim.

The runtime does not prove that U selected the semantically intended allocation site merely because the allocation has a registered type. The trusted mapping prevents U from forging a TypeHash, but stronger allocation site or control flow provenance remains a separate extension.
