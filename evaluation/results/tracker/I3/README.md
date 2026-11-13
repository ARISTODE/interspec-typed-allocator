# I3 raw output: yaml/libyaml policy switches and rebuilt parity set

Tracker item I3 in `EVAL_TRACKER.md`, as changed by JH on 2026-11-13.
Functional evidence from the Claude Code VM. Nothing here is a timing
measurement; the `elapsed_ns` fields in the bench output are not used.

Each run directory is the unmodified output of
`scripts/run_yaml_policy_switches.sh`, started once from a clean checkout of
the commit in its name. No case was retried or replaced.

| Directory | Commit | Result |
|---|---|---|
| `01-tests-before-implementation-a0e7dca/` | `a0e7dca` | Tests exist, switches do not. The SP2 and SP3 tests fail as intended. All 48 parity runs already match the expected events, scalars, bytes and hash; the 12 `extended_sp3` runs fail only because no configuration is reported yet. |
| `02-implementation-2bc267e/` | `2bc267e` | SP2, SP3 and benign switch tests pass; parity 48/48. |

## No SP1 test

In this integration T is a bench program that sends U only the document
bytes, which U has to read. The libyaml parser and event objects live entirely
in U. There is no T field for SP1 to withhold, so `INTERSPEC_SP1` is read and
reported but changes nothing here.

## Switch tests (`switch-tests/`)

The driver is the fault-test build of `yaml_app_bench` in mode `extended_sp3`
on `evaluation/parity/yaml/block_flow.yaml`.

| Test | Switch off | Switch on |
|---|---|---|
| SP2 | U flips byte 0 of its copy of the document after parsing; T's document then starts with `0x94` | Same U write; T's document still starts with `0x6b` |
| SP3 | U returns an untracked heap copy of a scalar; T accepts it and the parse result is unchanged | `INTERSPEC_REJECT boundary=yaml_libyaml reason=untracked`, exit status 86 (this bench exits instead of aborting) |

The second `[SP2] sandbox mutated` line in each SP2 case is U's hook running
again when the sandbox shuts down, after T has printed its observation.

## Parity set (`parity/`)

Six documents in `evaluation/parity/yaml/`, four modes (native, `rlbox_only`,
`tracked_no_check`, `extended_sp3`), one and two parse iterations: 48 processes
on the builds without test hooks, all switches on. Expected values are in
`evaluation/parity/yaml/expected.json`, computed by PyYAML's pure-Python parser
(`tools/yaml_parity_oracle.py`) and committed before any bench was run.

This set is rebuilt from the description of the Stage 12 run. It is not the
original Stage 12 corpus. It compares aggregate counts and a 64-bit FNV-1a hash
of scalar bytes, not complete event sequences, tags, anchors or aliases. The
largest scalar is 41 bytes; the 8,191-byte staging limit is not exercised.
