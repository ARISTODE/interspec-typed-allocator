#!/usr/bin/env python3

import argparse
import json
from pathlib import Path


def load_json(root, relpath):
    return json.loads((root / relpath).read_text())


def boundary_metrics(root, entry):
    result = {
        "name": entry["name"],
        "role": entry.get("role", "p7c"),
        "status": entry["status"],
        "pointer_shapes": entry.get("pointer_shapes", []),
    }
    if entry["status"] != "full":
        result["complete"] = False
        result["missing"] = ["full integration"]
        return result

    missing = []
    policy_path = entry.get("policy")
    if not policy_path or not (root / policy_path).is_file():
        missing.append("policy")
    boundary_path = entry.get("boundary_policy")
    if boundary_path and not (root / boundary_path).is_file():
        missing.append("boundary_policy")
    if not entry.get("source_revision"):
        missing.append("source_revision")

    if missing:
        result["complete"] = False
        result["missing"] = missing
        return result

    policy = load_json(root, policy_path)
    allocations = policy.get("allocations", [])
    precise = [a for a in allocations if "site" in a]
    uses = policy.get("uses", [])

    helpers = []
    if boundary_path:
        boundary = load_json(root, boundary_path)
        helpers = boundary.get("helper_sites", [])

    result.update({
        "complete": True,
        "allocation_sites": len(allocations) + len(helpers),
        "inferred_allocation_sites": len(allocations),
        "precise_source_allocation_sites": len(precise),
        "precise_source_fraction": (
            len(precise) / len(allocations) if allocations else 0.0
        ),
        "trusted_uses": len(uses),
        "helper_sites": len(helpers),
        "adversarial": entry.get("adversarial", []),
        "source_revision": entry["source_revision"],
    })
    return result


def build_report(root, manifest):
    entries = manifest["boundaries"]
    metrics = [boundary_metrics(root, entry) for entry in entries]
    p7c = [m for m in metrics if m["role"] == "p7c"]
    full_p7c = [m for m in p7c if m.get("complete")]
    shapes = sorted({shape for m in full_p7c for shape in m["pointer_shapes"]})
    required_shapes = sorted(manifest.get("required_pointer_shapes", []))
    missing_shapes = sorted(set(required_shapes) - set(shapes))
    required_count = manifest.get("required_new_boundaries", 0)

    complete = (
        len(full_p7c) >= required_count
        and not missing_shapes
        and all(m.get("complete") for m in p7c)
    )

    return {
        "schema_version": manifest.get("schema_version", 1),
        "complete": complete,
        "required_new_boundaries": required_count,
        "completed_new_boundaries": len(full_p7c),
        "required_pointer_shapes": required_shapes,
        "covered_pointer_shapes": shapes,
        "missing_pointer_shapes": missing_shapes,
        "boundaries": metrics,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest", default="integration/p7c_manifest.json",
        help="manifest path relative to repository root")
    parser.add_argument("--root", default=None)
    parser.add_argument("--output")
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[1]
    manifest = load_json(root, args.manifest)
    report = build_report(root, manifest)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text)
    else:
        print(text, end="")

    if args.require_complete and not report["complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
