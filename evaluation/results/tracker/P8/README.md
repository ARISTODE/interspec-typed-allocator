# P8: cost of one registry check

Tracker item P8 in `EVAL_TRACKER.md`. Measured on the Claude Code cloud VM
described in `evaluation/results/tracker/P1/` (KVM guest, 4 virtual CPUs, not a
dedicated host), pinned to CPU 0, on 2026-11-14 with nothing else running in
the session (`loadavg-before.txt` shows the decaying average of an analysis
that had been stopped a few minutes earlier).

`01-vm-f3dc8a5/` is the output of

    python3 tools/run_runtime_microbench.py --out <dir> --repetitions 15 --cpus 0

at commit `f3dc8a5`, which includes the allocator change of 2026-11-14
(`evaluation/results/tracker/A1/`): 39 configurations, 15 repetitions, one
million iterations each, 585 samples (`raw.csv`, per-repetition stdout and
stderr). `tools/verify_runtime_microbench.py` passes on it
(`verification.json`). `MICROBENCH_TABLE.md` is the tool's table.

Medians with two live allocations: one `Runtime::check` 22.5 ns
(22.1 to 27.3), of which the shared lock alone is 22.3 ns and the lookup 5.6 ns
when measured separately; a typed allocation 78 ns and a release 160 ns with
16,384 live allocations. The tool's own caveats apply (rows are not additive;
ranges are observed minima and maxima).
