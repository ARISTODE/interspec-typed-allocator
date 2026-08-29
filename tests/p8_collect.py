#!/usr/bin/env python3

import csv
import json
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.p8_aggregate_runtime import aggregate
from tools.p8_collect import (
    collect_automation,
    collect_boundary_security,
    collect_rlbox_overhead,
    collect_runtime_overhead,
    collect_runtime_security,
)


def runtime_rows():
    rows = []
    for population in (1, 16, 256, 4096, 16384):
        for metric, ns in (
            ("domain_only_live", 10), ("check_live", 30),
            ("domain_only_interior", 12), ("check_interior", 36),
            ("domain_only_remaining", 8), ("remaining_bytes", 40),
        ):
            operations = 100
            rows.append({"metric": metric, "population": str(population), "threads": "1",
                         "operations": str(operations), "total_ns": str(ns * operations),
                         "ns_per_op": str(ns), "ops_per_sec": "1"})
    return rows


def rlbox_rows():
    rows = []
    for population in (1, 16, 256, 4096, 16384):
        for metric, ns in (("rlbox_domain_range", 4.0), ("extended_sp3", 20.0)):
            rows.append({"metric": metric, "population": str(population),
                         "operations": "100", "samples": "5",
                         "median_ns_per_op": str(ns),
                         "min_ns_per_op": str(ns - 1.0),
                         "max_ns_per_op": str(ns + 1.0)})
    return rows


def write_runtime(path, ns):
    fields = ["metric", "population", "threads", "operations",
              "total_ns", "ns_per_op", "ops_per_sec"]
    with Path(path).open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow({"metric": "check_live", "population": 4096, "threads": 1,
                         "operations": 100, "total_ns": ns * 100,
                         "ns_per_op": ns, "ops_per_sec": int(1e9 / ns)})


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

    security = [{"case": case, "expected": "x", "actual": "x", "result": "pass"}
                for case in p8["required_runtime_security_cases"]]
    assert len(collect_runtime_security(security, p8["required_runtime_security_cases"])) == 7
    bad = list(security)
    bad[0] = dict(bad[0], result="fail")
    try:
        collect_runtime_security(bad, p8["required_runtime_security_cases"])
        raise AssertionError("failed security row must reject P8 collection")
    except ValueError as error:
        assert "runtime security case failed" in str(error)

    evidence = [{"boundary": boundary, "case": case, "result": "pass"}
                for boundary, cases in p8["boundary_security_requirements"].items()
                for case in cases]
    boundary_rows = collect_boundary_security(
        p7c, p8["boundary_security_requirements"], evidence, True)
    assert len(boundary_rows) == 11
    assert all(row["evidence"] == "rlbox_nacl_regression" for row in boundary_rows)

    runtime = collect_runtime_overhead(
        runtime_rows(), p8["runtime_pairs"], p8["required_runtime_populations"])
    assert len(runtime) == 15
    live = next(row for row in runtime
                if row["comparison"] == "live_base_pointer" and row["population"] == 4096)
    assert float(live["additional_ns_per_op"]) == 20.0
    assert float(live["extended_over_baseline"]) == 3.0

    backend = collect_rlbox_overhead(
        rlbox_rows(), p8["rlbox_backend_pair"], p8["required_runtime_populations"])
    assert len(backend) == 5
    assert all(float(row["baseline_ns_per_op"]) == 4.0 for row in backend)
    assert all(float(row["extended_ns_per_op"]) == 20.0 for row in backend)
    assert all(float(row["additional_ns_per_op"]) == 16.0 for row in backend)
    assert all(float(row["extended_over_baseline"]) == 5.0 for row in backend)
    assert all(row["samples"] == 5 for row in backend)

    incomplete = rlbox_rows()[:-1]
    try:
        collect_rlbox_overhead(incomplete, p8["rlbox_backend_pair"],
                               p8["required_runtime_populations"])
        raise AssertionError("missing RLBox matched pair must fail")
    except ValueError as error:
        assert "missing matched RLBox runtime pair" in str(error)

    missing = [row for row in runtime_rows()
               if not (row["metric"] == "check_live" and row["population"] == "4096")]
    try:
        collect_runtime_overhead(missing, p8["runtime_pairs"], p8["required_runtime_populations"])
        raise AssertionError("missing paired measurement must reject P8 collection")
    except ValueError as error:
        assert "missing Extended-SP3 runtime row" in str(error)

    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)
        paths = []
        for index, ns in enumerate((50, 30, 40), start=1):
            path = temp / f"run-{index}.csv"
            write_runtime(path, ns)
            paths.append(path)
        aggregated = aggregate(paths)
        assert len(aggregated) == 1
        assert float(aggregated[0]["ns_per_op"]) == 40.0
        assert float(aggregated[0]["min_ns_per_op"]) == 30.0
        assert float(aggregated[0]["max_ns_per_op"]) == 50.0
        assert aggregated[0]["samples"] == 3

    print("P8 collection tests: ok")


if __name__ == "__main__":
    main()
