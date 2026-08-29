#!/usr/bin/env python3

import argparse
import csv
import statistics
from pathlib import Path


def read_run(path):
    result = {}
    with Path(path).open(newline="") as handle:
        for row in csv.DictReader(handle):
            key = (row["metric"], int(row["population"]), int(row["threads"]))
            if key in result:
                raise ValueError(f"duplicate metric in {path}: {key}")
            operations = int(row["operations"])
            total_ns = int(row["total_ns"])
            if operations <= 0 or total_ns <= 0:
                raise ValueError(f"invalid timing row in {path}: {key}")
            result[key] = (operations, total_ns / operations)
    if not result:
        raise ValueError(f"no runtime rows in {path}")
    return result


def aggregate(paths):
    runs = [read_run(path) for path in paths]
    expected = set(runs[0])
    for index, run in enumerate(runs[1:], start=2):
        if set(run) != expected:
            missing = sorted(expected - set(run))
            extra = sorted(set(run) - expected)
            raise ValueError(
                f"runtime run {index} metric set mismatch; missing={missing}, extra={extra}"
            )

    rows = []
    for key in sorted(expected):
        metric, population, threads = key
        operation_counts = {run[key][0] for run in runs}
        if len(operation_counts) != 1:
            raise ValueError(f"operation count mismatch for {key}: {sorted(operation_counts)}")
        operations = operation_counts.pop()
        samples = [run[key][1] for run in runs]
        median = statistics.median(samples)
        total_ns = max(1, int(round(median * operations)))
        rows.append({
            "metric": metric,
            "population": population,
            "threads": threads,
            "operations": operations,
            "total_ns": total_ns,
            "ns_per_op": f"{median:.6f}",
            "ops_per_sec": f"{(1e9 / median):.0f}",
            "samples": len(samples),
            "min_ns_per_op": f"{min(samples):.6f}",
            "max_ns_per_op": f"{max(samples):.6f}",
        })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("inputs", nargs="+")
    args = parser.parse_args()
    if len(args.inputs) < 3:
        raise SystemExit("P8 runtime aggregation requires at least three repetitions")

    rows = aggregate(args.inputs)
    fields = list(rows[0].keys())
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
