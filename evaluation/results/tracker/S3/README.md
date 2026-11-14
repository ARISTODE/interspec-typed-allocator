# S3 raw output: PoC 2 (nginx/libpcre, PCRE 8.45) under each configuration

Tracker item S3 in `EVAL_TRACKER.md`. Functional evidence from the Claude Code
VM; nothing here is a timing measurement. One run, started once from a clean
checkout of `944eb9d` with `scripts/run_nginx_poc2.sh`. No case was retried or
replaced. `01-poc2-944eb9d/poc2/<configuration>__<attack>/` holds `env.json`,
`stdout.txt`, `stderr.txt` and `exit_code.txt` for each of the 10 processes;
`summary.json` and `TABLE.md` are derived from those files only.

The PoC program is `integration/nginx_server/policy_switch_test.cpp` with a
named-capture expression, so that the wrapper fetches the PCRE name table as
nginx does for a regex location with named captures. The library is PCRE 8.45
(`pcre_fullinfo` with `PCRE_INFO_NAMETABLE`), not PCRE2 as in the paper text.

## Configurations (decided by JH on 2026-11-13)

| Name | What it is |
|---|---|
| `rlbox_only` | RLBox-only bridge build on the untracked fault-test module: no tracking, no registry, no selective copy, sandbox confinement kept. |
| `interspec` | The one build with SP1, SP2 and SP3 on. |

## Result

| Configuration | U reads T's output vector | T's subject after U's write | Name table pointer outside sandbox | Untracked name table pointer in sandbox |
|---|---|---|---|---|
| `rlbox_only` | yes | changed | rejected (confinement) | accepted |
| `interspec` | no | unchanged | rejected (confinement) | rejected (`untracked`) |

- SP1, SP2 and SP3 each show an effect over `rlbox_only`.
- The pointer of the paper's PoC 2, `0xFFFFFFF0`, shows **no difference**: the
  sandbox confinement check that every isolated variant performs rejects it in
  both configurations, before SP3 is reached. What SP3 adds is the rejection of
  a pointer that is inside the sandbox but is not the registered name table.
  The paper's PoC 2 text should use that pointer for the SP3 claim.
- No process crashed. No crash is counted as a rejection.
