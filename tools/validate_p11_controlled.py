#!/usr/bin/env python3

import argparse
import csv
from pathlib import Path

EXPECTED_WORKLOADS = {"option_parse", "local_dry_run"}
EXPECTED_MODES = {"rlbox_only", "tracked_no_check", "extended_sp3"}
PINNED_WASM2C = "c4f18c48cea47421617f72ba5edc95c68aa85671"
PINNED_RSYNC = "7c20b077c980036a19587701cec320cc88e42a4a"


def parse_environment(path):
    values = {}
    for line in Path(path).read_text().splitlines():
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def read_csv(path):
    with Path(path).open(newline="") as source:
        return list(csv.DictReader(source))


def validate(environment, summary, raw, runner_environment):
    errors = []
    warnings = []

    if runner_environment not in {"self-hosted", "local"}:
        errors.append(
            "runner environment must be self-hosted or local; GitHub-hosted runners are reference-only"
        )

    try:
        repetitions = int(environment.get("repetitions", "0"))
    except ValueError:
        repetitions = 0
    try:
        warmups = int(environment.get("warmups", "-1"))
    except ValueError:
        warmups = -1

    if repetitions < 31:
        errors.append(f"controlled run requires at least 31 repetitions, found {repetitions}")
    if warmups < 3:
        errors.append(f"controlled run requires at least 3 warmups, found {warmups}")

    affinity = environment.get("cpu_affinity", "unrestricted")
    if not affinity or affinity == "unrestricted":
        errors.append("controlled run must pin measured processes with INTERSPEC_P11_CPU")

    if environment.get("rlbox_wasm2c_revision") != PINNED_WASM2C:
        errors.append("unexpected RLBox wasm2c revision")
    if environment.get("rsync_revision") != PINNED_RSYNC:
        errors.append("unexpected rsync revision")

    governor = environment.get("governor", "unknown")
    turbo = environment.get("turbo", "unknown")
    if governor == "unknown":
        warnings.append(
            "CPU governor is not exposed; document how frequency policy was kept stable on the host"
        )
    if turbo == "unknown":
        warnings.append(
            "turbo/boost state is not exposed; document how boost policy was kept stable on the host"
        )

    if runner_environment == "self-hosted" and environment.get("hosted_ci") == "true":
        warnings.append(
            "environment.txt records hosted_ci=true because the base driver sees GITHUB_ACTIONS; "
            "RUNNER_ENVIRONMENT=self-hosted is authoritative for this controlled workflow"
        )

    summary_by_workload = {row.get("workload"): row for row in summary}
    missing = EXPECTED_WORKLOADS - set(summary_by_workload)
    if missing:
        errors.append("summary is missing workloads: " + ", ".join(sorted(missing)))
    for workload in EXPECTED_WORKLOADS & set(summary_by_workload):
        row = summary_by_workload[workload]
        try:
            row_repetitions = int(row.get("repetitions", "0"))
        except ValueError:
            row_repetitions = 0
        if row_repetitions != repetitions:
            errors.append(
                f"summary repetition count for {workload} is {row_repetitions}, expected {repetitions}"
            )

    triples = {}
    for row in raw:
        workload = row.get("workload")
        mode = row.get("mode")
        try:
            repetition = int(row.get("repetition", "-1"))
            total_ns = int(row.get("total_ns", "0"))
        except ValueError:
            errors.append("raw CSV contains a non-integer repetition or timing")
            continue
        if workload not in EXPECTED_WORKLOADS:
            errors.append(f"raw CSV contains unexpected workload {workload!r}")
            continue
        if mode not in EXPECTED_MODES:
            errors.append(f"raw CSV contains unexpected mode {mode!r}")
            continue
        if total_ns <= 0:
            errors.append("raw CSV contains a non-positive timing")
        key = (workload, repetition)
        triples.setdefault(key, set())
        if mode in triples[key]:
            errors.append(f"duplicate raw sample for {workload} repetition {repetition} mode {mode}")
        triples[key].add(mode)

    for workload in EXPECTED_WORKLOADS:
        for repetition in range(repetitions):
            modes = triples.get((workload, repetition), set())
            if modes != EXPECTED_MODES:
                errors.append(
                    f"incomplete raw triple for {workload} repetition {repetition}: {sorted(modes)}"
                )

    expected_rows = len(EXPECTED_WORKLOADS) * repetitions * len(EXPECTED_MODES)
    if len(raw) != expected_rows:
        errors.append(f"raw CSV has {len(raw)} rows, expected {expected_rows}")

    return errors, warnings


def render(errors, warnings, runner_environment):
    lines = [
        "P11 controlled-hardware validation",
        f"runner_environment={runner_environment}",
        f"publication_candidate={'PASS' if not errors else 'FAIL'}",
    ]
    if errors:
        lines.append("errors:")
        lines.extend(f"  {item}" for item in errors)
    if warnings:
        lines.append("warnings:")
        lines.extend(f"  {item}" for item in warnings)
    if not errors and not warnings:
        lines.append("warnings: none")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--raw", required=True)
    parser.add_argument("--runner-environment", default="local")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    errors, warnings = validate(
        parse_environment(args.environment),
        read_csv(args.summary),
        read_csv(args.raw),
        args.runner_environment,
    )
    report = render(errors, warnings, args.runner_environment)
    Path(args.output).write_text(report)
    print(report, end="")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
