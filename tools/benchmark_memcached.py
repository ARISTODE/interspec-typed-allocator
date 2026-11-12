#!/usr/bin/env python3
"""Complete-server collection, with an explicitly scoped VM capacity mode."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import shutil
import select
import statistics
import subprocess
import threading
import time
from memcached_common import Client, Server, guarded_command

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


def process_status(pid):
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
    return record, Path(f'/proc/{candidate}')


def read_process_status(path):
    return {line.split(':', 1)[0]: line.split(':', 1)[1].strip()
            for line in path.read_text().splitlines() if ':' in line}


def process_starttime(path):
    # Field 22, after the parenthesized comm (which may contain spaces).
    return (path / 'stat').read_text().rsplit(')', 1)[1].split()[19]


def observed_client_affinity(pid, client):
    """Read only post-exec status, bracketed by executable and PID identity.

    process_status's first snapshot is used ONLY to locate the namespace child.
    It may precede taskset/exec and is never evidence of the client's mask.
    None means a transition/exit was observed: the caller can poll again.
    """
    located, path = process_status(pid)
    try:
        start_before = process_starttime(path)
        exe_before = (path / 'exe').resolve(strict=True)
        if exe_before != client.resolve(): return None
        current = read_process_status(path / 'status')
        exe_after = (path / 'exe').resolve(strict=True)
        start_after = process_starttime(path)
    except (FileNotFoundError, ProcessLookupError):
        return None
    if exe_before != exe_after or start_before != start_after: return None
    if current['Pid'] != located['Pid'] or current['PPid'] != located['PPid']:
        return None
    if int(current.get('NSpid', current['Pid']).split()[-1]) != pid: return None
    return {'cpus': current['Cpus_allowed_list'], 'starttime_ticks': start_after,
            'proc_visible_pid': int(current['Pid']), 'namespace_pid': pid,
            'executable': str(exe_after), 'method': 'exe/status/exe with stable process starttime'}


def usage(pid):
    record, _ = process_status(pid)
    result = {}
    for key in ('VmRSS', 'VmHWM', 'VmSize'):
        result[key + '_kib'] = int(record[key].split()[0])
    result["observed_server_cpus"] = record["Cpus_allowed_list"]
    return result


def cpu_set(text):
    result = set()
    for part in text.split(","):
        ends = [int(x) for x in part.split("-")]
        result.update(range(ends[0], ends[-1] + 1))
    return result


def validate_client_affinity(observed, requested):
    assert cpu_set(observed) == cpu_set(requested), "Observed client affinity mismatch"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--work", type=Path, default=Path("/tmp/interspec-memcached-deployment"))
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--operations", type=int, default=0)
    p.add_argument("--warmup-operations", type=int, default=0)
    p.add_argument("--seconds", type=float, default=5)
    p.add_argument("--warmup", type=float, default=1)
    p.add_argument("--repetitions", type=int, default=5)
    p.add_argument("--clients", type=int, default=4)
    p.add_argument("--pipeline", type=int, default=8)
    p.add_argument("--value-bytes", type=int, default=256)
    p.add_argument("--keys", type=int, default=1024)
    p.add_argument("--get-percent", type=int, default=50)
    p.add_argument("--measurement-mode", choices=("full", "count-only", "sampled"), default="count-only")
    p.add_argument("--sample-every", type=int, default=1024)
    p.add_argument("--sample-cap-per-client", type=int, default=100000)
    p.add_argument("--workload-mode", choices=("legacy", "independent-v1"), default="independent-v1")
    p.add_argument("--workload-seed", type=int, default=20261109)
    p.add_argument("--variants", default=",".join(VARIANTS),
                   help="comma-separated subset of native,rlbox-only,tracked-no-check,interspec")
    p.add_argument("--workloads", default="cache_only,watch_active",
                   help="comma-separated subset of cache_only,watch_active")
    p.add_argument("--server-cpus")
    p.add_argument("--client-cpus")
    p.add_argument("--label", default="shared_container_pilot")
    p.add_argument("--correctness-summary", type=Path, required=True)
    p.add_argument("--client-binary", type=Path, help="Use a frozen prebuilt client; never compile")
    p.add_argument("--functional-rehearsal", action="store_true", help="Allow one repetition, VM functional evidence only")
    p.add_argument("--capacity-diagnostic", action="store_true", help="Single RLBox-only VM capacity observation; no comparison acceptance")
    a = p.parse_args()
    if a.capacity_diagnostic:
        assert a.server_cpus and a.client_cpus
        assert not cpu_set(a.server_cpus) & cpu_set(a.client_cpus)
    assert a.sample_every > 0 and 0 < a.sample_cap_per_client <= 10000000
    assert 0 <= a.workload_seed < 2**64
    variants = [v.strip() for v in a.variants.split(",") if v.strip()]
    workloads = [w.strip() for w in a.workloads.split(",") if w.strip()]
    assert variants and len(set(variants)) == len(variants) and all(v in VARIANTS for v in variants)
    assert workloads and len(set(workloads)) == len(workloads) and all(w in ("cache_only", "watch_active") for w in workloads)
    if a.capacity_diagnostic:
        assert variants == ["rlbox-only"] and workloads == ["cache_only"]
        assert a.repetitions == 1 and a.operations > 0 and a.warmup_operations > 0
        assert a.measurement_mode == "count-only" and a.workload_mode == "independent-v1"
    else:
        assert "native" in variants, "native baseline required"
    gate = json.loads(a.correctness_summary.read_text())
    assert gate["passed"] == gate["total"] == 50, "correctness gate failed/incomplete"
    for variant in variants:
        binary = a.work / "bin" / f"memcached-{variant}"
        assert hashlib.sha256(binary.read_bytes()).hexdigest() == gate["binary_sha256"][binary.name], "binary changed since correctness validation"
    assert a.repetitions >= (1 if a.functional_rehearsal or a.capacity_diagnostic else 3) and a.seconds > 0 and a.warmup > 0
    a.out.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    client = a.out / "memcached-client"  # Keep archived/shared client binaries untouched.
    if a.client_binary:
        shutil.copyfile(a.client_binary, client)
        client.chmod(0o700)
    else:
        subprocess.run(["g++", "-std=c++17", "-O2", "-pthread", str(root/"evaluation/memcached_client.cpp"), "-o", str(client)], check=True)
    environment = {"label": a.label, "host": platform.uname()._asdict(), "parameters": {k: str(v) if isinstance(v, Path) else v for k, v in vars(a).items()},
        "build": json.loads((a.work/"build-manifest.json").read_text()),
        "scope": "VM capacity diagnostic only; no acceptance or equivalence" if a.capacity_diagnostic else ("VM functional rehearsal only" if a.functional_rehearsal else "collection; host control not asserted"),
        "client_sha256": hashlib.sha256(client.read_bytes()).hexdigest(),
        "workload_source_sha256": hashlib.sha256((root/"evaluation/memcached_workload.h").read_bytes()).hexdigest(),
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
    for workload in workloads:
        for rep in range(a.repetitions):
            order = variants.copy(); rng.shuffle(order)
            for rank, variant in enumerate(order):
                name = f"{workload}-{rep}-{variant}"
                watcher = None
                with Server(a.work/"bin"/f"memcached-{variant}", a.out/"logs", name, cpu=a.server_cpus, guarded=True,
                            extra=["-o", "worker_logbuf_size=1024,watcher_logbuf_size=4096"]) as server:
                    try:
                        if a.capacity_diagnostic:
                            assert cpu_set(usage(server.proc.pid)["observed_server_cpus"]) == cpu_set(a.server_cpus), "Server affinity mismatch"
                        with Client(server.port) as c:
                            for i in range(a.keys):
                                assert c.store(f"bench{i}".encode(), b"x"*a.value_bytes) == b"STORED\r\n"
                        if workload == "watch_active": watcher = Watcher(server.port)
                        prefix = ["taskset", "-c", a.client_cpus] if a.client_cpus else []
                        def measure(seconds, operations, phase):
                            cmd = prefix + [str(client), str(server.port), str(seconds), str(a.clients), str(a.pipeline), str(a.value_bytes), str(a.keys), str(a.get_percent), str(operations), a.workload_mode, str(a.workload_seed), a.measurement_mode, str(a.sample_every), str(a.sample_cap_per_client)]
                            if a.capacity_diagnostic:
                                # A non-measured probe verifies taskset can select the full mask.
                                probe = subprocess.check_output(prefix + [os.sys.executable, "-c", "import os,json;print(json.dumps(sorted(os.sched_getaffinity(0))))"], text=True)
                                assert set(json.loads(probe)) == cpu_set(a.client_cpus), "Client mask unavailable"
                                with (a.out/"logs"/f"{name}.{phase}.stdout").open("w") as stdout_file, (a.out/"logs"/f"{name}.{phase}.stderr").open("w") as stderr_file:
                                    proc = subprocess.Popen(guarded_command(cmd), stdout=stdout_file, stderr=stderr_file, text=True)
                                    observed = None
                                    observation = None
                                    try:
                                        deadline = time.monotonic() + 10
                                        while proc.poll() is None and time.monotonic() < deadline:
                                            try: observation = observed_client_affinity(proc.pid, client)
                                            except RuntimeError:
                                                if proc.poll() is not None: break
                                                raise
                                            if observation is not None:
                                                observed = observation['cpus']
                                                validate_client_affinity(observed, a.client_cpus)
                                                break
                                            time.sleep(.001)
                                        proc.wait(timeout=max(seconds+30, 120))
                                    finally:
                                        if proc.poll() is None: proc.kill()
                                        proc.wait()
                                        (a.out/"logs"/f"{name}.{phase}.affinity.json").write_text(json.dumps({"probe_cpus": json.loads(probe), "observed_client_cpus": observed, "observation_identity": observation, "requested_client_cpus": a.client_cpus})+"\n")
                                stdout = (a.out/"logs"/f"{name}.{phase}.stdout").read_text()
                                stderr = (a.out/"logs"/f"{name}.{phase}.stderr").read_text()
                                result = subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
                                # Smoke runs may finish before a runtime observation. Main counts may not.
                                if operations >= 4000000: assert observed is not None, "Client runtime affinity not observed"
                            else:
                                result = subprocess.run(guarded_command(cmd), capture_output=True, text=True, check=False, timeout=max(seconds+30, 120))
                            (a.out / "logs" / f"{name}.{phase}.stdout").write_text(result.stdout)
                            (a.out / "logs" / f"{name}.{phase}.stderr").write_text(result.stderr)
                            result.check_returncode()
                            data = json.loads(result.stdout)
                            assert data["errors"] == 0
                            if operations: assert data["operations"] == operations
                            return data
                        if a.capacity_diagnostic:
                            with Client(server.port) as c: warmup_before = c.stats()
                        measure(a.warmup, a.warmup_operations, "warmup")
                        if a.capacity_diagnostic:
                            with Client(server.port) as c: warmup_after = c.stats()
                            (a.out/"logs"/f"{name}.warmup.stats.json").write_text(json.dumps({"before": warmup_before, "after": warmup_after}, indent=2)+"\n")
                        if watcher: watcher.settle()
                        with Client(server.port) as c: before = c.stats()
                        measured = measure(a.seconds, a.operations, "measured")
                        if watcher: watcher.settle()
                        with Client(server.port) as c: after = c.stats()
                        row = {"workload": workload, "repetition": rep, "order": rank, "variant": variant, **measured, **usage(server.proc.pid), "startup_ms": server.startup_ns/1e6}
                        for key in ("cmd_get", "cmd_set", "get_hits", "get_misses"):
                            row[key] = int(after[key]) - int(before[key])
                        assert row["cmd_get"] + row["cmd_set"] == row["operations"], "Server/client operation mismatch"
                        assert row["get_misses"] == 0 and row["get_hits"] == row["cmd_get"], "Unexpected GET miss"
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
    for workload in workloads:
        selected = [r for r in rows if r["workload"] == workload]
        for variant in variants:
            samples = [r for r in selected if r["variant"] == variant]
            assert all(r["measurement_mode"] == a.measurement_mode for r in samples)
            summary = {"measurement_mode": a.measurement_mode, "sample_every": a.sample_every if a.measurement_mode == "sampled" else 0, "sample_cap_per_client": a.sample_cap_per_client if a.measurement_mode == "sampled" else 0, "latency_valid": all(r["latency_valid"] for r in samples), "workload_mode": a.workload_mode, "workload_seed": a.workload_seed, "workload": workload, "variant": variant, "n": len(samples), "all_no_log_loss": all(r["valid_no_log_loss"] for r in samples), "all_no_lru_loss": all(r["valid_no_lru_loss"] for r in samples)}
            for key in ("ops_per_s", "p50_us", "p95_us", "p99_us", "VmRSS_kib", "VmHWM_kib", "server_cpu_s", "cpu_us_per_op", "startup_ms"):
                values = [r[key] for r in samples]
                valid = all(v is not None for v in values)
                summary[key+"_median"] = statistics.median(values) if valid else None
                summary[key+"_min"] = min(values) if valid else None
                summary[key+"_max"] = max(values) if valid else None
            for base in ("native", "rlbox-only", "tracked-no-check"):
                if base not in variants: continue
                baseline = {r["repetition"]: r for r in selected if r["variant"] == base}
                loss = [(1-r["ops_per_s"]/baseline[r["repetition"]]["ops_per_s"])*100 for r in samples]
                summary[f"throughput_loss_vs_{base}_paired_median_pct"] = statistics.median(loss)
            summaries.append(summary)
    (a.out/"summary.json").write_text(json.dumps(summaries, indent=2)+"\n")


if __name__ == "__main__": main()
