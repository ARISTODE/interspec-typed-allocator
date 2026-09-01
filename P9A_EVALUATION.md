# P9a True RLBox-Only Baseline

P9a closes the main performance-baseline gap left intentionally by P8. P8 isolates the cost of the final Extended-SP3 pointer acceptance check by comparing `tracked_no_check` with `extended_sp3`, but both variants retain typed allocation metadata and allocation-site provenance. P9a adds a third `rlbox_only` runtime path so the total incremental cost of Extended SP3 can be measured relative to RLBox without InterSpec allocation tracking on the evaluated rsync/popt boundary.

P9a is an evaluation extension, not a new security mechanism.

## 1. Evaluation question

For the same pinned rsync/popt workload and RLBox + NaCl sandbox, how much runtime cost is introduced by:

1. trusted typed allocation and provenance tracking,
2. final T-side liveness/type/spatial validation, and
3. the complete Extended-SP3 mechanism relative to the RLBox-only runtime path?

P9a decomposes those costs with three configurations measured within the same repetition.

## 2. Configuration definitions

### `rlbox_only`

The same pinned RLBox + NaCl sandbox and rsync/popt API boundary are used, but the evaluated popt runtime path has no active InterSpec allocation mechanism:

1. the pinned upstream `popt.c` is compiled without source-derived InterSpec allocation instrumentation,
2. `INTERSPEC_TYPED_POPT` allocator interposition is disabled, so popt uses its ordinary sandbox `malloc`/`realloc`/`free` path,
3. trusted input marshalling uses RLBox's ordinary sandbox allocator,
4. T does not reserve an InterSpec typed arena,
5. T does not instantiate `PolicyRuntime` or register generated allocation policy,
6. T does not register InterSpec allocation/lifetime callbacks, and
7. T does not execute the Extended-SP3 liveness/type/spatial acceptance check.

The benchmark uses known-valid inputs. `rlbox_only` is a performance denominator, not an adversarial security configuration.

The NaCl backend binary is still built from the same repository revision and therefore contains dormant InterSpec support code. Because the typed arena and callbacks are never activated on the `rlbox_only` path, P9a treats this as an RLBox-only **runtime-path baseline**. P9b will reproduce the final paper experiment using the wasm2c backend used by the existing InterSpec evaluation.

### `tracked_no_check`

This is the P8 measurement-only baseline. The sandbox, typed allocation metadata, source-authenticated allocation provenance, generated policy registration, lifetime tracking, and marshalling are enabled, but the final T-side Extended-SP3 acceptance check is bypassed.

### `extended_sp3`

This is the normal security configuration. Typed allocation/provenance is enabled and T performs the final liveness, expected-type, and complete-extent validation before accepting a U-controlled pointer.

## 3. Cost decomposition

For each workload repetition, P9a computes:

```text
tracking_overhead =
    (tracked_no_check / rlbox_only - 1) * 100%

validation_overhead =
    (extended_sp3 / tracked_no_check - 1) * 100%

total_extended_sp3_overhead =
    (extended_sp3 / rlbox_only - 1) * 100%
```

The first quantity includes the runtime consequences of typed allocation/provenance, including the different selected allocation path. The second isolates final trusted pointer validation. The third is the quantity needed for a total Extended-SP3-versus-RLBox claim on this prototype backend.

The two component percentages must not be added because they use different denominators.

## 4. Workloads and pairing

P9a initially uses the same complete rsync workloads already exercised by P8:

1. `option_parse`: destination-backed options and direct popt result handling through the complete rsync executable,
2. `local_dry_run`: normal local-transfer startup and positional-argument parsing.

All three binaries must successfully execute each valid workload before timing begins.

Every repetition executes all three configurations. Execution order rotates through all six permutations of the three variants to reduce systematic warmup and frequency-order bias. The raw artifact records workload, mode, repetition, and elapsed nanoseconds.

## 5. Reproducibility requirements

P9a must preserve immutable module paths for each measured configuration. The Extended-SP3 and RLBox-only NaCl modules are copied to distinct files before the trusted rsync binaries are linked, so rebuilding the canonical working module cannot silently change a previously prepared binary's configuration.

The evaluation driver restores the Extended-SP3 source/CMake state before returning so the existing P7c/P8 YAML extension continues to run against the security configuration.

Hosted GitHub runner timings remain reference measurements only. Final publication values must be regenerated on controlled hardware from the same raw CSV format.

## 6. Completion criteria

P9a is complete when CI demonstrates that:

1. `rlbox_only`, `tracked_no_check`, and `extended_sp3` all execute the same valid rsync workloads,
2. the generated RLBox-only trusted bridge contains no typed-arena reservation, policy initialization, allocation callback registration, or typed input-copy path,
3. the RLBox-only untrusted popt build uses the pinned uninstrumented `popt.c` with typed allocator interposition disabled,
4. every raw repetition contains all three modes,
5. aggregation reports tracking/provenance, validation, and total Extended-SP3 overhead separately,
6. the existing P8 two-way artifact is mechanically derived from the same three-way sample stream and remains valid, and
7. CI uploads a standalone `p9a-rlbox-only-results` artifact containing raw samples, summary, environment metadata, and a mechanically rendered paper-facing table.

No timing threshold is a correctness gate.

## 7. Outputs

P9a produces:

1. `rsync-performance.csv`: raw three-way application samples,
2. `rsync-performance-summary.csv`: paired three-way aggregation,
3. `P9A_RESULTS.md`: mechanically rendered reference table,
4. `environment.txt`: commit/platform metadata, and
5. `README.txt`: exact baseline semantics and interpretation.
