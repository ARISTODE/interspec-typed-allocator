# YAML/libyaml Full Application Evaluation

This evaluation upgrades the previous YAML/libyaml boundary smoke test into a complete libyaml parser workload. The goal is to obtain the same evidence classes already available for rsync and memcached: functional equivalence, adversarial enforcement, a true Native baseline, an RLBox-only baseline, tracking without the final check, and full Extended SP3.

## Scope

The trusted side is a small YAML application driver and the untrusted side is the pinned libyaml parser. The untrusted parser runs inside RLBox wasm2c. The workload is a deterministic 1 MiB YAML document parsed repeatedly.

The application consumes scalar events produced by libyaml. The boundary wrapper copies each scalar value into a fixed 8 KiB sandbox staging allocation before T consumes it. This staging allocation is the explicit boundary helper site already represented by the YAML policy. It is not claimed to be a source-derived allocation inside libyaml's allocator abstraction.

## Compared configurations

* Native: the same pinned libyaml source compiled as an ordinary native library. No sandbox or boundary copy is present.
* RLBox-only: libyaml executes in RLBox wasm2c. T copies the 1 MiB input into U once per parse and copies scalar values back through the boundary staging buffer. No InterSpec allocation metadata or SP3 check executes.
* Tracking-only: the same RLBox path uses the trusted typed staging allocation and lifetime metadata, but bypasses the final T-side SP3 acceptance check for valid benchmark input.
* Extended SP3: the complete path additionally checks scalar pointers for liveness, expected type, and requested spatial extent before T copies the value.

Tracking and Extended SP3 use the same typed wasm module. The only benchmark difference between those two modes is the final SP3 check.

## Workload

The driver mechanically generates an exactly 1 MiB YAML document. It contains 256 key/value pairs with large scalar values plus deterministic filler. This keeps the input size comparable to the original InterSpec YAML workload while producing a moderate, repeatable number of protected scalar boundary values per parse.

Publication protocol:

    INTERSPEC_YAML_ITERATIONS=1000
    INTERSPEC_YAML_REPETITIONS=15
    INTERSPEC_YAML_WARMUPS=2
    bash scripts/run_yaml_libyaml_evaluation.sh yaml-libyaml-results

Hosted CI runs the full 1,000-parse workload with five paired repetitions to provide a reproducibility reference. Publication results use the same 1,000-parse workload with fifteen paired repetitions on controlled hardware.

The primary timing includes the repeated parse loop. For sandboxed configurations it also includes the per-iteration T-to-U copy of the 1 MiB input, because that copy is required by the copy-based isolation boundary. One-time process startup and sandbox construction occur before the timed loop.

## Correctness

For the same input and iteration count, Native, RLBox-only, tracking-only, and Extended SP3 must produce identical:

* event count,
* scalar count,
* total scalar bytes, and
* scalar-content hash.

A mismatch fails the evaluation rather than being treated as performance noise.

## Security validation

Faults are injected in U on the real parser-output path before T copies a scalar.

| Fault | Expected decision |
| --- | --- |
| live tracked allocation with the wrong trusted type | reject: wrong_type |
| ordinary sandbox allocation with no trusted metadata | reject: untracked |
| released typed allocation | reject: untracked |
| valid typed pointer with an excessive reported extent | reject: out_of_bounds |
| another live allocation of the same expected type | accept |

The final control deliberately demonstrates the current limit of SP3: liveness, type, and extent do not establish intended-object identity between two simultaneously live objects of the same type.

## Performance reporting

Every repetition contains all four configurations. Execution order rotates to reduce systematic order bias. The report derives paired ratios per repetition:

    RLBox isolation          = RLBox / Native - 1
    tracking/provenance      = Tracking / RLBox - 1
    final validation         = InterSpec / Tracking - 1
    InterSpec over RLBox     = InterSpec / RLBox - 1
    InterSpec over Native    = InterSpec / Native - 1

The percentages are not additive because their denominators differ.

Hosted GitHub Actions values are reproducibility references. Final paper numbers should be regenerated on the same controlled machine used for rsync and memcached, with fixed CPU policy and identical source revisions.

## Reproducibility

Run:

    bash scripts/run_yaml_libyaml_evaluation.sh yaml-libyaml-results

The output directory contains the generated 1 MiB document, correctness outputs, security evidence, raw paired performance samples, per-run statistics, summary CSV, environment metadata, and a mechanically rendered YAML_RESULTS.md.
