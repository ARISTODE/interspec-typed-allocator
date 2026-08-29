# P8 Paper-Quality Evaluation

P0 through P7c established the Extended-SP3 mechanism and showed that the same generated policy/runtime path can enforce pointer type, liveness, and object-bounded spatial safety on several real library boundaries. P8 turns that implementation into a reproducible evidence package suitable for a paper or artifact evaluation.

## Research questions

### RQ1 — Security effectiveness

Does Extended SP3 reject pointer corruptions that satisfy the original sandbox-domain check?

The evidence separates tracked wrong type, same-domain untracked pointers, containing-object bound violations, stale pointers, unauthorized allocation callback sites, and TypeId/TypeHash misuse. Boundary-level evidence comes from the combined RLBox + NaCl regression; runtime-level edge cases come from the P6 security matrix. A passing P8 result requires both layers.

### RQ2 — Automation and generalization

How much security policy comes from source analysis, and how much requires explicit boundary knowledge?

P8 reports four quantities separately:

1. precise source-derived allocation sites;
2. explicit integration helper sites required for allocator abstractions such as `pcre_malloc` or `YAML_MALLOC`;
3. adversarial-only helper sites used solely to construct negative tests;
4. trusted-use evidence from real application source versus a small analysis adapter.

This prevents attack harness code from being counted as integration effort and prevents representative P7c adapters from being described as automatic discovery in real application code.

### RQ3 — Incremental enforcement cost

What does Extended SP3 add beyond domain/range validation?

P8 has two paired microbenchmark layers.

**Primary backend comparison.** Inside the pinned RLBox + NaCl process, the same valid 8-byte range is checked using RLBox's actual `is_pointer_in_sandbox_memory()` predicate at both ends of the range and then using Extended SP3:

```text
RLBox domain/range baseline:
    begin pointer is in U memory
    + end pointer is in U memory

Extended SP3:
    live tracked allocation
    + expected trusted type
    + requested extent within the containing object
```

Both sides reload the pointer from a volatile source on every operation so the compiler cannot hoist the pure domain predicate out of the loop. The benchmark repeats each measurement at least three times, uses the median, retains min/max and every evidence file, and sweeps 1, 16, 256, 4,096, and 16,384 live allocations.

**Secondary primitive decomposition.** The ordinary runtime benchmark also compares Extended SP3 with an idealized arithmetic-only U-domain/range predicate. This is a lower bound used to expose metadata lookup cost; it is not presented as the measured cost of the RLBox backend.

The paper-facing primitive metrics are absolute additional nanoseconds/check and the Extended/baseline ratio. Absolute cost is emphasized because the domain-only baseline is intentionally very cheap.

P8 still does not conflate pointer-check cost with RLBox transitions or application-specific marshalling. The real rsync, bipbuffer, PCRE, and libyaml paths remain functional/security regressions. An end-to-end application performance claim requires a separate matched RLBox-only build and repeated workload timing.

### RQ4 — Reproducibility and claim boundaries

Can another evaluator regenerate every reported table from the repository, and do the generated results preserve the system's limitations?

A single P8 driver produces machine-readable CSV/JSON plus a generated Markdown summary. CI uploads those outputs as an artifact. The report must preserve these limitations:

1. no general control-flow integrity;
2. U-owned object contents remain untrusted;
3. no physical address reuse / generation identity;
4. no intended-object identity among simultaneously live allocations of the same trusted type;
5. arbitrary library ABI marshalling remains application-specific;
6. memcached, PCRE, and libyaml P7c trusted-use policies are representative analysis adapters rather than original-application T-side inference.

## P8 outputs

```bash
bash scripts/run_p8_evaluation.sh p8-results
```

produces the raw repeated runtime measurements and the paper-facing outputs:

```text
p8-results/
  security.csv
  runtime-runs/
  runtime.csv
  rlbox-runtime.csv                 # when matched backend evidence is supplied
  p7c-generalization.json
  automation.csv
  security-runtime.csv
  security-boundaries.csv
  runtime-overhead.csv              # idealized primitive decomposition
  rlbox-runtime-overhead.csv        # matched RLBox/NaCl comparison
  summary.json
  summary.md
  environment.txt
  ctest.txt
```

`tools/p8_collect.py` validates the evidence contract and refuses to generate a required table when a security case, boundary attack, runtime population, or matched baseline/Extended pair is missing.

## Acceptance criteria

P8 is complete when all of the following hold on one exact commit.

1. Core, policy inference, P6 evaluation, packaging, and combined RLBox + NaCl regressions are green.
2. `tools/p7c_report.py --require-complete` remains green.
3. P8 reports all four real boundaries and excludes adversarial-only helper sites from integration effort.
4. Each trusted-use source is labeled `real_application_source` or `analysis_adapter`.
5. The idealized runtime results contain paired domain-only and Extended-SP3 measurements at every required population.
6. The matched backend results contain RLBox domain/range and Extended-SP3 medians at every required population.
7. The collector fails closed on missing/mismatched evidence.
8. Security tables contain both runtime-level and real-boundary evidence.
9. CI uploads the complete P8 result directory.
10. The generated summary preserves the limitations above.

## Interpretation discipline

P8 strengthens the evidence; it does not broaden the security claim. A fact is called source-derived only when the checked-in analysis derives it from pinned source. A boundary helper remains an explicit policy declaration. A representative trusted-use adapter demonstrates enforcement generality but is not equivalent to automatic inference from the original trusted application.

Hosted CI measurements are regression/reference evidence, not final publication performance numbers. The final paper timing table should be regenerated on a dedicated, otherwise idle machine using the controlled procedure in `REPRODUCIBILITY.md`.
