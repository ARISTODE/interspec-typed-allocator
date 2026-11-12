"""Durable lifecycle for the original matrix collector, using whole-scenario blocks."""
import argparse
import contextlib
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import signal
import time
import tarfile
import tempfile
import uuid
from memcached_common import guarded_command
from evaluation_checkpoint import Ledger, atomic_write, encoded, digest, sync_directory

TOOLS = ('benchmark_memcached_matrix.py', 'benchmark_memcached.py', 'matrix_checkpoint.py', 'evaluation_checkpoint.py', 'memcached_common.py', 'process_guard.py')
SOURCES = ('evaluation/memcached_client.cpp', 'evaluation/memcached_workload.h', 'evaluation/memcached_measurement.h')
VARIANTS = ('native', 'rlbox-only', 'tracked-no-check', 'interspec')

def process_identity(pid):
    def status(path):
        return dict(line.split(":", 1) for line in path.read_text().splitlines() if ":" in line)
    own = status(Path('/proc/self/status'))
    for path in Path('/proc').iterdir():
        if not path.name.isdecimal(): continue
        try:
            current = status(path / 'status')
            if current.get('PPid', '').strip() == own['Pid'].strip() and int(current.get('NSpid', current['Pid']).split()[-1]) == pid:
                stat = (path / 'stat').read_text()
                return {'proc_stat': stat, 'starttime_ticks': stat.rsplit(')', 1)[1].split()[19], 'proc_visible_pid': int(path.name), 'namespace_pid': pid}
        except (FileNotFoundError, ProcessLookupError, PermissionError): continue
    raise RuntimeError('Cannot record original child identity')

def sha(p): return digest(p.read_bytes())
def write(p, v): atomic_write(p, encoded(v) + b'\n')
def inventory(root):
    result = {}
    for p in sorted(root.rglob('*')):
        if p.is_symlink(): raise ValueError('Symlink forbidden: ' + str(p))
        if p.is_file() and p.name not in ('.lock', '.driver-lock'):
            result[str(p.relative_to(root))] = sha(p)
    return result

@contextlib.contextmanager
def locked(root):
    with (root / '.driver-lock').open('a+b') as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield

def initialize(root, work, correctness, client, arguments, allow_replacement=False):
    if root.exists(): raise ValueError('Fresh state directory required')
    if any(x.split('=')[0] in ('--out', '--work', '--correctness-summary', '--client-binary') for x in arguments):
        raise ValueError('Input/output paths are supplied by the frozen plan')
    source = Path(__file__).resolve().parents[1]
    gate = json.loads(correctness.read_bytes())
    if gate['passed'] != 50 or gate['total'] != 50: raise ValueError('Correctness gate incomplete')
    inputs = {'correctness.json': correctness, 'work/build-manifest.json': work / 'build-manifest.json', 'bin/client': client}
    inputs.update({'work/bin/memcached-' + v: work / 'bin' / ('memcached-' + v) for v in VARIANTS})
    for v in VARIANTS:
        if sha(inputs['work/bin/memcached-' + v]) != gate['binary_sha256']['memcached-' + v]:
            raise ValueError('Correctness binary binding mismatch')
    inputs.update({'tools/' + n: source / 'tools' / n for n in TOOLS})
    inputs.update({n: source / n for n in SOURCES})
    root.mkdir(parents=True)
    for relative, original in inputs.items():
        target = root / relative; target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(target, original.read_bytes())
        if relative.startswith(('bin/', 'work/bin/')): target.chmod(0o700)
    from benchmark_memcached_matrix import SCENARIOS
    plan = {'version': 1, 'phase': 'full-matrix-scenario-blocks-v1', 'arguments': arguments,
            'scenarios': SCENARIOS, 'variants': list(VARIANTS), 'files': inventory(root),
            'interruption_policy': 'one-explicit-whole-scenario-replacement' if allow_replacement else 'exclude-only',
            'source_revision': subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip(),
            'source_identity': 'Exact bundled hashes authoritative, including uncommitted edits',
            'scope': 'VM functional only' if '--functional-rehearsal' in arguments else 'Host control not asserted'}
    write(root / 'plan.json', plan); Ledger(root).init((root / 'plan.json').read_bytes())
    return verify(root)

def verify(root, state=None):
    state = Ledger(root).status() if state is None else state; plan = json.loads((root / 'plan.json').read_bytes())
    if sha(root / 'plan.json') != state['plan_sha256']: raise ValueError('Plan mismatch')
    for relative, expected in plan['files'].items():
        p = root / relative
        if p.is_symlink() or not p.resolve().is_relative_to(root.resolve()) or sha(p) != expected:
            raise ValueError('Frozen input mismatch: ' + relative)
    for name in TOOLS:
        if sha(Path(__file__).parent / name) != plan['files']['tools/' + name]:
            raise ValueError('Run with the frozen bundled toolchain: ' + name)
    scenarios = {s['name'] for s in plan['scenarios']}; seen = set()
    for ident, e in state['operations'].items():
        if e['kind'] != 'run': continue
        d = json.loads(e['details']); key = (d['scenario'], d['epoch'])
        if d['scenario'] not in scenarios or key in seen or d['epoch'] not in (0, 1): raise ValueError('Invalid/duplicate block')
        seen.add(key)
        if e['status'] == 'excluded':
            proof = json.loads((root / (e['evidence_sha256'] + '.blob')).read_bytes())
            if inventory(root / 'attempts' / ident) != proof['retained_files']: raise ValueError('Excluded evidence corruption')
        if e['status'] == 'completed':
            proof = json.loads((root / (e['evidence_sha256'] + '.blob')).read_bytes())
            if proof['attempt'] != ident or proof['scenario'] != d['scenario']: raise ValueError('Completion identity mismatch')
            directory = root / 'attempts' / ident
            if inventory(directory) != proof['files']: raise ValueError('Completed output corruption')
            if not {'summary.json', 'samples.csv', 'environment.json'} <= set(proof['files']): raise ValueError('Incomplete output')
    return plan, state

class Collection:
    def __init__(self, root, maximum, inject):
        self.root = root; self.plan, self.state = verify(root); self.maximum = maximum; self.inject = inject; self.executed = 0; self.excluded = []
        if any(e['status'] == 'uncertain' for e in self.state['operations'].values()): raise ValueError('Uncertain block: explicit reconciliation required')
    def begin(self, scenario):
        entries = [(i, e, json.loads(e['details'])) for i, e in self.state['operations'].items() if e['kind'] == 'run' and json.loads(e['details'])['scenario'] == scenario]
        if entries:
            ident, entry, details = max(entries, key=lambda t: t[2]['epoch'])
            if entry['status'] == 'completed': return self.root / 'attempts' / ident, False
            proof = json.loads((self.root / (entry['evidence_sha256'] + '.blob')).read_bytes())
            if not proof.get('replacement_authorized'):
                self.excluded.append(scenario); return None, False
            epoch = details['epoch'] + 1
        else: epoch = 0
        if self.executed >= self.maximum: raise StopIteration('Block limit reached; grid remains pending')
        self.ident = uuid.uuid4().hex; self.scenario = scenario
        Ledger(self.root).start(self.ident, 'run', json.dumps({'scenario': scenario, 'epoch': epoch, 'phase': self.plan['phase']}))
        directory = self.root / 'attempts' / self.ident; directory.mkdir(parents=True); sync_directory(directory.parent)
        return directory, True
    def launch(self, cmd, out):
        write(out / 'command.json', {'argv': cmd, 'phase': self.plan['phase'], 'scenario': self.scenario})
        if self.inject == 'before_launch': raise RuntimeError('Injected before_launch')
        with (out / 'collector.stdout').open('xb') as stdout, (out / 'collector.stderr').open('xb') as stderr:
            proc = subprocess.Popen(guarded_command(cmd), stdout=stdout, stderr=stderr, start_new_session=True)
            try:
                write(out / 'process.json', {'pid': proc.pid, **process_identity(proc.pid), 'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(), 'instruction': 'Audit only; do not signal a PID without verifying identity'})
                if self.inject == 'during_collection':
                    time.sleep(1)
                    raise RuntimeError('Injected during_collection')
                code = proc.wait()
                if code:
                    write(out / 'observed_failure.json', {'returncode': code, 'replacement_prohibited': True})
                    raise RuntimeError('Collector failed; no replacement allowed')
            finally:
                try: os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError: pass
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired: pass
                try: os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                proc.wait()
        if self.inject == 'after_result_saved': raise RuntimeError('Injected after_result_saved')
        for p in out.rglob('*'):
            if p.is_file():
                with p.open('rb') as f: os.fsync(f.fileno())
        for p in sorted([out] + [p for p in out.rglob('*') if p.is_dir()], key=lambda p: len(p.parts), reverse=True): sync_directory(p)
        if hasattr(self, 'validator'): self.validator(out)
        Ledger(self.root).resolve(self.ident, 'completed', encoded({'attempt': self.ident, 'scenario': self.scenario, 'files': inventory(out)}))
        self.executed += 1

def run(root, maximum=6, inject=None):
    with locked(root):
        collection = Collection(root, maximum, inject)
        report = root / 'reports' / uuid.uuid4().hex
        args = collection.plan['arguments'] + ['--work', str(root / 'work'), '--correctness-summary', str(root / 'correctness.json'), '--client-binary', str(root / 'bin/client'), '--out', str(report), '--include-tracking']
        from benchmark_memcached_matrix import main
        try: main(args, checkpoint=collection)
        except StopIteration as e: return {'pending': str(e), 'executed': collection.executed}
        return {'report': str(report), 'excluded': collection.excluded, 'grid_complete': not collection.excluded}

def reconcile(root, ident, reason, retry, no_active):
    with locked(root):
        plan, state = verify(root); e = state['operations'][ident]; d = json.loads(e['details'])
        if not no_active: raise ValueError('Confirm no original collector/server/client remains active')
        if retry and (root / 'attempts' / ident / 'observed_failure.json').exists(): raise ValueError('Observed collector failure cannot be replaced')
        if retry and (plan['interruption_policy'] != 'one-explicit-whole-scenario-replacement' or d['epoch'] != 0): raise ValueError('Replacement not predeclared or exhausted')
        if e['status'] != 'uncertain': raise ValueError('Only uncertain interruption can be reconciled')
        Ledger(root).resolve(ident, 'excluded', encoded({'reason': reason, 'whole_scenario_excluded': True, 'replacement_authorized': retry, 'no_original_processes_active_confirmed': True, 'retained_files': inventory(root / 'attempts' / ident)}), reconciliation=True)

def export(root, archive, no_active=False, verifier=None):
    with locked(root), Ledger(root).locked():
        # Ledger lock is held while taking the complete portable snapshot.
        if archive.exists() or archive.resolve().is_relative_to(root.resolve()): raise ValueError('New archive outside state required')
        state = Ledger(root).read()
        (verifier or verify)(root, state)
        if any(e['status'] == 'uncertain' for e in state['operations'].values()) and not no_active:
            raise ValueError('Uncertain state export requires --confirm-no-active-processes after verifying collector, server and client have stopped')
        files = inventory(root)
        import io
        fd, temporary = tempfile.mkstemp(prefix='.matrix-export-', dir=archive.parent)
        with os.fdopen(fd, 'wb') as raw:
            with tarfile.open(fileobj=raw, mode='w:gz') as tar:
                for relative in files: tar.add(root / relative, arcname=relative, recursive=False)
                data = encoded({'files': files}); info = tarfile.TarInfo('CHECKPOINT_MANIFEST.json'); info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            raw.flush(); os.fsync(raw.fileno())
        os.link(temporary, archive); os.unlink(temporary)
        sync_directory(archive.parent)
        return {'archive': str(archive), 'sha256': sha(archive)}

def restore(archive, root, expected, verifier=None):
    if root.exists() or sha(archive) != expected: raise ValueError('Fresh destination and matching SHA-256 required')
    root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root.parent) as tmp:
        target = Path(tmp)
        with tarfile.open(archive, 'r:gz') as tar:
            members = tar.getmembers(); names = [m.name for m in members]
            if len(names) != len(set(names)): raise ValueError('Duplicate archive paths')
            for m in members:
                if not m.isfile() or m.name.startswith('/') or '..' in Path(m.name).parts: raise ValueError('Unsafe archive member')
            manifest = json.loads(tar.extractfile('CHECKPOINT_MANIFEST.json').read())
            if set(names) != set(manifest['files']) | {'CHECKPOINT_MANIFEST.json'}: raise ValueError('Archive inventory mismatch')
            for name, expected_file in manifest['files'].items():
                data = tar.extractfile(name).read()
                if digest(data) != expected_file: raise ValueError('Archive content mismatch')
                p = target / name; p.parent.mkdir(parents=True, exist_ok=True); atomic_write(p, data)
            for p in [target / 'bin/client'] + list((target / 'work/bin').iterdir()): p.chmod(0o700)
        (verifier or verify)(target)
        for directory in sorted([target] + [x for x in target.rglob('*') if x.is_dir()], key=lambda x: len(x.parts), reverse=True): sync_directory(directory)
        os.rename(target, root); sync_directory(root.parent)
    return {'restored': str(root)}

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init'); init.add_argument('directory', type=Path); init.add_argument('--work', type=Path, required=True); init.add_argument('--correctness-summary', type=Path, required=True); init.add_argument('--client-binary', type=Path, required=True); init.add_argument('--allow-one-interruption-replacement', action='store_true')
    for command in ('run', 'status', 'reconcile', 'export'):
        q = sub.add_parser(command); q.add_argument('directory', type=Path)
        if command == 'run': q.add_argument('--max-scenarios', type=int, default=6); q.add_argument('--inject', choices=['before_launch', 'during_collection', 'after_result_saved'])
        if command == 'reconcile': q.add_argument('attempt'); q.add_argument('--reason', required=True); q.add_argument('--retry-whole-scenario', action='store_true'); q.add_argument('--confirm-no-active-processes', action='store_true')
        if command == 'export': q.add_argument('archive', type=Path); q.add_argument('--confirm-no-active-processes', action='store_true')
    q = sub.add_parser('restore'); q.add_argument('archive', type=Path); q.add_argument('directory', type=Path); q.add_argument('--sha256', required=True)
    raw = list(sys.argv[1:] if argv is None else argv); arguments = []
    if '--' in raw:
        i = raw.index('--'); arguments = raw[i+1:]; raw = raw[:i]
    a = p.parse_args(raw); root = a.directory.resolve()
    if arguments and a.command != 'init': p.error('Frozen arguments only accepted at init')
    if a.command == 'init': result = initialize(root, a.work.resolve(), a.correctness_summary.resolve(), a.client_binary.resolve(), arguments, a.allow_one_interruption_replacement)
    elif a.command == 'run': result = run(root, a.max_scenarios, a.inject)
    elif a.command == 'status': result = verify(root)
    elif a.command == 'reconcile': result = reconcile(root, a.attempt, a.reason, a.retry_whole_scenario, a.confirm_no_active_processes)
    elif a.command == 'export':
        verify(root); result = export(root, a.archive.resolve(), a.confirm_no_active_processes)
    else: result = restore(a.archive, root, a.sha256)
    print(json.dumps(result, indent=2))

if __name__ == '__main__': main()
