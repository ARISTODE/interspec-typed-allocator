# P4: rsync/popt timing

Tracker item P4 in `EVAL_TRACKER.md`. Measured on the Claude Code cloud VM
described in `evaluation/results/tracker/P1/` (KVM guest, 4 virtual CPUs, not a
dedicated host) on 2026-11-14, every measured rsync process pinned to CPU 0,
nothing else running in the session.

Both directories are one run each of

    INTERSPEC_P11_CPU=0 bash scripts/run_p11_wasm2c_performance.sh <dir>/run

with `steps.txt` (exit status and commit) and the load average before and
after. Protocol (the script's defaults): complete rsync 3.4.1 processes in
four variants (native with bundled popt, RLBox-only, tracking without check,
InterSpec), 2 warm-up rounds, 15 repetitions in rotated order, wall time of
the whole process, overheads as medians of per-repetition ratios.

| Directory | Commit | Result |
|---|---|---|
| `01-vm-47520ed-without-file-comparison/` | `47520ed` | Completed (exit 0, 180 samples), but the script then only required every rsync to exit successfully and did not compare the synced files with their source. Kept; not the evidence for P4. |
| `02-vm-4107215/` | `4107215` | With the comparison added to the script (after each invocation that writes files, outside the timed interval): exit 0, 180 samples, `run/file-comparisons.txt`: 136 synced files compared byte for byte, all equal. |

Second run, 194 MiB local file sync (`run/rsync-performance.csv`):

| | Median | Lowest repetition | Highest repetition |
|---|---:|---:|---:|
| Native | 1,310 ms | | |
| RLBox-only | 1,303 ms | | |
| Tracking without check | 1,300 ms | | |
| InterSpec | 1,295 ms | | |
| RLBox-only over native | -0.7% | -2.6% | +5.6% |
| Check over tracking | -0.4% | -2.6% | +1.9% |
| InterSpec over RLBox-only | -0.4% | -4.3% | +1.6% |
| InterSpec over native | -1.7% | -3.8% | +2.0% |

Reading: on the file sync, sandboxing popt and InterSpec's policies cost
nothing that this VM can resolve; every difference is inside the spread
between repetitions, and the negative medians are not speed-ups. The run is
dominated by file input and output; popt parses the command line once.

The script also times two smaller workloads. Option parsing alone (a 2 to 3 ms
process): RLBox-only over native +32.3% (13.1 to 58.9), InterSpec over
RLBox-only -0.8% (-14.7 to +14.2). The dry run is not usable on this VM: its
samples fall into two groups around 25 ms and 44 ms regardless of variant, and
in the second run most native samples landed in the slower group.

The synced file is 194 MiB of zero bytes, as the script has always generated
it; with that content "the files match" is a weak statement about data
integrity.
