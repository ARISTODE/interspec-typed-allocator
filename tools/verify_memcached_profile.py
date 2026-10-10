#!/usr/bin/env python3
"""Recount archived diagnostic events without importing the collector parser."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path


def verify(root, gate_path):
    def load(path):
        return json.loads(path.read_text())
    def require(ok, message):
        if not ok:
            raise ValueError(message)
    environment = load(root / "environment.json")
    gate = load(gate_path)
    require(gate["passed"] == gate["total"] == 50, "correctness gate")
    require(environment["diagnostic_sha256"] == gate["binary_sha256"]["memcached-diagnostics"] == environment["build"]["binary_sha256"]["memcached-diagnostics"], "diagnostic binary identity")
    rows = load(root / "check-frequency.json")
    require(len(rows) == 6 and {r["name"] for r in rows} == {"balanced_1c", "balanced_8c", "read_heavy_1k", "write_heavy", "watch_light", "watch_moderate"}, "profile coverage")
    sources = [root / "environment.json", root / "check-frequency.json", gate_path]
    for row in rows:
        name = row["name"]
        paths = [root / f"{name}.trace", root / f"{name}.client.json", root / f"{name}.stats.json"]
        trace_path, client_path, stats_path = paths
        raw_path = root / "logs" / f"check-profile-{name}.stderr"
        raw = raw_path.read_bytes()
        trace = trace_path.read_bytes()
        require(trace == raw[row["trace_start_offset"]:row["trace_end_offset"]], f"{name}: trace interval mismatch")
        require(hashlib.sha256(trace).hexdigest() == row["trace_sha256"], f"{name}: trace hash")
        client = load(client_path)
        target = environment["parameters"]["write_operations" if name == "write_heavy" else "operations"]
        require(client["operations"] == row["operations"] == target and client["errors"] == 0 and target > 0, f"{name}: client workload")
        runtime = 0
        checks, calls, into_u, from_u, handles = (Counter() for _ in range(5))
        for line in trace.decode().splitlines():
            require(line.startswith("INTERSPEC "), f"{name}: unexpected diagnostic/error output")
            fields = dict(token.split("=", 1) for token in line.split()[1:])
            event, outcome = fields["event"], fields["result"]
            if event == "check":
                require(outcome == "ok", f"{name}: failed runtime check")
                runtime += 1
            if outcome == "sp3_ok":
                checks[event] += 1
            if event == "sandbox_call":
                calls[outcome] += 1
            if event == "copy_into_u":
                into_u[outcome] += int(fields["requested"])
            if event == "copy_from_u":
                from_u[outcome] += int(fields["requested"])
            if event in ("lru_hold", "lru_take") and outcome == "ok":
                handles[event] += 1
        require(runtime == sum(checks.values()) == row["runtime_checks"] and dict(checks) == row["check_operations"], f"{name}: check attribution")
        for actual, field in ((calls, "sandbox_call_functions"), (into_u, "copy_into_u_operations"), (from_u, "copy_from_u_operations")):
            require(dict(actual) == row[field], f"{name}: {field}")
        for actual, field in ((sum(calls.values()), "sandbox_calls"), (sum(into_u.values()), "bytes_into_u"), (sum(from_u.values()), "bytes_from_u")):
            require(actual == row[field] and math.isclose(row[field + "_per_operation"], actual / target), f"{name}: {field} frequency")
        require(math.isclose(row["checks_per_operation"], runtime / target) and math.isclose(row["checks_per_1000_operations"], runtime * 1000 / target), f"{name}: check frequency arithmetic")
        require(calls["interspec_mc_request"] >= checks["request"] + checks["push"], f"{name}: missing request calls")
        require(calls["interspec_mc_offer"] == checks["offer_input"], f"{name}: offer call mismatch")
        stats = load(stats_path)
        for field in ("log_worker_dropped", "log_watcher_skipped", "lru_bumps_dropped"):
            require(int(stats["after"][field]) - int(stats["before"][field]) == row["loss_counters"][field] == 0, f"{name}: dropped work")
        moves = int(stats["after"]["moves_to_warm"]) - int(stats["before"]["moves_to_warm"])
        require(moves == row["moves_to_warm"], f"{name}: LRU stats")
        require(handles["lru_hold"] == row["lru_holds"] and handles["lru_take"] == row["lru_takes"], f"{name}: LRU trace")
        require(row["coverage_valid"] and runtime > 0 and sum(calls.values()) > 0, f"{name}: protected path not observed")
        if name == "write_heavy":
            require(moves > 0 and handles["lru_hold"] > 0 and handles["lru_take"] > 0, "write_heavy: actual LRU path not observed")
        sources += paths + [raw_path]
    return {"validated": True, "scenarios": len(rows), "timing_evidence": False,
            "source_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--correctness-summary", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.profile, args.correctness_summary)
    (args.profile / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print("Recounted and validated all six raw diagnostic profiles, including write workload LRU coverage.")
