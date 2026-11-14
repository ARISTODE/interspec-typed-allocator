#!/usr/bin/env python3
"""Memory cost of memcached and nginx, RLBox-only against InterSpec (tracker item P9).

Starts one server, keeps it under load for the given time (at least 600 s for
the tracker item) and samples, for every process of the server:

  VmRSS and VmHWM from /proc/PID/status (VmHWM is the peak resident set size);
  the linear memory of every wasm2c sandbox from /proc/PID/smaps.

How a sandbox is found. The wasm2c runtime reserves the address range of a
linear memory with PROT_NONE and makes the first `size` bytes readable and
writable (src/wasm2c_rt_mem.c of the pinned backend). In smaps this is an
anonymous `rw-p` mapping directly followed by an anonymous `---p` mapping of at
least 1 GiB. The size of the `rw-p` mapping is the sandbox heap size (what
RLBox reports as get_total_memory); its Rss is the part that was touched. The
subcommand `check` validates this against a program that prints
get_total_memory (evaluation/memory/linear_memory_check.cpp).

The load is validated like a timing run (no failed operation); the numbers are
memory sizes, not timings.
"""

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

RESERVATION_MIN = 1 << 30


def mappings(pid):
    """[(start, end, perms, path, rss_bytes)] from /proc/PID/smaps."""
    result, current = [], None
    for line in Path(f"/proc/{pid}/smaps").read_text().splitlines():
        head = line.split()
        if head and "-" in head[0] and len(head) >= 5 and len(head[1]) == 4:
            start, end = (int(x, 16) for x in head[0].split("-"))
            current = [start, end, head[1], head[5] if len(head) > 5 else "", 0]
            result.append(current)
        elif line.startswith("Rss:") and current is not None:
            current[4] = int(line.split()[1]) * 1024
    return [tuple(m) for m in result]


def linear_memories(pid):
    """[{size, rss}] for every sandbox linear memory of the process."""
    maps = mappings(pid)
    found = []
    for previous, entry in zip(maps, maps[1:]):
        start, end, perms, path, _ = entry
        if perms != "---p" or path or end - start < RESERVATION_MIN:
            continue
        if previous[2] == "rw-p" and not previous[3] and previous[1] == start:
            found.append({"size": previous[1] - previous[0], "rss": previous[4]})
    return found


def process_tree(pid):
    pids, index = [pid], 0
    while index < len(pids):
        try:
            children = Path(f"/proc/{pids[index]}/task/{pids[index]}/children").read_text()
        except OSError:
            children = ""
        pids.extend(int(c) for c in children.split())
        index += 1
    return pids


def status(pid):
    values = {}
    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
        if line.startswith(("VmRSS:", "VmHWM:")):
            values[line.split(":")[0]] = int(line.split()[1]) * 1024
    return values


def sample(pid):
    row = {"processes": 0, "rss_bytes": 0, "peak_rss_bytes": 0, "sandboxes": 0,
           "sandbox_heap_bytes": 0, "sandbox_heap_resident_bytes": 0}
    for process in process_tree(pid):
        try:
            values, memories = status(process), linear_memories(process)
        except OSError:
            continue
        row["processes"] += 1
        row["rss_bytes"] += values.get("VmRSS", 0)
        row["peak_rss_bytes"] += values.get("VmHWM", 0)
        row["sandboxes"] += len(memories)
        row["sandbox_heap_bytes"] += sum(m["size"] for m in memories)
        row["sandbox_heap_resident_bytes"] += sum(m["rss"] for m in memories)
    return row


def check(a):
    proc = subprocess.Popen([str(a.program)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            text=True)
    rows, passed = [], True
    try:
        for phase in ("after creation", "after 96 MiB allocated in the sandbox"):
            reported = int(proc.stdout.readline().split()[1])
            memories = linear_memories(proc.pid)
            row = {"phase": phase, "get_total_memory": reported,
                   "sandboxes_found": len(memories),
                   "size_from_smaps": memories[0]["size"] if memories else None,
                   "resident_from_smaps": memories[0]["rss"] if memories else None}
            row["equal"] = len(memories) == 1 and memories[0]["size"] == reported
            passed &= row["equal"]
            rows.append(row)
            proc.stdin.write("\n")
            proc.stdin.flush()
        passed &= proc.wait(timeout=30) == 0
    finally:
        if proc.poll() is None:
            proc.kill()
    passed &= rows[1]["get_total_memory"] > rows[0]["get_total_memory"]
    a.out.mkdir(parents=True)
    (a.out / "check.json").write_text(json.dumps({"passed": bool(passed), "phases": rows},
                                                 indent=2) + "\n")
    print(json.dumps({"passed": bool(passed), "phases": rows}))
    return 0 if passed else 1


def run(a):
    binary = a.work / "bin" / f"{a.application}-{a.variant}"
    a.out.mkdir(parents=True)
    env_keys = [k for k in os.environ if k.startswith("INTERSPEC_")]
    for key in env_keys:
        del os.environ[key]
    metadata = {"application": a.application, "variant": a.variant, "seconds": a.seconds,
                "interval_seconds": a.interval, "server_cpus": a.server_cpus,
                "client_cpus": a.client_cpus, "label": a.label,
                "source_commit": a.source_commit,
                "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    load_result, load_error = {}, []
    watcher = None
    if a.application == "memcached":
        from benchmark_memcached import Watcher
        from memcached_common import Client, Server
        clients, pipeline, value_bytes, keys, get_percent = 2, 2, 256, 10000, 50
        metadata["load"] = {"scenario": "watch_moderate", "clients": clients,
                            "pipeline": pipeline, "value_bytes": value_bytes, "keys": keys,
                            "get_percent": get_percent, "watcher": "fetchers mutations"}
        server = Server(binary, a.out, "server", cpu=a.server_cpus,
                        extra=["-o", "worker_logbuf_size=1024,watcher_logbuf_size=4096"])
        with Client(server.port) as c:
            for i in range(keys):
                assert c.store(f"bench{i}".encode(), b"x" * value_bytes) == b"STORED\r\n"
        watcher = Watcher(server.port)
        command = ["taskset", "-c", a.client_cpus, str(a.client), str(server.port),
                   str(a.seconds), str(clients), str(pipeline), str(value_bytes), str(keys),
                   str(get_percent), "0", "independent-v1", "20261109", "count-only", "1024",
                   "100000"]
    else:
        from benchmark_nginx import LUA
        from nginx_common import Server
        script = a.out / "validate.lua"
        script.write_text(LUA)
        metadata["load"] = {"threads": 4, "connections": 100, "path": "/items/123/alpha"}
        server = Server(binary, a.out / "server", workers=0, cpu=a.server_cpus)
        command = ["taskset", "-c", a.client_cpus, a.wrk, "--latency", "-t4", "-c100",
                   f"-d{a.seconds}s", "-s", str(script.resolve()),
                   f"http://127.0.0.1:{server.port}/items/123/alpha"]
    (a.out / "run.json").write_text(json.dumps(metadata, indent=2) + "\n")

    def load():
        try:
            done = subprocess.run(command, capture_output=True, text=True,
                                  timeout=a.seconds + 300)
            (a.out / "load.stdout").write_text(done.stdout)
            (a.out / "load.stderr").write_text(done.stderr)
            done.check_returncode()
            if a.application == "memcached":
                load_result.update(json.loads(done.stdout))
            else:
                lines = [l for l in done.stdout.splitlines() if l.startswith("INTERSPEC_WRK ")]
                load_result.update(json.loads(lines[0].removeprefix("INTERSPEC_WRK ")))
        except Exception as error:  # reported below, fails the run
            load_error.append(repr(error))

    rows = []
    try:
        first = dict(elapsed_s=0.0, phase="before load", **sample(server.proc.pid))
        rows.append(first)
        thread = threading.Thread(target=load)
        start = time.monotonic()
        thread.start()
        with (a.out / "samples.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(first))
            writer.writeheader()
            writer.writerow(first)
            while thread.is_alive():
                thread.join(timeout=a.interval)
                row = dict(elapsed_s=round(time.monotonic() - start, 1),
                           phase="under load" if thread.is_alive() else "after load",
                           **sample(server.proc.pid))
                writer.writerow(row)
                handle.flush()
                rows.append(row)
        if watcher:
            watcher.settle()
        alive = server.proc.poll() is None
        watcher_bytes = watcher.bytes if watcher else None
    finally:
        if watcher:
            watcher.close()
        server.close()
    log = server.logpath.read_text(errors="replace")
    if a.application == "memcached":
        load_valid = not load_error and load_result.get("errors") == 0 and watcher_bytes > 0
    else:
        load_valid = (not load_error and load_result.get("requests", 0) > 0
                      and load_result.get("validated") == load_result.get("requests")
                      and all(load_result.get(k) == 0 for k in
                              ("bad", "connect_errors", "read_errors", "write_errors",
                               "status_errors", "timeouts")))
    under = [r for r in rows if r["phase"] != "before load"]
    summary = {
        "application": a.application, "variant": a.variant,
        "load_seconds": rows[-1]["elapsed_s"], "samples": len(rows),
        "load_valid": bool(load_valid), "load_error": load_error,
        "server_alive_at_end": alive, "rejections_in_log": log.count("INTERSPEC_REJECT"),
        "load": load_result, "watcher_bytes": watcher_bytes,
        "processes": rows[-1]["processes"], "sandboxes": rows[-1]["sandboxes"],
        "peak_rss_bytes": max(r["peak_rss_bytes"] for r in rows),
        "rss_bytes_before_load": rows[0]["rss_bytes"], "rss_bytes_at_end": rows[-1]["rss_bytes"],
        "sandbox_heap_bytes_before_load": rows[0]["sandbox_heap_bytes"],
        "sandbox_heap_bytes_max": max(r["sandbox_heap_bytes"] for r in rows),
        "sandbox_heap_bytes_at_end": rows[-1]["sandbox_heap_bytes"],
        "sandbox_heap_resident_bytes_max": max(r["sandbox_heap_resident_bytes"] for r in rows),
        "sandbox_heap_first_sample_under_load": under[0]["sandbox_heap_bytes"] if under else None,
        "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (a.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))
    ok = load_valid and alive and summary["rejections_in_log"] == 0 and \
        summary["load_seconds"] >= a.seconds
    return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("check")
    c.add_argument("--program", required=True, type=Path)
    c.add_argument("--out", required=True, type=Path)
    r = sub.add_parser("run")
    r.add_argument("--application", required=True, choices=("memcached", "nginx"))
    r.add_argument("--variant", required=True, choices=("native", "rlbox-only", "interspec"))
    r.add_argument("--work", required=True, type=Path, help="deployment build directory")
    r.add_argument("--out", required=True, type=Path)
    r.add_argument("--seconds", type=int, default=600)
    r.add_argument("--interval", type=float, default=5.0)
    r.add_argument("--server-cpus", default="0-1")
    r.add_argument("--client-cpus", default="2-3")
    r.add_argument("--client", type=Path, help="memcached load generator binary")
    r.add_argument("--wrk", default="wrk")
    r.add_argument("--label", required=True)
    r.add_argument("--source-commit", required=True)
    a = parser.parse_args()
    return check(a) if a.command == "check" else run(a)


if __name__ == "__main__":
    sys.exit(main())
