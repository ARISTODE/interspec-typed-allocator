#!/usr/bin/env python3
"""Per-policy cost on the four original registry boundaries (tracker item P6).

For one boundary, measures the InterSpec binary with each policy alone, with
all policies on and with all off, and the RLBox-only binary for reference. One
repetition measures every configuration once, in an order drawn from a seeded
generator, so every configuration is paired with the others inside each
repetition. The policies are selected with the run-time switches
INTERSPEC_SP1, INTERSPEC_SP2 and INTERSPEC_SP3 (tracker items I1 to I4).

Each measurement validates the result of the work it timed (file contents for
rsync, the parse hash for yaml, per-response validation for nginx, server and
client operation counts and loss counters for memcached). One invalid
measurement fails the run. Raw samples are written as they are taken.

Subcommands: rsync, yaml, memcached, nginx.
"""

import argparse
import csv
import filecmp
import hashlib
import json
import os
import platform
import random
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

SWITCHES = ("INTERSPEC_SP1", "INTERSPEC_SP2", "INTERSPEC_SP3")


def configurations(policies):
    """name -> (binary key, switch values or None)."""
    result = {"rlbox-only": ("rlbox-only", None),
              "interspec-all-off": ("interspec", ("0", "0", "0"))}
    for policy in policies:
        index = ("sp1", "sp2", "sp3").index(policy)
        result[f"interspec-{policy}"] = (
            "interspec", tuple("1" if i == index else "0" for i in range(3)))
    result["interspec-all-on"] = (
        "interspec", tuple("1" if p in policies else "0" for p in ("sp1", "sp2", "sp3")))
    return result


def policy_env(switches, report=False):
    env = {k: v for k, v in os.environ.items()
           if k not in SWITCHES and k != "INTERSPEC_POLICY_REPORT"
           and not k.startswith("INTERSPEC_TEST_")}
    env["LC_ALL"] = "C"
    if switches:
        env.update(dict(zip(SWITCHES, switches)))
        if report:
            env["INTERSPEC_POLICY_REPORT"] = "1"
    return env


class SwitchedEnvironment:
    """The server helpers copy os.environ; set the switches around their start."""

    def __init__(self, switches, report=False):
        self.target = policy_env(switches, report)

    def __enter__(self):
        self.saved = dict(os.environ)
        os.environ.clear()
        os.environ.update(self.target)

    def __exit__(self, *unused):
        os.environ.clear()
        os.environ.update(self.saved)


def machine():
    model = ""
    for line in Path("/proc/cpuinfo").read_text().splitlines():
        if line.startswith("model name"):
            model = line.split(":", 1)[1].strip()
            break
    memory = next(l for l in Path("/proc/meminfo").read_text().splitlines()
                  if l.startswith("MemTotal"))
    return {"cpu_model": model, "logical_cpus": os.cpu_count(),
            "memory": memory.split(":")[1].strip(), "kernel": platform.release(),
            "loadavg": Path("/proc/loadavg").read_text().strip()}


def expected_report(switches):
    return f"sp1={switches[0]} sp2={switches[1]} sp3={'full' if switches[2] == '1' else 'off'}"


# --- rsync/popt -------------------------------------------------------------

class Rsync:
    unit, higher_is_better = "ns", False
    workloads = ("option_parse", "file_sync_194mb")

    def __init__(self, a):
        self.binaries = {"rlbox-only": a.rlbox_only, "interspec": a.interspec}
        self.cpu = a.cpu
        self.data = a.scratch / "data"
        self.src, self.dst = self.data / "src", self.data / "dst"
        self.backup = a.scratch / "backup"
        for path in (self.src, self.dst, self.backup):
            path.mkdir(parents=True, exist_ok=True)
        (self.src / "input.txt").write_text("InterSpec P11 wasm2c performance\n")
        big = self.src / "sync-194mb.bin"
        if not big.exists() or big.stat().st_size != 194 << 20:
            with big.open("wb") as handle:
                handle.truncate(194 << 20)
        self.parameters = {"file": "194 MiB of zero bytes, as in P4", "cpu": a.cpu}

    def arguments(self, workload):
        if workload == "option_parse":
            return [f"--backup-dir={self.backup}", "--max-size=1M", "--block-size=1024",
                    "--version"]
        return ["-a", "--checksum", "--block-size=1024", f"{self.src}/", f"{self.dst}/"]

    def measure(self, workload, binary, switches, directory, report=False):
        if workload == "file_sync_194mb":
            shutil.rmtree(self.dst)
            self.dst.mkdir()
        command = ["taskset", "-c", str(self.cpu), str(self.binaries[binary])] + \
            self.arguments(workload)
        start = time.perf_counter_ns()
        done = subprocess.run(command, env=policy_env(switches, report),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        elapsed = time.perf_counter_ns() - start
        valid = done.returncode == 0
        if workload == "file_sync_194mb" and valid:
            names = sorted(os.listdir(self.src))
            valid = sorted(os.listdir(self.dst)) == names and all(
                filecmp.cmp(self.src / n, self.dst / n, shallow=False) for n in names)
        result = (hashlib.sha256(done.stdout).hexdigest() if workload == "option_parse"
                  else "files equal to source")
        return {"value": elapsed, "valid": valid, "result": result,
                "stderr": done.stderr.decode(errors="replace")}


# --- yaml/libyaml -----------------------------------------------------------

class Yaml:
    unit, higher_is_better = "ns", False
    workloads = ("yaml_parse_1mb",)

    def __init__(self, a):
        from yaml_measurement_validation import (DOCUMENT_SHA256, expected_hash, parse_line)
        self.parse_line = parse_line
        self.binaries = {"rlbox-only": a.rlbox_only, "interspec": a.interspec}
        self.input, self.iterations, self.cpu = a.input, a.iterations, a.cpu
        self.data = a.input.read_bytes()
        if hashlib.sha256(self.data).hexdigest() != DOCUMENT_SHA256:
            sys.exit("input differs from the fixed YAML workload")
        # The validator of the four-variant harness also fixes the number of
        # checks, which here depends on the SP3 switch; everything else is
        # checked the same way.
        self.expected = {"iterations": a.iterations, "input_bytes": len(self.data),
                         "events": 518 * a.iterations, "scalars": 512 * a.iterations,
                         "scalar_bytes": 1025536 * a.iterations}
        self.expected_hash = expected_hash(a.iterations)
        self.parameters = {"input": str(a.input), "iterations": a.iterations, "cpu": a.cpu,
                           "input_sha256": DOCUMENT_SHA256}

    def measure(self, workload, binary, switches, directory, report=False):
        mode = "rlbox_only" if binary == "rlbox-only" else "extended_sp3"
        command = ["taskset", "-c", str(self.cpu), str(self.binaries[binary]), mode,
                   str(self.input), str(self.iterations)]
        done = subprocess.run(command, env=policy_env(switches, report), text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            row = self.parse_line(done.stdout)
            valid = (done.returncode == 0 and row["mode"] == mode
                     and all(int(row[k]) == v for k, v in self.expected.items())
                     and row["hash"] == self.expected_hash)
            if binary == "interspec":
                sp3_on = switches[2] == "1"
                valid = valid and int(row["checks"]) == (512 * self.iterations if sp3_on else 0)
        except Exception as error:  # an invalid line fails the measurement
            return {"value": 0, "valid": False, "result": f"invalid: {error}",
                    "stderr": done.stderr}
        result = " ".join(f"{k}={row[k]}" for k in
                          ("iterations", "input_bytes", "events", "scalars", "scalar_bytes", "hash"))
        return {"value": int(row["elapsed_ns"]), "valid": valid, "result": result,
                "checks": int(row["checks"]), "stderr": done.stderr}


# --- memcached/bipbuffer ----------------------------------------------------

class Memcached:
    unit, higher_is_better = "operations_per_s", True
    workloads = ("watch_moderate",)

    def __init__(self, a):
        self.work, self.client, self.seconds, self.warmup = a.work, a.client, a.seconds, a.warmup
        self.server_cpus, self.client_cpus = a.server_cpus, a.client_cpus
        # The watch_moderate scenario of tools/benchmark_memcached_matrix.py.
        self.clients, self.pipeline, self.value_bytes, self.keys, self.get_percent = 2, 2, 256, 10000, 50
        self.parameters = {"scenario": "watch_moderate", "clients": 2, "pipeline": 2,
                           "value_bytes": 256, "keys": 10000, "get_percent": 50,
                           "seconds": a.seconds, "warmup_seconds": a.warmup,
                           "server_cpus": a.server_cpus, "client_cpus": a.client_cpus,
                           "client_sha256": hashlib.sha256(a.client.read_bytes()).hexdigest()}
        self.binaries = {b: a.work / "bin" / f"memcached-{b}" for b in ("rlbox-only", "interspec")}

    def measure(self, workload, binary, switches, directory, report=False):
        from benchmark_memcached import Watcher
        from memcached_common import Client, Server
        seconds = 1 if report else self.seconds
        with SwitchedEnvironment(switches, report):
            server = Server(self.binaries[binary], directory, "server", cpu=self.server_cpus,
                            extra=["-o", "worker_logbuf_size=1024,watcher_logbuf_size=4096"])
        watcher = None
        try:
            with Client(server.port) as c:
                for i in range(self.keys):
                    assert c.store(f"bench{i}".encode(), b"x" * self.value_bytes) == b"STORED\r\n"
            watcher = Watcher(server.port)

            def load(duration, phase):
                command = ["taskset", "-c", self.client_cpus, str(self.client), str(server.port),
                           str(duration), str(self.clients), str(self.pipeline),
                           str(self.value_bytes), str(self.keys), str(self.get_percent), "0",
                           "independent-v1", "20261109", "count-only", "1024", "100000"]
                done = subprocess.run(command, capture_output=True, text=True,
                                      timeout=duration + 120)
                (Path(directory) / f"{phase}.stdout").write_text(done.stdout)
                (Path(directory) / f"{phase}.stderr").write_text(done.stderr)
                done.check_returncode()
                return json.loads(done.stdout)

            load(self.warmup, "warmup")
            watcher.settle()
            with Client(server.port) as c:
                before = c.stats()
            data = load(seconds, "measured")
            watcher.settle()
            with Client(server.port) as c:
                after = c.stats()
            delta = {k: int(after[k]) - int(before[k]) for k in
                     ("cmd_get", "cmd_set", "get_hits", "get_misses", "log_worker_written",
                      "log_worker_dropped", "log_watcher_skipped")}
            valid = (data["errors"] == 0
                     and delta["cmd_get"] + delta["cmd_set"] == data["operations"]
                     and delta["get_misses"] == 0 and delta["get_hits"] == delta["cmd_get"]
                     and delta["log_worker_dropped"] == 0 and delta["log_watcher_skipped"] == 0
                     and delta["log_worker_written"] > 0 and watcher.bytes > 0
                     and server.proc.poll() is None)
            (Path(directory) / "stats.json").write_text(json.dumps(
                {"client": data, "server_delta": delta, "watcher_bytes": watcher.bytes}) + "\n")
            value = data["ops_per_s"]
        finally:
            if watcher:
                watcher.close()
            server.close()
        log = server.logpath.read_text(errors="replace")
        if "INTERSPEC_REJECT" in log:
            valid = False
        return {"value": value, "valid": valid,
                "result": "all operations answered, no GET miss, no log line lost",
                "stderr": log}


# --- nginx/libpcre ----------------------------------------------------------

class Nginx:
    unit, higher_is_better = "requests_per_s", True
    workloads = ("regex_location_4_threads",)

    def __init__(self, a):
        from benchmark_nginx import LUA
        self.work, self.wrk, self.seconds, self.warmup = a.work, a.wrk, a.seconds, a.warmup
        self.server_cpus, self.client_cpus = a.server_cpus, a.client_cpus
        self.threads, self.connections = 4, 100
        self.script = a.scratch / "validate.lua"
        a.scratch.mkdir(parents=True, exist_ok=True)
        self.script.write_text(LUA)
        self.parameters = {"threads": 4, "connections": 100, "seconds": a.seconds,
                           "warmup_seconds": a.warmup, "path": "/items/123/alpha",
                           "server_cpus": a.server_cpus, "client_cpus": a.client_cpus}
        self.binaries = {b: a.work / "bin" / f"nginx-{b}" for b in ("rlbox-only", "interspec")}

    def measure(self, workload, binary, switches, directory, report=False):
        from nginx_common import Server
        seconds = 1 if report else self.seconds
        with SwitchedEnvironment(switches, report):
            server = Server(self.binaries[binary], directory, workers=0, cpu=self.server_cpus)
        try:
            def wrk(duration, phase):
                command = ["taskset", "-c", self.client_cpus, self.wrk, "--latency",
                           f"-t{self.threads}", f"-c{self.connections}", f"-d{duration}s",
                           "-s", str(self.script.resolve()),
                           f"http://127.0.0.1:{server.port}/items/123/alpha"]
                done = subprocess.run(command, text=True, capture_output=True,
                                      timeout=duration + 60)
                (Path(directory) / f"{phase}.stdout").write_text(done.stdout)
                (Path(directory) / f"{phase}.stderr").write_text(done.stderr)
                done.check_returncode()
                values = [json.loads(line.removeprefix("INTERSPEC_WRK "))
                          for line in done.stdout.splitlines() if line.startswith("INTERSPEC_WRK ")]
                assert len(values) == 1, done.stdout
                return values[0]

            if self.warmup:
                wrk(self.warmup, "warmup")
            data = wrk(seconds, "measured")
            valid = (data["requests"] > 0 and data["validated"] == data["requests"]
                     and all(data[k] == 0 for k in ("bad", "connect_errors", "read_errors",
                                                    "write_errors", "status_errors", "timeouts"))
                     and server.proc.poll() is None)
            value = data["requests"] * 1e6 / data["duration_us"]
        finally:
            server.close()
        log = server.logpath.read_text(errors="replace")
        if "INTERSPEC_REJECT" in log:
            valid = False
        return {"value": value, "valid": valid,
                "result": "every response had status 200 and the expected body", "stderr": log}


ADAPTERS = {"rsync": (Rsync, "rsync_popt", ("sp1", "sp2", "sp3")),
            "yaml": (Yaml, "yaml_libyaml", ("sp2", "sp3")),
            "memcached": (Memcached, "memcached_bipbuffer", ("sp1", "sp2", "sp3")),
            "nginx": (Nginx, "nginx_libpcre", ("sp1", "sp2", "sp3"))}


# The name under which a bridge reports its switches, where it differs.
REPORT_NAME = {"nginx_libpcre": "nginx_pcre"}


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--out", required=True, type=Path)
    common.add_argument("--scratch", required=True, type=Path,
                        help="directory for working files (not evidence)")
    common.add_argument("--repetitions", type=int, default=15)
    common.add_argument("--seed", type=int, default=20261114)
    common.add_argument("--label", required=True)
    common.add_argument("--source-commit", required=True)
    sub = parser.add_subparsers(dest="boundary", required=True)
    for name in ("rsync", "yaml"):
        p = sub.add_parser(name, parents=[common])
        p.add_argument("--rlbox-only", required=True, type=Path)
        p.add_argument("--interspec", required=True, type=Path)
        p.add_argument("--cpu", type=int, default=0)
        if name == "yaml":
            p.add_argument("--input", required=True, type=Path)
            p.add_argument("--iterations", type=int, default=1000)
    for name in ("memcached", "nginx"):
        p = sub.add_parser(name, parents=[common])
        p.add_argument("--work", required=True, type=Path, help="deployment build directory")
        p.add_argument("--seconds", type=int, default=10)
        p.add_argument("--warmup", type=int, default=2)
        p.add_argument("--server-cpus", default="0-1")
        p.add_argument("--client-cpus", default="2-3")
        if name == "memcached":
            p.add_argument("--client", required=True, type=Path)
        else:
            p.add_argument("--wrk", default="wrk")
    a = parser.parse_args()

    adapter_class, boundary, policies = ADAPTERS[a.boundary]
    a.scratch.mkdir(parents=True, exist_ok=True)
    adapter = adapter_class(a)
    configs = configurations(policies)
    a.out.mkdir(parents=True)
    metadata = {"boundary": boundary, "policies_at_this_boundary": list(policies),
                "configurations": {n: {"binary": b, "switches": dict(zip(SWITCHES, s)) if s else None}
                                   for n, (b, s) in configs.items()},
                "workloads": list(adapter.workloads), "unit": adapter.unit,
                "repetitions": a.repetitions, "seed": a.seed, "parameters": adapter.parameters,
                "source_commit": a.source_commit, "label": a.label, "machine_start": machine(),
                "binaries_sha256": {k: hashlib.sha256(Path(v).read_bytes()).hexdigest()
                                    for k, v in adapter.binaries.items()},
                "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (a.out / "run.json").write_text(json.dumps(metadata, indent=2) + "\n")

    # Gate and warm-up: every configuration once per workload, with the policy
    # report on; the report must name the switches that were requested, and the
    # result must equal the RLBox-only result.
    gate, passed, expected = {}, True, {}
    for workload in adapter.workloads:
        for name, (binary, switches) in configs.items():
            directory = a.out / "gate" / f"{workload}-{name}"
            directory.mkdir(parents=True)
            m = adapter.measure(workload, binary, switches, directory, report=True)
            reports = [l for l in m["stderr"].splitlines() if l.startswith("INTERSPEC_POLICY ")]
            entry = {"valid": m["valid"], "result": m["result"], "policy_report": reports}
            if name == "rlbox-only":
                expected[workload] = m["result"]
            entry["result_matches_rlbox_only"] = m["result"] == expected[workload]
            entry["report_matches_switches"] = (
                switches is None or any(expected_report(switches) in l and
                                        f"boundary={REPORT_NAME.get(boundary, boundary)} " in l
                                        for l in reports))
            if "checks" in m:
                entry["checks"] = m["checks"]
            gate[f"{workload}/{name}"] = entry
            passed &= (entry["valid"] and entry["result_matches_rlbox_only"]
                       and entry["report_matches_switches"])
    (a.out / "gate.json").write_text(json.dumps(gate, indent=2) + "\n")
    if not passed:
        print("gate failed; see gate.json")
        return 1

    rng = random.Random(a.seed)
    columns = ["workload", "repetition", "position", "configuration", "binary", "value", "unit",
               "valid", "result_matches_rlbox_only"]
    samples, failed = [], False
    with (a.out / "samples.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for workload in adapter.workloads:
            for repetition in range(1, a.repetitions + 1):
                order = list(configs)
                rng.shuffle(order)
                for position, name in enumerate(order, 1):
                    binary, switches = configs[name]
                    directory = a.out / "runs" / f"{workload}-r{repetition:02d}-{name}"
                    directory.mkdir(parents=True)
                    m = adapter.measure(workload, binary, switches, directory)
                    row = {"workload": workload, "repetition": repetition, "position": position,
                           "configuration": name, "binary": binary, "value": m["value"],
                           "unit": adapter.unit, "valid": m["valid"],
                           "result_matches_rlbox_only": m["result"] == expected[workload]}
                    if not (row["valid"] and row["result_matches_rlbox_only"]):
                        failed = True
                        (directory / "failed.stderr.txt").write_text(m["stderr"])
                    writer.writerow(row)
                    handle.flush()
                    samples.append(row)
    (a.out / "finish.json").write_text(json.dumps(
        {"machine_end": machine(), "all_measurements_valid": not failed,
         "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=2) + "\n")
    if failed:
        print("a measurement was invalid; no summary written")
        return 1

    # Cost of a configuration against a baseline, per repetition: the relative
    # increase in time per unit of work (time ratio, or inverse throughput ratio).
    summary = []
    for workload in adapter.workloads:
        by = {(r["repetition"], r["configuration"]): float(r["value"])
              for r in samples if r["workload"] == workload}
        for name in configs:
            values = [by[(i, name)] for i in range(1, a.repetitions + 1)]
            row = {"workload": workload, "configuration": name, "repetitions": len(values),
                   "unit": adapter.unit, "median": round(statistics.median(values), 3),
                   "min": round(min(values), 3), "max": round(max(values), 3)}
            for baseline in ("interspec-all-off", "rlbox-only"):
                costs = []
                for i in range(1, a.repetitions + 1):
                    x, b = by[(i, name)], by[(i, baseline)]
                    costs.append(100 * ((b / x if adapter.higher_is_better else x / b) - 1))
                row[f"median_cost_pct_vs_{baseline}"] = round(statistics.median(costs), 3)
                row[f"min_cost_pct_vs_{baseline}"] = round(min(costs), 3)
                row[f"max_cost_pct_vs_{baseline}"] = round(max(costs), 3)
            summary.append(row)
    with (a.out / "summary.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    for row in summary:
        print(json.dumps(row))
    return 0


if __name__ == "__main__":
    sys.exit(main())
