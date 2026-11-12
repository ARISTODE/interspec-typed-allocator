# Memcached workload generator correction

Base: 6e164d3a62db94e4774345ee32f7d03cf3906bce. The earlier generator selects key `(op*104729)%keys` and GET `(op*37)%100 < get_percent`. With 10,000 keys, each key always receives the same operation type. Historical numbers are retained as **legacy**, not retrospectively relabeled as independently mixed traffic.

## Corrected mode

`independent-v1` uses separately domain-tagged, seeded counter hashes for key and operation-type choices. It removes the algebraic key/type coupling and provides reproducible pseudorandom mixing, not a mathematical independence or cryptographic guarantee. GET percentage is a target probability; finite samples need not have exactly that ratio. This is uniform key selection, not a popularity-skew model.

For fixed work, global operation IDs are exactly `[0,N)` across any number of clients or pipeline depth. Choice for each ID depends only on seed/mode/keys/GET target. Scheduling can change which thread sends each request and wire order. For timed runs, each worker uses disjoint IDs `ordinal*clients+worker`; scheduling changes how many requests each worker finishes. Thus a seed reproduces the indexed workload, not wall-clock execution or the exact timed request multiset.

Client invocation is backward-compatible:

`client PORT SECONDS CLIENTS PIPELINE VALUE_BYTES KEYS GET_PERCENT [TOTAL_OPERATIONS [WORKLOAD_MODE [SEED]]]`

Direct old invocations default to `legacy`. For timed corrected work, pass `0 independent-v1 20261109` after GET_PERCENT. Explicit legacy preserves the old fixed and per-thread timed sequence. Seed is ignored by legacy. Existing archived client binaries and results remain untouched.

The timing collector, matrix runner and diagnostic profiler now default explicitly to `independent-v1`, expose `--workload-mode` and `--workload-seed`, record them in raw output/environment/summaries/tables, and compile a client under each output directory instead of overwriting a shared archived client. The joined report refuses different timing/profile modes or corrected seeds; missing historical metadata is treated as legacy.

## Validation

- C++ regression tests cover 18 million requests across seeds 0, 20261109 and UINT64_MAX, GET targets 10/50/95%, and 10,000 keys. Each tested key received both GET and SET. All global GET counts passed a predeclared six-binomial-SD tolerance; conditional per-key tests passed a deliberately broad regression bound. These finite tests detect the old coupling, not prove randomness.
- Legacy formulas and per-thread IDs are tested directly for 100,000 indices.
- Fixed-work ID coverage and deterministic choices are tested across clients 1/8 and pipeline 1/10/16, including a partial final batch of 10,003 operations. Corrected timed worker IDs are disjoint. GET targets 0/100 and invalid mode are tested.
- Real InterSpec server smoke test: 18 runs covering both modes, clients/pipelines 1/1, 8/10 and 8/16, and 10/50/95% GET. Each completed exactly 5,000 validated responses. Server cmd_get/cmd_set matched independently computed expected counts across concurrency/pipeline changes.
- Metadata join tests reject legacy/corrected mixing and mismatched seeds; accept matching and historical legacy inputs.

Run unit/metadata checks through CTest targets `memcached_workload_test` and `memcached_workload_metadata`. The recorded integration harness and logs accompany the patch evidence archive.

## Evaluation consequences

All end-to-end timing variants and associated diagnostic profiles must be rerun for claims about independently mixed traffic. Do not pool corrected results with old runs, or change only one comparator. The corrected generator also changes client CPU work, so it needs a client-capacity/overhead sensitivity control. A shorter smoke run establishes functional validity, not a replacement performance result.

This correction does not establish that key/type coupling caused the old negative bars. Same-binary controls and matched copy diagnostics from the separate investigation already show the VM can produce apparent speedups without implementation changes. Dedicated-host, independently repeated balanced blocks, A/A controls and uncertainty remain necessary for publication-grade causal performance claims. No speedup mechanism has been established.
