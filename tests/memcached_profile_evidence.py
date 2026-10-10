#!/usr/bin/env python3
"""Synthetic trace fixtures test rejection, not application measurements."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from verify_memcached_profile import verify


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


class ProfileEvidenceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); self.gate = self.root / "gate.json"
        write(self.gate, dict(passed=50, total=50, binary_sha256={"memcached-diagnostics": "test"}))
        write(self.root / "environment.json", dict(diagnostic_sha256="test", build=dict(binary_sha256={"memcached-diagnostics": "test"}), parameters=dict(operations=100, write_operations=100)))
        rows = []
        for name in ("balanced_1c", "balanced_8c", "read_heavy_1k", "write_heavy", "watch_light", "watch_moderate"):
            trace = "".join(f"INTERSPEC event={event} result={result} requested={n}\n" for event, result, n in (
                ("check", "ok", 16), ("request", "sp3_ok", 16),
                ("sandbox_call", "interspec_mc_request", 0),
                ("copy_into_u", "push", 16), ("copy_from_u", "poll", 16),
                ("lru_hold", "ok", 1), ("lru_take", "ok", 1)))
            (self.root / f"{name}.trace").write_text(trace)
            (self.root / "logs").mkdir(exist_ok=True)
            (self.root / "logs" / f"check-profile-{name}.stderr").write_text("setup\n" + trace + "shutdown\n")
            write(self.root / f"{name}.client.json", dict(operations=100, errors=0))
            loss = dict(log_worker_dropped=0, log_watcher_skipped=0, lru_bumps_dropped=0)
            write(self.root / f"{name}.stats.json", dict(before=dict(moves_to_warm=0, **loss), after=dict(moves_to_warm=1, **loss)))
            rows.append(dict(name=name, operations=100, trace_start_offset=6, trace_end_offset=6+len(trace), trace_sha256=hashlib.sha256(trace.encode()).hexdigest(),
                runtime_checks=1, check_operations=dict(request=1), sandbox_call_functions=dict(interspec_mc_request=1),
                copy_into_u_operations=dict(push=16), copy_from_u_operations=dict(poll=16),
                sandbox_calls=1, sandbox_calls_per_operation=.01, bytes_into_u=16, bytes_into_u_per_operation=.16,
                bytes_from_u=16, bytes_from_u_per_operation=.16, checks_per_operation=.01, checks_per_1000_operations=10,
                loss_counters=loss, moves_to_warm=1, lru_holds=1, lru_takes=1, coverage_valid=True))
        write(self.root / "check-frequency.json", rows)

    def change(self, fn):
        path = self.root / "check-frequency.json"; rows = json.loads(path.read_text()); fn(rows); write(path, rows)

    def test_complete(self):
        self.assertEqual(verify(self.root, self.gate)["scenarios"], 6)

    def test_trace_tampering(self):
        (self.root / "write_heavy.trace").write_text("INTERSPEC event=check result=ok\n")
        with self.assertRaisesRegex(ValueError, "trace interval"):
            verify(self.root, self.gate)

    def test_missing_write_coverage(self):
        self.change(lambda rows: rows[3].update(coverage_valid=False))
        with self.assertRaisesRegex(ValueError, "not observed"):
            verify(self.root, self.gate)

    def test_wrong_copy_count(self):
        self.change(lambda rows: rows[0].update(bytes_into_u=32))
        with self.assertRaisesRegex(ValueError, "bytes_into_u frequency"):
            verify(self.root, self.gate)

    def test_wrong_client_count(self):
        write(self.root / "write_heavy.client.json", dict(operations=50, errors=0))
        with self.assertRaisesRegex(ValueError, "client workload"):
            verify(self.root, self.gate)


if __name__ == "__main__": unittest.main()
