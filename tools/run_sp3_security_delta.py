#!/usr/bin/env python3
"""Collect raw H1/H2 outcomes without guessing or filtering the verdicts.

Security-delta binaries contain fault hooks and sanitizers. They must never be
used as latency/throughput benchmarks. A separate verifier reads these files.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time
import traceback

from memcached_common import Client, Server
from nginx_common import Server as NginxServer, request as nginx_request
from test_memcached_deployment import activate_lru


H1 = [(1, 2, mode) for mode in (1, 2, 3, 4, 5, 6, 9, 10)] + [
    (3, 2, 7), (3, 2, 8)
]
H2_MEMCACHED = (11, 12)
H2_YAML = ("legitimate", "untracked", "revoked", "wrong_type",
           "same_type", "same_type_pinned")
H2_VARIANTS = ("h2-upstream", "h2-domain", "h2-extended", "h2-handle")
H1_NGINX = [(path, kind) for path in (1, 2) for kind in (1, 2, 3, 4, 5)] + [
    (2, 6), (3, 1), (3, 2), (3, 3), (3, 4)
]
H1_RSYNC = [(target, mode) for target in (1, 2, 3) for mode in (1, 2, 3, 4, 5)]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def exercise_memcached(server, role):
    """Capture protocol results even when a deliberately broken U aborts T."""
    outputs = {}
    if role == 3:
        try:
            activate_lru(server)
            outputs["lru_bump"] = "completed"
        except Exception as error:
            outputs["lru_bump"] = type(error).__name__ + ": " + str(error)
    else:
        try:
            with Client(server.port, timeout=2) as watcher:
                outputs["watch"] = watcher.command(b"watch fetchers mutations").decode(errors="replace")
                with Client(server.port, timeout=2) as client:
                    outputs["store"] = client.store(b"delta-key", b"value").decode(errors="replace")
                    outputs["get"] = str(client.get(b"delta-key"))
                try:
                    outputs["watch_record"] = watcher.line().decode(errors="replace")
                except (OSError, EOFError) as error:
                    outputs["watch_record"] = type(error).__name__
        except Exception as error:
            outputs["traffic_error"] = type(error).__name__ + ": " + str(error)

    # Permit the asynchronous LRU thread to act, but do not retry if it
    # behaves unexpectedly. Do not confuse intentional test teardown with a
    # process crash before observation.
    time.sleep(0.15)
    outputs["alive_before_probe"] = server.proc.poll() is None
    if outputs["alive_before_probe"]:
        try:
            with Client(server.port, timeout=2) as client:
                outputs["version"] = client.command(b"version").decode(errors="replace").startswith("VERSION ")
        except Exception as error:
            outputs["version_error"] = type(error).__name__ + ": " + str(error)
    return outputs, server.proc.poll()


def run_memcached(work, out, name, variant, *, role, target, mode):
    directory = out / "cases" / name
    directory.mkdir(parents=True, exist_ok=False)
    binary = work / "bin" / f"memcached-{variant}"
    record = {"case": name, "kind": "memcached", "variant": variant,
              "mode": mode, "role": role, "target": target,
              "binary_sha256": sha(binary), "status": "started"}
    protocol = {}
    start = time.monotonic()
    try:
        with Server(binary, directory, "server", trace=True, census=True,
                    fault={"role": role, "target": target, "fault": mode}) as server:
            protocol, process_code = exercise_memcached(server, role)
            record["exit_code_before_teardown"] = process_code
            record["alive_before_teardown"] = process_code is None
        record["status"] = "observed"
    except Exception:
        record["status"] = "harness_error"
        record["harness_error"] = traceback.format_exc()
    record["elapsed_seconds"] = time.monotonic() - start
    write_json(directory / "protocol.json", protocol)
    write_json(directory / "execution.json", record)
    for key, filename in (("stderr_sha256", "server.stderr"),
                          ("stdout_sha256", "server.stdout")):
        if (directory / filename).exists():
            record[key] = sha(directory / filename)
    record["execution_sha256"] = sha(directory / "execution.json")
    record["protocol_sha256"] = sha(directory / "protocol.json")
    print(json.dumps({"case": name, "status": record["status"],
                      "alive": record.get("alive_before_teardown")}), flush=True)
    return record


def run_yaml(work, out, name, policy, scenario):
    directory = out / "cases" / name
    directory.mkdir(parents=True, exist_ok=False)
    binary = work / "bin/yaml-t-domain-delta"
    command = [str(binary), policy, scenario]
    env = dict(os.environ, LC_ALL="C", ASAN_OPTIONS="detect_leaks=0:halt_on_error=1:abort_on_error=1",
               UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
    start = time.monotonic()
    record = {"case": name, "kind": "yaml_t_driver", "policy": policy,
              "scenario": scenario, "binary_sha256": sha(binary),
              "source_provenance": "project_authored_t", "command": command,
              "status": "started"}
    try:
        completed = subprocess.run(command, capture_output=True, timeout=40, env=env)
        (directory / "server.stdout").write_bytes(completed.stdout)
        (directory / "server.stderr").write_bytes(completed.stderr)
        record["exit_code_before_teardown"] = completed.returncode
        record["status"] = "observed"
    except Exception:
        record["status"] = "harness_error"
        record["harness_error"] = traceback.format_exc()
    record["elapsed_seconds"] = time.monotonic() - start
    write_json(directory / "execution.json", record)
    record["execution_sha256"] = sha(directory / "execution.json")
    for key, filename in (("stderr_sha256", "server.stderr"),
                          ("stdout_sha256", "server.stdout")):
        if (directory / filename).exists(): record[key] = sha(directory / filename)
    print(json.dumps({"case": name, "status": record["status"],
                      "exit": record.get("exit_code_before_teardown")}), flush=True)
    return record


def run_yaml_h1(yaml_work, out, name, variant, mode):
    directory = out / "cases" / name
    directory.mkdir(parents=True, exist_ok=False)
    binary = yaml_work / f"yaml-{variant}-fault"
    policy = "rlbox_only" if variant == "rlbox" else "extended_sp3"
    fixture = out / "h1-yaml-input.yaml"
    command = [str(binary), policy, str(fixture), "1"]
    if mode: command.append(str(mode))
    env = dict(os.environ, LC_ALL="C", ASAN_OPTIONS="detect_leaks=0:halt_on_error=1:abort_on_error=1",
               UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
    record = {"case": name, "kind": "yaml_h1", "variant": variant, "mode": mode,
              "binary_sha256": sha(binary), "command": command, "status": "started"}
    start = time.monotonic()
    try:
        completed = subprocess.run(command, capture_output=True, timeout=40, env=env)
        (directory / "server.stdout").write_bytes(completed.stdout)
        (directory / "server.stderr").write_bytes(completed.stderr)
        record["exit_code_before_teardown"] = completed.returncode
        record["status"] = "observed"
    except Exception:
        record["status"] = "harness_error"
        record["harness_error"] = traceback.format_exc()
    record["elapsed_seconds"] = time.monotonic() - start
    write_json(directory / "execution.json", record)
    record["execution_sha256"] = sha(directory / "execution.json")
    for key, filename in (("stderr_sha256", "server.stderr"),
                          ("stdout_sha256", "server.stdout")):
        if (directory / filename).exists(): record[key] = sha(directory / filename)
    print(json.dumps({"case": name, "status": record["status"],
                      "exit": record.get("exit_code_before_teardown")}), flush=True)
    return record


def run_nginx_h1(nginx_work, out, name, variant, path, kind):
    directory = out / "cases" / name
    directory.mkdir(parents=True, exist_ok=False)
    binary = nginx_work / "bin" / f"nginx-security-{variant}"
    record = {"case": name, "kind": "nginx_h1", "variant": variant,
              "fault_path": path, "fault_kind": kind, "binary_sha256": sha(binary),
              "status": "started"}
    protocol = {}
    start = time.monotonic()
    if path == 3:
        config = directory / "invalid.conf"
        config.write_text('events {} http { server { location ~ "[" { return 200; } } }\n')
        env = dict(os.environ, INTERSPEC_NGINX_FAULT_PATH="3",
                   INTERSPEC_NGINX_FAULT_KIND=str(kind))
        command = [str(binary), "-t", "-p", str(directory.resolve()) + "/",
                   "-c", str(config.resolve())]
        try:
            completed = subprocess.run(command, capture_output=True, timeout=30, env=env)
            (directory / "server.stdout").write_bytes(completed.stdout)
            (directory / "server.stderr").write_bytes(completed.stderr)
            record["exit_code_before_teardown"] = completed.returncode
            record["status"] = "observed"
        except Exception:
            record["status"] = "harness_error"
            record["harness_error"] = traceback.format_exc()
    else:
        try:
            with NginxServer(binary, directory, wait=False,
                             fault=(path, kind) if kind else None, trace=True) as server:
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline and server.proc.poll() is None:
                    try:
                        protocol["health"] = nginx_request(server.port, "/health")
                        break
                    except Exception:
                        time.sleep(0.05)
                if server.proc.poll() is None:
                    try:
                        protocol["route"] = nginx_request(server.port, "/items/123/alpha")
                    except Exception as error:
                        protocol["route_error"] = type(error).__name__ + ": " + str(error)
                time.sleep(0.2)
                record["exit_code_before_teardown"] = server.proc.poll()
                record["alive_before_teardown"] = server.proc.poll() is None
            record["status"] = "observed"
        except Exception:
            record["status"] = "harness_error"
            record["harness_error"] = traceback.format_exc()
        # Nginx's local helper writes both output streams to one raw file.
        combined = directory / "stderr.log"
        if combined.exists():
            raw = combined.read_bytes()
            (directory / "server.stderr").write_bytes(raw)
            (directory / "server.stdout").write_bytes(b"")
    record["elapsed_seconds"] = time.monotonic() - start
    write_json(directory / "protocol.json", protocol)
    write_json(directory / "execution.json", record)
    record["execution_sha256"] = sha(directory / "execution.json")
    record["protocol_sha256"] = sha(directory / "protocol.json")
    for key, filename in (("stderr_sha256", "server.stderr"),
                          ("stdout_sha256", "server.stdout")):
        if (directory / filename).exists(): record[key] = sha(directory / filename)
    print(json.dumps({"case": name, "status": record["status"],
                      "alive": record.get("alive_before_teardown")}), flush=True)
    return record


def rsync_output_snapshot(root):
    result = {}
    for file in sorted(root.rglob("*")):
        key = str(file.relative_to(root))
        if file.is_symlink():
            result[key] = {"kind": "symlink", "target": os.readlink(file)}
        elif file.is_file():
            result[key] = {"kind": "file", "bytes": file.stat().st_size,
                           "sha256": sha(file)}
        else:
            result[key] = {"kind": "directory"}
    return result


def run_rsync_h1(rsync_work, out, name, variant, mode, target):
    directory = out / "cases" / name
    directory.mkdir(parents=True, exist_ok=False)
    canary = target == 6
    binary = rsync_work / (f"copyback-security-{variant}" if canary else
                           f"rsync-security-{variant}")
    source = out / "h1-rsync-source"
    destination = directory / "dst"
    if not canary: destination.mkdir()
    command = ([str(binary)] if canary else [str(binary), "-aH", "--block-size=1024",
               "--max-size=1M", str(source) + "/", str(destination) + "/"])
    env = dict(os.environ, LC_ALL="C", INTERSPEC_TEST_FAULT=str(mode),
               INTERSPEC_TEST_TARGET=str(target if not canary else 1),
               INTERSPEC_TRACE="1", ASAN_OPTIONS="detect_leaks=0:halt_on_error=1:abort_on_error=1",
               UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
    record = {"case": name, "kind": "rsync_h1", "mode": mode, "target": target,
              "variant": variant, "binary_sha256": sha(binary), "command": command,
              "status": "started"}
    start = time.monotonic()
    try:
        def no_core(): resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        completed = subprocess.run(command, capture_output=True, timeout=60,
                                   env=env, preexec_fn=no_core)
        (directory / "server.stdout").write_bytes(completed.stdout)
        (directory / "server.stderr").write_bytes(completed.stderr)
        record["exit_code_before_teardown"] = completed.returncode
        record["status"] = "observed"
    except Exception:
        record["status"] = "harness_error"
        record["harness_error"] = traceback.format_exc()
    record["elapsed_seconds"] = time.monotonic() - start
    manifest = {} if canary else rsync_output_snapshot(destination)
    write_json(directory / "filesystem.json", manifest)
    write_json(directory / "execution.json", record)
    record["execution_sha256"] = sha(directory / "execution.json")
    record["filesystem_sha256"] = sha(directory / "filesystem.json")
    for key, filename in (("stderr_sha256", "server.stderr"),
                          ("stdout_sha256", "server.stdout")):
        if (directory / filename).exists(): record[key] = sha(directory / filename)
    print(json.dumps({"case": name, "status": record["status"],
                      "exit": record.get("exit_code_before_teardown")}), flush=True)
    return record


def repeat_correctness_gate(root, work, out, case):
    """Run the existing 50-case suite after a pair, preserving failures."""
    directory = out / "gates" / case
    directory.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, str(root / "tools/test_memcached_deployment.py"),
               "--work", str(work), "--out", str(directory / "correctness")]
    with (directory / "gate.log").open("wb") as log:
        try:
            proc = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                  timeout=1800)
            code = proc.returncode
        except subprocess.TimeoutExpired:
            code = "timeout"
    summary_path = directory / "correctness/summary.json"
    gate = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    record = {"case": case, "exit_code": code, "passed": gate.get("passed"),
              "total": gate.get("total"), "gate_log_sha256": sha(directory / "gate.log"),
              "gate_summary_sha256": sha(summary_path) if summary_path.exists() else None}
    write_json(directory / "gate-execution.json", record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=Path("/tmp/interspec-memcached-deployment"))
    parser.add_argument("--yaml-work", type=Path, default=Path("/tmp/interspec-yaml-libyaml"))
    parser.add_argument("--nginx-work", type=Path, default=Path("/tmp/interspec-nginx-deployment"))
    parser.add_argument("--rsync-work", type=Path, default=Path("/tmp/interspec-rlbox-wasm2c"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--correctness-summary", type=Path,
                        help="required for memcached experiments; optional for independent boundaries")
    parser.add_argument("--post-case-gate", action="store_true",
                        help="rerun all 50 correctness cases after every H1/H2 memcached scenario")
    parser.add_argument("--scope", choices=("all", "h1", "h1_yaml", "h1_nginx", "h1_rsync", "h2_memcached", "h2_yaml"), default="all")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    os.environ.setdefault("ASAN_OPTIONS", "detect_leaks=0:halt_on_error=1:abort_on_error=1")
    os.environ.setdefault("UBSAN_OPTIONS", "halt_on_error=1:print_stacktrace=1")
    if args.out.exists() and any(args.out.iterdir()):
        parser.error("output directory is nonempty; preserve prior unexpected/failed runs")
    args.out.mkdir(parents=True, exist_ok=True)
    needs_gate = args.scope in ("all", "h1", "h2_memcached")
    if needs_gate and not args.correctness_summary:
        parser.error("memcached experiments require the prior 50-case correctness summary")
    if args.correctness_summary:
        gate = json.loads(args.correctness_summary.read_text())
        if gate.get("passed") != 50 or gate.get("total") != 50:
            parser.error("correctness summary must show all 50 cases passed")
    gate_sha = sha(args.correctness_summary) if args.correctness_summary else "not_applicable"

    entries = []
    gates = []
    def save():
        write_json(args.out / "collection.json", {"schema": 1,
            "scope": args.scope, "post_case_gate": args.post_case_gate,
            "initial_correctness_gate_sha256": gate_sha,
            "cases": entries, "post_case_gates": gates})

    manifest = {"schema": 1, "purpose": "sp3_security_delta_no_timing",
                "host": platform.platform(), "python": sys.version,
                "project_commit": subprocess.check_output(
                    ["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
                "project_dirty": bool(subprocess.check_output(
                    ["git", "-C", str(root), "status", "--porcelain"])),
                "build_manifest_sha256": sha(args.work / "security-asan/build-manifest.json")
                    if needs_gate else "not_applicable",
                "initial_correctness_gate_sha256": gate_sha,
                "source_hashes": {str(p.relative_to(root)): sha(p) for p in [
                    root / "include/interspec/runtime.h",
                    root / "integration/memcached_server/bridge.cpp",
                    root / "integration/memcached_server/bipbuffer_u.c",
                    root / "integration/yaml_libyaml/yaml_t_domain_delta.cpp",
                    root / "integration/yaml_libyaml/yaml_app_bench.cpp",
                    root / "integration/yaml_libyaml/yaml_app_wasm.c",
                    root / "integration/nginx_server/bridge.cpp",
                    root / "integration/nginx_server/pcre_u.c",
                    root / "integration/rsync_popt/p4c_bridge.cpp",
                    root / "integration/rsync_popt/p4c_bridge_untrusted.c",
                    root / "integration/rsync_popt/popt_typed_shim_wasm.c"]}}
    write_json(args.out / "provenance.json", manifest)
    save()

    if args.scope in ("all", "h1"):
        for role, target, mode in H1:
            case = f"h1-r{role}-t{target}-m{mode}"
            for variant, injected in (("h1-rlbox", 0),
                                      ("h1-rlbox", mode + 100),
                                      ("h1-rlbox", mode),
                                      ("h1-extended", mode)):
                label = "legitimate" if injected == 0 else "content-control" if injected > 100 else "fault"
                name = f"{case}-{variant}-{label}"
                entries.append(run_memcached(args.work, args.out, name, variant,
                                             role=role, target=target, mode=injected))
                save()
            if args.post_case_gate:
                gates.append(repeat_correctness_gate(root, args.work, args.out, case))
                save()

    if args.scope in ("all", "h1_yaml"):
        (args.out / "h1-yaml-input.yaml").write_text("key: value\n")
        for mode in (1, 2, 3, 4, 5):
            for variant, fault in (("rlbox", 0), ("rlbox", mode), ("typed", mode)):
                label = "legitimate" if fault == 0 else "fault"
                name = f"h1-yaml-m{mode}-{variant}-{label}"
                entries.append(run_yaml_h1(args.yaml_work, args.out, name, variant, fault))
                save()

    if args.scope in ("all", "h1_nginx"):
        for path, kind in H1_NGINX:
            for variant, fault in (("rlbox", 0), ("rlbox", kind), ("extended", kind)):
                label = "legitimate" if fault == 0 else "fault"
                name = f"h1-nginx-p{path}-k{kind}-{variant}-{label}"
                entries.append(run_nginx_h1(args.nginx_work, args.out, name,
                                            variant, path, fault))
                save()

    if args.scope in ("all", "h1_rsync"):
        source = args.out / "h1-rsync-source"
        source.mkdir()
        (source / "file.txt").write_text("InterSpec SP3 security-delta workload\n")
        (source / "binary.bin").write_bytes(bytes(range(256)) * 128)
        for target, mode in [*H1_RSYNC, (6, 6)]:
            for variant, fault in (("rlbox", 0), ("rlbox", mode), ("extended", mode)):
                label = "legitimate" if fault == 0 else "fault"
                name = f"h1-rsync-t{target}-m{mode}-{variant}-{label}"
                entries.append(run_rsync_h1(args.rsync_work, args.out, name,
                                            variant, fault, target))
                save()

    if args.scope in ("all", "h2_memcached"):
        for variant in H2_VARIANTS:
            entries.append(run_memcached(args.work, args.out, f"h2-{variant}-legitimate",
                                         variant, role=3, target=2, mode=0))
            save()
        for mode in H2_MEMCACHED:
            case = f"h2-lru-m{mode}"
            for variant in H2_VARIANTS:
                entries.append(run_memcached(args.work, args.out, f"{case}-{variant}",
                                             variant, role=3, target=2, mode=mode))
                save()
            if args.post_case_gate:
                gates.append(repeat_correctness_gate(root, args.work, args.out, case))
                save()

    if args.scope in ("all", "h2_yaml"):
        for scenario in H2_YAML:
            for policy in ("domain_sp3", "extended_sp3"):
                name = f"h2-yaml-{scenario}-{policy}"
                entries.append(run_yaml(args.work, args.out, name, policy, scenario))
                save()

    print(f"Collected {len(entries)} raw executions and {len(gates)} post-case gates; run independent verifier", flush=True)


if __name__ == "__main__":
    main()
