# P5: yaml/libyaml timing

Tracker item P5 in `EVAL_TRACKER.md`. Measured on the Claude Code cloud VM
described in `evaluation/results/tracker/P1/` (KVM guest, 4 virtual CPUs, not a
dedicated host) on 2026-11-14, with the whole run pinned to CPU 0 and nothing
else running in the session.

## Correction of 2026-11-15: what RLBox-only means

JH pointed out on 2026-11-15 that the RLBox-only variant must enforce none of
SP1, SP2 and SP3: its wrapper copies everything. Until commit `8fc7020` the
benchmark tool did not set the wrapper's switches for the RLBox-only mode, so
run 01 measured RLBox-only with the selective copies. The tool now starts the
RLBox-only mode with `INTERSPEC_SP1=0 INTERSPEC_SP2=0`
(`tools/run_yaml_libyaml_benchmarks.py`, `tools/rlbox_only_baseline.py`).

Two runs have the corrected baseline.

`02-vm-7dafa19-rlbox-only-copies-everything/` is not used. It started while
the machine was still busy with another job (`loadavg-before.txt`: 2.40) and
its spread is the widest of all runs (InterSpec over RLBox-only -3.1%, from
-13.3 to +40.4). Before repeating it I fixed the rule: one more run, started
only when the 1-minute load average is below 0.30, and that run counts
whatever it shows.

`03-vm-16509e7-rlbox-only-copies-everything-idle-start/` is that run and the
evidence for P5. Same command and protocol as run 01, at commit `16509e7`;
load average at the start 0.24 (`loadavg-before.txt`), exit status 0
(`steps.txt`), 60 samples, every timed result equal to the native result,
`run/correctness.json` and `run/security.json` pass. The script first builds
for about 8 minutes and then times for 10.5 minutes; the session ran a few
file copies and git commands during the first minute of the build and nothing
during the timed part. `rlbox-only-policy-report.txt` shows `sp1=0 sp2=0` for
the RLBox-only mode; the mode performs no registry check (`"checks": "0"` in
`run/run-stats.jsonl`).

| | Median | Lowest repetition | Highest repetition |
|---|---:|---:|---:|
| Native, 1,000 parses | 7,348 ms | | |
| RLBox-only | 9,907 ms | | |
| Tracking without check | 9,469 ms | | |
| InterSpec | 9,520 ms | | |
| RLBox-only over native | +33.9% | +0.5% | +53.4% |
| Tracking over RLBox-only | -2.2% | -17.5% | +24.2% |
| InterSpec over tracking | -3.0% | -15.3% | +19.6% |
| InterSpec over RLBox-only | -1.4% | -15.2% | +10.9% |
| InterSpec over native | +35.2% | -11.9% | +50.5% |

Reading. InterSpec over RLBox-only is -1.4% with a range from -15.2% to
+10.9%: no cost that this machine can resolve, and not a speed-up. The spread
between repetitions is wide for this workload in every run (a sample is one
process that runs for 7 to 11 seconds on a shared virtual CPU), also when the
machine was idle at the start. P6 measures the same boundary with interleaved
slices and finds every policy within -0.9% and -0.7% of the configuration with
all policies off.

The rest of this file describes run 01 (RLBox-only with selective copies).

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
