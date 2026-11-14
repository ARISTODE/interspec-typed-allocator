#!/usr/bin/env python3
"""Markdown tables from the raw samples of tools/benchmark_ports.py and
tools/benchmark_policy_cost.py (tracker items P7 and P6).

Everything is recomputed from samples.csv; the summary.csv files written by the
harnesses are not read. The value of a configuration in a repetition is the
sum of its slices (time) or the mean of its windows (throughput; the windows
have equal length). The estimator is the median over repetitions of the paired
ratio (same repetition, two configurations), with the smallest and largest
ratio next to it.
"""

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path


def paired(by, name, baseline, repetitions, higher_is_better=False):
    ratios = []
    for i in repetitions:
        x, b = by[(i, name)], by[(i, baseline)]
        ratios.append(b / x if higher_is_better else x / b)
    return statistics.median(ratios), min(ratios), max(ratios)


def percent(triple):
    return "{:+.1f}% ({:+.1f} to {:+.1f})".format(*(100 * (v - 1) for v in triple))


def ports(directories, out):
    lines = []
    for directory in directories:
        run = json.loads((directory / "run.json").read_text())
        finish = json.loads((directory / "finish.json").read_text())
        rows = list(csv.DictReader((directory / "samples.csv").open()))
        if not finish["all_timed_runs_correct"]:
            sys.exit(f"{directory}: a timed run was not correct")
        configs = run["configurations"]
        repetitions = sorted({int(r["repetition"]) for r in rows})
        rounds = run.get("rounds", 1)
        by = {}
        for r in rows:
            key = (int(r["repetition"]), r["configuration"])
            by[key] = by.get(key, 0) + int(r["elapsed_ns"])
        if (len(by) != len(configs) * len(repetitions) or len(repetitions) != run["repetitions"]
                or len(rows) != len(by) * rounds):
            sys.exit(f"{directory}: incomplete grid")
        gate = json.loads((directory / "gate.json").read_text())
        title = run["boundary"] + ("" if run["boundary"] == run["harness_entry"]
                                    else f" ({run['harness_entry']})")
        lines += [f"### {title}, {run['mode']}", "",
                  f"Workload: {' '.join(run['arguments'][-3:])} "
                  f"per slice; {len(repetitions)} paired repetitions of {rounds} interleaved "
                  f"slices each; CPU {run['cpu']}.", ""]
        baselines = (["native", "rlbox-only"] if run["mode"] == "variants"
                     else ["rlbox-only", "interspec-all-off"])
        lines += ["| Configuration | Median time of a repetition (ms) | Checks per slice | " +
                  " | ".join(f"Against {b}: median (range)" for b in baselines) + " |",
                  "|---|---:|---:|" + "---:|" * len(baselines)]
        for name in configs:
            values = [by[(i, name)] for i in repetitions]
            cells = [percent(paired(by, name, b, repetitions)) if b != name else "" for b in baselines]
            lines.append(f"| {name} | {statistics.median(values) / 1e6:.1f} | "
                         f"{gate[name].get('checks', 0):,} | " + " | ".join(cells) + " |")
        lines.append("")
    out.write_text("\n".join(lines) + "\n")


def policies(directories, out):
    lines = []
    for directory in directories:
        run = json.loads((directory / "run.json").read_text())
        finish = json.loads((directory / "finish.json").read_text())
        rows = list(csv.DictReader((directory / "samples.csv").open()))
        if not finish["all_measurements_valid"]:
            sys.exit(f"{directory}: a measurement was invalid")
        higher = run["unit"].endswith("_per_s")
        for workload in run["workloads"]:
            subset = [r for r in rows if r["workload"] == workload]
            repetitions = sorted({int(r["repetition"]) for r in subset})
            rounds = run.get("rounds", {}).get(workload, 1)
            slices = {}
            for r in subset:
                slices.setdefault((int(r["repetition"]), r["configuration"]), []).append(
                    float(r["value"]))
            by = {k: (statistics.mean(v) if higher else sum(v)) for k, v in slices.items()}
            configs = list(run["configurations"])
            if (len(by) != len(configs) * len(repetitions) or len(repetitions) != run["repetitions"]
                    or any(len(v) != rounds for v in slices.values())):
                sys.exit(f"{directory}: incomplete grid for {workload}")
            lines += [f"### {run['boundary']}, {workload}", "",
                      f"{len(repetitions)} paired repetitions of {rounds} interleaved "
                      f"{'windows' if higher else 'slices'} each; unit {run['unit']}. Cost is the "
                      "relative increase in time per unit of work.", "",
                      "| Configuration | Median of the repetitions | Cost against all policies off: median (range) | "
                      "Cost against RLBox-only: median (range) |", "|---|---:|---:|---:|"]
            for name in configs:
                values = [by[(i, name)] for i in repetitions]
                median = statistics.median(values)
                shown = f"{median / 1e6:.1f} ms" if run["unit"] == "ns" else f"{median:,.0f}"
                cells = [percent(paired(by, name, b, repetitions, higher)) if b != name else ""
                         for b in ("interspec-all-off", "rlbox-only")]
                lines.append(f"| {name} | {shown} | {cells[0]} | {cells[1]} |")
            lines.append("")
    out.write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("ports", "policies"))
    parser.add_argument("--runs", required=True, nargs="+", type=Path,
                        help="output directories of the harness")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    (ports if args.kind == "ports" else policies)(args.runs, args.out)
    print(args.out.read_text())
    return 0


if __name__ == "__main__":
    sys.exit(main())
