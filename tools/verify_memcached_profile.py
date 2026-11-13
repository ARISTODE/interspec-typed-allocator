#!/usr/bin/env python3
"""Recount archived diagnostic events without importing the collector parser."""
import argparse
from collections import Counter
import hashlib
import json
import math
import re
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
        snapshots, copied_records = Counter(), Counter()
        for line in trace.decode().splitlines():
            if line.startswith("INTERSPEC_T_COPY "):
                # SP3 snapshots carry a digest separately from frequency events.
                # Accept only the bridge's exact record schema, never arbitrary
                # diagnostics (especially rejection/sanitizer output).
                match = re.fullmatch(
                    r"INTERSPEC_T_COPY boundary=memcached_bipbuffer "
                    r"operation=(peek|peek_all|poll) bytes=(0|[1-9][0-9]*) "
                    r"fnv64=[0-9a-f]{16}", line)
                require(match is not None, f"{name}: malformed snapshot diagnostic")
                snapshots[(match[1], int(match[2]))] += 1
                continue
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
                copied_records[(outcome, int(fields["requested"]))] += 1
            if event in ("lru_hold", "lru_take") and outcome == "ok":
                handles[event] += 1
        require(snapshots == copied_records, f"{name}: snapshot/copy record mismatch")
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


# Strict frozen-candidate evidence path. Legacy archived evidence above remains
# separately verifiable; it cannot satisfy this schema.
SCENARIO_SHAPES = [
    ("balanced_1c", "cache_only", 1, 10, 256, 50),
    ("balanced_8c", "cache_only", 8, 10, 256, 50),
    ("read_heavy_1k", "cache_only", 8, 16, 1024, 95),
    ("write_heavy", "cache_only", 8, 8, 256, 10),
    ("watch_light", "watch_active", 1, 1, 256, 50),
    ("watch_moderate", "watch_active", 2, 2, 256, 50),
]


def require(ok, message):
    if not ok: raise ValueError(message)


def load_json(path):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, "duplicate JSON key")
            value[key] = item
        return value
    def invalid(value): raise ValueError("nonfinite JSON " + value)
    return json.loads(Path(path).read_text(), object_pairs_hook=unique, parse_constant=invalid)


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def independent_oracle(count, keys, pct, seed):
    """Separate integer implementation; never imports collector or C++ mapping."""
    limit = 2**64
    def scramble(x):
        a = (x + 11400714819323198485) % limit
        b = ((a ^ (a // 2**30)) * 13787848793156543929) % limit
        c = ((b ^ (b // 2**27)) * 10723151780598845931) % limit
        return c ^ (c // 2**31)
    salts = [scramble(seed ^ 2611923443488327891), scramble(seed ^ 1376283091369227076)]
    histogram = [[i, 0, 0] for i in range(keys)]
    for i in range(count):
        values = []
        for bound, salt in zip((keys, 100), salts):
            x = scramble(i ^ salt)
            while x < limit % bound: x = scramble(x)
            values.append(x % bound)
        histogram[values[0]][1 if values[1] < pct else 2] += 1
    return histogram


def validate_plan(path):
    path = Path(path).resolve(); base = path.parent; plan = load_json(path)
    require(plan["schema"] in ("corrected-profile-v1", "source-profile-v2"), "plan schema")
    current = plan["schema"] == "source-profile-v2"
    require(plan["workload_mode"] == "independent-v1" and type(plan["workload_seed"]) is int and plan["workload_seed"] == 20261109 and
            plan["measurement_mode"] == "count-only", "fixed mode/seed")
    require(len(plan["scenarios"]) == 6, "six scenarios")
    for row, shape in zip(plan["scenarios"], SCENARIO_SHAPES):
        require(all(type(row[key]) is int for key in ("clients", "pipeline", "value_bytes", "keys", "get_percent", "operations", "profile_keys")), "scenario integer metadata")
        require(tuple(row[k] for k in ("name", "mode", "clients", "pipeline", "value_bytes", "get_percent")) == shape, "scenario shape/order")
        require(row["keys"] == 10000, "declared scenario keys")
        n, keys = (200000, 10000) if row["name"] == "write_heavy" else (5000, 2048)
        require(row["operations"] == n and row["profile_keys"] == keys, "profile count/key cap")
        histogram = independent_oracle(n, keys, row["get_percent"], plan["workload_seed"])
        expected = row["expected"]
        require(histogram == expected["key_verb_multiset"], "expected key/verb oracle")
        require(hashlib.sha256(json.dumps(histogram, separators=(",", ":")).encode()).hexdigest() == expected["key_verb_multiset_sha256"], "oracle hash")
        gets = sum(x[1] for x in histogram)
        require(expected["get"] == gets and expected["set"] == n - gets, "expected request totals")
    required = {"inputs/client-validation/provenance.json", "inputs/client-validation/release-reproduction-functional.log", "inputs/client-validation/COMMANDS.md",
                "sources/harness/tests/memcached_profile_evidence.py", "sources/harness/tests/memcached_corrected_profile.py",
                "sources/server/integration/memcached_server/bridge.cpp", "sources/server/integration/memcached_server/bipbuffer_u.c",
                "inputs/client", "inputs/client-provenance.json", "inputs/correctness.json",
                "inputs/work/build-manifest.json", "inputs/work/bin/memcached-diagnostics"}
    required |= {"sources/harness/tools/" + name + ".py" for name in
                 ("profile_memcached_checks", "verify_memcached_profile", "benchmark_memcached", "benchmark_memcached_matrix", "memcached_common", "process_guard")}
    required |= {"sources/client/evaluation/" + name for name in
                 ("memcached_client.cpp", "memcached_workload.h", "memcached_measurement.h")}
    if current:
        required |= {"sources/harness/tools/current_memcached_profile.py",
                     "sources/client/tests/memcached_buffered_protocol.py"}
        required |= {"inputs/client-validation/" + name for name in
                     ("compiler-version.txt", "build.stdout", "build.stderr", "protocol.stderr")}
    require(required <= set(plan["files"]), "missing frozen inputs")
    for relative, digest in plan["files"].items():
        file = base / relative
        require(not Path(relative).is_absolute() and ".." not in Path(relative).parts and not file.is_symlink(), "unsafe frozen path")
        require(sha(file) == digest, "frozen file hash: " + relative)
    provenance = load_json(base / "inputs/client-provenance.json")
    require(sha(base / "inputs/client") == provenance["binary_sha256"], "client binary binding")
    require(plan["client_revision"] == provenance["revision"], "client revision binding")
    if not current:
        require(plan["client_revision"] == "0318e75d4a910789e13d9282d9544e8dd7e044bf", "client revision")
        require(provenance["binary_sha256"] == "52861a45be40fa8f17c76ff8dca7ec3e09f99c4970d86d0b243c91d1b9af2b0b", "frozen buffered client")
    for relative, digest in provenance["source_sha256"].items():
        require(sha(base / "sources/client" / relative) == digest, "client source binding")
    gate = load_json(base / "inputs/correctness.json"); build = load_json(base / "inputs/work/build-manifest.json")
    require(gate["passed"] == gate["total"] == len(gate["cases"]) == 50 and all(c["pass"] is True for c in gate["cases"]), "50-case correctness gate")
    actual = sha(base / "inputs/work/bin/memcached-diagnostics")
    require(actual == gate["binary_sha256"]["memcached-diagnostics"] == build["binary_sha256"]["memcached-diagnostics"], "diagnostic binary/gate/build binding")
    if not current:
        require(actual == "4ea15a50835d1c463b996199fc29e5a9f8a0be52e0471dcc1797e7d888a6140f", "frozen diagnostic binary")
        require(build["project_commit"] == "6e164d3a62db94e4774345ee32f7d03cf3906bce", "server revision")
    execution = plan["execution"]
    require(all(Path(execution[key]).is_absolute() for key in ("plan_root", "harness_root", "python", "guard")), "execution roots")
    require(execution["guard"] == str(Path(execution["harness_root"]) / "tools/process_guard.py") and
            isinstance(execution["account_name"], str) and execution["account_name"] and type(execution["uid"]) is int, "execution identity")
    validation = load_json(base / "inputs/client-validation/provenance.json")
    require(validation["candidate_commit"] == plan["client_revision"] and validation["validation"]["release_candidate_protocol"] == "passed", "retained protocol validation")
    if current:
        validate_current_inputs(plan, base, provenance, validation, build)
    for relative, digest in validation["candidate_source_sha256"].items():
        require(sha(base / "sources/client" / relative) == digest, "protocol-test source binding")
    for relative, field in (("integration/memcached_server/bridge.cpp", "bridge_source_sha256"), ("integration/memcached_server/bipbuffer_u.c", "untrusted_source_sha256")):
        require(sha(base / "sources/server" / relative) == build[field], "server source binding")
    return plan



def validate_current_inputs(plan, base, provenance, validation, build):
    """Independent provenance checks for v2; v1 historical pins are unchanged."""
    require(re.fullmatch(r"[0-9a-f]{40}", plan["client_revision"]) is not None, "current source revision")
    require(build["project_commit"] == plan["client_revision"] and build["project_dirty"] is False,
            "current server clean-source revision")
    sources = {"evaluation/memcached_client.cpp", "evaluation/memcached_workload.h",
               "evaluation/memcached_measurement.h", "tests/memcached_buffered_protocol.py"}
    require(set(provenance["source_sha256"]) == sources and
            validation["candidate_source_sha256"] == provenance["source_sha256"], "current client source set")
    require(validation["candidate_binary_sha256"] == provenance["binary_sha256"], "protocol binary binding")
    original = plan["original_inputs"]
    require(provenance["source_root"] == original["client_source"] and
            provenance["binary_path"] == original["client"], "current client original paths")
    compiler = provenance["compiler"]
    require(Path(compiler["path"]).is_absolute() and re.fullmatch(r"[0-9a-f]{64}", compiler["sha256"]) is not None,
            "compiler identity")
    require(sha(base / "inputs/client-validation/compiler-version.txt") == compiler["version_sha256"], "compiler version binding")
    require(provenance["build_command"] == [compiler["path"], "-std=c++17", "-O2", "-pthread",
            str(Path(original["client_source"]) / "evaluation/memcached_client.cpp"), "-o", original["client"]],
            "client build command")
    require(validation["command"] == [plan["execution"]["python"],
            str(Path(original["client_source"]) / "tests/memcached_buffered_protocol.py"),
            original["client"], "--count-only-valid"] and type(validation["returncode"]) is int and
            validation["returncode"] == 0, "current protocol command/status")
    require((base / "inputs/client-validation/release-reproduction-functional.log").read_text() ==
            "10 buffered stream functional cases passed; no performance evidence\n" and
            not (base / "inputs/client-validation/protocol.stderr").read_bytes(), "current protocol output")


def strict_recount(trace):
    counters = {name: Counter() for name in ("checks", "calls", "into", "from", "handles", "snapshots", "copied")}
    runtime = 0
    fields_expected = set("seq pid runtime thread event ptr base size site actual_type expected_type requested offset remaining replacement result".split())
    decimal = set("seq pid thread size site requested offset remaining".split())
    addresses = set("ptr base actual_type expected_type replacement".split())
    call_names = {"interspec_mc_" + op for op in ("new", "free", "request", "push", "offer", "peek_all", "last_size", "peek", "poll", "reset", "used", "unused", "empty")}
    allowed = {"check": {"ok"}, "lru_hold": {"ok"}, "lru_take": {"ok"},
               "sandbox_call": call_names, "copy_into_u": {"push", "offer"},
               "copy_from_u": {"peek", "peek_all", "poll"}, "buffer_role": {"worker", "watcher", "lru"}}
    for op in ("request", "push", "offer_input", "input"): allowed[op] = {"sp3_ok"}
    for op in ("peek", "peek_all", "poll"): allowed[op] = {"sp3_ok", "copied"}
    for op in ("allocate", "allocate_from_site", "allocate_from_pc", "release", "reallocate", "remaining_bytes", "live_allocation"): allowed[op] = {"ok"}
    require(trace and trace.endswith(b"\n"), "empty or unterminated trace")
    for line in trace.decode("utf-8", errors="strict").splitlines():
        if line.startswith("INTERSPEC_T_COPY "):
            m = re.fullmatch(r"INTERSPEC_T_COPY boundary=memcached_bipbuffer operation=(peek|peek_all|poll) bytes=(0|[1-9][0-9]*) fnv64=[0-9a-f]{16}", line)
            require(m is not None, "malformed copy snapshot")
            counters["snapshots"][(m[1], int(m[2]))] += 1
            continue
        require(line.startswith("INTERSPEC "), "unexpected trace diagnostic")
        fields = {}
        for token in line.split(" ")[1:]:
            require(token.count("=") == 1, "malformed trace token")
            key, value = token.split("=")
            require(key not in fields, "duplicate trace field")
            fields[key] = value
        require(set(fields) == fields_expected, "trace field schema")
        require(all(re.fullmatch(r"0|[1-9][0-9]*", fields[k]) for k in decimal), "trace integer schema")
        require(all(re.fullmatch(r"0x[0-9a-f]+", fields[k]) for k in addresses), "trace address schema")
        require(re.fullmatch(r"0x[0-9a-f]+|\(nil\)", fields["runtime"]), "trace runtime schema")
        event, result, size = fields["event"], fields["result"], int(fields["requested"])
        require(event in allowed and result in allowed[event], "unknown or failed trace event")
        if event == "check": runtime += 1
        if result == "sp3_ok": counters["checks"][event] += 1
        if event == "sandbox_call": counters["calls"][result] += 1
        if event == "copy_into_u": counters["into"][result] += size
        if event == "copy_from_u":
            counters["from"][result] += size; counters["copied"][(result, size)] += 1
        if event in ("lru_hold", "lru_take"): counters["handles"][event] += 1
    require(runtime == sum(counters["checks"].values()) and runtime > 0, "runtime/bridge check attribution or coverage")
    require(counters["snapshots"] == counters["copied"], "copy snapshot record reconciliation")
    calls, checks = counters["calls"], counters["checks"]
    require(calls["interspec_mc_request"] >= checks["request"] + checks["push"], "request call reconciliation")
    require(calls["interspec_mc_offer"] == checks["offer_input"], "offer call reconciliation")
    return {"runtime_checks": runtime, "check_operations": dict(checks), "sandbox_call_functions": dict(calls),
            "copy_into_u_operations": dict(counters["into"]), "copy_from_u_operations": dict(counters["from"]),
            "sandbox_calls": sum(calls.values()), "bytes_into_u": sum(counters["into"].values()),
            "bytes_from_u": sum(counters["from"].values()), "lru_holds": counters["handles"]["lru_hold"],
            "lru_takes": counters["handles"]["lru_take"]}


def verify_attempt(directory, scenario, plan, base):
    directory = Path(directory); state = load_json(directory / "attempt.json")
    require(state["name"] == scenario["name"] and state["attempt"] == 1 and state["status"] == "collected", "attempt identity/status")
    require(state["interval"] == plan["interval"], "interval declaration")
    expected_files = {"before.json", "after.json", "client.stdout", "client.stderr", "server.stdout", "server.stderr", "trace.txt", "counts.json"}
    require(set(state["files"]) == expected_files, "attempt file inventory")
    require({p.name for p in directory.iterdir()} == expected_files | {"attempt.json"}, "unexpected/missing attempt files")
    for name, digest in state["files"].items(): require(sha(directory / name) == digest, "attempt raw hash")
    port = state["port"]; require(type(port) is int and 1 <= port <= 65535, "server port")
    argv = [str(Path(plan["execution"]["plan_root"]) / "inputs/client"), str(port), "0", *[str(scenario[k]) for k in
            ("clients", "pipeline", "value_bytes", "profile_keys", "get_percent", "operations")], "independent-v1", "20261109", "count-only"]
    require(state["client_argv"] == argv, "client argv")
    wrapped = state["executed_client_argv"]
    require(len(wrapped) == len(argv) + 3 and wrapped[3:] == argv and wrapped[2].isdigit() and
            wrapped[0] == plan["execution"]["python"] and wrapped[1] == plan["execution"]["guard"], "guarded client argv")
    server = [str(Path(plan["execution"]["plan_root"]) / "inputs/work/bin/memcached-diagnostics"), "-l", "127.0.0.1", "-p", str(port),
              "-U", "0", "-m", "64", "-t", "4", "-u", plan["execution"]["account_name"],
              "-o", "worker_logbuf_size=1024,watcher_logbuf_size=4096"]
    require(state["server_argv"] == server, "server argv")
    require(type(state["server_returncode"]) is int and state["server_returncode"] in (0, -15) and (directory / "server.stdout").read_bytes() == b"", "server process/stdout")
    require(type(state["client_returncode"]) is int and state["client_returncode"] == 0 and (directory / "client.stderr").read_bytes() == b"", "client process/stderr")
    client = load_json(directory / "client.stdout")
    numeric_fields = ("operations", "errors", "workload_seed", "sample_every", "sample_cap_per_client",
                      "latency_sample_count", "latency_selected_count", "latency_dropped_count")
    require(all(type(client[k]) is int and client[k] >= 0 for k in numeric_fields), "client integer metadata")
    require(client["operations"] == scenario["operations"] and client["errors"] == 0, "client count/errors")
    require(all(client[k] == plan[k] for k in ("workload_mode", "workload_seed", "measurement_mode")), "client mode/seed")
    require(all(client[k] is None for k in ("p50_us", "p95_us", "p99_us", "max_us")), "count-only quantiles")
    require(all(client[k] == 0 for k in ("sample_every", "sample_cap_per_client", "latency_sample_count", "latency_selected_count", "latency_dropped_count")), "count-only sample counts")
    require(client["latency_valid"] is False and client["latency_scope"] == "unavailable", "count-only latency scope")
    # Incidental elapsed/rate/CPU fields are intentionally not analyzed.
    before, after = load_json(directory / "before.json"), load_json(directory / "after.json")
    def counter(value):
        require((type(value) is int and value >= 0) or
                (isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]*", value)), "canonical stats integer")
        return int(value)
    observed = {k: counter(after[k]) - counter(before[k]) for k in ("cmd_get", "cmd_set", "get_hits", "get_misses", "log_worker_dropped", "log_watcher_skipped", "lru_bumps_dropped", "moves_to_warm")}
    require(all(value >= 0 for value in observed.values()), "negative counter delta")
    require(observed["cmd_get"] == observed["get_hits"] == scenario["expected"]["get"] and observed["cmd_set"] == scenario["expected"]["set"], "observed aggregate GET/SET/hit counts")
    require(all(observed[k] == 0 for k in ("get_misses", "log_worker_dropped", "log_watcher_skipped", "lru_bumps_dropped")), "observed losses/misses")
    if scenario["mode"] == "watch_active":
        require(state["watcher"]["error"] is None and all(type(state["watcher"][key]) is int and state["watcher"][key] > 0 for key in ("bytes", "lines")), "watcher activity")
    else: require("watcher" not in state, "unexpected watcher")
    raw = (directory / "server.stderr").read_bytes(); start, end = state["trace_start_offset"], state["trace_end_offset"]
    require(type(start) is int and type(end) is int and 0 <= start < end <= len(raw), "trace offset bounds")
    require((start == 0 or raw[start-1:start] == b"\n") and raw[end-1:end] == b"\n", "trace line boundaries")
    trace = (directory / "trace.txt").read_bytes()
    require(trace == raw[start:end] and sha(directory / "trace.txt") == state["trace_sha256"], "trace bytes/hash")
    counts = strict_recount(trace)
    require(counts == load_json(directory / "counts.json"), "independent trace recount")
    if scenario["name"] == "write_heavy":
        require(observed["moves_to_warm"] > 0 and counts["lru_holds"] > 0 and counts["lru_takes"] > 0, "write protected coverage")
    return {"name": scenario["name"], "operations": scenario["operations"], "observed_aggregate_counters": observed,
            "expected_key_verb_multiset_sha256": scenario["expected"]["key_verb_multiset_sha256"], **counts}


def verify_frozen(root, plan_path):
    root, plan_path = Path(root).resolve(), Path(plan_path).resolve(); base = plan_path.parent
    plan = validate_plan(plan_path); run = load_json(root / "run.json")
    require(run["schema"] == plan["schema"] and run["plan_sha256"] == sha(plan_path) and run["status"] == "collected", "run/plan status/hash")
    names = [s["name"] for s in plan["scenarios"]]
    require(run["attempts"] == [{"name": name, "attempt": 1, "status": "collected"} for name in names], "duplicate/incomplete attempt grid")
    require({p.name for p in root.iterdir() if p.is_dir()} == set(names), "scenario directory grid")
    require({p.name for p in root.iterdir() if p.is_file()} <= {"run.json", "verification.json"}, "unexpected run file")
    rows = [verify_attempt(root / s["name"], s, plan, base) for s in plan["scenarios"]]
    return {"validated": True, "scenarios": 6, "timing_evidence": False, "latency_evidence": False,
            "mapping_scope": "independently reconstructed expected multiset; observed aggregate counters; per-key correctness relies on frozen client and its retained protocol tests",
            "snapshot_scope": "snapshot schema and byte-count records reconcile; payload digest truth is not independently recomputed",
            "plan_sha256": sha(plan_path), "rows": rows,
            "source_sha256": {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob("*")) if p.is_file() and p.name != "verification.json"}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--correctness-summary", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--validate-plan", action="store_true")
    args = parser.parse_args()
    if args.validate_plan:
        require(args.plan is not None, "--plan required")
        validate_plan(args.plan); print(json.dumps({"validated_plan": True, "sha256": sha(args.plan)}))
    elif args.plan:
        require(args.profile is not None, "--profile required")
        print(json.dumps(verify_frozen(args.profile, args.plan), indent=2))
    else:
        require(args.profile is not None and args.correctness_summary is not None, "legacy inputs required")
        print(json.dumps(verify(args.profile, args.correctness_summary), indent=2))
