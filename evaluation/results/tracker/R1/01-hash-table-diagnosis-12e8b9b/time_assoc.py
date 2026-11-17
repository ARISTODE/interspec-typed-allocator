#!/usr/bin/env python3
"""time_assoc.py BIN ROUNDS [variants...]: interleaved runs pinned to CPU 0; prints median elapsed per variant and ratio to rlbox-only."""
import os, re, statistics, subprocess, sys, random
bin_, rounds = sys.argv[1], int(sys.argv[2])
variants = sys.argv[3:] or ["rlbox-only", "tracked-no-check", "interspec"]
t = {v: [] for v in variants}
rng = random.Random(1)
base = {k: v for k, v in os.environ.items() if not k.startswith("INTERSPEC_")}
for r in range(rounds):
    order = variants[:]; rng.shuffle(order)
    for v in order:
        env = dict(base)
        name = v.split("@")[0]
        if name == "rlbox-only": env.update(INTERSPEC_SP1="0", INTERSPEC_SP2="0")
        d = bin_ if "@" not in v else v.split("@")[1]
        out = subprocess.run(["taskset", "-c", "0", f"{d}/assoc-{name}", "20000", "400000"], env=env, capture_output=True, text=True).stdout
        t[v].append(int(re.search(r"elapsed_ns=(\d+)", out).group(1)))
ref = variants[0]
for v in variants:
    ratios = sorted(a / b for a, b in zip(t[v], t[ref]))
    print(f"{v:40s} median {statistics.median(t[v])/1e6:7.2f} ms  min {min(t[v])/1e6:7.2f}  ratio to {ref}: median {statistics.median(ratios):.3f} ({ratios[0]:.3f}..{ratios[-1]:.3f})")
