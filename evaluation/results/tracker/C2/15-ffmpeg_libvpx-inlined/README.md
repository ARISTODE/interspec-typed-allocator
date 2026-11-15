# C2: ffmpeg/libvpx, finished

Tracker item C2 in `EVAL_TRACKER.md`. Database `ffmpeg_vpx_only`
(`../09-large-boundaries/README.md`), counting rule of the tables
(`paper_counting_rule`), Claude Code cloud VM, 4 threads, 10,000 MB.
Times in UTC (PST is UTC-8).

The output in `ffmpeg_libvpx/` comes from two runs:

| Part | Run | Query variant | Time |
|---|---|---|---|
| Four pointer queries | `../13-ffmpeg_libvpx-factored-disk-full/` | `paper_counting_rule_factored` | 2026-11-14 22:16:52 to 2026-11-15 02:19:08, 4 hours 2 minutes |
| Scalar query | this run, started with `COVERAGE_REUSE_BQRS=1` | `paper_counting_rule_inlined` | 03:06:14 to 04:28:27, 82 minutes |
| Type query and export | this run | `paper_counting_rule_inlined` | 04:28:27 to 04:29:58 |

`reused-pointer-bqrs.sha256` lists the four pointer outputs this run read; they
are byte for byte those of run 13, and the four pointer CSV files here are
identical to the ones in `../13-…/pointer-queries/`. The scalar query of run 13
could not finish in the shipped form (95.8 billion rows, disk full); the
variant used here differs from that of run 13 by two `pragma[inline]`
annotations (`evaluation/coverage/query_variants/README.md`), checked in
`../14-inlined-variant-check/`.

## Result (`ffmpeg_libvpx/policy_summary.csv`)

| | Fields |
|---|---:|
| Interface fields | 4,715 (347 pointer, 2,735 scalar, 993 struct, 309 array, 331 other) |
| T to U | 3,391 |
| U to T | 724 |
| Protected by SP1 (not copied to U) | 2,465 (52.3% of 4,715) |
| Protected by SP2 (not copied back) | 2,531 (53.7%) |
| Pointer slots | 347: SP3 26, SP2 only 21, SP1 only 1, other 299 |

The paper's row is 345 fields with 112 under SP1 (32.5%). It is the artifact's
analysis of bridge wrappers on modified sources with an older pipeline; this
run takes every libvpx function that unmodified ffmpeg calls, and the libvpx
struct fields those calls reach, as the interface. The two rows count
different interfaces.

## Files

- `steps.txt`, `task-output.txt`: exit status 0.
- `execute-queries-*.log.gz`, `query-run-*.log`: evaluator logs of the scalar
  and the type query. `largest-relations-and-gaps.txt`: the largest relations
  (`log_summary.py`). The largest that remain are pairs of expressions of the
  same function (4.4 billion rows), `exprUsesVariableOrAlias` (3.2 billion) and
  `occursBefore` (1.97 billion).
- The scratch directory in the text files is written as `$S`.
