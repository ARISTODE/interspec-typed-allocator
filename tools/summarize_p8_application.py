#!/usr/bin/env python3

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path

MODES = {"tracked_no_check", "extended_sp3"}


def load(path):
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source))
    required = {"workload", "mode", "repetition", "total_ns"}
    if not rows or set(rows[0]) != required:
        raise ValueError("unexpected or empty P8 application CSV")
    return [{
        "workload": row["workload"],
        "mode": row["mode"],
        "repetition": int(row["repetition"]),
        "total_ns": int(row["total_ns"]),
    } for row in rows]


def summarize(samples):
    by_mode = defaultdict(list)
    pairs = defaultdict(dict)
    for sample in samples:
        if sample["mode"] not in MODES:
            raise ValueError(f"unknown application mode: {sample['mode']}")
        by_mode[(sample["workload"], sample["mode"])].append(sample["total_ns"])
        key = (sample["workload"], sample["repetition"])
        if sample["mode"] in pairs[key]:
            raise ValueError(f"duplicate application pair: {key}")
        pairs[key][sample["mode"]] = sample["total_ns"]

    result = []
    for workload in sorted({sample["workload"] for sample in samples}):
        baseline = by_mode[(workload, "tracked_no_check")]
        extended = by_mode[(workload, "extended_sp3")]
        if not baseline or not extended:
            raise ValueError(f"missing application mode for {workload}")
        overheads = []
        for (name, _), values in pairs.items():
            if name != workload:
                continue
            if set(values) != MODES:
                raise ValueError(f"incomplete application pair for {workload}")
            overheads.append(
                (values["extended_sp3"] / values["tracked_no_check"] - 1.0) * 100.0)
        result.append({
            "workload": workload,
            "repetitions": len(overheads),
            "baseline_median_ms": statistics.median(baseline) / 1e6,
            "extended_median_ms": statistics.median(extended) / 1e6,
            "baseline_mean_ms": statistics.fmean(baseline) / 1e6,
            "extended_mean_ms": statistics.fmean(extended) / 1e6,
            "paired_overhead_median_pct": statistics.median(overheads),
            "paired_overhead_mean_pct": statistics.fmean(overheads),
            "paired_overhead_min_pct": min(overheads),
            "paired_overhead_max_pct": max(overheads),
        })
    return result


def write(path, rows):
    fields = [
        "workload", "repetitions",
        "baseline_median_ms", "extended_median_ms",
        "baseline_mean_ms", "extended_mean_ms",
        "paired_overhead_median_pct", "paired_overhead_mean_pct",
        "paired_overhead_min_pct", "paired_overhead_max_pct",
    ]
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                key: (f"{value:.6f}" if isinstance(value, float) else value)
                for key, value in row.items()
            })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    write(Path(args.output), summarize(load(Path(args.input))))


if __name__ == "__main__":
    main()
