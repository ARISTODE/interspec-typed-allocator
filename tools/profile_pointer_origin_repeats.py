#!/usr/bin/env python3
"""Repeat fixed-operation memcached boundary pointer counts, never timing data.

Each interval excludes preload, startup, and watcher setup and includes a
declared asynchronous drain. Per-site rates are reported with run dispersion.
"""
import argparse
from collections import Counter
import hashlib
import json
import platform
from pathlib import Path
import statistics
import subprocess
import time

from benchmark_memcached import Watcher
from benchmark_memcached_matrix import SCENARIOS
from memcached_common import Client, Server
from summarize_pointer_census import parse_record


def signature(directions, sites, origins):
    return {
        "by_direction": dict(sorted(directions.items())),
        "by_storage": dict(sorted(origins.items())),
        "by_site": [
            {"direction": direction, "site": site, "storage": storage,
             "observations": count}
            for (direction, site, storage), count in sorted(sites.items())
        ],
    }


def spread(values):
    return {"median": statistics.median(values),
            "minimum": min(values), "maximum": max(values),
            "population_stdev": statistics.pstdev(values),
            "repetitions": len(values)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work", type=Path, default=Path("/tmp/interspec-memcached-deployment"))
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--correctness-summary", required=True, type=Path)
    p.add_argument("--repetitions", type=int, default=5)
    p.add_argument("--operations", type=int, default=2500)
    p.add_argument("--write-operations", type=int, default=20000)
    p.add_argument("--key-cap", type=int, default=512)
    p.add_argument("--write-key-cap", type=int, default=2000)
    p.add_argument("--drain-seconds", type=float, default=0.5)
    args = p.parse_args()
    assert args.repetitions >= 3 and args.operations > 0 and args.write_operations > 0
    assert args.key_cap > 0 and args.write_key_cap > 0 and args.drain_seconds >= 0.3
    gate = json.loads(args.correctness_summary.read_text())
    assert gate["passed"] == gate["total"] == 50, "paired correctness gate must pass"
    diagnostic = args.work / "bin/memcached-diagnostics"
    binary_sha = hashlib.sha256(diagnostic.read_bytes()).hexdigest()
    assert binary_sha == gate["binary_sha256"][diagnostic.name]

    args.out.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    client = args.work / "pointer-origin-memcached-client"
    subprocess.run(["g++", "-std=c++17", "-O2", "-pthread",
                    str(root / "evaluation/memcached_client.cpp"),
                    "-o", str(client)], check=True)
    environment = {
        "parameters": {key: str(value) if isinstance(value, Path) else value
                       for key, value in vars(args).items()},
        "host": platform.uname()._asdict(),
        "build": json.loads((args.work / "build-manifest.json").read_text()),
        "diagnostic_sha256": binary_sha,
        "client_sha256": hashlib.sha256(client.read_bytes()).hexdigest(),
        "collector_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "interval": ("fixed client operations plus %.2f second asynchronous drain; "
                     "startup, preload, and watcher setup are excluded; "
                     "diagnostic instrumented runs are not timing evidence")
                    % args.drain_seconds,
    }
    (args.out / "environment.json").write_text(json.dumps(environment, indent=2) + "\n")

    samples = []
    summaries = []
    for scenario in SCENARIOS:
        scenario_samples = []
        target = args.write_operations if scenario["name"] == "write_heavy" else args.operations
        keys = min(scenario["keys"], args.write_key_cap if scenario["name"] == "write_heavy" else args.key_cap)
        for repetition in range(1, args.repetitions + 1):
            name = f"{scenario['name']}-repeat{repetition:02d}"
            watcher = None
            with Server(diagnostic, args.out / "logs", name, census=True,
                        extra=["-o", "worker_logbuf_size=1024,watcher_logbuf_size=4096"]) as server:
                try:
                    with Client(server.port) as c:
                        for i in range(keys):
                            assert c.store(f"bench{i}".encode(),
                                           b"x" * scenario["value_bytes"]) == b"STORED\r\n"
                    time.sleep(0.4)
                    if scenario["mode"] == "watch_active":
                        watcher = Watcher(server.port)
                        watcher.settle()
                    time.sleep(0.2)
                    with Client(server.port) as c:
                        before = c.stats()
                    start_offset = server.logpath.stat().st_size
                    cmd = [str(client), str(server.port), "0",
                           str(scenario["clients"]), str(scenario["pipeline"]),
                           str(scenario["value_bytes"]), str(keys),
                           str(scenario["get_percent"]), str(target)]
                    measured = json.loads(subprocess.run(
                        cmd, capture_output=True, text=True, check=True, timeout=120
                    ).stdout)
                    assert int(measured["operations"]) == target and measured["errors"] == 0
                    if watcher:
                        watcher.settle()
                    time.sleep(args.drain_seconds)
                    end_offset = server.logpath.stat().st_size
                    with Client(server.port) as c:
                        after = c.stats()
                    assert server.proc.poll() is None, "server exited unexpectedly"
                finally:
                    if watcher is not None:
                        watcher.close()

            with server.logpath.open("rb") as stream:
                stream.seek(start_offset)
                raw = stream.read(end_offset - start_offset)
            trace = raw.decode("utf-8", errors="replace")
            trace_path = args.out / f"{name}.trace"
            trace_path.write_bytes(raw)
            assert "INTERSPEC_REJECT" not in trace, "normal workload rejected by SP3"
            directions, sites, origins = Counter(), Counter(), Counter()
            for line_number, line in enumerate(trace.splitlines(), 1):
                record = parse_record(line, trace_path, line_number, "memcached_bipbuffer")
                if record is None:
                    continue
                if record["direction"] == "u_to_t":
                    assert record["storage"] == "u_tracked_heap" and record["result"] == "accepted", record
                else:
                    assert record["result"] == "observed", record
                directions[record["direction"]] += 1
                origins[record["storage"]] += 1
                sites[(record["direction"], record["site"], record["storage"])] += 1
            losses = {key: int(after[key]) - int(before[key])
                      for key in ("log_worker_dropped", "log_watcher_skipped", "lru_bumps_dropped")}
            assert all(loss == 0 for loss in losses.values()), (name, losses)
            row = {
                "scenario": scenario["name"], "repetition": repetition,
                "client_operations": target, "preloaded_keys": keys,
                "client_report": measured, "loss_counters": losses,
                "monitored_stats_before": {
                    key: int(before[key]) for key in losses
                },
                "monitored_stats_after": {
                    key: int(after[key]) for key in losses
                },
                "observations": sum(directions.values()),
                "observations_per_1000_ops": 1000.0 * sum(directions.values()) / target,
                "trace_sha256": hashlib.sha256(raw).hexdigest(),
                "trace_file": trace_path.name,
                "start_offset": start_offset, "end_offset": end_offset,
                **signature(directions, sites, origins),
            }
            scenario_samples.append(row)
            samples.append(row)
            print("INTERSPEC_POINTER_REPEAT_SAMPLE " + json.dumps({
                "scenario": row["scenario"], "repetition": row["repetition"],
                "operations": target, "observations": row["observations"],
                "by_storage": row["by_storage"], "loss_counters": losses,
            }, sort_keys=True), flush=True)
            (args.out / "samples.json").write_text(json.dumps(samples, indent=2) + "\n")

        origin_names = sorted({origin for row in scenario_samples for origin in row["by_storage"]})
        site_names = sorted({(entry["direction"], entry["site"], entry["storage"])
                             for row in scenario_samples for entry in row["by_site"]})
        origin_rates = {}
        for origin in origin_names:
            origin_rates[origin] = spread([1000.0 * row["by_storage"].get(origin, 0) / target
                                          for row in scenario_samples])
        site_rates = []
        for direction, site, storage in site_names:
            rates = []
            for row in scenario_samples:
                observed = next((entry["observations"] for entry in row["by_site"]
                                 if (entry["direction"], entry["site"], entry["storage"]) ==
                                    (direction, site, storage)), 0)
                rates.append(1000.0 * observed / target)
            site_rates.append({
                "direction": direction, "site": site, "storage": storage,
                "per_1000_operations": spread(rates),
            })
        summary = {
            "scenario": scenario["name"], "purpose": scenario["purpose"],
            "repetitions": args.repetitions, "client_operations_per_repeat": target,
            "observations_per_1000_operations": spread([
                row["observations_per_1000_ops"] for row in scenario_samples
            ]),
            "storage_per_1000_operations": origin_rates,
            "site_per_1000_operations": site_rates,
            "loss_free_and_no_rejections": True,
        }
        summaries.append(summary)
        print("INTERSPEC_POINTER_REPEAT_SUMMARY " + json.dumps(summary, sort_keys=True), flush=True)
        (args.out / "normalized-summary.json").write_text(json.dumps({
            "schema": 1,
            "source": "memcached diagnostic fixed-operation repeated normal workloads",
            "not_performance_measurement": True,
            "unit": "pointer observations per 1000 client operations, not distinct pointers",
            "t_pointer_addresses_pass_raw_to_u": False,
            "vma_is_not_allocation_provenance": True,
            "asynchronous_drain_seconds": args.drain_seconds,
            "runs": summaries,
        }, indent=2, sort_keys=True) + "\n")

    assert sum(row["observations"] for row in samples) > 0, "census instrumentation inactive"


if __name__ == "__main__":
    main()
