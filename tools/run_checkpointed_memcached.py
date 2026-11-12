#!/usr/bin/env python3
"""Small real-server recovery smoke. Not a publication benchmark or uploader."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import pwd
import signal
import socket
import subprocess
import tarfile
import tempfile
import time
import uuid

from evaluation_checkpoint import Ledger, atomic_write, encoded, digest, sync_directory
from memcached_common import Client


def write(path, value):
    atomic_write(path, encoded(value) + b'\n')


def sha(path):
    return digest(path.read_bytes())


def inject(point, requested):
    if point == requested:
        raise RuntimeError('Injected interruption: ' + point)


def initialize(root, spec):
    if root.exists():
        raise ValueError('Initialization requires a fresh directory')
    plan = json.loads(spec.read_bytes())
    if not plan.get('schedule'):
        raise ValueError('Nonempty schedule required')
    identities = set()
    for run in plan['schedule']:
        identity = run['id']
        if not isinstance(identity, str) or not identity or identity in identities:
            raise ValueError('Unique nonempty scheduled identities required')
        identities.add(identity)
        if not isinstance(run['block'], str) or not run['block']:
            raise ValueError('Explicit block required')
        for key in ('clients', 'pipeline', 'value_bytes', 'keys', 'operations', 'warmup_operations'):
            if type(run[key]) is not int or run[key] <= 0:
                raise ValueError('Positive integer required: ' + key)
        for key in ('expected_get', 'expected_set', 'warmup_expected_get', 'warmup_expected_set', 'seed', 'get_percent'):
            if type(run[key]) is not int or run[key] < 0:
                raise ValueError('Nonnegative integer required: ' + key)
        if run['get_percent'] > 100 or run['expected_get'] + run['expected_set'] != run['operations'] or run['warmup_expected_get'] + run['warmup_expected_set'] != run['warmup_operations']:
            raise ValueError('Invalid exact operation counts')
    # Resolve source files before creating the destination.
    binaries = {name: Path(plan[name]).resolve().read_bytes() for name in ('client', 'server')}
    root.mkdir(parents=True)
    (root / 'bin').mkdir()
    for name, data in binaries.items():
        path = root / 'bin' / name
        atomic_write(path, data)
        path.chmod(0o700)
        plan[name] = 'bin/' + name
    plan.update(version=1, scope='nonpublication real-server recovery smoke',
                binary_sha256={name: digest(data) for name, data in binaries.items()},
                driver_sha256=sha(Path(__file__)), helper_sha256={name: sha(Path(__file__).parent / name) for name in ('evaluation_checkpoint.py', 'memcached_common.py')}, workload_mode='independent-v1', timing_mode='count-only')
    (root / 'toolchain').mkdir()
    for name in ('run_checkpointed_memcached.py', 'evaluation_checkpoint.py', 'memcached_common.py'):
        atomic_write(root / 'toolchain' / name, (Path(__file__).parent / name).read_bytes())
    write(root / 'plan.json', plan)
    Ledger(root).init((root / 'plan.json').read_bytes())
    return verify(root)


def verify(root, state=None):
    ledger = Ledger(root)
    state = ledger.status() if state is None else state
    plan = json.loads((root / 'plan.json').read_bytes())
    if sha(root / 'plan.json') != state['plan_sha256'] or plan['driver_sha256'] != sha(Path(__file__)):
        raise ValueError('Frozen plan/driver mismatch')
    for name in ('evaluation_checkpoint.py', 'memcached_common.py'):
        if sha(Path(__file__).parent / name) != plan['helper_sha256'][name]:
            raise ValueError('Frozen helper mismatch')
    for name in ('client', 'server'):
        if plan[name] != 'bin/' + name or (root / plan[name]).is_symlink() or sha(root / plan[name]) != plan['binary_sha256'][name]:
            raise ValueError('Frozen binary mismatch')
    for name, expected in dict(plan['helper_sha256'], **{'run_checkpointed_memcached.py': plan['driver_sha256']}).items():
        if sha(root / 'toolchain' / name) != expected:
            raise ValueError('Bundled toolchain mismatch')
    scheduled = {r['id']: r for r in plan['schedule']}
    seen = set()
    for op_id, entry in state['operations'].items():
        if entry['kind'] != 'run':
            continue
        details = json.loads(entry['details'])
        if details['scheduled_id'] not in scheduled or details['block'] != scheduled[details['scheduled_id']]['block']:
            raise ValueError('Unknown run identity/block')
        if details['scheduled_id'] in seen:
            raise ValueError('Duplicate scheduled identity')
        seen.add(details['scheduled_id'])
        if entry['status'] == 'completed':
            evidence = json.loads((root / (entry['evidence_sha256'] + '.blob')).read_bytes())
            if evidence['attempt'] != op_id or evidence['scheduled_id'] != details['scheduled_id']:
                raise ValueError('Completion identity mismatch')
            result_relative = 'attempts/' + op_id + '/result.json'
            if result_relative not in evidence['files']:
                raise ValueError('Completion lacks result digest')
            for relative, expected in evidence['files'].items():
                path = root / relative
                if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or sha(path) != expected:
                    raise ValueError('Run output mismatch')
            result = json.loads((root / 'attempts' / op_id / 'result.json').read_bytes())
            if result['scheduled_id'] != details['scheduled_id'] or result['attempt'] != op_id or result['valid'] is not True:
                raise ValueError('Invalid completed result')
            for label, warmup in [('warmup', True), ('measured', False)]:
                validate_counts(result[label]['client'], result[label]['counters'], scheduled[details['scheduled_id']], warmup)
    return plan, state


def child_setup():
    # Linux-specific recovery runner: direct child dies even if the driver is
    # SIGKILLed. Process groups are still cleaned on ordinary exceptions.
    import ctypes
    parent = os.getppid()
    if ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGKILL) != 0:
        raise OSError('PR_SET_PDEATHSIG failed')
    if os.getppid() != parent or parent == 1:
        os.kill(os.getpid(), signal.SIGKILL)


def record_process(directory, label, proc):
    write(directory / (label + '-process.json'), {
        'pid': proc.pid, 'process_group': proc.pid,
        'proc_stat': Path('/proc/%d/stat' % proc.pid).read_text(),
        'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'note': 'Audit only. Never kill a reused PID; verify boot ID and stat starttime first.'})


def stop(proc):
    if proc is None:
        return
    # Kill descendants even when the leader has exited.
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait()


@contextlib.contextmanager
def server_process(binary, directory, extra):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    proc = None
    with (directory / 'server.stdout').open('wb') as out, (directory / 'server.stderr').open('wb') as err:
        try:
            args = [str(binary), '-l', '127.0.0.1', '-p', str(port), '-U', '0', '-m', '64', '-t', '4', '-u', pwd.getpwuid(os.getuid()).pw_name] + extra
            env = {k: v for k, v in os.environ.items() if not k.startswith('INTERSPEC_TEST_') and k != 'INTERSPEC_TRACE'}
            env['LC_ALL'] = 'C'
            proc = subprocess.Popen(args, stdout=out, stderr=err, start_new_session=True, env=env, preexec_fn=child_setup)
            record_process(directory, "server", proc)
            deadline = time.monotonic() + 20
            while True:
                if proc.poll() is not None:
                    raise RuntimeError('Server exited during startup')
                try:
                    with Client(port, timeout=0.2) as client:
                        if not client.command(b'version').startswith(b'VERSION '):
                            raise ValueError('Unexpected server version response')
                    break
                except (OSError, EOFError):
                    if time.monotonic() >= deadline:
                        raise TimeoutError('Server startup')
                    time.sleep(.02)
            yield port
        finally:
            stop(proc)


def measure(root, directory, run, port, warmup, failure):
    n = run['warmup_operations'] if warmup else run['operations']
    label = 'warmup' if warmup else 'measured'
    args = [str((root / 'bin/client').resolve()), str(port), '0'] + [str(run[k]) for k in ('clients', 'pipeline', 'value_bytes', 'keys', 'get_percent')] + [str(n), 'independent-v1', str(run['seed']), 'count-only', '1024', '100000']
    with Client(port) as c:
        before = c.stats()
    proc = None
    with (directory / (label + '.stdout')).open('wb') as out, (directory / (label + '.stderr')).open('wb') as err:
        try:
            proc = subprocess.Popen(args, stdout=out, stderr=err, start_new_session=True, preexec_fn=child_setup)
            record_process(directory, label, proc)
            if not warmup:
                inject('during_client', failure)
            if proc.wait(timeout=120) != 0:
                raise RuntimeError('Client failed')
        finally:
            stop(proc)
    with Client(port) as c:
        after = c.stats()
    write(directory / (label + '-stats.json'), {'before': before, 'after': after})
    data = json.loads((directory / (label + '.stdout')).read_bytes())
    counters = {k: int(after[k]) - int(before[k]) for k in ('cmd_get', 'cmd_set', 'get_hits', 'get_misses', 'log_worker_dropped', 'log_watcher_skipped', 'lru_bumps_dropped')}
    validate_counts(data, counters, run, warmup)
    return {'client': data, 'counters': counters}


def validate_counts(data, counters, run, warmup):
    prefix = 'warmup_' if warmup else ''
    n = run['warmup_operations'] if warmup else run['operations']
    valid = (data['errors'] == 0 and data['operations'] == n and data['p99_us'] is None and data['latency_sample_count'] == 0 and counters['cmd_get'] == run[prefix + 'expected_get'] and counters['cmd_set'] == run[prefix + 'expected_set'] and counters['get_misses'] == 0 and counters['get_hits'] == counters['cmd_get'] and all(counters[k] == 0 for k in ('log_worker_dropped', 'log_watcher_skipped', 'lru_bumps_dropped')))
    if not valid:
        raise ValueError('Exact workload validation failed')


def execute(root, maximum=1, failure=None):
    if maximum <= 0:
        raise ValueError('max-runs must be positive')
    # Held over the entire invocation, unlike the ledger's brief atomic-write lock.
    import fcntl
    with (root / '.driver-lock').open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan, state = verify(root)
        if any(e['status'] == 'uncertain' for e in state['operations'].values()):
            raise ValueError('Uncertain action: reconcile manually; no automatic retry')
        runs = [e for e in state['operations'].values() if e['kind'] == 'run']
        done = {json.loads(e['details'])['scheduled_id'] for e in runs}
        excluded = {json.loads(e['details'])['block'] for e in runs if e['status'] in ('excluded', 'not_executed')}
        selected = [r for r in plan['schedule'] if r['id'] not in done and r['block'] not in excluded][:maximum]
        ledger = Ledger(root)
        for run in selected:
            attempt = uuid.uuid4().hex
            ledger.start(attempt, 'run', json.dumps({'scheduled_id': run['id'], 'block': run['block']}))
            directory = root / 'attempts' / attempt
            directory.mkdir(parents=True)
            sync_directory(directory.parent)
            sync_directory(root)
            try:
                inject('before_launch', failure)
                with server_process((root / plan['server']).resolve(), directory, plan.get('server_extra', [])) as port:
                    with Client(port) as c:
                        for k in range(run['keys']):
                            if c.store(('bench%d' % k).encode(), b'x' * run['value_bytes']) != b'STORED\r\n':
                                raise ValueError('Prepopulation failed')
                    warmup = measure(root, directory, run, port, True, failure)
                    measured = measure(root, directory, run, port, False, failure)
                if b'INTERSPEC' in (directory / 'server.stderr').read_bytes():
                    raise ValueError('Server diagnostic detected')
                write(directory / 'result.json', {'attempt': attempt, 'scheduled_id': run['id'], 'block': run['block'], 'valid': True, 'warmup': warmup, 'measured': measured})
                inject('after_result_saved', failure)
                for output in directory.iterdir():
                    if output.is_file():
                        with output.open('rb') as stream:
                            os.fsync(stream.fileno())
                sync_directory(directory)
                files = {str(p.relative_to(root)): sha(p) for p in sorted(directory.iterdir()) if p.is_file()}
                ledger.resolve(attempt, 'completed', encoded({'attempt': attempt, 'scheduled_id': run['id'], 'files': files}))
                print(json.dumps({'completed': run['id'], 'attempt': attempt}), flush=True)
            except BaseException as error:
                write(directory / 'interruption.json', {'error': repr(error), 'instruction': 'Inspect processes and evidence; explicitly exclude this block. Never retry automatically.'})
                raise
        _, final_state = verify(root)
        runs = [e for e in final_state['operations'].values() if e['kind'] == 'run']
        return {'executed': len(selected), 'excluded_blocks': sorted(excluded), 'completed': [json.loads(e['details'])['scheduled_id'] for e in runs if e['status'] == 'completed'], 'note': 'Any completed member of an excluded block is retained for audit, excluded from analysis.'}


def export(root, archive):
    import fcntl
    with (root / '.driver-lock').open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ledger = Ledger(root)
        with ledger.locked():
            return export_locked(root, archive, ledger.read())


def export_locked(root, archive, state):
    verify(root, state)
    if archive.exists() or archive.resolve().is_relative_to(root.resolve()):
        raise ValueError('Archive must be new and outside checkpoint directory')
    files = {}
    for p in sorted(root.rglob('*')):
        if p.is_symlink():
            raise ValueError('Symlinks not allowed')
        if p.is_file() and p.name not in ('.lock', '.driver-lock'):
            files[str(p.relative_to(root))] = sha(p)
    manifest = {'version': 1, 'files': files}
    with tarfile.open(archive, 'w:gz') as tar:
        for relative in files:
            tar.add(root / relative, arcname=relative, recursive=False)
        import io
        data = encoded(manifest)
        info = tarfile.TarInfo('CHECKPOINT_MANIFEST.json')
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    with archive.open('rb') as stream:
        os.fsync(stream.fileno())
    sync_directory(archive.parent)
    write(Path(str(archive) + '.sha256.json'), {'archive': archive.name, 'sha256': sha(archive), 'manifest': manifest})
    return {'archive': str(archive), 'sha256': sha(archive)}


def restore(archive, root, expected):
    if root.exists() or sha(archive) != expected:
        raise ValueError('Fresh destination and matching archive SHA-256 required')
    root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.restore-', dir=root.parent) as tmp:
        target = Path(tmp)
        with tarfile.open(archive, 'r:gz') as tar:
            members = tar.getmembers()
            names = [m.name for m in members]
            if len(names) != len(set(names)):
                raise ValueError('Duplicate archive paths')
            for member in members:
                if not member.isfile() or member.name.startswith('/') or '..' in Path(member.name).parts or not (target / member.name).resolve().is_relative_to(target.resolve()):
                    raise ValueError('Unsafe archive member')
            manifest = json.loads(tar.extractfile('CHECKPOINT_MANIFEST.json').read())
            if set(names) != set(manifest['files']) | {'CHECKPOINT_MANIFEST.json'}:
                raise ValueError('Archive inventory mismatch')
            for member in members:
                if member.name == 'CHECKPOINT_MANIFEST.json':
                    continue
                data = tar.extractfile(member).read()
                if digest(data) != manifest['files'][member.name]:
                    raise ValueError('Archive content mismatch')
                path = target / member.name
                path.parent.mkdir(parents=True, exist_ok=True)
                atomic_write(path, data)
            for name in ('client', 'server'):
                (target / 'bin' / name).chmod(0o700)
        verify(target)
        for directory in sorted((p for p in target.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            sync_directory(directory)
        sync_directory(target)
        os.rename(target, root)
        sync_directory(root.parent)
    return verify(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init'); init.add_argument('directory', type=Path); init.add_argument('--plan', required=True, type=Path)
    run = sub.add_parser('run'); run.add_argument('directory', type=Path); run.add_argument('--max-runs', default=1, type=int); run.add_argument('--inject', choices=['before_launch', 'during_client', 'after_result_saved'])
    status = sub.add_parser('status'); status.add_argument('directory', type=Path)
    exp = sub.add_parser('export'); exp.add_argument('directory', type=Path); exp.add_argument('archive', type=Path)
    res = sub.add_parser('restore'); res.add_argument('archive', type=Path); res.add_argument('directory', type=Path); res.add_argument('--sha256', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'init': result = initialize(args.directory, args.plan)
        elif args.command == 'run': result = execute(args.directory, args.max_runs, args.inject)
        elif args.command == 'status': result = verify(args.directory)
        elif args.command == 'export': result = export(args.directory, args.archive)
        else: result = restore(args.archive, args.directory, args.sha256)
        print(json.dumps(result, indent=2))
    except (ValueError, KeyError, OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        parser.exit(1, 'Recovery stopped: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
