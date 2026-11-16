# P2: memcached/bipbuffer timing

Tracker item P2 in `EVAL_TRACKER.md`. Measured on the Claude Code cloud VM
described in `evaluation/results/tracker/P1/`.

| Directory | Result |
|---|---|
| `01-vm-5037e6d-failed-driver-setup/` | Not a measurement. The driver (`driver.sh`) built memcached under a scratch directory and then ran the correctness gate without `--work`, so the gate looked for the binaries under its default `/tmp/interspec-memcached-deployment` and all 50 cases failed with "No such file or directory" within milliseconds. No timing was started. An error in the driver, not in memcached. |
| `02-vm-5994983-interrupted-by-restart/` | Not a complete measurement. With the work directory passed correctly the build and the correctness gate passed (50 of 50) and the timed matrix started (six scenarios, four variants, 15 repetitions of 30 s). The session's machine restarted after 206 of the 360 samples, during the fourth scenario, and the run died with it. The samples that exist are in `matrix.stdout.txt` and `matrix/`; they are kept and are not used for any number. The run was launched detached while the session was idle, and an idle session's machine can be reclaimed. |
| `03-vm-5994983-checkpointed-complete/` | The measurement with the old baseline (RLBox-only with selective copies, see the correction below); not the evidence any more. Six scenarios, four variants, 15 paired repetitions, 30 s windows after a 5 s warm-up: 360 samples, none excluded. `tools/verify_memcached_matrix.py` passes on it (`verifier.stdout.txt`). |
| `04-vm-02631e0-verifier-fails-on-build-record/` | Not the evidence. First run after the correction of 2026-11-15 (below), with the RLBox-only server started with SP1 and SP2 off (`server-environment-observed.txt`). Gate 50 of 50; all six scenarios measured, 360 samples, every sample valid (`PAIRED_RATIOS.md`). `tools/verify_memcached_matrix.py` exits 1 with "uncommitted build source" (`verifier.stdout.txt`): the build record says the source tree was not clean when the build ended. The cause is mine: while the build ran I edited three README files and `tools/measure_memory_cost.py` in the same checkout; they were committed 25 s after the build ended as `4ecfe97`, whose parent is the build's commit `02631e0`. None of the four files is an input of the build, but the verifier has to pass on the raw output, and it does not. Also in this run: the session's machine restarted during the sixth block (watch_moderate, 53 of 60 samples written, kept in `interrupted-watch_moderate/`); the block was reconciled and replaced once, as the plan allows (`ledger.json`, `blocks/reconcile.stdout.txt`). InterSpec against RLBox-only in this run: median loss 0.2% to 2.6% per scenario, every range includes zero. |
| `05-vm-8311683-rlbox-only-copies-everything/` | The measurement that counts since the correction of 2026-11-15. Built from a clean tree at `8311683` (`git-status-before-build.txt` and `git-status-after-build.txt` are empty, `build-manifest.json` says `"project_dirty": false`), gate 50 of 50, six scenarios, four variants, 15 paired repetitions, 30 s windows: 360 samples, none excluded, no block interrupted. `tools/verify_memcached_matrix.py` passes (`verifier.stdout.txt`, exit 0 in `steps.txt`). The RLBox-only server ran with SP1 and SP2 off (`server-environment-observed.txt`, read from the running servers during block 3). |

## The run that counts (`05-vm-8311683-rlbox-only-copies-everything/`)

Same protocol as run 03 (below): checkpoint mode, one scenario per block, the
plan fixes the SHA-256 of the binaries, the client and the tools; server on
CPUs 0-1, client on CPUs 2-3. The driver (`driver.sh`) refuses to build from a
tree with uncommitted changes and stops unless the build record says clean,
which is what run 04 lacked. The blocks ran back to back from 18:21 to 22:00
PT on 2026-11-15; `blocks/loadavg-before-block-N.txt` therefore shows the load
of the block before (the servers and the client use all four CPUs), not a
foreign load. During the run the session only read files, edited the tracker
and committed it (`16509e7`); no build or other measurement ran.

Loss of throughput, median of the 15 paired ratios (smallest to largest),
from `PAIRED_RATIOS.md` (computed by `paired.py` from `report/all-samples.csv`):

| Scenario | Median Kops/s: native, RLBox-only, tracking without check, InterSpec | RLBox-only against native | InterSpec against native | Tracking against RLBox-only | InterSpec against RLBox-only |
|---|---|---:|---:|---:|---:|
| balanced_1c | 184.6, 179.1, 181.7, 178.5 | +3.20% (-1.46 to +8.34) | +2.41% (-3.83 to +6.03) | -1.31% (-9.56 to +3.70) | -0.90% (-6.79 to +5.98) |
| balanced_8c | 645.4, 610.1, 620.3, 609.2 | +4.58% (-3.84 to +10.42) | +4.25% (-2.03 to +12.82) | -0.13% (-4.41 to +3.96) | +1.91% (-5.12 to +5.95) |
| read_heavy_1k | 947.9, 887.4, 889.3, 879.2 | +6.32% (+1.30 to +10.56) | +7.75% (+3.67 to +12.29) | +0.23% (-5.97 to +6.47) | +1.94% (-6.68 to +5.00) |
| write_heavy | 488.8, 467.2, 474.6, 472.8 | +3.61% (-6.74 to +10.45) | +3.22% (-5.75 to +7.72) | +0.27% (-9.02 to +3.46) | +0.30% (-8.69 to +4.17) |
| watch_light | 24.9, 24.8, 24.6, 24.7 | -0.12% (-10.32 to +5.26) | +1.68% (-6.67 to +4.13) | +0.56% (-4.46 to +5.59) | +0.28% (-4.90 to +4.48) |
| watch_moderate | 87.1, 88.0, 86.4, 85.1 | +1.05% (-3.21 to +6.49) | +3.02% (-2.12 to +6.77) | +1.22% (-6.21 to +7.52) | +1.29% (-4.70 to +5.84) |

Reading. InterSpec against a wrapper that copies everything: medians between
-0.9% and +1.9%, and the range includes zero in every scenario. This machine
cannot resolve a cost of the three policies on memcached/bipbuffer. Run 04,
the same measurement with the rejected build record, gave +0.2% to +2.6%, and
run 03 with the old baseline +0.3% to +1.7%: the copies that SP1 and SP2
remove are too small a part of a memcached request to show. The absolute
throughput of this run is 5 to 12% below run 04 in five of the six scenarios,
for all four variants alike; the paired ratios are what the item uses. The
verifier keeps `publication_ready` false because the host is not controlled.

## Correction of 2026-11-15: what RLBox-only means

JH pointed out on 2026-11-15 that the RLBox-only variant must enforce none of
SP1, SP2 and SP3: its wrapper copies every field to U and every field back to
T. The wrapper's switches `INTERSPEC_SP1` and `INTERSPEC_SP2` are on when
unset, and the timing tools did not set them for the RLBox-only variant, so in
runs 01 to 03 the RLBox-only server made the same selective copies as InterSpec
and differed from it only by the object registry. `tools/benchmark_memcached.py`
now starts the RLBox-only server with both switches off (commit `8fc7020`), and
the checkpoint mode carries `tools/rlbox_only_baseline.py` in its frozen copy
of the tools (`02631e0`). Columns that do not involve RLBox-only are
unaffected. Run 03 below is therefore a measurement of InterSpec against a
wrapper with selective copies.

## The complete run (`03-vm-5994983-checkpointed-complete/`)

How it was run. The matrix tool's checkpoint mode, one scenario per block, so
that a machine restart costs at most one scenario. The plan (`plan.json`) fixes
the SHA-256 of the four server binaries, the client and the tools before the
first block; every block checks them. The binaries were built from commit
`5994983` (`build-manifest.json`), and the correctness gate passed on the same
binaries (50 of 50, `correctness.json`). Server on CPUs 0-1, client on CPUs
2-3. No block was interrupted and no scenario was replaced (`ledger.json`). The
machine restarted once between block 1 and block 2; the state directory
survived and the hashes were checked again. `environment/` holds the machine
description recorded at the start of each block, `blocks/` the output of each
invocation.

Every one of the 360 timed runs had no client error, no GET miss, no logger
loss and no LRU loss, and ran for at least 30 s.

Result (`PAIRED_RATIOS.md`, computed from `report/all-samples.csv`; the tool's
own table is `report/FINAL_TABLE.md`). Loss of throughput, median of the 15
paired ratios, smallest and largest in brackets:

| Scenario | InterSpec against RLBox-only | InterSpec against native | RLBox-only against native |
|---|---:|---:|---:|
| balanced_1c | +0.54% (-5.24 to +4.73) | +1.40% (-10.76 to +10.49) | +1.24% (-11.38 to +10.01) |
| balanced_8c | +0.28% (-8.39 to +8.01) | +3.78% (-2.08 to +6.91) | +2.48% (-3.75 to +12.76) |
| read_heavy_1k | +1.66% (-5.40 to +8.34) | +7.43% (+3.72 to +12.02) | +5.68% (+0.55 to +10.54) |
| write_heavy | +0.27% (-6.92 to +7.72) | +2.75% (-3.94 to +9.49) | +2.39% (-3.02 to +9.04) |
| watch_light | +1.13% (-7.00 to +10.33) | -0.27% (-4.83 to +9.01) | -0.85% (-6.65 to +6.15) |
| watch_moderate | +1.03% (-8.12 to +5.83) | +3.90% (-12.05 to +12.53) | +2.72% (-6.07 to +12.60) |

What the numbers support. The median cost of InterSpec over RLBox-only is
between 0.3% and 1.7% in every scenario. The range of the paired ratios is
about ten times larger than that and contains zero in every scenario, so on
this machine the cost of InterSpec over RLBox-only cannot be told apart from
run-to-run variation. Only `read_heavy_1k` shows a cost against native whose
whole range is above zero. The machine is a shared virtual machine with four
virtual CPUs (see P1); the server and the client share it.

The verifier prints "Publication readiness remains false": the tool sets that
flag for any run whose host it cannot show to be controlled. It is a statement
about the host, and JH decided on 2026-11-13 that the numbers come from this
virtual machine.
