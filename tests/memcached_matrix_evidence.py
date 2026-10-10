#!/usr/bin/env python3
"""Negative controls for the evidence validator. All fixtures are synthetic."""
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from verify_memcached_matrix import SCENARIOS, VARIANTS, verify


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.matrix = self.root / "matrix"
        self.gate = self.root / "gate.json"
        hashes = {"memcached-" + v: "fixture-" + v for v in VARIANTS}
        write_json(self.gate, dict(passed=50, total=50, binary_sha256=hashes))
        combined, all_rows = [], []
        for name, cfg in SCENARIOS.items():
            folder = self.matrix / name
            params = dict(zip(("clients", "pipeline", "value_bytes", "keys", "get_percent", "workloads"), cfg))
            params.update(seconds=1, warmup=.3, repetitions=3, variants=",".join(VARIANTS))
            write_json(folder / "environment.json", dict(parameters=params,
                       build=dict(project_commit="synthetic", project_dirty=False, binary_sha256=hashes),
                       client_sha256="fixture", collector_sha256="fixture", host={}, affinity=[]))
            rows = []
            for rep in range(3):
                for order, v in enumerate(VARIANTS):
                    row = dict(workload=cfg[-1], repetition=rep, order=order, variant=v,
                               operations=100, elapsed_s=1, ops_per_s=100, errors=0,
                               p50_us=1, p95_us=2, p99_us=3, max_us=4, VmRSS_kib=1024,
                               VmHWM_kib=2048, server_cpu_s=.1, cpu_us_per_op=1000,
                               startup_ms=1, log_worker_written=100, log_worker_dropped=0,
                               log_watcher_sent=100, log_watcher_skipped=0, lru_bumps_dropped=0,
                               moves_to_warm=1, watcher_bytes_including_warmup=100,
                               valid_no_log_loss=True, valid_no_lru_loss=True)
                    stem = f"{cfg[-1]}-{rep}-{v}"
                    keys = ("log_worker_written", "log_worker_dropped", "log_watcher_sent", "log_watcher_skipped", "lru_bumps_dropped", "moves_to_warm")
                    write_json(folder / "logs" / (stem + ".stats.json"), dict(before={k: 0 for k in keys}, after={k: row[k] for k in keys}))
                    (folder / "logs" / (stem + ".stderr")).write_text("")
                    rows.append(row)
            write_csv(folder / "samples.csv", rows)
            all_rows += [dict(scenario=name, **r) for r in rows]
            summaries = []
            for v in VARIANTS:
                s = dict(variant=v, n=3, all_no_log_loss=True, all_no_lru_loss=True)
                for metric in ("ops_per_s", "p50_us", "p95_us", "p99_us", "VmRSS_kib", "VmHWM_kib", "server_cpu_s", "cpu_us_per_op", "startup_ms"):
                    for suffix in ("median", "min", "max"):
                        s[metric + "_" + suffix] = rows[0][metric]
                for base in VARIANTS[:3]:
                    s[f"throughput_loss_vs_{base}_paired_median_pct"] = 0
                summaries.append(s)
            write_json(folder / "summary.json", summaries)
            c = dict(name=name, valid_lossless=True)
            for prefix in ("native", "rlbox", "tracking", "interspec"):
                c.update({prefix + "_ops_per_s": 100, prefix + "_p99_us": 3,
                          prefix + "_cpu_us_per_op": 1000, prefix + "_rss_mib": 1})
            for field in ("rlbox_loss_vs_native_pct", "interspec_loss_vs_native_pct", "interspec_loss_vs_rlbox_pct", "tracking_loss_vs_rlbox_pct", "interspec_loss_vs_tracking_pct"):
                c[field] = 0
            combined.append(c)
        write_csv(self.matrix / "all-samples.csv", all_rows)
        write_json(self.matrix / "final-summary.json", dict(variants=list(VARIANTS), scenarios=combined,
                   repetitions=3, seconds=1, warmup=.3, invalid_loss_scenarios=[]))

    def run_verify(self):
        return verify(self.matrix, self.gate)

    def change_raw(self, fn):
        path = self.matrix / "balanced_1c/samples.csv"
        with path.open() as stream:
            rows = list(csv.DictReader(stream))
        fn(rows)
        write_csv(path, rows)

    def test_complete_fixture(self):
        self.assertEqual(self.run_verify()["samples"], 72)
        self.assertFalse(self.run_verify()["publication_ready"])

    def test_missing_tracking_pair(self):
        self.change_raw(lambda rows: rows.pop(2))
        with self.assertRaisesRegex(ValueError, "missing/duplicate pair"):
            self.run_verify()

    def test_duplicate_pair(self):
        self.change_raw(lambda rows: rows.append(rows[0]))
        with self.assertRaisesRegex(ValueError, "missing/duplicate pair"):
            self.run_verify()

    def test_tracking_drop_rejected_even_if_flags_claim_valid(self):
        self.change_raw(lambda rows: rows[2].update(log_worker_dropped="1"))
        with self.assertRaisesRegex(ValueError, "tracked-no-check.*log_worker_dropped"):
            self.run_verify()

    def test_client_error(self):
        self.change_raw(lambda rows: rows[0].update(errors="1"))
        with self.assertRaisesRegex(ValueError, "client run"):
            self.run_verify()

    def test_wrong_throughput(self):
        self.change_raw(lambda rows: rows[0].update(ops_per_s="200"))
        with self.assertRaisesRegex(ValueError, "throughput arithmetic"):
            self.run_verify()

    def test_wrong_summary(self):
        path = self.matrix / "final-summary.json"
        doc = json.loads(path.read_text())
        doc["scenarios"][0]["tracking_loss_vs_rlbox_pct"] = .1
        write_json(path, doc)
        with self.assertRaisesRegex(ValueError, "matrix tracking_loss"):
            self.run_verify()

    def test_binary_mismatch(self):
        gate = json.loads(self.gate.read_text())
        gate["binary_sha256"]["memcached-tracked-no-check"] = "changed"
        write_json(self.gate, gate)
        with self.assertRaisesRegex(ValueError, "binary differs"):
            self.run_verify()


if __name__ == "__main__":
    unittest.main()
