#!/usr/bin/env python3

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path


REQUIRED_MODES = {"tracked_no_check", "extended_sp3"}


def load_samples(path):
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source))
    required = {"boundary", "mode", "repetition", "iterations", "total_ns", "ns_per_op"}
    if not rows or set(rows[0]) != required:
        raise ValueError("unexpected or empty P8 performance CSV")
    parsed = []
    for row in rows:
        parsed.append({
            "boundary": row["boundary"],
            "mode": row["mode"],
            "repetition": int(row["repetition"]),
            "iterations": int(row["iterations"]),
            "total_ns": int(row["total_ns"]),
            "ns_per_op": float(row["ns_per_op"]),
        })
    return parsed


def summarize(samples):
    grouped = defaultdict(list)
    paired = defaultdict(dict)
    for sample in samples:
        if sample["mode"] not in REQUIRED_MODES:
            raise ValueError(f"unknown performance mode: {sample['mode']}")
        grouped[(sample["boundary"], sample["mode"])].append(sample["ns_per_op"])
        key = (sample["boundary"], sample["repetition"])
        if sample["mode"] in paired[key]:
            raise ValueError(f"duplicate paired sample: {key} {sample['mode']}")
        paired[key][sample["mode"]] = sample["ns_per_op"]

    boundaries = sorted({sample["boundary"] for sample in samples})
    rows = []
    for boundary in boundaries:
        modes = {mode for (name, mode) in grouped if name == boundary}
        if modes != REQUIRED_MODES:
            raise ValueError(f"missing paired mode for {boundary}: {modes}")
        baseline_values = grouped[(boundary, "tracked_no_check")]
        extended_values = grouped[(boundary, "extended_sp3")]
        pair_overheads = []
        for (name, _rep), values in paired.items():
            if name != boundary:
                continue
            if set(values) != REQUIRED_MODES:
                raise ValueError(f"incomplete repetition for {boundary}")
            baseline = values["tracked_no_check"]
            extended = values["extended_sp3"]
            pair_overheads.append((extended / baseline - 1.0) * 100.0)
        rows.append({
            "boundary": boundary,
            "repetitions": len(pair_overheads),
            "baseline_median_ns": statistics.median(baseline_values),
            "extended_median_ns": statistics.median(extended_values),
            "baseline_mean_ns": statistics.fmean(baseline_values),
            "extended_mean_ns": statistics.fmean(extended_values),
            "paired_overhead_median_pct": statistics.median(pair_overheads),
            "paired_overhead_mean_pct": statistics.fmean(pair_overheads),
            "paired_overhead_min_pct": min(pair_overheads),
            "paired_overhead_max_pct": max(pair_overheads),
        })
    return rows


def write_summary(path, rows):
    fields = [
        "boundary", "repetitions",
        "baseline_median_ns", "extended_median_ns",
        "baseline_mean_ns", "extended_mean_ns",
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
    rows = summarize(load_samples(Path(args.input)))
    write_summary(Path(args.output), rows)


if __name__ == "__main__":
    main()
