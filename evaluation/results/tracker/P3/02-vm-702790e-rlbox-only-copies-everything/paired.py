#!/usr/bin/env python3
"""Paired ratios for the nginx/libpcre timing run. Usage: paired.py timing/samples.csv

Checks every window (all responses validated, no error, at least 30 s) and
prints the Markdown table stored as PAIRED_RATIOS.md.
"""
import csv, statistics, sys

rows = list(csv.DictReader(open(sys.argv[1])))
variants = ["native", "rlbox-only", "tracked-no-check", "interspec"]
pairs = [("rlbox-only", "native"), ("interspec", "native"),
         ("tracked-no-check", "rlbox-only"), ("interspec", "tracked-no-check"),
         ("interspec", "rlbox-only")]
for r in rows:
    assert r["validated"] == r["requests"] and int(r["requests"]) > 0, r
    assert all(int(r[k]) == 0 for k in ["bad", "connect_errors", "read_errors",
               "write_errors", "status_errors", "timeouts"]), r
    assert int(r["duration_us"]) >= 30_000_000, r
threads = sorted({int(r["threads"]) for r in rows})
reps = sorted({int(r["repetition"]) for r in rows})
assert len(rows) == len(threads) * len(reps) * len(variants)
value = {(int(r["threads"]), int(r["repetition"]), r["variant"]): r for r in rows}

def table(column, loss, fmt):
    head = ("| Client threads | Median: native, RLBox-only, tracking without check, InterSpec | "
            + " | ".join(f"{x} against {b}" for x, b in pairs) + " |")
    print(head); print("|---:|---|" + "---:|" * len(pairs))
    for t in threads:
        med = [statistics.median(float(value[t, i, v][column]) for i in reps) for v in variants]
        cells = []
        for x, b in pairs:
            ratios = []
            for i in reps:
                q = float(value[t, i, x][column]) / float(value[t, i, b][column])
                ratios.append(100 * (1 - q) if loss else 100 * (q - 1))
            cells.append(f"{statistics.median(ratios):+.2f}% ({min(ratios):+.2f} to {max(ratios):+.2f})")
        print(f"| {t} | " + ", ".join(fmt(m) for m in med) + " | " + " | ".join(cells) + " |")

print("# Paired throughput loss with ranges\n")
print(f"Computed from `timing/samples.csv` ({len(rows)} rows: {len(threads)} thread counts, "
      f"{len(variants)} variants, {len(reps)} repetitions) by `paired.py`.")
print("""For each repetition the loss of X against B is 1 - requests_per_s(X) / requests_per_s(B),
both from the same repetition. A cell gives the median over the repetitions and, in
brackets, the smallest and largest value. Positive means X is slower. Every window
passed the checks at the top of `paired.py`.
""")
print("## Throughput (requests/s), loss\n")
table("requests_per_s", True, lambda m: f"{m:,.0f}")
print("\n## Server CPU time per request (microseconds), increase\n")
table("server_cpu_us_per_request", False, lambda m: f"{m:.2f}")
print("\n## Repetitions in which InterSpec is slower than RLBox-only\n")
for t in threads:
    n = sum(float(value[t, i, "interspec"]["requests_per_s"]) < float(value[t, i, "rlbox-only"]["requests_per_s"]) for i in reps)
    print(f"- {t} client threads: {n} of {len(reps)}")
