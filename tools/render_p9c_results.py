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
        lines.append(
            f"| {row['boundary']} | {row['sp3_fields']} | {row['raw_alignment']} |"
        )

    lines += [
        "",
        "## 2. Capability classification",
        "",
        f"Resolved eligible cases: **{classification['eligible']}**. "
        f"Resolved ineligible cases: **{classification['ineligible']}**. "
        f"Cases explicitly classified as insufficient source metadata: "
        f"**{classification['insufficient_source_metadata']}**.",
        "",
        "The current result intentionally does not turn matching raw row counts into paper field "
        "identities. The processed paper artifact preserves aggregate SP3 counts, while the packaged "
        "raw reports come from report paths whose cardinality or semantics are not consistently "
        "paper aligned. Therefore a precise Extended SP3 coverage percentage over the 32 paper fields "
        "is not yet supported by the preserved evidence.",
        "",
        "## 3. Existing prototype evidence",
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

    lines += [
        "",
        "These boundary integrations are valid mechanism evidence, but P9c does not count them as "
        "coverage of a particular paper field until the original field identity is reconstructed and "
        "bound to that trusted use.",
        "",
        "## 4. Machine-readable case units",
        "",
        f"`p9c-cases.csv` contains **{len(cases)} rows**, one stable count-unit identifier for every "
        "SP3 field reported by the paper. A generated identifier is not a claim about the original "
        "source field name. Its purpose is to make unresolved evidence explicit instead of inventing "
        "a mapping.",
        "",
        "P9c can move a case from `insufficient_source_metadata` to `eligible` or `ineligible` only "
        "through a manifest override that records the reconstructed identity and source basis. "
        "A demonstrated prototype claim additionally requires an exact paper-case mapping.",
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
