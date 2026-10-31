# InterSpec pointer census: hosted experiment results

Measurements captured on 2026-10-31 UTC, against `34dfc042b09d6955dd51731dbbdd2490b2e6ac13`. All six GitHub Actions workflows completed successfully, including application regression and independent native-versus-isolated parity audits.

## Observed pointers

| Isolated boundary | T stack | T ELF image candidate | T unknown | Checked U allocation | Total events |
| :--- | ---: | ---: | ---: | ---: | ---: |
| rsync/popt | 8 | 2,232 | 27 | 35 | 2,302 |
| YAML/libyaml | 0 | 0 | 2 | 1,024 | 1,026 |
| nginx/PCRE | 176 | 0 | 24,500 | 13,088 | 37,764 |
| memcached/bipbuffer | 1,357 | 26 | 263 | 462 | 2,108 |

These are *event counts* for the selected correctness workloads, not unique allocations. Trusted addresses stay in T. The adapters copy bytes or convert references to handles, so the numbers must not be interpreted as raw T addresses entering U.

### Observation-site breakdown

| Boundary | Trusted side | U checked pointers |
| :--- | :--- | :--- |
| rsync/popt | 690 image/static option destinations; string copies: 1,542 image/static, 8 stack, 27 unknown | 35 strings |
| YAML/libyaml | 2 unknown document buffer sources | 1,024 scalar results |
| nginx/PCRE | 176 stack compile outputs, 12,206 unknown capture outputs, 12,294 unknown pattern/subject sources | 12,382 staging checks, 702 capture checks, 4 name-table checks |
| memcached/bipbuffer | 1,352 stack size outputs, 129 unknown LRU references, 26 image/static and 5 stack offer sources, 134 unknown push sources | 37 input, 31 offer, 74 peek, 47 poll, 134 push, 139 request checks |

### Regression gates

1. **rsync:** Six paired native/isolated workloads, including three file-manifest equality checks.
2. **YAML:** Four matching semantic signatures on the 1 MiB YAML document.
3. **nginx:** All 24 functional, reload, error-path, and source-corruption cases passed, with native/isolated parity.
4. **memcached:** Five variant contract runs with at least 16 assertions each, plus native and isolated upstream suites.

### GitHub evidence

| Boundary | CI run | Artifact name | Archive SHA-256 |
| :--- | :--- | :--- | :--- |
| rsync | [41160844051](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/41160844051) | p9b-wasm2c-diagnostics | a7f1945b30a442003c0e5501c8ce35684376266d714a24c5eba65808ed548635 |
| YAML | [41160843991](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/41160843991) | yaml-libyaml-evaluation | 978f0c29c32e87bca5c49fd0497bba85ffc66c592aaf2a7aa4c9f22350b4c898 |
| nginx | [41160844095](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/41160844095) | nginx-deployment-evidence | d7bfecc9106b322289a43a8a7963f09609b4c72453782b67ccfdcaa8ee906723 |
| memcached | [41160843977](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/41160843977) | memcached-deployment-evidence | b2ecb8c563c0cacd7100ab013e6775880698d28f6c39194a191e57 |

Raw artifacts retain pointer-census JSON, source-log SHA-256 values, and independent parity-audit JSON.

### Limitations for paper writing

1. **T stack** identifies the current executing thread at observation time, not every thread stack.
2. **T image/static** means membership in a readable non-executable ELF mapping. It does not resolve a named global symbol.
3. **Unknown** must not be equated with heap; resolving it requires allocation or symbol provenance.
4. **Checked U allocation** denotes a successful typed metadata check. Internal U stack/global pointers not observed by these checked return sites are outside this census.
5. This is evidence of tested *observable* application parity, not universal semantic equivalence.
6. Cross-application totals must not be pooled into a single prevalence percentage because the workloads and operation counts differ.

### Repeatability caveat

An earlier successful run under commit `352020efcecd4dd16b4fd50be51813a7eabcdb8e` recorded **3,643 memcached events**, versus **2,108** in the latest sample. Its T categories were 1,365 stack, 26 image/static, and 655 unknown, plus 1,597 validated U pointers. Async watcher and queue scheduling affect boundary-call frequency while all functional cases still pass.

The earlier rsync run also recorded 2,302 events, with T stack/unknown counts of 13/22 rather than 8/27. Two runs are insufficient for paper confidence intervals. Before publishing pointer-frequency percentages, repeat fixed traces and report counts per boundary operation with dispersion.
