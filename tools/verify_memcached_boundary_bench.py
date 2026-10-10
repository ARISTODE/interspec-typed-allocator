#!/usr/bin/env python3
"""Independently check raw process outputs, sample grid, timings and summaries."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import median


def verify(root):
    def require(ok, message):
        if not ok:
            raise ValueError(message)
    def csv_rows(path):
        with path.open(newline="") as stream:
            return list(csv.DictReader(stream))
    env = json.loads((root / "environment.json").read_text())
    reps, iterations = env["repetitions"], env["iterations"]
    require(reps >= 5 and iterations >= 1000 and not env["build"]["source_dirty"], "measurement protocol/source state")
    variants = {"native", "rlbox-only", "tracked-no-check", "interspec"}
    require(set(env["build"]["binary_sha256"]) == variants, "binary manifest incomplete")
    require(all(len(h) == 64 for h in env["build"]["binary_sha256"].values()), "binary hashes invalid")
    samples = csv_rows(root / "raw.csv")
    cells = {}
    for v in variants:
        pairs = {(m, b) for m in ("request_push", "offer", "peek_all", "poll") for b in (64, 256, 1024, 4096)} | {("empty_call", 0)}
        if v != "native":
            pairs |= {("wrapper_mutex", 0), ("pointer_confinement", 64)}
            pairs |= {(m, b) for m in ("copy_into_u", "copy_from_u") for b in (64, 256, 1024, 4096)}
        cells[v] = pairs
    expected = {(v, m, b, rep) for v, pairs in cells.items() for m, b in pairs for rep in range(reps)}
    indexed = {(r["variant"], r["metric"], int(r["bytes"]), int(r["repetition"])): r for r in samples}
    require(len(indexed) == len(samples) and set(indexed) == expected, "missing or duplicate raw cell")
    sources = [root / name for name in ("environment.json", "raw.csv", "summary.json")]
    for rep in range(reps):
        ranks = set()
        for v in variants:
            stdout, stderr = root / f"{rep}-{v}.stdout", root / f"{rep}-{v}.stderr"
            require(not stderr.read_bytes(), "benchmark stderr not empty")
            raw = csv_rows(stdout)
            matching = [r for r in samples if r["variant"] == v and int(r["repetition"]) == rep]
            require(raw == [{k: value for k, value in row.items() if k not in ("variant", "order", "repetition")} for row in matching], "process output differs from raw.csv")
            require(len({r["order"] for r in matching}) == 1, "variant order mismatch")
            ranks.add(int(matching[0]["order"]))
            sources += [stdout, stderr]
        require(ranks == {0, 1, 2, 3}, "incomplete paired order")
    groups = {}
    for (v, metric, size, rep), row in indexed.items():
        n, total, value = int(row["operations"]), int(row["total_ns"]), float(row["ns_per_op"])
        require(n == iterations and total > 0 and math.isfinite(value) and value > 0, "invalid timer/count")
        require(math.isclose(value, total / n, abs_tol=1e-8), "ns/op arithmetic")
        checksum = (n * (n + 1) // 2 if metric == "empty_call" else
                    0 if metric in ("wrapper_mutex", "copy_into_u", "copy_from_u") else n)
        require(int(row["checksum"]) == checksum, "functional checksum")
        groups.setdefault((v, metric, size), []).append(value)
    summaries = json.loads((root / "summary.json").read_text())
    require(len(summaries) == len(groups), "summary coverage")
    seen = set()
    for s in summaries:
        key = (s["variant"], s["metric"], s["bytes"])
        require(key in groups and key not in seen and s["n"] == reps, "summary identity/repetitions")
        seen.add(key)
        for field, fn in (("median_ns", median), ("min_ns", min), ("max_ns", max)):
            require(math.isclose(s[field], fn(groups[key]), abs_tol=1e-8), "summary arithmetic")
    return dict(validated=True, publication_ready=False, configurations=len(groups), samples=len(samples),
                repetitions=reps, source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.results)
    (args.results / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"Independently verified {result['samples']} raw boundary samples and {result['configurations']} configurations.")
