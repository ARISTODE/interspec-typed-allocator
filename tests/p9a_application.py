#!/usr/bin/env python3

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.summarize_p9a_application import summarize


def main():
    samples = []
    for repetition, scale in ((0, 1), (1, 2), (2, 3)):
        for mode, base in (
            ("rlbox_only", 100),
            ("tracked_no_check", 110),
            ("extended_sp3", 121),
        ):
            samples.append({
                "workload": "sample",
                "mode": mode,
                "repetition": repetition,
                "total_ns": base * scale,
            })

    row = summarize(samples)[0]
    assert row["workload"] == "sample"
    assert row["repetitions"] == 3
    assert abs(row["tracking_overhead_median_pct"] - 10.0) < 1e-9
    assert abs(row["validation_overhead_median_pct"] - 10.0) < 1e-9
    assert abs(row["total_overhead_median_pct"] - 21.0) < 1e-9
    assert abs(row["rlbox_median_ms"] - 0.0002) < 1e-12
    assert abs(row["tracked_median_ms"] - 0.00022) < 1e-12
    assert abs(row["extended_median_ms"] - 0.000242) < 1e-12

    incomplete = [sample for sample in samples
                  if not (sample["repetition"] == 2 and sample["mode"] == "rlbox_only")]
    try:
        summarize(incomplete)
    except ValueError as exc:
        assert "incomplete P9a triple" in str(exc)
    else:
        raise AssertionError("incomplete P9a triple was accepted")

    print("P9a application summary tests: ok")


if __name__ == "__main__":
    main()
