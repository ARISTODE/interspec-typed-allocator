# S2 raw output: PoC 1 (rsync/popt) under each configuration

Tracker item S2 in `EVAL_TRACKER.md`. Functional evidence from the Claude Code
build machine; nothing here is a timing measurement. One run, started once from
a clean checkout of `bd94353` with `scripts/run_rsync_poc1.sh`. No case was
retried or replaced. `01-poc1-bd94353/poc1/<configuration>__<attack>/` holds
`env.json`, `stdout.txt`, `stderr.txt` and `exit_code.txt` for each of the 24
processes; `summary.json` and `TABLE.md` are derived from those files only.

The PoC program is the option table of the paper's PoC 1 listing
(`integration/rsync_popt/policy_switch_test.cpp`). U's three actions are those
of the `interspec-artifact` PoC: read the help text of `set`, write `val` of
`readonly`, and return `0xDEADBEEF` for the `--set` string. A fourth action,
not in the paper, returns an untracked heap pointer inside the sandbox.

## Configurations

| Name | What it is |
|---|---|
| `rlbox_only` | The RLBox comparator build of the security-delta study: no InterSpec tracking, no selective copy, but RLBox confinement and T's bounded string copy stay on. |
| `switches_all_off` | The one InterSpec build with `INTERSPEC_SP1=0 INTERSPEC_SP2=0 INTERSPEC_SP3=0`: no selective copy and no pointer check of any kind. |
| `domain_only_sp3` | The one build with SP1 and SP2 on and `INTERSPEC_SP3=domain`. |
| `full_sp3` | The one build with all three on. |

## Result

| Configuration | U reads help text | T's `val` after U's write | Pointer outside sandbox | Untracked pointer in sandbox |
|---|---|---|---|---|
| `rlbox_only` | yes | 1337 | rejected by RLBox confinement | accepted |
| `switches_all_off` | yes | 1337 | **crash (SIGSEGV)**, not a rejection | accepted |
| `domain_only_sp3` | no | 42 | rejected (`outside_domain`) | accepted |
| `full_sp3` | no | 42 | rejected (`untracked`) | rejected (`untracked`) |

What each policy adds:

- SP1 and SP2 each show an effect over `rlbox_only`.
- Full SP3 shows an effect over `domain_only_sp3`: only it rejects the
  untracked pointer inside the sandbox.
- Domain-only SP3 shows **no effect over `rlbox_only`** on the paper's PoC 1
  pointer. RLBox confinement already rejects `0xDEADBEEF`. Domain-only SP3
  differs only from `switches_all_off`, where T dereferences the pointer and
  the process dies with SIGSEGV. That crash is recorded as a crash.

So whether "each policy shows an effect that the configuration without it does
not" holds for the domain check depends on which baseline "RLBox-only" means.
The tracker item is left open on that point.

Other limits: with SP2 on, `poptGetNextOpt` still returns U's 1337 to T as its
return value (see `stage=next rc=1337` in the `sp2_write_readonly_val` cases).
The `rlbox_only` driver reports `sp3=full` in its policy line with the suffix
`+sp3_fixed_at_compile_time`; its pointer handling is the comparator's, not a
switch.
