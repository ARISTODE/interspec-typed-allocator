#!/usr/bin/env python3
"""Fast lifecycle tests with fake server bytes; never runs a benchmark."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import matrix_checkpoint as m
from evaluation_checkpoint import Ledger, encoded

class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); work = self.base / 'work'; (work / 'bin').mkdir(parents=True)
        hashes = {}
        for v in m.VARIANTS:
            p = work / 'bin' / ('memcached-' + v); p.write_bytes(v.encode()); hashes[p.name] = m.sha(p)
        (work / 'build-manifest.json').write_text('{}')
        gate = self.base / 'correctness.json'; gate.write_text(json.dumps({'passed':50,'total':50,'binary_sha256':hashes}))
        client = self.base / 'client'; client.write_bytes(b'client')
        self.root = self.base / 'state'
        m.initialize(self.root, work, gate, client, ['--functional-rehearsal'], True)
    def complete(self, collection, scenario):
        directory, launch = collection.begin(scenario); self.assertTrue(launch)
        for name in ('summary.json','samples.csv','environment.json'): (directory / name).write_text('{}')
        Ledger(self.root).resolve(collection.ident, 'completed', encoded({'attempt':collection.ident,'scenario':scenario,'files':m.inventory(directory)}))
        return directory
    def test_skip_and_corruption(self):
        c = m.Collection(self.root, 6, None); directory = self.complete(c, 'balanced_1c')
        c = m.Collection(self.root, 6, None); self.assertFalse(c.begin('balanced_1c')[1])
        (directory / 'samples.csv').write_text('corrupt')
        with self.assertRaises(ValueError): m.verify(self.root)
    def test_uncertain_retry_retains_block(self):
        c = m.Collection(self.root, 6, None); directory, _ = c.begin('balanced_1c'); (directory/'partial').write_text('retain')
        with self.assertRaises(ValueError): m.Collection(self.root,6,None)
        m.reconcile(self.root,c.ident,'Interrupted test; processes absent',True,True)
        replacement = m.Collection(self.root,6,None); new, _ = replacement.begin('balanced_1c')
        self.assertNotEqual(directory,new); self.assertEqual((directory/'partial').read_text(),'retain')
        with self.assertRaises(ValueError): m.reconcile(self.root,replacement.ident,'second',True,True)
    def test_exclude_not_complete(self):
        c=m.Collection(self.root,6,None); c.begin('watch_light'); m.reconcile(self.root,c.ident,'interruption',False,True)
        c=m.Collection(self.root,6,None); self.assertEqual(c.begin('watch_light'),(None,False)); self.assertEqual(c.excluded,['watch_light'])
    def test_duplicate_block_rejected(self):
        self.complete(m.Collection(self.root,6,None),'balanced_1c')
        Ledger(self.root).start('duplicate', 'run', json.dumps({'scenario':'balanced_1c','epoch':0}))
        with self.assertRaises(ValueError): m.verify(self.root)
    def test_frozen_binary_mismatch(self):
        (self.root/'bin/client').write_bytes(b'changed')
        with self.assertRaises(ValueError): m.verify(self.root)
    def test_uncertain_export_requires_stopped_confirmation(self):
        m.Collection(self.root,6,None).begin('balanced_1c')
        with self.assertRaises(ValueError): m.export(self.root,self.base/'bad.tgz')
        self.assertFalse((self.base/'bad.tgz').exists())
    def test_config_mismatch(self):
        (self.root/'plan.json').write_text('{}')
        with self.assertRaises(ValueError): m.verify(self.root)
    def test_portable_roundtrip(self):
        self.complete(m.Collection(self.root,6,None),'balanced_1c')
        archive=self.base/'state.tgz'; result=m.export(self.root,archive); fresh=self.base/'fresh'
        m.restore(archive,fresh,result['sha256']); m.verify(fresh)
        self.assertFalse(m.Collection(fresh,6,None).begin('balanced_1c')[1])
    def test_no_failure_retry(self):
        c=m.Collection(self.root,6,None); d,_=c.begin('balanced_1c'); (d/'observed_failure.json').write_text('{}')
        with self.assertRaises(ValueError): m.reconcile(self.root,c.ident,'failure',True,True)

if __name__ == '__main__': unittest.main()
