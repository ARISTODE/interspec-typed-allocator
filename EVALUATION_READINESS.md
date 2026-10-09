# Evaluation readiness audit

Verified on 2026-10-09 against published PR #20 at `9d99966`.

All four selected applications have working integrations and reference results. **All planned evaluation results are not yet ready.** The remaining gaps are listed below; controlled publication measurements are still outstanding.

## Evidence inventory

| Evidence | Verified coverage | Readiness |
| --- | --- | --- |
| Application references | 12 workloads, 334 raw timed samples across rsync, memcached, YAML and nginx | Available; hosted/shared reference |
| Runtime microbenchmarks | 39 configurations × 5 repetitions = 195 raw samples | Available and recomputed from original artifact |
| Latest runtime CI smoke | 39 configurations, one sample each at 9d99966's CI merge revision | Available separately; not a repeated reference |
| P8 boundary validation microbenchmarks | All four boundaries, seven pairs each, 20,000 iterations per sample | CI summary verified; NaCl backend |
| Memcached SP3 frequency | Six profiles, five observe successful checks | Write-heavy coverage missing |
| Memcached six-scenario tracking-only comparison | Native/RLBox/InterSpec are present | Tracking-only cells missing |
| wasm2c transition/copy/wrapper breakdown and boundary frequency | Planned in MEMCACHED_PERFORMANCE_PLAN.md | Not collected |
| Controlled publication run | Application and microbenchmark protocols documented | Not run |

Application numbers and baseline definitions: [SELECTED_EVALUATION_RESULTS.md](SELECTED_EVALUATION_RESULTS.md). CI at the published head passed core, memcached, P10 and nginx PR workflows. Nginx includes 24/24 cases, two-worker operation and two graceful reloads. The implementation stack remains unmerged.

## Repeated runtime reference

Source: memcached workflow 37593628863, five repetitions and 200,000 iterations for the ordinary check loops. This reference uses GCC 13.3.0 on a hosted x86_64 runner, with four CPUs available and no requested affinity. These are trusted runtime measurements with no sandbox crossing.

| Operation | Live allocations | Median ns/op | Min to max ns/op |
| --- | ---: | ---: | ---: |
| shared_lock | 2 | 8.45 | 7.83 to 8.90 |
| metadata_lookup | 2 | 4.45 | 4.32 to 4.48 |
| type_compare | 2 | 1.54 | 1.54 to 1.65 |
| bounds_check | 2 | 1.64 | 1.54 to 1.75 |
| check_live | 2 | 11.66 | 11.55 to 11.80 |
| check_interior | 2 | 11.94 | 11.89 to 12.01 |
| check_wrong_type | 2 | 12.28 | 12.21 to 12.31 |
| remaining_bytes | 2 | 11.87 | 11.85 to 11.90 |
| allocate | 16384 | 82.37 | 79.44 to 82.67 |
| allocate_from_site | 16384 | 76.50 | 74.64 to 80.45 |
| release | 16384 | 38.91 | 37.95 to 40.19 |

Primitive costs are independent and must not be added. Use `check_live` for the direct production check cost. Allocation/release rows measure 16,384 operations per repetition.

| Live allocations | Full check median ns/op |
| ---: | ---: |
| 2 | 11.66 |
| 16 | 12.82 |
| 256 | 18.48 |
| 4096 | 28.07 |
| 16384 | 32.98 |

| Trusted threads | Concurrent check median ns/op |
| ---: | ---: |
| 1 | 55.25 |
| 2 | 70.01 |
| 4 | 81.86 |
| 8 | 82.24 |

Concurrent ns/op divides total elapsed time by aggregate completed checks. It includes thread creation/join and contention over 4,096 tracked allocations, so it is not individual request latency or a linear scalability claim. Eight threads oversubscribe this four-CPU runner.

The complete 39-row matrix is in [microbenchmark-summary.csv](evaluation/results/selected/microbenchmark-summary.csv), with five raw samples per row in the retained source. The latest single-pass CI smoke is kept separately and is not substituted into this repeated reference.

## P8 boundary reference

| Boundary | Tracking without final validation ns/op | Extended SP3 ns/op | Paired repetitions |
| --- | ---: | ---: | ---: |
| memcached_bipbuffer | 2.865 | 21.683 | 7 |
| nginx_libpcre | 2.865 | 22.633 | 7 |
| rsync_popt | 4.874 | 23.227 | 7 |
| yaml_libyaml | 2.865 | 22.388 | 7 |

These NaCl measurements reuse a valid U object and time trusted copy/use with versus without the final check. They retain allocation tracking in both modes and do not time a sandbox transition in each iteration. They do not replace the outstanding wasm2c Native-to-RLBox decomposition or measure total application overhead.

Source: [CI run 37840970704](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/37840970704), job 113529933478, artifact 11577986711. The timestamped summary is retained locally. Its paired raw CSV exists in that CI artifact; artifact download returned HTTP 403 in this workspace, so those pairs were not independently recomputed here. Runtime raw data above was independently verified from the already retained memcached archive.

## Remaining results

1. Tracking-only samples are absent from the selected six-scenario matrix; the separate two-workload pilot does not fill these cells.
2. The 1,000-operation write-heavy diagnostic profile records zero successful checks; no direct check-cost estimate is valid.
3. Empty native versus RLBox call, wrapper mutex, pointer confinement, both copy directions at 64/256/1024/4096 bytes, and complete request+push/offer/peek_all/poll operation costs are outstanding.
4. RLBox invocations and T-to-U/U-to-T bytes per client operation are not recorded; existing counts cover SP3 checks only.
5. All application and microbenchmark publication measurements must use the documented controlled host protocol; memcached needs 30-second intervals, 5-second warmups, 15 pairs and disjoint CPU affinity.

The missing wasm2c breakdown is distinct from the completed P8 boundary validation measurements. An observed zero in a short diagnostic profile establishes missing coverage, not zero check overhead.

## Reproduction

```sh
python3 tools/summarize_selected_evaluation.py --nginx-results evaluation/results/nginx-pcre/hosted-37835791042
python3 tools/audit_evaluation_readiness.py
```

The audit verifies original artifact SHA-256 values and retained extracts, raw application source hashes, all runtime cells and repetitions, elapsed-time arithmetic, runtime summaries, and frequency count arithmetic. It fails on missing runtime samples or changed evidence. Readiness and source hashes are saved under `evaluation/results/selected/`.
