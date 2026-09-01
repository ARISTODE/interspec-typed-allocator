#!/usr/bin/env python3

import csv
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_p8_report import build


def write_security(path, rows):
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(
            output, fieldnames=["case", "expected", "actual", "result"])
        writer.writeheader()
        writer.writerows(rows)


def test_repository_p8_report():
    with tempfile.TemporaryDirectory() as temp:
        security = Path(temp) / "security.csv"
        write_security(security, [
            {"case": "a", "expected": "ok", "actual": "ok", "result": "pass"},
            {"case": "b", "expected": "wrong_type", "actual": "wrong_type", "result": "pass"},
        ])
        report = build(ROOT, security, ROOT / "integration/p7c_manifest.json")
        assert report["deterministic_complete"]
        assert report["security"]["case_count"] == 2
        assert report["automation"]["boundary_count"] == 4
        assert report["automation"]["inferred_allocation_sites"] == 3
        assert report["automation"]["precise_source_allocation_sites"] == 3
        assert report["automation"]["integration_helper_sites"] == 4
        assert report["automation"]["adversarial_helper_sites_excluded_from_automation"] == 2
        assert report["automation"]["trusted_uses"] == 4
        assert abs(
            report["automation"]["source_derived_fraction_of_integration_allocation_policy"]
            - 3 / 7
        ) < 1e-12


def test_security_failure_prevents_completion():
    with tempfile.TemporaryDirectory() as temp:
        security = Path(temp) / "security.csv"
        write_security(security, [
            {"case": "bad", "expected": "ok", "actual": "untracked", "result": "fail"},
        ])
        report = build(ROOT, security, ROOT / "integration/p7c_manifest.json")
        assert not report["deterministic_complete"]
        assert report["security"]["failed_cases"] == ["bad"]


if __name__ == "__main__":
    test_repository_p8_report()
    test_security_failure_prevents_completion()
    print("P8 deterministic report tests: ok")
