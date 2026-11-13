# I1 raw output: rsync/popt policy switches

Tracker item I1 in `EVAL_TRACKER.md`. Functional evidence from the Claude Code
build machine. Nothing here is a timing measurement.

Each run directory is the unmodified output of
`scripts/run_rsync_policy_switches.sh`, started from a clean checkout of the
commit in its name (`source-commit.txt`, `source-status.txt`). Runs were started
once each. No case was retried or replaced.

| Directory | Commit | Result |
|---|---|---|
| `00-environment-failures/` | `5145be1` | Two attempts to run the existing `scripts/run_rlbox_wasm2c_poc.sh` before any change. Both failed for reasons of this machine: CMake 3.28 (RLBox needs 3.30), then no `libpopt-dev` (rsync linked its bundled popt next to the bridge). Fixed by installing both, as CI does. |
| `01-tests-before-implementation-64e078e/` | `64e078e` | Tests exist, switches do not. All four tests fail, as intended: U reads the help text with SP1 "on", U's write never reaches T with SP2 "off", and the invalid pointer is rejected with SP3 "off". Benign fails only on the missing configuration report. |
| `02-implementation-80db23c/` | `80db23c` | Switches implemented. See below. |

## What the three switch tests show (`02-implementation-80db23c/switch-tests/`)

The driver is `integration/rsync_popt/policy_switch_test.cpp`, linked against
the same bridge source as the complete rsync executable, in a test build where
U misbehaves on request. It uses the PoC 1 option table from the paper
appendix. Each case is one process; `env.json`, `stdout.txt`, `stderr.txt` and
`exit_code.txt` are kept per case, and `summary.json` lists every check.

| Test | Switch off | Switch on |
|---|---|---|
| SP1 | U prints `descrip='SECRET_HELP' argDescrip='SECRET_ARG'`; T finds both strings in U memory | U prints `(null)` for both; T finds neither string anywhere in U memory |
| SP2 | U sets `val` of `readonly` to 1337 in its copy; T's own table then holds 1337 | Same U write; T's table still holds 42 |
| SP3 | U returns an untracked heap copy for the `--set` string; T accepts it (`off` and `domain`) | `INTERSPEC_REJECT reason=InterSpec rejected popt char pointer: untracked`, then the bridge's deliberate abort (exit by SIGABRT). The rejection line, not the abort, is what the test requires |

Limits of these tests:

- SP2 stops the write-back of the option table only. In both SP2 cases
  `poptGetNextOpt` still returns 1337 to T, because the return value is U's to
  produce. See `sp2_on_u_writes/stdout.txt`, `stage=next rc=1337`.
- The SP3 case is one fault (untracked pointer, same content). The other fault
  classes are in `SP3_SECURITY_DELTA_RESULTS.md`; this test only shows that the
  switch selects the check.
- `sp3=domain` is exercised by one case in which it accepts the pointer. No
  case here shows domain-only SP3 rejecting anything.

## Benign run (`02-implementation-80db23c/benign/`)

The complete rsync executable from the build without test hooks, compared with
native rsync of the same revision on four commands (`--version` with string
and numeric options, a dry run, a checksummed local sync with an exclude, and
an unknown option). `all_on` is the configuration the tracker asks for. The
other four are the configurations P6 will time.
