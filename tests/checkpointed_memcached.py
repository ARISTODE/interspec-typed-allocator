#!/usr/bin/env python3
"""Unit fixtures only; these do not claim real-server benchmark evidence."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import run_checkpointed_memcached as r
from evaluation_checkpoint import Ledger, encoded


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'state'
        binary = self.base / 'binary'; binary.write_bytes(b'fixture only')
        self.spec = self.base / 'spec.json'
        one = dict(id='one', block='a', clients=1, pipeline=1, value_bytes=64, keys=1,
                   operations=10, warmup_operations=2, expected_get=10, expected_set=0,
                   warmup_expected_get=2, warmup_expected_set=0, seed=42, get_percent=100)
        two = dict(one, id='two', block='a')
        three = dict(one, id='three', block='b')
        self.spec.write_text(json.dumps(dict(client=str(binary), server=str(binary), schedule=[one,two,three])))
        r.initialize(self.root, self.spec)

    def completed(self, identity='one', block='a'):
        op = 'fixture-' + identity
        directory = self.root / 'attempts' / op
        directory.mkdir(parents=True)
        def counts(n):
            return dict(client=dict(errors=0,operations=n,p99_us=None,latency_sample_count=0), counters=dict(cmd_get=n,cmd_set=0,get_hits=n,get_misses=0,log_worker_dropped=0,log_watcher_skipped=0,lru_bumps_dropped=0))
        r.write(directory / 'result.json', dict(valid=True, attempt=op, scheduled_id=identity, warmup=counts(2), measured=counts(10)))
        ledger = Ledger(self.root)
        ledger.start(op, 'run', json.dumps(dict(scheduled_id=identity, block=block)))
        ledger.resolve(op, 'completed', encoded(dict(attempt=op, scheduled_id=identity, files={str((directory/'result.json').relative_to(self.root)):r.sha(directory/'result.json')})))
        return directory

    def test_restore_and_duplicate_safe_resume(self):
        for identity, block in [('one','a'), ('two','a'), ('three','b')]:
            self.completed(identity, block)
        archive = self.base / 'snapshot.tar.gz'
        r.export(self.root, archive)
        restored = self.base / 'restored'
        r.restore(archive, restored, r.sha(archive))
        with patch.object(r, 'server_process', side_effect=AssertionError('must not launch')):
            self.assertEqual(r.execute(restored)['executed'], 0)
        self.assertEqual(len(Ledger(restored).status()['operations']), 3)

    def test_corrupt_output(self):
        directory = self.completed()
        (directory / 'result.json').write_text('{}')
        with self.assertRaises(ValueError): r.execute(self.root)

    def test_corrupt_plan_and_binary(self):
        (self.root / 'bin/client').write_bytes(b'changed')
        with self.assertRaises(ValueError): r.verify(self.root)
        (self.root / 'plan.json').write_text('{}')
        with self.assertRaises((ValueError, KeyError)): r.verify(self.root)

    def test_intent_injection_excludes_whole_block(self):
        with self.assertRaises(RuntimeError): r.execute(self.root, failure='before_launch')
        state = Ledger(self.root).status()
        op = next(iter(state['operations']))
        with self.assertRaises(ValueError): r.execute(self.root)
        Ledger(self.root).resolve(op, 'excluded', b'Operator confirmed no live process; exclude entire block a', reconciliation=True)
        with self.assertRaises(RuntimeError): r.execute(self.root, failure='before_launch')
        details = [json.loads(e['details'])['scheduled_id'] for e in Ledger(self.root).status()['operations'].values()]
        self.assertEqual(sorted(details), ['one', 'three'])

    def test_duplicate_and_hash_failure_restore(self):
        self.completed()
        Ledger(self.root).start('duplicate', 'run', json.dumps(dict(scheduled_id='one',block='a')))
        with self.assertRaises(ValueError): r.verify(self.root)
        archive = self.base / 'bad.tar.gz'
        with tarfile.open(archive,'w:gz') as tar:
            info = tarfile.TarInfo('../escape'); info.size=1
            tar.addfile(info,io.BytesIO(b'x'))
        with self.assertRaises(ValueError): r.restore(archive,self.base/'fresh',r.sha(archive))
        self.assertFalse((self.base/'fresh').exists())
        with self.assertRaises(ValueError): r.restore(archive,self.base/'fresh','0'*64)

    def test_during_client_cleans_direct_process(self):
        # Real subprocess cleanup test, not a memcached/server benchmark.
        binary = self.root / 'bin/client'
        binary.write_text('#!/usr/bin/env python3\nimport time\ntime.sleep(60)\n')
        binary.chmod(0o700)
        directory = self.base / 'client-test'; directory.mkdir()
        run = json.loads(self.spec.read_text())['schedule'][0]
        class StatsFixture:
            def __init__(self, port): pass
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def stats(self): return {}
        with patch.object(r, 'Client', StatsFixture):
            with self.assertRaises(RuntimeError):
                r.measure(self.root, directory, run, 1, False, 'during_client')
        identity = json.loads((directory/'measured-process.json').read_bytes())
        self.assertFalse(Path('/proc/%d' % identity['pid']).exists())
        self.assertTrue((directory/'measured.stdout').exists())

    def test_after_result_injection_is_uncertain(self):
        @contextlib.contextmanager
        def server(binary, directory, extra):
            (directory/'server.stderr').write_bytes(b'')
            yield 1
        class ClientFixture:
            def __init__(self, port): pass
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def store(self,*args): return b'STORED\r\n'
        with patch.object(r,'server_process',server), patch.object(r,'Client',ClientFixture), patch.object(r,'measure',return_value={'fixture': True}):
            with self.assertRaises(RuntimeError): r.execute(self.root,failure='after_result_saved')
        self.assertEqual(next(iter(Ledger(self.root).status()['operations'].values()))['status'],'uncertain')
        self.assertEqual(len(list(self.root.glob('attempts/*/result.json'))),1)
        with self.assertRaises(ValueError): r.execute(self.root)


if __name__ == '__main__': unittest.main()
