#!/usr/bin/env python3

import argparse
import csv
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
from collections import defaultdict

MODES = ("native", "rlbox_only", "tracked_no_check", "extended_sp3")


def parse_line(stdout):
    lines = [line for line in stdout.splitlines() if line.startswith("YAML_BENCH ")]
    if len(lines) != 1:
        raise RuntimeError(f"unexpected YAML output: {stdout!r}")
    return dict(item.split("=", 1) for item in lines[0].split()[1:])


def run(command, check=True):
    completed = subprocess.run(command, text=True, capture_output=True)
    if check and completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {command}\n"
            f"stdout={completed.stdout}\nstderr={completed.stderr}"
        )
    return completed


def make_document(path):
    target = 1024 * 1024
    lines = [b"---\n"]
    for i in range(256):
        key = f"key{i:03d}".encode()
        fill = bytes([97 + (i % 26)]) * 4000
        lines.append(key + b": " + fill + b"\n")
    body = b"".join(lines)
    tail = b"...\n"
    remaining = target - len(body) - len(tail)
    if remaining < 3:
        raise RuntimeError("generated YAML exceeded 1 MiB")
    filler = b"#" + b"x" * (remaining - 2) + b"\n"
    data = body + filler + tail
    if len(data) != target:
        raise RuntimeError("generated YAML is not exactly 1 MiB")
    path.write_bytes(data)


def signature(row):
    return tuple(
        row[key]
        for key in ("iterations", "input_bytes", "events", "scalars", "scalar_bytes", "hash")
    )


def mode_command(args, mode, input_path, iterations, fault=0):
    if mode == "native":
        return [args.native, str(input_path), str(iterations)]
    if mode == "rlbox_only":
        return [args.rlbox, "rlbox_only", str(input_path), str(iterations)]
    command = [args.typed, mode, str(input_path), str(iterations)]
    if fault:
        command.append(str(fault))
    return command


def paired_overhead(numerator, denominator):
    return (numerator / denominator - 1.0) * 100.0


def summarize(samples):
    by_mode = defaultdict(list)
    groups = defaultdict(dict)
    for row in samples:
        by_mode[row["mode"]].append(row["total_ns"])
        groups[row["repetition"]][row["mode"]] = row["total_ns"]

    result = {}
    for mode in MODES:
        values = by_mode[mode]
        result[f"{mode}_median_ms"] = statistics.median(values) / 1e6
        result[f"{mode}_mean_ms"] = statistics.fmean(values) / 1e6

    metrics = {
        "isolation_overhead": [],
        "tracking_overhead": [],
        "validation_overhead": [],
        "total_overhead": [],
        "interspec_vs_native": [],
    }
    for repetition, values in sorted(groups.items()):
        if set(values) != set(MODES):
            raise RuntimeError(f"incomplete YAML repetition {repetition}")
        metrics["isolation_overhead"].append(
            paired_overhead(values["rlbox_only"], values["native"])
        )
        metrics["tracking_overhead"].append(
            paired_overhead(values["tracked_no_check"], values["rlbox_only"])
        )
        metrics["validation_overhead"].append(
            paired_overhead(values["extended_sp3"], values["tracked_no_check"])
        )
        metrics["total_overhead"].append(
            paired_overhead(values["extended_sp3"], values["rlbox_only"])
        )
        metrics["interspec_vs_native"].append(
            paired_overhead(values["extended_sp3"], values["native"])
        )

    for name, values in metrics.items():
        result[f"{name}_median_pct"] = statistics.median(values)
        result[f"{name}_mean_pct"] = statistics.fmean(values)
        result[f"{name}_min_pct"] = min(values)
        result[f"{name}_max_pct"] = max(values)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--native", required=True)
    parser.add_argument("--rlbox", required=True)
    parser.add_argument("--typed", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--commit", default="unknown")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    input_path = out / "document-1m.yaml"
    make_document(input_path)

    correctness_iterations = int(os.environ.get("INTERSPEC_YAML_CORRECTNESS_ITERATIONS", "2"))
    correctness = {}
    reference = None
    for mode in MODES:
        completed = run(mode_command(args, mode, input_path, correctness_iterations))
        row = parse_line(completed.stdout)
        correctness[mode] = row
        (out / f"correctness-{mode}.stdout").write_text(completed.stdout)
        (out / f"correctness-{mode}.stderr").write_text(completed.stderr)
        if reference is None:
            reference = signature(row)
        elif signature(row) != reference:
            raise RuntimeError(f"correctness mismatch for {mode}")

    (out / "correctness.json").write_text(
        json.dumps(
            {
                "passed": True,
                "iterations": correctness_iterations,
                "variants": correctness,
            },
            indent=2,
        )
    )

    expected = {1: "wrong_type", 2: "untracked", 3: "untracked", 4: "out_of_bounds"}
    rejections = {}
    for fault, reason in expected.items():
        completed = run(
            mode_command(args, "extended_sp3", input_path, 1, fault=fault),
            check=False,
        )
        (out / f"fault-{fault}.stdout").write_text(completed.stdout)
        (out / f"fault-{fault}.stderr").write_text(completed.stderr)
        if completed.returncode != 86 or f"reason={reason}" not in completed.stderr:
            raise RuntimeError(
                f"fault {fault} expected {reason}, rc=86; got "
                f"rc={completed.returncode}, stderr={completed.stderr!r}"
            )
        rejections[str(fault)] = reason

    same_type = run(mode_command(args, "extended_sp3", input_path, 1, fault=5))
    native_once = run(mode_command(args, "native", input_path, 1))
    same_row = parse_line(same_type.stdout)
    native_row = parse_line(native_once.stdout)
    if signature(same_row) != signature(native_row):
        raise RuntimeError("same-type substitution changed valid YAML result")
    (out / "fault-5.stdout").write_text(same_type.stdout)
    (out / "fault-5.stderr").write_text(same_type.stderr)

    security = {
        "passed": True,
        "rejections": rejections,
        "same_type_substitution": {
            "accepted": True,
            "contents_match_native": True,
        },
    }
    (out / "security.json").write_text(json.dumps(security, indent=2))

    iterations = int(os.environ.get("INTERSPEC_YAML_ITERATIONS", "1000"))
    repetitions = int(os.environ.get("INTERSPEC_YAML_REPETITIONS", "15"))
    warmups = int(os.environ.get("INTERSPEC_YAML_WARMUPS", "2"))
    if iterations < 1 or repetitions < 3 or warmups < 0:
        raise RuntimeError("invalid YAML benchmark settings")

    variants = [
        (mode, mode_command(args, mode, input_path, iterations))
        for mode in MODES
    ]
    rotations = [variants[i:] + variants[:i] for i in range(len(variants))]
    orders = rotations + [list(reversed(order)) for order in rotations]

    for _ in range(warmups):
        for _, command in variants:
            parse_line(run(command).stdout)

    samples = []
    run_stats = []
    performance_signature = None
    for repetition in range(repetitions):
        for mode, command in orders[repetition % len(orders)]:
            completed = run(command)
            row = parse_line(completed.stdout)
            sig = signature(row)
            if performance_signature is None:
                performance_signature = sig
            elif sig != performance_signature:
                raise RuntimeError(
                    f"performance output mismatch for {mode}, repetition {repetition}"
                )
            samples.append(
                {
                    "workload": "yaml_parse_1mb",
                    "mode": mode,
                    "repetition": repetition,
                    "total_ns": int(row["elapsed_ns"]),
                }
            )
            run_stats.append({"repetition": repetition, **row})

    with (out / "yaml-performance.csv").open("w", newline="") as output:
        writer = csv.DictWriter(
            output, fieldnames=["workload", "mode", "repetition", "total_ns"]
        )
        writer.writeheader()
        writer.writerows(samples)

    (out / "run-stats.jsonl").write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in run_stats) + "\n"
    )

    summary = summarize(samples)
    with (out / "yaml-performance-summary.csv").open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(summary))
        writer.writeheader()
        writer.writerow(summary)

    env = {
        "commit": args.commit,
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "iterations": iterations,
        "repetitions": repetitions,
        "warmups": warmups,
        "input_bytes": input_path.stat().st_size,
        "hosted_ci": os.environ.get("GITHUB_ACTIONS", "false"),
        "measurement": (
            "parse loop; sandboxed variants include per-iteration T-to-U input copy"
        ),
        "native_baseline": "native libyaml parser",
        "rlbox_baseline": "RLBox wasm2c with boundary scalar copy",
        "tracking_configuration": (
            "typed scalar staging allocation, final SP3 check disabled"
        ),
        "security_configuration": (
            "typed scalar staging allocation plus liveness/type/extent check"
        ),
        "rlbox_wasm2c_revision": "c4f18c48cea47421617f72ba5edc95c68aa85671",
        "libyaml_revision": "90a56d4500aa1a1798514c5cb55c3ad4cb095f94",
    }
    (out / "environment.json").write_text(json.dumps(env, indent=2))

    def ms(key):
        return f"{summary[key]:.3f}"

    def pct(key):
        return f"{summary[key]:.2f}%"

    scalar_per_parse = int(correctness["native"]["scalars"]) // correctness_iterations
    lines = [
        "# YAML/libyaml Evaluation Results",
        "",
        "The full libyaml parser processes a deterministic 1 MiB YAML document. "
        "Hosted CI values are reference measurements; publication numbers require "
        "the same driver on controlled hardware.",
        "",
        f"Reference commit: {args.commit}",
        "",
        "## Correctness and security",
        "",
        "* Native, RLBox-only, tracking-only, and Extended-SP3 outputs match.",
        "* Wrong-type, ordinary untracked, released, and excessive-extent scalar "
        "pointers are rejected before trusted copying.",
        "* A live same-type substitution is accepted with unchanged contents, "
        "matching the current SP3 scope.",
        f"* The benchmark produces {scalar_per_parse} scalar boundary values per parse.",
        "",
        "## Performance",
        "",
        "| Native median (ms) | RLBox median (ms) | Tracking median (ms) | "
        "InterSpec median (ms) | RLBox vs Native | Tracking vs RLBox | "
        "Validation vs Tracking | InterSpec vs RLBox | InterSpec vs Native |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| {ms('native_median_ms')} | {ms('rlbox_only_median_ms')} | "
        f"{ms('tracked_no_check_median_ms')} | {ms('extended_sp3_median_ms')} | "
        f"{pct('isolation_overhead_median_pct')} | "
        f"{pct('tracking_overhead_median_pct')} | "
        f"{pct('validation_overhead_median_pct')} | "
        f"{pct('total_overhead_median_pct')} | "
        f"{pct('interspec_vs_native_median_pct')} |",
        "",
        "Overheads are medians of paired per-repetition ratios. Negative values "
        "are not interpreted as speedups.",
        "",
        "## Environment",
        "",
        json.dumps(env, indent=2),
        "",
    ]
    (out / "YAML_RESULTS.md").write_text("\n".join(lines))
    print((out / "YAML_RESULTS.md").read_text())


if __name__ == "__main__":
    main()
