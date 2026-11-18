#!/usr/bin/env python3
"""Usage: machine_quiet_check.py [--cpu N] [--runs N] [--median-max S] [--slow S] [--slow-allowed N] -- COMMAND...

Runs COMMAND a number of times pinned to one CPU and prints the wall time of
every run, the median and the largest. COMMAND should be a deterministic,
CPU-bound program of about 0.1 s whose time on a quiet machine is known.

The machine counts as quiet if the median is at most --median-max seconds and
at most --slow-allowed runs take longer than --slow seconds. Exit status 0 if
quiet, 1 if not. Without --median-max the tool only reports.

Why: on a virtual machine the same program can take up to twice as long when
the host is busy, without any load inside the machine (the load average stays
at zero). evaluation/results/tracker/R1/05-campaign-577528c/README.md has the
measurement that led to this check.
"""
import os
import statistics
import subprocess
import sys
import time


def main():
    args = sys.argv[1:]
    if "--" not in args:
        sys.exit(__doc__)
    split = args.index("--")
    options, command = args[:split], args[split + 1:]
    values = {"--cpu": "0", "--runs": "10", "--median-max": None, "--slow": None, "--slow-allowed": "0"}
    if len(options) % 2 or not command:
        sys.exit(__doc__)
    for name, value in zip(options[::2], options[1::2]):
        if name not in values:
            sys.exit(__doc__)
        values[name] = value
    times = []
    for _ in range(int(values["--runs"])):
        start = time.perf_counter()
        done = subprocess.run(["taskset", "-c", values["--cpu"]] + command, env=os.environ,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        times.append(time.perf_counter() - start)
        if done.returncode:
            sys.exit(f"machine_quiet_check.py: command failed with status {done.returncode}")
    median, largest = statistics.median(times), max(times)
    slow = sum(1 for t in times if values["--slow"] is not None and t > float(values["--slow"]))
    quiet = None
    if values["--median-max"] is not None:
        quiet = median <= float(values["--median-max"]) and slow <= int(values["--slow-allowed"])
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    verdict = "" if quiet is None else (" quiet" if quiet else " not-quiet")
    print(f"{stamp} cpu {values['--cpu']} runs {' '.join(f'{t:.3f}' for t in times)} "
          f"median {median:.3f} max {largest:.3f} slow {slow}{verdict}")
    sys.exit(0 if quiet in (None, True) else 1)


if __name__ == "__main__":
    main()
