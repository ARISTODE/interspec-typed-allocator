# InterSpec benchmark evidence audit, 1 November 2026 (Pacific)

## Outcome

The archived hosted reference contains **400 raw application samples** across **12 workloads and four modes**. The current independent audit recomputes every paired overhead from those source rows. All sample matrices are complete; the Memcached and Nginx records have zero reported workload errors and no detected drops in the recorded counters. The three archived ZIP hashes match the saved provenance manifest.

These are **hosted reference results**, not controlled publication measurements. The studies ran in separate environments and must not be pooled into a single cross-application geometric mean. The new SP3 pool and nonheap extension is not part of these archived builds.

## Recomputed paired overhead relative to RLBox

Positive values indicate higher runtime or lower throughput. Values are the **median of paired repetition-level percentages**, not the percentage difference of unpaired medians.

| Application | Workload | Repetitions per mode | SP3 overhead vs RLBox |
| --- | --- | ---: | ---: |
| Memcached/bipbuffer | balanced_1c | 5 | +1.47% |
| Memcached/bipbuffer | balanced_8c | 5 | +2.45% |
| Memcached/bipbuffer | read_heavy_1k | 5 | +2.77% |
| Memcached/bipbuffer | write_heavy | 5 | +2.05% |
| Memcached/bipbuffer | watch_light | 5 | −0.75% |
| Memcached/bipbuffer | watch_moderate | 5 | +1.57% |
| Nginx/PCRE8 | 4 client threads | 5 | −0.58% |
| Nginx/PCRE8 | 8 client threads | 5 | −0.77% |
| YAML/libyaml | 1 MiB, 1,000 parses | 15 | +0.0074% |
| Rsync/popt | option_parse | 15 | −6.2546% |
| Rsync/popt | local_dry_run | 15 | +0.0560% |
| Rsync/popt | file_sync_194mb | 15 | +0.3704% |

These values match the existing selected summary and the newer Memcached completion report at their published precision. The original upstream ZIP/libzip benchmark is not represented by a verified isolation source or raw sample set here.

## Evidence mapping

| Dataset | Raw samples | GitHub evidence | Source in this repository |
| --- | ---: | --- | --- |
| Memcached | 120 | [hosted CI 38092306794](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/38092306794) | `evaluation/results/completion/hosted-38092306794/matrix-raw.csv` |
| Nginx | 40 | [hosted CI 37835791042](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/37835791042) | `evaluation/results/nginx-pcre/hosted-37835791042/performance/samples.csv` |
| YAML | 60 | [hosted CI 37593628736](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/37593628736) | `evaluation/results/yaml-libyaml/hosted-37593628736/yaml-performance.csv` |
| Rsync | 180 | Archived local paired raw rows; see provenance in repository | `evaluation/results/rsync-popt/rsync-performance.csv` |

`tools/audit_hosted_reference.py` enforces expected modes, workloads, repetitions and absence of duplicate/missing cells, checks documented correctness counters, verifies archived hashes and recomputes the paired overheads. The workflow records the audit as a fresh artifact; it does not alter the original raw measurements.

## Publication readiness

**Not ready.** `EVALUATION_COMPLETION.md` and `CONTROLLED_EVALUATION.md` require a dedicated controlled Linux host, physical CPU isolation, clean matching builds, and fifteen paired repetitions. The Memcached publication matrix alone specifies 360 samples with thirty-second windows and five-second warmups, consuming roughly 3.5 hours of traffic. No dedicated host has been identified and no cloud resources have been provisioned.

Before revising the manuscript:

1. Run the controlled host protocol and independent verifiers for all final applications and runtime microbenchmarks.
2. Reconcile the original paper's SP1/SP2/SP3 policy coverage and PoCs against executed implementation and raw evidence.
3. Establish the source and workload provenance for the original ZIP/libzip row or explicitly omit it from verified claims.
4. Re-run the relevant benchmark protocol after the new SP3 layout-aware runtime is actually integrated. Its unit test passing alone does not establish application deployment or overhead.

Until then, present this table only as **exploratory hosted reference**; do not cite negative or near-zero overheads as publication conclusions.
