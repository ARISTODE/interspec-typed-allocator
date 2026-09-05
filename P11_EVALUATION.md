# P11 Final RLBox wasm2c Performance Evaluation

P11 answers the remaining performance question for Extended SP3 on the RLBox wasm2c backend used by the final InterSpec implementation path: what is the incremental cost of trusted allocation/provenance tracking, what is the cost of the final trusted pointer check, and what is the total cost over an RLBox-only runtime path?

P11 is an evaluation milestone, not a new security mechanism.

## 1. Why the primary benchmark is rsync/popt

P10 establishes that the Extended-SP3 mechanism generalizes across rsync/popt, memcached/bipbuffer, nginx/libpcre, and yaml/libyaml on wasm2c. Among those integrations, rsync/popt is the complete trusted application path with a matched RLBox-only execution configuration and stable end-to-end workloads. P11 therefore uses rsync/popt for the primary three-way total-overhead decomposition rather than manufacturing unmatched full-application baselines for the P7c boundary-only integrations.

The P7c/P10 boundaries remain security-generalization evidence. The P8 paired boundary benchmark remains useful for isolating final validation cost at individual pointer uses, but it does not measure total tracking/provenance overhead.

## 2. Configurations

### `rlbox_only`

The same pinned RLBox wasm2c sandbox and rsync/popt API boundary are used, but the measured runtime path has no active InterSpec mechanism:

1. bundled `popt.c` is restored to the pinned upstream source without allocation-site instrumentation;
2. `INTERSPEC_TYPED_POPT` allocator interposition is disabled;
3. trusted input marshalling uses RLBox ordinary sandbox allocation;
4. T does not reserve the InterSpec typed region;
5. T does not initialize `PolicyRuntime` or register allocation-site policy;
6. T does not install InterSpec allocation/lifetime callbacks; and
7. T does not execute the final Extended-SP3 pointer acceptance check.

Dormant backend support code may remain linked. The claim is therefore an RLBox-only **runtime-path baseline**, matching P9a's baseline semantics while moving the experiment to wasm2c.

### `tracked_no_check`

The typed wasm2c module, trusted allocation metadata, direct-import allocation-site provenance, lifetime tracking, generated policy, and marshalling are enabled. Only the final T-side liveness/type/spatial acceptance check is bypassed for known-valid benchmark inputs.

### `extended_sp3`

The complete mechanism is enabled. T accepts a U-controlled pointer only after the normal liveness, expected-type, and spatial-extent validation.

## 3. Cost decomposition

For every paired repetition P11 computes:

```text
tracking_overhead =
    (tracked_no_check / rlbox_only - 1) * 100%

validation_overhead =
    (extended_sp3 / tracked_no_check - 1) * 100%

total_extended_sp3_overhead =
    (extended_sp3 / rlbox_only - 1) * 100%
```

The component percentages are not added because their denominators differ.

## 4. Workloads and measurement unit

P11 reuses the two complete-rsync workloads established by P9a:

1. `option_parse`: destination-backed options and direct popt result handling;
2. `local_dry_run`: local-transfer startup and positional-argument parsing.

The measurement unit is complete process wall time. Sandbox creation, application startup, boundary marshalling, allocation/provenance tracking, trusted checks, and normal process exit are therefore included rather than timing an isolated metadata lookup.

All three binaries must execute both valid workloads before measurement begins.

## 5. Pairing and order control

Every repetition contains all three configurations. The driver rotates through all six permutations of the variants to reduce systematic warmup and frequency-order bias. A configurable warmup phase runs before recorded samples.

The raw CSV is the source of truth. Aggregation is mechanically derived from complete per-repetition triples, and no timing threshold is a correctness gate.

## 6. Controlled-hardware protocol

Hosted GitHub Actions provides a reproducibility reference only. Publication numbers should be regenerated on a controlled machine using the exact same driver.

Recommended publication run:

```bash
INTERSPEC_P11_REPETITIONS=31 \
INTERSPEC_P11_WARMUPS=3 \
INTERSPEC_P11_CPU=2 \
./scripts/run_p11_wasm2c_performance.sh p11-wasm2c-results
```

For a controlled run:

1. use an otherwise idle machine or dedicated VM with no competing benchmark workload;
2. pin all measured processes to one chosen logical CPU with `INTERSPEC_P11_CPU` when appropriate;
3. keep CPU frequency policy and turbo/boost settings fixed for the complete run;
4. avoid changing kernel, compiler, sandbox, rsync, or benchmark revisions between variants;
5. run all three variants in the same measurement session; and
6. report the generated `environment.txt` together with the raw CSV.

The driver records the observed CPU model, kernel, frequency governor, turbo/boost state when exposed by Linux, CPU affinity request, repetition count, and pinned source revisions. It does not silently change host power-management settings.

## 7. Reproduction

```bash
chmod +x scripts/run_p11_wasm2c_performance.sh
./scripts/run_p11_wasm2c_performance.sh p11-wasm2c-results
```

The driver first runs the complete P9b wasm2c preparation path. It then creates three immutable rsync binaries: full Extended SP3, tracking without final validation, and RLBox-only. The RLBox-only module is rebuilt from pinned uninstrumented popt with typed allocator interposition disabled.

## 8. Outputs

P11 produces:

1. `rsync-performance.csv`: raw three-way paired samples;
2. `rsync-performance-summary.csv`: mechanically aggregated timings and overhead decomposition;
3. `P11_RESULTS.md`: rendered result table;
4. `environment.txt`: platform and measurement metadata;
5. `p9b-prepare.log`: backend/build preparation diagnostics; and
6. `README.txt`: artifact semantics.

## 9. Completion criteria

P11 engineering is complete when CI demonstrates that:

1. all three wasm2c configurations execute both valid workloads;
2. the RLBox-only trusted bridge contains no typed-region reservation, PolicyRuntime initialization, wasm allocation-policy registration, or runtime callback installation;
3. the RLBox-only bundled popt source is the pinned uninstrumented source and typed allocator interposition is disabled;
4. every recorded repetition contains all three modes;
5. aggregation reports tracking/provenance, validation, and total overhead separately; and
6. CI uploads the complete P11 reference artifact.

A hosted CI run satisfies the reproducibility and engineering gate, but not the stronger claim that the numbers are publication-quality controlled-hardware measurements. The controlled-hardware run uses the same script and artifact format.
