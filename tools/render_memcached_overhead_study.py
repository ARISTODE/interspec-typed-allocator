#!/usr/bin/env python3
"""Join end-to-end, check-frequency, and runtime microbenchmark evidence."""
import argparse
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--matrix", type=Path, required=True,
                   help="final-summary.json from benchmark_memcached_matrix.py")
    p.add_argument("--checks", type=Path, required=True,
                   help="check-frequency.json from profile_memcached_checks.py")
    p.add_argument("--microbench", type=Path, required=True,
                   help="summary.json from run_runtime_microbench.py")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()

    matrix = json.loads(args.matrix.read_text())
    checks = {r["name"]: r for r in json.loads(args.checks.read_text())}
    micro = json.loads(args.microbench.read_text())
    direct = [
        r for r in micro
        if r["metric"] == "check_live" and r["population"] == 2 and r["threads"] == 1
    ]
    if len(direct) != 1:
        raise SystemExit("expected one population-2 check_live microbenchmark row")
    check_ns = direct[0]["ns_per_op_median"]

    lines = [
        "# Memcached performance overhead study",
        "",
        "## End-to-end overhead",
        "",
        "Positive percentages mean lower throughput. All overheads are paired by repetition. Lossy watcher runs are not valid overhead measurements.",
        "",
        "| Scenario | Native Kops/s | RLBox Kops/s | RLBox Δ native | InterSpec Kops/s | InterSpec Δ native | InterSpec Δ RLBox | p99 N/R/I µs | Loss-free |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in matrix["scenarios"]:
        lines.append(
            f"| {row['name']} | {row['native_ops_per_s']/1000:.1f} | "
            f"{row['rlbox_ops_per_s']/1000:.1f} | {row['rlbox_loss_vs_native_pct']:+.2f}% | "
            f"{row['interspec_ops_per_s']/1000:.1f} | {row['interspec_loss_vs_native_pct']:+.2f}% | "
            f"{row['interspec_loss_vs_rlbox_pct']:+.2f}% | "
            f"{row['native_p99_us']:.1f}/{row['rlbox_p99_us']:.1f}/{row['interspec_p99_us']:.1f} | "
            f"{'yes' if row['valid_lossless'] else 'NO'} |"
        )

    if "tracked-no-check" in matrix["variants"]:
        lines += ["", "## Allocation tracking decomposition", "",
                  "All variants share the same experiment and repetition pairing. Positive percentages mean lower throughput. These costs cannot be added.", "",
                  "| Scenario | Tracking Kops/s | Tracking loss vs RLBox | InterSpec loss vs tracking | Tracking p99 µs | Tracking CPU µs/op | Tracking RSS MiB |",
                  "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for row in matrix["scenarios"]:
            lines.append(f"| {row['name']} | {row['tracking_ops_per_s']/1000:.1f} | "
                         f"{row['tracking_loss_vs_rlbox_pct']:+.2f}% | "
                         f"{row['interspec_loss_vs_tracking_pct']:+.2f}% | "
                         f"{row['tracking_p99_us']:.1f} | {row['tracking_cpu_us_per_op']:.3f} | "
                         f"{row['tracking_rss_mib']:.2f} |")

    lines += [
        "",
        "## SP3 primitive microbenchmark",
        "",
        "| Primitive | Population | Median ns/op | Min–max ns/op |",
        "| --- | ---: | ---: | ---: |",
    ]
    wanted = {
        "shared_lock", "metadata_lookup", "type_compare", "bounds_check",
        "check_live", "check_interior", "remaining_bytes", "allocate_from_site", "release",
    }
    for row in micro:
        if row["metric"] not in wanted:
            continue
        if row["metric"] not in ("allocate_from_site", "release") and row["population"] != 2:
            continue
        lines.append(
            f"| {row['metric']} | {row['population']} | {row['ns_per_op_median']:.2f} | "
            f"{row['ns_per_op_min']:.2f}–{row['ns_per_op_max']:.2f} |"
        )

    lines += [
        "",
        "## Correlating checks with application overhead",
        "",
        f"The direct production Runtime::check cost used below is {check_ns:.2f} ns/check at population 2. The estimate is checks/op × this microbenchmark cost; it intentionally excludes RLBox transitions, byte copies, queue synchronization, and other application work.",
        "",
        "| Scenario | Client ops profiled | SP3 checks | Checks/op | Checks/1k ops | Estimated direct check ns/client op |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in matrix["scenarios"]:
        profile = checks.get(row["name"])
        if not profile:
            lines.append(f"| {row['name']} | n/a | n/a | n/a | n/a | n/a |")
            continue
        # A short profile that never reached a protected path cannot establish
        # its cost. Keep the observed zero count but exclude it from correlation.
        estimate = (f"{profile['checks_per_operation'] * check_ns:.2f}"
                    if profile["runtime_checks"] > 0 else "unavailable (path not observed)")
        lines.append(
            f"| {row['name']} | {profile['operations']} | {profile['runtime_checks']} | "
            f"{profile['checks_per_operation']:.4f} | {profile['checks_per_1000_operations']:.1f} | "
            f"{estimate} |"
        )

    lines += [
        "",
        "A zero observed check count is retained as a coverage gap and is excluded from the cost correlation. It does not establish zero enforcement cost for that workload.",
        "",
        "Interpretation: the microbenchmark establishes the cost of one metadata validation, while the fixed-operation profiler establishes how frequently real memcached paths invoke it. The end-to-end table then measures the actual aggregate effect. The estimate should explain direction and scale, not exactly equal the throughput delta, because checks execute concurrently and interact with sandbox transitions, copies, locks, cache effects, batching, and background logger/LRU work.",
        "",
    ]
    args.output.write_text("\n".join(lines))


if __name__ == "__main__":
    main()
