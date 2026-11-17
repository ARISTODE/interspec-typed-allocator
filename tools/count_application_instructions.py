#!/usr/bin/env python3
"""Instructions executed by rsync/popt and yaml/libyaml (tracker item R3).

The counterpart of tools/count_port_instructions.py for the two single-process
applications. Each configuration runs under `valgrind --tool=callgrind
--trace-children=yes`; the count of a run is the sum of the `Collected` lines of
all its processes (rsync forks). Every run is made `--repeat` times and all
counts are written out, so that the reader sees whether a count repeats.

rsync: the two workloads of tools/benchmark_policy_cost.py (option parsing and
the 194 MiB file sync); the count is that of the whole run, process start and
sandbox creation included.
yaml: the fixed 1 MiB document parsed `--iterations` and half as many times;
the count per parse is the difference quotient, so that process start, sandbox
creation and reading the input cancel.

Configurations: native, rlbox-only (SP1 and SP2 off, registry compiled out),
interspec with all policies on, and the interspec binary with all policies off.

A count is not a time: it does not see cache misses, branch mispredictions or
code alignment. It answers how much more work a configuration does.
"""

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_policy_cost import Rsync, policy_env  # noqa: E402

CONFIGS = {"native": ("native", None), "rlbox-only": ("rlbox-only", ("0", "0", "1")),
           "interspec": ("interspec", ("1", "1", "1")),
           "interspec-all-off": ("interspec", ("0", "0", "0"))}


def count(command, switches, stem):
    done = subprocess.run(["valgrind", "--tool=callgrind", "--trace-children=yes",
                           f"--callgrind-out-file={stem}.%p.callgrind"] + command,
                          env=policy_env(switches), stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=14400)
    Path(f"{stem}.stdout.txt").write_bytes(done.stdout)
    Path(f"{stem}.stderr.txt").write_bytes(done.stderr)
    collected = [int(n) for n in re.findall(r"Collected : (\d+)", done.stderr.decode(errors="replace"))]
    if done.returncode != 0 or not collected:
        sys.exit(f"{stem}: exit {done.returncode}, {len(collected)} counts; see {stem}.stderr.txt")
    return sum(collected), len(collected), done.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("application", choices=("rsync", "yaml"))
    parser.add_argument("--native", required=True, type=Path)
    parser.add_argument("--rlbox-only", required=True, type=Path)
    parser.add_argument("--interspec", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--scratch", type=Path, help="rsync: directory for the files to sync")
    parser.add_argument("--input", type=Path, help="yaml: the fixed document")
    parser.add_argument("--iterations", type=int, default=12, help="yaml: parses of the larger run")
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--source-commit", default="")
    args = parser.parse_args()
    binaries = {"native": args.native, "rlbox-only": args.rlbox_only, "interspec": args.interspec}
    args.out.mkdir(parents=True)
    rows = []

    def run(workload, size, command_of, after=None):
        reference = None
        for name, (binary, switches) in CONFIGS.items():
            for repeat in range(args.repeat):
                stem = args.out / f"{workload}-{size}-{name}-{repeat}"
                total, processes, stdout = count(command_of(name, binary), switches, stem)
                result = after(name, stdout) if after else None
                reference = result if reference is None else reference
                if result != reference:
                    sys.exit(f"{stem}: result differs from the first configuration")
                if repeat:  # keep the profiles of one run, the counts of all
                    for profile in args.out.glob(f"{stem.name}.*.callgrind"):
                        profile.unlink()
                rows.append({"workload": workload, "size": size, "configuration": name,
                             "repeat": repeat, "processes": processes, "instructions": total})
                print(f"{workload} {size} {name} #{repeat}: {total:,} in {processes} process(es)",
                      flush=True)

    if args.application == "rsync":
        adapter = Rsync(SimpleNamespace(rlbox_only=args.rlbox_only, interspec=args.interspec,
                                        cpu=0, scratch=args.scratch))
        for workload in adapter.workloads:
            def command(name, binary, workload=workload):
                if workload == "file_sync_194mb":
                    shutil.rmtree(adapter.dst)
                    adapter.dst.mkdir()
                return [str(binaries[binary])] + adapter.arguments(workload)

            def after(name, stdout, workload=workload):
                if workload == "option_parse":
                    return "exit 0"  # the version text names the build
                return (adapter.dst / "sync-194mb.bin").stat().st_size
            run(workload, "run", command, after)
        sizes = {"run": 1}
    else:
        from yaml_measurement_validation import parse_line
        modes = {"rlbox-only": "rlbox_only", "interspec": "extended_sp3"}
        low, high = args.iterations // 2, args.iterations
        for iterations in (low, high):
            def command(name, binary, iterations=iterations):
                mode = [] if binary == "native" else [modes[binary]]  # the native program has no mode
                return [str(binaries[binary])] + mode + [str(args.input), str(iterations)]

            def after(name, stdout):
                row = parse_line(stdout.decode())
                return (row["iterations"], row["events"], row["scalars"], row["hash"])
            run("yaml_parse_1mb", iterations, command, after)
        sizes = {low: low, high: high}

    with (args.out / "counts.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    def counts(workload, size, name):
        return [r["instructions"] for r in rows
                if (r["workload"], r["size"], r["configuration"]) == (workload, size, name)]

    summary = {"application": args.application, "source_commit": args.source_commit,
               "workloads": {}}
    lines = []
    for workload in dict.fromkeys(r["workload"] for r in rows):
        entry = {}
        for name in CONFIGS:
            per_size = {size: counts(workload, size, name) for size in sizes}
            spread = max(max(c) - min(c) for c in per_size.values())
            if args.application == "yaml":
                (low, low_counts), (high, high_counts) = per_size.items()
                value = (high_counts[0] - low_counts[0]) / (high - low)
            else:
                value = per_size["run"][0]
            entry[name] = {"counts": {str(k): v for k, v in per_size.items()},
                           "largest_difference_between_repeats": spread, "instructions": value}
        base = entry["rlbox-only"]["instructions"]
        for name in CONFIGS:
            entry[name]["against_rlbox_only_percent"] = 100 * (entry[name]["instructions"] / base - 1)
        summary["workloads"][workload] = entry
        unit = "per parse" if args.application == "yaml" else "of the whole run"
        lines += [f"### {args.application}, {workload}", "",
                  f"| Configuration | Instructions {unit} | Against rlbox-only | "
                  "Largest difference between repeats |", "|---|---:|---:|---:|"]
        lines += [f"| {name} | {e['instructions']:,.0f} | {e['against_rlbox_only_percent']:+.2f}% | "
                  f"{e['largest_difference_between_repeats']:,} |" for name, e in entry.items()]
        lines.append("")
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    (args.out / "TABLE.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
