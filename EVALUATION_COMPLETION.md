# Evaluation completion ledger

## Current progress: 13 November 2026

**Stage 20 adds an opt-in trusted typed-staging integration to the ordinary
YAML adapter and validates its normal real-libyaml path. The broader evaluation
remains incomplete.** The single frozen batch matched all 75 predeclared
outcomes: 71 successful parsing processes and four expected sandbox capacity-limit
exits.
This is a new application integration, not completion of the original-paper
evaluation or a security-effectiveness result.

### Stage 20 integration and validated outcomes

- New explicit mode `typed_staging_identity` allocates one 8192-byte aggregate
  through trusted setup and retains its nonzero expected base independently
  of guest results. The four-argument typed API checks returned scalar ranges
  before copying. The aggregate is one element, not 8192 independent chars.
- Existing native, RLBox-only, tracked-no-check and legacy extended modes
  remain. The original one-argument setup export remains; a new two-argument
  export accepts the trusted staging offset. The host retains ownership of
  supplied staging; the guest frees only helper-owned storage.
  The new mode is not selected by default and introduces no independent SP1,
  SP2 or all-policy selector.
- Seven valid documents × five modes × one/two iterations produced 70
  successful parsing processes and 105 completed stream-processing iterations.
  Coverage includes block/flow syntax, decoded escapes and
  embedded NUL, multiline scalars, anchors/tags, multiple documents and empty
  scalars, UTF-16LE BOM and an 8191-byte maximum supported scalar.
- Five separate one-iteration controls used a valid 8192-byte scalar. Native
  parsed it successfully, bringing the totals to 71 successful processes and
  106 completed stream-processing iterations. Each sandbox mode returned the
  exact predeclared
  capacity-limit exit, empty stdout, one input-copy observation and the normal
  capacity diagnostic. These four exits are expected capacity limits,
  not successful sandbox parses or typed-check rejection evidence.
- The new mode had 14 successful parsing processes and one expected capacity
  exit. New and legacy extended modes each recorded 96 driver check counts
  and 96 existing downstream observations. Each sandbox mode had 22 input-copy
  occurrences. Observation was uniformly enabled and trace disabled.
- One offline ordinary-only build succeeded on its first attempt. All 35 new
  build artifacts were retained and checked. All 75 declared process outcomes
  matched once, with no unexpected failures, timeouts, retries, replacements
  or unexecuted cells. Incidental elapsed values remain raw and were not analyzed.

The independent predeclared oracle supplies event/scalar counts, decoded-byte
totals and an ordered-byte rolling hash. The driver exposes those aggregates,
not full event sequences or scalar boundaries. Acceptance is not complete YAML
conformance, alias/tag/anchor equality or collision-proof semantic equivalence.

### Effective path and lifecycle evidence

Actual Wasm metadata and linked symbols retain the original `(i32)->i32` setup
ABI and include the new `(i32,i32)->i32` setup ABI. Narrow compiled inspection
shows typed allocation metadata, 8192-byte element size and alignment one,
the mode branch, live metadata lookup, expected type, typed stride/exact element
start and extent, and comparison with the independently retained trusted base.
Successful validation precedes the existing observation and scalar copy.

The counter increments before validation, and observation labels are supplied
by the caller; neither alone proves an effective check. Source, actual compiled
data flow and the downstream occurrences together support the valid-path claim.
Normal success is gated on guest shutdown and successful checked metadata
release. No independent allocation/release counter is exposed. The four
capacity exits exercise ordinary error unwinding but do not prove every
exceptional lifecycle property.

### Tested source and publication mapping

The source-only publication is commit `308766480eb9c00a3203b0a5afdaab664173699b`, parent
`5145be16f43ebd5183cc01780bc1ed4dadbb862e`, with full publication tree
`08353b8b97502e26f9915f8723b2f0e267046cc2`. The separate ledger child changes
only `EVALUATION_COMPLETION.md`; no benchmark was rerun after publication.

The build and collection used frozen staged tree
`faae265527340ba5c03e5370a742149b33d6811d`. Later local commit
`7546ad49a68954e1dff7ed45de71a2b4d6fe2bd1` records that exact already-tested tree
without byte changes; it was created after collection. Its local mirror parent
`4c7c4cef287181557bf9519c5a7cc0b719ba7b28` reproduces the earlier remote base
`293286f1e277fc383ab75a979d5160cdd72846ae`, tree
`f4ce6fb1b12a444365433643e94abdd9037f1c2f`, but does not claim remote ancestry.

Before publication, concurrent work advanced the branch to `5145be16`, tree
`ee5f01c54dffe85abeddd0bb700e89dca91deced`. All 388 earlier base file blobs and
modes remained unchanged; exactly three files were added:
`.github/workflows/controlled-publication-evaluation.yml`,
`CONTROLLED_GITHUB_CI.md` and `EVAL_TRACKER.md`. Publication preserves those
concurrent additions verbatim. The new source commit retains all 390 paths,
bytes and modes from the tested tree, plus those three additions. Its full tree
therefore differs from the tested tree. The concurrent workflow and documents
were not build inputs and were not validated by the Stage 20 runs. Trigger
inspection found the added workflow manual-only; it was not dispatched.
The API-created commit has remote ancestry and different commit metadata.

Exactly five source paths changed, preserving Git file modes:
`integration/yaml_libyaml/yaml_app_bench.cpp`, `yaml_app_wasm.c`,
`yaml_scalar_staging.h`, `TYPED_STAGING.md` in that same directory, and
`scripts/run_yaml_libyaml_evaluation.sh`. The script change is only one adjacent
header-copy line; that all-in-one script was never run. No generic runtime,
policy/generator, backend, other adapter, workflow or paper was changed by
Stage 20.

The candidate patch SHA-256 is
`5fa7b82101e3747cabdcc59447985e41214b8c5bc7058c35bd40e62db154fcab`.
The new native, ordinary and typed executable SHA-256 identities are respectively
`63c25501e6c458cb1d87271c7d12d8973eff24b76f87aeec5e1095709f1c5f28`,
`a05e313706f2d82af6ae6e2f0a7b8db7c39f396c1b95a487fe7d00ca901eb527` and
`0da34341dedcb4c41f0714cdaa53050ff22f87f322e8f64cc34197bc9ef1c6e2`.
Tracked-no-check, legacy extended and new typed-staging modes share that new
typed executable. Stage 19 retains its distinct legacy-path/Stage 12 provenance.

### Retained Stage 20 evidence

- Final independent saved-result acceptance: `independent-review/final-review.json`,
  SHA-256 `efe5ee673c1d855fc8d363198370a1d874445ebe23651c281e03ada71ee85536`.
  Report `REPORT.md` SHA-256:
  `dc9264ddb90d518126e19886dada8f33275aaec14d42d989f9d0af6c39adcb7e`.
- Archive: `interspec-typed-yaml-staging-verified-20261113.tar.gz`; SHA-256 `1e1f616ba69f8172bb728bb9f203c643a80c67ec8f6839b6c310a2c14efc2946`;
  5,305,925 bytes, 428 manifest entries and
  429 regular archive files including the manifest.
  The official Space download matched the archive SHA-256 and size; all
  manifest files verified. A relocated saved-data replay was byte-identical
  without launching applications.
- Evidence includes `REPORT.md`, `API_INVENTORY.md`, `source/candidate.patch`,
  `source/tested-source-identity.json`, the complete tested-source bundle and
  snapshot, `plan/prebuild-freeze.json`, `plan/launch-freeze.json`,
  `plan/commands.json`, `plan/expected.json`, `plan/input-oracle.json`,
  `build-attempt/`, `built-artifact-manifest.json`, `built-artifacts/`,
  `compiled/COMPILED_PATH.md`, `attempt/summary.json`, every per-cell raw
  command/record/stdout/stderr, `observed-results.json` and the independent
  review/audit files. Paths are relative to `interspec-typed-yaml-staging-evidence/` inside the
  private Space archive, not repository-relative links. No private file ID or
  download URL is published in the repository.

### What remains open after Stage 20

The contract identifies the selected staging aggregate, not libyaml's original
allocation, the semantic provenance of the current event, a new identity per
scalar or temporal/ABA protection. Its fixed bound largely coincides with the
old staging limit. The narrower addition is typed exact element-start and
trusted expected-base validation. Valid-input acceptance does not demonstrate
invalid-pointer rejection, adversarial resistance or security effectiveness.

The application-authored aggregate is not new source-derived precise allocation
coverage. Generated policy remains unchanged: zero precise source-derived
allocation sites, two helper declarations and one dynamic-byte scalar use.
Generated `api.c` still matches pinned upstream libyaml
`90a56d4500aa1a1798514c5cb55c3ad4cb095f94`. Existing memcached and YAML delta API
references were inventoried only; their restricted nested-pointer/security
paths were not followed or exercised.

Ledger items 6 and 7 remain open. Historical original-paper attribution,
independent all-policy ablations, source-derived coverage/recall, comprehensive
lifecycle visibility, rejection effectiveness and causal cost attribution are
not closed. New-mode allocation ownership and validation both change, so this
is not an isolated final-check cost ablation. Stages 16 and 17 retain their
descriptive VM throughput and latency scope.

Stage 20 used only the available VM, with no CloudLab/host search, corruption,
fault or invalid-pointer experiment, broad CTest, all-in-one script, hardware
counter or paper edit. Both publication commits include `[skip ci]`; no workflow
was dispatched and no CI pass is claimed. Earlier dated sections retain their
historical status and attribution.


## Progress through Stage 19: 13 November 2026

**Stage 19's ordinary YAML effective-policy path diagnostic is complete and
independently accepted. The broader evaluation remains incomplete.** The
existing final-validation switch changes the executed check path on two valid
libyaml inputs while preserving the declared functional outputs. This narrows
one current-integration question; original-paper attribution, independent
all-policy ablations, source-derived coverage and causal costs remain open.

### Stage 19 validated results

- The frozen plan ran exactly once on the available VM: two valid inputs ×
  four modes × existing observation off/on, each with one parse iteration,
  for 16 ordinary real-libyaml processes. All exited zero and passed, with no
  failures, timeouts, retries, replacements or missing cells.
- Native, RLBox-only, tracked-no-check and Extended SP3 all matched the
  independent predeclared event/scalar counts, decoded byte totals and ordered
  scalar-byte rolling hashes in both observation settings:

| Input | Input bytes | Events | Scalars | Decoded bytes | Rolling hash |
| --- | ---: | ---: | ---: | ---: | --- |
| `block_flow` | 58 | 19 | 9 | 39 | `058a636345d985ce` |
| `multi_document_empty` | 35 | 15 | 3 | 0 | `14650fb0739d0383` |

- Extended mode reported nine and three checks per respective parse; the
  other modes reported zero. Across both observation settings this is 24
  Extended driver-counter increments. With observation on, Extended emitted
  12 downstream scalar occurrences, and the six sandbox invocations each
  emitted one input-copy occurrence. The three-document input still has one
  parse iteration and one input-copy occurrence per sandbox invocation.
- Observation-off stderr and native stderr were empty. Observation-on sandbox
  stderr contained exactly the expected records and no other diagnostics.
  The empty-scalar input entered the check path three times despite its zero
  decoded-byte total.
- Before/after identities matched. All 35 retained build artifacts, nine
  relevant source files and two inputs were verified. The explicit six-variable
  child environment excluded inherited loader overrides and credentials.
  Independent saved-output verification accepted all 16 records; a relocated
  replay produced byte-identical review results without launching applications.

### What demonstrates the executed check path

The driver increments its counter **before** calling the generated check, so
the count alone is insufficient. Narrow source inspection and retained typed
binary disassembly establish a mode-dependent branch into live-allocation
metadata lookup, expected-type comparison and remaining-extent comparison.
Only a successful return reaches the enabled post-check observation before
scalar copying. This compiled path is not an erased or counter-only stub.
The source, compiled path and downstream occurrences together support the
selected valid-input path-activation result.

The observer's accepted/storage label is caller-supplied, not an independent
metadata probe. Raw address, PID and storage fields were retained without
interpretation. These valid-input results do not establish invalid-input
rejection effectiveness, adversarial resistance, object-identity protection or
comprehensive enforcement correctness. The functional oracle checks aggregates
and a non-cryptographic 64-bit rolling hash, not complete event sequences,
scalar boundaries, tags, anchors or alias resolution. It does not establish
complete YAML semantic equality or collision-proof content equivalence.

### Executable provenance and actual policy inventory

Tracked-no-check and Extended SP3 use the **same** retained typed executable,
SHA-256 `7e6a68896521d82174b5715552e09c9c28980975325c093015362050916e1dcf`,
and the same generated policy/module bytes. The intervention changes a runtime
path, not compiled policy bytes. Ordinary and typed build artifacts differ,
including their staging-allocation paths; that broader contrast is not the
isolated final-check intervention.

The executable remains the Stage 12 build from source commit
`333d2b0d10af992fa93e2f653f800d443d8c6b8d`, tree
`23927085a6aacb17227071427b1833b3aa492e0c`, with libyaml
`90a56d4500aa1a1798514c5cb55c3ad4cb095f94`. Nine relevant source files have
the same bytes as historical Stage 15 source. No rebuild occurred, and neither
Stage 15 nor a later ledger-only commit is relabeled as the executable source.

The generated policy records **zero precise source-derived allocation sites**,
two helper declarations, one ordinary scalar-staging helper and one dynamic-byte
scalar-range use. The other helper has a declared adversarial role and was not
exercised. Generated `api.c` is byte-identical to pinned upstream `src/api.c`.
This inventory does not say that libyaml allocates nothing. It supplies no
source-coverage denominator or recall measurement and does not validate the
paper's coverage percentages. This driver has no independently implemented
SP1, SP2 or all-policy selectors. Its legacy byte-range check is distinct from
other typed-element and object-identity APIs. The exact binaries do not export
allocation/lifecycle counters; no instrumentation or trace-enabled build was
introduced to fill that gap.

### Retained Stage 19 review and archive

- Final independent review: `independent-review/final-review.json`.
- Report SHA-256:
  `d547cea36591a044704b92838750c2395009d88eb494010cde095ef8670ec3a8`.
- Archive: `interspec-yaml-policy-path-verified-20261113.tar.gz`;
  SHA-256 `ae3316cf9eafce983ec75cf0aff525f99234afc1b3e07b4d2db90fa24e74411a`;
  1,536,188 bytes. The official download matched its SHA-256 and size, and
  all 140 manifest entries verified. The archive contains 141 regular files,
  including the manifest, and is retained privately in Space rather than
  published as a GitHub artifact.
- Evidence members include `REPORT.md`, `STATIC_FINDINGS.md`,
  `plan/commands.json`, `plan/expected.json`, `plan/identities.json`,
  `plan/freeze.json`, `attempt/summary.json`, `attempt/<execution_id>/`,
  `observed-results.json`, `results-freeze.json`,
  `evidence/artifact-comparison.json`, `evidence/api-source-comparison.json`,
  `evidence/scalar-mode-copy.asm`, `evidence/scalar-check-postcheck.asm`,
  `independent-review/verify_saved_results.py` and
  `independent-review/saved-audit-executions.json`.
  All listed member paths are relative to the archive's
  `interspec-yaml-policy-path-evidence/` root, not repository-relative links.

### What remains open after Stage 19

Ledger items 6 and 7 remain open. The original 12 application pairs still lack
complete historical source/build/workload/mode/raw-repetition bindings in the
inspected archive. Effective independent policy ablations, comprehensive
source-derived coverage, lifecycle visibility, rejection effectiveness and
causal cost attribution are not closed by this diagnostic. Stages 16 and 17
retain their accepted descriptive VM throughput and latency scope. No timing
comparison is reported here; incidental raw elapsed values were not analyzed.

Stage 19 used only the available VM. No CloudLab or other host, rebuild,
fault/security experiment, invalid-pointer exercise, restricted source analysis,
broad test suite, hardware counter, paper edit or CI dispatch was used. This
publication changes only `EVALUATION_COMPLETION.md`, with `[skip ci]`, and does
not claim a CI pass. Earlier dated sections retain their historical status and
attribution.


## Progress through Stage 18: 13 November 2026

**Stage 18 completes the document-location and arithmetic portion of the
original-paper provenance review. The broader evaluation remains incomplete.**
All 12 original performance rows now have exact manuscript and processed-data
locations, but none has a complete historical source, executable, workload,
policy-mode and raw-repetition binding in the inspected archive. This is
partial progress on ledger item 6, not completion of that item or validation
of the original application measurements. Item 7 remains open.

### Stage 18 verified findings

- The 12 rows in `data/processed/paper/performance_overhead.csv:2–13` match
  `tex/eval.tex:54–77`. The displayed pairs give a geometric mean runtime-ratio
  overhead of 7.4988998677%, rounding to 7.5%. Stored policy percentages give
  geometric means of −0.7626303%, +0.1608451% and +10.4332630%, rounding to
  −0.8%, +0.2% and +10.4%. These are processed-table arithmetic results.
- All 132 pinned input blobs and the complete set of 110 compact performance
  rollup files were retained and checked. The artifact explicitly omits full
  performance raw logs, generated datasets, binaries, build directories and
  upstream Git histories (`docs/DATA_PROVENANCE.md:19–28`). Its table-checking
  script reads processed CSVs; inspecting it does not establish run identity.
- Nine of 24 policy-ablation percentage cells numerically correspond to five
  historical microbenchmark CSVs: PNG SP3, bipbuffer c1/c8 SP3, and YAML/ZIP
  SP1/SP2/SP3. Twelve cells are stored as zero; three other nonzero cells remain
  unmapped. Neither the zero cells nor the unmapped cells are independently
  validated by those nine correspondences.
- Three complete phase-percentage vectors match retained profiles at displayed
  precision: PNG, YAML and ZIP. Bipbuffer is a partial match: copy-out is
  17.6243%, rounding to 17.6%, rather than the stored 17.7%; its other three
  phase percentages match. Nginx and rsync remain unresolved.
- Supplied coverage counts reproduce 3,179/7,523 = 42.2571%,
  4,426/7,523 = 58.8329% and 1,955/1,966 = 99.4405%, with consistent stored
  partitions. This verifies count arithmetic, not source-derived coverage,
  effective enforcement or the underlying policy transformations.

### Numerical matches do not establish historical derivation

The nine ablation matches use ratios of arithmetic means of five `ns_per_op`
samples per mode. Ratios of medians from those same files do not reproduce the
cells at two decimals. The paper states median-of-five measurements
(`tex/eval.tex:14`), so the estimator would need reconciliation **if these files
were used to derive those cells**. The match alone does not establish that
historical derivation or disprove the methodology of an unbound application
row. For example, ZIP SP3 is 50.9285% by mean ratio and 36.0810% by median ratio.

SP3-only records are expected for an SP3 ablation. Their presence does not
conflict by itself with the combined table's all-policy-off versus all-policy-on
caption (`tex/eval.tex:82–87`). The relevant overlap is narrower:

| Boundary | SP3 ablation cell | Combined displayed delta | Ratio of combined absolute pair | Historical SP3-only mean ratio | Same-file all-policy mean ratio |
| --- | ---: | ---: | ---: | ---: | ---: |
| YAML | 6.17% | 6.2% | 6.236559% | 6.170938% | 5.748659% |
| ZIP | 50.93% | 50.9% | 50.909091% | 50.928471% | 61.059338% |

The SP3-only mean ratios reproduce the ablation cells and round to the combined
displayed deltas, but do not recover the combined table's absolute application
pairs. This warrants reconciliation if those files are offered as combined-table
support; it does not prove that the combined measurements used SP3-only mode.
Stored mode flags are not independent evidence of effective enforcement.

ZIP's matching SP3-only profile gives 53.53561 ns guard time per profiled
operation and a 41.409% guard share. Multiplying the paper's 0.2656 µs whole-query
latency by that share rounds to 0.110 µs, but no evidence binds the two scopes
to the same run/build. The profile does not independently validate a measured
110 ns guard interval. YAML and ZIP profile operation counts also differ from
the paper's stated workloads. No causal cost or copy-removal speedup is closed.

### Evidence identities and separation from later results

The original artifact is pinned at
[`2b2d2fd4de69ee44a4363e69f8cfb82ceed132db`](https://github.com/ARISTODE/interspec-artifact/tree/2b2d2fd4de69ee44a4363e69f8cfb82ceed132db),
tree `79e5315d72d6055b33dd03ce1ac88f23af82ddb6`. Its README names paper snapshot
[`c692d9581e17689ca1dc20545c48a355c6a86ff6`](https://github.com/ARISTODE/Automatic-Access-Policy-Enforcement/tree/c692d9581e17689ca1dc20545c48a355c6a86ff6).
The retained `tex/eval.tex` is blob `9dd820668fcd83fc588ea104cf10b35e9aee16f1`.
That file and the two retained ablation/phase TSVs have identical bytes at
observed paper head `5bb54e15f45b0f369018e2a6d9762e1a7d88c585`; this is not a
claim that the whole paper is unchanged. The saved PDF text read corroborates
the relevant cells and workloads, but is not a PDF-byte hash. No paper was edited.

Later retained application data contains 400 CSV rows across 12 workloads and
four boundaries, not the original ten boundaries. Its recorded sources remain
distinct:

| Later dataset | Rows | Recorded execution/source commit |
| --- | ---: | --- |
| Memcached hosted 38092306794 | 120 | `d1546785002fc9f9005d2d17360bddaf4839e4a4` |
| Nginx hosted 37835791042 | 40 | `2c9d51dc56d896ce7c543fe726d0e31def34b13c` |
| YAML hosted 37593628736 | 60 | `cdef5b825e7c2db213127fcb9cb228270cf2667d` |
| Rsync retained reference | 180 | `6c9df666bba8ef6d5d12679a4bd3e6a24bdbe973` |

This pass counted and hashed these files without repeating prior full
experimental audits. They do not replace the original application evidence,
validate the historical negative nginx claim, or become results of the later
VM servers or Stage 15 measurement source. Later nginx uses PCRE8, while the
original provenance documentation describes PCRE2.

### Retained Stage 18 review and archive

Final independent review accepted the clarified narrative, identities and
arithmetic. All 163 primary inputs and numerical mappings remained unchanged;
all 174 inner-manifest entries verified. Both saved-data verifiers produced
byte-identical results after relocation, without launching applications.

- Archive: `interspec-original-provenance-verified-20261113.tar.gz`;
  SHA-256 `ab7723ffed8cea3dc789b30ca9e5c60bde7f3bbc058b2cea343bcdf8db07266a`;
  227,351 bytes. The official download matched its SHA-256 and size; all 185
  package-manifest entries and all 174 inner-manifest entries verified.
  The archive is retained privately in Space, not published as a GitHub artifact.
- Final review members: `independent-review/FINAL_ACCEPTANCE.md` and
  `independent-review/FINAL_ACCEPTANCE.json`.

- Report SHA-256:
  `2ea5b44425806c773462ee19229d1c9b1b1232fec87d13065c0521741265f3e8`.
- Detailed archive members include `stage18-provenance/REPORT.md`,
  `stage18-provenance/findings/PAPER_ROW_MAPPING.json`,
  `stage18-provenance/findings/ABLATION_NUMERICAL_MAPPING.json`,
  `stage18-provenance/findings/PHASE_NUMERICAL_MAPPING.json`,
  `stage18-provenance/findings/PROCESSED_ARITHMETIC.json`,
  `stage18-provenance/findings/INPUT_IDENTITIES.json` and
  `stage18-provenance/findings/LATER_DATASET_IDENTITIES.json`.
  All listed member paths are relative to the archive's
  `interspec-stage18-evidence/` root, not repository-relative links.

### What remains open after Stage 18

The useful next evidence is the actual run manifests, source/dependency
revisions, executable hashes, workload inputs and raw repetitions for the 12
original application pairs. Their absence from the inspected archive does not
prove that no other archive exists. Estimator, mode and profile-scope questions
remain conditional on establishing those bindings. Effective ablations,
source-derived coverage, causal claims and publication measurements remain open.
The Stage 16 throughput and Stage 17 latency references retain their accepted
descriptive scope. The older controlled-host/headroom protocol remains
unfulfilled; missing records are not a request for CloudLab or another host.

Stage 18 used read-only retrieval and saved-document arithmetic. No target
application, build, test suite, benchmark, CI workflow, hardware counter,
security/fault experiment or restricted pointer/callback analysis ran.
This publication changes only `EVALUATION_COMPLETION.md`, with `[skip ci]`.
No source, workflow or paper edits are included and no CI pass is claimed.
Earlier dated sections below retain their historical status and attribution.

## Progress through Stage 17: 13 November 2026

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
