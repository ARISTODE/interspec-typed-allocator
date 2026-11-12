#!/usr/bin/env python3
"""Deterministic exec-transition regressions; no server or diagnostic runs."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import benchmark_memcached as b

class AffinityObservation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.proc = self.root/'proc'; self.proc.mkdir()
        self.client = self.root/'client'; self.client.write_text('client')
        self.guard = self.root/'guard'; self.guard.write_text('guard')
        self.record = {'Pid': '123', 'PPid': '99', 'NSpid': '123 7', 'Cpus_allowed_list': '0-8'}
        self.status('4-8'); self.stat('100'); (self.proc/'exe').symlink_to(self.client)
    def status(self, cpus, pid='123', ppid='99'):
        (self.proc/'status').write_text(f'Pid:\t{pid}\nPPid:\t{ppid}\nNSpid:\t{pid} 7\nCpus_allowed_list:\t{cpus}\n')
    def stat(self, start):
        (self.proc/'stat').write_text('123 (client with spaces) ' + ' '.join(['S'] + ['0']*18 + [start]))
    def observe(self):
        with patch.object(b, 'process_status', return_value=(self.record, self.proc)):
            return b.observed_client_affinity(7, self.client)
    def test_stale_pre_exec_snapshot_reproduces_old_bug_and_is_discarded(self):
        # Resolver read guard status (0-8); taskset then set 4-8 and exec'd client.
        # The old status-before-exe code would falsely attribute 0-8 to client.
        self.assertEqual((self.proc/'exe').resolve(), self.client.resolve())
        self.assertEqual(self.record['Cpus_allowed_list'], '0-8')
        observed = self.observe()
        self.assertEqual(observed['cpus'], '4-8')
        self.assertEqual(observed['starttime_ticks'], '100')
    def test_guard_not_yet_execed_is_not_an_observation(self):
        (self.proc/'exe').unlink(); (self.proc/'exe').symlink_to(self.guard)
        self.assertIsNone(self.observe())
    def test_executable_change_during_status_read_is_rejected(self):
        original = b.read_process_status
        def transition(path):
            result = original(path)
            (self.proc/'exe').unlink(); (self.proc/'exe').symlink_to(self.guard)
            return result
        with patch.object(b, 'read_process_status', side_effect=transition):
            self.assertIsNone(self.observe())
    def test_process_starttime_change_is_rejected(self):
        with patch.object(b, 'process_starttime', side_effect=['100', '101']):
            self.assertIsNone(self.observe())
    def test_wrong_parent_or_pid_is_rejected(self):
        self.status('4-8', ppid='98'); self.assertIsNone(self.observe())
        self.status('4-8', pid='124'); self.assertIsNone(self.observe())
    def test_post_exec_wrong_mask_is_retained_not_hidden(self):
        self.status('0-8'); observed = self.observe()
        self.assertEqual(observed['cpus'], '0-8')
        with self.assertRaisesRegex(AssertionError, 'Observed client affinity mismatch'):
            b.validate_client_affinity(observed['cpus'], '4-8')
    def test_process_exit_during_bracket_is_not_observation(self):
        (self.proc/'stat').unlink(); self.assertIsNone(self.observe())

if __name__ == '__main__': unittest.main()
