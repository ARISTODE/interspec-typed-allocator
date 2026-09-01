#!/usr/bin/env python3

import argparse
import csv
from pathlib import Path


def read_csv(path):
    with Path(path).open(newline="") as source:
        return list(csv.DictReader(source))


def num(value, digits=3):
    return f"{float(value):.{digits}f}"


def pct(value):
    return f"{float(value):.1f}%"


def render(rows, reference_commit, environment_note):
    lines = [
        "# P9a RLBox-Only Baseline Results",
        "",
        "This file is mechanically rendered from the P9a three-way rsync measurement artifact. "
        "The values are a reproducible CI reference; final publication timings should be regenerated "
        "on controlled hardware.",
        "",
        "Reference implementation commit:",
        "",
        "```text",
        reference_commit,
        "```",
        "",
        "Reference environment:",
        "",
        "```text",
        environment_note.strip(),
        "```",
        "",
        "## Three-way application comparison",
        "",
        "`rlbox_only` uses the same pinned RLBox + NaCl sandbox and rsync/popt API bridge, but ordinary "
        "sandbox allocation is used and the trusted bridge does not reserve the typed arena, instantiate "
        "PolicyRuntime, register allocation provenance/lifetime callbacks, or execute Extended-SP3 validation. "
        "`tracked_no_check` enables typed allocation/provenance but bypasses final pointer acceptance. "
        "`extended_sp3` enables the complete mechanism.",
        "",
        "| Workload | RLBox only median (ms) | Tracked/no-check median (ms) | Extended SP3 median (ms) | Tracking/provenance overhead | Validation overhead | Total Extended-SP3 overhead |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['workload']} | {num(row['rlbox_median_ms'])} | "
            f"{num(row['tracked_median_ms'])} | {num(row['extended_median_ms'])} | "
            f"{pct(row['tracking_overhead_median_pct'])} | "
            f"{pct(row['validation_overhead_median_pct'])} | "
            f"{pct(row['total_overhead_median_pct'])} |"
        )

    lines += [
        "",
        "The decomposition is intentionally paired within each repetition: tracking/provenance is "
        "`tracked_no_check / rlbox_only`, validation is `extended_sp3 / tracked_no_check`, and total "
        "mechanism overhead is `extended_sp3 / rlbox_only`. Percentages should not be added because "
        "the denominators differ.",
        "",
        "This P9a baseline removes InterSpec from the measured rsync/popt runtime path but still uses "
        "the same NaCl backend build containing dormant InterSpec support code. No typed arena or InterSpec "
        "callbacks are activated in `rlbox_only`. P9b remains responsible for reproducing the final "
        "paper experiment on the wasm2c backend used by the existing InterSpec evaluation.",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    text = render(
        read_csv(args.summary),
        args.commit,
        Path(args.environment).read_text(),
    )
    Path(args.output).write_text(text + "\n")


if __name__ == "__main__":
    main()
