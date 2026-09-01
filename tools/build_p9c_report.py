#!/usr/bin/env python3

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

CASE_FIELDS = [
    "paper_case_id",
    "boundary",
    "paper_case_ordinal",
    "identity_status",
    "capability_status",
    "prototype_status",
    "source_basis",
    "notes",
]

ALLOWED_CAPABILITY = {"eligible", "ineligible", "insufficient_source_metadata"}
ALLOWED_PROTOTYPE = {"demonstrated", "not_demonstrated", "unresolved_mapping"}


def slug(value):
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def read_coverage(path):
    with path.open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    if not rows:
        raise ValueError("paper coverage CSV contains no rows")
    required = {
        "boundary",
        "sp3_fields",
        "unknown_fields",
        "pointer_fields",
        "pointer_covered_fields",
    }
    if not required.issubset(rows[0]):
        raise ValueError("paper coverage CSV is missing required columns")
    return rows


def build(root, coverage_path, manifest_path, audit_path=None):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path else None
    coverage = read_coverage(coverage_path)

    manifest_counts = {
        row["boundary"]: int(row["sp3_fields"])
        for row in manifest["boundaries"]
    }
    coverage_counts = {
        row["boundary"]: int(row["sp3_fields"])
        for row in coverage
    }

    expected_total = int(manifest["expected_sp3_total"])
    failures = []
    if manifest_counts != coverage_counts:
        failures.append("boundary SP3 counts differ from the pinned paper table")
    if sum(coverage_counts.values()) != expected_total:
        failures.append(
            f"paper SP3 total is {sum(coverage_counts.values())}, expected {expected_total}"
        )
    if len(coverage_counts) != len(manifest_counts):
        failures.append("paper boundary set differs from the P9c manifest")

    boundary_meta = {row["boundary"]: row for row in manifest["boundaries"]}
    evidence_boundaries = {
        row["boundary"]: row for row in manifest.get("prototype_boundary_evidence", [])
    }

    cases = []
    for boundary, count in coverage_counts.items():
        meta = boundary_meta[boundary]
        for ordinal in range(1, count + 1):
            case_id = f"{slug(boundary)}_sp3_{ordinal:02d}"
            cases.append(
                {
                    "paper_case_id": case_id,
                    "boundary": boundary,
                    "paper_case_ordinal": ordinal,
                    "identity_status": "aggregate_only",
                    "capability_status": "insufficient_source_metadata",
                    "prototype_status": (
                        "unresolved_mapping"
                        if boundary in evidence_boundaries
                        else "not_demonstrated"
                    ),
                    "source_basis": (
                        f"{manifest['source']['processed_table']}@"
                        f"{manifest['source']['commit']};{meta['raw_case_path']}"
                    ),
                    "notes": (
                        "Stable identifier for one field-count unit from the paper table. "
                        "The packaged aggregate table does not preserve the exact field identity."
                    ),
                }
            )

    by_id = {case["paper_case_id"]: case for case in cases}
    unknown_overrides = []
    for override in manifest.get("case_overrides", []):
        case_id = override["paper_case_id"]
        if case_id not in by_id:
            unknown_overrides.append(case_id)
            continue
        case = by_id[case_id]
        for key in (
            "identity_status",
            "capability_status",
            "prototype_status",
            "source_basis",
            "notes",
        ):
            if key in override:
                case[key] = override[key]

    if unknown_overrides:
        failures.append("unknown case overrides: " + ",".join(sorted(unknown_overrides)))

    ids = [case["paper_case_id"] for case in cases]
    if len(ids) != len(set(ids)):
        failures.append("duplicate paper case identifiers")

    invalid_capability = [
        case["paper_case_id"]
        for case in cases
        if case["capability_status"] not in ALLOWED_CAPABILITY
    ]
    invalid_prototype = [
        case["paper_case_id"]
        for case in cases
        if case["prototype_status"] not in ALLOWED_PROTOTYPE
    ]
    if invalid_capability:
        failures.append("invalid capability status: " + ",".join(invalid_capability))
    if invalid_prototype:
        failures.append("invalid prototype status: " + ",".join(invalid_prototype))

    explicit_classification = not failures and len(cases) == expected_total
    capability_counts = Counter(case["capability_status"] for case in cases)
    prototype_counts = Counter(case["prototype_status"] for case in cases)
    identity_counts = Counter(case["identity_status"] for case in cases)

    resolved = capability_counts["eligible"] + capability_counts["ineligible"]
    capability_resolution_complete = explicit_classification and resolved == expected_total
    source_fidelity_complete = (
        explicit_classification
        and identity_counts["aggregate_only"] == 0
        and all(
            case["identity_status"] not in {"unknown", "aggregate_only"}
            for case in cases
        )
    )

    audit_complete = False
    source_limit = False
    coverage_claim = {
        "paper_denominator": expected_total,
        "exact_case_level_percentage_supported": source_fidelity_complete,
        "exact_eligible_lower_bound": capability_counts["eligible"],
        "exact_demonstrated_lower_bound": prototype_counts["demonstrated"],
    }
    if audit is not None:
        conclusion = audit.get("conclusion", {})
        source_limit = (
            conclusion.get("status") == "source_fidelity_limitation"
            and conclusion.get("exact_field_identity_map_recoverable_from_preserved_artifact") is False
            and conclusion.get("exact_case_level_percentage_supported") is False
            and int(conclusion.get("paper_denominator", -1)) == expected_total
        )
        audit_complete = source_limit and bool(audit.get("checks"))
        if source_limit:
            coverage_claim = {
                "paper_denominator": expected_total,
                "exact_case_level_percentage_supported": False,
                "exact_eligible_lower_bound": int(conclusion.get("exact_eligible_lower_bound", 0)),
                "exact_demonstrated_lower_bound": int(conclusion.get("exact_demonstrated_lower_bound", 0)),
                "interpretation": conclusion.get("interpretation", ""),
            }

    p9c_evaluation_complete = (
        explicit_classification
        and not failures
        and (capability_resolution_complete or audit_complete)
    )

    paper_rows = []
    for row in coverage:
        meta = boundary_meta[row["boundary"]]
        paper_rows.append(
            {
                "boundary": row["boundary"],
                "sp3_fields": int(row["sp3_fields"]),
                "unknown_fields": int(row["unknown_fields"]),
                "raw_case_path": meta["raw_case_path"],
                "raw_alignment": meta["raw_alignment"],
                "raw_alignment_note": meta["raw_alignment_note"],
            }
        )

    return {
        "schema_version": 2,
        "paper_source_integrity": not failures,
        "classification_explicit": explicit_classification,
        "capability_resolution_complete": capability_resolution_complete,
        "source_fidelity_complete": source_fidelity_complete,
        "source_reconstruction_audit_complete": audit_complete,
        "source_fidelity_limit_acknowledged": source_limit,
        "p9c_evaluation_complete": p9c_evaluation_complete,
        "paper": {
            "source": manifest["source"],
            "boundary_count": len(coverage_counts),
            "sp3_case_count": len(cases),
            "expected_sp3_case_count": expected_total,
            "boundaries": paper_rows,
        },
        "classification": {
            "eligible": capability_counts["eligible"],
            "ineligible": capability_counts["ineligible"],
            "insufficient_source_metadata": capability_counts[
                "insufficient_source_metadata"
            ],
            "resolved": resolved,
        },
        "prototype": {
            "demonstrated_exact_paper_cases": prototype_counts["demonstrated"],
            "not_demonstrated": prototype_counts["not_demonstrated"],
            "unresolved_mapping": prototype_counts["unresolved_mapping"],
            "boundary_evidence": manifest.get("prototype_boundary_evidence", []),
        },
        "coverage_claim": coverage_claim,
        "source_reconstruction_audit": audit,
        "completion_failures": failures,
        "cases": cases,
    }


def write_cases(path, cases):
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=CASE_FIELDS)
        writer.writeheader()
        for case in cases:
            writer.writerow({key: case[key] for key in CASE_FIELDS})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--coverage",
        default="evaluation/p9c/interspec_paper_integrity_coverage.csv",
    )
    parser.add_argument(
        "--manifest",
        default="evaluation/p9c/paper_sp3_manifest.json",
    )
    parser.add_argument(
        "--audit",
        default="evaluation/p9c/source_reconstruction_audit.json",
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--require-source-integrity", action="store_true")
    parser.add_argument("--require-resolved", action="store_true")
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()

    coverage = (ROOT / args.coverage).resolve()
    manifest = (ROOT / args.manifest).resolve()
    audit = (ROOT / args.audit).resolve() if args.audit else None
    out = Path(args.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    report = build(ROOT, coverage, manifest, audit)
    (out / "p9c-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_cases(out / "p9c-cases.csv", report["cases"])

    if args.require_source_integrity and not (
        report["paper_source_integrity"] and report["classification_explicit"]
    ):
        raise SystemExit(1)
    if args.require_resolved and not report["capability_resolution_complete"]:
        raise SystemExit(1)
    if args.require_complete and not report["p9c_evaluation_complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
