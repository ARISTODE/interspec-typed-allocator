#!/usr/bin/env python3
"""Paired timing of a ported boundary (tracker items P7 and P6).

One repetition consists of `--rounds` rounds. A round runs every configuration
once, in an order drawn from a seeded generator, each as a fresh process pinned
to one CPU. The time of one run is the `elapsed_ns` the program reports for its
workload loop (sandbox creation and input loading are outside it); the wall
time of the process is recorded too. The time of a configuration in a
repetition is the sum over the rounds, so the configurations of one repetition
do the same work in short slices that alternate. On a machine whose speed
changes from second to second (a shared virtual machine) this exposes all
configurations of a repetition to the same conditions; with one long run per
configuration it does not.

Modes:
  variants  the binaries native, rlbox-only, tracked-no-check (where the
            boundary has one) and interspec, all policies on (P7)
  policies  the interspec binary with SP1, SP2 and SP3 each alone, all on and
            all off, and the rlbox-only binary for reference (P6)

Before timing, every configuration runs once and its result must equal the
reference configuration's (all fields except variant, checks, elapsed_ns).
Every timed run is checked the same way; one mismatch or non-zero exit fails
the whole measurement. Raw samples are written before any summary.
"""

import argparse
import csv
import hashlib
import json
import os
import platform
import random
import statistics
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_port_parity import BOUNDARIES, NOT_RESULT, VARIANTS, parse  # noqa: E402

POLICY_CONFIGS = {
    "rlbox-only": ("rlbox-only", None),
    "interspec-all-off": ("interspec", ("0", "0", "0")),
    "interspec-sp1": ("interspec", ("1", "0", "0")),
    "interspec-sp2": ("interspec", ("0", "1", "0")),
    "interspec-sp3": ("interspec", ("0", "0", "1")),
    "interspec-all-on": ("interspec", ("1", "1", "1")),
}


def machine():
    model = ""
    for line in Path("/proc/cpuinfo").read_text().splitlines():
        if line.startswith("model name"):
            model = line.split(":", 1)[1].strip()
            break
    memory = next(l for l in Path("/proc/meminfo").read_text().splitlines()
                  if l.startswith("MemTotal"))
    return {"cpu_model": model, "logical_cpus": os.cpu_count(), "memory": memory.split(":")[1].strip(),
            "kernel": platform.release(), "loadavg": Path("/proc/loadavg").read_text().strip()}


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--boundary", required=True, choices=sorted(BOUNDARIES))
    parser.add_argument("--mode", required=True, choices=("variants", "policies"))
    parser.add_argument("--bin", required=True, type=Path)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--workloads", required=True, type=Path,
                        help="JSON: boundary -> {case: index into the corpus, iterations}")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--repetitions", type=int, default=15)
    parser.add_argument("--rounds", type=int, default=1,
                        help="interleaved slices per repetition (see above)")
    parser.add_argument("--cpu", type=int, default=0)
    parser.add_argument("--seed", type=int, default=20261114)
    parser.add_argument("--label", required=True, help="description of the machine")
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()

    spec = BOUNDARIES[args.boundary]
    workload = json.loads(args.workloads.read_text())["boundaries"][args.boundary]
    case = json.loads((args.corpus / "cases.json").read_text())["cases"][workload["case"]]
    arguments = spec["args"](args.corpus, case, str(workload["iterations"]))
    base_env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}

    if args.mode == "variants":
        names = list(spec.get("variants", VARIANTS))
        configs = {name: (name, ("1", "1", "1")) for name in names}
        reference = "native"
    else:
        configs = dict(POLICY_CONFIGS)
        reference = "rlbox-only"

    def command(name):
        binary = args.bin / f"{spec['prefix']}-{configs[name][0]}"
        return ["taskset", "-c", str(args.cpu), str(binary)] + arguments

    def environment(name):
        env = dict(base_env)
        switches = configs[name][1]
        if switches:
            env.update(INTERSPEC_SP1=switches[0], INTERSPEC_SP2=switches[1],
                       INTERSPEC_SP3=switches[2])
        return env

    def run(name):
        start = time.perf_counter_ns()
        done = subprocess.run(command(name), env=environment(name), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=1800)
        wall = time.perf_counter_ns() - start
        return done, wall

    def result_of(fields):
        return {k: v for k, v in fields.items() if k not in NOT_RESULT}

    args.out.mkdir(parents=True)
    binaries = sorted({configs[name][0] for name in configs})
    metadata = {
        "boundary": spec.get("reported_as", args.boundary), "harness_entry": args.boundary,
        "mode": args.mode, "configurations": list(configs), "reference": reference,
        "repetitions": args.repetitions, "rounds": args.rounds,
        "time_of_a_repetition": "sum of elapsed_ns over the rounds",
        "seed": args.seed, "cpu": args.cpu,
        "case": case, "iterations": workload["iterations"], "arguments": arguments,
        "source_commit": args.source_commit, "label": args.label, "machine_start": machine(),
        "binaries_sha256": {b: hashlib.sha256(
            (args.bin / f"{spec['prefix']}-{b}").read_bytes()).hexdigest() for b in binaries},
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (args.out / "run.json").write_text(json.dumps(metadata, indent=2) + "\n")

    # Gate: one run of each configuration; also serves as warm-up.
    gate, expected = {}, None
    for name in [reference] + [n for n in configs if n != reference]:
        done, _ = run(name)
        fields = parse(spec["tag"], done.stdout.decode(errors="replace"))
        entry = {"exit_code": done.returncode, "stdout": done.stdout.decode(errors="replace"),
                 "stderr": done.stderr.decode(errors="replace")}
        if done.returncode == 0 and fields is not None:
            if name == reference:
                expected = result_of(fields)
            entry["result_matches_reference"] = expected is not None and result_of(fields) == expected
            entry["checks"] = int(fields.get("checks", "0"))
        else:
            entry["result_matches_reference"] = False
        gate[name] = entry
    (args.out / "gate.json").write_text(json.dumps(gate, indent=2) + "\n")
    if not all(e["result_matches_reference"] for e in gate.values()):
        print("gate failed: " + ", ".join(n for n, e in gate.items()
                                          if not e["result_matches_reference"]))
        return 1

    rng = random.Random(args.seed)
    columns = ["repetition", "round", "position", "configuration", "binary", "elapsed_ns", "wall_ns",
               "checks", "exit_code", "result_matches_reference"]
    samples, failed = [], False
    with (args.out / "samples.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for repetition, round_ in ((i, k) for i in range(1, args.repetitions + 1)
                                   for k in range(1, args.rounds + 1)):
            order = list(configs)
            rng.shuffle(order)
            for position, name in enumerate(order, 1):
                done, wall = run(name)
                fields = parse(spec["tag"], done.stdout.decode(errors="replace")) or {}
                row = {"repetition": repetition, "round": round_, "position": position,
                       "configuration": name,
                       "binary": configs[name][0], "elapsed_ns": fields.get("elapsed_ns", ""),
                       "wall_ns": wall, "checks": fields.get("checks", ""),
                       "exit_code": done.returncode,
                       "result_matches_reference": bool(fields) and result_of(fields) == expected}
                if done.returncode != 0 or not row["result_matches_reference"]:
                    failed = True
                    stem = f"failed-r{repetition}-k{round_}-{name}"
                    (args.out / f"{stem}.stderr.txt").write_bytes(done.stderr)
                    (args.out / f"{stem}.stdout.txt").write_bytes(done.stdout)
                writer.writerow(row)
                handle.flush()
                samples.append(row)
    finish = {"machine_end": machine(),
              "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "all_timed_runs_correct": not failed}
    (args.out / "finish.json").write_text(json.dumps(finish, indent=2) + "\n")
    if failed:
        print("a timed run failed or returned a different result; no summary written")
        return 1

    by = {}
    for r in samples:
        key = (r["repetition"], r["configuration"])
        by[key] = by.get(key, 0) + int(r["elapsed_ns"])
    baselines = [reference] + (["rlbox-only"] if args.mode == "variants" else ["interspec-all-off"])
    summary = []
    for name in configs:
        values = [by[(i, name)] for i in range(1, args.repetitions + 1)]
        row = {"configuration": name, "repetitions": len(values), "rounds": args.rounds,
               "median_elapsed_ms": round(statistics.median(values) / 1e6, 3),
               "min_elapsed_ms": round(min(values) / 1e6, 3),
               "max_elapsed_ms": round(max(values) / 1e6, 3),
               "checks_per_slice": gate[name].get("checks", 0)}
        for baseline in baselines:
            ratios = [by[(i, name)] / by[(i, baseline)] for i in range(1, args.repetitions + 1)]
            row[f"median_ratio_to_{baseline}"] = round(statistics.median(ratios), 4)
            row[f"min_ratio_to_{baseline}"] = round(min(ratios), 4)
            row[f"max_ratio_to_{baseline}"] = round(max(ratios), 4)
        summary.append(row)
    with (args.out / "summary.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    for row in summary:
        print(json.dumps(row))
    return 0


if __name__ == "__main__":
    sys.exit(main())
