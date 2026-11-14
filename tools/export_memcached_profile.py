#!/usr/bin/env python3
"""Export derived rates only after independently replaying a frozen profile."""
import argparse
import json
from pathlib import Path
from verify_memcached_profile import load_json, verify_frozen


def export(profile, plan_path):
    verified = verify_frozen(profile, plan_path)
    plan = load_json(plan_path)
    result = []
    for row, scenario in zip(verified["rows"], plan["scenarios"]):
        operations = row["operations"]
        result.append({**row, "profile_keys": scenario["profile_keys"],
                       "workload_mode": plan["workload_mode"], "workload_seed": plan["workload_seed"],
                       "measurement_mode": plan["measurement_mode"], "coverage_valid": True,
                       "checks_per_operation": row["runtime_checks"] / operations,
                       "checks_per_1000_operations": row["runtime_checks"] * 1000 / operations,
                       **{field + "_per_operation": row[field] / operations for field in
                          ("sandbox_calls", "bytes_into_u", "bytes_from_u")},
                       "plan_sha256": verified["plan_sha256"], "profile_schema": plan["schema"],
                       "timing_evidence": False, "latency_evidence": False})
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Keep derived output outside the immutable raw directory.
    if args.output.resolve().is_relative_to(args.profile.resolve()):
        raise SystemExit("export must be outside the raw profile directory")
    rows = export(args.profile, args.plan)
    with args.output.open("x") as stream:
        json.dump(rows, stream, indent=2); stream.write("\n")
