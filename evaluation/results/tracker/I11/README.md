# I11 raw output: ucl/libucl registry port

Tracker item I11 in `EVAL_TRACKER.md`. Functional evidence from the Claude Code
VM. Nothing here is a timing measurement; `elapsed_ns` in the bench output is
not used.

libucl 0.9.4 (`058286f`, pinned in `evaluation/coverage/pins.json`) runs inside
an RLBox wasm2c sandbox. The trusted program keeps the interface of the
`interspec-artifact` wrapper, `parse_query_emit(input, key1, key2, &val1,
&val2, &emitted)`. The library source is upstream; the artifact ships only its
wrapper and workload, not libucl.

| Directory | Commit | Result |
|---|---|---|
| `01-tests-before-implementation-4ed7d54/` | `4ed7d54` | The port and its tests exist; the three policies are not switchable (the wrapper copies both ways and always checks). The "on" cases of SP1 and SP2 and the "off" case of SP3 fail, as intended. Benign 30/40: the ten InterSpec runs fail only because no configuration is reported. |
| `02-implementation-ef8a85b/` | `ef8a85b` | Switch tests pass; benign 40/40. |
| `03-arena-exhaustion-before-reuse-0972491/` | `0972491` | Not a pass or fail run: the port as first committed fails between 20,000 and 30,000 parses in both variants with the registry, because the typed arena does not reuse released addresses. See the README there. |
| `04-buffer-reuse-f8962c2/` | `f8962c2` | After the shim was changed to keep one buffer per result: switch tests pass, benign 40/40, and 200,000 parses complete in all three isolated variants (`long-run-*`). |
| `05-allocator-reuse-9f803c0/` | `9f803c0` | After the allocator change, with the shim allocating per parse again: switch tests pass, benign 40/40, 200,000 parses complete in all three isolated variants. |

Each run is the unmodified output of `scripts/run_ucl_port.sh`, started once
from a clean checkout. Before the two commits were made, the port was built
once in a scratch directory to get it compiling (WASI has no `realpath`; a stub
was added), and one test expectation was corrected: the first version of
`nested.conf` wrote `logging.level` as a literal key, which a path lookup does
not find. Those development runs are not evidence and were not kept.

## Policies at this boundary

| Policy | Field | Switch off | Switch on |
|---|---|---|---|
| SP1 | the three out-parameters, which U writes and never reads | U is handed T's values `0x5ec2e701` to `03` | U is handed 0 |
| SP2 | the document and the two keys, which U reads and never writes | U flips byte 0 of its copy; T's document then starts with `0x8c` | T's document still starts with `0x73` |
| SP3 | the two looked-up strings and the emitted document that U returns | U returns an untracked heap copy; T accepts it | `INTERSPEC_REJECT boundary=ucl_libucl operation=string_value reason=untracked`, exit status 86 |

The registry knows the returned objects through two declared helper sites in
the U shim (`string_value`, `emitted`): the shim copies each result into a
typed allocation before handing it to T. libucl's own allocation sites are not
instrumented.
From `f8962c2` to `9f803c0` the shim kept one such allocation per result and
reused it. Since the allocator change of 2026-11-14
(`evaluation/results/tracker/A1/`) it allocates per parse again, as at
`ef8a85b`.

## Benign run (`benign/`)

Five cases from `evaluation/parity/ucl/` (three documents, different lookup
paths, one missing key), one and two iterations, four programs each: 40
processes. Every isolated variant prints the same looked-up values, emitted
length and emitted hash as the native build of the same libucl revision.
