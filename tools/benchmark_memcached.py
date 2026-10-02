#!/usr/bin/env python3
"""Paired complete-server pilot/controlled-host collection; no diagnostic code."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import select
import statistics
import subprocess
import threading
import time
from memcached_common import Client, Server

VARIANTS = ["native", "rlbox-only", "tracked-no-check", "interspec"]


class Watcher:
    def __init__(self, port):
        self.client = Client(port)
        assert self.client.command(b"watch fetchers mutations") == b"OK\r\n"
        self.stop = threading.Event()
        self.bytes = 0
        self.lines = 0
        self.last_received = time.monotonic()
        self.error = None
        def drain():
            try:
                while not self.stop.is_set():
                    if not select.select([self.client.sock], [], [], .1)[0]: continue
                    data = self.client.sock.recv(65536)
                    if not data: raise EOFError("watcher closed")
                    self.bytes += len(data); self.lines += data.count(b"\n")
                    self.last_received = time.monotonic()
            except Exception as error:
                self.error = str(error)
        self.thread = threading.Thread(target=drain)
        self.thread.start()

    def settle(self):
        # Logger batching is asynchronous; wait for its final output before
        # reading loss counters. This wait is outside the client timing window.
        start = time.monotonic()
        while time.monotonic() - start < 5:
            if time.monotonic() - max(start, self.last_received) > .4: break
            time.sleep(.05)
        assert self.error is None, self.error

    def close(self):
        self.stop.set(); self.thread.join(); self.client.close()


def usage(pid):
    def status(path):
        return {line.split(':', 1)[0]: line.split(':', 1)[1].strip()
                for line in path.read_text().splitlines() if ':' in line}
    # Some managed PID namespaces expose a host-mounted /proc. Resolve only
    # this process's own children, and verify both parent and namespace PID.
    own = status(Path('/proc/self/status'))
    candidates = [pid]
    for children in Path('/proc/self/task').glob('*/children'):
        candidates.extend(map(int, children.read_text().split()))
    # Kernels without CONFIG_CHECKPOINT_RESTORE omit task/*/children.
    # PPid and NSpid below still restrict selection to our exact child.
    candidates.extend(int(path.name) for path in Path('/proc').iterdir() if path.name.isdecimal())
    record = None
    for candidate in candidates:
        path = Path(f'/proc/{candidate}/status')
        try: current = status(path)
        except (FileNotFoundError, ProcessLookupError, PermissionError): continue
        namespace_pid = current.get('NSpid', current['Pid']).split()[-1]
        if current['PPid'] == own['Pid'] and int(namespace_pid) == pid:
            record = current
            break
    if record is None: raise RuntimeError(f'cannot resolve server PID {pid} in /proc')
    result = {}
    for key in ('VmRSS', 'VmHWM', 'VmSize'):
        result[key + '_kib'] = int(record[key].split()[0])
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--work", type=Path, default=Path("/tmp/interspec-memcached-deployment"))
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--seconds", type=float, default=5)
    p.add_argument("--warmup", type=float, default=1)
    p.add_argument("--repetitions", type=int, default=5)
    p.add_argument("--clients", type=int, default=4)
    p.add_argument("--pipeline", type=int, default=8)
    p.add_argument("--value-bytes", type=int, default=256)
    p.add_argument("--keys", type=int, default=1024)
    p.add_argument("--get-percent", type=int, default=50)
    p.add_argument("--server-cpus")
    p.add_argument("--client-cpus")
    p.add_argument("--label", default="shared_container_pilot")
    p.add_argument("--correctness-summary", type=Path, required=True)
    a = p.parse_args()
    gate = json.loads(a.correctness_summary.read_text())
    assert gate["passed"] == gate["total"] == 50, "correctness gate failed/incomplete"
    for variant in VARIANTS:
        binary = a.work / "bin" / f"memcached-{variant}"
        assert hashlib.sha256(binary.read_bytes()).hexdigest() == gate["binary_sha256"][binary.name], "binary changed since correctness validation"
    assert a.repetitions >= 3 and a.seconds > 0 and a.warmup > 0
    a.out.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    client = a.work / "memcached-client"
    subprocess.run(["g++", "-std=c++17", "-O2", "-pthread", str(root/"evaluation/memcached_client.cpp"), "-o", str(client)], check=True)
    environment = {"label": a.label, "host": platform.uname()._asdict(), "parameters": {k: str(v) if isinstance(v, Path) else v for k, v in vars(a).items()},
        "build": json.loads((a.work/"build-manifest.json").read_text()),
        "client_sha256": hashlib.sha256(client.read_bytes()).hexdigest(),
        "collector_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "cpuinfo": Path("/proc/cpuinfo").read_text().split("\n\n")[0],
        "affinity": sorted(os.sched_getaffinity(0)),
        "measurement": "loopback closed-loop ASCII clients; per-response latency includes pipelining; traces and fault hooks compiled out",
        "buffer_configuration_kib": {"worker": 1024, "watcher": 4096}}
    for key, path in {"governor": "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor", "intel_no_turbo": "/sys/devices/system/cpu/intel_pstate/no_turbo", "cpu_quota": "/sys/fs/cgroup/cpu.max", "memory_limit": "/sys/fs/cgroup/memory.max"}.items():
        environment[key] = Path(path).read_text().strip() if Path(path).exists() else "unavailable"
    (a.out/"environment.json").write_text(json.dumps(environment, indent=2)+"\n")
    rows = []
    rng = random.Random(20261002)
    for workload in ("cache_only", "watch_active"):
        for rep in range(a.repetitions):
            order = VARIANTS.copy(); rng.shuffle(order)
            for rank, variant in enumerate(order):
                name = f"{workload}-{rep}-{variant}"
                watcher = None
                with Server(a.work/"bin"/f"memcached-{variant}", a.out/"logs", name, cpu=a.server_cpus,
                            extra=["-o", "worker_logbuf_size=1024,watcher_logbuf_size=4096"]) as server:
                    try:
                        with Client(server.port) as c:
                            for i in range(a.keys):
                                assert c.store(f"bench{i}".encode(), b"x"*a.value_bytes) == b"STORED\r\n"
                        if workload == "watch_active": watcher = Watcher(server.port)
                        prefix = ["taskset", "-c", a.client_cpus] if a.client_cpus else []
                        def measure(seconds):
                            cmd = prefix + [str(client), str(server.port), str(seconds), str(a.clients), str(a.pipeline), str(a.value_bytes), str(a.keys), str(a.get_percent)]
                            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=seconds+30)
                            return json.loads(result.stdout)
                        measure(a.warmup)
                        if watcher: watcher.settle()
                        with Client(server.port) as c: before = c.stats()
                        measured = measure(a.seconds)
                        if watcher: watcher.settle()
                        with Client(server.port) as c: after = c.stats()
                        row = {"workload": workload, "repetition": rep, "order": rank, "variant": variant, **measured, **usage(server.proc.pid), "startup_ms": server.startup_ns/1e6}
                        row["server_cpu_s"] = sum(float(after[k])-float(before[k]) for k in ("rusage_user", "rusage_system"))
                        row["cpu_us_per_op"] = row["server_cpu_s"]*1e6/row["operations"]
                        for key in ("log_worker_written", "log_worker_dropped", "log_watcher_sent", "log_watcher_skipped", "lru_bumps_dropped", "moves_to_warm"):
                            row[key] = int(after[key])-int(before[key])
                        row["watcher_bytes_including_warmup"] = watcher.bytes if watcher else 0
                        row["valid_no_log_loss"] = row["log_worker_dropped"] == row["log_watcher_skipped"] == 0
                        row["valid_no_lru_loss"] = row["lru_bumps_dropped"] == 0
                        if watcher: assert row["log_worker_written"] > 0 and watcher.bytes > 0
                        (a.out/"logs"/f"{name}.stats.json").write_text(json.dumps({"before": before, "after": after}, indent=2)+"\n")
                    finally:
                        if watcher: watcher.close()
                assert "INTERSPEC" not in server.logpath.read_text(), "diagnostics present in benchmark binary"
                rows.append(row)
                with (a.out/"samples.csv").open("w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=list(row)); writer.writeheader(); writer.writerows(rows)
                print(json.dumps(row), flush=True)
    summaries = []
    for workload in ("cache_only", "watch_active"):
        selected = [r for r in rows if r["workload"] == workload]
        for variant in VARIANTS:
            samples = [r for r in selected if r["variant"] == variant]
            summary = {"workload": workload, "variant": variant, "n": len(samples), "all_no_log_loss": all(r["valid_no_log_loss"] for r in samples), "all_no_lru_loss": all(r["valid_no_lru_loss"] for r in samples)}
            for key in ("ops_per_s", "p50_us", "p95_us", "p99_us", "VmRSS_kib", "VmHWM_kib", "server_cpu_s", "cpu_us_per_op", "startup_ms"):
                summary[key+"_median"] = statistics.median(r[key] for r in samples)
                summary[key+"_min"] = min(r[key] for r in samples)
                summary[key+"_max"] = max(r[key] for r in samples)
            for base in ("native", "rlbox-only", "tracked-no-check"):
                baseline = {r["repetition"]: r for r in selected if r["variant"] == base}
                loss = [(1-r["ops_per_s"]/baseline[r["repetition"]]["ops_per_s"])*100 for r in samples]
                summary[f"throughput_loss_vs_{base}_paired_median_pct"] = statistics.median(loss)
            summaries.append(summary)
    (a.out/"summary.json").write_text(json.dumps(summaries, indent=2)+"\n")


if __name__ == "__main__": main()
