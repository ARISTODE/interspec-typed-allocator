#!/usr/bin/env python3
"""Read-only host inventory. Passing this does not prove measurement quality."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess


def cpus(value):
    result = set()
    for part in value.split(","):
        limits = part.split("-")
        if len(limits) == 1:
            result.add(int(limits[0]))
        elif len(limits) == 2:
            lo, hi = map(int, limits)
            if lo > hi: raise ValueError("reversed CPU range")
            result.update(range(lo, hi + 1))
        else: raise ValueError("invalid CPU range")
    if not result or min(result) < 0: raise ValueError("empty/invalid CPU set")
    return result


def inventory(server, client, dedicated):
    affinity = set(os.sched_getaffinity(0))
    errors = []
    if server & client: errors.append("server and client CPU sets overlap")
    if not (server | client) <= affinity: errors.append("selected CPUs are outside current affinity")
    if len(server) < 4 or len(client) < 4: errors.append("at least four server and four client CPUs are required by this protocol")
    if not dedicated: errors.append("dedicated host has not been established by its operator")
    def read(path):
        p = Path(path)
        return p.read_text().strip() if p.exists() else None
    topology = {}
    physical_cores = {"server": set(), "client": set()}
    for cpu in sorted(server | client):
        root = f"/sys/devices/system/cpu/cpu{cpu}"
        topology[cpu] = {key: read(root + suffix) for key, suffix in {
            "siblings":"/topology/thread_siblings_list", "governor":"/cpufreq/scaling_governor",
            "min_khz":"/cpufreq/scaling_min_freq", "max_khz":"/cpufreq/scaling_max_freq"}.items()}
        if not topology[cpu]["siblings"]:
            errors.append(f"physical topology is unavailable for CPU {cpu}")
            continue
        siblings = cpus(topology[cpu]["siblings"])
        physical_cores["server" if cpu in server else "client"].add(tuple(sorted(siblings)))
        if cpu in server and siblings & client: errors.append(f"CPU {cpu} shares a physical core with client CPUs")
    for group, cores in physical_cores.items():
        if len(cores) < 4:
            errors.append(f"{group} CPU set has fewer than four distinct physical cores")
    required = ("git", "cmake", "cc", "g++", "make", "autoconf", "automake", "python3", "taskset", "wrk")
    missing = [x for x in required if not shutil.which(x)]
    if missing: errors.append("missing build/runtime tools: " + ", ".join(missing))
    quota = read("/sys/fs/cgroup/cpu.max")
    if quota and quota.split()[0] != "max":
        limit, period = map(int, quota.split())
        if limit / period < len(server | client): errors.append("cgroup CPU quota is below selected CPU count")
    if not all(t["governor"] for t in topology.values()):
        errors.append("frequency policy is not visible; host operator must supply and review its configuration")
    return dict(ready_for_operator_review=not errors, publication_ready=False,
                host=platform.uname()._asdict(), affinity=sorted(affinity), server_cpus=sorted(server),
                client_cpus=sorted(client), operator_declared_dedicated=dedicated, topology=topology,
                physical_core_counts={group: len(cores) for group, cores in physical_cores.items()},
                cpu_quota=quota, memory_limit=read("/sys/fs/cgroup/memory.max"),
                cpuinfo=read("/proc/cpuinfo"), errors=sorted(set(errors)))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--server-cpus", required=True)
    p.add_argument("--client-cpus", required=True)
    p.add_argument("--operator-confirms-dedicated", action="store_true")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = inventory(cpus(a.server_cpus), cpus(a.client_cpus), a.operator_confirms_dedicated)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("ready_for_operator_review", "publication_ready", "errors")}, indent=2))
    raise SystemExit(0 if result["ready_for_operator_review"] else 1)
