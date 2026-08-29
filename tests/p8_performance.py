#!/usr/bin/env python3

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.summarize_p8_performance import summarize


def main():
    samples = [
        {"boundary": "a", "mode": "tracked_no_check", "repetition": 0,
         "iterations": 100, "total_ns": 1000, "ns_per_op": 10.0},
        {"boundary": "a", "mode": "extended_sp3", "repetition": 0,
         "iterations": 100, "total_ns": 1200, "ns_per_op": 12.0},
        {"boundary": "a", "mode": "extended_sp3", "repetition": 1,
         "iterations": 100, "total_ns": 1100, "ns_per_op": 11.0},
        {"boundary": "a", "mode": "tracked_no_check", "repetition": 1,
         "iterations": 100, "total_ns": 1000, "ns_per_op": 10.0},
    ]
    rows = summarize(samples)
    assert len(rows) == 1
    row = rows[0]
    assert row["boundary"] == "a"
    assert row["repetitions"] == 2
    assert row["baseline_median_ns"] == 10.0
    assert row["extended_median_ns"] == 11.5
    assert abs(row["paired_overhead_median_pct"] - 15.0) < 1e-12

    bad = samples[:-1]
    try:
        summarize(bad)
        raise AssertionError("incomplete pair should fail")
    except ValueError as error:
        assert "incomplete repetition" in str(error)

    print("P8 performance summary tests: ok")


if __name__ == "__main__":
    main()
