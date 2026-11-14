#!/usr/bin/env python3
"""Run the rebuilt YAML parity set (tracker item I3): 48 processes.

Six documents x four modes (native, rlbox_only, tracked_no_check, extended_sp3)
x one and two parse iterations, on the builds without test hooks, with all
policy switches on. Each process must exit 0, print one YAML_BENCH line whose
events, scalars, scalar_bytes and hash equal the committed expectation
(evaluation/parity/yaml/expected.json, computed by an independent parser), and
report the expected number of checks. Raw output is written before anything is
compared and nothing is retried. Elapsed time in the output is not used.

This set is rebuilt from the description of the Stage 12 run. It is not the
original Stage 12 corpus, which is not in this repository.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

LINE = re.compile(r"^YAML_BENCH mode=(\S+) iterations=(\d+) input_bytes=(\d+) events=(\d+) "
                  r"scalars=(\d+) scalar_bytes=(\d+) hash=([0-9a-f]{16}) checks=(\d+) "
                  r"elapsed_ns=\d+$")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", required=True, type=Path)
    parser.add_argument("--rlbox", required=True, type=Path)
    parser.add_argument("--typed", required=True, type=Path)
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    expected = json.loads((args.corpus / "expected.json").read_text())["documents"]
    assert len(expected) == 6
    modes = {"native": (args.native, None), "rlbox_only": (args.rlbox, "rlbox_only"),
             "tracked_no_check": (args.typed, "tracked_no_check"),
             "extended_sp3": (args.typed, "extended_sp3")}
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "INTERSPEC_SP1": "1",
           "INTERSPEC_SP2": "1", "INTERSPEC_SP3": "1", "INTERSPEC_POLICY_REPORT": "1"}
    args.out.mkdir(parents=True)
    plan = []
    for name in sorted(expected):
        document = args.corpus / name
        assert hashlib.sha256(document.read_bytes()).hexdigest() == expected[name]["sha256"]
        for mode, (binary, argument) in modes.items():
            for iterations in ("1", "2"):
                command = [str(binary)] + ([argument] if argument else []) + \
                          [str(document), iterations]
                plan.append((f"{Path(name).stem}__{mode}__x{iterations}", name, mode,
                             iterations, command))
    assert len(plan) == 48

    for run, _, _, _, command in plan:
        directory = args.out / run
        directory.mkdir()
        done = subprocess.run(command, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=300)
        (directory / "command.json").write_text(json.dumps(command) + "\n")
        (directory / "stdout.txt").write_bytes(done.stdout)
        (directory / "stderr.txt").write_bytes(done.stderr)
        (directory / "exit_code.txt").write_text(f"{done.returncode}\n")

    rows, failures = [], 0
    for run, name, mode, iterations, _ in plan:
        directory = args.out / run
        want = expected[name]["expected"][iterations]
        stdout = (directory / "stdout.txt").read_text(errors="replace")
        stderr = (directory / "stderr.txt").read_text(errors="replace")
        code = int((directory / "exit_code.txt").read_text())
        lines = stdout.splitlines()
        match = LINE.match(lines[0]) if len(lines) == 1 else None
        checks = {"exit_zero": code == 0, "one_bench_line": match is not None}
        if match:
            checks["mode"] = match[1] == mode
            checks["iterations"] = match[2] == iterations
            checks["input_bytes"] = int(match[3]) == expected[name]["input_bytes"]
            checks["events"] = int(match[4]) == want["events"]
            checks["scalars"] = int(match[5]) == want["scalars"]
            checks["scalar_bytes"] = int(match[6]) == want["scalar_bytes"]
            checks["hash"] = match[7] == want["hash"]
            checks["checks"] = int(match[8]) == (want["scalars"] if mode == "extended_sp3" else 0)
        # The only permitted diagnostics are the wrapper's configuration line.
        other = [l for l in stderr.splitlines() if not l.startswith("INTERSPEC_POLICY ")]
        checks["no_other_stderr"] = not other
        if mode == "extended_sp3":
            checks["reports_all_on"] = (
                "INTERSPEC_POLICY boundary=yaml_libyaml sp1=1 sp2=1 sp3=full" in stderr)
        passed = all(checks.values())
        failures += not passed
        rows.append({"run": run, "passed": passed, "checks": checks})
        if not passed:
            print(f"FAIL {run}: " + ", ".join(k for k, v in checks.items() if not v))
    summary = {"total": len(rows), "passed": len(rows) - failures,
               "binaries_sha256": {k: hashlib.sha256(v[0].read_bytes()).hexdigest()
                                   for k, v in modes.items()},
               "expected_sha256": hashlib.sha256(
                   (args.corpus / "expected.json").read_bytes()).hexdigest(),
               "runs": rows}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"yaml parity: {summary['passed']}/{summary['total']} runs passed")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
