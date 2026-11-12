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


METADATA = ("measurement_mode", "sample_every", "sample_cap_per_client", "workload_mode", "workload_seed")
LATENCIES = ("p50_us", "p95_us", "p99_us", "max_us")


def metadata(record, *, parameters=False):
    # Historical artifacts predate all five fields. Partial metadata is never
    # interpreted as historical evidence.
    if not any(k in record for k in METADATA):
        return None
    require(all(k in record for k in METADATA), "incomplete measurement/workload metadata")
    mode, workload = record["measurement_mode"], record["workload_mode"]
    require(mode in ("full", "count-only", "sampled") and workload in ("legacy", "independent-v1"), "unknown measurement/workload mode")
    every, cap, seed = (int(record[k]) for k in METADATA[1:3] + METADATA[4:])
    require(0 <= seed < 2**64, "invalid workload seed")
    if mode == "sampled":
        require(every > 0 and 0 < cap <= 10000000, "invalid sampling metadata")
    elif parameters:
        # CLI parameters retain unused defaults; emitted records normalize them.
        every = cap = 0
    else:
        require(every == cap == 0, "non-sampled sampling metadata")
    return mode, every, cap, workload, seed


def latency_valid(row, meta, clients):
    if meta is None:
        require(not any(k in row for k in ("latency_valid", "latency_sample_count")), "mixed legacy latency metadata")
        valid = True
    else:
        mode, _, cap, _, _ = meta
        retained, selected, dropped = (int(row[k]) for k in ("latency_sample_count", "latency_selected_count", "latency_dropped_count"))
        require(0 <= retained <= selected <= int(row["operations"]) and dropped >= 0 and retained + dropped == selected, "latency sample arithmetic")
        if mode == "count-only":
            require(retained == selected == dropped == 0, "count-only latency samples")
        elif mode == "full":
            require(retained == selected == int(row["operations"]) and dropped == 0, "full latency sample count")
        else:
            require(retained <= clients * cap, "latency sample cap")
        valid = mode != "count-only" and retained > 0 and dropped == 0
        require(row["latency_valid"] == str(valid), "latency validity mismatch")
        scope = {"count-only": "unavailable", "full": "all_responses_batch_send_to_validation", "sampled": "sampled_response_batch_send_to_validation"}[mode]
        require(row["latency_scope"] == scope, "latency scope mismatch")
        require(math.isfinite(float(row["timed_client_cpu_s"])) and float(row["timed_client_cpu_s"]) >= 0, "invalid client CPU")
    if valid:
        values = [float(row[k]) for k in LATENCIES]
        require(all(math.isfinite(v) for v in values) and 0 <= values[0] <= values[1] <= values[2] <= values[3], "latency quantiles")
    else:
        require(all(row[k] == "" for k in LATENCIES), "unavailable latency must be null")
    return valid


def read_csv(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def verify(directory, gate_path):
    def load(path):
        return json.loads(path.read_text())
    gate = load(gate_path)
    require(gate["passed"] == gate["total"] == 50, "correctness gate incomplete")
    final = load(directory / "final-summary.json")
    meta = metadata(final)
    require(set(final["variants"]) == set(VARIANTS) and len(final["variants"]) == 4, "missing or duplicate variant")
    require(len(final["scenarios"]) == 6 and {s["name"] for s in final["scenarios"]} == set(SCENARIOS), "scenario coverage")
    rehearsal = final.get("evidence_scope") == "vm_recovery_rehearsal"
    require(not rehearsal or final.get("publication_ready") is False, "rehearsal publication claim")
    require(final.get("grid_complete", True) is True and final.get("excluded_scenarios", []) == [], "incomplete matrix grid")
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
        client_path = folder / "memcached-client"
        if client_path.exists():
            require(hashlib.sha256(client_path.read_bytes()).hexdigest() == env["client_sha256"], f"{name}: client binary hash mismatch")
            inputs.append(client_path)
        parameters = env["parameters"]
        require(metadata(parameters, parameters=True) == meta, f"{name}: environment metadata mismatch")
        require(tuple(parameters[k] for k in ("clients", "pipeline", "value_bytes", "keys", "get_percent", "workloads")) == configuration, f"{name}: workload differs")
        require(bool(parameters.get("functional_rehearsal", False)) == rehearsal, f"{name}: rehearsal scope mismatch")
        for key in ("operations", "warmup_operations"):
            require(parameters.get(key, 0) == final.get(key, 0), f"{name}: {key} differs")
        for key in ("seconds", "warmup", "repetitions"):
            require(parameters[key] == final[key], f"{name}: {key} differs")
        require(parameters["variants"].split(",") == final["variants"], f"{name}: variants differ")
        for variant in VARIANTS:
            binary = "memcached-" + variant
            require(env["build"]["binary_sha256"][binary] == gate["binary_sha256"][binary], f"{name}: binary differs from correctness gate")
        require(not env["build"]["project_dirty"], f"{name}: uncommitted build source")
        builds.append((env["build"], env["client_sha256"], env["collector_sha256"], env["host"], env["affinity"], env.get("workload_source_sha256")))
        indexed = {(r["variant"], int(r["repetition"])): r for r in raw}
        require(len(raw) == len(indexed) and set(indexed) == expected, f"{name}: missing/duplicate pair")
        for rep in range(final["repetitions"]):
            require({int(indexed[v, rep]["order"]) for v in VARIANTS} == set(range(4)), f"{name}: order coverage")
        for row in raw:
            require(metadata(row) == meta, f"{name}: raw metadata mismatch")
            require(row["workload"] == configuration[-1], f"{name}: wrong workload")
            operations, elapsed = int(row["operations"]), float(row["elapsed_s"])
            target = final.get("operations", 0)
            complete = operations == target if target else elapsed >= final["seconds"]
            require(operations > 0 and math.isfinite(elapsed) and elapsed > 0 and complete and int(row["errors"]) == 0, f"{name}: failed/incomplete client run")
            near(row["ops_per_s"], int(row["operations"]) / float(row["elapsed_s"]), f"{name}: throughput arithmetic", tolerance=1e-7)
            for key in ("log_worker_dropped", "log_watcher_skipped", "lru_bumps_dropped"):
                require(int(row[key]) == 0, f"{name}/{row['variant']}: {key}")
            require(row["valid_no_log_loss"] == row["valid_no_lru_loss"] == "True", f"{name}: invalid loss flag")
            latency_valid(row, meta, configuration[0])
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
            require(metadata(summary) == meta, f"{name}: summary metadata mismatch")
            variant = summary["variant"]
            samples = [indexed[variant, rep] for rep in range(final["repetitions"])]
            if meta is not None:
                require(summary["workload"] == configuration[-1] and summary["latency_valid"] is all(r["latency_valid"] == "True" for r in samples), f"{name}: summary latency metadata")
            require(summary["n"] == len(samples) and summary["all_no_log_loss"] and summary["all_no_lru_loss"], f"{name}: summary validity")
            for metric in ("ops_per_s", "p50_us", "p95_us", "p99_us", "VmRSS_kib", "VmHWM_kib", "server_cpu_s", "cpu_us_per_op", "startup_ms"):
                if metric in LATENCIES and any(r[metric] == "" for r in samples):
                    require(all(summary[metric + "_" + suffix] is None for suffix in ("median", "min", "max")), f"{name}: unavailable summary latency")
                    continue
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
                if metric in LATENCIES and any(indexed[variant, rep][metric] == "" for rep in range(final["repetitions"])):
                    require(combined[f"{prefix}_{field}"] is None, f"{name}: unavailable matrix latency")
                    continue
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
            "limitation": "VM functional recovery rehearsal only; not timing evidence." if rehearsal else "Hosted reference; controlled publication protocol remains required.",
            "evidence_scope": final.get("evidence_scope", "historical_collection"),
            "source_commit": builds[0][0]["project_commit"], "samples": len(all_raw),
            "measurement_metadata": dict(zip(METADATA, meta)) if meta is not None else None,
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
