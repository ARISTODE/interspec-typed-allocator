#!/usr/bin/env python3
"""Independently validate 18 source-injected U stack/global denial traces."""
import argparse
import hashlib
import json
from pathlib import Path

from summarize_pointer_census import parse_record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", required=True, type=Path)
    p.add_argument("--correctness-summary", required=True, type=Path)
    args = p.parse_args()

    summary = json.loads((args.results / "summary.json").read_text())
    gate = json.loads(args.correctness_summary.read_text())
    assert gate["passed"] == gate["total"] == 50
    assert summary["normal_correctness_gate"] == 50
    assert summary["binary_sha256"] == gate["binary_sha256"]["memcached-diagnostics"]
    assert summary["not_normal_prevalence"] is True
    expected = {(role, target, mode) for role in (1, 2, 3)
                for target in (1, 2, 3) for mode in (9, 10)}
    actual = {(row["role"], row["target"], row["fault_mode"]) for row in summary["cases"]}
    assert summary["total"] == summary["passed"] == len(summary["cases"]) == len(expected)
    assert actual == expected
    assert all(row["passed"] for row in summary["cases"])

    count = 0
    for row in summary["cases"]:
        role, target, mode = row["role"], row["target"], row["fault_mode"]
        kind = "u_static_global_untracked" if mode == 9 else "u_escaped_stack_untracked"
        name = f"u-origin-r{role}-t{target}-m{mode}"
        assert row["case"] == name and row["source_provenance"] == kind
        raw = (args.results / "logs" / f"{name}.stderr").read_bytes()
        assert hashlib.sha256(raw).hexdigest() == row["log_sha256"]
        assert row["server_exit_code"] == -6
        log = raw.decode(errors="replace")
        assert f"mode={mode} target={target} " in log
        assert "INTERSPEC_REJECT " in log and "reason=untracked" in log
        records = [parse_record(line, name, number, "memcached_bipbuffer")
                   for number, line in enumerate(log.splitlines(), 1)]
        rejected = [r for r in records if r is not None
                    and r["direction"] == "u_to_t"
                    and r["storage"] == "u_unclassified"
                    and r["result"] == "rejected_or_untracked"]
        assert rejected and len(rejected) == row["rejection_census_events"]
        assert all(r["site"] == {1: "request", 2: "peek_all", 3: "poll"}[target]
                   for r in rejected), (name, rejected)
        assert row["actual_runtime_result"] == "untracked"
        count += 1
    print("INTERSPEC_U_STORAGE_VERIFIED " + json.dumps({
        "passed": count, "expected": 18,
        "unique_roles": 3, "checked_return_targets": 3,
        "synthetic_u_storage_origins": 2,
        "normal_prevalence_measured": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
