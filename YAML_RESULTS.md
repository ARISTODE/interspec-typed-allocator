# YAML/libyaml Evaluation Results

The full libyaml parser processes a deterministic 1 MiB YAML document. Hosted CI values are reference measurements; publication numbers require the same driver on controlled hardware.

Reference benchmark commit: `5061877dd2a1ee349faf5d3b249471a6c955cd00`.

## Correctness and security

Native, RLBox-only, tracking-only, and Extended-SP3 produce identical event counts, scalar counts, scalar byte counts, and scalar-content hashes. The benchmark produces **512 scalar boundary values per parse**, so the 1,000-iteration performance workload executes **512,000 SP3 validations** in the full configuration.

Wrong-type, ordinary untracked, released, and excessive-extent scalar pointers are rejected before trusted copying. A live same-type substitution is accepted with unchanged contents, which matches the current SP3 scope and demonstrates that intended-object identity is not enforced.

## Full 1,000-parse hosted reference

Configuration: exactly 1 MiB input, 1,000 parses per timed run, 5 paired repetitions, 1 warmup. Sandboxed variants include the per-iteration T-to-U copy of the 1 MiB input. One-time sandbox creation occurs before the timed loop.

| Native median (ms) | RLBox median (ms) | Tracking median (ms) | InterSpec median (ms) | RLBox vs Native | Tracking vs RLBox | Validation vs Tracking | InterSpec vs RLBox | InterSpec vs Native |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 6846.004 | 11611.379 | 11890.698 | 11899.511 | +69.51% | +2.41% | +0.07% | +2.48% | +73.82% |

Overheads are medians of paired per-repetition ratios, rather than ratios of the displayed medians.

The key InterSpec result is the incremental cost over an already isolated RLBox deployment: **+2.48% total**. Of that, the final liveness/type/extent validation itself contributes only **+0.07%** over tracking-only in this workload; most of the incremental cost is associated with the typed boundary-staging configuration. RLBox isolation and copy-based marshalling account for the much larger Native-to-RLBox delta.

Across all five repetitions, InterSpec-vs-RLBox ranged from **+2.37% to +2.60%**, and InterSpec-vs-Native ranged from **+73.48% to +74.12%**, so the full hosted workload is substantially more stable than the short smoke run.

## Raw paired samples

| Repetition | Native (ms) | RLBox (ms) | Tracking (ms) | InterSpec (ms) |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 6846.004 | 11624.484 | 11890.698 | 11899.511 |
| 1 | 6857.923 | 11610.946 | 11891.023 | 11897.276 |
| 2 | 6844.467 | 11627.120 | 11886.027 | 11917.827 |
| 3 | 6853.658 | 11611.379 | 11890.807 | 11913.306 |
| 4 | 6844.364 | 11601.812 | 11887.791 | 11889.405 |

## Publication protocol

The final controlled-host run uses the same benchmark and 1,000-parse workload with 15 paired repetitions:

    INTERSPEC_YAML_ITERATIONS=1000
    INTERSPEC_YAML_REPETITIONS=15
    INTERSPEC_YAML_WARMUPS=2
    bash scripts/run_yaml_libyaml_evaluation.sh yaml-libyaml-results

Hosted CI establishes correctness, security behavior, workload stability, and the complete measurement pipeline. Controlled-hardware numbers remain the publication source of truth.
