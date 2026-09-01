#!/usr/bin/env python3

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.render_p9a_results import render


def main():
    rows = [{
        "workload": "sample",
        "rlbox_median_ms": "1.000",
        "tracked_median_ms": "1.100",
        "extended_median_ms": "1.210",
        "tracking_overhead_median_pct": "10",
        "validation_overhead_median_pct": "10",
        "total_overhead_median_pct": "21",
    }]
    text = render(rows, "deadbeef", "cpu=test\nkernel=test")
    assert "RLBox only median" in text
    assert "1.000 | 1.100 | 1.210" in text
    assert "10.0% | 10.0% | 21.0%" in text
    assert "dormant InterSpec support code" in text
    assert "P9b" in text
    print("P9a result renderer tests: ok")


if __name__ == "__main__":
    main()
