#!/usr/bin/env python3
"""Paired ratios from a samples file with columns workload,mode,repetition,total_ns.
usage: paired.py CSV WORKLOAD"""
import csv, statistics, collections, sys
path, wl = sys.argv[1], sys.argv[2]
by = collections.defaultdict(dict)
for r in csv.DictReader(open(path)):
    if r["workload"] == wl:
        by[int(r["repetition"])][r["mode"]] = float(r["total_ns"])
reps = sorted(by)
print(f"{wl}: {len(reps)} repetitions")
print("| | Median | Lowest repetition | Highest repetition |\n|---|---:|---:|---:|")
for m in ("native", "rlbox_only", "tracked_no_check", "extended_sp3"):
    print(f"| {m} | {statistics.median(by[i][m] for i in reps)/1e6:,.0f} ms | | |")
for a, b in (("rlbox_only", "native"), ("tracked_no_check", "rlbox_only"), ("extended_sp3", "tracked_no_check"),
             ("extended_sp3", "rlbox_only"), ("extended_sp3", "native")):
    x = [by[i][a] / by[i][b] - 1 for i in reps]
    print(f"| {a} over {b} | {100*statistics.median(x):+.1f}% | {100*min(x):+.1f}% | {100*max(x):+.1f}% |")
