# Rsync/popt Evaluation Results

The rsync/popt path is now a complete application evaluation rather than a boundary-only smoke test. The protected binary runs the pinned bundled popt parser inside RLBox wasm2c and executes real rsync transfers with the Extended-SP3 allocation policy.

## Functional and security validation

The application experiment suite exercises archive transfer, a 1 MiB maximum-size filter, dry-run output, update/delete/backup behavior, invalid numeric options, and unknown options against a native reference built from the same rsync revision.

Observed application-path security results:

* 12/12 invalid pointer injections on the real option-return, string-slot copyback, and positional-argument paths are rejected before the corrupted pointer is copied into trusted use.
* Wrong-type pointers are rejected as wrong_type.
* Ordinary untracked and released pointers are rejected as untracked.
* Unterminated string contents are rejected by the bounded boundary-copy validation.
* 3/3 live same-type substitutions are accepted with preserved contents, demonstrating the current lack of intended-object identity binding.
* The copyback canary preserves the trusted destination even when U redirects its option destination.
* The shadow-refresh regression preserves T-side updates made between parser calls.

These results are application evidence for the tested rsync paths, not exhaustive coverage of remote transport, daemon mode, authentication, host popt aliases/configuration, or the complete rsync option space.

## Four-way performance reference

The report-facing P11 harness measures four matched variants:

* Native: the pinned rsync source with its unmodified bundled popt.
* RLBox only: bundled popt isolated with RLBox wasm2c, with no active InterSpec typed allocation or final SP3 check.
* Tracking/no-check: trusted allocation-site provenance and typed allocation metadata enabled, final SP3 acceptance check bypassed only for valid performance input.
* Extended SP3: the complete mechanism.

The hosted reference below uses 15 paired repetitions and 2 warmups on an AMD EPYC 9V45 GitHub Actions runner. It is a reproducibility reference, not the controlled-hardware publication result.

| Workload | Native median (ms) | RLBox median (ms) | Tracking median (ms) | InterSpec median (ms) | RLBox vs Native | Tracking vs RLBox | Validation vs Tracking | InterSpec vs RLBox | InterSpec vs Native |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 194 MiB local file sync | 613.280 | 613.998 | 614.371 | 616.161 | +0.14% | -0.44% | +0.30% | +0.37% | +0.72% |
| Local dry run | 41.678 | 42.504 | 42.556 | 42.558 | +1.99% | +0.20% | +0.00% | +0.06% | +2.03% |
| Option parse/startup | 0.648 | 1.174 | 1.369 | 1.128 | +80.46% | +13.42% | -14.20% | -6.25% | +73.77% |

Overheads are medians of paired per-repetition ratios, so they are not necessarily equal to ratios of the displayed medians. Negative values in the sub-millisecond option-parse workload are treated as timing noise rather than speedups.

The 194 MiB transfer is the report-relevant workload. Its hosted reference shows approximately 0.37% incremental Extended-SP3 overhead over RLBox-only and 0.72% over Native. The local dry-run result is similarly small. The option-parse process is too short for stable percentage interpretation and should not be used as the main paper performance claim.

## Publication protocol

The same script is used for the controlled-host run:

    INTERSPEC_P11_REPETITIONS=31
    INTERSPEC_P11_WARMUPS=3
    INTERSPEC_P11_CPU=2
    bash scripts/run_p11_wasm2c_performance.sh p11-wasm2c-results

The controlled run should keep CPU frequency policy fixed, pin the measured process when appropriate, and retain the raw CSV and environment metadata. The raw paired samples remain the source of truth.

## Reproduction

Run:

    bash scripts/run_sp3_diagnostics.sh results/sp3-diagnostics
    bash scripts/run_p11_wasm2c_performance.sh p11-wasm2c-results

The first command regenerates functional/security evidence. The second produces the Native/RLBox/tracking/Extended-SP3 performance matrix and a mechanically rendered P11_RESULTS.md.
