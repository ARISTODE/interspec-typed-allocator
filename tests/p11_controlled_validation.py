#!/usr/bin/env python3

import csv
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools" / "validate_p11_controlled.py"
MODES = ("rlbox_only", "tracked_no_check", "extended_sp3")
WORKLOADS = ("option_parse", "local_dry_run")


def write_environment(path, repetitions=31, warmups=3, affinity="2"):
    path.write_text(
        "\n".join(
            [
                "commit=test",
                "kernel=test",
                "cpu=test",
                "logical_cpus=4",
                "governor=performance",
                "turbo=intel_pstate_no_turbo=1",
                f"cpu_affinity={affinity}",
                f"repetitions={repetitions}",
                f"warmups={warmups}",
                "hosted_ci=true",
                "measurement=complete process wall time via time.perf_counter_ns",
                "rlbox_baseline=rlbox_only",
                "tracking_configuration=tracked_no_check",
                "security_configuration=extended_sp3",
                "rlbox_wasm2c_revision=c4f18c48cea47421617f72ba5edc95c68aa85671",
                "rsync_revision=7c20b077c980036a19587701cec320cc88e42a4a",
            ]
        )
        + "\n"
    )


def write_summary(path, repetitions=31):
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=["workload", "repetitions"])
        writer.writeheader()
        for workload in WORKLOADS:
            writer.writerow({"workload": workload, "repetitions": repetitions})


def write_raw(path, repetitions=31):
    with path.open("w", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(["workload", "mode", "repetition", "total_ns"])
        for workload in WORKLOADS:
            for repetition in range(repetitions):
                for mode in MODES:
                    writer.writerow([workload, mode, repetition, 1000000 + repetition])


def run_validator(tmp, runner="self-hosted"):
    report = tmp / "validation.txt"
    return subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--environment",
            str(tmp / "environment.txt"),
            "--summary",
            str(tmp / "summary.csv"),
            "--raw",
            str(tmp / "raw.csv"),
            "--runner-environment",
            runner,
            "--output",
            str(report),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def main():
    with tempfile.TemporaryDirectory() as directory:
        tmp = Path(directory)
        write_environment(tmp / "environment.txt")
        write_summary(tmp / "summary.csv")
        write_raw(tmp / "raw.csv")
        valid = run_validator(tmp)
        assert valid.returncode == 0, valid.stdout
        assert "publication_candidate=PASS" in valid.stdout

        hosted = run_validator(tmp, runner="github-hosted")
        assert hosted.returncode != 0
        assert "GitHub-hosted runners are reference-only" in hosted.stdout

        write_environment(tmp / "environment.txt", repetitions=5)
        write_summary(tmp / "summary.csv", repetitions=5)
        write_raw(tmp / "raw.csv", repetitions=5)
        short = run_validator(tmp)
        assert short.returncode != 0
        assert "at least 31 repetitions" in short.stdout

        write_environment(tmp / "environment.txt", affinity="unrestricted")
        write_summary(tmp / "summary.csv")
        write_raw(tmp / "raw.csv")
        unpinned = run_validator(tmp)
        assert unpinned.returncode != 0
        assert "must pin measured processes" in unpinned.stdout

    print("P11 controlled-hardware validator: all checks passed")


if __name__ == "__main__":
    main()
