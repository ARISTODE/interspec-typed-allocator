#!/usr/bin/env python3
"""Regenerate the two coverage tables from analysis output (tracker item C2).

Input: one directory per benchmark, each holding the policy_summary.csv that
the interspec-artifact analysis writes (scripts/run_coverage_analysis.sh).
Output: both tables as CSV and Markdown, next to the paper's current numbers.

Column mapping. The artifact has no script that derives its paper tables from
raw reports, so the mapping was inferred by matching its processed tables
against its own raw summaries. It reproduces the paper for 7 of the 8
boundaries that have a raw summary, for these columns:

  interface fields      total_nodes
  SP1 fields            t_to_u_confidentiality_protected_nodes
  SP2 fields            t_to_u_integrity_protected_nodes
  pointer fields        total_pointer_slots
  SP3 fields            sp3_slots

The paper's split of pointer fields into "SP2", "not dereferenced by T", "SP3"
and "unknown" could not be matched to any column or pair of columns. This
script therefore reports the partition the analysis itself writes
(partition_sp2_only + partition_sp1_and_sp2, partition_sp1_only,
partition_sp3, partition_other) and does not claim it equals the paper's.
"""

import argparse
import csv
import json
from pathlib import Path

BOUNDARIES = {
    "ffmpeg_libvpx": "ffmpeg/libvpx", "magick_libpng": "magick/libpng",
    "memcached_bipbuffer": "memcached/bipbuffer", "memcached_hash": "memcached/hash",
    "nginx_libpcre": "nginx/libpcre", "nginx_openssl": "nginx/openssl",
    "rsync_popt": "rsync/popt", "ucl_libucl": "ucl/libucl",
    "yaml_libyaml": "yaml/libyaml", "zip_libzip": "zip/libzip",
}


def pct(part, whole):
    return round(100.0 * part / whole, 1) if whole else 0.0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", required=True, type=Path, nargs="+",
                        help="directories that contain <benchmark>/policy_summary.csv")
    parser.add_argument("--paper", required=True, type=Path,
                        help="interspec-artifact data/processed/paper directory")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    rows, sources = {}, {}
    for directory in args.reports:
        for summary in sorted(directory.glob("*/policy_summary.csv")):
            benchmark = summary.parent.name
            if benchmark not in BOUNDARIES:
                continue
            record = next(csv.DictReader(summary.open()))
            rows[benchmark] = {k: int(v) for k, v in record.items()
                               if k != "benchmark" and v.lstrip("-").isdigit()}
            sources[benchmark] = str(summary)

    paper1 = {r["boundary"]: r for r in csv.DictReader(
        (args.paper / "sp1_confidentiality_coverage.csv").open())}
    paper2 = {r["boundary"]: r for r in csv.DictReader(
        (args.paper / "integrity_coverage.csv").open())}

    sp1, integrity = [], []
    for benchmark, boundary in BOUNDARIES.items():
        if benchmark not in rows:
            continue
        r = rows[benchmark]
        fields = r["total_nodes"]
        sp1.append({"boundary": boundary, "interface_fields": fields,
                    "sp1_fields": r["t_to_u_confidentiality_protected_nodes"],
                    "coverage_pct": pct(r["t_to_u_confidentiality_protected_nodes"], fields),
                    "paper_interface_fields": int(paper1[boundary]["interface_fields"]),
                    "paper_sp1_fields": int(paper1[boundary]["sp1_fields"]),
                    "paper_coverage_pct": float(paper1[boundary]["coverage_pct"])})
        pointer_sp2 = r["partition_sp2_only_slots"] + r["partition_sp1_and_sp2_slots"]
        integrity.append({
            "boundary": boundary, "fields": fields,
            "sp2_fields": r["t_to_u_integrity_protected_nodes"],
            "sp2_pct": pct(r["t_to_u_integrity_protected_nodes"], fields),
            "pointer_fields": r["total_pointer_slots"],
            "pointer_sp2_slots": pointer_sp2,
            "pointer_sp1_only_slots": r["partition_sp1_only_slots"],
            "pointer_sp3_slots": r["partition_sp3_slots"],
            "pointer_other_slots": r["partition_other_slots"],
            "paper_fields": int(paper2[boundary]["fields"]),
            "paper_sp2_fields": int(paper2[boundary]["sp2_fields"]),
            "paper_pointer_fields": int(paper2[boundary]["pointer_fields"]),
            "paper_sp3_fields": int(paper2[boundary]["sp3_fields"])})

    for name, table in (("coverage_sp1.csv", sp1), ("coverage_integrity.csv", integrity)):
        if table:
            with (args.out / name).open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(table[0]))
                writer.writeheader()
                writer.writerows(table)

    lines = ["# Coverage tables regenerated from analysis output", "",
             f"Boundaries with output: {len(sp1)} of {len(BOUNDARIES)}. "
             "Missing: " + (", ".join(b for k, b in BOUNDARIES.items() if k not in rows) or "none") + ".",
             "", "## SP1 (confidentiality)", "",
             "| Boundary | Interface fields | SP1 fields | Coverage | Paper: fields | Paper: SP1 | Paper: coverage |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for r in sp1:
        lines.append(f"| {r['boundary']} | {r['interface_fields']} | {r['sp1_fields']} | "
                     f"{r['coverage_pct']}% | {r['paper_interface_fields']} | "
                     f"{r['paper_sp1_fields']} | {r['paper_coverage_pct']}% |")
    if sp1:
        total, covered = sum(r["interface_fields"] for r in sp1), sum(r["sp1_fields"] for r in sp1)
        lines.append(f"| Subtotal of these rows | {total} | {covered} | {pct(covered, total)}% | "
                     f"{sum(r['paper_interface_fields'] for r in sp1)} | "
                     f"{sum(r['paper_sp1_fields'] for r in sp1)} | |")
    lines += ["", "## SP2 and SP3 (integrity)", "",
              "| Boundary | Fields | SP2 fields | SP2 share | Pointer fields | Pointer: SP2 | "
              "Pointer: SP1 only | Pointer: SP3 | Pointer: other | Paper: SP2 | Paper: pointers | Paper: SP3 |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in integrity:
        lines.append(f"| {r['boundary']} | {r['fields']} | {r['sp2_fields']} | {r['sp2_pct']}% | "
                     f"{r['pointer_fields']} | {r['pointer_sp2_slots']} | "
                     f"{r['pointer_sp1_only_slots']} | {r['pointer_sp3_slots']} | "
                     f"{r['pointer_other_slots']} | {r['paper_sp2_fields']} | "
                     f"{r['paper_pointer_fields']} | {r['paper_sp3_fields']} |")
    (args.out / "COVERAGE_TABLES.md").write_text("\n".join(lines) + "\n")
    (args.out / "sources.json").write_text(json.dumps(sources, indent=2) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
