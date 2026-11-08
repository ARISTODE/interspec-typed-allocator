# Evaluation completion ledger

This ledger starts from the source and evidence audit of 10 October 2026.
Completion means a reproducible implementation, successful execution, retained
raw evidence, independent validation and visible results. Implemented scripts
or green build jobs alone do not close a measurement task. Historical datasets
remain separate from new experiments. No missing cell is assigned zero.

| Item | Acceptance evidence | Current status |
| --- | --- | --- |
| 1. Memcached tracking comparison | All six scenarios and four variants from one paired experiment; 50 case correctness gate; matched binary hashes; all responses valid; zero logger, watcher and LRU drops; recomputed summaries and tracking table | Validated hosted reference: run 38092306794, 120 samples, all loss and binary gates passed |
| 2. Write workload protected coverage | Fixed declared workload and count; observed successful protected checks and LRU activity; exact measured trace interval; preload excluded; zero drops; raw trace and count reconciliation | Validated diagnostic: 200,000 operations, 2,070 SP3 checks, 1,000 LRU hold/take pairs, zero drops |
| 3. wasm2c cost breakdown | Repeated empty native and sandbox calls, mutex, confinement, copies at 64/256/1024/4096 bytes, complete buffer operations; raw samples; functional and anti-elision controls | Validated hosted reference: 98 configurations, seven repetitions, 686 raw samples independently recomputed |
| 4. Boundary activity | Actual sandbox invocations and bytes copied in both directions per validated client operation; diagnostic instrumentation compiled out of timed builds; independently counted evidence | Validated diagnostic: all six profiles independently recounted from exact raw trace intervals |
| 5. Publication measurements | Controlled hardware and power configuration; disjoint CPU placement; adequate load generator capacity; matched builds and inputs; documented warmups and repetition counts; variation, latency, CPU and memory; application and microbenchmarks on same host | Pending; a suitable host has not been established |
| 6. Original paper row provenance | Every claimed boundary/workload tied to source and binary revisions, policy configuration, raw repetitions and reproducible arithmetic; unresolved rows excluded from verified claims | Pending |
| 7. Policy and coverage reconciliation | Effective SP1/SP2/SP3 ablations; generated wrapper coverage review; source-bound analysis census and reproducible field/origin transformations | Pending |
| 8. Original PoCs | Observed executions of allowed and blocked controls; exact binary, configuration and source binding; preserved stdout/stderr and exit status | Pending |
| 9. SP3 security delta | Preregistered H1/H2 application comparators; healthy legitimate controls; T sanitizer and protocol outcomes; post-scenario correctness gates; hash-checked raw evidence; independent replay | Primary case matrix executed and independently verified: H2 memcached interior-pointer harm prevention confirmed against domain-only; H2 libyaml project-authored T-driver mechanism confirmed; H1 YAML 3 no-delta/2 inconclusive, rsync 10 no-delta/6 inconclusive, nginx 8 no-delta/7 bridge-guarded, memcached 2 no-delta/8 inconclusive. No global H1 equivalence claim. Separately labeled pointer-census confirmation is pending CI rerun. |

### Extended-SP3 security delta evidence

[Workflow 42423558556](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/42423558556)
preserves 12 memcached H2 executions and two passing post-scenario 50-case
gates. The independent verifier was also rerun locally against its downloaded
raw evidence and passed. In the injected `item* + 1` case, the domain-only
predicate accepted the forged T pointer and a trusted ASan report followed;
Extended SP3 rejected before use. The original application-specific one-use
handle also prevented the corruption. The `item* + 65536` case had no observed
baseline harm and its harm-prevention delta is inconclusive.

The separately verified H1 YAML artifact contains 15 executions. Modes 1,
2, and 5 matched legitimate output, while modes 3 and 4 changed output but
had no T sanitizer report. Mode 4 also refutes the plan's assumption of a
T-specific scalar-length cap on that bridge. The first H1 memcached
instrumented fault-binary legitimate cases hit a logger-format rejection,
so they are not healthy controls despite the separate 50/50 application
gate. A later sanitized-source correction and valid run are documented below.
No paper guarantee or numerical claim is changed by the inconclusive cases.
Results and artifact
links are tracked in [`SP3_SECURITY_DELTA_RESULTS.md`](SP3_SECURITY_DELTA_RESULTS.md).

The independently replayed
[rsync H1 run 42425295349](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/42425295349)
preserves 48 fault-comparator executions. Ten matched the legitimate
filesystem and stdout; six were inconclusive, and no trusted sanitizer error
was observed. Nginx's first 45 cases aborted on a native startup UBSan
nonnull-attribute diagnostic in an upstream zero-byte copy before the PCRE
boundary was exercised. The failed evidence is retained, and the corrected
run below is used instead.

The corrected [nginx H1 run 42425810424](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/42425810424)
preserves 45 cases covering 15 PCRE fault scenarios. Eight showed no
observable delta and seven were rejected by existing trusted bridge
validation; none produced a trusted sanitizer error. The raw artifact passed
independent local replay with the stricter incomplete-control check. The
earlier invalid startup-sanitizer run is retained separately and does not
contribute to the conclusions.

Run [42425295349](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/42425295349)
additionally provided 12 H2 libyaml T-context executions. Actual libyaml
read-handler invocation and RLBox domain checking verified rejection of
untracked, revoked, wrong-type, and identity-mismatched registered T objects;
plain same-type substitution remained accepted. The mutation is modeled in
project-authored trusted test code, not an observed upstream U return.
The same run's H1 memcached role-1 legitimate comparator still rejected
logger format under additional tracing, so those eight cases remain invalid
and are not folded into no-delta counts. A fail-fast healthy-control smoke
and separated optional census logging were evaluated in the subsequent
passing run below.

The [new H1 smoke run 42427415881](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/42427415881)
failed both no-fault controls even without pointer census. Archived configure
logs reveal that ASan/UBSan enables the upstream memcached `NEED_ALIGN` path,
where a missing pair of parentheses in the logger's padding expression
produces invalid records. The next security-only build corrects this upstream
alignment arithmetic in its copied logger source. The trusted format check
remains enabled; the older failed controls remain archived as invalid.

The [corrected SP3 run 42427969783](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/42427969783)
subsequently passed all five dedicated workflow jobs and archived
[40 memcached H1 raw executions](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/42427969783/artifacts/13597002131).
Both fault-disabled legitimate binaries were healthy; ten subsequent 50-case
correctness gates passed, and all ten Extended rejection expectations matched
the pre-registered predictions. The stricter independent verifier replayed the
downloaded evidence and classified **two no-observed-delta, eight
inconclusive, zero trusted sanitizer harm, and zero invalid controls**.
Extended-SP3 rejection-code predictions all matched, but the preregistered
RLBox-only expectation that T would keep serving was contradicted in five
H1 modes (1, 3, 4, 9, 10): the existing T logger or staging validator
aborted. This behavioral deviation is recorded separately rather than
conflated with Extended check outcomes.
The same artifact contains 12 H2 LRU executions and two more passing 50-case
gates, plus 12 H2 libyaml T-driver executions, also independently replayed.
The planned census-labeled repeat remains separate from these primary results.
The observed results cannot justify a global claim that Extended SP3 is
unnecessary for all U-domain pointers, nor a stronger T-domain guarantee
than an already-deployed application-specific one-use handle.

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

## Validated completion evidence

The first four items are complete as hosted reference or diagnostic evidence.
They are not controlled publication measurements. The fresh runtime reference
also contains 195 verified samples across all 39 configurations.

[Run 38092306794](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/38092306794)
passed every job step. Source branch commit is `2f005c7641fda32c47511c1fc94a92acf08f5623`;
the executed merge is `d1546785002fc9f9005d2d17360bddaf4839e4a4`.
Both resolve to source tree `5e020bd09cc8bd3efe7c0d17290a0ebaad612506`.
The artifact digest matched GitHub:
`05644f047af9c0e25d8995e7447b934f3f16ecb59d383aed124dea3d36545fe8`.
The archive was downloaded and its matrix, profiles, boundary samples and
runtime rows independently recomputed locally. All 50 application cases passed.

[All result tables](evaluation/results/completion/hosted-38092306794/performance-report.md),
[boundary measurements](evaluation/results/completion/hosted-38092306794/boundary-results.md),
[activity report](evaluation/results/completion/hosted-38092306794/activity-report.md)
and [source manifest](evaluation/results/completion/hosted-38092306794/manifest.json)
link to the retained evidence. The private explorer preserves the complete
original artifact and every trace, plus charts and all result tables.

The earlier first pass, run 38091669296, independently passed the complete
120 sample matrix. Its artifact digest was
`1893674b2d4354deaf36ee5e207741bb3f818a4f6cf72c5832a2a28065a44c57`.
It remains a separate experiment rather than being combined with the final run.
The original NaCl artifact from run 37840970704 was also recovered: its 56 raw
samples and four summaries were independently verified, closing the earlier
artifact retrieval gap. This does not make NaCl timings interchangeable with
wasm2c timings.

Next: identify a suitable dedicated host and follow
[CONTROLLED_EVALUATION.md](CONTROLLED_EVALUATION.md). Items 5 through 8 remain
open. The historical negative 0.8 percent nginx figure is still not connected
to a matching raw experiment and is not validated by these new measurements.
