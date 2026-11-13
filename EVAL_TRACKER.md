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
| F1 | Merge the PR stack (#15 to #28) and `claude/nifty-cray-ik99hh` into `main` of `interspec-typed-allocator` | `main` contains the work, the core, memcached, nginx and sp3-security-delta workflows pass at that commit, and tag `eval-base` points to it | cc | blocked | Candidate `7f7b689` (fast-forward of `main`, which is its ancestor). All four pass there: ci [43398890812](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/43398890812), memcached-deployment [43398890615](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/43398890615), nginx-deployment [43398899526](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/43398899526), sp3-security-delta [43398890465](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/43398890465). Earlier candidate `5145be1` failed memcached-deployment (logs in `evaluation/results/tracker/F1/`) | Blocked on JH: approve the fast-forward of `main` to `7f7b689` and the tag `eval-base` there. Nothing was merged or tagged. `7f7b689` holds PRs #15 to #28, the branch through Stage 20, the memcached-deployment repair `81d4785`, I1, I2 and the I4 test hooks. It does not hold `708ceb7` (another session's second change to the memcached profiling step, never run in CI) or the I4 implementation `30852b9`; choosing a later commit instead needs all four workflows green at that commit. The nginx-deployment pass is the pull-request run; the push run 43398891319 was cancelled by the workflow's own concurrency rule when the pull-request run started. The repair restored the collector of the last green run as `tools/profile_memcached_checks_hosted.py`, after `545474d` (pushed without CI) had pinned `tools/profile_memcached_checks.py` to fixed binary hashes |

## Phase 2: Implementation gaps

| ID | Item | Done when | Where | Status | Evidence | Notes |
|---|---|---|---|---|---|---|
| I1 | rsync/popt: one build with SP1, SP2, full SP3 and a switch for each policy | A test shows each switch changes behavior (SP1 on: U cannot read the withheld field. SP2 on: U's update does not reach T. SP3 on: an invalid pointer is rejected) and the benign run passes with all three on | cc | done | Tests `64e078e`, implementation `1bb53dc`. Raw output `evaluation/results/tracker/I1/02-implementation-80db23c/` (`switch-tests/summary.json`, `benign/summary.json`). Clean-runner rerun at `7f7b689`: policy-switches [43398890604](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/43398890604), job log in `evaluation/results/tracker/I1/03-ci-7f7b689/` | Checked again before `done`: each of the SP1, SP2 and SP3 switch tests passes on both sides of the switch, and the complete rsync passes its benign run with all three on (also all off and each alone). ci [43398890812](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/43398890812) and sp3-security-delta [43398890465](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/43398890465), which build the same bridge, pass at `7f7b689`. Switches: `INTERSPEC_SP1`, `INTERSPEC_SP2` (0 or 1), `INTERSPEC_SP3` (0, domain, 1); unset means on. SP1 and SP2 use the field table of the artifact wrapper. SP2 off is new code, because the artifact never copied the option table back. Limit: with SP2 on, U's changed `val` still reaches T as the return value of `poptGetNextOpt`. The CI artifact itself could not be downloaded here, so the CI check rests on the job log |
| I2 | memcached/bipbuffer: same as I1 | Same test as I1, plus the 50-case gate passes | cc | done | Tests `cb27f12`, implementation `4c6b5b6`. Raw output `evaluation/results/tracker/I2/02-implementation-4c6b5b6/` (`switch-tests/summary.json`, `gate/summary.json`). Clean-runner rerun at `7f7b689`: policy-switches [43398890604](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/43398890604), job log in `evaluation/results/tracker/I2/03-ci-7f7b689/` | Checked again before `done`: SP1, SP2 and SP3 switch tests pass on both sides of the switch, the benign run passes, and the 50-case gate is 50/50 with all three on. memcached-deployment [43398890615](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/43398890615) passes at `7f7b689`. SP1 field: length out-parameter of `bipbuf_peek_all`. SP2 field: `data` of `bipbuf_offer`. Both from the artifact's policy export, because its bipbuffer wrapper has no selective copy code; this reading of "same test as I1" still needs JH's confirmation (see Log). At this boundary SP3 off and domain are the same, since every isolated variant already checks confinement |
| I3 | yaml/libyaml: same as I1 | Same test as I1, plus the 48-run parity set passes | cc | blocked | | Blocked on JH, three points. (1) No field for SP1: in this integration T is a bench driver that sends U only the document bytes, which U must read; `yaml_parser_t` and `yaml_event_t` live entirely in U. "U cannot read the withheld field" has no field to test unless the wrapper is rebuilt around the libyaml API with a T-owned `yaml_event_t`. SP2 (document bytes) and SP3 are testable as in I2. (2) The 48-run parity set (Stage 12 corpus and harness) is not in the repository, only in the private archive `interspec-unified-yaml-functional-verified-20261111.tar.gz`. (3) Another session is changing `integration/yaml_libyaml/` on this branch (`3087664`, Stage 20). Unblocks: JH decides (1), supplies or commits (2), and says who owns the yaml files |
| I4 | nginx/libpcre: same as I1 | Same test as I1, plus the 104-response parity set passes | cc | doing | Tests `dc664f9`, implementation `30852b9`, raw output `evaluation/results/tracker/I4/` (run at `30852b9`) | Switch tests pass (SP1, SP2, SP3, benign) and the repository's nginx gate passes 24/24 with all three on. Missing: the 104-response parity set. Its corpus and harness (Stage 13) are not in the repository, only in the private archive `interspec-nginx-functional-verified-20261111.tar.gz`; JH has to supply it. Also missing: a CI run of the new `policy-switches` nginx job. SP1 field: output vector of `pcre_exec`. SP2 field: subject of `pcre_exec`. Library is PCRE 8.45, see I5. SP3 off and domain are the same here, as for I2 |
| I5 | One PCRE version everywhere | Integration, PoC 2 and paper text all name the same library version | cc + ws | blocked | | Blocked on JH: which version. Facts: the integration (`scripts/build_nginx_deployment.sh`, all security-delta and parity evidence, I4) uses PCRE 8.45 from `nektro/pcre-8.45` at `e67dabe`. PoC 2 and the wrapper in `interspec-artifact` use PCRE2 (`pcre2_pattern_info`). The paper is mixed: `eval.tex` lines 257, 320, 322 say PCRE2, while `auto_policy_inference.tex` uses the PCRE1 API (`pcre_compile`, `pcre_exec`). Recommendation: PCRE 8.45 everywhere, because all full-SP3 evidence is on it; then PoC 2 is rerun on 8.45 under S3 and the three `eval.tex` lines change in ws. Nothing was changed for I5 |
| I6 | nginx/OpenSSL `ex_data_ptr` experiment | A wasm2c build that uses the real `SSL_set_ex_data` and `SSL_get_ex_data` calls, with T registering the connection object, runs the legitimate case and at least two altered pointers under RLBox-only, domain-only SP3 and full SP3, with raw logs kept | cc | todo | | In scope only if D3 allows |

## Phase 3: Security evaluation

| ID | Item | Done when | Where | Status | Evidence | Notes |
|---|---|---|---|---|---|---|
| S1 | Move the drafted subsection "Object Checks Beyond the Memory Domain" into paper `main` and name the old check domain-only SP3 in the evaluation | Text is in `main`, the PDF builds, and every count in the subsection matches `SP3_SECURITY_DELTA_RESULTS.md` | ws | todo | | Draft is on `backup/pre-oct-restore-20261112` |
| S2 | PoC 1 (rsync/popt) rerun under RLBox-only, domain-only SP3 and full SP3 | Raw stdout, stderr and exit codes kept for every configuration. Each policy shows an effect that the configuration without it does not. No crash is counted as a rejection | cc | doing | Harness `bd94353`, raw output `evaluation/results/tracker/S2/01-poc1-bd94353/` (24 processes: 4 configurations by 6 attacks) | Raw stdout, stderr and exit codes are kept for every configuration, and no crash is counted as a rejection. Open: "each policy shows an effect". SP1 and SP2 show an effect over RLBox-only. Full SP3 shows one over domain-only SP3 (untracked pointer inside the sandbox). Domain-only SP3 shows none over RLBox-only on the paper's PoC 1 pointer: RLBox confinement already rejects `0xDEADBEEF`. It differs only from the one build with all switches off, where T crashes with SIGSEGV. JH decides which baseline "RLBox-only" means and whether that satisfies the condition. Also waits for I1 to be `done`. Not in CI |
| S3 | PoC 2 (nginx/libpcre) rerun, same three configurations | Same as S2 | cc | todo | | Depends on I4 and I5 |
| S4 | Add the OpenSSL result to the paper | Result from I6 is in `eval.tex` and matches the raw logs | ws | todo | | Depends on I6 |
| S5 | One summary table: boundary, fault class, outcome under each configuration | Table is in `eval.tex` and a script regenerates it from the raw result files | ws | todo | | |

## Phase 4: Coverage and automation

| ID | Item | Done when | Where | Status | Evidence | Notes |
|---|---|---|---|---|---|---|
| C1 | Rebuild the CodeQL databases for the 10 boundaries at pinned source revisions | Each database builds from a recorded revision with a recorded command, and its hash is stored | cc | blocked | | Blocked on JH: the revisions to pin are not recorded anywhere I can read. `interspec-artifact` omits upstream histories; its scripts expect sources under `benchmarks/` and name only libvpx 1.15.2 and libyaml 0.2.5. No revision is given for ffmpeg, ImageMagick/libpng, libucl, libzip, nginx, OpenSSL, memcached or rsync. The CodeQL CLI can be downloaded on the build machine, so the builds themselves are feasible. Unblocks: JH supplies the ten revisions (the old build tree of D2 may have them), or allows pinning current releases with every difference explained under C2 |
| C2 | Regenerate the two coverage tables from C1 | A script produces both tables from query output. Every difference from the current numbers (7,523 fields, 42.3%, 58.8%, 99.4%) is explained in Notes | cc | todo | | Depends on C1 |
| C3 | Table of metadata sources for full SP3 | For each pointer field that needs SP3 (currently 32, plus 11 unknown) the table gives the expected memory domain, where the type comes from (allocation site, declared helper, manual registration in T, none) and where the bounds come from | cc + ws | todo | | Depends on C1 |
| C4 | Manual effort per boundary | Counted from the repository: lines of boundary specification, manual type entries, registration calls in T | cc | done | `tools/count_manual_effort.py`, output `evaluation/results/tracker/C4/MANUAL_EFFORT.md` and `manual_effort.json` (each count with its file and line) | Scope is the four registry boundaries in this repository; the other six have no registry, so no type entries or registration calls. Counts (specification lines, manual type entries, manual registration calls in T): rsync/popt 8, 1, 0. memcached/bipbuffer 11, 1, 3. yaml/libyaml 17, 1, 1. nginx/libpcre 8, 3, 0. The memcached calls are the T-object registration of the LRU item experiment. Not counted, because the item does not ask for it: the hand-written bridges themselves (about 570 to 1,230 lines per boundary across T and U). Reopen if the six domain-only boundaries or the bridge code should be included |

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
- 2026-11-13: tracker committed to `interspec-typed-allocator` (`fd5bf5f`).
- 2026-11-13: F1 `todo` to `doing`. PR #28 merged into `claude/nifty-cray-ik99hh`; candidate pushed without `[skip ci]` so the workflows run at the exact commit proposed for `main`. Merge to `main` and tag wait for JH.
- 2026-11-13: F1 stays `doing`. memcached-deployment failed at candidate `5145be1` (runs 43393783638 and 43393791474, step "Profile SP3 check frequency"). ci and sp3-security-delta passed there. Repair committed as `81d4785`, not yet run in CI.
- 2026-11-13: I1 `todo` to `doing`. Tests written first (`64e078e`) and run against the unchanged bridge, where all four fail as intended (`evaluation/results/tracker/I1/01-tests-before-implementation-64e078e/`). With the implementation (`1bb53dc`) the same script passes (`02-implementation-80db23c/`). Two earlier build attempts failed on this machine (CMake 3.28, missing `libpopt-dev`); logs in `00-environment-failures/`.
- 2026-11-13: commits `3087664` and `9aa34f0` ("Stage 20", YAML typed staging) were pushed to this branch by another session during I1. Merged as `6e61102`, no rebase and no force push. They change `integration/yaml_libyaml/`, which I3 also has to change.
- 2026-11-13: proposal for JH, no tracker text changed. I2 to I4 say "same test as I1", and the session rule says to reuse the artifact's selective copy code. In `interspec-artifact` only the rsync/popt wrapper has such code. The memcached, yaml and nginx wrappers read SP1 and SP2 switches that control nothing; only their SP3 switch has an effect. For I2 to I4 the withheld and read-only fields have to be taken from the policy exports (`data/raw/policy_reports/<boundary>/`) and the copy code written new. I2 is proceeding on that reading; say so if I2 to I4 should be defined differently.
- 2026-11-13: I2 `todo` to `doing`. Tests first (`cb27f12`): switch tests fail as intended, gate 50/50 (`evaluation/results/tracker/I2/01-tests-before-implementation-cb27f12/`). Implementation `4c6b5b6`: switch tests pass and gate 50/50 with all three on (`02-implementation-4c6b5b6/`). No failed or repeated run.
- 2026-11-13: I3 `todo` to `blocked`. Reasons in Notes: no SP1 field at the yaml boundary as integrated, 48-run parity set not in the repository, concurrent edits to the yaml integration by another session.
- 2026-11-13: `f904ae6` was meant to start CI and did not: its message quoted the skip marker, which GitHub honors anywhere in a commit message. No workflow ran at `f904ae6`. The next push carries a clean message.
- 2026-11-13: I4 started (tests commit `dc664f9`). The 104-response parity set (Stage 13 corpus and harness) is not in the repository either, only in `interspec-nginx-functional-verified-20261111.tar.gz`. I4 can reach the switch tests and the repository's own nginx gate, but not `done`, until JH supplies that set.
- 2026-11-13: F1 stays `doing`. Added a current-source frozen profile wrapper after compatibility repair `81d4785`, preserving that collector and all concurrent work through `f904ae6`. Both workflow call sites use the reviewed wrapper; v1 historical pins are unchanged. Focused VM validation passed 17 current-profile, 39 corrected-profile, ten legacy-profile and 12 metadata/renderer cases (code/source and logs in `evaluation/results/tracker/F1/profile-migration-vm/`). No actual server profile, hosted workflow, merge to main, tag or paper edit was performed. Publication uses `[skip ci]`; F1 acceptance remains open.
- 2026-11-13: I4 `todo` to `doing`. Tests first (`dc664f9`): switch tests fail as intended, nginx gate 24/24. Implementation `30852b9`: switch tests pass, gate 24/24 with all three on (`evaluation/results/tracker/I4/`). Not `done`: the 104-response parity set is not in the repository.
- 2026-11-13: I5 `todo` to `blocked`. Needs JH's choice of PCRE version; facts and a recommendation are in Notes.
- 2026-11-13: workflows at `7f7b689` so far: ci [43398890812](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/43398890812) pass, memcached-deployment [43398890615](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/43398890615) pass (the `81d4785` repair works), policy-switches [43398890604](https://github.com/ARISTODE/interspec-typed-allocator/actions/runs/43398890604) pass for both the I1 and I2 jobs. nginx-deployment and sp3-security-delta still running when this line was written. CI artifacts cannot be downloaded from this machine (storage host blocked), so the CI check is from job logs.
- 2026-11-13: S2 `todo` to `doing`. PoC 1 run once under four configurations (`evaluation/results/tracker/S2/`). Finding for JH: against an RLBox-only baseline that keeps RLBox confinement, domain-only SP3 adds nothing on PoC 1's out-of-sandbox pointer; full SP3 adds the rejection of an untracked in-sandbox pointer.
- 2026-11-13: I1 `doing` to `done`. Evidence reopened: local summaries, and the CI job log of policy-switches run 43398890604 at `7f7b689` (every step exit 0). ci and sp3-security-delta pass at `7f7b689`.
- 2026-11-13: I2 `doing` to `done`. Evidence reopened: local summaries (switch tests, gate 50/50) and the CI job log of the same run. memcached-deployment passes at `7f7b689`. If JH rejects the choice of SP1 and SP2 fields for I2, it reopens.
- 2026-11-13: `708ceb7` (another session) replaced the memcached-deployment profiling step again, with `scripts/run_memcached_profile.sh`, and states that no workflow was run. Merged as `2d3e8ef`. The step validated in CI at `7f7b689` is therefore no longer the one at the branch head; the head needs its own CI run.
- 2026-11-13: C1 `todo` to `blocked`: no recorded source revisions for the ten boundaries. C2 and C3 wait on C1.
- 2026-11-13: C4 `todo` to `done`. Counted by script at `fe72b8f` for the four registry boundaries; output reopened and compared with the listed source lines. Scope question for JH is in Notes.
- 2026-11-13: I6 not started: in scope only if D3 allows, and D3 is `todo`. S3 not started: depends on I4 and I5.
- 2026-11-13: F1 `doing` to `blocked` on JH. All four workflows pass at `7f7b689` (run links in Evidence). Waiting for approval of the fast-forward of `main` and of the tag `eval-base`.
- 2026-11-13: this commit is pushed so that CI runs at the branch head, which adds `708ceb7` and the I4 implementation to what was tested at `7f7b689`.
