#!/usr/bin/env python3
"""Predeclared VM-only A/A and client-resource diagnostic; no acceptance decision."""
import argparse
import csv
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time
import uuid
import matrix_checkpoint as checkpoint
from evaluation_checkpoint import Ledger, atomic_write, encoded, sync_directory
from benchmark_memcached_matrix import SCENARIOS

TOOLS = tuple(dict.fromkeys(checkpoint.TOOLS + ('capacity_diagnostic.py',)))
CONFIGS = {'count4-A': '4-7', 'count4-B': '4-7', 'count5': '4-8', 'count1': '4'}
SEED = 2026111001
sha, write, inventory = checkpoint.sha, checkpoint.write, checkpoint.inventory


def schedule():
    rng = random.Random(SEED)
    scenarios = [s for s in SCENARIOS if s['name'] in ('balanced_8c', 'read_heavy_1k')]
    blocks = []
    for scenario in scenarios:
        labels = list(CONFIGS); rng.shuffle(labels)
        # Each treatment occupies each position once and every directed
        # adjacency occurs once in this even-order Williams design.
        rows = [[0, 1, 3, 2], [1, 2, 0, 3], [2, 3, 1, 0], [3, 0, 2, 1]]
        rng.shuffle(rows)
        for row in rows:
            blocks.append({'scenario': scenario, 'order': [labels[i] for i in row]})
    rng.shuffle(blocks)
    for i, block in enumerate(blocks):
        block.update(id=f'block-{i:02d}', workload_seed=2026111000 + i)
    return blocks


def expected_counts(root, blocks, measured, warmup):
    # Excluded, untimed integer oracle using exactly the frozen workload header.
    source = root / 'expected_counts.cpp'
    source.write_text('''#include "evaluation/memcached_workload.h"
#include <iostream>
int main(){unsigned long long n,w,seed; unsigned pct; while(std::cin>>n>>w>>seed>>pct){unsigned long long a=0,b=0; for(unsigned long long i=0;i<n || i<w;++i){bool g=memcached_workload::request(memcached_workload::Mode::independent_v1,seed,i,10000,pct).get; if(i<n)a+=g; if(i<w)b+=g;}std::cout<<a<<" "<<b<<"\\n";}}
''')
    subprocess.run(['g++', '-std=c++17', '-O2', str(source), '-o', str(root / 'bin/count-oracle')], check=True)
    request = ''.join(f"{measured} {warmup} {b['workload_seed']} {b['scenario']['get_percent']}\n" for b in blocks)
    result = subprocess.run([str(root / 'bin/count-oracle')], input=request, text=True, capture_output=True, check=True)
    write(root / 'count-oracle-record.json', {'input': request, 'stdout': result.stdout, 'stderr': result.stderr, 'excluded_from_measurement': True})
    for block, line in zip(blocks, result.stdout.splitlines(), strict=True):
        block['expected_get'], block['warmup_expected_get'] = map(int, line.split())


def initialize(root, work, correctness, client, smoke=False):
    if root.exists(): raise ValueError('Fresh state directory required')
    source = Path(__file__).resolve().parents[1]
    gate = json.loads(correctness.read_bytes())
    if gate['passed'] != 50 or gate['total'] != 50: raise ValueError('Correctness gate incomplete')
    server = work / 'bin/memcached-rlbox-only'
    if sha(server) != gate['binary_sha256'][server.name]: raise ValueError('Correctness binary binding mismatch')
    files = {'correctness.json': correctness, 'work/build-manifest.json': work / 'build-manifest.json', 'work/bin/memcached-rlbox-only': server, 'bin/client': client}
    files.update({'tools/' + n: source / 'tools' / n for n in TOOLS})
    files.update({n: source / n for n in checkpoint.SOURCES})
    root.mkdir(parents=True)
    for relative, original in files.items():
        target = root / relative; target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(target, original.read_bytes())
        if relative.startswith(('bin/', 'work/bin/')): target.chmod(0o700)
    blocks = schedule(); operations, warmup = (20000, 4000) if smoke else (20000000, 4000000)
    expected_counts(root, blocks, operations, warmup)
    plan = {'version': 1, 'phase': 'capacity-diagnostic-smoke-excluded' if smoke else 'capacity-diagnostic-v1',
            'scope': 'VM-only single-server capacity diagnostic; no acceptance, equivalence, publication or host-control claim',
            'schedule_seed': SEED, 'blocks': blocks, 'configs': CONFIGS, 'operations': operations, 'warmup_operations': warmup,
            'server_cpus': '0-3', 'variant': 'rlbox-only', 'measurement_mode': 'count-only', 'workload_mode': 'independent-v1',
            'interruption_policy': 'exclude whole matched block; retain every outcome; never retry',
            'duration_note': 'Fixed counts chosen before collection, not calibrated from outcomes. Roughly 15s measured and 3s warmup intended for fastest baseline; actual duration may differ.',
            'analysis': 'Descriptive within-block ratios to count4-A and A/B, all points with order and invocation epoch. No independent-session bootstrap or threshold acceptance. Any +/-2% band descriptive only.',
            'source_revision': subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip(),
            'client_provenance': {'baseline_revision': '2c6b957', 'baseline_role': 'Previously vetted corrected measurement client; parent supplies build provenance', 'binary_sha256': sha(client), 'source_sha256': {n: sha(source/n) for n in checkpoint.SOURCES}},
            'cpu_scope': 'Allowed logical/virtual CPU IDs; no physical-core or dedicated-host claim',
            'source_identity': 'Bundled file hashes authoritative, including uncommitted edits', 'files': inventory(root)}
    write(root / 'plan.json', plan); Ledger(root).init((root / 'plan.json').read_bytes())
    return verify(root)


def command(root, plan, block, config, out):
    scenario = block['scenario']
    args = [sys.executable, str(root / 'tools/benchmark_memcached.py'), '--capacity-diagnostic', '--variants', 'rlbox-only', '--workloads', 'cache_only', '--repetitions', '1', '--seconds', '15', '--warmup', '3', '--work', str(root / 'work'), '--correctness-summary', str(root / 'correctness.json'), '--client-binary', str(root / 'bin/client'), '--out', str(out), '--server-cpus', plan['server_cpus'], '--client-cpus', plan['configs'][config], '--operations', str(plan['operations']), '--warmup-operations', str(plan['warmup_operations']), '--workload-seed', str(block['workload_seed']), '--measurement-mode', 'count-only', '--workload-mode', 'independent-v1', '--label', plan['phase']]
    for field in ('clients', 'pipeline', 'value_bytes', 'keys', 'get_percent'):
        args += ['--' + field.replace('_', '-'), str(scenario[field])]
    return args


def validate_output(directory, plan, block):
    prefix = directory / 'logs/cache_only-0-rlbox-only'
    data = json.loads(Path(str(prefix) + '.measured.stdout').read_bytes())
    warmup = json.loads(Path(str(prefix) + '.warmup.stdout').read_bytes())
    for row, n in ((data, plan['operations']), (warmup, plan['warmup_operations'])):
        if not (row['operations'] == n and row['errors'] == 0 and row['measurement_mode'] == 'count-only' and row['latency_sample_count'] == 0 and all(row[k] is None for k in ('p50_us', 'p95_us', 'p99_us', 'max_us')) and row['workload_mode'] == plan['workload_mode'] and row['workload_seed'] == block['workload_seed'] and row['latency_valid'] is False and all(row[k] == 0 for k in ('latency_selected_count', 'latency_dropped_count', 'sample_every', 'sample_cap_per_client'))): raise ValueError('Fixed work/count-only validation failed')
    warm_stats = json.loads(Path(str(prefix) + '.warmup.stats.json').read_bytes())
    warm_delta = {k: int(warm_stats['after'][k]) - int(warm_stats['before'][k]) for k in ('cmd_get', 'cmd_set', 'get_hits', 'get_misses', 'log_worker_dropped', 'log_watcher_skipped', 'lru_bumps_dropped')}
    if not (warm_delta['cmd_get'] == block['warmup_expected_get'] and warm_delta['cmd_set'] == plan['warmup_operations'] - block['warmup_expected_get'] and warm_delta['get_hits'] == warm_delta['cmd_get'] and all(warm_delta[k] == 0 for k in ('get_misses', 'log_worker_dropped', 'log_watcher_skipped', 'lru_bumps_dropped'))): raise ValueError('Warmup exact counts or zero-loss validation failed')
    stats = json.loads(Path(str(prefix) + '.stats.json').read_bytes())
    delta = {k: int(stats['after'][k]) - int(stats['before'][k]) for k in ('cmd_get', 'cmd_set', 'get_hits', 'get_misses', 'log_worker_dropped', 'log_watcher_skipped', 'lru_bumps_dropped')}
    if not (delta['cmd_get'] == block['expected_get'] and delta['cmd_set'] == plan['operations'] - block['expected_get'] and delta['get_hits'] == delta['cmd_get'] and all(delta[k] == 0 for k in ('get_misses', 'log_worker_dropped', 'log_watcher_skipped', 'lru_bumps_dropped'))): raise ValueError('Exact server counts or zero-loss validation failed')
    rows = list(csv.DictReader((directory / 'samples.csv').open()))
    if len(rows) != 1 or rows[0]['variant'] != 'rlbox-only' or rows[0]['workload'] != 'cache_only' or int(rows[0]['operations']) != plan['operations'] or float(rows[0]['ops_per_s']) != data['ops_per_s']: raise ValueError('Collector sample mismatch')
    from benchmark_memcached import cpu_set
    if cpu_set(rows[0]['observed_server_cpus']) != cpu_set(plan['server_cpus']): raise ValueError('Server affinity evidence mismatch')
    environment = json.loads((directory/'environment.json').read_bytes())
    requested = environment['parameters']['client_cpus']
    for phase in ('warmup', 'measured'):
        affinity = json.loads(Path(str(prefix) + '.' + phase + '.affinity.json').read_bytes())
        if set(affinity['probe_cpus']) != cpu_set(requested): raise ValueError('Client probe affinity mismatch')
        observed = affinity['observed_client_cpus']
        if (observed is not None and cpu_set(observed) != cpu_set(requested)) or (plan['phase'] == 'capacity-diagnostic-v1' and observed is None): raise ValueError('Client runtime affinity missing/mismatch')
    return data


def verify(root, state=None):
    state = Ledger(root).status() if state is None else state
    plan = json.loads((root / 'plan.json').read_bytes())
    if sha(root / 'plan.json') != state['plan_sha256']: raise ValueError('Plan mismatch')
    for relative, expected in plan['files'].items():
        p = root / relative
        if p.is_symlink() or not p.resolve().is_relative_to(root.resolve()) or sha(p) != expected: raise ValueError('Frozen input mismatch: ' + relative)
    for name in TOOLS:
        if sha(Path(__file__).parent / name) != plan['files']['tools/' + name]: raise ValueError('Use frozen bundled toolchain: ' + name)
    blocks = {b['id']: b for b in plan['blocks']}; seen = set()
    for ident, entry in state['operations'].items():
        if entry['kind'] == 'upload': continue
        if json.loads(entry['details']).get('type') == 'block_exclusion':
            if json.loads(entry['details'])['block'] not in blocks: raise ValueError('Unknown excluded block')
            continue
        if entry['kind'] != 'run': raise ValueError('Unexpected ledger action')
        detail = json.loads(entry['details']); key = (detail['block'], detail['config'])
        if detail['block'] not in blocks or detail['config'] not in CONFIGS or key in seen: raise ValueError('Unknown/duplicate scheduled identity')
        seen.add(key)
        if entry['status'] in ('completed', 'excluded'):
            proof = json.loads((root / (entry['evidence_sha256'] + '.blob')).read_bytes())
            if inventory(root / 'attempts' / ident) != proof['files']: raise ValueError('Retained evidence corruption')
            if entry['status'] == 'completed':
                if proof['attempt'] != ident or proof['scenario'] != detail['block'] + '/' + detail['config']: raise ValueError('Completion identity mismatch')
                validate_output(root / 'attempts' / ident, plan, blocks[detail['block']])
    return plan, state


def execute(root, maximum=1, inject=None):
    if maximum != 1: raise ValueError('Exactly one matched block per invocation; export/upload before continuing')
    with checkpoint.locked(root):
        plan, state = verify(root)
        if any(e['status'] == 'uncertain' for e in state['operations'].values()): raise ValueError('Uncertain run: explicitly exclude its whole block; no retries')
        details = [(json.loads(e['details']), e['status']) for e in state['operations'].values() if e['kind'] == 'run' and json.loads(e['details']).get('type') != 'block_exclusion']
        excluded = {d['block'] for d, status in details if status != 'completed'}
        excluded.update(json.loads(e['details'])['block'] for e in state['operations'].values() if e['kind'] == 'run' and json.loads(e['details']).get('type') == 'block_exclusion')
        done = {(d['block'], d['config']) for d, status in details if status == 'completed'}
        pending = [b for b in plan['blocks'] if b['id'] not in excluded and not all((b['id'], c) in done for c in b['order'])]
        if not pending: return {'remaining_blocks': 0, 'excluded_blocks': sorted(excluded)}
        block = pending[0]
        # Never continue a partially completed block after an invocation ended.
        if any((block['id'], c) in done for c in block['order']): raise ValueError('Partial block: explicit whole-block exclusion required')
        epoch = uuid.uuid4().hex
        for position, config in enumerate(block['order']):
            ident = uuid.uuid4().hex; directory = root / 'attempts' / ident
            detail = {'block': block['id'], 'config': config, 'position': position, 'epoch': epoch, 'start_unix': time.time(), 'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
            Ledger(root).start(ident, 'run', json.dumps(detail))
            directory.mkdir(parents=True); sync_directory(directory.parent)
            # Reuse the tested guarded collector lifecycle, but validate real
            # output before allowing it to resolve the measured-run checkpoint.
            collection = checkpoint.Collection.__new__(checkpoint.Collection)
            collection.root = root; collection.plan = plan; collection.ident = ident
            collection.scenario = block['id'] + '/' + config; collection.executed = 0; collection.inject = inject
            collection.validator = lambda out: validate_output(out, plan, block)
            collection.launch(command(root, plan, block, config, directory), directory)
            print(json.dumps({'completed': detail, 'attempt': ident}), flush=True)
        verify(root)
        return {'completed_block': block['id'], 'remaining_blocks': len(pending) - 1, 'next': 'Export and verify remote checkpoint before next run invocation'}


def reconcile(root, attempt, reason, no_active):
    with checkpoint.locked(root):
        plan, state = verify(root)
        if not no_active: raise ValueError('Verify original collector/server/client stopped before confirmation')
        entry = state['operations'][attempt]
        if entry['status'] != 'uncertain': raise ValueError('Only uncertain runs can be reconciled')
        Ledger(root).resolve(attempt, 'excluded', encoded({'reason': reason, 'whole_block_excluded': True, 'no_active_processes_confirmed': True, 'files': inventory(root / 'attempts' / attempt)}), reconciliation=True)



def exclude_block(root, block, reason, no_active):
    with checkpoint.locked(root):
        plan, state = verify(root)
        if not no_active or block not in {b['id'] for b in plan['blocks']}:
            raise ValueError('Known block and stopped-process confirmation required')
        if any(e['status'] == 'uncertain' for e in state['operations'].values()):
            raise ValueError('First reconcile uncertain run')
        ident = uuid.uuid4().hex
        Ledger(root).start(ident, 'run', json.dumps({'type': 'block_exclusion', 'block': block, 'reason': reason}))
        Ledger(root).resolve(ident, 'completed', encoded({'whole_block_excluded': True, 'reason': reason, 'no_active_processes_confirmed': True}))


def main():
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init'); init.add_argument('directory', type=Path); init.add_argument('--work', type=Path, required=True); init.add_argument('--correctness-summary', type=Path, required=True); init.add_argument('--client-binary', type=Path, required=True); init.add_argument('--smoke-excluded', action='store_true')
    for name in ('run', 'status', 'reconcile', 'exclude-block', 'export'):
        q = sub.add_parser(name); q.add_argument('directory', type=Path)
        if name == 'run': q.add_argument('--max-blocks', type=int, default=1); q.add_argument('--inject', choices=['before_launch', 'during_collection', 'after_result_saved'])
        if name == 'reconcile': q.add_argument('attempt'); q.add_argument('--reason', required=True); q.add_argument('--confirm-no-active-processes', action='store_true')
        if name == 'exclude-block': q.add_argument('block'); q.add_argument('--reason', required=True); q.add_argument('--confirm-no-active-processes', action='store_true')
        if name == 'export': q.add_argument('archive', type=Path); q.add_argument('--confirm-no-active-processes', action='store_true')
    q = sub.add_parser('restore'); q.add_argument('archive', type=Path); q.add_argument('directory', type=Path); q.add_argument('--sha256', required=True)
    a = p.parse_args(); root = a.directory.resolve()
    if a.command == 'init': result = initialize(root, a.work.resolve(), a.correctness_summary.resolve(), a.client_binary.resolve(), a.smoke_excluded)
    elif a.command == 'run': result = execute(root, a.max_blocks, a.inject)
    elif a.command == 'status': result = verify(root)
    elif a.command == 'reconcile': result = reconcile(root, a.attempt, a.reason, a.confirm_no_active_processes)
    elif a.command == 'exclude-block': result = exclude_block(root, a.block, a.reason, a.confirm_no_active_processes)
    elif a.command == 'export': result = checkpoint.export(root, a.archive.resolve(), a.confirm_no_active_processes, verifier=verify)
    else: result = checkpoint.restore(a.archive, root, a.sha256, verifier=verify)
    print(json.dumps(result, indent=2))

if __name__ == '__main__': main()
