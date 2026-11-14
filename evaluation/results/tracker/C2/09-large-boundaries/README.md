# C2: the three large boundaries (nginx/libpcre, ffmpeg/libvpx, nginx/openssl)

Tracker item C2 in `EVAL_TRACKER.md`. The seven other boundaries are in
`../08-paper-counting-rule-6ec6b97/`. Queries: the artifact's, variant
`paper_counting_rule` (`evaluation/coverage/query_variants/`). Machine: the
Claude Code cloud VM, 4 virtual CPUs, 16 GB; CodeQL CLI 2.23.2 with 4 threads,
10,000 MB and a query cache capped at 6,000 MB.

| Directory | Run | Outcome |
|---|---|---|
| `a-nginx_libpcre-database-nginx-timeout/` | nginx/libpcre on database `nginx` (nginx, PCRE and all of OpenSSL) | Killed by the 115-minute cap. Fourth attempt on this database that did not finish (`../02-…`, `../03-…`, `../05-…`). |
| `b-nginx_libpcre-database-nginx_pcre/` | nginx/libpcre on database `nginx_pcre` | Finished in 25 minutes. 158 interface fields. |
| `c-ffmpeg_libvpx-database-ffmpeg_vpx_only-stopped/` | ffmpeg/libvpx on database `ffmpeg_vpx_only` | Stopped by hand after 91 minutes; one predicate had run 53 minutes on small inputs (`stopped.txt`). |
| `database-scope/` | Counting queries and their output for the databases | See below. |

Later runs of ffmpeg/libvpx and nginx/openssl use the variant
`paper_counting_rule_regrouped` and are in `../11-…`; the check of that variant
is in `../10-regrouped-variant-check/`.

## Why the analysis did not finish on database `nginx`

The artifact's queries build relations over every function of the database,
not only over the functions at the boundary. One example:
`exprMayTargetUFromBoundaryRoots(Function f, Expr expr)` has disjuncts that do
not bind `f`, so its size is about (functions in the database) x (expressions
that may point into U). The evaluator log of run `a`
(`largest-relations-and-gaps.txt`) has relations of 198 to 273 million rows, a
magic set of 594 million rows and helper relations of 1.35 to 2.85 billion
rows. The cost follows the size of the database, not the size of the boundary.

Database `nginx` has 30,385 functions with bodies; 27,954 of them are OpenSSL's
(`database-scope/count-nginx.csv`, `openssl-by-directory-nginx.csv`), because
nginx was built with `--with-openssl` from source inside the traced build.
PCRE has 112 and nginx 1,573.

## Databases scoped to the boundary

Three databases were added to `evaluation/coverage/pins.json`. Sources and
library versions are those of the full databases; code that is on neither side
of the boundary is built before tracing starts or not built at all. Build
records: `../../C1/05-databases-scoped/`.

| Database | For | What is left out | Functions with bodies / expressions |
|---|---|---|---|
| `nginx_pcre` | nginx/libpcre | OpenSSL is built before tracing. Its headers stay (703 inline functions). | nginx 1,573 / 303,197 (same as in `nginx`); PCRE 70 / 46,087 (`nginx`: 112 / 46,903, the difference is two configure test files `conftest.c` and `conftest.cpp`, `pcre-files-*.csv`) |
| `ffmpeg_vpx_only` | ffmpeg/libvpx | ffmpeg is configured with `--disable-everything` plus the libvpx encoders and decoders and what they need. | ffmpeg 5,406 / 968,504 (`ffmpeg_libvpx`: 27,510 / 5,843,899); libvpx 3,235 / 582,418 (same 279 files, `libvpx-files-*.csv`) |
| `nginx_openssl_libs` | nginx/openssl | OpenSSL's command-line program, tests and fuzzers (`no-apps`; tests and fuzzers are not built by nginx's rule in this configuration). OpenSSL is U at this boundary and cannot be left out. | OpenSSL 21,267 / 1,556,272 (`nginx`: 27,954 / 2,477,489); `crypto`, `ssl`, `providers` and `engines` as in `nginx` to within 0.2% of the expressions |

Check that the boundary itself is unchanged in `ffmpeg_vpx_only`: in both
ffmpeg databases only `libavcodec/libvpxenc.c` (28 calls of libvpx functions,
275 accesses of libvpx struct fields) and `libavcodec/libvpxdec.c` (15 and 58)
touch libvpx (`ffmpeg-files-using-libvpx*.csv`).

The first build of `nginx_pcre` failed (exit 97: the prepare script was not
copied; `../../C1/05-databases-scoped/c1-nginx-pcre/`); fixed in
`scripts/build_codeql_databases.sh` and built again in a new directory. The
`source-commit.txt` of the build records names the commit before the build
scripts were committed; the scripts that ran are the ones committed in
`a9b80e9` and `75c54b6`.

## nginx/libpcre: 158 fields against the paper's 57

`b-…/nginx_libpcre/policy_summary.csv`: 158 fields (44 pointer, 107 scalar, 7
struct); T to U 119 fields, of which 41 are not copied to U (SP1) and 101 are
not copied back (SP2); 44 pointer slots.

The paper's row (57 fields, SP1 3, SP2 14) is the artifact's analysis of six
bridge wrappers (`ngx_pcre_rlbox_*`) on a modified nginx with PCRE2
(`interspec-artifact/data/raw/policy_reports/nginx_libpcre/policy_summary.csv`,
`total_fields` 57). This run analyses unmodified nginx 1.x with PCRE 8.45 (JH
decision I5) and takes every PCRE function that nginx calls as the interface:
`pcre_compile` 33 fields, `pcre_exec` 45, `pcre_fullinfo` 39, `pcre_study` 40,
and the callback `ngx_regex_free` 1. The two numbers count different
interfaces of different library versions and cannot be compared row by row.

## Notes on the raw files

- `analysis.log` of the runs that were killed is empty: the driver's output is
  piped through `grep` and lost when the run is killed. The evaluator logs
  (`execute-queries-*.log.gz`) are complete up to the kill.
- The scratch directory in `command.txt` and `query-run-*.log` is written as `$S`.
- The partial `pointer_slots.param.bqrs` of run `a` was not kept; the next run
  reset the report directory.
