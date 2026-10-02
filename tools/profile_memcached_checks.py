#!/usr/bin/env python3
"""Count successful SP3 metadata checks on fixed-operation memcached workloads."""
import argparse
from collections import Counter
import hashlib
import json
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
    p.add_argument("--key-cap", type=int, default=2048,
                   help="cap preloaded keys for trace volume; traffic mix and concurrency remain scenario-specific")
    args = p.parse_args()
    assert args.operations > 0 and args.key_cap > 0

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

    results = []
    for scenario in SCENARIOS:
        keys = min(scenario["keys"], args.key_cap)
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
                start_offset = server.logpath.stat().st_size
                cmd = [
                    str(client), str(server.port), "0",
                    str(scenario["clients"]), str(scenario["pipeline"]),
                    str(scenario["value_bytes"]), str(keys),
                    str(scenario["get_percent"]), str(args.operations),
                ]
                measured = json.loads(subprocess.run(
                    cmd, capture_output=True, text=True, check=True, timeout=120
                ).stdout)
                if watcher:
                    watcher.settle()
                time.sleep(0.5)
                end_offset = server.logpath.stat().st_size
            finally:
                if watcher:
                    watcher.close()

        with server.logpath.open("rb") as f:
            f.seek(start_offset)
            trace = f.read(end_offset - start_offset).decode(errors="replace")
        op_counts = Counter()
        runtime_checks = 0
        for line in trace.splitlines():
            if not line.startswith("INTERSPEC "):
                continue
            match = EVENT.search(line)
            if not match:
                continue
            event, result = match.groups()
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
        results.append({
            **scenario,
            "profile_keys": keys,
            "operations": operations,
            "runtime_checks": runtime_checks,
            "checks_per_operation": runtime_checks / operations,
            "checks_per_1000_operations": runtime_checks * 1000.0 / operations,
            "check_operations": dict(sorted(op_counts.items())),
        })

    (args.out / "check-frequency.json").write_text(json.dumps(results, indent=2) + "\n")
    operation_names = sorted({name for row in results for name in row["check_operations"]})
    lines = [
        "# Memcached SP3 check frequency",
        "",
        f"Each row drives {args.operations} fixed client operations. Counts are taken only from the measured phase; preload and watcher setup are excluded.",
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
        "",
        "The operation columns name the actual protected bridge paths (for example request, push, offer_input, peek, peek_all, or poll). These counts are workload frequencies, not timing measurements.",
        "",
    ]
    (args.out / "CHECK_FREQUENCY.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
