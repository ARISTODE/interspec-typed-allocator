# SP3's dereference condition with the opacity test (C2, follow-up of R5)

Analysis runs of 2026-11-19 (PT) on the Claude Code cloud VM, with the CodeQL
bundle and the databases of the earlier C2 runs. JH approved on 2026-11-19
that the paper's integrity table and coverage text use this analysis.

## What changed and why

The tables use the counting rule `paper_counting_rule` (JH, 2026-11-14), which
switches the artifact's opacity rule off so that every field reachable from the
interface counts as an interface field. The opacity rule also decided, as a
side effect, which pointer slots T can dereference. Without it, SP3's
dereference condition (Condition B in the paper) is approximated by
`slotUsedByTrustedViaEscape` in `pointer_slots_classification.ql`: every slot
below a pointer that T passes to U counts as used by T when the argument is
rooted in a parameter or a global of T. This counted thousands of pointers deep
inside OpenSSL's `SSL`, `SSL_CTX` and `HMAC_CTX` objects and popt's context as
dereferenced by nginx and rsync, although these programs never access the
fields of those structures: OpenSSL's and popt's definitions are internal, and
T uses the objects only through the library's API.

Variant `paper_counting_rule_sp3_opacity`
(`evaluation/coverage/query_variants/apply.py`, commit `f65c90a`) is the
tables' variant plus one restriction: a slot inside an object whose class is
opaque to T by the shipped test (`classOpaqueToTrusted` of the artifact: not
defined in T, T accesses none of its fields, and no field definition is in a T
file or a public `include/` header) does not satisfy SP3's trusted-use
condition. A pointer that T obtains from such an object through a getter is the
getter's return value, which is classified on its own. SP1, SP2 and every other
column are computed as before.

Only the pointer queries change. Each run reuses the scalar and slot-type query
results of the run behind the tables (`reused-query-results.json`; the paper's
tables come from C2/08, C2/09b, C2/15 and C2/16, and those query results are
identical to them), and runs the four pointer queries again
(`sp3op-run.sh`).

## Checks

- For all ten boundaries, `policy_summary.csv` is identical to the tables' run
  in every column that the paper's tables use: interface fields, SP1, SP2 and
  pointer fields. The columns that depend on SP3's dereference condition differ
  at ffmpeg/libvpx, nginx/openssl and rsync/popt (the SP3 counts, and the
  analysis' own partition of pointer slots, `partition_*` and `u_to_t_*`,
  which the paper does not use); the other seven summaries are identical in
  every column. At nginx/openssl the classification has the same 182,079 rows
  and 120,812 slots, and all columns other than the SP3 ones are equal.
- Every pointer field that our ports check and that the tables' run reported
  as needing SP3 still needs SP3 here (`bipbuf_peek_all`, `bipbuf_request`,
  `assoc_find`, `assoc_iterate`, `poptBadOption`, `poptGetArgs`,
  `poptGetOptArg`, `ucl_object_tostring`, the scalar value of
  `yaml_parser_parse`, the name of `zip_stat_index`, and the frame and packet
  that libvpx returns).

## Result

`sp3_columns.csv`, written by `tools/render_sp3_columns.py` from the ten
`pointer_slots_classification.csv` files. "Inferred": every pointer at or
below the field has one expected domain (T or U, possibly also NULL) and is
not at the depth limit.

| Boundary | Pointer fields | Need SP3, tables' run | Need SP3, this run | Inferred | Domain stated by the developer | Pointer coverage |
|---|---:|---:|---:|---:|---:|---:|
| ffmpeg/libvpx | 347 | 29 | 9 | 9 | 0 | 100% |
| magick/libpng | 2,183 | 1 | 1 | 1 | 0 | 100% |
| memcached/bipbuffer | 12 | 2 | 2 | 2 | 0 | 100% |
| memcached/hash | 24 | 7 | 7 | 7 | 0 | 100% |
| nginx/libpcre | 44 | 0 | 0 | 0 | 0 | 100% |
| nginx/openssl | 120,812 | 2,472 | 22 | 16 | 6 | 99.995% |
| rsync/popt | 637 | 23 | 8 | 7 | 1 | 99.843% |
| ucl/libucl | 649 | 1 | 1 | 1 | 0 | 100% |
| yaml/libyaml | 461 | 2 | 2 | 2 | 0 | 100% |
| zip/libzip | 653 | 3 | 3 | 3 | 0 | 100% |
| Total or mean | 125,822 | 2,540 | 55 | 48 | 7 | 99.984% |

The 7 fields without one inferred domain (`not_inferred_fields.txt`): the
return values of `SSL_get_ex_data`, `SSL_CTX_get_ex_data`,
`X509_get_ex_data`, `X509_NAME_oneline` and `poptBadOption`, for which both T
and U values reach the pointer, and the time value that nginx passes to
`ASN1_TIME_print` together with its `data` pointer, for which no definition
is found (`ASN1_STRING` is declared in a public header, so the opacity test
keeps it visible, although nginx uses it only through `ASN1_STRING_length`
and `ASN1_STRING_data`). None of the 55 lies at the depth limit.

Run times (`steps.txt`): nginx/openssl 26 minutes, the eight smaller
boundaries 2 to 11 minutes each, ffmpeg/libvpx 60 minutes.

## Kept runs that are not results

- `diagnostics/field-access/`: variant `paper_counting_rule_sp3_field_access`,
  the same restriction without the header part of the test (a class counts
  as opaque when T accesses none of its fields). Stopped by hand during
  nginx/libpcre. It drops the two yaml/libyaml fields that the port checks
  (the scalar value inside `yaml_event_t`): the C++ driver's field accesses
  do not reach the class entities of the C library in the database, so the
  test alone would count a class that T does read as unread. The shipped
  test keeps such classes through their public header, so it is the one used.
- `diagnostics/disk-full/`: the first start of the runs failed within two
  minutes on all boundaries because the disk was full (CodeQL query caches of
  an earlier stopped run). Caches were cleared and the runner changed to clear
  each database's cache after its run.
- `ffmpeg_libvpx/stopped-0050Z.*`: the first ffmpeg/libvpx run of this variant,
  stopped by hand after 10 minutes to try the field-access variant; run again
  afterwards.
