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
