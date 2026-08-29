# P8 Paper-Quality Evaluation

P0 through P7c established the Extended-SP3 mechanism and showed that the same generated policy/runtime path can enforce pointer type, liveness, and object-bounded spatial safety on several real library boundaries. P8 turns that implementation into a reproducible evidence package suitable for a paper or artifact evaluation.

## Research questions

### RQ1 — Security effectiveness

Does Extended SP3 reject pointer corruptions that satisfy the original sandbox-domain check?

The paper evidence separates the following classes:

1. tracked pointer with the wrong trusted allocation type;
2. same-domain pointer with no trusted allocation metadata;
3. correct allocation/type paired with an extent that escapes the containing object;
4. stale pointer after logical release/reallocation;
5. allocation callback reached from an unauthorized instruction;
6. TypeHash/TypeId misuse and collision cases already covered by P5/P6.

Boundary-level evidence is drawn from the combined RLBox + NaCl regression. Runtime-level edge cases are drawn from the P6 security matrix. A passing P8 security result requires both layers.

### RQ2 — Automation and generalization

How much security policy comes from source analysis, and how much requires explicit boundary knowledge?

P8 reports four quantities separately instead of collapsing them into a single “automation percentage”:

1. precise source-derived allocation sites;
2. explicit integration helper sites required because the library allocation path uses an abstraction such as `pcre_malloc` or `YAML_MALLOC`;
3. adversarial-only helper sites used solely to construct negative tests;
4. trusted-use evidence derived from real application source versus a small analysis adapter.

This distinction prevents attack harness code from being counted as integration effort and prevents representative P7c use adapters from being described as automatic discovery in real application code.

### RQ3 — Incremental enforcement cost

What does Extended SP3 add beyond the original domain/range check?

The trusted runtime benchmark measures the same live pointer and byte extent in two ways:

```text
Original-SP3-style baseline:
    pointer/extent lies in permitted U domain

Extended SP3:
    live tracked allocation
    + expected trusted type
    + requested extent within the containing object
```

The primary primitive metric is `extended_ns / domain_only_ns` and the absolute additional nanoseconds per check. Measurements are swept over allocation populations so the ordered containing-allocation lookup cost is visible rather than hidden in one small configuration.

P8 does not conflate this primitive cost with RLBox transition and application-marshalling cost. End-to-end RLBox workloads remain part of the functional regression, while an application-level performance claim is made only when a matched baseline and repeated timing methodology are available.

### RQ4 — Reproducibility and claim boundaries

Can another evaluator regenerate every reported table from the repository, and do the generated results preserve the system’s limitations?

A single P8 driver produces machine-readable CSV/JSON plus a generated Markdown summary. CI uploads those outputs as an artifact. The report must explicitly preserve these limitations:

1. no general control-flow integrity;
2. U-owned object contents remain untrusted;
3. no physical address reuse / generation identity;
4. no intended-object identity among simultaneously live allocations of the same trusted type;
5. arbitrary library ABI marshalling remains application-specific;
6. PCRE/libyaml trusted-use policies in P7c are representative analysis adapters rather than real nginx/libyaml application-source inference.

## P8 outputs

Running:

```bash
bash scripts/run_p8_evaluation.sh p8-results
```

produces:

```text
p8-results/
  security.csv
  runtime.csv
  p7c-generalization.json
  automation.csv
  security-boundaries.csv
  runtime-overhead.csv
  summary.json
  summary.md
  environment.txt
  ctest.txt
```

The raw `security.csv` and `runtime.csv` come from the compiled runtime evaluation binaries. `tools/p8_collect.py` converts those raw measurements plus checked-in policy manifests into the paper-facing outputs.

## Acceptance criteria

P8 is complete when all of the following hold on one exact commit.

1. Core, policy inference, P6 evaluation, packaging, and combined RLBox + NaCl regressions are green.
2. `tools/p7c_report.py --require-complete` remains green.
3. P8 reports all four real boundaries and never counts adversarial-only helper sites as integration effort.
4. The report labels each trusted-use source as `real_application_source` or `analysis_adapter`.
5. Runtime results include paired domain-only and Extended-SP3 measurements at every lookup population.
6. The collector rejects missing or mismatched baseline/extended measurements instead of silently producing partial ratios.
7. Security tables include both runtime-level and real-boundary evidence.
8. CI uploads the complete P8 result directory.
9. The generated summary includes the preserved limitations above.

## Interpretation discipline

P8 is intended to strengthen the evidence, not broaden the claim. A result should be reported as “source-derived” only when the checked-in analysis actually derives it from the pinned source. A boundary helper is an explicit policy declaration, even when the surrounding library source is real. A representative trusted-use adapter demonstrates enforcement generality, but it is not equivalent to proving that the original application’s T-side use was inferred automatically.
