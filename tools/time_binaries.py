#!/usr/bin/env python3
"""Time several binaries of one workload with interleaved slices.

Usage: time_binaries.py OUT REPETITIONS ROUNDS BASE NAME=BINARY[@SP1,SP2,SP3[@FIRST]]... -- ARGUMENTS

@SP1,SP2,SP3 sets the three policy switches for that configuration (empty: none
set); @FIRST puts one argument before ARGUMENTS for that configuration (the
yaml programs take their mode there).

The protocol of tools/benchmark_ports.py (tracker item P7), for binaries that
do not come from one build directory (tracker items R2 and R3): a repetition consists of ROUNDS rounds, a
round runs every configuration once in a seeded random order on CPU 0, and the
time of a configuration in a repetition is the sum of the elapsed_ns its runs
print. Every run must exit 0 and print the same result fields as the first run.
Writes samples.csv (one row per run) and RATIOS.md (median, smallest and
largest of the paired ratios against BASE and the medians per configuration).
"""
import csv, os, random, re, statistics, subprocess, sys
from pathlib import Path

out, repetitions, rounds, base = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
split = sys.argv.index("--")
configs = {}
for item in sys.argv[5:split]:
    name, binary = item.split("=", 1)
    binary, text, first = (binary.split("@") + ["", ""])[:3]
    configs[name] = (binary, text.split(",") if text else None, [first] if first else [])
arguments = sys.argv[split + 1:]
assert base in configs
out.mkdir(parents=True)
clean = {k: v for k, v in os.environ.items() if not k.startswith("INTERSPEC_")}
NOT_RESULT = {"variant", "mode", "checks", "elapsed_ns"}
rng, reference, rows = random.Random(20261117), None, []
for repetition in range(1, repetitions + 1):
    for round_ in range(1, rounds + 1):
        order = list(configs)
        rng.shuffle(order)
        for name in order:
            binary, switches, first = configs[name]
            env = dict(clean)
            if switches:
                env.update(INTERSPEC_SP1=switches[0], INTERSPEC_SP2=switches[1], INTERSPEC_SP3=switches[2])
            done = subprocess.run(["taskset", "-c", "0", binary] + first + arguments, env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            fields = dict(re.findall(r"(\w+)=(\S+)", done.stdout))
            if done.returncode != 0 or "elapsed_ns" not in fields:
                (out / "failed.txt").write_text(f"{name}\n{done.stdout}\n{done.stderr}\n")
                sys.exit(f"{name} failed in repetition {repetition}, round {round_}")
            result = {k: v for k, v in fields.items() if k not in NOT_RESULT}
            reference = reference or result
            if result != reference:
                sys.exit(f"{name}: result differs from the first run")
            rows.append({"repetition": repetition, "round": round_, "configuration": name,
                         "elapsed_ns": int(fields["elapsed_ns"]), "checks": fields.get("checks", "")})
with (out / "samples.csv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
total = {}
for r in rows:
    key = (r["repetition"], r["configuration"])
    total[key] = total.get(key, 0) + r["elapsed_ns"]
reps = range(1, repetitions + 1)
lines = [f"{repetitions} repetitions of {rounds} rounds; arguments: {' '.join(arguments)}", "",
         f"| Configuration | Median time of a repetition (ms) | Against {base}: median | smallest | largest |",
         "|---|---:|---:|---:|---:|"]
for name in configs:
    ratios = [total[(i, name)] / total[(i, base)] - 1 for i in reps]
    lines.append(f"| {name} | {statistics.median(total[(i, name)] for i in reps) / 1e6:,.1f} | "
                 f"{100 * statistics.median(ratios):+.1f}% | {100 * min(ratios):+.1f}% | {100 * max(ratios):+.1f}% |")
(out / "RATIOS.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
