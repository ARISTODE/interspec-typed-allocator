# C2: nginx/openssl, finished

Tracker item C2 in `EVAL_TRACKER.md`. Database `nginx_openssl_libs`
(`../09-large-boundaries/README.md`), counting rule of the tables, query
variant `paper_counting_rule_inlined` (checked in
`../14-inlined-variant-check/`), Claude Code cloud VM, 4 threads, 10,000 MB.
One run, exit 0, 63 minutes. Times in UTC (PST is UTC-8).

| Step | Time |
|---|---|
| Four pointer queries | 2026-11-15 04:31:07 to 04:55:29, 24 minutes |
| Scalar query | 04:55:29 to 05:28:15, 33 minutes |
| Type query and export | 05:28:15 to 05:33:58 |

## Result (`nginx_openssl/policy_summary.csv`)

| | Fields |
|---|---:|
| Interface fields | 351,808 (120,812 pointer, 100,033 scalar, 51,494 struct, 5,179 array, 74,290 other) |
| T to U | 221,106 |
| U to T | 28,850 |
| Protected by SP1 (not copied to U) | 130,196 (37.0%) |
| Protected by SP2 (not copied back) | 132,396 (37.6%) |
| Pointer fields whose value from U is used by T | 2,472: expected domain resolved for 501, not for 1,971 |

## Why 351,808 and not the paper's 1,485

The interface here is every OpenSSL function that unmodified nginx calls: 214
functions (`node_surface_summary_by_interface.csv`). The analysis expands each
parameter to every field reachable from it and counts a field once per
function. OpenSSL's objects are large trees: `SSL_set_SSL_CTX` alone has 9,208
fields, the median function has 1,680, and 119 of the 214 functions have more
than 1,000. The same `SSL_CTX` field is counted again for every function that
takes an `SSL_CTX`.

The paper's row (1,485 fields, SP1 624, SP2 651) is the artifact's analysis of
bridge wrappers on a modified nginx with an older version of the pipeline; the
artifact has no `policy_summary.csv` for this boundary. The two rows count
different interfaces.

This one row is 93% of the fields of all ten boundaries, so it decides every
pooled percentage (`../18-tables-ten-boundaries/README.md`).

## Files

- `nginx_openssl/`: the driver's output. `pointer_slots_classification.csv`
  (37 MB) and `slot_type_breakdown.csv` (62 MB) are stored gzipped;
  `csv-sha256.txt` has the SHA-256 of all CSV files before compression.
- `steps.txt`, `task-output.txt`: exit status 0.
- `execute-queries-*.log.gz`, `query-run-*.log`, `largest-relations-and-gaps.txt`:
  evaluator logs. The largest relation is `exprUsesVariableOrAlias` with 3.7
  billion rows.
- The scratch directory in the text files is written as `$S`.
