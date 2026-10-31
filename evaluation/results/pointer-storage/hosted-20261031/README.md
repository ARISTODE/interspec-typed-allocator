# Verified pointer-origin and behavioral-parity follow-up

**Status:** All five GitHub Actions workflows passed on implementation commit [`4b6b47c762cd87c6991232339c6a6a137d194f8b`](https://github.com/ARISTODE/interspec-typed-allocator/commit/4b6b47c762cd87c6991232339c6a6a137d194f8b). The paper repository has not been changed. Generated on 2026-10-31 UTC.

This is diagnostic evidence for four **instrumented** compartment boundaries. It does not establish coverage of all ten boundaries in the InterSpec paper or every pointer internal to U. Counts are pointer-use observations at selected boundary adapters, not unique objects. T pointers in these examples are copied or tokenized; their numerical addresses do not cross raw into U.

## Normal-workload storage observations

| Boundary | T current stack | T stack-labeled VMA | T ELF image/static region | T brk heap VMA | T anonymous VMA | SP3-accepted U allocation | Total |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| rsync/popt | 15 | 19 | 2232 | 1 | 0 | 35 | 2302 |
| YAML/libyaml | 0 | 0 | 0 | 0 | 2 | 1024 | 1026 |
| nginx/PCRE | 176 | 0 | 0 | 24500 | 0 | 13088 | 37764 |
| memcached/bipbuffer | 1241 | 0 | 26 | 0 | 261 | 468 | 1996 |

The **stack-labeled VMA** category does not identify its owning thread. The **ELF image/static region** category includes readable nonexecutable ELF segments and does not prove a particular pointer refers to a named global. The **brk heap VMA** and **anonymous VMA** categories do not identify individual allocation bases, extents, types, or live lifetimes. The expanded Linux VMA observations classify formerly unknown addresses in these workloads, but they are **not** substitutes for the trusted SP3 allocation metadata table. `t_adapter_only` events are local trusted references, not raw pointer values sent to U.

Each application summary in [summary.json](summary.json) retains event direction and boundary site, per-case raw stderr SHA-256, category breakdown, and the exact source commit. These results must not be presented as the number of distinct stack or global variables.

## U stack and global source-injection denial tests

The diagnostic/fault-only memcached WASM module creates two explicitly adversarial return candidates: a U static-duration array and an escaped U stack-local address. Three execution roles times three checked return targets times two origins yield **18 tests**. Every test returned the expected SP3 `untracked` rejection before trusted-side copying, with a rejected census event. The independent verifier reparsed each saved stderr log, confirmed its SHA-256, the injecting source mode, rejection reason, and checked site. The normal 50-case memcached correctness gate passed before these tests.

These negative tests show **fail-closed handling** for two U pointer origins; they do **not** measure natural prevalence, grant support to legitimate U stack/global pointers, or prove comprehensive stack/global tracking.

## Five-repeat memcached pointer frequency study

A fixed client-operation workload was run five times per scenario, producing **30 traces** with **338,603 independently verified pointer events**. Preload, startup, and watcher initialization are excluded from each observation interval; a fixed 0.5-second asynchronous drain is included. Counts are normalized per **1,000 completed client operations**.

| Scenario | Client ops per run | Repetitions | Median events/1k ops | Observed range | Population SD |
| :--- | ---: | ---: | ---: | ---: | ---: |
| balanced_1c | 2500 | 5 | 69.6 | 69.6 to 88.0 | 7.4 |
| balanced_8c | 2500 | 5 | 72.0 | 72.0 to 72.0 | 0.0 |
| read_heavy_1k | 2500 | 5 | 640.8 | 620.8 to 1040.0 | 190.7 |
| write_heavy | 20000 | 5 | 39.6 | 39.6 to 39.6 | 0.0 |
| watch_light | 2500 | 5 | 15531.6 | 15170.8 to 15856.0 | 286.3 |
| watch_moderate | 2500 | 5 | 10339.2 | 10260.8 to 10356.0 | 37.3 |

These diagnostic event rates are **not** runtime overhead measurements. Internal watcher and LRU activity may generate many pointer events per client request, and asynchronous scheduling still causes dispersion. The raw trace hashes, full per-site normalized distributions, samples, environment/build provenance, and original loss-counter snapshots are in the `pointer-origin-repeats` subdirectory of the memcached workflow artifact. The independent verifier recomputed every site and storage rate, statistic, and sample hash, and checked zero client errors, no unexpected SP3 rejection, and zero monitored queue-loss deltas.

## Behavioral regression gates

1. **rsync/popt:** six native-versus-isolated correctness workloads, observable output and manifest comparisons, SP3 corruption probes, and parity audit.
2. **YAML/libyaml:** native/isolated semantic signatures and document correctness variants, with the parity audit.
3. **nginx/PCRE:** 24 native/isolated cases covering request responses, corruption, multiworker operation, and reload, with the parity audit.
4. **memcached/bipbuffer:** 50 normal/corruption/upstream application checks, six-scenario four-variant performance matrix, independent evidence validators, plus the 18 new source-injected denial tests.

These validate behavior on the **tested workloads**, not whole-program equivalence. Timed performance measurements remain separate from the pointer census.

## Hosted provenance

Implementation commit: `4b6b47c762cd87c6991232339c6a6a137d194f8b`.

1. [ci](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/41172235035): **success**.
2. [p10](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/41172235015): **success**.
3. [yaml](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/41172234996): **success**.
4. [nginx](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/41172235005): **success**.
5. [memcached](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/41172234985): **success**.

| Artifact | GitHub artifact ID | SHA-256 digest |
| :--- | ---: | :--- |
| rsync | 13031865918 | `sha256:fc41cc2e7ba8c703bac988a955589dfad71042630e35a3514edaa17202578a32` |
| yaml | 13032475355 | `sha256:d1644522255343127bfb7614e7a1cd5e2a898f9730d9280c8db0bbaa8ad9eb98` |
| memcached | 13032266700 | `sha256:996ab18e38bd26f0fd5b7574e86c4aa3a434769215847e5d54f91ab6c2beeb90` |
| nginx | 13032641854 | `sha256:bdb624ff450db56d44f400fc98b3d704554f0486b28ae14ce2a9ba1b90e0ad3e` |

See [summary.json](summary.json) for complete per-site statistics and [initial-pass.json](initial-pass.json) for the preceding exploratory run on commit `cbfdb80afbf3f14064bd2b8053f77687440f7739`, which also passed all five workflows but preceded the independent verifiers and stack-category label clarification.

The implementation and reproducibility protocol are in [evaluation/experiments/pointer-storage-followup-20261031.md](../../../experiments/pointer-storage-followup-20261031.md) and the source scripts under `tools/`.

## Remaining boundaries and guarantees

Pointer objects in global/stack storage still require explicit trusted metadata registration, domain/lifetime rules, and normal-workload coverage evidence before we can claim support. Named globals cannot be proved from a broad ELF segment membership check; anonymous regions cannot be treated as typed allocations. Interior-struct and struct-pool pointer validation, expected type inference for `void*` or unions, and comprehensive temporal safety are separate unfinished items. The current SP3 type/spatial guarantee is limited to allocation records that the runtime actually tracks.
