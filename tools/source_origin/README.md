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

| Original application | T stack | T static | U static | U string/i18n candidate |
| --- | ---: | ---: | ---: | ---: |
| nginx / PCRE | 3 | 0 | 2 | 0 |
| rsync / popt | 0 | 0 | 0 | 3 |
| memcached / bipbuffer | 5 | 1 | 0 | 0 |

These are **14 distinct original application pointer-valued API expressions** verified from the pinned C source, not dynamic events. They omit other potential sites, so there is no complete denominator. rsync's error strings may originate from literals or localization-managed storage, depending on the configuration. No InterSpec wrapper code is counted.

Separately, the original PCRE sources contain **11 static error-return assignments**, and libyaml contains **103 literal argument expressions** used to populate parser problem/context fields. These **114 library source candidates are not counted as original application boundary uses**, because they may never be observed by T in the evaluated interface.

Examples of original source sites:

1. Nginx: `src/core/ngx_regex.c:296`, `&errstr` and `&erroff`, which are stack output parameters. PCRE's `pcre_compile.c:9642` returns a pointer into its static `error_texts` array.
2. Nginx: `src/core/ngx_regex.c:684`, stack `&errstr` for `pcre_study`. Its error strings are literals.
3. Rsync: `options.c:1572`, `options.c:2048`, `tls.c:285` use `poptStrerror` results.
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
2. Instrument **original application call sites**, not wrappers, for dynamic pointer-origin counts across normal and error workloads.
3. Separately measure actual pointer transport through each isolated adapter and T dereferences.
4. Regression-check original versus isolated behavior. The current PCRE bridge drops detailed error strings and offsets.
5. Do not use these preliminary site counts or previous adapter counts as paper prevalence figures.

The official paper repository has not been changed.
