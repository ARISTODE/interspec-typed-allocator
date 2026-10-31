# Follow-up pointer-origin and behavioral parity experiment

Status: experimental protocol, pending hosted CI validation. This document does **not** report paper-ready measurements.

## Scope and safeguards

The baseline pointer census records **pointer-use events** at explicitly instrumented InterSpec boundaries, not unique allocations or all U-internal pointers. Trusted inputs are copied or tokenized; their raw addresses do not cross into U. The native/isolated regression suites remain compulsory, and the six-scenario throughput benchmark does **not** enable tracing or the pointer census.

The new Linux-only classifier first checks the executing T thread's stack, then readable nonexecutable ELF PT_LOAD segments, then the address's VMA in `/proc/self/maps`. The `t_stack_named_vma` category refers to a mapping labeled `[stack]` or `[stack:tid]`; it does not prove which thread owns it. VMA classes are *mapping provenance*, never proof of object type, allocation base, memory ownership, or lifetime. An anonymous VMA may be a malloc arena, another thread's stack, or unrelated storage. The `[heap]` VMA identifies the conventional brk heap region, not an individual malloc object. The ELF category does not prove the pointer references a named global. A missing mapping is `t_unmapped`; an inaccessible maps file leaves `unknown`.

These observations apply to T staging and adapter sites, and to U pointers checked on return. Uninstrumented nested fields and unobserved dormant paths are outside the sample.

## Negative U storage probes

Modes 9 and 10 are compiled only into the memcached diagnostic/fault WASM module:

1. Mode 9 substitutes a U static-duration array into a checked pointer return.
2. Mode 10 substitutes an escaped address of a U stack-local array into the same return.

For each of three server roles and three return targets, both modes must terminate with a trusted-side SP3 `untracked` rejection and a `u_unclassified` rejected census event. The trusted bridge must reject before copying/dereferencing. Source-level knowledge identifies the injected origin; the trusted check does **not** magically infer whether an untracked address is stack or global. These probes test denial, not the normal prevalence of U stack/global pointers. A separate verifier confirms the full 18-case Cartesian product and raw log hashes, injection records, rejection reasons, and checked return sites.

## Repeated fixed-operation census

The memcached diagnostic client exercises all six declared cache/watcher scenarios with five repetitions each. Each ordinary repetition completes 2,500 client operations; write-heavy completes 20,000. The observation window begins after preload and watcher setup, includes a fixed 0.5-second asynchronous drain, and ends before server teardown. Each row retains full raw trace SHA-256 and file, exact client operation count, storage/site/direction counts, and before/after loss counters. A separate verifier independently reparses all 30 traces, rechecks their hashes and operation/loss invariants, and recomputes every median and dispersion value.

For every scenario and site, the report contains the median, minimum, maximum, and population standard deviation of **pointer observations per 1,000 client operations** across the five repetitions. These are not unique pointer counts and must not be interpreted as runtime performance overhead. Asynchronous queue scheduling may still contribute dispersion; a fixed drain does not make asynchronous events deterministic.

## Existing mandatory regression gates

Keep the 50-case memcached normal/fault/upstream gate, the rsync native/isolated output comparisons, libyaml semantic signatures, nginx native/isolated request cases, and memcached independent performance/evidence validators unchanged. The isolated variants must preserve all externally observable behavior on tested workloads. Absence of a regression in these suites is not proof of whole-program observational equivalence.

## Reproducibility

CI uploads `memcached-results/u-storage-faults` and `memcached-results/pointer-origin-repeats` alongside the original results. The Python collectors emit `INTERSPEC_U_STORAGE_PROBE`, `INTERSPEC_POINTER_REPEAT_SAMPLE`, and `INTERSPEC_POINTER_REPEAT_SUMMARY` records into hosted workflow logs for independent review. All four application workflows also rerun the normal census with the expanded VMA categories.

Do not promote numerical claims to the paper until hosted jobs pass, trace provenance has been retained, normalized counts are verified, and their limitations are explained.
