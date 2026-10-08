#!/usr/bin/env python3
"""Recompute the selected application reference tables from paired raw samples."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / 'evaluation/results'


def read_csv(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def load(path):
    return json.loads(path.read_text())


def paired(rows, mode_key, value_key, modes, repetitions, scale=1):
    groups = {}
    for row in rows:
        group = groups.setdefault(int(row['repetition']), {})
        mode = row[mode_key]
        assert mode not in group, 'duplicate variant within repetition'
        group[mode] = float(row[value_key]) / scale
    assert set(groups) == set(range(repetitions)), 'missing repetition'
    assert all(set(group) == set(modes) for group in groups.values()), 'incomplete paired sample'
    assert all(value > 0 and math.isfinite(value) for group in groups.values() for value in group.values())
    return [groups[i] for i in range(repetitions)]


def result(benchmark, workload, unit, groups, names, source, throughput=False, seconds=None):
    native, rlbox, interspec, tracking = names
    deltas = [100 * (1 - group[interspec] / group[rlbox]) if throughput else
              100 * (group[interspec] / group[rlbox] - 1) for group in groups]
    # Inverse throughput is a time-per-operation proxy, not measured request latency.
    normalized = [100 * (group[rlbox] / group[interspec] - 1) if throughput else
                  100 * (group[interspec] / group[rlbox] - 1) for group in groups]
    median = lambda mode: statistics.median(group[mode] for group in groups)
    return dict(benchmark=benchmark, workload=workload, unit=unit,
                native=median(native), rlbox=median(rlbox), interspec=median(interspec),
                tracking=median(tracking) if tracking else None,
                paired_delta_pct=statistics.median(deltas), paired_min_pct=min(deltas),
                paired_max_pct=max(deltas), delta_definition='throughput loss' if throughput else 'runtime increase',
                inverse_throughput_or_runtime_overhead_pct=statistics.median(normalized),
                repetitions=len(groups), seconds_per_measurement=seconds,
                source=str(source.relative_to(ROOT)), publication_ready=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--nginx-results', type=Path, required=True,
                        help='directory containing correctness/summary.json and performance/{environment.json,samples.csv,summary.json}')
    parser.add_argument('--output', type=Path, default=ROOT / 'SELECTED_EVALUATION_RESULTS.md')
    args = parser.parse_args()
    output = []
    sources = []
    modes = ['native', 'rlbox_only', 'tracked_no_check', 'extended_sp3']
    names = ['native', 'rlbox_only', 'extended_sp3', 'tracked_no_check']

    rsync = RESULTS / 'rsync-popt'
    raw_path = rsync / 'rsync-performance.csv'
    raw = read_csv(raw_path)
    sources.append(raw_path)
    for summary in read_csv(rsync / 'rsync-performance-summary.csv'):
        subset = [row for row in raw if row['workload'] == summary['workload']]
        groups = paired(subset, 'mode', 'total_ns', modes, int(summary['repetitions']), 1e6)
        row = result('rsync/popt', summary['workload'], 'ms', groups, names, raw_path)
        assert math.isclose(row['paired_delta_pct'], float(summary['total_overhead_median_pct']), abs_tol=1e-6)
        output.append(row)

    yaml = RESULTS / 'yaml-libyaml/hosted-37593628736'
    env = load(yaml / 'environment.json')
    correctness, security = load(yaml / 'correctness.json'), load(yaml / 'security.json')
    assert correctness['passed'] and security['passed'] and len(security['rejections']) == 4
    assert env['input_bytes'] == 1048576 and env['iterations'] == 1000 and env['repetitions'] == 15
    assert len({(v['events'], v['scalars'], v['scalar_bytes'], v['hash']) for v in correctness['variants'].values()}) == 1
    raw_path = yaml / 'yaml-performance.csv'
    groups = paired(read_csv(raw_path), 'mode', 'total_ns', modes, env['repetitions'], 1e6)
    row = result('YAML/libyaml', '1 MiB document, 1000 parses', 'ms', groups, names, raw_path)
    summary = read_csv(yaml / 'yaml-performance-summary.csv')[0]
    assert math.isclose(row['paired_delta_pct'], float(summary['total_overhead_median_pct']), abs_tol=1e-6)
    output.append(row)
    sources.append(raw_path)

    memcached = RESULTS / 'memcached-overhead/hosted-37593628863'
    gate = load(memcached / 'correctness/summary.json')
    assert gate['passed'] == gate['total'] == 50
    matrix = load(memcached / 'overhead-matrix/final-summary.json')
    assert not matrix['invalid_loss_scenarios']
    raw_path = memcached / 'overhead-matrix/all-samples.csv'
    raw = read_csv(raw_path)
    for sample in raw:
        assert sample['valid_no_log_loss'] == sample['valid_no_lru_loss'] == 'True'
        assert int(sample['errors']) == 0
        assert all(int(sample[key]) == 0 for key in ['log_worker_dropped', 'log_watcher_skipped', 'lru_bumps_dropped'])
    write_lru = [int(row['moves_to_warm']) for row in raw
                 if row['scenario'] == 'write_heavy' and row['variant'] == 'interspec']
    assert len(write_lru) == matrix['repetitions'] and all(value > 0 for value in write_lru)
    for scenario in matrix['scenarios']:
        scenario_env = load(memcached / 'overhead-matrix' / scenario['name'] / 'environment.json')
        assert scenario_env['parameters']['seconds'] == matrix['seconds']
        assert scenario_env['parameters']['repetitions'] == matrix['repetitions']
        assert all(gate['binary_sha256']['memcached-' + variant] == scenario_env['build']['binary_sha256']['memcached-' + variant]
                   for variant in matrix['variants'])
        groups = paired([r for r in raw if r['scenario'] == scenario['name']],
                        'variant', 'ops_per_s', matrix['variants'], matrix['repetitions'], 1000)
        row = result('memcached/bipbuffer', scenario['name'], 'Kops/s', groups,
                     ['native', 'rlbox-only', 'interspec', None], raw_path,
                     throughput=True, seconds=matrix['seconds'])
        assert math.isclose(row['paired_delta_pct'], scenario['interspec_loss_vs_rlbox_pct'], abs_tol=1e-6)
        output.append(row)
    sources.append(raw_path)

    nginx = args.nginx_results.resolve()
    gate = load(nginx / 'correctness/summary.json')
    assert gate['passed'] and all(case['passed'] for case in gate['cases'])
    assert gate['worker_reload_tested'] and len(gate['cases']) == 24
    for name in ['workers-reload/native', 'workers-reload/interspec']:
        detail = next(case['detail'] for case in gate['cases'] if case['name'] == name)
        assert detail['reloads'] == 2 and len(detail['worker_generations']) == 3
        assert detail['concurrent_requests_after_reload'] == 160
    env = load(nginx / 'performance/environment.json')
    assert env['seconds'] == 30 and env['connections'] == 100 and env['repetitions'] == 5
    assert all(gate['binary_sha256'][variant] == digest for variant, digest in env['binary_sha256'].items())
    raw_path = nginx / 'performance/samples.csv'
    raw = read_csv(raw_path)
    assert len(raw) == 40
    for sample in raw:
        assert int(sample['requests']) == int(sample['validated']) > 0
        assert all(int(sample[key]) == 0 for key in ['bad', 'connect_errors', 'read_errors', 'write_errors', 'status_errors', 'timeouts'])
    for summary in load(nginx / 'performance/summary.json'):
        groups = paired([r for r in raw if int(r['threads']) == summary['threads']],
                        'variant', 'requests_per_s', ['native', 'rlbox-only', 'tracked-no-check', 'interspec'], 5, 1000)
        row = result('nginx/PCRE', f"{summary['threads']} wrk threads", 'Kreq/s', groups,
                     ['native', 'rlbox-only', 'interspec', 'tracked-no-check'], raw_path, throughput=True, seconds=30)
        assert math.isclose(row['paired_delta_pct'], summary['interspec_vs_rlbox_pct'], abs_tol=1e-6)
        output.append(row)
    sources.append(raw_path)

    assert len(output) == 12
    destination = RESULTS / 'selected'
    destination.mkdir(exist_ok=True)
    (destination / 'summary.json').write_text(json.dumps(output, indent=2) + '\n')
    with (destination / 'summary.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(output[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(output)
    manifest = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
    (destination / 'source-sha256.json').write_text(json.dumps(manifest, indent=2) + '\n')

    lines = ['# Selected application evaluation results', '',
             'All four selected Extended-SP3 applications have reference measurements. These are hosted or shared-environment results. Final controlled-hardware publication measurements remain outstanding.', '',
             '## Verified reference numbers', '',
             'Values are medians of individual runs. Deltas and ranges are computed from paired runs, so they need not equal ratios of the displayed medians.', '',
             '| Application | Workload | Unit | Native | RLBox | Tracking | InterSpec | Paired delta vs RLBox | Paired range | Repetitions |',
             '| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |']
    for row in output:
        tracking = f"{row['tracking']:.3f}" if row['tracking'] is not None else 'not collected'
        lines.append(f"| {row['benchmark']} | {row['workload']} | {row['unit']} | {row['native']:.3f} | {row['rlbox']:.3f} | {tracking} | {row['interspec']:.3f} | {row['paired_delta_pct']:+.2f}% | {row['paired_min_pct']:+.2f}% to {row['paired_max_pct']:+.2f}% | {row['repetitions']} |")
    lines += ['', 'For rsync and YAML, a positive delta means increased runtime: 100 × (InterSpec / RLBox − 1). For memcached and nginx, a positive delta means lost throughput: 100 × (1 − InterSpec / RLBox). The CSV also provides paired inverse-throughput overhead for conversions; it is not measured request latency. No geometric mean mixes these two definitions.', '',
              'Small and negative differences in these environments do not establish speedups. The rsync option-parse case is especially sensitive to process startup and timing noise.', '',
              '## Measurement and validation scope', '',
              '* Rsync: 15 paired repetitions per workload; the main workload is a 194 MiB local transfer. Application corruption validation rejects 12 invalid pointers. The remaining two workloads are secondary checks.',
              '* YAML: the selected newer hosted run uses an exactly 1 MiB document and 1,000 parses per timed run, with 15 paired repetitions and two warmups. Outputs match across all four variants. Four invalid pointer controls reject and the same-type substitution control is accepted as expected.',
              '* Memcached: all 50 deployment cases pass. The six-scenario table uses the existing smoke protocol: one-second measurements, 0.3-second warmups, and three paired repetitions. Every timed run is free of client errors and logger/LRU drops. These rows do not satisfy the planned 30-second, 15-repetition publication protocol. Tracking-only is absent from this six-scenario matrix; do not substitute values from a different run.',
              f"* Memcached's timed write-heavy InterSpec runs record moves_to_warm counter deltas of {', '.join(map(str, write_lru))}, all with zero LRU drops. These application counters establish LRU activity but are not direct counts of SP3 validations. The separate short diagnostic profile still has zero checks and remains unsuitable for check-cost correlation.",
              '* Nginx: all 24 application cases pass, including two-worker operation and two graceful reloads for Native and InterSpec. The performance matrix has 100 connections, 30-second windows, three-second warmups, five paired repetitions, and four/eight wrk client threads. Performance uses one nginx event loop, not four/eight nginx workers. Every response passes validation and every timed binary matches the correctness gate.', '',
              '## Source datasets', '']
    for path in sources:
        relative = str(path.relative_to(ROOT))
        lines.append(f'* [{relative}]({relative})')
    lines += ['', 'Source SHA-256 values and the machine-readable table are under `evaluation/results/selected/`. Original artifacts and per-run provenance are retained alongside the source CSVs. Older reference runs remain separately identified.', '',
              '## Remaining publication work', '',
              '1. Run the selected workloads on controlled hardware with recorded CPU affinity and power policy, sufficient repetitions, and load-generator capacity checks. Memcached especially needs its longer planned measurement protocol.',
              '2. Extend the memcached write-heavy diagnostic profile until counters demonstrate protected LRU activity. Its current 1,000-operation profile observes zero checks and is excluded from check-cost correlation.',
              '3. Collect the memcached Native-to-RLBox boundary-cost breakdown. Existing primitive measurements do not separately quantify transitions, copies, or wrapper synchronization.',
              '4. Review and merge the draft implementation stack. These measurements cover the selected Extended-SP3 integrations, not all ten manuscript boundaries or a fresh evaluation of all original policies.', '']
    args.output.write_text('\n'.join(lines))
    print(f'Validated {len(output)} workload rows from {len(sources)} raw datasets: {args.output}')


if __name__ == '__main__':
    main()
