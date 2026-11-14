# P2: memcached/bipbuffer timing

Tracker item P2 in `EVAL_TRACKER.md`. Measured on the Claude Code cloud VM
described in `evaluation/results/tracker/P1/`.

| Directory | Result |
|---|---|
| `01-vm-5037e6d-failed-driver-setup/` | Not a measurement. The driver (`driver.sh`) built memcached under a scratch directory and then ran the correctness gate without `--work`, so the gate looked for the binaries under its default `/tmp/interspec-memcached-deployment` and all 50 cases failed with "No such file or directory" within milliseconds. No timing was started. An error in the driver, not in memcached. |
| `02-vm-5994983-interrupted-by-restart/` | Not a complete measurement. With the work directory passed correctly the build and the correctness gate passed (50 of 50) and the timed matrix started (six scenarios, four variants, 15 repetitions of 30 s). The session's machine restarted after 206 of the 360 samples, during the fourth scenario, and the run died with it. The samples that exist are in `matrix.stdout.txt` and `matrix/`; they are kept and are not used for any number. The run was launched detached while the session was idle, and an idle session's machine can be reclaimed. |
| `03-vm-5994983-checkpointed-complete/` | The measurement. Six scenarios, four variants, 15 paired repetitions, 30 s windows after a 5 s warm-up: 360 samples, none excluded. `tools/verify_memcached_matrix.py` passes on it (`verifier.stdout.txt`). |

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
