# C2: seven boundaries with the paper's counting rule

Queries without the opacity rule (output of `../04-variant-without-opacity-rule-2e8bec6/`,
reused with `COVERAGE_REUSE_BQRS=1`), export step with the variant
`paper_counting_rule` (JH's decision of 2026-11-14). All seven exports exited 0.
Tables: `tables/COVERAGE_TABLES.md`. Missing: ffmpeg/libvpx, nginx/libpcre,
nginx/openssl.

| Boundary | Fields: paper | Fields: here | SP1: paper | SP1: here | SP2: paper | SP2: here |
|---|---:|---:|---:|---:|---:|---:|
| magick/libpng | 418 | 12,937 | 156 | 9,228 | 178 | 9,577 |
| memcached/bipbuffer | 80 | 80 | 1 | 23 | 7 | 45 |
| memcached/hash | 86 | 86 | 17 | 33 | 33 | 48 |
| rsync/popt | 767 | 1,667 | 92 | 1,087 | 116 | 1,159 |
| ucl/libucl | 152 | 1,622 | 0 | 904 | 8 | 1,035 |
| yaml/libyaml | 1,903 | 1,919 | 1,303 | 1,454 | 1,194 | 1,460 |
| zip/libzip | 2,230 | 2,230 | 873* | 873 | 947 | 947 |

\* paper 871.

Why each row differs from the paper (checked against the artifact's raw reports
in `interspec-artifact/data/raw/policy_reports/`, per interface function):

- zip/libzip: same fields per function. SP2 equal, SP1 differs by 2.
- memcached/bipbuffer, memcached/hash: same fields per function. The artifact's
  raw SP1 and SP2 counts equal the shipped export rule (T must own the field),
  so the paper's rows for these two did not use the rule its text describes.
  With that rule the counts rise (1 to 23, 7 to 45; 17 to 33, 33 to 48).
  memcached/hash has 24 pointer fields here against 26 and 5 SP3 fields against 4.
- ucl/libucl: the paper's 152 fields equal the shipped queries, which skip
  `struct ucl_parser` because trusted code never looks into it
  (`../01-analysis-63bf903/ucl_libucl`: 152). Without that rule each function
  that takes the parser gains 294 fields (for example `ucl_parser_new` 2 to 296).
- rsync/popt: same eleven functions. Nine of them gain 90 fields each, the
  fields behind `poptContext`, which the raw report did not count. The shipped
  queries give 77 fields here, so the paper's 767 came from a third version of
  the queries that is not in the artifact.
- yaml/libyaml: same five functions, 2 to 6 more fields per function (1,919
  against 1,903). The artifact did not record its libyaml revision; ours is the
  commit pinned in this repository. The SP1 and SP2 counts are of the paper's
  size (1,454 and 1,460 against 1,303 and 1,194) but not equal: the raw report
  has 416 unresolved fields, ours 244.
- magick/libpng: the paper's row (418, 156, 178) cannot be derived from the
  artifact's own raw report, which has 14,487 fields, SP1 9,375, SP2 8,462.
  Against that raw report: the same 26 libpng functions with 5 to 15 fewer
  fields each (libpng 1.6.59 here, revision not recorded there), and the raw
  report also counts three callbacks (`native_read_cb`, `native_write_cb`,
  `native_flush_cb`, 1,290 fields) that are not in our database.

Consequence for the paper: with one rule applied to every boundary the totals
grow well beyond 7,523 fields; the seven rows alone have 20,541 fields, SP1
13,602 (66.2%).
