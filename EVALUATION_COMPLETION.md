# Evaluation completion ledger

## Current progress: 13 November 2026

**Stage 17's fixed-work, all-response VM latency reference is complete and
independently accepted. The broader evaluation remains incomplete.** All six
memcached scenarios × four variants × eight balanced blocks completed once:
192 measured cells and 192 separate warmups. This closes the separately
declared descriptive latency study on the available VM, alongside Stage 16's
count-only throughput reference. It does not establish controlled-host
performance, generator headroom, steady state or production-tail behavior.

### Stage 17 validated results

- Collection ran on 13 November, 06:31:20–06:39:40 UTC, in 500.040 seconds
  (8 minutes 20 seconds). The single retained attempt exited zero without
  timeout. No measured cell failed, was excluded, extended, replaced or retried.
- Each measured cell completed 100,000 validated operations and retained all
  100,000 latency values: 19,200,000 measured values, exactly 153,600,000 binary
  payload bytes. There was no sampling, cap loss or per-worker sample-vector
  growth at this bound. Separate warmups completed 19,200,000 operations and
  fresh servers received 1,920,000 preload SETs; these phases are not pooled.
- All phase GET/SET/hit/miss counts matched the independent fixed-work oracle.
  Client errors and misses, logging/watcher/LRU cumulative and delta losses
  were zero; required watchers were active. Coverage, balanced order, identities,
  clean exits and empty ordinary client/server diagnostics all passed.
- The unchanged stock matrix verifier accepted all 192 observations. The
  independent saved-data review checked all 491 frozen inputs, decoded every
  raw value and recomputed all 768 cell quantiles. It verified 264 eight-cell
  metric vectors, all rendered tables and all 192 cell CSV rows. A relocated
  replay produced byte-identical audit outputs without launching applications.

### Raw-derived p99 latency

Microseconds, median [minimum, maximum] across the eight per-cell p99 values.
These are not pooled p99 values. Each cell uses the lower order statistic
`sorted[floor(p × (N − 1))]`, without interpolation; for 100,000 values, p99
is zero-based index 98,999. Across eight cell values, the summary median is
the arithmetic mean of sorted positions four and five.

| Scenario | Native | RLBox-only | Tracked-no-check | InterSpec |
| --- | ---: | ---: | ---: | ---: |
| balanced_1c | 92.414 [72.579, 96.625] | 92.639 [84.988, 116.786] | 94.011 [78.148, 102.534] | 86.490 [74.191, 109.635] |
| balanced_8c | 211.939 [97.557, 292.641] | 175.433 [146.921, 341.534] | 178.539 [145.670, 304.017] | 179.765 [137.066, 241.143] |
| read_heavy_1k | 382.540 [210.277, 592.121] | 253.288 [174.672, 420.131] | 299.415 [183.686, 370.347] | 225.900 [165.869, 313.021] |
| write_heavy | 214.648 [172.029, 329.015] | 189.710 [124.267, 304.779] | 240.472 [151.078, 380.753] | 225.909 [167.241, 309.506] |
| watch_light | 80.136 [71.738, 87.151] | 76.665 [66.840, 83.105] | 75.358 [65.108, 90.376] | 72.304 [61.152, 81.402] |
| watch_moderate | 78.237 [70.175, 93.381] | 79.810 [71.758, 87.491] | 74.632 [64.687, 84.557] | 82.920 [71.979, 102.634] |

Measured windows ranged from 0.045053005 to 2.633444899 seconds: deliberately
fixed work, not sustained-duration runs. Latency begins before sending the
constructed pipeline batch and ends after each response's receive, exact byte
validation and accounting. It includes loopback/network, queueing, client
scheduling/validation and server work; later batch responses also include work
handling earlier responses. Request construction before send is excluded.
These are correlated end-to-end durations, not isolated server service times.

Full mode uses a per-response receive path, unlike Stage 16's buffered
count-only mode. Retained Stage 17 throughput belongs to these same full-mode
observations; no Stage 16 throughput is substituted or cross-mode difference
treated as pure instrumentation cost. Export, merge and sort occur after the
timing endpoints, but instrumentation and changed binary layout can still
perturb behavior. All observations, including the largest response duration
of 33.263 milliseconds, remain retained.

Shared-host noise, short windows, startup/termination effects, unknown physical
topology/frequency/quota behavior, unproved generator headroom and correlated
responses preclude stable ordering, equivalence, slowdown bounds, causal
overhead and production-tail conclusions. No significance test, confidence
interval, trimming or causal-policy decomposition is claimed. The stock
renderer retains its historical generic labels and unclassified status;
the Stage 17 protocol and accepted report define this narrower interpretation.

### Stage 17 identities and retained evidence

The base measurement source matches published Stage 15 commit
`545474d07526fe4c249d13f3b0a8d64a54b08b38`, tree
`ccef25a6c25e78af14b0c0e6a90305d72c46cd2b`. Stage 17 adds an independently
reviewed four-path local patch, retained in the archive but not published.
The rebuilt and measured client is SHA-256
`8b525752e9f7d4988be92cc9afb61533cd0fd2f7f5bbf5d99c28db19b31e8b72`.
The four unchanged historical ordinary servers retain source attribution
`6e164d3a62db94e4774345ee32f7d03cf3906bce` and their recorded binary hashes;
they are not Stage 17 server builds. Their hash-bound 50-case correctness gate
was inherited, not rerun.

The initial validation launcher failed before executing any command because
bare CMake was absent from PATH. Its record is retained separately. The
subsequently approved absolute-path validation ran its five finite commands
once and passed, including eight valid-input fixtures with 8,024 responses
and 6,018 raw fixture values. No outcome was replaced. Compiler, build/link
metadata, source patch and binaries are retained with the collection.

- Archive: `interspec-vm-latency-20261113.tar.gz`;
  SHA-256 `ab4e815257d934af63f097867b5b36af0aa4092c78e0692e3c8aeda77fc61432`;
  54,733,821 bytes. The downloaded archive's exact SHA-256 and size matched;
  all 3,633 manifest files (171,310,881 uncompressed bytes) were verified.
  The archive is retained privately in Space, not published as a GitHub artifact.
- Detailed archive members: `stage17-vm-latency/PROTOCOL.md`,
  `stage17-vm-latency/REPORT.md`, `stage17-vm-latency/LATENCY_TABLES.md`,
  `stage17-vm-latency/ANALYSIS.json`, `stage17-vm-latency/RAW_DERIVED_CELLS.csv`,
  `stage17-independent-review/FINAL_REVIEW.md`,
  `stage17-independent-review/FINAL_ACCEPTANCE.json` and
  `stage17-independent-review/RELOCATED_REPLAY.json`. These are archive-relative
  paths, not repository-relative links. The tables include p50, p95, p99,
  maximum-observed-response and duration; raw payloads and sidecars preserve
  every measured value in worker-local vector order, not request-ID traces.
- Final report SHA-256:
  `b05d076b01a2411a1b44025f3ec5c3a7c5395015794af836d3fb7d39d7560b4d`.
- Frozen collection manifest SHA-256:
  `fab061acd2bf461b20f56bfb9676fac4bc1055eda8e01387418dd0409011c31f`.

### What remains open after Stage 17

The fixed-work VM latency reference is no longer pending. Original paper-row
provenance, effective policy ablations, source-derived coverage, causal-policy
claims and other publication measurements remain separate open work. The older
controlled-host/headroom protocol remains unfulfilled and unchanged. Work stays
on the available VM; CloudLab or another host is not a required next step.

No capacity A/A repeat, restricted corruption/callback work, security/fault
experiment, hardware-counter run, broad test suite, CI run or paper edit was
performed for Stage 17. This repository update changes only the progress
ledger and uses `[skip ci]`; no full CI pass is claimed. Earlier dated sections
below preserve their historical status, source identities and limitations.

## Progress through Stage 16: 13 November 2026

**Stage 16's corrected VM-reference matrix is complete and independently
accepted. The broader evaluation remains incomplete.** All six memcached
scenarios × four variants × eight balanced blocks completed in one retained
attempt on the available VM: 192 measured observations and 192 warmups, with
no failed, excluded, replacement or retried cell. This separately predeclared
study provides descriptive end-to-end reference results. It does not establish
controlled-host performance, generator headroom or causal instrumentation cost.

### Stage 16 validated results

- Collection ran on 13 November, 05:27:42–05:51:22 UTC, in 23 minutes 40 seconds
  (1,419.949 seconds); the outer process exited zero without timeout.
- The independent raw audit accepted 825,285,732 measured valid responses,
  165,533,949 warmup valid responses and 1,920,000 preload SETs. These are
  distinct phases, not equal-operation-count workloads across variants.
- All 384 client outcomes and 192 server exits passed. The declared gates
  found zero client errors or misses, exact measured GET+SET reconciliation,
  zero logger/watcher/LRU loss deltas and cumulative final counters, active
  watchers and no server diagnostics. All order, coverage and identity checks
  passed, including eight blocks per scenario and each variant in every rank
  twice. The historical hash-bound 50/50 deployment gate was reused, not rerun;
  the 192 ordinary per-cell preload/warmup/measurement gates are new evidence.
- The stock saved-sample verifier passed all 192 observations. Independent
  saved-evidence review recomputed the analysis and both report tables, checking
  2,142 raw/summary/provenance files plus all 401 frozen inputs. One relocated
  replay produced byte-identical audit output without launching applications.
  The final report's two status-only edits were separately accepted; all other
  audited inputs remained unchanged.

### Paired descriptive throughput differences

Each entry is the median percentage [minimum, maximum] of eight within-block
values, calculated as `100 × (1 − InterSpec/baseline throughput)`. Positive
values mean lower InterSpec throughput; negative values mean higher throughput.
These observed ranges are not confidence bounds or isolated checking/tracking
overhead. All eight values are retained, without outlier removal.

| Scenario | InterSpec vs native (%) | InterSpec vs RLBox-only (%) | InterSpec vs tracked-no-check (%) |
| --- | ---: | ---: | ---: |
| balanced_1c | +2.74 [-6.90, +7.16] | +2.08 [-3.29, +7.67] | +3.81 [-1.69, +9.15] |
| balanced_8c | +1.35 [-12.97, +27.48] | -6.61 [-29.29, +23.68] | -3.59 [-10.94, +9.97] |
| read_heavy_1k | +5.79 [-15.65, +12.62] | +3.57 [-5.10, +13.69] | +0.84 [-13.81, +9.20] |
| write_heavy | +7.55 [-15.93, +24.72] | +4.80 [-26.57, +17.50] | +11.66 [-23.08, +32.08] |
| watch_light | +0.06 [-12.49, +14.55] | +2.43 [-6.06, +16.00] | -2.27 [-9.19, +8.71] |
| watch_moderate | +7.53 [-17.76, +19.12] | +2.30 [-7.75, +15.22] | +3.29 [-10.13, +13.69] |

**All 18 comparison ranges cross zero.** This session establishes no stable
variant ordering, equivalence, slowdown bound or speedup mechanism. No
statistical-significance claim is made. The retained report also gives all
four variants' median/minimum/maximum throughput; `ANALYSIS.json` preserves
individual throughput values, operation mixes, process CPU/RSS observations
and every paired ratio. The unchanged stock renderer's historical "overhead"
labels are not adopted as causal conclusions; the explicit Stage 16 report
and protocol define the accepted interpretation.

### Stage 16 identities and retained evidence

The measurement-source baseline is published Stage 15 commit
`545474d07526fe4c249d13f3b0a8d64a54b08b38`, tree
`ccef25a6c25e78af14b0c0e6a90305d72c46cd2b`. Its unchanged count-only client is
SHA-256 `52861a45be40fa8f17c76ff8dca7ec3e09f99c4970d86d0b243c91d1b9af2b0b`.
The separately frozen local collector adapter is SHA-256
`e3bf152da86d13e030ec949029c8270529fac1a41fe70fde11ef778c78c22688`.
The four unchanged ordinary server binaries retain source attribution
`6e164d3a62db94e4774345ee32f7d03cf3906bce` and their exact recorded binary hashes;
they are not rebuilt Stage 15 servers.

- Archive: `interspec-memcached-vm-reference-verified-20261113.tar.gz`;
  SHA-256 `f5eff9bd05c526362c774fe1f214ad357ab5d2378f61e2e40fe9770eec9bdf00`;
  5,141,156 bytes. All 2,571 manifest files were verified after a download
  roundtrip. The archive is retained privately in Space, not published as a
  GitHub artifact.
- Detailed members under the archive's `interspec-stage16-evidence/` root:
  `stage16-vm-reference/PROTOCOL.md`, `stage16-vm-reference/REPORT.md`,
  `stage16-vm-reference/ANALYSIS.json`, `independent-review/FINAL_REVIEW.md`,
  `independent-review/FINAL_REPORT_ACCEPTANCE.json` and
  `independent-review/RELOCATED_REPLAY.json`. These are archive-relative paths,
  not repository-relative links.
- Final report SHA-256:
  `4e39fe4f2b5e9d76e61ce8a2b173f4f4e2f2ebdfde0fbccdbe5d19241edcdd8e`.

### What remains open

Stage 16 closes its corrected six-by-four VM-reference collection. Count-only
mode collected no latency samples; the separate comparative latency study is
being designed, with no run or result yet. Paper-row provenance, effective
policy ablations, source-derived coverage and causal-policy claims remain
separate open work. The earlier controlled-host/headroom acceptance protocol
remains unfulfilled and unchanged; this result does not establish those claims.
Work stays on the available VM, without CloudLab or another host as a required
next step.

No new capacity A/A repeats, restricted corruption/callback work, security/fault
experiments, hardware-counter runs, broad tests, CI runs or paper edits were
performed for Stage 16. The repository update records progress only and uses
`[skip ci]`; no full CI pass is claimed. Earlier dated results below retain
their original scope and identities.

## Progress through Stage 15: 12 November 2026

**The evaluation remains incomplete.** Stage 15 integrates the previously
validated measurement-source chain and closes focused local source/build/test
validation. Controlled performance, comparative latency, the full corrected
matrix and the unresolved provenance/causal-policy questions remain open.

Published source commit `545474d07526fe4c249d13f3b0a8d64a54b08b38` has parent
`21a947b6e8594dfb567a31d9bd8883646bc4df06` and changes 42 evaluation-tooling paths.
Its tree is identical to tested local commit
`c69fccc12bece80eac5c4b82ca37fa593df6a055`, retained in the evidence archive.
The GitHub commit metadata differs; no source bytes changed during publication.
It preserves the consolidated `333d2b0` candidate plus the newer ledger, with
only one additional trailing-space cleanup. Production runtime headers,
application bridges, workflows, paper and historical results are unchanged.
Builds/tests ran on staged tree `ccef25a6c25e78af14b0c0e6a90305d72c46cd2b`;
that identical tree was committed locally after independent saved-output review.

### Focused validation completed once

- All 388 source-file identities, 28 changed Python-file syntax checks,
  whitespace checks, CMake configuration and four selected build targets passed.
- Two deterministic C++ workload/sampling tests, 23 synthetic matrix tests,
  30 profile-evidence tests, seven mock-affinity tests and 12 renderer/schema
  cases passed.
- Ten valid-response, count-only loopback client cases passed: 926 validated
  responses across fragmentation, coalescing, buffer refills, incomplete batches
  and legacy mapping. These were mock-server cases, not new memcached profiles.
- Two unchanged selected runtime-test methods passed: functional grids at
  1,023/2,049 iterations (39 rows each) and retained-instruction disassembly.
  The executed `-O2` test binary is distinct from the compile-only CMake
  `-O3` runtime target; both binaries and exact build commands are retained.
  Direct comparison also reproduced the archived 43,576-byte `-O2` runtime
  executable exactly, with matching benchmark/header/driver source bytes and
  all 57 historical archive-manifest entries checked. This is one byte-identical
  rebuild, not historical host/timing validation or a new performance result.
- Fourteen YAML evidence methods passed, using exact path adaptations and
  verified imports. They validate synthetic fixtures and saved historical
  output, not new YAML application executions.

No full-suite CTest, runtime driver/mutated-binary method, corrupted-response
client fixture, checkpoint crash test, actual server collection, capacity run,
security/fault experiment or controlled-host timing study was run. Incidental
elapsed values are functional-test artifacts, not performance results. Earlier
measurements retain their original source and executable attribution.

### Retained Stage 15 evidence

- Archive: `interspec-measurement-integration-verified-20261112.tar.gz`; SHA-256 `424f811aca8d833f69ced4797f2a9de7818d945456f3993742c0e6b2cb6596af`.
  All 910 manifest files were verified after a download roundtrip. This private
  Space archive contains the exact source bundle/snapshot, frozen
  command plans, raw outputs, tested binaries and independent acceptance.
  See `stage15-evidence/REPORT.md`,
  `stage15-independent-review/FINAL_REVIEW.md` and
  `stage15-independent-review/relocated-audit.json`.
- New source bundle SHA-256:
  `ef2d52e21a21223ce3cb5900b482d75f3fbd8a6bb01887582586c3008204332b`.
- Saved-evidence verification does not launch applications or repeat tests.
  Publication commits use `[skip ci]`; no full CI pass is claimed.

The source-integration work recorded as open on 11 November is now closed for
this exact patch and test scope. The controlled-host/headroom protocol, full
matrix and matching profiles, separate latency study, publication measurements,
paper-row provenance, effective policy ablations, source-derived coverage and
causal-policy claims remain open. Restricted corruption/callback work remains
blocked. The dated results below keep their original scope.

## Progress through Stage 14: 11 November 2026

**The evaluation remains incomplete.** The new results below close specific
ordinary functional and evidence-validation tasks. They do not establish
controlled-host performance, generator headroom, statistical equivalence,
security effectiveness, or completion of the full comparative matrix. Earlier
hosted measurements and security results are preserved in the historical ledger
below and are not relabeled as measurements of the new candidate.

### Verified since the historical ledger

| Stage | Verified result | Scope and remaining limit |
| --- | --- | --- |
| 5–7: VM capacity and client diagnostics | The repaired observation path, buffered-client comparison and separate resource diagnostic were completed and independently checked. | Spare client capacity and equivalence were not established. A/A variation and inconsistent added-resource effects remain; repeated capacity timing on this VM has stopped. The long corrected four-variant matrix was not started. |
| 10: corrected memcached profiles | Six predeclared actual profiles completed once each: 225,000 validated responses, zero client errors or misses, and zero logger, watcher or LRU drops. Raw trace/count reconciliation and independent relocated replay passed. | Ordinary fixed-profile evidence only, using the corrected generator and buffered count-only client. This is not a timing, capacity or comparative latency result. |
| 11: unified selected source | The selected client, profile, YAML-measurement and runtime-measurement corrections were unified at clean local commit `333d2b0d10af992fa93e2f653f800d443d8c6b8d`; source correspondence and retained-evidence replay passed. | The source chain remains local-only. Historical executables and measurements retain their original revisions; they are not rebound to this commit. |
| 12: ordinary YAML/libyaml | 48/48 real executions passed: six independently specified valid documents × four modes × one/two parse iterations. All exits were zero, stderr was empty, and independent raw-result and relocated replay passed. | Aggregate event/scalar counts, decoded-byte totals, driver-specific rolling hashes and check counts only. No full parser conformance, arbitrary-size compatibility or timing claim. |
| 13: ordinary nginx/PCRE8 | 104/104 saved raw HTTP responses matched independently specified status/body bytes: four release variants × 13 cases × forward/reverse order. Four metadata commands, four syntax checks and four clean server exits passed. Independent portable audit and relocated replay passed. | Each variant used one persistent connection. This is the frozen ordinary PCRE8 interpreter corpus, not comprehensive nginx/PCRE conformance, security or performance evidence. |
| 14: YAML decoded-scalar limit | All 24 predeclared processes ran once: 18 successful parses (exit 0) and six expected sandbox capacity-limit outcomes (exit 1). All outcomes matched the frozen expectations; independent raw audit, relocated replay and archive verification passed. | This separately tests the inclusive 8,191-decoded-byte staging limit. The two valid 8,192-byte inputs parsed natively but exceeded the limit in all three sandbox modes. These are supported-input limitations, not successful sandbox parses or security rejections. |

The four YAML modes and nginx variants are native, RLBox-only,
tracked-no-check and Extended SP3/InterSpec. Stages 12 and 13 built their ordinary
application binaries from the exact unified source above. Their frozen inputs,
source and binary identities, commands, raw outputs, outcomes and independent
reviews are retained. Neither application pass retried or replaced an outcome;
independent saved-result replay did not launch applications.

All six Stage 10 profiles observed positive protected-check activity. Its
write-heavy profile completed 200,000 operations, with 5,156 checks, 1,577 LRU
hold/take pairs and 1,605 moves to warm. These are counts for the declared trace
interval, including its drain, not universal per-request costs. The live client
evidence is aggregate GET/SET/hit/miss validation, with per-key correctness also
relying on the retained client and its prior protocol/multiset tests. No
independent live per-key packet capture or payload-digest truth is claimed.

The six Stage 12 documents cover block/flow collections, Unicode/escapes,
multiline scalars, multiple/empty documents, anchors/tags and BOM UTF-16LE.
The driver does not expose complete event-type sequences, scalar boundaries,
tag/anchor identity or alias resolution; its 64-bit hash is non-cryptographic.
The largest scalar in the Stage 12 corpus is 12 decoded bytes. Stage 14
separately checks the wrapper's 8,191-byte decoded-scalar limit; it does not
extend Stage 12's scope or establish arbitrary-size compatibility.

Stage 13 adds regex virtual-host selection, mixed named/numbered captures,
empty and optional captures, zero-capture matches, and location precedence.
Its raw audit verified 72 retained build artifacts, 16 consumed candidate files,
883 upstream files and the exact unified source bundle. This is retained
process/request/response evidence, not an independent network packet capture.

Stage 14 reused the exact three Stage 12 executables for four modes without a
rebuild. Its six valid documents cover ASCII at 8,190 bytes; ASCII at 8,191
bytes repeated around an empty scalar; escaped Unicode and BOM UTF-16LE decoded
to 8,191 UTF-8 bytes; and ASCII/escaped-Unicode scalars decoded to 8,192 bytes.
The four within-limit documents parsed in all modes. Native also parsed both
8,192-byte documents; each sandbox mode instead returned empty stdout and exact
`yaml benchmark error: scalar_staging_capacity` stderr with exit 1 for both.
The result is 18 successful parses plus six capacity-limit outcomes, not 24
successful parses. The expected limits and ordinary output fields were frozen
before execution. No application source, binary or protocol was changed.

### Retained evidence identities

These archives are retained privately in Space, not checked into this
repository or published as GitHub artifacts. Each was uploaded, materialized
again, checked against its SHA-256 and verified against its file manifest.
Member paths below are relative to each archive's top-level directory; they
identify the detailed reports and audits, not repository-relative links.

- Stage 10: `interspec-corrected-profiles-verified-20261111.tar.gz`;
  SHA-256 `d95b5cfd78aaef5d68186f7a6f9081636d86f6204ba245d96f125a33e20a1eab`;
  556 manifest files. See `stage10-profile-evidence/REPORT.md` and its
  `independent-review/` records.
- Stages 11–12: `interspec-unified-yaml-functional-verified-20261111.tar.gz`;
  SHA-256 `a214099f511a701a8116473471f567925a9031e1fb6a004a98ea3c10f1260eb9`;
  690 manifest files. See `stage11-unified-evidence/REPORT.md`,
  `stage12-yaml-functional-evidence/REPORT.md` and the retained independent audits.
- Stage 13: `interspec-nginx-functional-verified-20261111.tar.gz`;
  SHA-256 `4166828374e016a52235175f6c8f24b28cfc80321879ee845e073864f5c4b7fd`;
  522 manifest files. See `stage13-nginx-functional-evidence/REPORT.md` and
  `stage13-independent-review/actual-results-review.json`.
- Stage 14: `interspec-yaml-scalar-limit-verified-20261111.tar.gz`;
  SHA-256 `f009cee05dc7cf6a0f9f2012cecd5e379e02471acf3a2a8b4c6700cfb82b310d`;
  182 manifest files. See `stage14-yaml-scalar-evidence/REPORT.md` and
  `stage14-independent-review/REPORT.md` / `actual-results-review.json`.
- Exact unified source bundle SHA-256:
  `a1f9b2a843f79c4a6c9ea8fd6c913bd5a2ee58fd42145d2cd921f1cb84faf695`.

### Still open

1. Establish a defensible controlled-host, noise and load-generator-headroom
   protocol before the full corrected four-variant memcached matrix and its
   matching diagnostic profiles. No further noisy capacity repeats are planned
   on the current VM.
2. Run the separate comparative latency study and the remaining controlled
   application/microbenchmark publication measurements under their own accepted
   protocols. Incidental elapsed fields in functional outputs are not results.
3. Reconcile original paper-row provenance, effective policy ablations,
   source-derived coverage and causal-policy claims. These functional results do
   not close those gaps or validate unsupported historical numbers.
4. Keep restricted corruption/callback experiments blocked; no retry is part of
   this progress update. Historical security outcomes below remain separately
   scoped evidence, not new validation.
5. Review any eventual publication/integration of the local source chain
   separately. This progress update changes documentation only and does not
   publish source-integration commits, alter protocols or revise the paper.

## Historical completion ledger (October 2026)

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
