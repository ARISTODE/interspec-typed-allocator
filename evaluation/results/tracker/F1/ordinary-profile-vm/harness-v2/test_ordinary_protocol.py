"""Synthetic-only control/recording checks. No applications are launched."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json
import tempfile
import unittest
import run_ordinary_profile as runner
import verify_ordinary_profile as verifier

class Controls(unittest.TestCase):
    def test_optimized_environment_refused_before_inputs(self):
        with patch.dict(runner.os.environ,{"PYTHONOPTIMIZE":"1"}):
            with self.assertRaisesRegex(ValueError,"optimized"):
                runner.prepare(SimpleNamespace(source=Path("."),work=Path("missing"),out=Path("missing")))
    def test_injection_environment_refused_before_inputs(self):
        with patch.dict(runner.os.environ,{"INTERSPEC_TEST_FAULT":"0"}):
            with self.assertRaisesRegex(ValueError,"unexpected INTERSPEC"):
                runner.prepare(SimpleNamespace(source=Path("."),work=Path("missing"),out=Path("missing")))
    def test_duplicate_json_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"data.json";p.write_text('{"a":1,"a":2}')
            with self.assertRaisesRegex(ValueError,"duplicate"):verifier.load(p)
    def test_nonfinite_json_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"data.json";p.write_text('{"a":NaN}')
            with self.assertRaisesRegex(ValueError,"nonfinite"):verifier.load(p)
    def test_normal_gate_failure_retained(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);binary=root/"binary";binary.write_bytes(b"synthetic; never executed")
            deployment=SimpleNamespace(Client=object)
            common=SimpleNamespace(Server=lambda *args,**kwargs: (_ for _ in ()).throw(RuntimeError("synthetic startup failure")))
            state=runner.normal_gate(binary,root/"attempt",deployment,common,False)
            self.assertEqual(state["status"],"failed")
            self.assertEqual(state["full_50_case_gate_status"],"not_run")
            self.assertFalse(state["security_validation"])
            self.assertIn("synthetic startup failure",json.loads((root/"attempt/gate.json").read_text())["failure"]["message"])
            self.assertIs(deployment.Client,object)
            with self.assertRaises(FileExistsError):runner.normal_gate(binary,root/"attempt",deployment,common,False)
    def test_normal_shutdown_contract(self):
        for value in (0,-15):
            self.assertTrue(runner.valid_normal_stop(value));self.assertTrue(verifier.valid_normal_stop(value))
        for value in (1,-9,False,True,0.0,"0",None):
            self.assertFalse(runner.valid_normal_stop(value));self.assertFalse(verifier.valid_normal_stop(value))
    def test_completed_checks_recorded_before_shutdown(self):
        for code in (0,-15,1,-9):
            with tempfile.TemporaryDirectory() as d:
                root=Path(d);binary=root/"binary";binary.write_bytes(b"synthetic; never executed")
                class FakeServer:
                    def __init__(self,binary,directory,name,**kwargs):
                        self.args=[];self.proc=SimpleNamespace(returncode=code)
                        self.logpath=directory/"normal.stderr";self.logpath.write_bytes(b"")
                        (directory/"normal.stdout").write_bytes(b"")
                    def __enter__(self):return self
                    def __exit__(self,*args):return False
                deployment=SimpleNamespace(Client=object,normal=lambda *args:runner.NORMAL_CHECKS.copy())
                state=runner.normal_gate(binary,root/"attempt",deployment,SimpleNamespace(Server=FakeServer),False)
                self.assertTrue(state["normal_function_completed"])
                self.assertEqual(state["checks_passed"],16)
                self.assertEqual(state["status"],"passed" if code in (0,-15) else "failed")
    def test_protocol_inventory(self):
        self.assertEqual(runner.NORMAL_CHECKS,verifier.CHECKS)
        self.assertEqual(len(verifier.CHECKS),16)

if __name__=="__main__":unittest.main()
