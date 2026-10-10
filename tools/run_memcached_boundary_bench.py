#!/usr/bin/env python3
"""Collect repeated complete buffer operations and actual wasm2c primitives."""
import argparse
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess

VARIANTS = ("native", "rlbox-only", "tracked-no-check", "interspec")


def expected_cells(variant):
    cells = {(op, b) for op in ("request_push", "offer", "peek_all", "poll") for b in (64, 256, 1024, 4096)}
    cells.add(("empty_call", 0))
    if variant != "native":
        cells |= {("wrapper_mutex", 0), ("pointer_confinement", 64)}
        cells |= {(op, b) for op in ("copy_into_u", "copy_from_u") for b in (64, 256, 1024, 4096)}
    return cells


def summarize(rows, repetitions, iterations):
    groups = {}
    for row in rows:
        key = (row["variant"], row["metric"], int(row["bytes"]))
        rep = int(row["repetition"])
        group = groups.setdefault(key, {})
        assert rep not in group, "duplicate microbenchmark pair"
        assert int(row["operations"]) == iterations and int(row["total_ns"]) > 0
        value = float(row["ns_per_op"])
        assert math.isfinite(value) and value > 0 and math.isclose(value, int(row["total_ns"]) / iterations, abs_tol=1e-8)
        expected_checksum = (iterations * (iterations + 1) // 2 if key[1] == "empty_call" else
                             0 if key[1] in ("wrapper_mutex", "copy_into_u", "copy_from_u") else iterations)
        assert int(row["checksum"]) == expected_checksum, "functional checksum"
        group[rep] = value
    assert set(groups) == {(v, m, b) for v in VARIANTS for m, b in expected_cells(v)}, "incomplete microbenchmark matrix"
    result = []
    for (variant, metric, size), group in sorted(groups.items()):
        assert set(group) == set(range(repetitions)), "missing repetition"
        values = list(group.values())
        result.append(dict(variant=variant, metric=metric, bytes=size, n=len(values),
                           median_ns=statistics.median(values), min_ns=min(values), max_ns=max(values)))
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--work", type=Path, default=Path("/tmp/interspec-memcached-deployment"))
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--repetitions", type=int, default=7)
    p.add_argument("--iterations", type=int, default=20000)
    p.add_argument("--cpu")
    args = p.parse_args()
    assert args.repetitions >= 5 and args.iterations >= 1000
    args.out.mkdir(parents=True, exist_ok=True)
    binaries = args.work / "boundary-bench"
    manifest = json.loads((binaries / "manifest.json").read_text())
    # Existing result folders are untracked; source hashes and exact binary
    # identities bind this separate measurement build even after server CI.
    for v in VARIANTS:
        assert hashlib.sha256((binaries / v).read_bytes()).hexdigest() == manifest["binary_sha256"][v]
    environment = dict(build=manifest, host=platform.uname()._asdict(), affinity=sorted(os.sched_getaffinity(0)),
                       requested_cpu=args.cpu, repetitions=args.repetitions, iterations=args.iterations,
                       warmup_operations=1000, clock="steady_clock", publication_ready=False)
    (args.out / "environment.json").write_text(json.dumps(environment, indent=2) + "\n")
    rows = []
    rng = random.Random(20261010)
    for rep in range(args.repetitions):
        order = list(VARIANTS)
        rng.shuffle(order)
        for rank, variant in enumerate(order):
            prefix = ["taskset", "-c", args.cpu] if args.cpu else []
            run = subprocess.run(prefix + [str(binaries / variant), str(args.iterations)], capture_output=True, text=True, timeout=180)
            (args.out / f"{rep}-{variant}.stdout").write_text(run.stdout)
            (args.out / f"{rep}-{variant}.stderr").write_text(run.stderr)
            assert run.returncode == 0 and not run.stderr, (variant, run.returncode, run.stderr)
            sample = list(csv.DictReader(io.StringIO(run.stdout)))
            assert len(sample) == len(expected_cells(variant)) and {(r["metric"], int(r["bytes"])) for r in sample} == expected_cells(variant)
            rows += [dict(repetition=rep, order=rank, variant=variant, **r) for r in sample]
            with (args.out / "raw.csv").open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader(); writer.writerows(rows)
    result = summarize(rows, args.repetitions, args.iterations)
    (args.out / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    lines = ["# wasm2c boundary cost measurements", "",
             "Hosted reference. Seven paired repetitions by default; min and max are observed ranges, not confidence intervals. All times include loop and anti-elision controls and are not baseline-subtracted.", "",
             "Primitive copies reuse prevalidated live memory; metadata validation is excluded from these copy loops. Confinement uses the production sandbox address and memory-range operations. Mutex uses the production Buffer mutex after the process has entered multithreaded mode. Empty calls use a separately compiled native function or an actual wasm2c export. All have functional checksum controls.", "",
             "Complete buffer operations use the real upstream API and production bridge. A request_push includes trusted payload copying into the returned reservation. Setup and drain are outside each timed batch; warmup is 1000 operations. Payload sizes are 64, 256, 1024 and 4096 bytes. These are bounded queue microbenchmarks, not server workload overhead. Primitive medians must not be summed to predict a complete operation.", "",
             "| Variant | Operation | Bytes | Repetitions | Median ns/op | Min ns/op | Max ns/op |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for r in result:
        lines.append(f"| {r['variant']} | {r['metric']} | {r['bytes']} | {r['n']} | {r['median_ns']:.3f} | {r['min_ns']:.3f} | {r['max_ns']:.3f} |")
    (args.out / "RESULTS.md").write_text("\n".join(lines) + "\n")
    print(f"Validated {len(rows)} samples across {len(result)} configurations.")


if __name__ == "__main__":
    main()
