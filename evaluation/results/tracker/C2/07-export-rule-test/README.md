# C2: which counting rule produced the paper's SP1 and SP2 numbers

Diagnostic, not a coverage result.

The artifact's export step (`code/analysis/scripts/export_node_policy_surface.py`)
counts a node as T's data sent to U only if a leaf under it is owned by T and
exposed to U. `export_rule.diff` removes those two conditions: every node
under a parameter of a T-to-U interface counts, whoever owns the object, and a
node that U neither reads nor writes in that function counts as protected by
SP1 and by SP2. The changed script was run on the query output of
`../04-variant-without-opacity-rule-2e8bec6/` (no CodeQL rerun); the CSV files
here are its output.

| Boundary | | T-to-U nodes | SP1 only | SP2 only | SP1 and SP2 | unresolved | SP1 total | SP2 total |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| zip/libzip | artifact raw report (= paper) | 1,715 | 28 | 104 | 843 | 684 | 871 | 947 |
| | shipped export rule | 58 | 26 | 11 | 6 | 0 | 32 | 17 |
| | changed export rule | 1,557 | 28 | 102 | 845 | 526 | 873 | 947 |
| yaml/libyaml | artifact raw report (= paper) | 1,901 | 202 | 93 | 1,101 | 416 | 1,303 | 1,194 |
| | shipped export rule | 399 | 92 | 61 | 189 | 0 | 281 | 250 |
| | changed export rule | 1,853 | 92 | 98 | 1,362 | 244 | 1,454 | 1,460 |
| memcached/bipbuffer | artifact raw report (= paper) | 9 | 1 | 7 | 0 | 0 | 1 | 7 |
| | shipped export rule | 9 | 1 | 6 | 1 | 0 | 2 | 7 |
| | changed export rule | 63 | 1 | 23 | 22 | 0 | 23 | 45 |

Reading:

- zip/libzip: the changed rule reproduces the paper's row (SP2 exactly, SP1
  within 2). The paper's 871 and 947 therefore include the fields of objects
  that libzip itself allocates and owns (for example everything behind a
  `zip_t *`), counted as protected whenever one interface function does not
  touch them.
- yaml/libyaml: the changed rule gives the same order of magnitude as the
  paper and the shipped rule does not; the exact numbers differ because the raw
  report also came from other queries (1,903 nodes against 1,919).
- memcached/bipbuffer: the raw report matches the shipped rule, not the
  changed one.

So the artifact's raw reports, and with them the paper's coverage tables, were
produced by different versions of the pipeline for different boundaries, and
the two largest contributions to the paper's SP1 and SP2 totals (zip/libzip
and yaml/libyaml) come from the rule that counts U-owned state.

The second diagnostic variant (`../06-variant-all-owned-by-t-*`, every struct
counted as owned by T inside the queries) did not reproduce the paper's rows.
