#!/usr/bin/env python3
"""Run the publication-oriented memcached workload matrix and render the main 3-way table."""
import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys

SCENARIOS = [
    {
        "name": "balanced_1c",
        "mode": "cache_only",
        "clients": 1,
        "pipeline": 10,
        "value_bytes": 256,
        "keys": 10000,
        "get_percent": 50,
        "purpose": "low-concurrency balanced cache traffic; preserves the paper's 1-client, 1:1, pipeline-10 shape",
    },
    {
        "name": "balanced_8c",
        "mode": "cache_only",
        "clients": 8,
        "pipeline": 10,
        "value_bytes": 256,
        "keys": 10000,
        "get_percent": 50,
        "purpose": "higher-concurrency balanced cache traffic; preserves the paper's 8-client, 1:1, pipeline-10 shape",
    },
    {
        "name": "read_heavy_1k",
        "mode": "cache_only",
        "clients": 8,
        "pipeline": 16,
        "value_bytes": 1024,
        "keys": 10000,
        "get_percent": 95,
        "purpose": "read-mostly object-cache scenario with 1 KiB values",
    },
    {
        "name": "write_heavy",
        "mode": "cache_only",
        "clients": 8,
        "pipeline": 8,
        "value_bytes": 256,
        "keys": 10000,
        "get_percent": 10,
        "purpose": "mutation-heavy scenario stressing SET paths and asynchronous LRU activity",
    },
    {
        "name": "watch_light",
        "mode": "watch_active",
        "clients": 1,
        "pipeline": 1,
        "value_bytes": 256,
        "keys": 10000,
        "get_percent": 50,
        "purpose": "lossless active-observability scenario with a live watcher",
    },
    {
        "name": "watch_moderate",
        "mode": "watch_active",
        "clients": 2,
        "pipeline": 2,
        "value_bytes": 256,
        "keys": 10000,
        "get_percent": 50,
        "purpose": "moderate active-observability load with worker and watcher queues exercised continuously",
    },
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--work", type=Path, default=Path("/tmp/interspec-memcached-deployment"))
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--correctness-summary", type=Path, required=True)
    p.add_argument("--preset", choices=("smoke", "paper"), default="smoke")
    p.add_argument("--seconds", type=float)
    p.add_argument("--warmup", type=float)
    p.add_argument("--repetitions", type=int)
    p.add_argument("--server-cpus")
    p.add_argument("--client-cpus")
    p.add_argument("--include-tracking", action="store_true",
                   help="also collect tracked-no-check for decomposition; main table remains native/RLBox/InterSpec")
    p.add_argument("--label", default="memcached_overhead_matrix")
    args = p.parse_args()

    defaults = {
        "smoke": {"seconds": 1.0, "warmup": 0.3, "repetitions": 3},
        "paper": {"seconds": 30.0, "warmup": 5.0, "repetitions": 15},
    }[args.preset]
    seconds = args.seconds if args.seconds is not None else defaults["seconds"]
    warmup = args.warmup if args.warmup is not None else defaults["warmup"]
    repetitions = args.repetitions if args.repetitions is not None else defaults["repetitions"]
    variants = "native,rlbox-only,interspec"
    if args.include_tracking:
        variants = "native,rlbox-only,tracked-no-check,interspec"

    args.out.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    all_samples = []
    combined = []
    invalid = []

    for scenario in SCENARIOS:
        out = args.out / scenario["name"]
        cmd = [
            sys.executable, str(root / "tools/benchmark_memcached.py"),
            "--work", str(args.work),
            "--out", str(out),
            "--seconds", str(seconds),
            "--warmup", str(warmup),
            "--repetitions", str(repetitions),
            "--clients", str(scenario["clients"]),
            "--pipeline", str(scenario["pipeline"]),
            "--value-bytes", str(scenario["value_bytes"]),
            "--keys", str(scenario["keys"]),
            "--get-percent", str(scenario["get_percent"]),
            "--workloads", scenario["mode"],
            "--variants", variants,
            "--label", f"{args.label}:{scenario['name']}",
            "--correctness-summary", str(args.correctness_summary),
        ]
        if args.server_cpus:
            cmd += ["--server-cpus", args.server_cpus]
        if args.client_cpus:
            cmd += ["--client-cpus", args.client_cpus]
        subprocess.run(cmd, check=True)

        summary_rows = json.loads((out / "summary.json").read_text())
        rows = {row["variant"]: row for row in summary_rows}
        native, rlbox, interspec = rows["native"], rows["rlbox-only"], rows["interspec"]
        valid = all(
            row["all_no_log_loss"] and row["all_no_lru_loss"]
            for row in rows.values()
        )
        if not valid:
            invalid.append(scenario["name"])
        combined.append({
            **scenario,
            "valid_lossless": valid,
            "native_ops_per_s": native["ops_per_s_median"],
            "rlbox_ops_per_s": rlbox["ops_per_s_median"],
            "interspec_ops_per_s": interspec["ops_per_s_median"],
            "rlbox_loss_vs_native_pct": rlbox["throughput_loss_vs_native_paired_median_pct"],
            "interspec_loss_vs_native_pct": interspec["throughput_loss_vs_native_paired_median_pct"],
            "interspec_loss_vs_rlbox_pct": interspec["throughput_loss_vs_rlbox-only_paired_median_pct"],
            "native_p99_us": native["p99_us_median"],
            "rlbox_p99_us": rlbox["p99_us_median"],
            "interspec_p99_us": interspec["p99_us_median"],
            "native_cpu_us_per_op": native["cpu_us_per_op_median"],
            "rlbox_cpu_us_per_op": rlbox["cpu_us_per_op_median"],
            "interspec_cpu_us_per_op": interspec["cpu_us_per_op_median"],
            "native_rss_mib": native["VmRSS_kib_median"] / 1024.0,
            "rlbox_rss_mib": rlbox["VmRSS_kib_median"] / 1024.0,
            "interspec_rss_mib": interspec["VmRSS_kib_median"] / 1024.0,
        })
        if args.include_tracking:
            tracked = rows["tracked-no-check"]
            combined[-1].update({
                "tracking_ops_per_s": tracked["ops_per_s_median"],
                "tracking_loss_vs_rlbox_pct": tracked["throughput_loss_vs_rlbox-only_paired_median_pct"],
                "interspec_loss_vs_tracking_pct": interspec["throughput_loss_vs_tracked-no-check_paired_median_pct"],
                "tracking_p99_us": tracked["p99_us_median"],
                "tracking_cpu_us_per_op": tracked["cpu_us_per_op_median"],
                "tracking_rss_mib": tracked["VmRSS_kib_median"] / 1024.0,
            })
        with (out / "samples.csv").open(newline="") as f:
            for row in csv.DictReader(f):
                all_samples.append({"scenario": scenario["name"], **row})

    (args.out / "final-summary.json").write_text(json.dumps({
        "preset": args.preset,
        "seconds": seconds,
        "warmup": warmup,
        "repetitions": repetitions,
        "variants": variants.split(","),
        "scenarios": combined,
        "invalid_loss_scenarios": invalid,
    }, indent=2) + "\n")

    if all_samples:
        with (args.out / "all-samples.csv").open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(all_samples[0]))
            writer.writeheader()
            writer.writerows(all_samples)

    lines = [
        "# Memcached end-to-end overhead matrix",
        "",
        "Positive deltas mean lower throughput. Values are medians; overheads are medians of paired per-repetition ratios.",
        "",
        "| Scenario | Practical intent | Native Kops/s | RLBox Kops/s (Δ native) | InterSpec Kops/s (Δ native) | InterSpec Δ vs RLBox | p99 N/R/I (µs) | Loss-free |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in combined:
        lines.append(
            f"| {row['name']} | {row['purpose']} | "
            f"{row['native_ops_per_s']/1000:.1f} | "
            f"{row['rlbox_ops_per_s']/1000:.1f} ({row['rlbox_loss_vs_native_pct']:+.2f}%) | "
            f"{row['interspec_ops_per_s']/1000:.1f} ({row['interspec_loss_vs_native_pct']:+.2f}%) | "
            f"{row['interspec_loss_vs_rlbox_pct']:+.2f}% | "
            f"{row['native_p99_us']:.1f}/{row['rlbox_p99_us']:.1f}/{row['interspec_p99_us']:.1f} | "
            f"{'yes' if row['valid_lossless'] else 'NO'} |"
        )
    if args.include_tracking:
        lines += ["", "## Allocation tracking decomposition", "",
                  "All four variants are collected in the same paired experiment. Percentages describe throughput loss; these paired medians must not be added.", "",
                  "| Scenario | Tracking Kops/s | Tracking loss vs RLBox | InterSpec loss vs tracking | Tracking p99 µs | Lossless across all variants |",
                  "| --- | ---: | ---: | ---: | ---: | --- |"]
        for row in combined:
            lines.append(f"| {row['name']} | {row['tracking_ops_per_s']/1000:.1f} | "
                         f"{row['tracking_loss_vs_rlbox_pct']:+.2f}% | "
                         f"{row['interspec_loss_vs_tracking_pct']:+.2f}% | "
                         f"{row['tracking_p99_us']:.1f} | {'yes' if row['valid_lossless'] else 'NO'} |")
    lines += [
        "",
        "The balanced 1-client and 8-client scenarios preserve the original InterSpec memcached/bipbuffer workload shape of a 1:1 GET/SET ratio with pipeline depth 10 while making value size and working-set size explicit.",
        "Watcher scenarios are accepted for the main table only when every timed run has zero logger and LRU drops. A lossy run is retained as raw evidence but must not be interpreted as an overhead result.",
        "",
    ]
    (args.out / "FINAL_TABLE.md").write_text("\n".join(lines))
    if invalid:
        raise SystemExit("matrix contains lossy scenarios; raw evidence retained: " + ", ".join(invalid))


if __name__ == "__main__":
    main()
