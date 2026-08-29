# P8 Paper-Quality Evaluation and Finalization

P8 does not add a new security mechanism. Its purpose is to turn the completed P0-P7c prototype into a research artifact whose claims, metrics, baselines, and reproduction path are explicit enough to support the final paper.

## 1. Security claim

For a trusted use covered by Extended SP3, T accepts a U-controlled pointer only when trusted metadata shows that:

1. the pointer is contained in a currently live tracked allocation,
2. the allocation has the expected trusted type for that use, and
3. the complete requested byte extent is contained in that allocation.

For precise source-derived allocation sites, the allocation type is authorized by the analyzed allocation instruction and trusted NaCl callback execution state rather than by a TypeId selected by U. Explicit boundary-helper allocations are trusted policy declarations and use the same site-authenticated metadata path.

The mechanism does not establish general control-flow integrity, content integrity, intended-object identity among multiple simultaneously live allocations of the same type, or temporal identity under physical address reuse.

## 2. Evaluation questions

P8 answers four questions.

### Q1: Security

Does the implementation reject the corruption classes in the Extended-SP3 claim while preserving valid executions?

Evidence: the P6 security matrix plus real-boundary adversarial tests for wrong type, untracked same-domain pointers, stale pointers, and spatial overflow where applicable.

### Q2: Automation and coverage

How much security policy is derived automatically, and where are explicit boundary declarations still required?

Evidence: machine-readable counts of source-derived allocation sites, precise source locations, trusted-use policies, helper allocation sites, pointer shapes, and adversarial coverage across every completed boundary.

Source-derived and helper sites are reported separately. An allocator abstraction such as `pcre_malloc` or `YAML_MALLOC` must not be reported as direct-malloc inference merely because the final policy is generated.

### Q3: Performance

What is the cost of trusted metadata lookup/checking, and what is the end-to-end cost on real boundary workloads relative to a clearly defined baseline?

Evidence is split into two levels:

1. Runtime microbenchmarks from P6 measure metadata operations directly.
2. End-to-end boundary/application measurements compare the same pinned workload and sandbox configuration with and without Extended-SP3 pointer validation.

Performance numbers are measurements, not CI pass/fail criteria. Every result must carry environment and iteration metadata.

### Q4: Reproducibility

Can a fresh environment regenerate policy snapshots, execute security tests, produce evaluation tables, build the installable package, and reproduce the pinned RLBox + NaCl integrations?

Evidence: one P8 driver, CI artifacts, pinned revisions, environment metadata, and generated JSON/CSV/Markdown summaries.

## 3. Baseline definitions

P8 uses explicit baseline names.

`runtime-only`: direct trusted runtime microbenchmarks with no sandbox crossing. Used only to characterize metadata structures.

`rlbox-boundary-baseline`: the same pinned RLBox + NaCl boundary workload and marshalling path with Extended-SP3 acceptance checks disabled for measurement only. This is not a security configuration and must never be used by correctness tests.

`extended-sp3`: the full generated policy + PolicyRuntime + trusted metadata + liveness/type/spatial checks.

The end-to-end overhead is:

```text
overhead = (extended_sp3_time / rlbox_boundary_baseline_time - 1) * 100%
```

A native, unsandboxed application can be reported as additional context, but it is not the denominator for the incremental Extended-SP3 overhead claim.

## 4. Deterministic completion criteria

P8 is complete only when the following are CI-gated:

1. P6 security cases remain green.
2. P7c generalization report is complete.
3. All checked-in real-boundary policy snapshots regenerate exactly.
4. All completed boundaries declare pinned upstream revisions.
5. Every P8 boundary has at least one trusted-use policy and explicit adversarial coverage metadata.
6. The release package contains the P8 evaluation plan, generated deterministic report, and reproduction instructions.
7. The complete RLBox + NaCl regression remains green.

## 5. Performance reporting rules

Performance jobs do not fail because a timing crosses a threshold.

Each measurement records:

1. commit SHA,
2. operating system and kernel,
3. compiler and CMake versions,
4. CPU model when available,
5. iteration/repetition counts,
6. workload identifier,
7. baseline identifier,
8. raw sample measurements,
9. median and arithmetic mean,
10. computed incremental overhead where a paired baseline exists.

Hosted-runner numbers are suitable for regression visibility and artifact plumbing, but final paper numbers should be rerun on a controlled machine and copied from the same machine-readable output format.

## 6. Final paper-facing outputs

P8 should produce these files without manual transcription:

1. `p8-deterministic.json`: security/generalization/automation claim record.
2. `p8-automation.csv`: one row per real boundary.
3. `p8-performance.csv`: raw paired timing measurements.
4. `p8-performance-summary.csv`: aggregated timings and overhead.
5. `P8_RESULTS.md`: generated or mechanically derived paper-facing summary.

The final figures can consume the CSV files directly so the paper tables and repository evidence share one source of truth.
