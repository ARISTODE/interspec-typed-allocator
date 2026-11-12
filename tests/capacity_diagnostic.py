#!/usr/bin/env python3
"""Lifecycle/unit tests; all data synthetic or explicitly excluded smoke."""
from collections import Counter
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import capacity_diagnostic as c
from evaluation_checkpoint import Ledger

class Diagnostic(unittest.TestCase):
    def test_schedule(self):
        blocks = c.schedule()
        self.assertEqual(blocks, c.schedule()); self.assertEqual(len(blocks), 8)
        self.assertEqual(len({b['workload_seed'] for b in blocks}), 8)
        for scenario in ('balanced_8c', 'read_heavy_1k'):
            rows = [b['order'] for b in blocks if b['scenario']['name'] == scenario]
            self.assertEqual(len(rows), 4)
            self.assertEqual(set(Counter((label, pos) for row in rows for pos, label in enumerate(row)).values()), {1})
            self.assertEqual(len(Counter(pair for row in rows for pair in zip(row, row[1:]))), 12)
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); work = self.base / 'work'; (work / 'bin').mkdir(parents=True)
        server = work / 'bin/memcached-rlbox-only'; server.write_bytes(b'server')
        (work / 'build-manifest.json').write_text('{}')
        correctness = self.base / 'correctness.json'; correctness.write_text(json.dumps({'passed': 50, 'total': 50, 'binary_sha256': {server.name: c.sha(server)}}))
        client = self.base / 'client'; client.write_bytes(b'client')
        self.root = self.base / 'state'; c.initialize(self.root, work, correctness, client, True)
    def test_frozen_counts_and_args(self):
        plan, state = c.verify(self.root)
        self.assertEqual(plan['operations'], 20000)
        block = plan['blocks'][0]
        a = c.command(self.root, plan, block, 'count4-A', self.base/'out')
        b = c.command(self.root, plan, block, 'count4-B', self.base/'out')
        self.assertEqual(a, b); self.assertIn('--capacity-diagnostic', a)
        (self.root/'bin/client').write_bytes(b'changed')
        with self.assertRaises(ValueError): c.verify(self.root)
    def test_uncertain_no_retry_and_exclusion(self):
        with self.assertRaises(RuntimeError): c.execute(self.root, inject='before_launch')
        with self.assertRaises(ValueError): c.execute(self.root)
        _, state = c.verify(self.root); ident = next(iter(state['operations']))
        with self.assertRaises(ValueError): c.reconcile(self.root, ident, 'test', False)
        c.reconcile(self.root, ident, 'test', True)
        _, state = c.verify(self.root)
        self.assertEqual(state['operations'][ident]['status'], 'excluded')
        with self.assertRaises(ValueError): c.reconcile(self.root, ident, 'retry prohibited', True)
    def test_archive_roundtrip_and_tampering(self):
        archive = self.base/'state.tgz'
        result = c.checkpoint.export(self.root, archive, verifier=c.verify)
        restored = self.base/'restored'
        c.checkpoint.restore(archive, restored, result['sha256'], verifier=c.verify)
        self.assertEqual(c.verify(self.root)[0], c.verify(restored)[0])
        with self.assertRaises(ValueError): c.checkpoint.restore(archive, self.base/'bad', '0'*64, verifier=c.verify)
    def test_explicit_partial_block_exclusion(self):
        block = c.schedule()[0]['id']
        c.exclude_block(self.root, block, 'interrupted between runs', True)
        _, state = c.verify(self.root)
        self.assertEqual(json.loads(next(iter(state['operations'].values()))['details'])['type'], 'block_exclusion')
    def test_no_multi_block_invocation(self):
        with self.assertRaises(ValueError): c.execute(self.root, 2)

if __name__ == '__main__': unittest.main()
