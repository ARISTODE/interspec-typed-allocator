#!/usr/bin/env python3
"""Standalone: python3 tests/evaluation_checkpoint.py (POSIX, standard library)."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1] / 'tools/evaluation_checkpoint.py'
SPEC = importlib.util.spec_from_file_location('checkpoint_tool', TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ledger = MODULE.Ledger(self.root)
        self.ledger.init(b'{"frozen":true}')

    def run_cli(self, *args, crash=None):
        env = os.environ.copy()
        env.pop('EVALUATION_CHECKPOINT_CRASH', None)
        if crash:
            env['EVALUATION_CHECKPOINT_CRASH'] = crash
        return subprocess.run([sys.executable, str(TOOL), str(self.root), *args],
                              env=env, capture_output=True)

    def test_duplicate_init_and_id_blocked(self):
        with self.assertRaises(ValueError):
            self.ledger.init(b'other')
        self.ledger.start('one', 'run', 'session=1')
        with self.assertRaises(ValueError):
            self.ledger.start('one', 'run', 'session=1')
        with self.assertRaises(ValueError):
            self.ledger.start('two', 'run', 'session=1')

    def test_resume_requires_reconciliation(self):
        self.ledger.start('one', 'run', 'session=1')
        restarted = MODULE.Ledger(self.root)
        self.assertEqual(restarted.status()['operations']['one']['status'], 'uncertain')
        restarted.resolve('one', 'excluded', b'Interrupted; exit/result unknown', True)
        restarted.start('two', 'run', 'new session; old attempt retained')
        self.assertEqual(len(restarted.status()['operations']), 2)

    def test_completion_terminal(self):
        self.ledger.start('one', 'run', 'session=1')
        self.ledger.resolve('one', 'completed', b'validated full run output')
        with self.assertRaises(ValueError):
            self.ledger.resolve('one', 'excluded', b'change history', True)

    def test_upload_roundtrip_and_no_retry(self):
        self.ledger.start('upload1', 'upload', 'immutable remote key', b'archive')
        with self.assertRaises(ValueError):
            self.ledger.resolve('upload1', 'completed', b'receipt', downloaded=b'wrong')
        with self.assertRaises(ValueError):
            self.ledger.start('upload2', 'upload', 'same remote key', b'archive')
        self.ledger.resolve('upload1', 'completed', b'remote key + retrieval evidence',
                            True, b'archive')
        self.assertEqual(self.ledger.status()['operations']['upload1']['roundtrip_sha256'],
                         MODULE.digest(b'archive'))

    def test_not_executed_requires_explicit_evidence(self):
        self.ledger.start('one', 'run', 'session=1')
        with self.assertRaises(ValueError):
            self.ledger.resolve('one', 'not_executed', b'confirmed absent')
        with self.assertRaises(ValueError):
            self.ledger.resolve('one', 'not_executed', b' ', True)
        self.ledger.resolve('one', 'not_executed', b'authoritative job registry checked', True)

    def test_ledger_corruption_blocks(self):
        envelope = json.loads(self.ledger.path.read_text())
        envelope['state']['version'] = 2
        self.ledger.path.write_text(json.dumps(envelope))
        with self.assertRaises(ValueError):
            self.ledger.status()
        self.assertNotEqual(self.run_cli('status').returncode, 0)

    def test_missing_and_corrupt_artifact_blocks(self):
        sha = self.ledger.status()['plan_sha256']
        path = self.root / (sha + '.blob')
        path.write_bytes(b'corrupt')
        with self.assertRaises(ValueError):
            self.ledger.status()
        path.unlink()
        with self.assertRaises(FileNotFoundError):
            self.ledger.status()

    def test_sigkill_intent_atomicity(self):
        for point in ('before_file_fsync', 'before_replace', 'after_replace', 'after_directory_fsync'):
            with self.subTest(point=point):
                result = self.run_cli('start', point, '--kind', 'run', '--details', 'crash test', crash=point)
                self.assertEqual(result.returncode, -signal.SIGKILL)
                operations = self.ledger.status()['operations']
                if point in ('before_file_fsync', 'before_replace'):
                    self.assertNotIn(point, operations)
                else:
                    self.assertEqual(operations[point]['status'], 'uncertain')
                    self.ledger.resolve(point, 'excluded', b'fault injection interrupted', True)

    def test_sigkill_completion_atomicity(self):
        evidence = self.root / 'evidence.txt'
        evidence.write_bytes(b'validated result')
        # Prestore so crash hooks target ledger replacement rather than blob creation.
        self.ledger.blob(evidence.read_bytes())
        for point in ('before_file_fsync', 'before_replace', 'after_replace', 'after_directory_fsync'):
            with self.subTest(point=point):
                self.ledger.start(point, 'run', 'crash completion')
                result = self.run_cli('complete', point, '--evidence', str(evidence), crash=point)
                self.assertEqual(result.returncode, -signal.SIGKILL)
                status = self.ledger.status()['operations'][point]['status']
                self.assertEqual(status, 'uncertain' if point.startswith('before') else 'completed')
                if status == 'uncertain':
                    self.ledger.resolve(point, 'excluded', b'fault injection interrupted', True)

    def test_external_effect_then_kill_remains_uncertain(self):
        self.ledger.start('upload', 'upload', 'test fake external effect', b'archive')
        effect = self.root / 'external-effect'
        subprocess.run([sys.executable, '-c',
            'import os,signal,pathlib; pathlib.Path(' + repr(str(effect)) +
            ').write_bytes(b"archive"); os.kill(os.getpid(),signal.SIGKILL)'])
        self.assertTrue(effect.exists())
        self.assertEqual(self.ledger.status()['operations']['upload']['status'], 'uncertain')
        self.ledger.resolve('upload', 'completed', b'manually checked destination', True, effect.read_bytes())


if __name__ == '__main__':
    unittest.main(verbosity=2)
