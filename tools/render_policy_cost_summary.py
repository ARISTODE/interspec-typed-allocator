#!/usr/bin/env python3
"""One row per workload from per-policy timing runs (tracker item P6).

Usage: render_policy_cost_summary.py DIR...
DIR is an output directory of tools/benchmark_policy_cost.py or of
tools/benchmark_ports.py --mode policies. Prints a Markdown table: cost of each
policy alone and of all together against the same binary with all policies
off, and of all on and all off against the RLBox-only binary; median (smallest
to largest) of the paired ratios. Aggregation as in render_timing_tables.py.
"""
import csv, json, statistics, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_timing_tables import paired, percent
cols = ["interspec-sp1", "interspec-sp2", "interspec-sp3", "interspec-all-on"]
print("| Boundary, workload | SP1 alone | SP2 alone | SP3 alone | All on | All on, against RLBox-only | All off, against RLBox-only |")
print("|---|---:|---:|---:|---:|---:|---:|")
for d in map(Path, sys.argv[1:]):
    run = json.loads((d / "run.json").read_text())
    rows = list(csv.DictReader((d / "samples.csv").open()))
    if "workloads" in run:
        higher = run["unit"].endswith("_per_s")
        groups = [(w, [r for r in rows if r["workload"] == w], "value") for w in run["workloads"]]
    else:
        higher = False
        groups = [(run["harness_entry"], rows, "elapsed_ns")]
    for name, subset, field in groups:
        sl = {}
        for r in subset:
            sl.setdefault((int(r["repetition"]), r["configuration"]), []).append(float(r[field]))
        by = {k: (statistics.mean(v) if higher else sum(v)) for k, v in sl.items()}
        reps = sorted({k[0] for k in by})
        assert len(reps) == 15
        cells = [percent(paired(by, c, "interspec-all-off", reps, higher)) if (reps[0], c) in by else "no such policy" for c in cols]
        cells.append(percent(paired(by, "interspec-all-on", "rlbox-only", reps, higher)))
        cells.append(percent(paired(by, "interspec-all-off", "rlbox-only", reps, higher)))
        print(f"| {run['boundary']}, {name} | " + " | ".join(cells) + " |")
