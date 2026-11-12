#!/usr/bin/env python3
"""Frozen, one-pass ordinary diagnostics. Never a timing or capacity experiment."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import platform
import pwd
import shutil
import subprocess
import sys
import time

from benchmark_memcached import Watcher
from benchmark_memcached_matrix import SCENARIOS
from memcached_common import Client, Server, guarded_command

SCHEMA = "corrected-profile-v1"
INTERVAL = ("preload, pre-traffic 0.5 second drain, watcher setup/settle and 0.2 second pause excluded; "
            "trace begins after before-stats, includes fixed client traffic, post-traffic watcher settle "
            "when enabled (0.4 second quiet rule, 5 second ceiling), then 0.5 second drain; "
            "trace ends before after-stats; incidental client timings are raw provenance only")
HARNESS = ["tools/profile_memcached_checks.py", "tools/verify_memcached_profile.py",
           "tools/benchmark_memcached.py", "tools/benchmark_memcached_matrix.py",
           "tools/memcached_common.py", "tools/process_guard.py"]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def save(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
    os.replace(temp, path); sync_dir(path.parent)


def sync_tree(root):
    for path in Path(root).rglob("*"):
        if path.is_file():
            with path.open("rb") as stream: os.fsync(stream.fileno())
    for path in sorted((p for p in Path(root).rglob("*") if p.is_dir()), reverse=True): sync_dir(path)
    sync_dir(root)


def expected_work(operations, keys, percent, seed):
    """Independent Python reconstruction, not an observed wire transcript."""
    mask = (1 << 64) - 1
    def mix(value):
        value = (value + 0x9e3779b97f4a7c15) & mask
        value = ((value ^ (value >> 30)) * 0xbf58476d1ce4e5b9) & mask
        value = ((value ^ (value >> 27)) * 0x94d049bb133111eb) & mask
        return value ^ (value >> 31)
    def draw(index, domain, bound):
        word = mix(index ^ mix(seed ^ domain))
        threshold = ((1 << 64) - bound) % bound
        while word < threshold: word = mix(word)
        return word % bound
    counts = [[key, 0, 0] for key in range(keys)]
    for index in range(operations):
        key = draw(index, 0x243f6a8885a308d3, keys)
        get = draw(index, 0x13198a2e03707344, 100) < percent
        counts[key][1 if get else 2] += 1
    encoded = json.dumps(counts, separators=(",", ":")).encode()
    gets = sum(row[1] for row in counts)
    return {"get": gets, "set": operations - gets, "key_verb_multiset": counts,
            "key_verb_multiset_sha256": hashlib.sha256(encoded).hexdigest(),
            "scope": "expected key/verb multiset; actual server observations are aggregate counters only"}


def prepare(args):
    root = Path(__file__).resolve().parents[1]
    source = args.client_source_root.resolve()
    provenance = json.loads(args.client_provenance.read_text())
    if digest(args.client_binary) != provenance["binary_sha256"]: raise ValueError("client provenance binary")
    for rel, expected in provenance["source_sha256"].items():
        if digest(source / rel) != expected: raise ValueError("client provenance source")
    revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "-C", str(source), "status", "--porcelain"], text=True)
    if revision != provenance["revision"] or dirty: raise ValueError("client revision/clean-tree identity")
    gate = json.loads(args.correctness_summary.read_text())
    manifest = json.loads((args.work / "build-manifest.json").read_text())
    diagnostic = args.work / "bin/memcached-diagnostics"
    if gate["passed"] != 50 or gate["total"] != 50: raise ValueError("50-case gate")
    if digest(diagnostic) != gate["binary_sha256"][diagnostic.name] or digest(diagnostic) != manifest["binary_sha256"][diagnostic.name]:
        raise ValueError("diagnostic identity")
    if len(gate.get("cases", [])) != 50 or not all(c.get("pass") is True for c in gate["cases"]):
        raise ValueError("50-case gate cases")
    frozen = args.plan_directory.resolve(); frozen.mkdir(parents=True, exist_ok=False)
    files = {}
    def copy(src, relative):
        dst = frozen / relative; dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst); files[relative] = digest(dst)
    copy(args.client_binary, "inputs/client")
    copy(diagnostic, "inputs/work/bin/memcached-diagnostics")
    copy(args.work / "build-manifest.json", "inputs/work/build-manifest.json")
    copy(args.correctness_summary, "inputs/correctness.json")
    copy(args.client_provenance, "inputs/client-provenance.json")
    for rel in provenance["source_sha256"]: copy(source / rel, "sources/client/" + rel)
    for rel in HARNESS: copy(root / rel, "sources/harness/" + rel)
    for rel in ("tests/memcached_profile_evidence.py", "tests/memcached_corrected_profile.py"):
        copy(root / rel, "sources/harness/" + rel)
    prior = args.client_validation_directory.resolve()
    validation = json.loads((prior / "provenance.json").read_text())
    if validation["candidate_commit"] != revision or validation["candidate_source_sha256"] != {
            rel: digest(source / rel) for rel in validation["candidate_source_sha256"]}:
        raise ValueError("retained client validation source binding")
    for rel in ("provenance.json", "release-reproduction-functional.log", "COMMANDS.md"):
        copy(prior / rel, "inputs/client-validation/" + rel)
    for rel in validation["candidate_source_sha256"]:
        if "sources/client/" + rel not in files: copy(source / rel, "sources/client/" + rel)
    for rel, field in (("integration/memcached_server/bridge.cpp", "bridge_source_sha256"),
                       ("integration/memcached_server/bipbuffer_u.c", "untrusted_source_sha256")):
        if digest(source / rel) != manifest[field]: raise ValueError("server source binding")
        copy(source / rel, "sources/server/" + rel)
    scenarios = []
    for scenario in SCENARIOS:
        row = dict(scenario)
        row["operations"] = 200000 if row["name"] == "write_heavy" else 5000
        row["profile_keys"] = 10000 if row["name"] == "write_heavy" else 2048
        row["expected"] = expected_work(row["operations"], row["profile_keys"], row["get_percent"], 20261109)
        scenarios.append(row)
    plan = {"schema": SCHEMA, "scenarios": scenarios, "workload_mode": "independent-v1",
            "workload_seed": 20261109, "measurement_mode": "count-only", "files": files,
            "interval": INTERVAL, "attempt_policy": "one attempt per scenario; no resume, replacement or coverage-seeking retries",
            "interpretation": "ordinary functional/profile reconciliation only; no timing/capacity/latency conclusions",
            "out": str(args.out.resolve()), "client_revision": revision,
            "execution": {"plan_root": str(frozen), "harness_root": str(root),
                          "python": sys.executable, "guard": str(root / "tools/process_guard.py"),
                          "account_name": pwd.getpwuid(os.getuid()).pw_name, "uid": os.getuid()},
            "original_inputs": {"client": str(args.client_binary.resolve()), "client_source": str(source),
                "provenance": str(args.client_provenance.resolve()), "gate": str(args.correctness_summary.resolve()), "work": str(args.work.resolve())}}
    save(frozen / "plan.json", plan); sync_tree(frozen)
    return {"plan": str(frozen / "plan.json"), "sha256": digest(frozen / "plan.json"), "collected": False}


def check_plan(plan_path):
    from verify_memcached_profile import validate_plan
    plan = validate_plan(plan_path)
    base = plan_path.parent
    if str(base) != plan["execution"]["plan_root"]: raise ValueError("collection requires original frozen execution root")
    for rel in HARNESS:
        if digest(Path(__file__).resolve().parents[1] / rel) != plan["files"]["sources/harness/" + rel]:
            raise ValueError("collector live harness differs from freeze: " + rel)
    return plan, base


def summarize(trace):
    checks, calls, into_u, from_u, handles = (Counter() for _ in range(5))
    runtime = 0
    for line in trace.decode().splitlines():
        if not line.startswith("INTERSPEC "): continue
        fields = dict(token.split("=", 1) for token in line.split()[1:])
        event, result = fields["event"], fields["result"]
        if event == "check" and result == "ok": runtime += 1
        elif result == "sp3_ok": checks[event] += 1
        if event == "sandbox_call": calls[result] += 1
        if event == "copy_into_u": into_u[result] += int(fields["requested"])
        if event == "copy_from_u": from_u[result] += int(fields["requested"])
        if event in ("lru_hold", "lru_take") and result == "ok": handles[event] += 1
    return {"runtime_checks": runtime, "check_operations": dict(checks),
            "sandbox_call_functions": dict(calls), "copy_into_u_operations": dict(into_u),
            "copy_from_u_operations": dict(from_u), "sandbox_calls": sum(calls.values()),
            "bytes_into_u": sum(into_u.values()), "bytes_from_u": sum(from_u.values()),
            "lru_holds": handles["lru_hold"], "lru_takes": handles["lru_take"]}


def collect_one(plan, base, scenario, directory):
    directory.mkdir(exist_ok=False); sync_dir(directory.parent)
    state = {"name": scenario["name"], "status": "started", "attempt": 1, "interval": plan["interval"]}
    save(directory / "attempt.json", state)
    watcher = None
    try:
        with Server(base / "inputs/work/bin/memcached-diagnostics", directory, "server", trace=True,
                    guarded=True, extra=["-o", "worker_logbuf_size=1024,watcher_logbuf_size=4096"]) as server:
            state.update(server_argv=server.args, port=server.port)
            save(directory / "attempt.json", state)
            try:
                with Client(server.port) as conn:
                    for key in range(scenario["profile_keys"]):
                        if conn.store(f"bench{key}".encode(), b"x" * scenario["value_bytes"]) != b"STORED\r\n":
                            raise ValueError("preload response")
                time.sleep(.5)
                if scenario["mode"] == "watch_active":
                    watcher = Watcher(server.port); watcher.settle()
                time.sleep(.2)
                with Client(server.port) as conn: before = conn.stats()
                save(directory / "before.json", before)
                state["trace_start_offset"] = server.logpath.stat().st_size
                argv = [str(base / "inputs/client"), str(server.port), "0", str(scenario["clients"]),
                        str(scenario["pipeline"]), str(scenario["value_bytes"]), str(scenario["profile_keys"]),
                        str(scenario["get_percent"]), str(scenario["operations"]), plan["workload_mode"],
                        str(plan["workload_seed"]), plan["measurement_mode"]]
                state.update(client_argv=argv, executed_client_argv=guarded_command(argv))
                save(directory / "attempt.json", state)
                with (directory / "client.stdout").open("wb") as out, (directory / "client.stderr").open("wb") as err:
                    try:
                        process = subprocess.run(state["executed_client_argv"], stdout=out, stderr=err, timeout=120, check=False)
                        state["client_returncode"] = process.returncode
                    finally:
                        out.flush(); err.flush(); os.fsync(out.fileno()); os.fsync(err.fileno())
                save(directory / "attempt.json", state)
                if process.returncode: raise ValueError("client process failed")
                if watcher: watcher.settle()
                time.sleep(.5)
                state["trace_end_offset"] = server.logpath.stat().st_size
                save(directory / "attempt.json", state)
                with Client(server.port) as conn: after = conn.stats()
                save(directory / "after.json", after)
            finally:
                if watcher:
                    watcher.close()
                    state["watcher"] = {"bytes": watcher.bytes, "lines": watcher.lines, "error": watcher.error,
                                        "scope": "complete watcher connection through joined close; includes setup and after-stats"}
                    save(directory / "attempt.json", state)
                    if watcher.error is not None: raise ValueError("final watcher error: " + watcher.error)
        state["server_returncode"] = server.proc.returncode
        sync_tree(directory)
        raw = (directory / "server.stderr").read_bytes()
        trace = raw[state["trace_start_offset"]:state["trace_end_offset"]]
        with (directory / "trace.txt").open("wb") as stream:
            stream.write(trace); stream.flush(); os.fsync(stream.fileno())
        state["trace_sha256"] = digest(directory / "trace.txt")
        save(directory / "counts.json", summarize(trace))
        state["status"] = "collected"
    except Exception as error:
        state["status"] = "failed"
        state["failure"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        sync_tree(directory)
        state["files"] = {str(p.relative_to(directory)): digest(p) for p in directory.rglob("*")
                          if p.is_file() and p.name not in ("attempt.json", "attempt.json.tmp")}
        save(directory / "attempt.json", state)
    if state["status"] == "collected":
        try:
            from verify_memcached_profile import verify_attempt
            verify_attempt(directory, scenario, plan, base)
        except Exception as error:
            state["status"] = "failed"
            state["failure"] = {"type": type(error).__name__, "message": "validation: " + str(error)}
            save(directory / "attempt.json", state)
    return state


def collect(plan_path):
    plan, base = check_plan(plan_path)
    if any(key.startswith("INTERSPEC_") for key in os.environ): raise ValueError("unexpected INTERSPEC environment")
    out = Path(plan["out"]); out.mkdir(parents=True, exist_ok=False); sync_dir(out.parent)
    ledger = {"schema": SCHEMA, "plan_sha256": digest(plan_path), "status": "running", "attempts": [],
              "host": platform.uname()._asdict()}
    save(out / "run.json", ledger)
    for scenario in plan["scenarios"]:
        state = collect_one(plan, base, scenario, out / scenario["name"])
        ledger["attempts"].append({"name": scenario["name"], "attempt": 1, "status": state["status"]})
        save(out / "run.json", ledger)
    ledger["status"] = "collected" if all(r["status"] == "collected" for r in ledger["attempts"]) else "failed"
    save(out / "run.json", ledger)
    from verify_memcached_profile import verify_frozen
    try:
        result = verify_frozen(out, plan_path)
    except Exception as error:
        ledger["status"] = "failed"
        ledger["validation_failure"] = {"type": type(error).__name__, "message": str(error)}
        save(out / "run.json", ledger)
        raise
    save(out / "verification.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(allow_abbrev=False)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare", allow_abbrev=False)
    for name in ("plan-directory", "out", "client-binary", "client-provenance", "client-source-root", "client-validation-directory", "work", "correctness-summary"):
        prep.add_argument("--" + name, type=Path, required=True)
    run = sub.add_parser("collect", allow_abbrev=False); run.add_argument("--plan", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args) if args.command == "prepare" else collect(args.plan.resolve())
    print(json.dumps(result, indent=2))


if __name__ == "__main__": main()
