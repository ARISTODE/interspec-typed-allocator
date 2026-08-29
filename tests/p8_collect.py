#!/usr/bin/env python3

import csv
import json
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.p8_collect import (
    collect_automation,
    collect_boundary_security,
    collect_runtime_overhead,
    collect_runtime_security,
)


def runtime_rows():
    rows = []
    for population in (1, 16, 256, 4096, 16384):
        for metric, ns in (
            ("domain_only_live", 10),
            ("check_live", 30),
            ("domain_only_interior", 12),
            ("check_interior", 36),
            ("domain_only_remaining", 8),
            ("remaining_bytes", 40),
        ):
            operations = 100
            rows.append({
                "metric": metric,
                "population": str(population),
                "threads": "1",
                "operations": str(operations),
                "total_ns": str(ns * operations),
                "ns_per_op": str(ns),
                "ops_per_sec": "1",
            })
    return rows


def main():
    p8 = json.loads((ROOT / "evaluation/p8_manifest.json").read_text())
    p7c = json.loads((ROOT / p8["p7c_manifest"]).read_text())

    automation, totals = collect_automation(ROOT, p7c)
    assert len(automation) == 4
    assert totals["source_allocation_sites"] == 3
    assert totals["precise_source_allocation_sites"] == 3
    assert totals["integration_helper_sites"] == 3
    assert totals["adversarial_helper_sites"] == 3
    assert totals["production_allocation_sites"] == 6
    assert totals["source_allocation_fraction"] == 0.5
    assert totals["trusted_use_policies"] == 4
    assert totals["real_application_use_policies"] == 1
    assert totals["analysis_adapter_use_policies"] == 3

    security = [
        {"case": case, "expected": "x", "actual": "x", "result": "pass"}
        for case in p8["required_runtime_security_cases"]
    ]
    selected = collect_runtime_security(security, p8["required_runtime_security_cases"])
    assert len(selected) == 7
    bad = list(security)
    bad[0] = dict(bad[0], result="fail")
    try:
        collect_runtime_security(bad, p8["required_runtime_security_cases"])
        raise AssertionError("failed security row must reject P8 collection")
    except ValueError as error:
        assert "runtime security case failed" in str(error)

    evidence = []
    for boundary, cases in p8["boundary_security_requirements"].items():
        for case in cases:
            evidence.append({"boundary": boundary, "case": case, "result": "pass"})
    boundary_rows = collect_boundary_security(
        p7c, p8["boundary_security_requirements"], evidence, True)
    assert len(boundary_rows) == 11
    assert all(row["evidence"] == "rlbox_nacl_regression" for row in boundary_rows)

    runtime = collect_runtime_overhead(
        runtime_rows(), p8["runtime_pairs"], p8["required_runtime_populations"])
    assert len(runtime) == 15
    live = next(row for row in runtime
                if row["comparison"] == "live_base_pointer" and row["population"] == 4096)
    assert float(live["baseline_ns_per_op"]) == 10.0
    assert float(live["extended_ns_per_op"]) == 30.0
    assert float(live["additional_ns_per_op"]) == 20.0
    assert float(live["extended_over_baseline"]) == 3.0

    missing = runtime_rows()
    missing = [row for row in missing
               if not (row["metric"] == "check_live" and row["population"] == "4096")]
    try:
        collect_runtime_overhead(missing, p8["runtime_pairs"], p8["required_runtime_populations"])
        raise AssertionError("missing paired measurement must reject P8 collection")
    except ValueError as error:
        assert "missing Extended-SP3 runtime row" in str(error)

    print("P8 collection tests: ok")


if __name__ == "__main__":
    main()
