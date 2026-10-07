#!/usr/bin/env python3

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path

MODES = ("native", "rlbox_only", "tracked_no_check", "extended_sp3")
MODE_SET = set(MODES)

PREFIX = {
    "native": "native",
    "rlbox_only": "rlbox",
    "tracked_no_check": "tracked",
    "extended_sp3": "extended",
}


def load(path):
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source))
    required = {"workload", "mode", "repetition", "total_ns"}
    if not rows or set(rows[0]) != required:
        raise ValueError("unexpected or empty P11 report CSV")
    return [{
        "workload": row["workload"],
        "mode": row["mode"],
        "repetition": int(row["repetition"]),
        "total_ns": int(row["total_ns"]),
    } for row in rows]


def overhead(numerator, denominator):
    if denominator <= 0:
        raise ValueError("non-positive timing sample")
    return (numerator / denominator - 1.0) * 100.0


def summarize(samples):
    by_mode = defaultdict(list)
    groups = defaultdict(dict)
    for sample in samples:
        if sample["mode"] not in MODE_SET:
            raise ValueError(f"unknown P11 report mode: {sample['mode']}")
        by_mode[(sample["workload"], sample["mode"])].append(sample["total_ns"])
        group_key = (sample["workload"], sample["repetition"])
        if sample["mode"] in groups[group_key]:
            raise ValueError(f"duplicate sample: {group_key} {sample['mode']}")
        groups[group_key][sample["mode"]] = sample["total_ns"]

    result = []
    workloads = sorted({sample["workload"] for sample in samples})
    for workload in workloads:
        samples_by_mode = {mode: by_mode[(workload, mode)] for mode in MODES}
        if any(not values for values in samples_by_mode.values()):
            raise ValueError(f"missing mode for {workload}")

        metrics = {
            "isolation_overhead": [],
            "tracking_overhead": [],
            "validation_overhead": [],
            "total_overhead": [],
            "interspec_vs_native": [],
        }
        repetitions = []
        for (name, repetition), values in sorted(groups.items()):
            if name != workload:
                continue
            if set(values) != MODE_SET:
                raise ValueError(f"incomplete four-way group for {workload} repetition {repetition}")
            repetitions.append(repetition)
            metrics["isolation_overhead"].append(overhead(values["rlbox_only"], values["native"]))
            metrics["tracking_overhead"].append(overhead(values["tracked_no_check"], values["rlbox_only"]))
            metrics["validation_overhead"].append(overhead(values["extended_sp3"], values["tracked_no_check"]))
            metrics["total_overhead"].append(overhead(values["extended_sp3"], values["rlbox_only"]))
            metrics["interspec_vs_native"].append(overhead(values["extended_sp3"], values["native"]))

        row = {"workload": workload, "repetitions": len(repetitions)}
        for mode in MODES:
            values = samples_by_mode[mode]
            prefix = PREFIX[mode]
            row[f"{prefix}_median_ms"] = statistics.median(values) / 1e6
            row[f"{prefix}_mean_ms"] = statistics.fmean(values) / 1e6

        for prefix, values in metrics.items():
            row[f"{prefix}_median_pct"] = statistics.median(values)
            row[f"{prefix}_mean_pct"] = statistics.fmean(values)
            row[f"{prefix}_min_pct"] = min(values)
            row[f"{prefix}_max_pct"] = max(values)
        result.append(row)
    return result


def write(path, rows):
    fields = [
        "workload", "repetitions",
        "native_median_ms", "rlbox_median_ms", "tracked_median_ms", "extended_median_ms",
        "native_mean_ms", "rlbox_mean_ms", "tracked_mean_ms", "extended_mean_ms",
    ]
    for prefix in (
        "isolation_overhead", "tracking_overhead", "validation_overhead",
        "total_overhead", "interspec_vs_native"
    ):
        fields += [
            f"{prefix}_median_pct", f"{prefix}_mean_pct",
            f"{prefix}_min_pct", f"{prefix}_max_pct",
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
