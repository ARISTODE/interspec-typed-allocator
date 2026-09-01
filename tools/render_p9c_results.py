#!/usr/bin/env python3

import argparse
import csv
import json
from pathlib import Path


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def render(report, cases):
    paper = report["paper"]
    classification = report["classification"]
    prototype = report["prototype"]
    claim = report["coverage_claim"]
    audit = report.get("source_reconstruction_audit") or {}

    lines = [
        "# P9c SP3 Coverage Reconciliation",
        "",
        "This file is mechanically rendered from the P9c machine-readable report. "
        "P9c uses the final InterSpec paper coverage unit, an interface pointer field, "
        "and preserves the paper's total of 32 SP3 fields.",
        "",
        "## 1. Paper source of truth",
        "",
        f"The pinned processed paper table contains **{paper['sp3_case_count']} SP3 fields** "
        f"across **{paper['boundary_count']} boundaries**. The source is "
        f"`{paper['source']['repository']}@{paper['source']['commit']}` at "
        f"`{paper['source']['processed_table']}`.",
        "",
        "| Boundary | Paper SP3 fields | Raw case evidence alignment |",
        "| --- | ---: | --- |",
    ]
    for row in paper["boundaries"]:
        lines.append(f"| {row['boundary']} | {row['sp3_fields']} | {row['raw_alignment']} |")

    lines += [
        "",
        "## 2. Capability classification",
        "",
        f"Resolved eligible cases: **{classification['eligible']}**. "
        f"Resolved ineligible cases: **{classification['ineligible']}**. "
        f"Cases explicitly classified as insufficient source metadata: "
        f"**{classification['insufficient_source_metadata']}**.",
        "",
        "A paper case is not promoted merely because a raw report has the same row count or because "
        "its boundary has an Extended SP3 prototype. Exact field identity is required first.",
        "",
        "## 3. Source reconstruction audit",
        "",
    ]

    conclusion = audit.get("conclusion", {})
    if report.get("source_reconstruction_audit_complete"):
        lines += [
            "The reconstruction audit concludes that the preserved final-paper artifact does not "
            "contain a recoverable one-row-per-paper-field identity map for all 32 SP3 fields. "
            "The processed table is aggregate-only, while preserved raw reports differ in granularity, "
            "cardinality, report version, or boundary coverage.",
            "",
            f"Audit checks recorded: **{len(audit.get('checks', []))}**. "
            f"Exact case-level percentage supported: **no**.",
            "",
        ]
    else:
        lines += ["The source reconstruction audit is incomplete.", ""]

    lines += [
        "## 4. Defensible coverage claim",
        "",
        f"Paper denominator: **{claim['paper_denominator']}** SP3 fields. "
        f"Exact eligible lower bound: **{claim['exact_eligible_lower_bound']}**. "
        f"Exact demonstrated lower bound: **{claim['exact_demonstrated_lower_bound']}**.",
        "",
        "These lower bounds are provenance bounds, not estimates of actual applicability. "
        "P9c therefore does **not** report an Extended SP3 percentage over the 32 paper fields. "
        "Doing so would require inventing field identities that the preserved evidence does not establish.",
        "",
        "## 5. Existing prototype evidence",
        "",
        f"Exact paper cases mechanically mapped to a demonstrated prototype use: "
        f"**{prototype['demonstrated_exact_paper_cases']}**.",
        "",
        "| Boundary | Pointer shape | Backend evidence | Exact paper case mapping |",
        "| --- | --- | --- | --- |",
    ]
    for row in prototype["boundary_evidence"]:
        lines.append(
            f"| {row['boundary']} | {row['pointer_shape']} | "
            f"{', '.join(row['backend_evidence'])} | "
            f"{'yes' if row['exact_paper_case_mapping'] else 'no'} |"
        )

    examples = audit.get("paper_named_examples", [])
    if examples:
        lines += [
            "",
            "The paper also names concrete SP3 examples that correspond to pointer shapes demonstrated "
            "by the prototype. P9c records these as semantic corroboration only, not as exact case mappings:",
            "",
        ]
        for example in examples:
            lines.append(f"* **{example['boundary']}**: {example['prototype_relationship']}")

    lines += [
        "",
        "## 6. Machine-readable case units",
        "",
        f"`p9c-cases.csv` contains **{len(cases)} rows**, one stable count-unit identifier for every "
        "SP3 field reported by the paper. A generated identifier is not a claim about the original "
        "source field name.",
        "",
        f"P9c evaluation complete: **{'yes' if report['p9c_evaluation_complete'] else 'no'}**. "
        f"Capability resolution complete: **{'yes' if report['capability_resolution_complete'] else 'no'}**. "
        f"Source fidelity complete: **{'yes' if report['source_fidelity_complete'] else 'no'}**.",
        "",
        "The evaluation is complete in source-fidelity-limitation mode: the denominator is reproduced "
        "exactly, unresolved identities remain explicit, and the result refuses an unsupported precise "
        "coverage fraction.",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    cases = read_csv(args.cases)
    Path(args.output).write_text(render(report, cases) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
