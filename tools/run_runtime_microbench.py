#!/usr/bin/env python3
"""Repeat the InterSpec runtime microbenchmark and summarize primitive costs."""
import argparse
import csv
import io
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--binary", type=Path)
    p.add_argument("--repetitions", type=int, default=9)
    p.add_argument("--iterations", type=int, default=1000000)
    p.add_argument("--cpus")
    args = p.parse_args()
    assert args.repetitions >= 3 and args.iterations > 0

    root = Path(__file__).resolve().parents[1]
    args.out.mkdir(parents=True, exist_ok=True)
    binary = args.binary or (args.out / "runtime_microbench")
    if args.binary is None:
        subprocess.run([
            "g++", "-std=c++17", "-O2", "-pthread", "-I", str(root / "include"),
            str(root / "evaluation/runtime_bench.cpp"), "-o", str(binary)
        ], check=True)

    prefix = ["taskset", "-c", args.cpus] if args.cpus else []
    env = dict(os.environ)
    env["INTERSPEC_BENCH_ITERATIONS"] = str(args.iterations)

    # Untimed warm-up to populate code/data paths before repeated measurements.
    subprocess.run(prefix + [str(binary)], env=env, capture_output=True, text=True, check=True)

    raw = []
    for rep in range(args.repetitions):
        result = subprocess.run(
            prefix + [str(binary)], env=env, capture_output=True, text=True, check=True
        )
        for row in csv.DictReader(io.StringIO(result.stdout)):
            raw.append({
                "repetition": rep,
                "metric": row["metric"],
                "population": int(row["population"]),
                "threads": int(row["threads"]),
                "operations": int(row["operations"]),
                "total_ns": int(row["total_ns"]),
                "ns_per_op": float(row["ns_per_op"]),
                "ops_per_sec": float(row["ops_per_sec"]),
            })

    with (args.out / "raw.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(raw[0]))
        writer.writeheader()
        writer.writerows(raw)

    groups = {}
    for row in raw:
        key = (row["metric"], row["population"], row["threads"])
        groups.setdefault(key, []).append(row["ns_per_op"])
    summary = []
    for (metric, population, threads), values in sorted(groups.items()):
        summary.append({
            "metric": metric,
            "population": population,
            "threads": threads,
            "n": len(values),
            "ns_per_op_median": statistics.median(values),
            "ns_per_op_min": min(values),
            "ns_per_op_max": max(values),
        })
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    environment = {
        "host": platform.uname()._asdict(),
        "repetitions": args.repetitions,
        "iterations": args.iterations,
        "cpus": args.cpus,
        "affinity": sorted(os.sched_getaffinity(0)),
        "compiler": subprocess.check_output(["g++", "--version"], text=True).splitlines()[0],
    }
    (args.out / "environment.json").write_text(json.dumps(environment, indent=2) + "\n")

    primary_order = [
        "shared_lock", "metadata_lookup", "type_compare", "bounds_check",
        "check_live", "check_interior", "remaining_bytes",
    ]
    selected = {
        row["metric"]: row for row in summary
        if row["population"] == 2 and row["threads"] == 1 and row["metric"] in primary_order
    }
    lines = [
        "# InterSpec SP3 runtime microbenchmark",
        "",
        "Population 2 is the deployment-representative hot-path case: a normal memcached sandbox has two tracked allocations (the bipbuffer object and its persistent input buffer). Larger populations in summary.json show lookup scaling.",
        "",
        "| Primitive | Median ns/op | Min–max ns/op | What it isolates |",
        "| --- | ---: | ---: | --- |",
    ]
    descriptions = {
        "shared_lock": "shared metadata-lock acquisition/release",
        "metadata_lookup": "ordered allocation lookup and containment test, excluding the lock",
        "type_compare": "expected-type hash equality check",
        "bounds_check": "offset/remaining-byte arithmetic and extent comparison",
        "check_live": "production Runtime::check: lock + lookup + type + bounds",
        "check_interior": "production Runtime::check on an interior pointer",
        "remaining_bytes": "production metadata lookup/type check returning remaining extent",
    }
    for metric in primary_order:
        row = selected.get(metric)
        if not row:
            continue
        lines.append(
            f"| {metric} | {row['ns_per_op_median']:.2f} | "
            f"{row['ns_per_op_min']:.2f}–{row['ns_per_op_max']:.2f} | "
            f"{descriptions[metric]} |"
        )
    for metric in ("allocate_from_site", "release"):
        rows = [r for r in summary if r["metric"] == metric and r["threads"] == 1]
        if rows:
            row = max(rows, key=lambda x: x["population"])
            lines.append(
                f"| {metric} | {row['ns_per_op_median']:.2f} | "
                f"{row['ns_per_op_min']:.2f}–{row['ns_per_op_max']:.2f} | "
                f"{'typed allocation registration on queue setup' if metric == 'allocate_from_site' else 'trusted allocation metadata release'} |"
            )
    lines += [
        "",
        "Primitive rows are measured independently and therefore are not algebraically additive: the production check executes them in one optimized function and shares instruction/data-cache effects. Use check_live as the direct per-check cost; the smaller rows explain where that cost comes from.",
        "",
    ]
    (args.out / "MICROBENCH_TABLE.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
