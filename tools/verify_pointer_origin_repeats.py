#!/usr/bin/env python3
"""Independently recompute repeated pointer-origin statistics from raw traces."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics

from benchmark_memcached_matrix import SCENARIOS
from summarize_pointer_census import parse_record


def dispersion(values):
    return {
        "median": statistics.median(values),
        "minimum": min(values),
        "maximum": max(values),
        "population_stdev": statistics.pstdev(values),
        "repetitions": len(values),
    }


def same_metrics(actual, expected):
    assert set(actual) == set(expected)
    for key, expected_value in expected.items():
        if isinstance(expected_value, float):
            assert math.isclose(actual[key], expected_value,
                                rel_tol=1e-10, abs_tol=1e-10), (key, actual[key], expected_value)
        else:
            assert actual[key] == expected_value, (key, actual[key], expected_value)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", required=True, type=Path)
    p.add_argument("--correctness-summary", required=True, type=Path)
    args = p.parse_args()
    root = args.results
    gate = json.loads(args.correctness_summary.read_text())
    env = json.loads((root / "environment.json").read_text())
    samples = json.loads((root / "samples.json").read_text())
    summary = json.loads((root / "normalized-summary.json").read_text())
    assert gate["passed"] == gate["total"] == 50
    assert env["diagnostic_sha256"] == gate["binary_sha256"]["memcached-diagnostics"]
    assert summary["schema"] == 1 and summary["not_performance_measurement"] is True
    assert summary["vma_is_not_allocation_provenance"] is True
    assert summary["t_pointer_addresses_pass_raw_to_u"] is False
    params = env["parameters"]
    repeats = int(params["repetitions"])
    assert repeats >= 3
    expected_scenarios = {scenario["name"]: scenario for scenario in SCENARIOS}
    assert len(samples) == len(expected_scenarios) * repeats
    assert len(summary["runs"]) == len(expected_scenarios)
    assert {row["scenario"] for row in summary["runs"]} == set(expected_scenarios)

    by_scenario = {}
    verified_traces = 0
    verified_events = 0
    for sample in samples:
        name = sample["scenario"]
        assert name in expected_scenarios
        iteration = sample["repetition"]
        assert isinstance(iteration, int) and 1 <= iteration <= repeats
        target = int(params["write_operations"] if name == "write_heavy" else params["operations"])
        assert sample["client_operations"] == target
        assert sample["client_report"]["operations"] == target
        assert sample["client_report"]["errors"] == 0
        assert sample["trace_file"] == f"{name}-repeat{iteration:02d}.trace"
        assert sample["end_offset"] >= sample["start_offset"]
        raw = (root / sample["trace_file"]).read_bytes()
        assert len(raw) == sample["end_offset"] - sample["start_offset"]
        assert hashlib.sha256(raw).hexdigest() == sample["trace_sha256"]
        assert b"INTERSPEC_REJECT" not in raw
        direction, storage, site = Counter(), Counter(), Counter()
        for number, line in enumerate(raw.decode("utf-8", errors="replace").splitlines(), 1):
            record = parse_record(line, sample["trace_file"], number, "memcached_bipbuffer")
            if record is None:
                continue
            if record["direction"] == "u_to_t":
                assert record["storage"] == "u_tracked_heap" and record["result"] == "accepted"
            else:
                assert record["result"] == "observed"
            direction[record["direction"]] += 1
            storage[record["storage"]] += 1
            site[(record["direction"], record["site"], record["storage"])] += 1
        assert sample["by_direction"] == dict(sorted(direction.items()))
        assert sample["by_storage"] == dict(sorted(storage.items()))
        actual_sites = {(r["direction"], r["site"], r["storage"]): r["observations"]
                        for r in sample["by_site"]}
        assert dict(site) == actual_sites
        observations = sum(direction.values())
        assert sample["observations"] == observations
        assert math.isclose(sample["observations_per_1000_ops"],
                            observations * 1000.0 / target, abs_tol=1e-10)
        before, after = sample["monitored_stats_before"], sample["monitored_stats_after"]
        assert set(before) == set(after) == set(sample["loss_counters"]) == {
            "log_worker_dropped", "log_watcher_skipped", "lru_bumps_dropped",
        }
        assert all(after[key] - before[key] == sample["loss_counters"][key] == 0
                   for key in before)
        by_scenario.setdefault(name, []).append({
            "repetition": iteration, "operations": target,
            "observations": observations, "storage": storage, "site": site,
        })
        verified_traces += 1
        verified_events += observations

    assert verified_events > 0
    for reported in summary["runs"]:
        name = reported["scenario"]
        rows = sorted(by_scenario[name], key=lambda x: x["repetition"])
        assert len(rows) == repeats
        assert [r["repetition"] for r in rows] == list(range(1, repeats + 1))
        target = rows[0]["operations"]
        assert reported["repetitions"] == repeats
        assert reported["client_operations_per_repeat"] == target
        assert reported["purpose"] == expected_scenarios[name]["purpose"]
        assert reported["loss_free_and_no_rejections"] is True
        same_metrics(reported["observations_per_1000_operations"], dispersion(
            [r["observations"] * 1000.0 / target for r in rows]
        ))
        origins = sorted({key for r in rows for key in r["storage"]})
        assert set(reported["storage_per_1000_operations"]) == set(origins)
        for origin in origins:
            same_metrics(reported["storage_per_1000_operations"][origin], dispersion(
                [r["storage"][origin] * 1000.0 / target for r in rows]
            ))
        keys = sorted({key for r in rows for key in r["site"]})
        observed = {(r["direction"], r["site"], r["storage"]): r["per_1000_operations"]
                    for r in reported["site_per_1000_operations"]}
        assert set(observed) == set(keys)
        for key in keys:
            same_metrics(observed[key], dispersion(
                [r["site"][key] * 1000.0 / target for r in rows]
            ))
    print("INTERSPEC_POINTER_REPEAT_VERIFIED " + json.dumps({
        "repetitions_per_scenario": repeats,
        "scenarios": len(expected_scenarios),
        "traces_verified": verified_traces,
        "observations_verified": verified_events,
        "normal_correctness_cases": 50,
        "all_trace_hashes_verified": True,
        "all_normalized_rates_recomputed": True,
        "all_monitored_loss_counters_zero": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
