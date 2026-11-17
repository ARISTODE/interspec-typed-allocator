#!/usr/bin/env python3
"""Instructions executed by a ported boundary's workload (tracker item R3).

Wall-clock time on a shared virtual machine varies between runs; the number of
instructions a deterministic program executes does not. This tool runs each
configuration of a boundary under `valgrind --tool=callgrind` with two
iteration counts and reports the instructions per iteration as the difference
quotient, so that process start, sandbox creation and input loading cancel.
Every run is made `--repeat` times; the counts of the repeats are written out
so that the reader can see whether they agree.

Configurations: native, rlbox-only (SP1 and SP2 off, as in the timing tools),
tracked-no-check where the boundary has it, interspec with all policies on,
and the interspec binary with all policies off.

A count is not a time: it does not see cache misses, branch mispredictions or
code alignment. It answers how much more work a configuration does.
"""

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_ports import RLBOX_ONLY_SWITCHES  # noqa: E402
from run_port_parity import BOUNDARIES, NOT_RESULT, VARIANTS, parse  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--boundary", required=True, choices=sorted(BOUNDARIES))
    parser.add_argument("--bin", required=True, type=Path)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--workloads", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--divide", type=int, default=1,
                        help="divide the timed workload's iteration count by this (callgrind is slow)")
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--source-commit", default="")
    args = parser.parse_args()

    spec = BOUNDARIES[args.boundary]
    workload = json.loads(args.workloads.read_text())["boundaries"][args.boundary]
    case = json.loads((args.corpus / "cases.json").read_text())["cases"][workload["case"]]
    high = workload["iterations"] // args.divide
    low = high // 2
    if low < 1:
        sys.exit("iteration count too small")
    names = list(spec.get("variants", VARIANTS))
    configs = {name: (name, RLBOX_ONLY_SWITCHES if name == "rlbox-only" else ("1", "1", "1"))
               for name in names}
    configs["interspec-all-off"] = ("interspec", ("0", "0", "0"))
    base_env = {k: v for k, v in os.environ.items() if not k.startswith("INTERSPEC_")}

    args.out.mkdir(parents=True)
    rows, reference = [], {}
    for name, (binary, switches) in configs.items():
        env = dict(base_env)
        if name != "native":
            env.update(INTERSPEC_SP1=switches[0], INTERSPEC_SP2=switches[1], INTERSPEC_SP3=switches[2])
        for iterations in (low, high):
            arguments = spec["args"](args.corpus, case, str(iterations))
            for repeat in range(args.repeat):
                stem = args.out / f"{name}-{iterations}-{repeat}"
                command = ["valgrind", "--tool=callgrind", f"--callgrind-out-file={stem}.callgrind",
                           str(args.bin / f"{spec['prefix']}-{binary}")] + arguments
                done = subprocess.run(command, env=env, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, text=True, timeout=7200)
                Path(f"{stem}.stdout.txt").write_text(done.stdout)
                Path(f"{stem}.stderr.txt").write_text(done.stderr)
                collected = re.search(r"Collected : (\d+)", done.stderr)
                if done.returncode != 0 or not collected:
                    sys.exit(f"{name} {iterations} failed (exit {done.returncode}); see {stem}.stderr.txt")
                fields = parse(spec["tag"], done.stdout)
                if fields is None:
                    sys.exit(f"{name} {iterations}: no result line; see {stem}.stdout.txt")
                result = {k: v for k, v in fields.items() if k not in NOT_RESULT}
                expected = reference.setdefault(iterations, result)
                if result != expected:
                    sys.exit(f"{name} {iterations}: result differs from the first configuration")
                if repeat:  # keep one profile per run size, the counts of all
                    os.remove(f"{stem}.callgrind")
                rows.append({"boundary": args.boundary, "configuration": name, "iterations": iterations,
                             "repeat": repeat, "instructions": int(collected.group(1))})
                print(f"{name} {iterations} #{repeat}: {rows[-1]['instructions']:,}", flush=True)

    with (args.out / "counts.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    def counts(name, iterations):
        return [r["instructions"] for r in rows
                if r["configuration"] == name and r["iterations"] == iterations]

    summary = {"boundary": args.boundary, "case": case, "low_iterations": low,
               "high_iterations": high, "source_commit": args.source_commit, "configurations": {}}
    for name in configs:
        low_counts, high_counts = counts(name, low), counts(name, high)
        per_iteration = (high_counts[0] - low_counts[0]) / (high - low)
        summary["configurations"][name] = {
            "instructions_low": low_counts, "instructions_high": high_counts,
            "largest_difference_between_repeats": max(max(low_counts) - min(low_counts),
                                                      max(high_counts) - min(high_counts)),
            "instructions_per_iteration": per_iteration}
    base = summary["configurations"]["rlbox-only"]["instructions_per_iteration"]
    for name, entry in summary["configurations"].items():
        entry["against_rlbox_only_percent"] = 100 * (entry["instructions_per_iteration"] / base - 1)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")

    lines = [f"### {args.boundary}", "",
             f"Iterations {low:,} and {high:,}; instructions per iteration = difference of the counts "
             f"divided by {high - low:,}.", "",
             "| Configuration | Instructions per iteration | Against rlbox-only | "
             "Largest difference between repeats |", "|---|---:|---:|---:|"]
    for name, entry in summary["configurations"].items():
        lines.append(f"| {name} | {entry['instructions_per_iteration']:,.1f} | "
                     f"{entry['against_rlbox_only_percent']:+.2f}% | "
                     f"{entry['largest_difference_between_repeats']:,} |")
    (args.out / "TABLE.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
