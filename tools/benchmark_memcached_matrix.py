#!/usr/bin/env python3
"""Run the publication-oriented memcached workload matrix and render the main 3-way table."""
import argparse
import csv
import json
import shutil
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


def main(argv=None, checkpoint=None):
    p = argparse.ArgumentParser(allow_abbrev=False)
    p.add_argument("--work", type=Path, default=Path("/tmp/interspec-memcached-deployment"))
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--correctness-summary", type=Path, required=True)
    p.add_argument("--measurement-mode", choices=("full", "count-only", "sampled"), default="count-only")
    p.add_argument("--sample-every", type=int, default=1024)
    p.add_argument("--sample-cap-per-client", type=int, default=100000)
    p.add_argument("--workload-mode", choices=("legacy", "independent-v1"), default="independent-v1")
    p.add_argument("--workload-seed", type=int, default=20261109)
    p.add_argument("--preset", choices=("smoke", "paper"), default="smoke")
    p.add_argument("--operations", type=int, default=0)
    p.add_argument("--warmup-operations", type=int, default=0)
    p.add_argument("--seconds", type=float)
    p.add_argument("--warmup", type=float)
    p.add_argument("--repetitions", type=int)
    p.add_argument("--server-cpus")
    p.add_argument("--client-cpus")
    p.add_argument("--include-tracking", action="store_true",
                   help="also collect tracked-no-check for decomposition; main table remains native/RLBox/InterSpec")
    p.add_argument("--label", default="memcached_overhead_matrix")
    p.add_argument("--client-binary", type=Path)
    p.add_argument("--functional-rehearsal", action="store_true")
    args = p.parse_args(argv)

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
        if checkpoint:
            out, execute = checkpoint.begin(scenario["name"])
            if out is None:
                continue
        cmd = [
            sys.executable, str(root / "tools/benchmark_memcached.py"),
            "--work", str(args.work),
            "--out", str(out),
            "--operations", str(args.operations), "--warmup-operations", str(args.warmup_operations),
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
            "--measurement-mode", args.measurement_mode, "--sample-every", str(args.sample_every),
            "--sample-cap-per-client", str(args.sample_cap_per_client),
            "--workload-mode", args.workload_mode, "--workload-seed", str(args.workload_seed),
        ]
        if args.server_cpus:
            cmd += ["--server-cpus", args.server_cpus]
        if args.client_cpus:
            cmd += ["--client-cpus", args.client_cpus]
        if args.client_binary:
            cmd += ["--client-binary", str(args.client_binary)]
        if args.functional_rehearsal:
            cmd += ["--functional-rehearsal"]
        if not checkpoint or execute:
            if checkpoint:
                checkpoint.launch(cmd, out)
            else:
                subprocess.run(cmd, check=True)

        if checkpoint:
            report_out = args.out / scenario["name"]
            shutil.copytree(out, report_out)
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
        "evidence_scope": "vm_recovery_rehearsal" if args.functional_rehearsal else "unclassified_collection",
        "publication_ready": False,
        "operations": args.operations, "warmup_operations": args.warmup_operations,
        "grid_complete": len(combined) == len(SCENARIOS),
        "excluded_scenarios": checkpoint.excluded if checkpoint else [],
        "scope": "VM functional rehearsal only" if args.functional_rehearsal else "collection; host control not asserted",
        "measurement_mode": args.measurement_mode,
        "sample_every": args.sample_every if args.measurement_mode == "sampled" else 0,
        "sample_cap_per_client": args.sample_cap_per_client if args.measurement_mode == "sampled" else 0,
        "workload_mode": args.workload_mode,
        "workload_seed": args.workload_seed,
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

    def latency(value): return "unavailable" if value is None else f"{value:.1f}"
    lines = [
        "# VM functional recovery rehearsal" if args.functional_rehearsal else "# Memcached end-to-end overhead matrix",
        "Not publication-ready. Incidental rates are retained for provenance, not controlled-host overhead evidence.",
        "",
        f"Measurement: {args.measurement_mode}; latency fields describe this run only. Count-only latency is unavailable; sampled quantiles describe selected responses, not every response.",
        "",
        f"Workload generator: {args.workload_mode}; seed: {args.workload_seed}. Independent mode uses a target GET probability, not an exact finite-sample ratio. Do not pool with legacy results.",
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
            f"{latency(row['native_p99_us'])}/{latency(row['rlbox_p99_us'])}/{latency(row['interspec_p99_us'])} | "
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
                         f"{latency(row['tracking_p99_us'])} | {'yes' if row['valid_lossless'] else 'NO'} |")
    lines += [
        "",
        "The balanced 1-client and 8-client scenarios preserve the original InterSpec memcached/bipbuffer target workload shape of 50% GET / 50% SET with pipeline depth 10 while making value size and working-set size explicit.",
        "Watcher scenarios are accepted for the main table only when every timed run has zero logger and LRU drops. A lossy run is retained as raw evidence but must not be interpreted as an overhead result.",
        "",
    ]
    (args.out / "FINAL_TABLE.md").write_text("\n".join(lines))
    if checkpoint and checkpoint.excluded:
        raise SystemExit("Incomplete grid: excluded scenarios " + ", ".join(checkpoint.excluded))
    if invalid:
        raise SystemExit("matrix contains lossy scenarios; raw evidence retained: " + ", ".join(invalid))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "checkpoint":
        from matrix_checkpoint import main as checkpoint_main
        checkpoint_main(sys.argv[2:])
    else:
        main()
