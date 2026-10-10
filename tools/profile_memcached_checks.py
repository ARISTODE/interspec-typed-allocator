#!/usr/bin/env python3
"""Count successful SP3 metadata checks on fixed-operation memcached workloads."""
import argparse
from collections import Counter
import hashlib
import json
import platform
from pathlib import Path
import re
import subprocess
import time

from benchmark_memcached import Watcher
from benchmark_memcached_matrix import SCENARIOS
from memcached_common import Client, Server

EVENT = re.compile(r"\bevent=([^ ]+).*\bresult=([^ ]+)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--work", type=Path, default=Path("/tmp/interspec-memcached-deployment"))
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--correctness-summary", type=Path, required=True)
    p.add_argument("--operations", type=int, default=5000)
    p.add_argument("--write-operations", type=int, default=200000,
                   help="fixed count for write_heavy, declared before execution; no retries based on observed counts")
    p.add_argument("--write-key-cap", type=int, default=10000)
    p.add_argument("--require-coverage", action="store_true")
    p.add_argument("--key-cap", type=int, default=2048,
                   help="cap preloaded keys for trace volume; traffic mix and concurrency remain scenario-specific")
    args = p.parse_args()
    assert args.operations > 0 and args.write_operations > 0 and args.key_cap > 0 and args.write_key_cap > 0

    gate = json.loads(args.correctness_summary.read_text())
    assert gate["passed"] == gate["total"] == 50
    diagnostic = args.work / "bin/memcached-diagnostics"
    assert hashlib.sha256(diagnostic.read_bytes()).hexdigest() == gate["binary_sha256"][diagnostic.name]

    args.out.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    client = args.work / "memcached-client"
    subprocess.run([
        "g++", "-std=c++17", "-O2", "-pthread",
        str(root / "evaluation/memcached_client.cpp"), "-o", str(client)
    ], check=True)
    (args.out / "environment.json").write_text(json.dumps({
        "parameters": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
        "host": platform.uname()._asdict(),
        "build": json.loads((args.work / "build-manifest.json").read_text()),
        "diagnostic_sha256": hashlib.sha256(diagnostic.read_bytes()).hexdigest(),
        "client_sha256": hashlib.sha256(client.read_bytes()).hexdigest(),
        "collector_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "interval": "client traffic plus 0.5 second asynchronous drain; preload and setup excluded; instrumented diagnostic, not timing evidence",
    }, indent=2) + "\n")

    results = []
    for scenario in SCENARIOS:
        keys = min(scenario["keys"], args.write_key_cap if scenario["name"] == "write_heavy" else args.key_cap)
        target_operations = args.write_operations if scenario["name"] == "write_heavy" else args.operations
        name = f"check-profile-{scenario['name']}"
        watcher = None
        with Server(
            diagnostic, args.out / "logs", name, trace=True,
            extra=["-o", "worker_logbuf_size=1024,watcher_logbuf_size=4096"]
        ) as server:
            try:
                with Client(server.port) as c:
                    for i in range(keys):
                        assert c.store(f"bench{i}".encode(), b"x" * scenario["value_bytes"]) == b"STORED\r\n"
                time.sleep(0.5)
                if scenario["mode"] == "watch_active":
                    watcher = Watcher(server.port)
                    watcher.settle()
                time.sleep(0.2)
                with Client(server.port) as c:
                    before = c.stats()
                start_offset = server.logpath.stat().st_size
                cmd = [
                    str(client), str(server.port), "0",
                    str(scenario["clients"]), str(scenario["pipeline"]),
                    str(scenario["value_bytes"]), str(keys),
                    str(scenario["get_percent"]), str(target_operations),
                ]
                measured = json.loads(subprocess.run(
                    cmd, capture_output=True, text=True, check=True, timeout=120
                ).stdout)
                if measured["operations"] != target_operations or measured["errors"] != 0:
                    raise RuntimeError("diagnostic client did not complete the declared workload")
                if watcher:
                    watcher.settle()
                time.sleep(0.5)
                end_offset = server.logpath.stat().st_size
                with Client(server.port) as c:
                    after = c.stats()
            finally:
                if watcher:
                    watcher.close()

        with server.logpath.open("rb") as f:
            f.seek(start_offset)
            trace = f.read(end_offset - start_offset).decode(errors="replace")
        (args.out / f"{scenario['name']}.trace").write_text(trace)
        (args.out / f"{scenario['name']}.client.json").write_text(json.dumps(measured, indent=2) + "\n")
        (args.out / f"{scenario['name']}.stats.json").write_text(json.dumps({"before": before, "after": after}, indent=2) + "\n")
        op_counts, call_counts = Counter(), Counter()
        copies_into_u, copies_from_u = Counter(), Counter()
        lru_holds = lru_takes = 0
        runtime_checks = 0
        for line in trace.splitlines():
            if not line.startswith("INTERSPEC "):
                continue
            match = EVENT.search(line)
            if not match:
                continue
            event, result = match.groups()
            fields = dict(part.split("=", 1) for part in line.split() if "=" in part)
            if event == "sandbox_call":
                call_counts[result] += 1
            elif event == "copy_into_u":
                copies_into_u[result] += int(fields["requested"])
            elif event == "copy_from_u":
                copies_from_u[result] += int(fields["requested"])
            elif event == "lru_hold" and result == "ok":
                lru_holds += 1
            elif event == "lru_take" and result == "ok":
                lru_takes += 1
            if event == "check" and result == "ok":
                runtime_checks += 1
            elif result == "sp3_ok":
                op_counts[event] += 1
        successful_checks = sum(op_counts.values())
        if successful_checks != runtime_checks:
            raise RuntimeError(
                f"{scenario['name']}: bridge-tagged checks={successful_checks}, runtime checks={runtime_checks}"
            )
        operations = int(measured["operations"])
        losses = {key: int(after[key]) - int(before[key]) for key in
                  ("log_worker_dropped", "log_watcher_skipped", "lru_bumps_dropped")}
        moves = int(after["moves_to_warm"]) - int(before["moves_to_warm"])
        coverage = runtime_checks > 0 and all(value == 0 for value in losses.values())
        if scenario["name"] == "write_heavy":
            coverage = coverage and lru_holds > 0 and lru_takes > 0 and moves > 0
        results.append({
            **scenario,
            "profile_keys": keys,
            "operations": operations,
            "runtime_checks": runtime_checks,
            "checks_per_operation": runtime_checks / operations,
            "checks_per_1000_operations": runtime_checks * 1000.0 / operations,
            "check_operations": dict(sorted(op_counts.items())),
            "coverage_valid": bool(coverage),
            "loss_counters": losses,
            "moves_to_warm": moves,
            "lru_holds": lru_holds, "lru_takes": lru_takes,
            "sandbox_calls": sum(call_counts.values()),
            "sandbox_calls_per_operation": sum(call_counts.values()) / operations,
            "sandbox_call_functions": dict(sorted(call_counts.items())),
            "bytes_into_u": sum(copies_into_u.values()),
            "bytes_from_u": sum(copies_from_u.values()),
            "bytes_into_u_per_operation": sum(copies_into_u.values()) / operations,
            "bytes_from_u_per_operation": sum(copies_from_u.values()) / operations,
            "copy_into_u_operations": dict(sorted(copies_into_u.items())),
            "copy_from_u_operations": dict(sorted(copies_from_u.items())),
            "trace_start_offset": start_offset, "trace_end_offset": end_offset,
            "trace_sha256": hashlib.sha256(trace.encode()).hexdigest(),
        })

    (args.out / "check-frequency.json").write_text(json.dumps(results, indent=2) + "\n")
    operation_names = sorted({name for row in results for name in row["check_operations"]})
    lines = [
        "# Memcached SP3 check frequency",
        "",
        f"Ordinary profiles drive {args.operations} fixed client operations; write_heavy drives {args.write_operations}. Counts include client traffic and the declared asynchronous drain; preload and watcher setup are excluded. These diagnostic builds do not provide timing results.",
        "",
        "| Scenario | Client ops | SP3 checks | Checks/op | Checks/1k ops | " + " | ".join(operation_names) + " |",
        "| --- | ---: | ---: | ---: | ---: | " + " | ".join("---:" for _ in operation_names) + " |",
    ]
    for row in results:
        counts = row["check_operations"]
        lines.append(
            f"| {row['name']} | {row['operations']} | {row['runtime_checks']} | "
            f"{row['checks_per_operation']:.4f} | {row['checks_per_1000_operations']:.1f} | "
            + " | ".join(str(counts.get(name, 0)) for name in operation_names) + " |"
        )
    lines += [
        "", "## Boundary activity", "",
        "| Scenario | Sandbox calls/op | Bytes into U/op | Bytes from U/op | LRU holds/takes | Moves to warm | Coverage valid |",
        "| --- | ---: | ---: | ---: | --- | ---: | --- |",
    ]
    for row in results:
        lines.append(f"| {row['name']} | {row['sandbox_calls_per_operation']:.4f} | "
                     f"{row['bytes_into_u_per_operation']:.4f} | {row['bytes_from_u_per_operation']:.4f} | "
                     f"{row['lru_holds']}/{row['lru_takes']} | {row['moves_to_warm']} | {row['coverage_valid']} |")
    lines += [
        "",
        "The operation columns name the actual protected bridge paths (for example request, push, offer_input, peek, peek_all, or poll). These counts are workload frequencies, not timing measurements.",
        "",
    ]
    (args.out / "CHECK_FREQUENCY.md").write_text("\n".join(lines))
    if args.require_coverage and not all(row["coverage_valid"] for row in results):
        raise SystemExit("protected coverage or loss validation failed; all raw diagnostics retained")


if __name__ == "__main__":
    main()
