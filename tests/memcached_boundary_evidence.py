#!/usr/bin/env python3
"""Synthetic negative controls; fixture values are never reported as results."""
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from run_memcached_boundary_bench import expected_cells
from verify_memcached_boundary_bench import verify


def write_csv(path, rows):
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


class BoundaryEvidenceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        variants = ("native", "rlbox-only", "tracked-no-check", "interspec")
        (self.root / "environment.json").write_text(json.dumps(dict(repetitions=5, iterations=1000,
            build=dict(source_dirty=False, binary_sha256={v: "0" * 64 for v in variants}))))
        rows, summaries = [], []
        for rep in range(5):
            for rank, variant in enumerate(variants):
                raw = []
                for metric, size in sorted(expected_cells(variant)):
                    checksum = 500500 if metric == "empty_call" else 0 if metric in ("wrapper_mutex", "copy_into_u", "copy_from_u") else 1000
                    row = dict(metric=metric, bytes=size, operations=1000, total_ns=10000, ns_per_op=10, checksum=checksum)
                    raw.append(row); rows.append(dict(repetition=rep, order=rank, variant=variant, **row))
                    if rep == 0:
                        summaries.append(dict(variant=variant, metric=metric, bytes=size, n=5, median_ns=10, min_ns=10, max_ns=10))
                write_csv(self.root / f"{rep}-{variant}.stdout", raw)
                (self.root / f"{rep}-{variant}.stderr").write_text("")
        write_csv(self.root / "raw.csv", rows)
        (self.root / "summary.json").write_text(json.dumps(summaries))

    def test_complete(self):
        r = verify(self.root)
        self.assertEqual((r["configurations"], r["samples"]), (98, 490))
        self.assertFalse(r["publication_ready"])

    def test_missing_cell(self):
        p = self.root / "raw.csv"
        with p.open() as f: rows = list(csv.DictReader(f))
        write_csv(p, rows[:-1])
        with self.assertRaisesRegex(ValueError, "missing or duplicate"):
            verify(self.root)

    def test_process_output_mismatch(self):
        p = self.root / "0-native.stdout"
        p.write_text(p.read_text().replace("10000", "20000", 1))
        with self.assertRaisesRegex(ValueError, "process output differs"):
            verify(self.root)

    def test_stderr_rejected(self):
        (self.root / "0-interspec.stderr").write_text("functional check failed")
        with self.assertRaisesRegex(ValueError, "stderr"):
            verify(self.root)

    def test_summary_corruption(self):
        p = self.root / "summary.json"; rows = json.loads(p.read_text())
        rows[0]["median_ns"] = 12; p.write_text(json.dumps(rows))
        with self.assertRaisesRegex(ValueError, "summary arithmetic"):
            verify(self.root)


if __name__ == "__main__": unittest.main()
