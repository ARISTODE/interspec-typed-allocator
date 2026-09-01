#!/usr/bin/env python3

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path

MODES = ("rlbox_only", "tracked_no_check", "extended_sp3")
MODE_SET = set(MODES)


def load(path):
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source))
    required = {"workload", "mode", "repetition", "total_ns"}
    if not rows or set(rows[0]) != required:
        raise ValueError("unexpected or empty P9a application CSV")
    return [{
        "workload": row["workload"],
        "mode": row["mode"],
        "repetition": int(row["repetition"]),
        "total_ns": int(row["total_ns"]),
    } for row in rows]


def overhead(numerator, denominator):
    if denominator <= 0:
        raise ValueError("non-positive P9a timing sample")
    return (numerator / denominator - 1.0) * 100.0


def summarize(samples):
    by_mode = defaultdict(list)
    triples = defaultdict(dict)
    for sample in samples:
        if sample["mode"] not in MODE_SET:
            raise ValueError(f"unknown P9a application mode: {sample['mode']}")
        key = (sample["workload"], sample["mode"])
        by_mode[key].append(sample["total_ns"])
        triple_key = (sample["workload"], sample["repetition"])
        if sample["mode"] in triples[triple_key]:
            raise ValueError(f"duplicate P9a sample: {triple_key} {sample['mode']}")
        triples[triple_key][sample["mode"]] = sample["total_ns"]

    result = []
    workloads = sorted({sample["workload"] for sample in samples})
    for workload in workloads:
        samples_by_mode = {mode: by_mode[(workload, mode)] for mode in MODES}
        if any(not values for values in samples_by_mode.values()):
            raise ValueError(f"missing P9a mode for {workload}")

        tracking_overheads = []
        validation_overheads = []
        total_overheads = []
        repetitions = []
        for (name, repetition), values in sorted(triples.items()):
            if name != workload:
                continue
            if set(values) != MODE_SET:
                raise ValueError(f"incomplete P9a triple for {workload} repetition {repetition}")
            repetitions.append(repetition)
            tracking_overheads.append(overhead(values["tracked_no_check"], values["rlbox_only"]))
            validation_overheads.append(overhead(values["extended_sp3"], values["tracked_no_check"]))
            total_overheads.append(overhead(values["extended_sp3"], values["rlbox_only"]))

        if not repetitions:
            raise ValueError(f"no complete P9a triples for {workload}")
        if len(set(repetitions)) != len(repetitions):
            raise ValueError(f"duplicate P9a repetitions for {workload}")

        row = {
            "workload": workload,
            "repetitions": len(repetitions),
        }
        for mode in MODES:
            values = samples_by_mode[mode]
            prefix = {
                "rlbox_only": "rlbox",
                "tracked_no_check": "tracked",
                "extended_sp3": "extended",
            }[mode]
            row[f"{prefix}_median_ms"] = statistics.median(values) / 1e6
            row[f"{prefix}_mean_ms"] = statistics.fmean(values) / 1e6

        for prefix, values in (
            ("tracking_overhead", tracking_overheads),
            ("validation_overhead", validation_overheads),
            ("total_overhead", total_overheads),
        ):
            row[f"{prefix}_median_pct"] = statistics.median(values)
            row[f"{prefix}_mean_pct"] = statistics.fmean(values)
            row[f"{prefix}_min_pct"] = min(values)
            row[f"{prefix}_max_pct"] = max(values)
        result.append(row)
    return result


def write(path, rows):
    fields = [
        "workload", "repetitions",
        "rlbox_median_ms", "tracked_median_ms", "extended_median_ms",
        "rlbox_mean_ms", "tracked_mean_ms", "extended_mean_ms",
        "tracking_overhead_median_pct", "tracking_overhead_mean_pct",
        "tracking_overhead_min_pct", "tracking_overhead_max_pct",
        "validation_overhead_median_pct", "validation_overhead_mean_pct",
        "validation_overhead_min_pct", "validation_overhead_max_pct",
        "total_overhead_median_pct", "total_overhead_mean_pct",
        "total_overhead_min_pct", "total_overhead_max_pct",
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
