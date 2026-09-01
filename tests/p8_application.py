#!/usr/bin/env python3

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.summarize_p8_application import summarize


def main():
    samples = [
        {"workload": "w", "mode": "tracked_no_check", "repetition": 0,
         "total_ns": 10_000_000},
        {"workload": "w", "mode": "extended_sp3", "repetition": 0,
         "total_ns": 11_000_000},
        {"workload": "w", "mode": "extended_sp3", "repetition": 1,
         "total_ns": 12_000_000},
        {"workload": "w", "mode": "tracked_no_check", "repetition": 1,
         "total_ns": 10_000_000},
    ]
    rows = summarize(samples)
    assert len(rows) == 1
    row = rows[0]
    assert row["workload"] == "w"
    assert row["repetitions"] == 2
    assert row["baseline_median_ms"] == 10.0
    assert row["extended_median_ms"] == 11.5
    assert abs(row["paired_overhead_median_pct"] - 15.0) < 1e-12

    try:
        summarize(samples[:-1])
        raise AssertionError("incomplete application pair should fail")
    except ValueError as error:
        assert "incomplete application pair" in str(error)

    print("P8 application summary tests: ok")


if __name__ == "__main__":
    main()
