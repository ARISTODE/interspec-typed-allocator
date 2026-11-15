# C2: both coverage tables for all ten boundaries

Produced by

    python3 tools/render_coverage_tables.py \
      --reports evaluation/results/tracker/C2/08-paper-counting-rule-6ec6b97 \
                evaluation/results/tracker/C2/09-large-boundaries/b-nginx_libpcre-database-nginx_pcre \
                evaluation/results/tracker/C2/15-ffmpeg_libvpx-inlined \
                evaluation/results/tracker/C2/16-nginx_openssl-inlined \
      --paper <interspec-artifact>/data/processed/paper \
      --out evaluation/results/tracker/C2/18-tables-ten-boundaries

from the `policy_summary.csv` of each boundary (`sources.json`). Tables:
`COVERAGE_TABLES.md`, `coverage_sp1.csv`, `coverage_integrity.csv`.
`../17-tables-nine-boundaries/` is the earlier state without nginx/openssl.

All ten use the counting rule JH decided on 2026-11-14 (variant
`paper_counting_rule`; the three large boundaries use `…_inlined`, which gives
the same output on every boundary where both finish).

## The paper's four numbers

| Paper | Regenerated, ten boundaries | Regenerated, nine without nginx/openssl |
|---|---|---|
| 7,523 interface fields | 377,222 | 25,414 |
| SP1: 3,179 fields, 42.3% | 146,304, 38.8% | 16,108, 63.4% |
| Integrity: 4,426 fields, 58.8% (SP2 3,286 + pointers T does not dereference 1,108 + SP3 32) | SP2 alone: 149,299, 39.6% (paper's SP2 alone: 43.7%) | SP2 alone: 16,903, 66.5% |
| Pointer integrity: 1,955 of 1,966, 99.4% | 123,825 of 125,822, 98.4% | 4,984 of 5,010, 99.5% |

Mean of the ten per-boundary SP1 percentages: 49.0% (paper's rows: 25.8%).
Mean of the ten SP2 percentages: 59.3%.

## Why each number differs

1. **Fields (7,523).** The rows of the paper come from different versions of
   the artifact's pipeline and, for the three large boundaries, from a
   different interface.
   - zip/libzip reproduces: 2,230 fields, SP1 873, SP2 947 (paper 2,230, 871, 947).
   - yaml/libyaml: 1,919 against 1,903.
   - memcached/bipbuffer and memcached/hash: same field counts (80, 86); the
     SP1 and SP2 counts differ because the paper's rows used the shipped
     export rule and not the rule its text describes.
   - ucl/libucl (1,622 against 152), rsync/popt (1,667 against 767),
     magick/libpng (12,937 against 418): the paper's rows come from queries
     with the opacity rule or from a version not in the artifact; per boundary
     in `../08-paper-counting-rule-6ec6b97/README.md`.
   - nginx/libpcre (158 against 57), ffmpeg/libvpx (4,715 against 345),
     nginx/openssl (351,808 against 1,485): the paper analysed bridge wrappers
     on modified sources; these runs take every library function the
     unmodified application calls (`../09-…`, `../15-…`, `../16-…` README).
2. **SP1 share (42.3%).** Follows from 1. The pooled share is decided by
   nginx/openssl, which has 93% of all fields and 37.0%. Without it the share
   is 63.4%; eight of the other nine boundaries are above the paper's row.
3. **Integrity share (58.8%).** The paper adds three columns: SP2 fields,
   pointer fields that U may modify and T does not dereference, and SP3
   fields. The second column (1,108) and the paper's "Ptr SP2" column (815)
   match no column or sum of columns of the analysis output, for any boundary,
   including zip/libzip where every other number reproduces. The table
   therefore gives the SP2 share alone and, separately, the pointer coverage
   below; it does not give a combined integrity share.
4. **Pointer integrity (99.4%).** Counterpart in the analysis' own columns
   (`export_node_policy_surface.py`): a pointer field needs SP3 when a pointer
   slot at or below it is influenced by U and used by T (`sp3_pointer_nodes`);
   it is resolved when every such slot has an expected domain (T, U or null)
   and no cut flow (`sp3_pointer_protected_nodes`), unresolved otherwise
   (`sp3_pointer_remaining_nodes`). Coverage = (pointer fields - unresolved) /
   pointer fields = 98.4% (unresolved: nginx/openssl 1,971, rsync/popt 15,
   ffmpeg/libvpx 11, the other seven 0). The paper has 32 SP3 fields and 11
   unknown; here 2,540 pointer fields need SP3, 543 resolved and 1,997
   unresolved. The paper's intermediate columns are not reproduced.

## Summary rows: decision by JH, 2026-11-14

Asked with the numbers above, JH chose: keep all ten rows as computed, no
pooled total, and report the mean of the ten per-boundary percentages. The
tables have a "Mean of the rows" line: SP1 49.0% (25.9 to 75.8), SP2 59.3%
(37.6 to 76.1), pointer coverage 99.3% (96.8 to 100.0). The mean of the
paper's ten SP1 rows is 25.8%. The pooled numbers are kept in
`pooled_totals.json` for the comparison with the paper's totals only.

Still for the paper (W2): a combined integrity share needs a definition of
"pointer fields T does not dereference" in terms of the analysis output; the
tables do not give one.
