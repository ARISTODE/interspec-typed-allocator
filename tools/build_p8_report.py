#!/usr/bin/env python3

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.p7c_report import build_report


def load_security_csv(path):
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source))
    if not rows:
        raise ValueError("security CSV contains no cases")
    required = {"case", "expected", "actual", "result"}
    if set(rows[0]) != required:
        raise ValueError("unexpected security CSV schema")
    return rows


def write_automation_csv(path, boundaries):
    fields = [
        "boundary",
        "role",
        "status",
        "source_revision",
        "inferred_allocation_sites",
        "precise_source_allocation_sites",
        "helper_sites",
        "trusted_uses",
        "pointer_shapes",
        "adversarial",
    ]
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for boundary in boundaries:
            writer.writerow({
                "boundary": boundary["name"],
                "role": boundary["role"],
                "status": boundary["status"],
                "source_revision": boundary.get("source_revision", ""),
                "inferred_allocation_sites": boundary.get("inferred_allocation_sites", 0),
                "precise_source_allocation_sites": boundary.get(
                    "precise_source_allocation_sites", 0),
                "helper_sites": boundary.get("helper_sites", 0),
                "trusted_uses": boundary.get("trusted_uses", 0),
                "pointer_shapes": ";".join(boundary.get("pointer_shapes", [])),
                "adversarial": ";".join(boundary.get("adversarial", [])),
            })


def build(root, security_csv, manifest_path):
    security = load_security_csv(security_csv)
    failed = [row["case"] for row in security if row["result"] != "pass"]
    manifest = json.loads(manifest_path.read_text())
    generalization = build_report(root, manifest)

    boundaries = generalization["boundaries"]
    real_boundaries = [b for b in boundaries if b["role"] in {"baseline", "p7c"}]
    missing_revision = [b["name"] for b in real_boundaries if not b.get("source_revision")]
    no_uses = [b["name"] for b in real_boundaries if b.get("trusted_uses", 0) < 1]
    no_adversarial = [b["name"] for b in real_boundaries if not b.get("adversarial")]

    deterministic_complete = (
        not failed
        and generalization["complete"]
        and not missing_revision
        and not no_uses
        and not no_adversarial
    )

    inferred = sum(b.get("inferred_allocation_sites", 0) for b in real_boundaries)
    precise = sum(b.get("precise_source_allocation_sites", 0) for b in real_boundaries)
    helpers = sum(b.get("helper_sites", 0) for b in real_boundaries)
    uses = sum(b.get("trusted_uses", 0) for b in real_boundaries)

    return {
        "schema_version": 1,
        "deterministic_complete": deterministic_complete,
        "security": {
            "case_count": len(security),
            "passed": len(security) - len(failed),
            "failed_cases": failed,
        },
        "generalization": generalization,
        "automation": {
            "boundary_count": len(real_boundaries),
            "inferred_allocation_sites": inferred,
            "precise_source_allocation_sites": precise,
            "helper_sites": helpers,
            "trusted_uses": uses,
            "source_derived_fraction_of_allocation_policy": (
                inferred / (inferred + helpers) if inferred + helpers else 0.0
            ),
        },
        "completion_failures": {
            "missing_source_revision": missing_revision,
            "boundaries_without_trusted_uses": no_uses,
            "boundaries_without_adversarial_metadata": no_adversarial,
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=None)
    parser.add_argument("--security-csv", required=True)
    parser.add_argument("--manifest", default="integration/p7c_manifest.json")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root else ROOT
    security_csv = Path(args.security_csv).resolve()
    manifest_path = (root / args.manifest).resolve()
    out = Path(args.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    report = build(root, security_csv, manifest_path)
    (out / "p8-deterministic.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n")
    write_automation_csv(out / "p8-automation.csv", report["generalization"]["boundaries"])

    if args.require_complete and not report["deterministic_complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
