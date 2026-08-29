#!/usr/bin/env python3

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.render_p8_results import render


def main():
    deterministic = {
        "security": {"passed": 25, "case_count": 25},
        "automation": {
            "boundary_count": 4,
            "inferred_allocation_sites": 3,
            "integration_helper_sites": 4,
            "adversarial_helper_sites_excluded_from_automation": 2,
            "source_derived_fraction_of_integration_allocation_policy": 3 / 7,
        },
    }
    automation = [{
        "boundary": "sample", "inferred_allocation_sites": "1",
        "integration_helper_sites": "1", "trusted_uses": "1",
        "pointer_shapes": "interior_u_object;buffer_with_extent",
    }]
    boundary = [{
        "boundary": "sample", "baseline_median_ns": "10",
        "extended_median_ns": "12", "paired_overhead_median_pct": "20",
    }]
    app = [{
        "workload": "dry_run", "baseline_median_ms": "1.0",
        "extended_median_ms": "1.1", "paired_overhead_median_pct": "10",
    }]
    text = render(deterministic, automation, boundary, app,
                  "deadbeef", "cpu=test\nkernel=test")
    assert "25/25" in text
    assert "42.9%" in text
    assert "sample | 1 | 1 | 1 | interior_u_object, buffer_with_extent" in text
    assert "12.00" in text
    assert "10.0%" in text
    assert "incremental validation overhead" in text
    assert "not total overhead over plain RLBox" in text
    print("P8 result renderer tests: ok")


if __name__ == "__main__":
    main()
