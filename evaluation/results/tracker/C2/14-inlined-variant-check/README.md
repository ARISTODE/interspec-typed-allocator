# C2: check of the query variant `paper_counting_rule_inlined`

The variant is `paper_counting_rule_factored` with `pragma[inline]` on two
predicates (`evaluation/coverage/query_variants/apply.py`):

- `exprUsesScalarVariableOrAlias(expr, var, origin)` in
  `scalar_slots_classification.ql`, called once, from `sinkArgUsesSlotOrAlias`;
- `returnSlotAliasVar(origin, baseVar, v)` in
  `pointer_slots_classification.ql`, called once, from
  `exprContainsReturnSlotRead`.

The first disjunct of each does not mention the call `origin`, so as a
predicate of its own it is paired with every call of the database: 3.28
billion rows on nginx/libpcre, and 95.8 billion on ffmpeg/libvpx, where the
disk filled (`../13-ffmpeg_libvpx-factored-disk-full/failed.txt`). Inlined, the
body is evaluated inside the caller, which binds `origin`. The pragma changes
where the body is evaluated, not what holds.

## Check

All eight boundaries that finish with `paper_counting_rule` were run again
with the variant in one run (2 threads, 3,500 MB, cap 115 minutes, exit 0 after
92 minutes) and every CSV file compared with the earlier output:
`../08-paper-counting-rule-6ec6b97/` for seven and
`../09-large-boundaries/b-nginx_libpcre-database-nginx_pcre/` for nginx/libpcre.

Result: 96 of 96 files identical (`csv-sha256.csv`).

`caller-rows.csv` has the row counts of the two callers from the evaluator
logs of this run. Both have rows on every boundary (1,152 to 9,666,167), so
the inlined bodies are exercised everywhere. The log cannot show the two
disjuncts of an inlined body separately.

## Effect on the cost

nginx/libpcre, scalar query: 4 minutes 16 seconds here against 19 minutes with
`paper_counting_rule_factored` (`../12-…/b-nginx_libpcre/`), same settings,
from the times of the `query-run-*.log` files.

The scratch directory in the text files is written as `$S`.
