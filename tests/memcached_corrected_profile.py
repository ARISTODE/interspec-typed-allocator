#!/usr/bin/env python3
"""Synthetic-only frozen profile evidence and lifecycle checks. No applications."""
import copy
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import profile_memcached_checks as collector
import verify_memcached_profile as verifier


def event(kind, result, requested=0):
    return (f"INTERSPEC seq=1 pid=1 runtime=0x1 thread=1 event={kind} ptr=0x0 base=0x0 size=0 site=0 "
            f"actual_type=0x0 expected_type=0x0 requested={requested} offset=0 remaining=0 replacement=0x0 result={result}\n")


class Evidence(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name); self.directory = self.base / "balanced_1c"; self.directory.mkdir()
        self.plan = {"interval": collector.INTERVAL, "workload_mode": "independent-v1", "workload_seed": 20261109, "measurement_mode": "count-only"}
        self.plan["execution"] = dict(plan_root=str(self.base), harness_root=str(Path(collector.__file__).resolve().parents[1]),
                                      python=sys.executable, guard=str(Path(collector.__file__).parent / "process_guard.py"), account_name=pwd.getpwuid(os.getuid()).pw_name, uid=os.getuid())
        self.row = dict(name="balanced_1c", mode="cache_only", clients=1, pipeline=10, value_bytes=256, profile_keys=2048,
                        get_percent=50, operations=5000, expected={"get":2503, "set":2497, "key_verb_multiset_sha256":"fixture"})
        self.client = dict(operations=5000, errors=0, workload_mode="independent-v1", workload_seed=20261109, measurement_mode="count-only",
                          p50_us=None, p95_us=None, p99_us=None, max_us=None, sample_every=0, sample_cap_per_client=0,
                          latency_sample_count=0, latency_selected_count=0, latency_dropped_count=0, latency_valid=False, latency_scope="unavailable")
        self.before = {k:0 for k in ("cmd_get", "cmd_set", "get_hits", "get_misses", "log_worker_dropped", "log_watcher_skipped", "lru_bumps_dropped", "moves_to_warm")}
        self.after = dict(self.before, cmd_get=2503, cmd_set=2497, get_hits=2503, moves_to_warm=1)
        self.trace = (event("check", "ok",16) + event("request", "sp3_ok",16) + event("sandbox_call", "interspec_mc_request") +
                      event("copy_into_u", "push",16) + event("copy_from_u", "poll",16) + event("lru_hold","ok",1) + event("lru_take","ok",1) +
                      "INTERSPEC_T_COPY boundary=memcached_bipbuffer operation=poll bytes=16 fnv64=0123456789abcdef\n").encode()
        argv = [str(self.base / "inputs/client"), "12345", "0", "1", "10", "256", "2048", "50", "5000", "independent-v1", "20261109", "count-only"]
        self.state = dict(name="balanced_1c", attempt=1, status="collected", interval=collector.INTERVAL, port=12345,
                          client_argv=argv, executed_client_argv=[sys.executable, str(Path(collector.__file__).parent / "process_guard.py"), "1", *argv],
                          client_returncode=0, server_returncode=-15, server_argv=[str(self.base / "inputs/work/bin/memcached-diagnostics"), "-l", "127.0.0.1", "-p", "12345", "-U", "0", "-m", "64", "-t", "4", "-u", pwd.getpwuid(os.getuid()).pw_name, "-o", "worker_logbuf_size=1024,watcher_logbuf_size=4096"],
                          trace_start_offset=6, trace_end_offset=6+len(self.trace), trace_sha256=hashlib.sha256(self.trace).hexdigest())
        self.write("client.stdout", self.client); self.write("before.json", self.before); self.write("after.json", self.after)
        self.write("counts.json", collector.summarize(self.trace))
        (self.directory / "client.stderr").write_bytes(b""); (self.directory / "server.stdout").write_bytes(b"")
        (self.directory / "server.stderr").write_bytes(b"setup\n" + self.trace + b"shutdown\n")
        (self.directory / "trace.txt").write_bytes(self.trace)
        self.refresh()

    def write(self, name, value): (self.directory / name).write_text(json.dumps(value))
    def refresh(self):
        self.state["files"] = {p.name:verifier.sha(p) for p in self.directory.iterdir() if p.name != "attempt.json"}
        self.write("attempt.json", self.state)
    def verify(self): return verifier.verify_attempt(self.directory, self.row, self.plan, self.base)
    def change_client(self, **changes): self.client.update(changes); self.write("client.stdout", self.client); self.refresh()

    def test_complete(self): self.assertEqual(self.verify()["operations"],5000)
    def test_copy_replay(self):
        moved=self.base / "restored"
        shutil.copytree(self.directory,moved)
        self.assertEqual(verifier.verify_attempt(moved,self.row,self.plan,self.base/"different-frozen-root")["operations"],5000)
    def test_server_failure(self):
        self.state["server_returncode"]=-9; self.refresh()
        with self.assertRaisesRegex(ValueError,"server process"): self.verify()
    def test_seed(self):
        self.change_client(workload_seed=3)
        with self.assertRaisesRegex(ValueError,"mode/seed"): self.verify()
    def test_mode(self):
        self.change_client(measurement_mode="full")
        with self.assertRaisesRegex(ValueError,"mode/seed"): self.verify()
    def test_null_latency(self):
        self.change_client(p99_us=0)
        with self.assertRaisesRegex(ValueError,"quantiles"): self.verify()
    def test_samples(self):
        self.change_client(latency_sample_count=1)
        with self.assertRaisesRegex(ValueError,"sample counts"): self.verify()
    def test_float_client_metadata(self):
        self.change_client(operations=5000.0)
        with self.assertRaisesRegex(ValueError,"integer metadata"): self.verify()
    def test_bool_client_metadata(self):
        self.change_client(errors=False)
        with self.assertRaisesRegex(ValueError,"integer metadata"): self.verify()
    def test_float_stats(self):
        self.after["cmd_set"]=2497.9; self.write("after.json",self.after); self.refresh()
        with self.assertRaisesRegex(ValueError,"stats integer"): self.verify()
    def test_bool_stats(self):
        self.after["get_misses"]=False; self.write("after.json",self.after); self.refresh()
        with self.assertRaisesRegex(ValueError,"stats integer"): self.verify()
    def test_wrong_observed_count(self):
        self.after["cmd_set"]-=1; self.write("after.json",self.after); self.refresh()
        with self.assertRaisesRegex(ValueError,"aggregate"): self.verify()
    def test_losses(self):
        self.after["log_worker_dropped"]=1; self.write("after.json",self.after); self.refresh()
        with self.assertRaisesRegex(ValueError,"losses"): self.verify()
    def test_client_argv(self):
        self.state["client_argv"][7]="10"; self.refresh()
        with self.assertRaisesRegex(ValueError,"client argv"): self.verify()
    def test_server_argv(self):
        self.state["server_argv"][-1]="other"; self.refresh()
        with self.assertRaisesRegex(ValueError,"server argv"): self.verify()
    def test_stderr(self):
        (self.directory / "client.stderr").write_text("problem\n"); self.refresh()
        with self.assertRaisesRegex(ValueError,"stderr"): self.verify()
    def test_hash(self):
        (self.directory / "client.stdout").write_text("{}")
        with self.assertRaisesRegex(ValueError,"raw hash"): self.verify()
    def test_upper_offset(self):
        self.state["trace_end_offset"]=10**20; self.refresh()
        with self.assertRaisesRegex(ValueError,"offset bounds"): self.verify()
    def test_negative_offset(self):
        self.state["trace_start_offset"]=-1; self.refresh()
        with self.assertRaisesRegex(ValueError,"offset bounds"): self.verify()
    def test_partial_line(self):
        self.state["trace_start_offset"]=7; self.refresh()
        with self.assertRaisesRegex(ValueError,"line boundaries"): self.verify()
    def test_duplicate_json(self):
        (self.directory / "client.stdout").write_text('{"operations":5000,"operations":5000}'); self.refresh()
        with self.assertRaisesRegex(ValueError,"duplicate JSON"): self.verify()
    def test_nonfinite(self):
        (self.directory / "client.stdout").write_text('{"x":NaN}'); self.refresh()
        with self.assertRaisesRegex(ValueError,"nonfinite JSON"): self.verify()
    def test_unknown_trace(self):
        with self.assertRaisesRegex(ValueError,"unknown or failed"): verifier.strict_recount(self.trace.replace(b"event=check",b"event=bogus"))
    def test_duplicate_trace(self):
        with self.assertRaisesRegex(ValueError,"duplicate trace"): verifier.strict_recount(self.trace.replace(b"event=check",b"event=check event=check"))
    def test_failed_trace(self):
        with self.assertRaisesRegex(ValueError,"unknown or failed"): verifier.strict_recount(self.trace.replace(b"result=ok",b"result=failed",1))
    def test_bad_integer_trace(self):
        with self.assertRaisesRegex(ValueError,"integer schema"): verifier.strict_recount(self.trace.replace(b"requested=16",b"requested=-1",1))
    def test_snapshot(self):
        with self.assertRaisesRegex(ValueError,"record reconciliation"): verifier.strict_recount(self.trace.replace(b"bytes=16",b"bytes=17"))
    def test_incomplete_attempt(self):
        self.state["status"]="started"; self.refresh()
        with self.assertRaisesRegex(ValueError,"identity/status"): self.verify()
    def test_unlisted_raw(self):
        (self.directory / "extra").write_text("test")
        with self.assertRaisesRegex(ValueError,"attempt files"): self.verify()
    def test_write_lru_required(self):
        row=copy.deepcopy(self.row); row["name"]="write_heavy"; self.state["name"]="write_heavy"; self.after["moves_to_warm"]=0
        self.write("after.json",self.after); self.refresh()
        with self.assertRaisesRegex(ValueError,"protected coverage"): verifier.verify_attempt(self.directory,row,self.plan,self.base)


class Lifecycle(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); self.root=Path(tmp.name)
        self.plan=dict(schema="corrected-profile-v1",interval=collector.INTERVAL, workload_mode="independent-v1",workload_seed=20261109,measurement_mode="count-only")
        self.row=dict(name="balanced_1c",mode="cache_only",clients=1,pipeline=10,value_bytes=256,profile_keys=1,get_percent=50,operations=2)
    def test_existing_output_refused(self):
        with patch.object(collector,"check_plan",return_value=({"out":str(self.root)},self.root)):
            with self.assertRaises(FileExistsError): collector.collect(self.root / "plan.json")
    def test_server_failure_retained(self):
        with patch.object(collector,"Server",side_effect=RuntimeError("synthetic startup failure")):
            result=collector.collect_one(self.plan,self.root,self.row,self.root/"attempt")
        self.assertEqual(result["status"],"failed")
        self.assertIn("startup failure",json.loads((self.root/"attempt/attempt.json").read_text())["failure"]["message"])
        with self.assertRaises(FileExistsError): collector.collect_one(self.plan,self.root,self.row,self.root/"attempt")
    def fake_server(self, binary, directory, name, **kwargs):
        class Fake:
            def __enter__(obj): return obj
            def __exit__(obj,*args): return False
        f=Fake(); f.port=12345; f.args=[]; f.proc=subprocess.CompletedProcess([], -15); f.logpath=directory/"server.stderr"; f.logpath.write_bytes(b"setup\n")
        (directory/"server.stdout").write_bytes(b""); return f
    def fake_client(self,*args,**kwargs):
        class Fake:
            def __enter__(obj): return obj
            def __exit__(obj,*args): return False
            def store(obj,*args): return b"STORED\r\n"
            def stats(obj): return {}
        return Fake()
    def run_failure(self, timeout):
        def process(*args,**kwargs):
            kwargs["stdout"].write(b"partial raw stdout")
            kwargs["stderr"].write(b"synthetic diagnostic")
            if timeout: raise subprocess.TimeoutExpired("synthetic",120)
            return subprocess.CompletedProcess([],1)
        with patch.object(collector,"Server",side_effect=self.fake_server), patch.object(collector,"Client",side_effect=self.fake_client), patch.object(collector.time,"sleep"), patch.object(collector.subprocess,"run",side_effect=process):
            state=collector.collect_one(self.plan,self.root,self.row,self.root/"attempt")
        self.assertEqual(state["status"],"failed")
        self.assertEqual((self.root/"attempt/client.stdout").read_bytes(),b"partial raw stdout")
        self.assertEqual(state["files"]["client.stderr"],verifier.sha(self.root/"attempt/client.stderr"))
        self.assertIn("client_argv",state)
    def test_nonzero_process_retained(self): self.run_failure(False)
    def test_timeout_retained(self): self.run_failure(True)
    def test_late_watcher_failure_retained(self):
        row=dict(self.row,mode="watch_active")
        class Watcher:
            bytes=10; lines=1; error=None
            def __init__(obj,*args): pass
            def settle(obj): pass
            def close(obj): obj.error="late synthetic read failure"; obj.bytes=20
        def process(*args,**kwargs):
            kwargs["stdout"].write(b"{}")
            return subprocess.CompletedProcess([],0)
        with patch.object(collector,"Server",side_effect=self.fake_server), patch.object(collector,"Client",side_effect=self.fake_client), patch.object(collector,"Watcher",Watcher), patch.object(collector.time,"sleep"), patch.object(collector.subprocess,"run",side_effect=process):
            state=collector.collect_one(self.plan,self.root,row,self.root/"attempt")
        self.assertEqual(state["status"],"failed")
        self.assertEqual(state["watcher"]["bytes"],20)
        self.assertIn("late synthetic",state["failure"]["message"])
    def test_successful_process_invalid_metadata_retained(self):
        def process(*args,**kwargs):
            kwargs["stdout"].write(b'{"measurement_mode":"full"}')
            with (self.root/"attempt/server.stderr").open("ab") as out: out.write(event("check","ok",1).encode())
            return subprocess.CompletedProcess([],0)
        with patch.object(collector,"Server",side_effect=self.fake_server), patch.object(collector,"Client",side_effect=self.fake_client), patch.object(collector.time,"sleep"), patch.object(collector.subprocess,"run",side_effect=process), patch.object(verifier,"verify_attempt",side_effect=ValueError("client mode/seed")):
            state=collector.collect_one(self.plan,self.root,self.row,self.root/"attempt")
        self.assertEqual(state["client_returncode"],0)
        self.assertEqual(state["status"],"failed")
        self.assertEqual(state["failure"]["message"],"validation: client mode/seed")
        self.assertEqual((self.root/"attempt/client.stdout").read_bytes(),b'{"measurement_mode":"full"}')
    def test_duplicate_grid(self):
        plan={"schema":"corrected-profile-v1","scenarios":[{"name":"a"},{"name":"b"}]}; p=self.root/"plan.json"; p.write_text("{}")
        (self.root/"run.json").write_text(json.dumps({"schema":"corrected-profile-v1","plan_sha256":verifier.sha(p),"status":"collected","attempts":[{"name":"a","attempt":1,"status":"collected"}]*2}))
        with patch.object(verifier,"validate_plan",return_value=plan):
            with self.assertRaisesRegex(ValueError,"attempt grid"): verifier.verify_frozen(self.root,p)
    def test_validation_failure_is_durable(self):
        plan_path=self.root/"plan.json"; plan_path.write_text("{}")
        plan=dict(self.plan,out=str(self.root/"run"),scenarios=[self.row])
        with patch.object(collector,"check_plan",return_value=(plan,self.root)), patch.object(collector,"collect_one",return_value={"status":"collected"}), patch.object(verifier,"verify_frozen",side_effect=ValueError("synthetic invalid metadata")):
            with self.assertRaisesRegex(ValueError,"invalid metadata"): collector.collect(plan_path)
        result=json.loads((self.root/"run/run.json").read_text())
        self.assertEqual(result["status"],"failed")
        self.assertEqual(result["validation_failure"]["message"],"synthetic invalid metadata")
        self.assertEqual(len(result["attempts"]),1)
    def test_independent_oracle(self):
        for n,keys,pct,expected in ((5000,2048,50,2503),(5000,2048,95,4731),(200000,10000,10,19976)):
            result=collector.expected_work(n,keys,pct,20261109)
            self.assertEqual(result["get"],expected)
            self.assertEqual(result["key_verb_multiset"],verifier.independent_oracle(n,keys,pct,20261109))


if __name__ == "__main__": unittest.main()
