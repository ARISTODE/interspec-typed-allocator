#!/usr/bin/env python3
"""Compile-time anti-elision and runtime functional-control regression tests."""
import csv
import io
import json
import sys
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RuntimeMicrobenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.binary = Path(cls.temp.name) / 'runtime'
        subprocess.run(['g++', '-std=c++17', '-O2', '-pthread', '-I', str(ROOT / 'include'),
                        str(ROOT / 'evaluation/runtime_bench.cpp'), '-o', str(cls.binary)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_exact_grid_and_controls(self):
        # Exercise incomplete and multiple full 1024-operation control periods.
        for n in (1023, 2049):
            p = subprocess.run([str(self.binary)], env=dict(os.environ, INTERSPEC_BENCH_ITERATIONS=str(n)),
                               text=True, capture_output=True, check=True)
            self.assertEqual(p.stderr, '')
            rows = list(csv.DictReader(io.StringIO(p.stdout)))
            self.assertEqual(len(rows), 39)
            self.assertEqual(len({(r['metric'], r['population'], r['threads']) for r in rows}), 39)
            for r in rows:
                count = int(r['operations'])
                self.assertGreater(int(r['total_ns']), 0)
                self.assertAlmostEqual(float(r['ns_per_op']), int(r['total_ns']) / count, places=8)

    @unittest.skipUnless(platform.machine() == 'x86_64' and shutil.which('objdump'), 'requires x86-64 objdump')
    def test_primitive_machine_instructions_retained(self):
        text = subprocess.check_output(['objdump', '-Cd', str(self.binary)], text=True)
        for name in ('primitive_bounds_check', 'primitive_type_compare'):
            match = re.search(r'^([0-9a-f]+) <[^\n]*' + name + r'[^\n]*>:\n(.*?)(?=\n\n)', text, re.M | re.S)
            self.assertIsNotNone(match)
            body = match[2]
            self.assertRegex(body, r'\bcmp\b')
            self.assertRegex(body, r'\bset(?:ae|be|e)\b')
            if name == 'primitive_bounds_check':
                self.assertRegex(body, r'\bsub\b')
            # A timed call plus independent untimed functional controls remain.
            self.assertGreaterEqual(len(re.findall(r'call[^\n]*' + name, text)), 3)

    def test_driver_evidence_and_corruption_rejection(self):
        sys.path.insert(0, str(ROOT / 'tools'))
        from verify_runtime_microbench import verify
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'results'
            cmd = [sys.executable, str(ROOT / 'tools/run_runtime_microbench.py'),
                   '--out', str(out), '--binary', str(self.binary),
                   '--repetitions', '3', '--iterations', '2049']
            subprocess.run(cmd, check=True, capture_output=True)
            self.assertEqual(verify(out)['samples'], 117)
            table = (out / 'MICROBENCH_TABLE.md').read_text()
            self.assertIn('| bounds_check | 2 |', table)
            self.assertIn('| allocate_from_site | 16384 |', table)
            self.assertFalse(json.loads((out / 'environment.json').read_text())['publication_ready'])
            self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
            p = out / 'summary.json'
            original = p.read_text()
            broken = json.loads(original)
            broken[0]['ns_per_op_median'] += 1
            p.write_text(json.dumps(broken))
            with self.assertRaisesRegex(ValueError, 'summary arithmetic'):
                verify(out)
            p.write_text(original)
            with (out / '0.stderr').open('w') as stream:
                stream.write('invalid control')
            with self.assertRaisesRegex(ValueError, 'process stderr'):
                verify(out)

    def test_negative_control_rejects_constant_true_bounds(self):
        source = (ROOT / 'evaluation/runtime_bench.cpp').read_text()
        self.assertIn('return bytes <= remaining;', source)
        source = source.replace('return bytes <= remaining;', 'return true;')
        path = Path(self.temp.name) / 'mutated.cpp'
        path.write_text(source)
        binary = Path(self.temp.name) / 'mutated'
        subprocess.run(['g++', '-std=c++17', '-O2', '-pthread', '-I', str(ROOT / 'include'),
                        str(path), '-o', str(binary)], check=True)
        result = subprocess.run([str(binary)], capture_output=True)
        self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()
