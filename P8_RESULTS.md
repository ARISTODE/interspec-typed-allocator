# P8 Results

P8 turns the Extended-SP3 implementation into a reproducible evidence package. The results below distinguish deterministic security/automation findings from hosted-CI performance measurements that are useful as reference data but should be rerun on a controlled machine before publication.

## RQ1 — Does Extended SP3 stop pointer corruptions that domain-only SP3 accepts?

Yes for every real-boundary attack class in the current evaluation.

The P8 RLBox tests first establish that the malicious pointer, or the entire malicious pointer/extent when the policy includes a runtime length, passes the pinned RLBox NaCl sandbox-domain predicate. The same value is then evaluated by Extended SP3 and rejected for a stronger allocation property.

| Boundary | Attack | Original domain/range validation | Extended SP3 |
| --- | --- | --- | --- |
| rsync/popt | tracked wrong type | accepts | `wrong_type` |
| rsync/popt | untracked U pointer | accepts | `untracked` |
| memcached/bipbuffer | tracked wrong type | accepts | `wrong_type` |
| memcached/bipbuffer | untracked U pointer | accepts | `untracked` |
| memcached/bipbuffer | oversized extent | accepts | `out_of_bounds` |
| nginx/libpcre | tracked wrong type | accepts | `wrong_type` |
| nginx/libpcre | untracked U pointer | accepts | `untracked` |
| nginx/libpcre | oversized name-table extent | accepts | `out_of_bounds` |
| yaml/libyaml | tracked wrong type | accepts | `wrong_type` |
| yaml/libyaml | untracked U pointer | accepts | `untracked` |
| yaml/libyaml | oversized scalar extent | accepts | `out_of_bounds` |

Thus the real-boundary matrix contains **11/11 cases in which the original domain property is satisfied but Extended SP3 rejects the corrupted use**. The machine-readable boundary evidence records `domain_baseline=accept` together with the exact Extended-SP3 rejection reason for every row, and the collector fails if either side does not match the expected relation.

The lower-level runtime security matrix additionally requires and passes seven representative cases covering wrong type, untracked pointers, cross-allocation bounds, stale-after-free, stale-after-realloc, unknown TypeIds, and TypeHash collision rejection. The complete P6 matrix contains further lifetime, arithmetic, and allocation edge cases.

This result should be read narrowly. Extended SP3 proves that a consumed pointer is contained in a live allocation with the expected trusted type and sufficient object extent. It does not prove that the allocation is the one particular same-type logical object T intended when several such objects are simultaneously live.

## RQ2 — How much of the policy is source-derived?

P8 deliberately avoids one ambiguous “automation percentage.” It separates source-derived allocation policy, required integration helpers, attack-only helpers, and trusted-use provenance.

| Boundary | Source-derived allocation sites | Integration helper sites | Attack-only helper sites | Trusted-use policies | Trusted-use evidence |
| --- | ---: | ---: | ---: | ---: | --- |
| rsync/popt | 2 | 1 | 0 | 1 | real application source |
| memcached/bipbuffer | 1 | 0 | 1 | 1 | analysis adapter |
| nginx/libpcre | 0 | 1 | 1 | 1 | analysis adapter |
| yaml/libyaml | 0 | 1 | 1 | 1 | analysis adapter |

Across the four evaluated boundaries, production allocation policy contains **3 source-derived sites and 3 explicit integration helper sites**. Under that precisely defined denominator, 50% of the selected production allocation sites are source-derived. The three additional helper sites used only to construct wrong-type attacks are excluded from integration effort.

The reason for the explicit PCRE and libyaml helpers is visible in their real source. Their selected allocations go through allocator abstractions (`pcre_malloc` and `YAML_MALLOC`) rather than the direct `malloc` syntax currently handled by the precise source transformer. P8 records these as annotations instead of describing them as automatic inference.

Trusted-use provenance is more limited than allocation provenance in P7c. The rsync/popt use is inferred from real `rsync/options.c`; the memcached, PCRE, and libyaml uses are representative T-side analysis adapters. Therefore the current result is **1 real-application trusted-use policy and 3 analysis-adapter policies**. Those adapters demonstrate enforcement generality across pointer shapes, not complete automatic application integration.

## RQ3 — What is the incremental pointer-check cost?

P8 provides two paired microbenchmark views.

The stronger backend comparison runs inside the pinned RLBox + NaCl process. For the same valid 8-byte range it compares RLBox's actual sandbox-memory predicate on the beginning and end of the range with Extended SP3's live-allocation, expected-type, and containing-object-bound check.

A representative hosted-CI run with five repetitions and 100,000 operations per sample produced the following medians:

| Live allocations | RLBox domain/range | Extended SP3 | Additional cost |
| ---: | ---: | ---: | ---: |
| 1 | 6.32 ns | 18.78 ns | 12.46 ns |
| 16 | 6.16 ns | 21.88 ns | 15.72 ns |
| 256 | 3.70 ns | 16.61 ns | 12.91 ns |
| 4,096 | 3.78 ns | 21.32 ns | 17.55 ns |
| 16,384 | 3.78 ns | 48.08 ns | 44.31 ns |

These values are **reference CI measurements, not publication-final performance numbers**. They were generated from commit `6e952fdf677effd77e6e67b117d4ba756d3dfd66` on an Ubuntu 24.04 hosted runner using an AMD EPYC 9V74 virtual CPU. The corresponding P8 artifact digest is `sha256:0637646ef6e426d21d7cd7c474d44ee5e4b858ff52912b63ce3ee52fa79fc52e`.

The five-sample ranges still show hosted-runner variability, so the exact medians above should not be treated as machine-independent performance results. What the reference run establishes is that the matched benchmark behaves plausibly after preventing compiler loop hoisting and that allocation-lookup scaling becomes visible at larger live-allocation populations. The observed absolute increment in that run remained in the tens-of-nanoseconds range, reaching about 44 ns/check at 16,384 live allocations.

The secondary primitive benchmark uses only arithmetic U-domain/range validation as a lower-bound baseline. It is useful for decomposing metadata cost but should not replace the matched RLBox comparison in the paper.

For publication, regenerate the table on a dedicated otherwise-idle machine with the same binary for both sides, at least nine repetitions, a larger operation count, and every raw repetition retained. `REPRODUCIBILITY.md` gives the command and records the environment automatically.

## RQ4 — Is the evidence reproducible and are the claims bounded?

The P8 pipeline is fail-closed. It refuses to construct a required paper table when a runtime security case, real-boundary attack, live-allocation population, matched baseline, or Extended-SP3 measurement is missing. For real-boundary RQ1 evidence it additionally requires that the original domain predicate accepts the malicious value and that Extended SP3 returns the expected stronger rejection reason. Source provenance and attack-only instrumentation remain explicit in the machine-readable manifests.

CI produces and uploads the raw repetitions plus:

```text
security.csv
security-runtime.csv
security-boundaries.csv
automation.csv
runtime.csv
runtime-overhead.csv
rlbox-runtime.csv
rlbox-runtime-overhead.csv
p7c-generalization.json
summary.json
summary.md
environment.txt
```

The generated report preserves the following limits rather than hiding them:

• allocation-site provenance is not general control-flow integrity;

• U-owned object contents remain untrusted;

• the arena does not physically reuse released addresses;

• same-type intended-object identity is not established;

• arbitrary library ABI marshalling remains application-specific; and

• the three new P7c trusted-use adapters are not claimed as automatic inference from the original trusted applications.

## P8 conclusion

The strongest P8 result is the security delta relative to original SP3: the current real-boundary suite contains 11 pointer corruptions that remain valid sandbox-domain pointers/ranges but are rejected once allocation type, liveness, and object bounds become authoritative trusted metadata.

The generalization evidence also shows where automation currently succeeds and where it stops. Direct allocation patterns can be source-derived, while allocator abstractions require explicit integration policy; trusted-use inference is demonstrated on real rsync source but remains adapter-based for the three P7c generalization boundaries.

The performance infrastructure is ready and the hosted results indicate a tens-of-nanoseconds incremental check cost, but final publication performance numbers should be collected on a controlled machine rather than copied from shared CI.
