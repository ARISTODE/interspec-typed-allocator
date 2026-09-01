#!/usr/bin/env python3

import argparse
import csv
import json
from pathlib import Path


def read_csv(path):
    with Path(path).open(newline="") as source:
        return list(csv.DictReader(source))


def pct(value):
    return f"{float(value):.1f}%"


def num(value, digits=2):
    return f"{float(value):.{digits}f}"


def selected_runtime_rows(rows):
    populations = {1, 256, 4096, 16384}
    selected = []
    for row in rows:
        if row["metric"] not in {"check_live", "remaining_bytes"}:
            continue
        if int(row["threads"]) != 1 or int(row["population"]) not in populations:
            continue
        selected.append(row)
    return sorted(selected, key=lambda r: (int(r["population"]), r["metric"]))


def render(deterministic, automation_rows, boundary_rows, app_rows,
           reference_commit, environment_note, runtime_rows=None):
    sec = deterministic["security"]
    auto = deterministic["automation"]

    lines = [
        "# P8 Representative Results",
        "",
        "This file is mechanically rendered from P8 machine-readable evaluation artifacts. "
        "The performance values below are a reproducible CI reference, not controlled-hardware "
        "publication numbers. Final paper timings should be regenerated with the same artifact "
        "formats on a dedicated machine.",
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
        "## 1. Security",
        "",
        f"The deterministic runtime security matrix passed **{sec['passed']}/{sec['case_count']}** cases. "
        "The real RLBox + NaCl boundary regression additionally exercises valid behavior and "
        "wrong-type, untracked same-domain, and spatial-overflow rejection where applicable.",
        "",
        "## 2. Automation and policy composition",
        "",
        f"Across **{auto['boundary_count']}** real boundaries, the integration allocation policy contains "
        f"**{auto['inferred_allocation_sites']} source-derived allocation sites** and "
        f"**{auto['integration_helper_sites']} explicit integration helper sites**. "
        f"The source-derived fraction is **{pct(100 * auto['source_derived_fraction_of_integration_allocation_policy'])}**. "
        f"The report separately excludes **{auto['adversarial_helper_sites_excluded_from_automation']}** "
        "test-only helper sites from that denominator.",
        "",
        "| Boundary | Source-derived sites | Integration helpers | Trusted uses | Pointer shape |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for row in automation_rows:
        lines.append(
            f"| {row['boundary']} | {row['inferred_allocation_sites']} | "
            f"{row['integration_helper_sites']} | {row['trusted_uses']} | "
            f"{row['pointer_shapes'].replace(';', ', ')} |"
        )

    lines += [
        "",
        "The explicit helpers for PCRE and libyaml correspond to real allocator abstractions "
        "(`pcre_malloc` and `YAML_MALLOC`) rather than direct `malloc` syntax. They are reported "
        "as explicit policy rather than being counted as source-derived direct-allocation inference.",
    ]

    if runtime_rows:
        lines += [
            "",
            "## 3. Trusted metadata runtime cost",
            "",
            "The low-level runtime benchmark measures trusted metadata operations without a sandbox crossing. "
            "The selected rows below show how containing-allocation lookup scales with the number of live allocations.",
            "",
            "| Live allocations | Operation | ns/op |",
            "| ---: | --- | ---: |",
        ]
        for row in selected_runtime_rows(runtime_rows):
            lines.append(
                f"| {row['population']} | {row['metric']} | {num(row['ns_per_op'])} |"
            )
        boundary_section = "## 4. Incremental validation cost at real boundaries"
        app_section = "## 5. Complete rsync paired measurement"
        interpretation_section = "## 6. Interpretation and limitations"
    else:
        boundary_section = "## 3. Incremental validation cost at real boundaries"
        app_section = "## 4. Complete rsync paired measurement"
        interpretation_section = "## 5. Interpretation and limitations"

    lines += [
        "",
        boundary_section,
        "",
        "These measurements keep the real U object, sandbox, typed allocation/provenance, and copy "
        "behavior fixed. `tracked_no_check` bypasses only the final T-side Extended-SP3 acceptance "
        "check. Thus the overhead is **incremental validation overhead**, not total overhead over plain RLBox. "
        "Because the no-check operation itself is only a few nanoseconds, percentage changes can look "
        "large; the absolute added nanoseconds are therefore shown explicitly.",
        "",
        "| Boundary | Baseline median (ns) | Extended SP3 median (ns) | Added median time (ns) | Paired median overhead |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in boundary_rows:
        baseline = float(row['baseline_median_ns'])
        extended = float(row['extended_median_ns'])
        lines.append(
            f"| {row['boundary']} | {num(baseline)} | {num(extended)} | "
            f"{num(extended - baseline)} | {pct(row['paired_overhead_median_pct'])} |"
        )

    lines += [
        "",
        app_section,
        "",
        "The complete pinned rsync executable is rebuilt twice from the same object files and linked "
        "against the same NaCl module. The measurement-only variant changes only the final trusted "
        "pointer validation in the popt bridge.",
        "",
        "| Workload | Baseline median (ms) | Extended SP3 median (ms) | Median-time delta (ms) | Paired median overhead |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in app_rows:
        baseline = float(row['baseline_median_ms'])
        extended = float(row['extended_median_ms'])
        lines.append(
            f"| {row['workload']} | {num(baseline, 3)} | {num(extended, 3)} | "
            f"{num(extended - baseline, 3)} | {pct(row['paired_overhead_median_pct'])} |"
        )

    lines += [
        "",
        interpretation_section,
        "",
        "P8 separates three performance questions rather than collapsing them into one number: "
        "the runtime benchmark characterizes trusted metadata operations, the real-boundary benchmark "
        "isolates final pointer-validation cost, and the complete-rsync pair measures that validation "
        "change at the application level. None of these is a total RLBox-only-versus-Extended-SP3 "
        "comparison because typed allocation/provenance remains enabled in the paired baseline.",
        "",
        "The security claim remains limited to liveness, expected trusted allocation type, and spatial "
        "containment of the requested extent. It does not establish general CFI, U object-content "
        "integrity, intended-object identity among simultaneous same-type allocations, or temporal "
        "identity under physical address reuse.",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--deterministic", required=True)
    parser.add_argument("--automation", required=True)
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--boundary-summary", required=True)
    parser.add_argument("--application-summary", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    deterministic = json.loads(Path(args.deterministic).read_text())
    text = render(
        deterministic,
        read_csv(args.automation),
        read_csv(args.boundary_summary),
        read_csv(args.application_summary),
        args.commit,
        Path(args.environment).read_text(),
        read_csv(args.runtime),
    )
    Path(args.output).write_text(text + "\n")


if __name__ == "__main__":
    main()
