#!/usr/bin/env python3
"""Negative SP3 probes for U static and stack storage; not prevalence data."""
import argparse
import hashlib
import json
from pathlib import Path
import traceback

from memcached_common import Server
from test_memcached_deployment import fault_case

KINDS = {
    9: "u_static_global_untracked",
    10: "u_escaped_stack_untracked",
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work", type=Path, default=Path("/tmp/interspec-memcached-deployment"))
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--correctness-summary", type=Path, required=True)
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    gate = json.loads(args.correctness_summary.read_text())
    assert gate["passed"] == gate["total"] == 50, "normal regression gate must pass first"
    binary = args.work / "bin/memcached-diagnostics"
    binary_sha = hashlib.sha256(binary.read_bytes()).hexdigest()
    assert binary_sha == gate["binary_sha256"][binary.name], "binary differs from correctness gate"

    cases = []
    for role in (1, 2, 3):
        for target in (1, 2, 3):
            for mode, origin in KINDS.items():
                name = f"u-origin-r{role}-t{target}-m{mode}"
                try:
                    with Server(binary, args.out / "logs", name, trace=True, census=True,
                                fault={"role": role, "target": target, "fault": mode}) as server:
                        fault_case(server, mode, role)
                    raw = server.logpath.read_bytes()
                    log = raw.decode(errors="replace")
                    assert f"mode={mode} target={target} " in log, "U mutation did not fire"
                    assert "INTERSPEC_REJECT " in log and "reason=untracked" in log, "SP3 did not reject U origin"
                    rejection = [s for s in log.splitlines()
                                 if s.startswith("INTERSPEC_POINTER_CENSUS ")
                                 and "boundary=memcached_bipbuffer " in s
                                 and "direction=u_to_t " in s
                                 and "storage=u_unclassified " in s
                                 and "result=rejected_or_untracked" in s]
                    assert rejection, "no census record for rejected U pointer"
                    row = {"case": name, "passed": True, "role": role, "target": target,
                           "fault_mode": mode, "source_provenance": origin,
                           "actual_runtime_result": "untracked",
                           "rejection_census_events": len(rejection),
                           "server_exit_code": server.proc.returncode,
                           "log_sha256": hashlib.sha256(raw).hexdigest()}
                except Exception:
                    row = {"case": name, "passed": False, "role": role, "target": target,
                           "fault_mode": mode, "source_provenance": origin,
                           "error": traceback.format_exc()}
                cases.append(row)
                print("INTERSPEC_U_STORAGE_PROBE " + json.dumps(row, sort_keys=True), flush=True)
                (args.out / "summary.json").write_text(json.dumps({
                    "schema": 1, "scope": "adversarial fault-only U origins at checked returns",
                    "not_normal_prevalence": True,
                    "normal_correctness_gate": 50, "binary_sha256": binary_sha,
                    "passed": sum(r["passed"] for r in cases), "total": len(cases),
                    "cases": cases,
                }, indent=2, sort_keys=True) + "\n")
    if not all(row["passed"] for row in cases):
        raise SystemExit("U storage pointer probes failed; raw logs and summary retained")


if __name__ == "__main__":
    main()
