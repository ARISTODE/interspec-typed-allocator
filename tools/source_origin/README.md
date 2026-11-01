# Original upstream pointer provenance: preliminary source audit

**Status:** Source-only minimum, plus native library storage checks. **Not** an exhaustive pointer census or paper-ready prevalence statistic.

## Pinned upstream revisions

| Repo | SHA |
| --- | --- |
| nginx/nginx | `1be0fb0c9f9bc3489c7b40576efd6afe6b2eccd5` |
| nektro/pcre-8.45 | `e67dabe61b327bd2d888954b0e74a7c9cfd0a195` |
| RsyncProject/rsync | `7c20b077c980036a19587701cec320cc88e42a4a` |
| yaml/libyaml | `90a56d4500aa1a1798514c5cb55c3ad4cb095f94` |
| memcached/memcached | `2d51e364799bc9698bd4b11728ea978cea12da6e` |

## Preliminary verified original-source expressions

| Original application | T stack | T literal | U static error | U argv/alias result |
| --- | ---: | ---: | ---: | ---: |
| nginx / PCRE8 | 3 | 0 | 2 | 0 |
| rsync / popt | 0 | 0 | 0 | 3 |
| memcached / bipbuffer | 5 | 1 | 0 | 0 |

These are **14 candidate original-application pointer-valued API expressions** supported by source and the selected API boundary mapping, **not** dynamic event counts or proof that the raw pointer is transmitted through the isolated adapter. The adapter may replace the original pointer with a copy or handle. No InterSpec wrapper code is counted.

In particular, the original rsync application calls both `poptBadOption` and `poptStrerror` at the same error-handling sites. The deployed P4c bridge isolates **`poptBadOption`** and copies its string return into trusted memory, whereas it deliberately leaves **`poptStrerror` in trusted host libpopt**. Thus the **three original `poptStrerror` expressions are separately recorded as excluded host helpers**, not as U-to-T pointer returns.

Separately, the original PCRE sources contain **11 static error-return assignments**, and libyaml contains **103 literal argument expressions** used to populate parser problem/context fields. These **114 library source candidates are not counted as original application boundary uses**, because they may never be observed by T in the evaluated interface.

Examples of original source sites:

1. Nginx: `src/core/ngx_regex.c:296`, `&errstr` and `&erroff`, which are stack output parameters. PCRE's `pcre_compile.c:9642` returns a pointer into its static `error_texts` array.
2. Nginx: `src/core/ngx_regex.c:684`, stack `&errstr` for `pcre_study`. Its error strings are literals.
3. Rsync: `options.c:1571`, `options.c:2047`, and `tls.c:284` use **isolated** `poptBadOption` results. Adjacent `poptStrerror` calls are **trusted host helpers**, not boundary uses.
4. Memcached: `logger.c:722` passes `scratch` from `logger.c:749` (stack) to `bipbuf_offer`; `logger.c:1141` passes literal `"OK\\r\\n"` (static). Four original `bipbuf_peek_all` call sites pass local size output parameters.
5. libyaml: original `src/parser.c`, `src/scanner.c`, `src/reader.c`, and `src/loader.c` set parser problem/context pointers to literals on error paths. Current isolated adapter does not return these fields.

## Native storage checks

A native diagnostic driver was built and executed against **unchanged pinned original C library implementations**, not the isolated adapters. All five probes passed:

| Original source result | Observed Linux mapping |
| --- | --- |
| PCRE compile error | Read-only image |
| PCRE study error | Read-only image |
| popt error message | Read-only image |
| libyaml parser problem | Read-only image |
| bipbuffer data return | Heap |

The driver and its arguments were **excluded** from all source-use counts. Mapping category alone is not proof of object type or identity; those are corroborated by source code.

## Still required

1. Enumerate *every* pointer-bearing original API site, including indirect pointers in structs and callbacks; retain unknown cases.
2. Instrument **original application call sites**, not wrappers, for dynamic pointer-origin counts across normal and error workloads. Measure the isolated API mapping separately.
3. Separately measure actual pointer transport through each isolated adapter and T dereferences.
4. Regression-check original versus isolated behavior. The current PCRE bridge drops detailed error strings and offsets.
5. Do not use these preliminary site counts or previous adapter counts as paper prevalence figures.

The official paper repository has not been changed.


## Native original application runtime pilot: Memcached

The separate [original-source-runtime workflow](../../.github/workflows/original-source-runtime.yml) uses the same pinned original memcached source twice: an ordinary native binary and a linker-intercepted native binary. The tracer intercepts the existing bipbuffer APIs **without modifying** original `logger.c`, `items.c`, `bipbuffer.c`, or `bipbuffer.h`. A deterministic TCP client exercises cache operations and the actual watcher event path, then checks native protocol parity.

`memcached_original_trace.c` emits runtime pointer events. `verify_memcached_native_origin.py` resolves the original caller PC with `addr2line`, checks upstream file hashes against the pinned Git revision, and **accepts only events originating from the original logger.c/items.c callsites**. The tracer, verifier, workload client and adapter are not counted. Unrecognized source attribution fails verification.

The CI artifact `original-native-memcached-pointer-events` contains the raw JSONL events, original file/line/API/role/origin counts, native behavior parity evidence, and SHA256s. Source sites and runtime events remain separate. Image classification is a memory-region observation, not an allocation-type guarantee.

**Scope limitations:** This is a native observation of selected direct bipbuffer pointer arguments and return values. It is not a complete original-app pointer denominator, not a measurement of every indirect pointer reachable through those arguments, and not yet proof that the isolated implementation preserves all native behavior. The next experiments must compare native and isolated cases and run corresponding original-application traces for nginx/PCRE, rsync/popt and yaml/libyaml.


## Verified native runtime event pilots

**Memcached/bipbuffer:** [passed GitHub Actions run](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/41343983340). Across the tested native workload, **208** stack pointer argument events and **1** readonly literal pointer argument event were attributed to **6** original application input sites. The remaining **216** return records were 18 heap-interior pointers and 198 null values. Total 425 logged pointer records. Native tracing/no-tracing protocol parity passed. The count is limited to selected pointer arguments and returns, not all bipbuffer object or nested pointers.

**Rsync/popt:** The first original native trace confirmed three read-only `poptStrerror` results with byte-for-byte native parity: two from `rsync` and one from auxiliary `tls`. [Original pilot artifact](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/41344969649). Crucially **these results are excluded from the deployed isolated-pointer count**, because `poptStrerror` remains trusted-host code. The updated instrumentation traces the genuinely isolated `poptBadOption` API separately, including its context input, to distinguish native source provenance from the bridge's copy of the returned string.

**Nginx/PCRE8:** [verified native GitHub Actions run](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/41345188937). Across one valid and one malformed regex configuration, the original `src/core/ngx_regex.c` made **5 stack output-parameter pointer events**, **1 readonly PCRE error-string return**, and **8 other null/unresolved pointer records**. Both CLI behavior checks passed. This is PCRE8, matching the new deployment implementation; the existing manuscript still describes a PCRE2 PoC and must be reconciled before rewriting.

**All results are native observations**. Actual raw pointer transit and native-vs-isolated behavior parity remain separate experiments. Static literals are not named global variables.
