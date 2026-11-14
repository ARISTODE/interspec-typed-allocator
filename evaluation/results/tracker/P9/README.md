# P9: memory cost

Tracker item P9 in `EVAL_TRACKER.md`. Measured on the Claude Code cloud VM
described in `evaluation/results/tracker/P1/`. These are memory sizes, not
timings.

| Directory | Content |
|---|---|
| `00-sandbox-heap-measurement-check/` | Check of the method: the sandbox heap size read from `/proc/PID/smaps` equals what RLBox reports as `get_total_memory`, before and after 96 MiB are allocated in a sandbox. |
| `01-vm-6fe7a6d-600s/` | The measurement: memcached and nginx, native, RLBox-only and InterSpec, 600 s under load each. |

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
  All six runs meet this (`summary.json`).

## Result

| Application | Variant | Peak RSS (MiB) | Sandboxes | Sandbox heap, all sandboxes (MiB) | Resident part of it, maximum (MiB) | Operations or requests served |
|---|---|---:|---:|---:|---:|---:|
| memcached | native | 8.72 | 0 | | | 58,694,696 |
| memcached | RLBox-only | 33.39 | 12 | 35.75 | 0.59 | 58,607,906 |
| memcached | InterSpec | 33.21 | 12 | 47.25 | 0.38 | 57,730,564 |
| nginx | native | 4.46 | 0 | | | 50,620,093 |
| nginx | RLBox-only | 8.39 | 22 | 26.12 | 2.32 | 41,136,606 |
| nginx | InterSpec | 8.55 | 22 | 46.75 | 2.39 | 39,838,713 |

"Sandbox heap" is the size of the linear memory that the sandbox has grown to
(what RLBox reports as total memory), summed over the sandboxes of the
process. Most of it is never touched; the resident part is what occupies
physical memory.

## Reading

- Peak RSS, InterSpec against RLBox-only: -0.5% for memcached (33.21 against
  33.39 MiB) and +1.9% for nginx (8.55 against 8.39 MiB). InterSpec does not
  cost resident memory that this measurement can resolve.
- Sandbox heap size, InterSpec against RLBox-only: +32% for memcached (47.25
  against 35.75 MiB, 12 sandboxes) and +79% for nginx (46.75 against 26.12 MiB,
  22 sandboxes). In both servers this is about 0.95 MiB more linear memory
  per sandbox. It is address space inside the sandbox that is not touched:
  the resident part of the heap does not grow (0.38 against 0.59 MiB, 2.39
  against 2.32 MiB). That fits arenas that the typed allocator sets aside per
  type; I did not break the 0.95 MiB down further.
- No growth over time. In all four sandboxed runs the sandbox heap has the
  same size in every one of the 120 samples under load, after 40 to 58 million
  operations, and RSS moves by less than 0.2 MiB. The allocator reuses a
  released address for a later allocation at the same site (commit `62cd9c7`),
  so the heap does not grow with the number of calls.
- The sandbox itself (RLBox-only against native) costs 24.7 MiB of peak RSS
  for memcached and 3.9 MiB for nginx.
