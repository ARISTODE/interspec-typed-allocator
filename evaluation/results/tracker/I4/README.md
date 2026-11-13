# I4 raw output: nginx/libpcre policy switches

Tracker item I4 in `EVAL_TRACKER.md`. Functional evidence from the Claude Code
build machine. Nothing here is a timing measurement. The library is PCRE 8.45
(the PCRE8 interpreter), not PCRE2.

Each run directory is the unmodified output of
`scripts/run_nginx_policy_switches.sh`, started once from a clean checkout of
the commit in its name. No case was retried or replaced.

| Directory | Commit | Result |
|---|---|---|
| `01-tests-before-implementation-dc664f9/` | `dc664f9` | Tests exist, switches do not. The SP1, SP2 and SP3 tests fail as intended. The repository's nginx gate passes 24/24. |
| `02-implementation-30852b9/` | `30852b9` | See `steps.txt` and `switch-tests/summary.json`. |

## Not covered

The tracker asks for the 104-response parity set (Stage 13: four variants, 13
cases, forward and reverse order). Its corpus and harness are not in this
repository; they are in the private archive
`interspec-nginx-functional-verified-20261111.tar.gz`. The gate run here is
`tools/test_nginx_deployment.py`, which is a different and smaller check. I4
is therefore not complete on this evidence.

## Where the fields come from

`interspec-artifact` has no selective copy code for this boundary: its PCRE2
wrapper reads SP1 and SP2 switches that control nothing, and its policy export
describes the PCRE2 API. The two fields used here are the PCRE 8.45 parameters
with the same access pattern:

- SP1: the output vector of `pcre_exec`. U writes it; T's contents before the
  call are never read, so they are not copied in.
- SP2: the subject of `pcre_exec`. U reads it and never writes it, so U's copy
  is not copied back.

## What the three switch tests show (`switch-tests/`)

| Test | Switch off | Switch on |
|---|---|---|
| SP1 | U reads `ovector[0]=0x5ec2e7`, the value T had in the vector | U reads `0xffffffff`, the wrapper's own initial value |
| SP2 | U flips byte 0 of its copy of the subject; T's subject then starts with `d0` | Same U write; T's subject is unchanged |
| SP3 | U returns an untracked heap copy of the capture offsets; T accepts it (`off` and `domain`) | `INTERSPEC_REJECT boundary=nginx_pcre operation=capture_offsets reason=untracked`, then the bridge's deliberate abort |

Limits: as for memcached, `INTERSPEC_SP3=0` and `domain` are the same here,
because every isolated variant already checks confinement. The gate ran with all
three on only.

## Run with the rebuilt parity set (`03-with-parity-2bc267e/`)

Same script at `2bc267e`, after JH's decisions of 2026-11-13: the
`INTERSPEC_SP3=domain` setting is gone (one SP3), and the script now also runs
the 104-response parity set rebuilt from the Stage 13 description
(`evaluation/parity/nginx/`: 13 requests with hand-written expected status and
body, four release variants, forward and reverse order on one persistent
connection each). Result: switch tests pass, gate 24/24, parity 104/104, and
each variant passes its version command, syntax check and clean exit.

The "Not covered" section above describes the state before this run. The set
is rebuilt, not the original Stage 13 corpus. Before this formal run the runner
was tried once on the binaries of `02-implementation-30852b9`; it also gave
104/104 and the expectations were not changed afterwards.
