# Evaluation completion ledger

This ledger starts from the source and evidence audit of 10 October 2026.
Completion means a reproducible implementation, successful execution, retained
raw evidence, independent validation and visible results. Implemented scripts
or green build jobs alone do not close a measurement task. Historical datasets
remain separate from new experiments. No missing cell is assigned zero.

| Item | Acceptance evidence | Current status |
| --- | --- | --- |
| 1. Memcached tracking comparison | All six scenarios and four variants from one paired experiment; 50 case correctness gate; matched binary hashes; all responses valid; zero logger, watcher and LRU drops; recomputed summaries and tracking table | Collection and independent validator implemented; new execution pending |
| 2. Write workload protected coverage | Fixed declared workload and count; observed successful protected checks and LRU activity; exact measured trace interval; preload excluded; zero drops; raw trace and count reconciliation | Longer fixed profile and independent trace verifier implemented; new execution pending |
| 3. wasm2c cost breakdown | Repeated empty native and sandbox calls, mutex, confinement, copies at 64/256/1024/4096 bytes, complete buffer operations; raw samples; functional and anti-elision controls | Separate measurement modules and collector implemented; native functional control passed locally; wasm2c execution pending |
| 4. Boundary activity | Actual sandbox invocations and bytes copied in both directions per validated client operation; diagnostic instrumentation compiled out of timed builds; independently counted evidence | Diagnostic instrumentation and independent recount implemented; new execution pending |
| 5. Publication measurements | Controlled hardware and power configuration; disjoint CPU placement; adequate load generator capacity; matched builds and inputs; documented warmups and repetition counts; variation, latency, CPU and memory; application and microbenchmarks on same host | Pending; a suitable host has not been established |
| 6. Original paper row provenance | Every claimed boundary/workload tied to source and binary revisions, policy configuration, raw repetitions and reproducible arithmetic; unresolved rows excluded from verified claims | Pending |
| 7. Policy and coverage reconciliation | Effective SP1/SP2/SP3 ablations; generated wrapper coverage review; source-bound analysis census and reproducible field/origin transformations | Pending |
| 8. Original PoCs | Observed executions of allowed and blocked controls; exact binary, configuration and source binding; preserved stdout/stderr and exit status | Pending |

## New memcached experiment

CI collects five paired repetitions of all four variants for each scenario,
with one second warmup and three seconds of measured traffic. This is an
expanded hosted reference, not the controlled publication protocol.

`verify_memcached_matrix.py` reads raw samples, per-run server statistics,
environment/build manifests and the correctness gate. It checks the exact
scenario/variant/repetition matrix, all loss counters including tracking,
response validation, workload identity, source cleanliness, binary bindings,
throughput and CPU arithmetic, latency ordering, all summary statistics and
paired overheads. Its output retains per-pair percentages and source hashes.
Regression tests deliberately remove or duplicate pairs, introduce tracking
loss, alter binary identities and corrupt client counts or reported results.

No new measurement is marked complete until the CI artifact is downloaded,
its GitHub digest is checked, and the independent verifier passes locally.
The source commit, run URL and result table will then be recorded here.

## Diagnostic and boundary experiments

The write profile declares 200,000 operations over 10,000 keys before execution.
Other profiles retain a 512 key cap and use 5,000 operations. The trace interval
excludes preload and includes the documented asynchronous drain. Valid write
coverage requires successful SP3 checks, actual LRU hold/take events, increased
LRU moves and zero losses. A failed profile is retained and fails the workflow;
there is no retry until a favorable observation appears.

The boundary experiment uses the real upstream bipbuffer and production bridge
with separate modules that export an empty call only for measurement. There are
98 configurations and seven repetitions, with raw process outputs and content
controls. No microbenchmark sum is treated as an application overhead estimate.
The independent verifier checks 686 expected raw cells, arithmetic, functional
checksums, process output identity and all summary statistics.

The current local environment reports an eight CPU cgroup quota and no visible
frequency governor. It is not established as a dedicated controlled host.
