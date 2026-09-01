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

Evidence: machine-readable counts of source-derived allocation sites, precise source locations, trusted-use policies, integration helper allocation sites, pointer shapes, and adversarial coverage across every completed boundary.

Source-derived and helper sites are reported separately. Test-only adversarial helper sites are also reported separately and are excluded from the automation denominator. An allocator abstraction such as `pcre_malloc` or `YAML_MALLOC` must not be reported as direct-malloc inference merely because the final policy is generated.

### Q3: Performance

What is the cost of trusted metadata operations, and what incremental cost does final T-side Extended-SP3 pointer validation add to real boundary/application use?

Evidence is split into three levels:

1. Runtime microbenchmarks from P6 measure metadata lookup/allocation operations directly.
2. Real-boundary paired measurements operate repeatedly on the same valid U object and compare identical copy/use behavior with versus without the final type/liveness/spatial acceptance check.
3. Full-rsync paired measurements execute the same pinned application workloads with the same NaCl module, typed allocation/provenance, and marshalling, changing only the final trusted pointer acceptance validation in a measurement-only baseline build.

These paired measurements quantify **incremental validation overhead**. They are not a measurement of the total cost of Extended SP3 relative to plain RLBox, because trusted typed allocation/provenance remains enabled in both variants.

Performance numbers are measurements, not CI pass/fail criteria. Every result carries environment and iteration/repetition metadata.

### Q4: Reproducibility

Can a fresh environment regenerate policy snapshots, execute security tests, produce evaluation tables, build the installable package, and reproduce the pinned RLBox + NaCl integrations?

Evidence: one P8 driver, CI artifacts, pinned revisions, environment metadata, and generated JSON/CSV/Markdown summaries.

## 3. Baseline definitions

P8 uses explicit baseline names.

`runtime-only`: direct trusted runtime microbenchmarks with no sandbox crossing. Used only to characterize metadata structures.

`tracked_no_check`: a measurement-only build/path with the same sandbox, typed allocation metadata, allocation-site provenance, generated policy registration, API marshalling, and valid workload as the security configuration, but with the final T-side Extended-SP3 acceptance check bypassed. It is never used for attack/correctness tests.

`extended_sp3`: the normal security configuration with generated policy, PolicyRuntime, trusted metadata, and final liveness/type/spatial validation before trusted pointer use.

For a paired measurement:

```text
overhead = (extended_sp3_time / tracked_no_check_time - 1) * 100%
```

This quantity must be labeled **incremental validation overhead**. A future true `rlbox_only` baseline would additionally remove typed allocation/provenance and would answer a different question: total incremental cost of the whole Extended-SP3 mechanism over RLBox.

A native, unsandboxed application can be reported as additional context, but it is not the denominator for either claim.

## 4. Deterministic completion criteria

P8 is complete only when the following are CI-gated:

1. P6 security cases remain green.
2. P7c generalization report is complete.
3. All checked-in real-boundary policy snapshots regenerate exactly.
4. All completed boundaries declare pinned upstream revisions.
5. Every P8 boundary has at least one trusted-use policy and explicit adversarial coverage metadata.
6. Integration helper sites and adversarial test-only helper sites are distinguished in machine-readable reporting.
7. The release package contains the P8 evaluation plan, generated deterministic report/results, and reproduction instructions.
8. The complete RLBox + NaCl regression remains green.

## 5. Performance reporting rules

Performance jobs do not fail because a timing crosses a threshold.

Each measurement records:

1. commit SHA,
2. operating system and kernel,
3. compiler/toolchain information when applicable,
4. CPU model when available,
5. iteration/repetition counts,
6. workload identifier,
7. baseline identifier,
8. raw sample measurements,
9. median and arithmetic mean,
10. paired incremental overhead statistics.

Measurement order alternates between baseline and Extended SP3 across repetitions to reduce systematic warmup/frequency bias.

Hosted-runner numbers are suitable as a reproducible CI reference and for validating the measurement pipeline. Final publication performance numbers should be regenerated on controlled hardware using the same machine-readable formats.

## 6. Final paper-facing outputs

P8 produces these evidence classes without manual transcription:

1. `p8-deterministic.json`: security/generalization/automation claim record.
2. `p8-automation.csv`: one row per real boundary.
3. P6 `runtime.csv`: trusted metadata microbenchmark samples.
4. `interspec-p8-boundary-performance.csv` and summary: raw/aggregated real-boundary validation measurements.
5. `interspec-p8-rsync-performance.csv` and summary: raw/aggregated complete-rsync paired measurements.
6. `P8_RESULTS.md`: mechanically derived paper-facing reference summary.

Final figures/tables should consume these JSON/CSV outputs directly so the paper and repository use the same source of truth.
