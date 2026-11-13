# I2 raw output: memcached/bipbuffer policy switches

Tracker item I2 in `EVAL_TRACKER.md`. Functional evidence from the Claude Code
build machine. Nothing here is a timing measurement.

Each run directory is the unmodified output of
`scripts/run_memcached_policy_switches.sh`, started once from a clean checkout
of the commit in its name. No case was retried or replaced.

| Directory | Commit | Result |
|---|---|---|
| `01-tests-before-implementation-cb27f12/` | `cb27f12` | Tests exist, switches do not. The SP1, SP2 and SP3 tests fail as intended. The 50-case gate passes (50/50); the gate check fails only because no server reports a policy configuration yet. |
| `02-implementation-4c6b5b6/` | `4c6b5b6` | Switch tests pass, gate 50/50 with all three policies on, and the `memcached-interspec` server reports `sp1=1 sp2=1 sp3=full`. |

## Where the fields come from

`interspec-artifact` has no selective copy code for this boundary: its
bipbuffer wrapper reads SP1 and SP2 switches that control nothing. The fields
are the SP1 and SP2 slots of that repository's policy export,
`data/raw/policy_reports/memcached_bipbuffer/`:

- SP1: the length out-parameter of `bipbuf_peek_all`. U writes it and never
  reads it, so T's value before the call is not copied in.
- SP2: the `data` argument of `bipbuf_offer`. U reads it and never writes it,
  so U's copy is not copied back.

## What the three switch tests show (`switch-tests/`)

The driver is `integration/memcached_server/policy_switch_test.cpp`, compiled
with the server's own `bridge.cpp` and the fault-test U module.

| Test | Switch off | Switch on |
|---|---|---|
| SP1 | U reads `len_in=0x5ec2e7`, the value T held in the out-parameter | U reads `len_in=0x0` |
| SP2 | U flips byte 0 of its copy of the record; T's record then starts with `ab` | Same U write; T's record is unchanged |
| SP3 | U returns an untracked heap copy from `bipbuf_peek_all`; T accepts it (`off` and `domain`) | `INTERSPEC_REJECT boundary=memcached_bipbuffer operation=peek_all reason=untracked`, then the bridge's deliberate abort |

Limits:

- At this boundary `INTERSPEC_SP3=0` and `INTERSPEC_SP3=domain` are the same.
  Every isolated variant, including RLBox-only, already checks that a returned
  pointer lies in sandbox memory; the switch only removes the registry check.
- The switches act in the `memcached-interspec` variant. The RLBox-only and
  tracked-no-check variants are compiled without the registry check; they
  honor SP1 and SP2 and report `+sp3_fixed_at_compile_time`.
- With SP1 off inside memcached, the wrapper reads the caller's uninitialized
  `size` variable before `bipbuf_peek_all`. That is the leak SP1 prevents, and
  it is why SP1 off is a comparison configuration only.
- The gate ran with all three on. It was not run with any switch off.
