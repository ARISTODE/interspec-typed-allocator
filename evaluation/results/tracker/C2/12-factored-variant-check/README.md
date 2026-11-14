# C2: check of the query variant `paper_counting_rule_factored`

The variant (`evaluation/coverage/query_variants/factored.py`) is
`paper_counting_rule_regrouped` with seven predicates of the artifact's
`ql/lib/PointerTargetDomain.qll` rewritten. Each predicate has the form
`P(Function f, Expr expr)` and some of its disjuncts do not mention `f`, so the
evaluator builds (functions of the database) x (expressions): 2.4 billion rows
on ffmpeg/libvpx (`../11-ffmpeg_libvpx-regrouped-stopped/`). The variant
splits each predicate into the disjuncts without `f` (`...AnyFunction(expr)`),
the disjuncts that bind `f` (`...ForFunction(f, expr)`) and an inlined wrapper
that is the disjunction of the two. The conditions are moved, not changed, and
every caller binds `f`, so the results are the same by construction. This
directory is the check of that claim on the boundaries that finish with
`paper_counting_rule`.

Every boundary was run again with the variant and every CSV file compared with
the earlier output (SHA-256 of all twelve files per boundary).

| Directory | Run | Result |
|---|---|---|
| `a-eight-boundaries-capped/` | Eight boundaries in one run with a cap of 115 minutes, 2 threads, 3,500 MB, while an ffmpeg/libvpx run used the other CPUs. | Seven finished: 84 of 84 files identical to `../08-paper-counting-rule-6ec6b97/` (`csv-sha256.csv`). nginx/libpcre was killed by the cap (exit=124) during its scalar query, 14 minutes after it started; it has no output files, which is not a difference. |
| `b-nginx_libpcre/` | nginx/libpcre again, alone in its run, same settings. | Finished in 30 minutes. 12 of 12 files identical to `../09-large-boundaries/b-nginx_libpcre-database-nginx_pcre/`. |
| `c-ffmpeg_libvpx-param-query/` | The one query of ffmpeg/libvpx that finished with both variants (param), from `../11-…` and from the run of `../13-…`. | The same 580 rows (sorted CSV, same SHA-256). |

Result: 96 of 96 files identical on the eight boundaries, and the same rows on
the only ffmpeg/libvpx query that the regrouped variant finished.

## Do the rewritten predicates have rows?

A check on empty predicates would show nothing (as in
`../10-regrouped-variant-check/a-nginx_libpcre/`). `variant-predicate-rows.csv`
in `a-…` and `b-…` has the final row count of every predicate the variants add,
read from the evaluator logs by `variant_predicate_rows.py`.

- The `AnyFunction` and `ForFunction` parts of all seven predicates have rows
  on all eight boundaries (from 7 rows to 27,443).
- The part that handles the one negated condition over `f`
  (`exprContainsAddressOfNonBoundaryRoots`: `c2AddressExcludedFor` and
  `c2ContainsUntrustedAddressSometimesExcluded`) has rows only on zip/libzip
  (17 and 41). On the other seven boundaries it is empty, so for that part the
  check rests on one boundary and on the argument from the form.

## Effect on the cost

nginx/libpcre: the four pointer queries took 10 minutes in run `a` (2 threads,
3,500 MB, another analysis running) against 16.5 minutes in `../09-…/b-…`
(4 threads, 10,000 MB), from the times of the `query-run-*.log` files. ffmpeg/libvpx:
the first pointer query took 55 minutes against 72, and the second 3.5 minutes
where the regrouped variant was stopped after 116 minutes
(`../11-ffmpeg_libvpx-regrouped-stopped/stopped.txt`). The relations of 2.4
billion rows are gone from the evaluator log; `occursBefore` (1.97 billion
rows) is not changed by the variant and is still there.

The scratch directory in `command.txt`, `manifest.json` and `analysis.log` is
written as `$S`.
