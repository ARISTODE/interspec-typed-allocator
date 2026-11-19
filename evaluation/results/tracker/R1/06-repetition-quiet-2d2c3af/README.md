# Repetition of the slow-host steps of run 05, with a speed check before each step

Run 05 (`../05-campaign-577528c/`) measured its application steps while the
host was slow. This run repeats those steps once, with the same commands and
the same sources, after the container had been restarted on a new boot. The
plan and its criterion were fixed in the tracker Log on 2026-11-18 before the
run; both runs are kept.

- Machine: Claude Code cloud VM (KVM guest, 4 vCPUs, Intel Xeon 2.10 GHz,
  16 GB, Ubuntu 24.04, GCC 13.3), boot of 2026-11-18 15:18 PT.
- Time: 2026-11-18 15:21 PT to 2026-11-19 00:22 PT. Driver `campaign3b.sh`
  (and `camp3b-p2.sh`), log `campaign3b.log`, steps in `steps.txt`: 16 steps
  run, all with exit status 0, none repeated. The steps marked "not repeated"
  are those of run 05 that were not affected (port builds, `p7/`, `instr/`,
  seven of the eight `p6-ports/`, memory).
- Commit `2d2c3af`. Its `include/`, `integration/`, `tools/` and `scripts/`
  are those of `577528c` plus `tools/machine_quiet_check.py`. rsync, yaml and
  memcached were built again by their scripts; the port binaries and the
  nginx build are those of run 05. All pass the alignment check
  (`align-*.txt`).
- Speed check (`quiet_gate.sh`, `tools/machine_quiet_check.py`): before each
  step, and before each of the six memcached blocks, 10 runs of the yaml
  RLBox-only binary of `69cc6e1` (fastest known time 0.116 s). The step starts
  when the median is at most 0.128 s and at most one run is above 0.145 s;
  otherwise the check is repeated every 3 minutes. The same check is recorded
  after the step (`*.quiet-before.txt`, `*.quiet-after.txt`).

## What the speed checks say

The machine was quiet at the start of every step, by construction. It was not
quiet throughout: 22 checks before steps failed and were waited out (up to 4
in a row, before `p4`), and the check right after a step failed for 10 of 21
steps and blocks (`micro/ext`, three of the four `micro/p8-*`, `p4`, `p5`,
memcached blocks 1 and 6, `p6-apps/rsync`, `p6-apps/memcached`), with medians
of 0.116 to 0.160 s. So the host still slows down for minutes at a time. The
difference to run 05 is the size: the yaml slices take 10.7 ms per parse here,
against 16.4 ms in run 05 and 10.9 ms in the quiet test of
`../../R3/02-code-placement/3-aligned/`.

`steps.txt` also records a hold of 4.5 minutes between `p2` and
`p6-apps/rsync` (the driver was stopped for a build of the paper and released
after a passed check).

## Complete applications, InterSpec against RLBox-only

15 repetitions; median, smallest and largest paired ratio; positive means
InterSpec takes more time per operation.

| Application, workload | Native | RLBox-only | InterSpec | Overhead | Run 05 |
|---|---:|---:|---:|---|---|
| memcached, 1 client, 1:1 GET/SET (Kops/s) | 221.2 | 217.4 | 217.7 | -0.1% (-4.3 to +10.2) | +0.4% (-6.8 to +5.2) |
| memcached, 8 clients, 1:1 GET/SET (Kops/s) | 782.3 | 760.8 | 758.0 | +0.2% (-6.6 to +7.2) | +0.2% (-8.3 to +9.5) |
| memcached, read-heavy, 1 KiB values (Kops/s) | 1,100.0 | 1,025.9 | 1,017.3 | +0.8% (-2.3 to +5.9) | +0.6% (-4.6 to +8.2) |
| memcached, write-heavy (Kops/s) | 595.8 | 580.4 | 578.4 | +0.6% (-3.5 to +2.9) | +3.1% (-3.4 to +14.5) |
| memcached, 1 client, log watcher (Kops/s) | 29.9 | 29.5 | 29.1 | +1.7% (-7.9 to +6.7) | +3.4% (-5.7 to +10.7) |
| memcached, 2 clients, log watcher (Kops/s) | 98.9 | 100.9 | 99.8 | +1.1% (-3.8 to +9.2) | +3.7% (-2.7 to +9.2) |
| nginx/libpcre, 4 threads (Kreq/s) | 86.2 | 72.1 | 71.0 | +1.3% (-5.5 to +7.3) | -0.5% (-8.6 to +9.3) |
| nginx/libpcre, 8 threads (Kreq/s) | 81.6 | 67.3 | 66.0 | +1.8% (-6.1 to +5.4) | +0.5% (-24.4 to +20.4) |
| rsync/popt, 194 MiB file sync (s) | 1.344 | 1.325 | 1.334 | +0.8% (-2.2 to +2.8) | -0.2% (-6.2 to +8.9) |
| rsync/popt, option parsing (ms) | 1.243 | 1.990 | 2.030 | +2.0% (-7.4 to +17.5) | +4.9% (-13.3 to +24.7) |
| yaml/libyaml, 1 MiB document (ms per parse) | 8.49 | 10.70 | 10.43 | -1.3% (-6.5 to +2.9) | +0.5% (-2.6 to +5.1) |

- Every range includes zero, as in run 05, and all ranges but three are
  narrower.
- memcached with 2 clients and a log watcher: InterSpec is slower in 13 of the
  15 repetitions (10 of 15 with 1 client). With a watcher memcached writes 1.5
  log entries per request through the boundary; without one it writes none
  (`log_worker_written` in `p2/report/all-samples.csv`), so the four loads
  without a watcher do not call the sandboxed library while they serve
  requests.
- RLBox-only against native: nginx 16% to 18% fewer requests (ratio of
  medians), yaml +26.8% (+16.5 to +33.4) per parse, rsync file sync -1.1%.
  Run 05 showed +64% for yaml.

Sources: `p2/report/`, `p3/run/timing/`, `p4/run/`, `r3/yaml-sliced/run/`.
`rendered-with-run-05/` is the output of `tools/render_paper_performance.py`
on a directory that takes these steps from this run and all others from run
05; the paper's tables are made from it.

## Per-policy cost of the applications (`p6-apps/`)

Against the same binary with all policies off, except the last column.

| Application, workload | SP1 alone | SP2 alone | SP3 alone | All on | All on, against RLBox-only |
|---|---|---|---|---|---|
| memcached, 2 clients, log watcher | -0.2% (-2.3 to +6.7) | +0.3% (-3.7 to +3.6) | +0.8% (-2.3 to +5.4) | +1.1% (-1.0 to +5.2) | +1.3% (-1.3 to +5.6) |
| nginx/libpcre, 4 threads | -1.4% (-9.5 to +3.7) | -2.3% (-10.9 to +6.2) | -0.3% (-10.4 to +6.8) | -2.5% (-13.2 to +8.2) | -1.4% (-6.4 to +11.0) |
| rsync/popt, option parsing | +0.4% (-2.2 to +1.3) | -0.4% (-3.9 to +4.8) | -0.2% (-2.6 to +1.0) | -0.3% (-2.0 to +2.0) | +0.9% (-0.8 to +2.9) |
| rsync/popt, file sync | -0.0% (-0.8 to +1.2) | -0.4% (-1.4 to +0.7) | +0.2% (-1.7 to +1.0) | +0.0% (-1.3 to +1.1) | +0.2% (-2.6 to +1.8) |
| yaml/libyaml | no such policy | -0.3% (-4.8 to +6.6) | -1.1% (-5.8 to +4.8) | -0.6% (-7.2 to +4.9) | +0.2% (-5.5 to +4.3) |

`p6-ports/ffmpeg_libvpx/` is the one port step of run 05 that was repeated:
all on +0.3% (-4.1 to +14.6), against RLBox-only +1.7% (-6.5 to +10.3).

## Registry operations (`micro/`)

P8 tool, ns per operation, median (smallest to largest) of 15 runs, CPU 0;
"before" is the registry of `930cb20`.

| Operation | Live objects | Before, single-threaded | After, single-threaded | Before, locked | After, locked |
|---|---:|---|---|---|---|
| Check (`check_live`) | 2 | 6.20 (5.94 to 7.67) | 2.60 (2.50 to 4.42) | 22.27 (21.86 to 25.96) | 22.23 (21.93 to 27.17) |
| Registration (`allocate_from_site`) | 16,384 | 57.15 (54.14 to 73.72) | 27.93 (21.26 to 38.14) | 75.71 (70.63 to 121.24) | 51.51 (50.35 to 69.17) |
| Release (`release`) | 16,384 | 156.02 (152.23 to 170.89) | 6.90 (6.29 to 13.69) | 166.16 (161.32 to 235.38) | 35.23 (33.80 to 44.49) |

Handles (`micro/ext/run/`, single-threaded): resolve 1.5 ns with 2 live
objects and 2.9 ns with 20,000; retire one handle and issue another 7.3 and
8.8 ns. These agree with the stopped run 04 (check 2.58, registration 23.21,
release 7.30 ns); the registration differs most (27.9 against 23.2 ns), and
the check after three of these steps failed, so the registration time is
known to about 5 ns.

## libpng across four builds (`r2/time/`)

One interleaved run of 17 configurations, against the aligned RLBox-only
build of `577528c`: all medians are between -2.6% and +3.3%, except the
RLBox-only binary of `8fc7020` at -5.4% (-11.7 to +3.3). This agrees with
`../../R2/README.md`: that one binary is the fast one.

## Stored form

As in run 05: profiles and per-run directories in `.tar.gz` files, executables
removed and listed in `removed-executables.sha256`.
