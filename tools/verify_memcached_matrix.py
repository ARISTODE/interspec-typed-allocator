#!/usr/bin/env python3
"""Independently recompute the complete four-variant experiment from raw CSVs.

No collection or summary routine is imported. A successful run requires exact
pair coverage, validated responses, no drops, the correctness binary identities,
source environment consistency, and matching derived arithmetic.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import median

VARIANTS = ("native", "rlbox-only", "tracked-no-check", "interspec")
SCENARIOS = {
    "balanced_1c": (1, 10, 256, 10000, 50, "cache_only"),
    "balanced_8c": (8, 10, 256, 10000, 50, "cache_only"),
    "read_heavy_1k": (8, 16, 1024, 10000, 95, "cache_only"),
    "write_heavy": (8, 8, 256, 10000, 10, "cache_only"),
    "watch_light": (1, 1, 256, 10000, 50, "watch_active"),
    "watch_moderate": (2, 2, 256, 10000, 50, "watch_active"),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def near(actual, expected, message, *, tolerance=1e-8):
    actual = float(actual)
    require(math.isfinite(actual) and math.isclose(actual, expected, rel_tol=tolerance, abs_tol=tolerance), message)


def read_csv(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def verify(directory, gate_path):
    def load(path):
        return json.loads(path.read_text())
    gate = load(gate_path)
    require(gate["passed"] == gate["total"] == 50, "correctness gate incomplete")
    final = load(directory / "final-summary.json")
    require(set(final["variants"]) == set(VARIANTS) and len(final["variants"]) == 4, "missing or duplicate variant")
    require(len(final["scenarios"]) == 6 and {s["name"] for s in final["scenarios"]} == set(SCENARIOS), "scenario coverage")
    require(final["repetitions"] >= 3, "insufficient paired repetitions")
    expected = {(v, n) for v in VARIANTS for n in range(final["repetitions"])}
    summary_by_name = {s["name"]: s for s in final["scenarios"]}
    all_raw = []
    inputs = [gate_path, directory / "final-summary.json", directory / "all-samples.csv"]
    builds = []
    result = []
    for name, configuration in SCENARIOS.items():
        folder = directory / name
        raw = read_csv(folder / "samples.csv")
        env = load(folder / "environment.json")
        summaries = load(folder / "summary.json")
        parameters = env["parameters"]
        require(tuple(parameters[k] for k in ("clients", "pipeline", "value_bytes", "keys", "get_percent", "workloads")) == configuration, f"{name}: workload differs")
        for key in ("seconds", "warmup", "repetitions"):
            require(parameters[key] == final[key], f"{name}: {key} differs")
        require(parameters["variants"].split(",") == final["variants"], f"{name}: variants differ")
        for variant in VARIANTS:
            binary = "memcached-" + variant
            require(env["build"]["binary_sha256"][binary] == gate["binary_sha256"][binary], f"{name}: binary differs from correctness gate")
        require(not env["build"]["project_dirty"], f"{name}: uncommitted build source")
        builds.append((env["build"], env["client_sha256"], env["collector_sha256"], env["host"], env["affinity"]))
        indexed = {(r["variant"], int(r["repetition"])): r for r in raw}
        require(len(raw) == len(indexed) and set(indexed) == expected, f"{name}: missing/duplicate pair")
        for rep in range(final["repetitions"]):
            require({int(indexed[v, rep]["order"]) for v in VARIANTS} == set(range(4)), f"{name}: order coverage")
        for row in raw:
            require(row["workload"] == configuration[-1], f"{name}: wrong workload")
            require(int(row["operations"]) > 0 and float(row["elapsed_s"]) >= final["seconds"] and int(row["errors"]) == 0, f"{name}: failed/incomplete client run")
            near(row["ops_per_s"], int(row["operations"]) / float(row["elapsed_s"]), f"{name}: throughput arithmetic", tolerance=1e-7)
            for key in ("log_worker_dropped", "log_watcher_skipped", "lru_bumps_dropped"):
                require(int(row[key]) == 0, f"{name}/{row['variant']}: {key}")
            require(row["valid_no_log_loss"] == row["valid_no_lru_loss"] == "True", f"{name}: invalid loss flag")
            require(0 <= float(row["p50_us"]) <= float(row["p95_us"]) <= float(row["p99_us"]) <= float(row["max_us"]), f"{name}: latency quantiles")
            near(row["cpu_us_per_op"], float(row["server_cpu_s"]) * 1e6 / int(row["operations"]), f"{name}: CPU arithmetic")
            if configuration[-1] == "watch_active":
                require(int(row["log_worker_written"]) > 0 and int(row["watcher_bytes_including_warmup"]) > 0, f"{name}: inactive watcher")
            stem = f"{row['workload']}-{row['repetition']}-{row['variant']}"
            stats_path = folder / "logs" / (stem + ".stats.json")
            stats = load(stats_path)
            for key in ("log_worker_written", "log_worker_dropped", "log_watcher_sent", "log_watcher_skipped", "lru_bumps_dropped", "moves_to_warm"):
                require(int(row[key]) == int(stats["after"][key]) - int(stats["before"][key]), f"{name}: stats counter {key}")
            stderr_path = folder / "logs" / (stem + ".stderr")
            require("INTERSPEC" not in stderr_path.read_text(), f"{name}: diagnostics in timing")
            inputs += [stats_path, stderr_path]
        require(len(summaries) == 4 and {s["variant"] for s in summaries} == set(VARIANTS), f"{name}: summary coverage")
        for summary in summaries:
            variant = summary["variant"]
            samples = [indexed[variant, rep] for rep in range(final["repetitions"])]
            require(summary["n"] == len(samples) and summary["all_no_log_loss"] and summary["all_no_lru_loss"], f"{name}: summary validity")
            for metric in ("ops_per_s", "p50_us", "p95_us", "p99_us", "VmRSS_kib", "VmHWM_kib", "server_cpu_s", "cpu_us_per_op", "startup_ms"):
                values = [float(r[metric]) for r in samples]
                require(all(math.isfinite(x) and x >= 0 for x in values), f"{name}: invalid {metric}")
                for suffix, fn in (("median", median), ("min", min), ("max", max)):
                    near(summary[metric + "_" + suffix], fn(values), f"{name}: {metric} {suffix}")
            for base in VARIANTS[:3]:
                loss = [(1 - float(r["ops_per_s"]) / float(indexed[base, int(r["repetition"])]["ops_per_s"])) * 100 for r in samples]
                near(summary[f"throughput_loss_vs_{base}_paired_median_pct"], median(loss), f"{name}: paired loss {variant}/{base}")
        combined = summary_by_name[name]
        require(combined["valid_lossless"], f"{name}: matrix validity")
        def loss(a, b):
            return [(1 - float(indexed[a, rep]["ops_per_s"]) / float(indexed[b, rep]["ops_per_s"])) * 100 for rep in range(final["repetitions"])]
        for prefix, variant in (("native", "native"), ("rlbox", "rlbox-only"), ("tracking", "tracked-no-check"), ("interspec", "interspec")):
            for field, metric, divisor in (("ops_per_s", "ops_per_s", 1), ("p99_us", "p99_us", 1), ("cpu_us_per_op", "cpu_us_per_op", 1), ("rss_mib", "VmRSS_kib", 1024)):
                near(combined[f"{prefix}_{field}"], median(float(indexed[variant, rep][metric]) for rep in range(final["repetitions"])) / divisor, f"{name}: matrix {prefix} {field}")
        pairs = (("rlbox_loss_vs_native_pct", "rlbox-only", "native"), ("interspec_loss_vs_native_pct", "interspec", "native"), ("interspec_loss_vs_rlbox_pct", "interspec", "rlbox-only"), ("tracking_loss_vs_rlbox_pct", "tracked-no-check", "rlbox-only"), ("interspec_loss_vs_tracking_pct", "interspec", "tracked-no-check"))
        ranges = {}
        for field, a, b in pairs:
            values = loss(a, b)
            near(combined[field], median(values), f"{name}: matrix {field}")
            ranges[field] = {"paired_values": values, "median": median(values), "min": min(values), "max": max(values)}
        result.append({"scenario": name, "samples": len(raw), "paired_throughput_loss_pct": ranges})
        inputs += [folder / f for f in ("samples.csv", "summary.json", "environment.json")]
        all_raw += [{"scenario": name, **r} for r in raw]
    require(all(b == builds[0] for b in builds), "different build/client/host across scenarios")
    require(all_raw == read_csv(directory / "all-samples.csv"), "combined raw CSV differs")
    require(final["invalid_loss_scenarios"] == [], "invalid scenario summary")
    return {"validated": True, "publication_ready": False,
            "limitation": "Hosted reference; controlled publication protocol remains required.",
            "source_commit": builds[0][0]["project_commit"], "samples": len(all_raw),
            "variants": list(VARIANTS), "repetitions": final["repetitions"], "results": result,
            "source_sha256": {str(p.relative_to(directory.parent)) if p.is_relative_to(directory.parent) else str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--correctness-summary", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.matrix, args.correctness_summary)
    (args.matrix / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"Verified {result['samples']} raw samples: six scenarios, four variants, {result['repetitions']} pairs. Publication readiness remains false.")


if __name__ == "__main__":
    main()
