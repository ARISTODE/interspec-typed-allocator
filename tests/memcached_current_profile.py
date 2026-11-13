#!/usr/bin/env python3
"""Current-source profile contract tests; synthetic gates, no server execution."""
import argparse
import copy
import json
import os
import pwd
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import current_memcached_profile as builder
import profile_memcached_checks as collector
import verify_memcached_profile as verifier
import export_memcached_profile as exporter


class CurrentPlan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.base = Path(cls.temp.name)
        source = cls.base / "source"
        files = set(builder.SOURCES) | set(collector.HARNESS) | {
            "tools/current_memcached_profile.py", "tests/memcached_profile_evidence.py",
            "tests/memcached_corrected_profile.py", "integration/memcached_server/bridge.cpp",
            "integration/memcached_server/bipbuffer_u.c"}
        for relative in files:
            target = source / relative; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        subprocess.run(["git", "init", "-q", str(source)], check=True)
        subprocess.run(["git", "-C", str(source), "add", "."], check=True)
        subprocess.run(["git", "-C", str(source), "-c", "user.name=Profile fixture", "-c",
                        "user.email=fixture@example.invalid", "commit", "-qm", "Synthetic profile source fixture"], check=True)
        cls.revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
        work = cls.base / "work"; (work / "bin").mkdir(parents=True)
        diagnostic = work / "bin/memcached-diagnostics"
        diagnostic.write_text("synthetic identity fixture; never executed\n")
        gate = cls.base / "gate.json"
        gate.write_text(json.dumps(dict(passed=50, total=50, cases=[{"pass": True}] * 50,
                                       binary_sha256={diagnostic.name: builder.sha(diagnostic)})))
        (work / "build-manifest.json").write_text(json.dumps(dict(project_commit=cls.revision,
            project_dirty=False, binary_sha256={diagnostic.name: builder.sha(diagnostic)},
            bridge_source_sha256=builder.sha(source / "integration/memcached_server/bridge.cpp"),
            untrusted_source_sha256=builder.sha(source / "integration/memcached_server/bipbuffer_u.c"))))
        # Exercise the actual CLI and current-source builder, including 926 valid
        # loopback responses. The diagnostic identity fixture is never launched.
        command = [sys.executable, str(source / "tools/profile_memcached_checks.py"), "prepare-current",
                   "--plan-directory", str(cls.base / "frozen"), "--out", str(cls.base / "raw"),
                   "--client-build-directory", str(cls.base / "client-build"), "--work", str(work),
                   "--correctness-summary", str(gate)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.command = command
        cls.result = json.loads(result.stdout)

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "frozen"
        shutil.copytree(self.base / "frozen", self.root)
        self.path = self.root / "plan.json"
        self.plan = json.loads(self.path.read_text())

    def change(self, relative, transform):
        p = self.root / relative; value = json.loads(p.read_text()); transform(value)
        p.write_text(json.dumps(value)); self.plan["files"][relative] = builder.sha(p)
        self.path.write_text(json.dumps(self.plan))

    def rejects(self, message):
        return self.assertRaisesRegex(ValueError, message)

    def test_current_plan_and_relocation(self):
        self.assertEqual(verifier.validate_plan(self.path)["schema"], "source-profile-v2")
        self.assertEqual(self.result["collected"], False)
        self.assertFalse((self.base / "raw").exists())

    def test_fresh_outputs_required(self):
        result = subprocess.run(self.command, capture_output=True, text=True, timeout=20)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FileExistsError", result.stderr)

    def test_full_synthetic_replay_and_render(self):
        raw = self.root.parent / "synthetic-raw"; raw.mkdir()
        plan = self.plan
        def event(kind, result, size=0):
            return (f"INTERSPEC seq=1 pid=1 runtime=0x1 thread=1 event={kind} ptr=0x0 base=0x0 size=0 site=0 "
                    f"actual_type=0x0 expected_type=0x0 requested={size} offset=0 remaining=0 replacement=0x0 result={result}\n")
        trace = (event("check", "ok", 16) + event("request", "sp3_ok", 16) +
                 event("sandbox_call", "interspec_mc_request") + event("copy_into_u", "push", 16) +
                 event("copy_from_u", "poll", 16) + event("lru_hold", "ok", 1) + event("lru_take", "ok", 1) +
                 "INTERSPEC_T_COPY boundary=memcached_bipbuffer operation=poll bytes=16 fnv64=0123456789abcdef\n").encode()
        def write(path, value): path.write_text(json.dumps(value))
        for row in plan["scenarios"]:
            directory = raw / row["name"]; directory.mkdir()
            argv = [str(Path(plan["execution"]["plan_root"]) / "inputs/client"), "12345", "0",
                    *[str(row[k]) for k in ("clients", "pipeline", "value_bytes", "profile_keys", "get_percent", "operations")],
                    "independent-v1", "20261109", "count-only"]
            state = dict(name=row["name"], status="collected", attempt=1, interval=plan["interval"], port=12345,
                client_argv=argv, executed_client_argv=[plan["execution"]["python"], plan["execution"]["guard"], "1", *argv],
                client_returncode=0, server_returncode=-15,
                server_argv=[str(Path(plan["execution"]["plan_root"]) / "inputs/work/bin/memcached-diagnostics"),
                    "-l", "127.0.0.1", "-p", "12345", "-U", "0", "-m", "64", "-t", "4", "-u", plan["execution"]["account_name"],
                    "-o", "worker_logbuf_size=1024,watcher_logbuf_size=4096"], trace_start_offset=0, trace_end_offset=len(trace))
            if row["mode"] == "watch_active": state["watcher"] = dict(error=None, bytes=10, lines=1)
            write(directory / "client.stdout", dict(operations=row["operations"], errors=0, workload_mode="independent-v1",
                workload_seed=20261109, measurement_mode="count-only", p50_us=None, p95_us=None, p99_us=None, max_us=None,
                sample_every=0, sample_cap_per_client=0, latency_sample_count=0, latency_selected_count=0,
                latency_dropped_count=0, latency_valid=False, latency_scope="unavailable"))
            before = {key: 0 for key in ("cmd_get", "cmd_set", "get_hits", "get_misses", "log_worker_dropped", "log_watcher_skipped", "lru_bumps_dropped", "moves_to_warm")}
            after = dict(before, cmd_get=row["expected"]["get"], cmd_set=row["expected"]["set"], get_hits=row["expected"]["get"], moves_to_warm=1)
            write(directory / "before.json", before); write(directory / "after.json", after)
            (directory / "client.stderr").write_bytes(b""); (directory / "server.stdout").write_bytes(b"")
            (directory / "server.stderr").write_bytes(trace); (directory / "trace.txt").write_bytes(trace)
            state["trace_sha256"] = builder.sha(directory / "trace.txt")
            write(directory / "counts.json", collector.summarize(trace))
            state["files"] = {p.name: builder.sha(p) for p in directory.iterdir()}
            write(directory / "attempt.json", state)
        write(raw / "run.json", dict(schema=plan["schema"], plan_sha256=builder.sha(self.path), status="collected",
            attempts=[dict(name=row["name"], attempt=1, status="collected") for row in plan["scenarios"]]))
        verified = verifier.verify_frozen(raw, self.path)
        self.assertEqual(verified["scenarios"], 6)
        rows = exporter.export(raw, self.path)
        checks = self.root.parent / "checks.json"; write(checks, rows)
        matrix = self.root.parent / "matrix.json"
        write(matrix, dict(workload_mode="independent-v1", workload_seed=20261109, measurement_mode="count-only", variants=[],
            scenarios=[dict(name=row["name"], native_ops_per_s=1, rlbox_ops_per_s=1, interspec_ops_per_s=1,
                rlbox_loss_vs_native_pct=0, interspec_loss_vs_native_pct=0, interspec_loss_vs_rlbox_pct=0,
                native_p99_us=None, rlbox_p99_us=None, interspec_p99_us=None, valid_lossless=True) for row in rows]))
        micro = self.root.parent / "micro.json"
        write(micro, [dict(metric="check_live", population=2, threads=1, ns_per_op_median=1, ns_per_op_min=1, ns_per_op_max=1)])
        report = self.root.parent / "report.md"
        result = subprocess.run([sys.executable, str(ROOT / "tools/render_memcached_overhead_study.py"), "--matrix", str(matrix),
            "--checks", str(checks), "--microbench", str(micro), "--output", str(report)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("unavailable/unavailable/unavailable", report.read_text())
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[3]["profile_keys"], 10000)

    def test_protocol_command(self):
        self.change("inputs/client-validation/provenance.json", lambda d: d["command"].__setitem__(-1, "--other"))
        with self.rejects("protocol command/status"): verifier.validate_plan(self.path)

    def test_protocol_binary(self):
        self.change("inputs/client-validation/provenance.json", lambda d: d.update(candidate_binary_sha256="0" * 64))
        with self.rejects("protocol binary binding"): verifier.validate_plan(self.path)

    def test_protocol_status_is_integer(self):
        self.change("inputs/client-validation/provenance.json", lambda d: d.update(returncode=False))
        with self.rejects("protocol command/status"): verifier.validate_plan(self.path)

    def test_build_command(self):
        self.change("inputs/client-provenance.json", lambda d: d["build_command"].__setitem__(2, "-O0"))
        with self.rejects("client build command"): verifier.validate_plan(self.path)

    def test_source_set(self):
        self.change("inputs/client-provenance.json", lambda d: d["source_sha256"].pop("tests/memcached_buffered_protocol.py"))
        with self.rejects("current client source set"): verifier.validate_plan(self.path)

    def test_source_revision(self):
        self.change("inputs/work/build-manifest.json", lambda d: d.update(project_commit="0" * 40))
        with self.rejects("current server clean-source revision"): verifier.validate_plan(self.path)

    def test_dirty_build(self):
        self.change("inputs/work/build-manifest.json", lambda d: d.update(project_dirty=True))
        with self.rejects("current server clean-source revision"): verifier.validate_plan(self.path)

    def test_protocol_log(self):
        relative = "inputs/client-validation/release-reproduction-functional.log"
        (self.root / relative).write_text("not a pass\n")
        self.plan["files"][relative] = builder.sha(self.root / relative)
        self.path.write_text(json.dumps(self.plan))
        with self.rejects("current protocol output"): verifier.validate_plan(self.path)

    def test_historical_pins_not_relaxed(self):
        self.plan["schema"] = "corrected-profile-v1"; self.path.write_text(json.dumps(self.plan))
        with self.rejects("client revision"): verifier.validate_plan(self.path)

    def test_no_schema_downgrade(self):
        self.plan["schema"] = "unknown"; self.path.write_text(json.dumps(self.plan))
        with self.rejects("plan schema"): verifier.validate_plan(self.path)


class ExportAndWorkflow(unittest.TestCase):
    def test_export_derived_rates(self):
        verified = dict(plan_sha256="fixture", rows=[dict(name="test", operations=10,
            runtime_checks=2, sandbox_calls=4, bytes_into_u=20, bytes_from_u=30)])
        plan = dict(schema="source-profile-v2", workload_mode="independent-v1", workload_seed=20261109,
                    measurement_mode="count-only", scenarios=[dict(profile_keys=2048)])
        with patch.object(exporter, "verify_frozen", return_value=verified) as verify, patch.object(exporter, "load_json", return_value=plan):
            row = exporter.export(Path("raw"), Path("plan"))[0]
        verify.assert_called_once_with(Path("raw"), Path("plan"))
        self.assertEqual(row["checks_per_operation"], .2)
        self.assertEqual(row["checks_per_1000_operations"], 200)
        self.assertEqual(row["bytes_from_u_per_operation"], 3)
        self.assertFalse(row["timing_evidence"])
        self.assertFalse(row["latency_evidence"])
        self.assertEqual(row["workload_seed"], 20261109)

    def test_export_rejects_unverified(self):
        with patch.object(exporter, "verify_frozen", side_effect=ValueError("incomplete")):
            with self.assertRaisesRegex(ValueError, "incomplete"): exporter.export(Path("raw"), Path("plan"))

    def test_wrapper_consumes_work_override(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / "bin").mkdir()
            fake = root / "bin/python3"
            fake.write_text('#!/bin/sh\nprintf "%s:%s\\n" "$*" "${INTERSPEC_MEMCACHED_WORK-unset}" >> "$PROFILE_TEST_LOG"\n')
            fake.chmod(0o700)
            gate = root / "gate.json"; gate.write_text("{}")
            log = root / "commands.log"
            result = subprocess.run(["bash", str(ROOT / "scripts/run_memcached_profile.sh"), str(root / "output"), str(gate)],
                capture_output=True, text=True, env={**os.environ, "PATH": str(root / "bin") + os.pathsep + os.environ["PATH"],
                    "INTERSPEC_MEMCACHED_WORK": str(root / "work"), "PROFILE_TEST_LOG": str(log)})
            self.assertEqual(result.returncode, 0, result.stderr)
            calls = log.read_text().splitlines()
            self.assertEqual(len(calls), 4)
            self.assertIn(" collect --plan ", calls[1])
            self.assertTrue(calls[1].endswith(":unset"))
            self.assertIn("--work " + str(root / "work"), calls[0])

    def test_workflow_contract(self):
        for name in ("memcached-deployment.yml", "controlled-publication-evaluation.yml"):
            workflow = (ROOT / ".github/workflows" / name).read_text()
            self.assertIn("bash scripts/run_memcached_profile.sh", workflow)
            self.assertNotIn("profile_memcached_checks.py --out", workflow)
            self.assertNotIn("--require-coverage", workflow)
        script = (ROOT / "scripts/run_memcached_profile.sh").read_text()
        self.assertIn("prepare-current", script)
        self.assertIn('collect --plan "$out/frozen/plan.json"', script)
        self.assertIn('export_memcached_profile.py', script)


if __name__ == "__main__": unittest.main()
