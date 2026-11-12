#!/usr/bin/env python3
"""POSIX local checkpoint ledger. Never executes, retries, or uploads experiments."""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import tempfile


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def fault(point):
    # Test-only crash injection; not a power-loss simulator.
    if os.environ.get('EVALUATION_CHECKPOINT_CRASH') == point:
        os.kill(os.getpid(), signal.SIGKILL)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_write(path, data):
    fd, name = tempfile.mkstemp(prefix='.checkpoint-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            fault('before_file_fsync')
            os.fsync(stream.fileno())
        fault('before_replace')
        os.replace(name, path)
        fault('after_replace')
        sync_directory(path.parent)
        fault('after_directory_fsync')
    finally:
        if os.path.exists(name):
            os.unlink(name)


class Ledger:
    """One local writer at a time; reads verify all referenced blobs.

    Start must return successfully before any external action. A persisted intent
    without a completion is uncertain, including if the action never started.
    """
    def __init__(self, root):
        self.root = Path(root)
        if not self.root.is_dir():
            raise ValueError('Create the ledger directory first on a durable local filesystem')
        self.path = self.root / 'ledger.json'

    @contextlib.contextmanager
    def locked(self):
        with (self.root / '.lock').open('a+b') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def read(self):
        envelope = json.loads(self.path.read_bytes())
        state = envelope['state']
        if digest(encoded(state)) != envelope['sha256']:
            raise ValueError('Ledger integrity mismatch; do not resume')
        if state['version'] != 1:
            raise ValueError('Unsupported ledger version')
        self.check_blob(state['plan_sha256'])
        for entry in state['operations'].values():
            if entry.get('evidence_sha256'):
                self.check_blob(entry['evidence_sha256'])
            if entry.get('expected_sha256'):
                self.check_blob(entry['expected_sha256'])
        return state

    def save(self, state):
        atomic_write(self.path, encoded({'state': state, 'sha256': digest(encoded(state))}) + b'\n')

    def blob(self, data):
        sha = digest(data)
        path = self.root / (sha + '.blob')
        if path.exists():
            self.check_blob(sha)
        else:
            atomic_write(path, data)
        return sha

    def check_blob(self, sha):
        if len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
            raise ValueError('Invalid blob digest')
        if digest((self.root / (sha + '.blob')).read_bytes()) != sha:
            raise ValueError('Artifact integrity mismatch; do not resume')

    def init(self, plan):
        with self.locked():
            if self.path.exists():
                raise ValueError('Ledger already exists')
            self.save({'version': 1, 'plan_sha256': self.blob(plan), 'operations': {}})

    def start(self, op_id, kind, details, expected=None):
        with self.locked():
            state = self.read()
            if not op_id or kind not in ('run', 'upload'):
                raise ValueError('Nonempty ID and run/upload kind required')
            if op_id in state['operations']:
                raise ValueError('ID already used; never automatically retry')
            # Serial execution and reconciliation are deliberate safety gates.
            if any(x['status'] == 'uncertain' for x in state['operations'].values()):
                raise ValueError('Reconcile outstanding uncertain action first')
            if kind == 'upload':
                if expected is None:
                    raise ValueError('Upload requires a local artifact')
                sha = self.blob(expected)
            else:
                if expected is not None:
                    raise ValueError('Run cannot have upload artifact')
                sha = None
            state['operations'][op_id] = {'kind': kind, 'status': 'uncertain',
                'details': details, 'expected_sha256': sha, 'history': ['intent persisted']}
            self.save(state)

    def resolve(self, op_id, outcome, evidence, reconciliation=False, downloaded=None):
        with self.locked():
            state = self.read()
            entry = state['operations'][op_id]
            if entry['status'] != 'uncertain':
                raise ValueError('Operation is already terminal')
            if outcome not in ('completed', 'excluded', 'not_executed'):
                raise ValueError('Invalid outcome')
            if not reconciliation and outcome != 'completed':
                raise ValueError('Explicit reconciliation required')
            if not evidence.strip():
                raise ValueError('Evidence is required')
            if entry['kind'] == 'upload' and outcome == 'completed':
                if downloaded is None or digest(downloaded) != entry['expected_sha256']:
                    raise ValueError('Download round-trip hash does not match upload artifact')
            if entry['kind'] != 'upload' and downloaded is not None:
                raise ValueError('Downloaded artifact is only valid for an upload')
            entry['evidence_sha256'] = self.blob(evidence)
            entry['status'] = outcome
            entry['history'].append('explicit reconciliation' if reconciliation else 'completion recorded')
            if entry['kind'] == 'upload' and outcome == 'completed':
                entry['roundtrip_sha256'] = digest(downloaded)
            self.save(state)

    def status(self):
        with self.locked():
            return self.read()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory')
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    init.add_argument('--plan', required=True, type=Path)
    sub.add_parser('status')
    start = sub.add_parser('start')
    start.add_argument('id')
    start.add_argument('--kind', required=True, choices=['run', 'upload'])
    start.add_argument('--details', required=True, help='Frozen run identity or upload destination/key')
    start.add_argument('--artifact', type=Path)
    for command in ('complete', 'reconcile'):
        done = sub.add_parser(command)
        done.add_argument('id')
        done.add_argument('--evidence', required=True, type=Path)
        done.add_argument('--downloaded', type=Path)
        if command == 'reconcile':
            done.add_argument('--outcome', required=True, choices=['completed', 'excluded', 'not_executed'])
    args = parser.parse_args()
    ledger = Ledger(args.directory)
    try:
        if args.command == 'init':
            ledger.init(args.plan.read_bytes())
        elif args.command == 'start':
            ledger.start(args.id, args.kind, args.details,
                         args.artifact.read_bytes() if args.artifact else None)
        elif args.command in ('complete', 'reconcile'):
            ledger.resolve(args.id, getattr(args, 'outcome', 'completed'),
                args.evidence.read_bytes(), args.command == 'reconcile',
                args.downloaded.read_bytes() if args.downloaded else None)
        print(json.dumps(ledger.status(), indent=2, sort_keys=True))
    except (ValueError, KeyError, OSError) as error:
        parser.exit(1, 'Checkpoint blocked: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
