#!/usr/bin/env python3
"""Paired ratios for the memcached/bipbuffer matrix. Usage: paired.py report/all-samples.csv

Checks every sample (no client error, no GET miss, no log or LRU loss, at
least 30 s) and prints the Markdown table stored as PAIRED_RATIOS.md.
"""
import csv, statistics, sys

rows = list(csv.DictReader(open(sys.argv[1])))
variants = ["native", "rlbox-only", "tracked-no-check", "interspec"]
pairs = [("rlbox-only", "native"), ("interspec", "native"),
         ("tracked-no-check", "rlbox-only"), ("interspec", "rlbox-only")]
for r in rows:
    assert int(r["errors"]) == 0 and int(r["get_misses"]) == 0, r
    assert r["valid_no_log_loss"] == "True" and r["valid_no_lru_loss"] == "True", r
    assert float(r["elapsed_s"]) >= 30.0, r
scenarios = list(dict.fromkeys(r["scenario"] for r in rows))
reps = sorted({int(r["repetition"]) for r in rows})
assert len(rows) == len(scenarios) * len(reps) * len(variants)
value = {(r["scenario"], int(r["repetition"]), r["variant"]): float(r["ops_per_s"]) for r in rows}
print("# Paired throughput loss with ranges\n")
print(f"Computed from `report/all-samples.csv` ({len(rows)} rows) by `paired.py`. For each repetition the loss of")
print("""configuration X against baseline B is 1 - ops_per_s(X) / ops_per_s(B), both from the
same repetition. A cell gives the median over the 15 repetitions and, in brackets,
the smallest and largest value. Positive means X is slower. Every sample passed the
checks at the top of `paired.py`.
""")
print("| Scenario | Median Kops/s: native, RLBox-only, tracking without check, InterSpec | "
      + " | ".join(f"{x} against {b}" for x, b in pairs) + " |")
print("|---|---|" + "---:|" * len(pairs))
for s in scenarios:
    med = [statistics.median(value[s, i, v] for i in reps) / 1000 for v in variants]
    cells = []
    for x, b in pairs:
        loss = [100 * (1 - value[s, i, x] / value[s, i, b]) for i in reps]
        cells.append(f"{statistics.median(loss):+.2f}% ({min(loss):+.2f} to {max(loss):+.2f})")
    print(f"| {s} | " + ", ".join(f"{m:.1f}" for m in med) + " | " + " | ".join(cells) + " |")
