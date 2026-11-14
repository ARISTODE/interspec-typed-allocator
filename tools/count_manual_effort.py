#!/usr/bin/env python3
"""Count the manual effort per registry boundary from this repository (tracker C4).

For each boundary the counts and the exact source locations behind them are
written, so every number can be checked by opening the listed lines.

Definitions used here:
  boundary specification   boundary.json: the hand-written declaration of helper
                           allocation sites (non-blank lines). policy.json is
                           listed separately: it is a checked-in snapshot of
                           CodeQL-inferred policy, not written by hand.
  manual type entries      helper sites in boundary.json. Each names its type by
                           hand. Sites with role "adversarial" exist only for
                           tests and are counted separately.
  registration calls in T  call sites in the trusted bridge that register a
                           type, a type layout or an object by hand
                           (register_type, register_type_layout,
                           register_external_*), and their unregister calls.
                           Calls into generated code (register_types,
                           register_wasm_allocation_policy,
                           register_allocation_policy) are counted separately.
"""

import argparse
import json
import re
import subprocess
from pathlib import Path

BOUNDARIES = {
    "rsync/popt": {"spec": "integration/rsync_popt",
                   "trusted": ["integration/rsync_popt/p4c_bridge.cpp"]},
    "memcached/bipbuffer": {"spec": "integration/memcached_bipbuffer",
                            "trusted": ["integration/memcached_server/bridge.cpp"]},
    "yaml/libyaml": {"spec": "integration/yaml_libyaml",
                     "trusted": ["integration/yaml_libyaml/yaml_app_bench.cpp"]},
    "nginx/libpcre": {"spec": "integration/nginx_server",
                      "trusted": ["integration/nginx_server/bridge.cpp"]},
}
MANUAL = re.compile(r"\b(register_type|register_type_layout|register_external_\w+)\s*\(")
UNREGISTER = re.compile(r"\b(unregister_external\w*)\s*\(")
GENERATED = re.compile(r"\b(register_types|register_wasm_allocation_policy|"
                       r"register_allocation_policy)\s*\(")


def nonblank(path):
    return sum(1 for line in path.read_text().splitlines() if line.strip())


def sites(root, files, pattern):
    found = []
    for name in files:
        for number, line in enumerate((root / name).read_text().splitlines(), 1):
            code = line.split("//")[0]
            for match in pattern.finditer(code):
                found.append(f"{name}:{number} {match.group(1)}")
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    args.out.mkdir(parents=True, exist_ok=True)
    commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"],
                                     text=True).strip()
    rows = {}
    for name, spec in BOUNDARIES.items():
        directory = root / spec["spec"]
        boundary = json.loads((directory / "boundary.json").read_text())
        policy = json.loads((directory / "policy.json").read_text())
        helper = boundary.get("helper_sites", [])
        manual = sites(root, spec["trusted"], MANUAL)
        rows[name] = {
            "boundary_json": f"{spec['spec']}/boundary.json",
            "boundary_specification_lines": nonblank(directory / "boundary.json"),
            "inferred_policy_json_lines": nonblank(directory / "policy.json"),
            "inferred_policy_entries": {k: len(v) for k, v in policy.items()},
            "manual_type_entries": [s for s in helper if s.get("role") != "adversarial"],
            "test_only_type_entries": [s for s in helper if s.get("role") == "adversarial"],
            "trusted_files": spec["trusted"],
            "manual_registration_calls": manual,
            "manual_unregistration_calls": sites(root, spec["trusted"], UNREGISTER),
            "generated_registration_calls": sites(root, spec["trusted"], GENERATED),
        }
    (args.out / "manual_effort.json").write_text(
        json.dumps({"commit": commit, "boundaries": rows}, indent=2) + "\n")
    lines = [f"Counted at `{commit[:7]}` by `tools/count_manual_effort.py`.", "",
             "| Boundary | Boundary specification (lines of `boundary.json`) | "
             "Manual type entries | Test-only type entries | "
             "Manual registration calls in T | Unregister calls in T | "
             "Calls into generated registration | Inferred `policy.json` (lines) |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name, row in rows.items():
        lines.append(
            f"| {name} | {row['boundary_specification_lines']} | "
            f"{len(row['manual_type_entries'])} | {len(row['test_only_type_entries'])} | "
            f"{len(row['manual_registration_calls'])} | "
            f"{len(row['manual_unregistration_calls'])} | "
            f"{len(row['generated_registration_calls'])} | "
            f"{row['inferred_policy_json_lines']} |")
    (args.out / "MANUAL_EFFORT.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
