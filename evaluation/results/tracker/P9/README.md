# P9: memory cost

Tracker item P9 in `EVAL_TRACKER.md`. Measured on the Claude Code cloud VM
described in `evaluation/results/tracker/P1/`. These are memory sizes, not
timings.

| Directory | Content |
|---|---|
| `00-sandbox-heap-measurement-check/` | Check of the method: the sandbox heap size read from `/proc/PID/smaps` equals what RLBox reports as `get_total_memory`, before and after 96 MiB are allocated in a sandbox. |
| `01-vm-6fe7a6d-600s/` | First measurement: memcached and nginx, native, RLBox-only and InterSpec, 600 s under load each. Its two RLBox-only runs made the selective copies of SP1 and SP2 (see the correction below); its nginx native and nginx InterSpec runs are still used. |
| `02-vm-16509e7-rlbox-only-copies-everything/` | The RLBox-only runs repeated with SP1 and SP2 off (`policy_switches` in each `run.json`): memcached native, RLBox-only and InterSpec on the binaries of P2 run 05, and nginx RLBox-only on the same binary as in run 01. 600 s under load each. |

## Correction of 2026-11-15: what RLBox-only means

JH pointed out on 2026-11-15 that the RLBox-only variant must enforce none of
SP1, SP2 and SP3: its wrapper copies everything. `tools/measure_memory_cost.py`
removed every `INTERSPEC_` variable before it started a server, so the
RLBox-only servers of run 01 made the selective copies. Since `4ecfe97` the
tool starts the RLBox-only server with `INTERSPEC_SP1=0 INTERSPEC_SP2=0` and
records the switches in `run.json`. Run 02 repeats the RLBox-only runs. The
memcached binaries had been rebuilt for P2 run 05, so all three memcached
variants were repeated on the new binaries; the nginx binaries are the ones of
run 01 (same SHA-256), so only nginx RLBox-only was repeated. Each run started
with a 1-minute load average below 0.30 (`loadavg-before-*.txt`). The numbers
below are from run 02 where it has the run and from run 01 otherwise; they
differ from run 01's by at most 0.6 MiB of peak RSS, and no heap size changed.

## How it was run

`tools/measure_memory_cost.py run`, one server per run, same binaries as the
timing runs (P2 for memcached, P3 for nginx; SHA-256 in each `run.json`).

- memcached: the `watch_moderate` load of P2 (2 clients, pipeline 2, 256-byte
  values, 10,000 keys, half GET, one watcher connection reading the log).
- nginx: `wrk` with 4 threads and 100 connections on the regex location of
  P3, every response checked.
- Every 5 s, for every process of the server: `VmRSS` and `VmHWM` from
  `/proc/PID/status`, and the linear memory of every wasm2c sandbox from
  `/proc/PID/smaps` (its size and the part that is resident). 121 samples
  per run (`samples.csv`).
- A run counts only if the load ran for the full 600 s without a failed
  operation, the server was alive at the end and its log has no rejection.
  All runs in both directories meet this (`summary.json`).

## Result

| Application | Variant | Run | Peak RSS (MiB) | Sandboxes | Sandbox heap, all sandboxes (MiB) | Resident part of it, maximum (MiB) | Operations or requests served |
|---|---|---|---:|---:|---:|---:|---:|
| memcached | native | 02 | 8.16 | 0 | | | 50,216,872 |
| memcached | RLBox-only | 02 | 33.20 | 12 | 35.75 | 0.44 | 49,115,422 |
| memcached | InterSpec | 02 | 33.20 | 12 | 47.25 | 0.39 | 49,409,586 |
| nginx | native | 01 | 4.46 | 0 | | | 50,620,093 |
| nginx | RLBox-only | 02 | 8.37 | 22 | 26.12 | 2.32 | 37,573,807 |
| nginx | InterSpec | 01 | 8.55 | 22 | 46.75 | 2.39 | 39,838,713 |

Run 01 for comparison (RLBox-only with selective copies): memcached native
8.72, RLBox-only 33.39, InterSpec 33.21 MiB; nginx RLBox-only 8.39 MiB; the
sandbox heap sizes were the same as above.

"Sandbox heap" is the size of the linear memory that the sandbox has grown to
(what RLBox reports as total memory), summed over the sandboxes of the
process. Most of it is never touched; the resident part is what occupies
physical memory.

## Reading

- Peak RSS, InterSpec against RLBox-only: equal for memcached (33.20 MiB
  both) and +2.2% for nginx (8.55 against 8.37 MiB). InterSpec does not cost
  resident memory that this measurement can resolve.
- Sandbox heap size, InterSpec against RLBox-only: +32% for memcached (47.25
  against 35.75 MiB, 12 sandboxes) and +79% for nginx (46.75 against 26.12 MiB,
  22 sandboxes). In both servers this is about 0.95 MiB more linear memory
  per sandbox. It is address space inside the sandbox that is not touched:
  the resident part of the heap does not grow (0.39 against 0.44 MiB, 2.39
  against 2.32 MiB). That fits arenas that the typed allocator sets aside per
  type; I did not break the 0.95 MiB down further.
- No growth over time. In all four sandboxed runs the sandbox heap has the
  same size in every sample under load, after 38 to 49 million operations,
  and RSS moves by less than 0.3 MiB. The allocator reuses a
  released address for a later allocation at the same site (commit `62cd9c7`),
  so the heap does not grow with the number of calls.
- The sandbox itself (RLBox-only against native) costs 25.0 MiB of peak RSS
  for memcached and 3.9 MiB for nginx.
