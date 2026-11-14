# P5: yaml/libyaml timing

Tracker item P5 in `EVAL_TRACKER.md`. Measured on the Claude Code cloud VM
described in `evaluation/results/tracker/P1/` (KVM guest, 4 virtual CPUs, not a
dedicated host) on 2026-11-14, with the whole run pinned to CPU 0 and nothing
else running in the session.

`01-vm-9e1b06a/` is one run of

    taskset -c 0 bash scripts/run_yaml_libyaml_evaluation.sh <dir>/run

started at commit `9e1b06a`. Two commits that touch only this directory and
the tracker were made while it ran, so the run's own record names `8a3f278`;
no source file differs between the two. `steps.txt` has the exit status (0);
`loadavg-before.txt` and `loadavg-after.txt` bracket the run (the script first
builds everything on the one pinned CPU, which is what raises the 15-minute
average at the end).

Protocol (the script's defaults): four variants (native, RLBox-only, tracking
without check, InterSpec), a generated 1 MiB document, 1,000 parses per
sample, 2 warm-up rounds, 15 repetitions in rotated order, overheads as
medians of per-repetition ratios. `run/yaml-performance.csv` has the 60
samples; every timed run's result was checked against the native result, and
`run/correctness.json` and `run/security.json` pass.

| | Median | Lowest repetition | Highest repetition |
|---|---:|---:|---:|
| Native, 1,000 parses | 7,235 ms | | |
| RLBox-only | 8,700 ms | | |
| Tracking without check | 8,466 ms | | |
| InterSpec | 8,495 ms | | |
| RLBox-only over native | +20.6% | +13.8% | +43.8% |
| Tracking over RLBox-only | -3.2% | -9.5% | +0.7% |
| Check over tracking | +1.3% | -7.7% | +6.1% |
| InterSpec over RLBox-only | -4.0% | -14.1% | +4.2% |
| InterSpec over native | +16.0% | +13.1% | +25.1% |

Two things to keep in mind when these numbers are used:

- The spread between repetitions is wide (RLBox-only over native ranges from
  14% to 44%). This is a shared VM.
- InterSpec is not faster than RLBox-only in any meaningful sense. The
  RLBox-only variant and the tracked variants do not run the same wrapper code
  for the scalar values (the tracked variants use a staging buffer), and the
  tracked path is consistently a little cheaper. The cost of the registry
  check itself is the "check over tracking" row: +1.3%, inside the noise.
