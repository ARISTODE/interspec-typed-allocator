# InterSpec evaluation tracker

Created 2026-11-13. This file is the only progress record for finishing the evaluation.
Keep it at the root of `interspec-typed-allocator` and update it in the same commit as the work.

## Rules

1. Status is one of `todo`, `doing`, `blocked`, `done`.
2. An item becomes `done` only when everything in its "Done when" column exists and the Evidence column links to it (commit SHA, CI run URL, or file path). Written code that has not run is `doing`.
3. Before you set `done`, open the evidence again and check it against "Done when". Do not rely on memory of a run.
4. A partly finished item stays `doing`, with one line in Notes that says what is missing.
5. If an item cannot be finished, set `blocked`, give the reason, and name the item or person that unblocks it.
6. Keep failed runs and say so in Notes. Do not rerun until a number looks better.
7. Do not add an item, split an item, or change a "Done when" without J. Huang's approval. Propose the change in the Log.
8. Timing from a shared VM or a hosted CI runner never closes a performance item (P2 to P9).

## Terms

- Domain-only SP3: checks only which compartment's memory a pointer lies in. This is what the May artifact implements.
- Full SP3: object registry check (live object, expected type, bounds, expected memory domain).
- The four registry boundaries: rsync/popt, memcached/bipbuffer, yaml/libyaml, nginx/libpcre.
- Where: `ws` = Claude cloud workspace (paper edits, data analysis, code edits that CI builds), `cc` = Claude Code on a build machine, `host` = dedicated measurement host, `JH` = J. Huang.

## Starting point (not tracked, already verified)

- Fault experiments of 7 to 8 Nov 2026 in `SP3_SECURITY_DELTA_RESULTS.md` (memcached item pointer, libyaml context pointer, pointers into U memory on four boundaries).
- Functional parity runs: memcached 50/50, nginx 104/104, yaml 48/48.
- Hosted reference timings (400 samples). These are not paper numbers.

## Decisions

| ID | Item | Done when | Where | Status | Evidence | Notes |
|---|---|---|---|---|---|---|
| D1 | Scope of the evaluation | JH picks one: two-tier (10 boundaries for SP1, SP2, domain check; registry boundaries for full SP3), full port to 10, or cut to the registry boundaries. Choice recorded here. | JH | todo | | Plan below assumes two-tier |
| D2 | Dedicated measurement host | Host named, access confirmed, and whether the old build tree and raw logs still exist on the Xeon Gold 6136 machine is recorded here | JH | todo | | Blocks P1 to P9 |
| D3 | Venue and deadline | Date recorded here | JH | todo | | Decides whether I6 and P7 are in scope |

## Phase 1: Freeze the code

| ID | Item | Done when | Where | Status | Evidence | Notes |
|---|---|---|---|---|---|---|
| F1 | Merge the PR stack (#15 to #28) and `claude/nifty-cray-ik99hh` into `main` of `interspec-typed-allocator` | `main` contains the work, the core, memcached, nginx and sp3-security-delta workflows pass at that commit, and tag `eval-base` points to it | cc | todo | | Ask JH before the merge and before the tag |

## Phase 2: Implementation gaps

| ID | Item | Done when | Where | Status | Evidence | Notes |
|---|---|---|---|---|---|---|
| I1 | rsync/popt: one build with SP1, SP2, full SP3 and a switch for each policy | A test shows each switch changes behavior (SP1 on: U cannot read the withheld field. SP2 on: U's update does not reach T. SP3 on: an invalid pointer is rejected) and the benign run passes with all three on | cc | todo | | Selective copy code exists in `interspec-artifact` wrappers |
| I2 | memcached/bipbuffer: same as I1 | Same test as I1, plus the 50-case gate passes | cc | todo | | |
| I3 | yaml/libyaml: same as I1 | Same test as I1, plus the 48-run parity set passes | cc | todo | | |
| I4 | nginx/libpcre: same as I1 | Same test as I1, plus the 104-response parity set passes | cc | todo | | |
| I5 | One PCRE version everywhere | Integration, PoC 2 and paper text all name the same library version | cc + ws | todo | | Paper says PCRE2, integration uses PCRE 8.45 |
| I6 | nginx/OpenSSL `ex_data_ptr` experiment | A wasm2c build that uses the real `SSL_set_ex_data` and `SSL_get_ex_data` calls, with T registering the connection object, runs the legitimate case and at least two altered pointers under RLBox-only, domain-only SP3 and full SP3, with raw logs kept | cc | todo | | In scope only if D3 allows |

## Phase 3: Security evaluation

| ID | Item | Done when | Where | Status | Evidence | Notes |
|---|---|---|---|---|---|---|
| S1 | Move the drafted subsection "Object Checks Beyond the Memory Domain" into paper `main` and name the old check domain-only SP3 in the evaluation | Text is in `main`, the PDF builds, and every count in the subsection matches `SP3_SECURITY_DELTA_RESULTS.md` | ws | todo | | Draft is on `backup/pre-oct-restore-20261112` |
| S2 | PoC 1 (rsync/popt) rerun under RLBox-only, domain-only SP3 and full SP3 | Raw stdout, stderr and exit codes kept for every configuration. Each policy shows an effect that the configuration without it does not. No crash is counted as a rejection | cc | todo | | Depends on I1 |
| S3 | PoC 2 (nginx/libpcre) rerun, same three configurations | Same as S2 | cc | todo | | Depends on I4 and I5 |
| S4 | Add the OpenSSL result to the paper | Result from I6 is in `eval.tex` and matches the raw logs | ws | todo | | Depends on I6 |
| S5 | One summary table: boundary, fault class, outcome under each configuration | Table is in `eval.tex` and a script regenerates it from the raw result files | ws | todo | | |

## Phase 4: Coverage and automation

| ID | Item | Done when | Where | Status | Evidence | Notes |
|---|---|---|---|---|---|---|
| C1 | Rebuild the CodeQL databases for the 10 boundaries at pinned source revisions | Each database builds from a recorded revision with a recorded command, and its hash is stored | cc | todo | | The original databases were not kept |
| C2 | Regenerate the two coverage tables from C1 | A script produces both tables from query output. Every difference from the current numbers (7,523 fields, 42.3%, 58.8%, 99.4%) is explained in Notes | cc | todo | | Depends on C1 |
| C3 | Table of metadata sources for full SP3 | For each pointer field that needs SP3 (currently 32, plus 11 unknown) the table gives the expected memory domain, where the type comes from (allocation site, declared helper, manual registration in T, none) and where the bounds come from | cc + ws | todo | | Depends on C1 |
| C4 | Manual effort per boundary | Counted from the repository: lines of boundary specification, manual type entries, registration calls in T | cc | todo | | |

## Phase 5: Performance

| ID | Item | Done when | Where | Status | Evidence | Notes |
|---|---|---|---|---|---|---|
| P1 | Host check | `tools/publication_host_preflight.py` output saved before the first run, with CPU sets for server and client that share no physical core | host | todo | | Depends on D2 |
| P2 | memcached/bipbuffer timing | Six scenarios, four variants (native, RLBox-only, tracking without check, InterSpec), 15 paired repetitions, 30 s windows. `verify_memcached_matrix.py` passes on the raw output | host | todo | | Depends on P1, F1 |
| P3 | nginx/libpcre timing | Four variants, 4 and 8 client threads, 15 paired repetitions. Correctness gate passes on the timed binaries | host | todo | | Depends on P1, F1, I5 |
| P4 | rsync/popt timing | Four variants, 194 MiB sync, 15 paired repetitions, output files match | host | todo | | Depends on P1, F1 |
| P5 | yaml/libyaml timing | Four variants, 1 MiB document, 1,000 parses, 15 paired repetitions, outputs match | host | todo | | Depends on P1, F1 |
| P6 | Per-policy cost on the four registry boundaries | Each of SP1, SP2 and full SP3 measured alone and all together, using the switches from I1 to I4, 15 paired repetitions | host | todo | | Depends on I1 to I4 |
| P7 | The other six boundaries, labeled domain-only SP3 | ffmpeg/libvpx, magick/libpng, memcached/hash, nginx/openssl, ucl/libucl and zip/libzip rebuilt from `interspec-artifact` and timed on the same host, RLBox-only against InterSpec, 15 paired repetitions, raw samples kept | host | todo | | Scope depends on D1 and D3 |
| P8 | Cost of one registry check | 39 configurations of `run_runtime_microbench.py`, 15 repetitions, on the host | host | todo | | Depends on P1 |
| P9 | Memory cost | Peak RSS and sandbox heap size for memcached and nginx, RLBox-only against InterSpec, over a run of at least 10 minutes | host | todo | | The allocator does not reuse freed addresses |
| P10 | One estimator for every table | A script regenerates every performance table from raw CSV files, using the median of paired ratios, and the paper states this estimator | ws | todo | | Can start on existing data |

## Phase 6: Paper and artifact

| ID | Item | Done when | Where | Status | Evidence | Notes |
|---|---|---|---|---|---|---|
| W1 | Performance tables and text in `eval.tex` | Every number comes from P2 to P9 through the P10 script. The setup paragraph names the real host, OS and library versions | ws | todo | | |
| W2 | Coverage tables and text in `eval.tex` | Every number comes from C2 to C4 | ws | todo | | |
| W3 | Abstract, introduction and conclusion numbers | They equal the numbers in `eval.tex` | ws | todo | | Abstract now says 1 to 19% and more than 75% |
| W4 | Open reviewer comments in `eval.tex` | The `\trent` and `\hamed` comments are answered in the text or removed with JH's agreement | ws + JH | todo | | |
| W5 | Artifact update | `interspec-artifact` holds the raw data, the scripts and a mapping from each paper claim to a file | cc | todo | | |
| W6 | Final check | A script confirms that every number in the evaluation section equals a value computed from the artifact data, and the PDF builds from a clean checkout | ws | todo | | Last item |

## Log

One line per change: date, item, old status to new status, evidence or reason.

- 2026-11-13: tracker created, all items `todo`.
