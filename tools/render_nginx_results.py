#!/usr/bin/env python3
"""Render observed nginx evidence without changing its completion status."""
import argparse
import csv
import json
from pathlib import Path
import statistics


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--results',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    gate=json.loads((a.results/'correctness/summary.json').read_text())
    timing=a.results/('performance' if (a.results/'performance').is_dir() else 'reference')
    env=json.loads((timing/'environment.json').read_text())
    summary=json.loads((timing/'summary.json').read_text())
    with (timing/'samples.csv').open(newline='') as stream:
        rows=list(csv.DictReader(stream))
    assert gate['passed'] and all(c['passed'] for c in gate['cases'])
    assert len(rows)==4*env['repetitions']*len(env['threads'])
    assert all(int(r['bad'])==0 and int(r['validated'])==int(r['requests']) for r in rows)
    profile=next(c['detail'] for c in gate['cases'] if c['name']=='check-frequency')
    core_log=a.results/'core-tests.log'
    core_ok=core_log.is_file() and '20/20' in core_log.read_text() and '100% tests passed, 0 tests failed' in core_log.read_text()
    lines=['# Nginx/PCRE application results','',
           'The actual pinned nginx server runs PCRE 8.45 inside RLBox wasm2c. '
           'These shared-environment timings are reference measurements, not controlled-hardware publication results.','',
           '## Correctness and enforcement','',
           f"The application suite passes **{len(gate['cases'])}/{len(gate['cases'])} cases**. All five variants pass normal HTTP routing, "
           'named/optional/case-insensitive captures, rewrites, maps, non-matches, HEAD, keepalive, and concurrent requests. Invalid regex configuration fails in every variant.','',
           '* Eight source-injected invalid pointers reject on actual name-table and capture-offset paths: wrong type, untracked, released, and excessive extent on each path.',
           '* A structurally invalid capture offset in a valid typed allocation rejects before nginx uses it.',
           '* Two valid same-type substitutions remain accepted with preserved contents, as expected from the current identity limitation.',
           f"* The routing profile executes {profile['sp3_checks']:,} successful metadata checks over {profile['requests']} requests: **{profile['checks_per_request']:g} checks/request**, with no typed allocations during the measured requests.",
           ('* The existing core regression suite passes 20/20.' if core_ok else
            '* Core regression execution is not recorded in this evidence directory.'),'']
    lines += ['The name-table check runs during configuration. The steady-state count consists of 17 subject-buffer checks '
              'and one capture-buffer check per selected routing request. These buffers are part of the application adapter; '
              'the measurement therefore covers the current deployment policy, including its explicit staging extensions.','']
    lines += [('Multiple-worker and graceful-reload application tests passed.' if gate['worker_reload_tested'] else
               '**Multiple-worker and graceful-reload coverage is pending.** The local suite uses one nginx event loop; the checked-in CI workflow adds worker/reload tests.'),'',
              '## Four-way reference','',
              f"Configuration: {env['connections']} connections, {env['seconds']} seconds per measurement, {env['warmup_seconds']} seconds warmup per run, "
              f"{env['repetitions']} paired repetitions, wrk thread counts {env['threads']}, nginx workers option {env['workers']} "
              '(0 means one event loop with master_process off). All HTTP status codes and response bodies were validated.','',
              '| wrk threads | Native Kreq/s | RLBox Kreq/s | Tracking Kreq/s | InterSpec Kreq/s | InterSpec vs RLBox | InterSpec vs Native | Paired InterSpec/RLBox loss range |',
              '| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |']
    for s in summary:
        m=s['median_requests_per_s']; vals=s['interspec_vs_rlbox_paired_pct']
        lines.append(f"| {s['threads']} | {m['native']/1000:.3f} | {m['rlbox-only']/1000:.3f} | {m['tracked-no-check']/1000:.3f} | {m['interspec']/1000:.3f} | {s['interspec_vs_rlbox_pct']:+.2f}% | {s['interspec_vs_native_pct']:+.2f}% | {min(vals):+.2f}% to {max(vals):+.2f}% |")
    lines += ['', 'Percentages are medians of paired throughput-loss ratios, 100 × (1 − target / baseline). They need not equal ratios of the displayed medians. Negative values and small differences are not treated as established speedups.','',
              '| wrk threads | Variant | Median p99 µs | Median startup ms | Median CPU µs/request | Median aggregate RSS KiB |',
              '| ---: | --- | ---: | ---: | ---: | ---: |']
    for threads in env['threads']:
        for variant in ['native','rlbox-only','tracked-no-check','interspec']:
            subset=[r for r in rows if int(r['threads'])==threads and r['variant']==variant]
            def median(key):
                vals=[float(r[key]) for r in subset if r[key]]
                return f'{statistics.median(vals):.3f}' if len(vals)==len(subset) else 'unavailable'
            lines.append(f"| {threads} | {variant} | {median('p99_us')} | {median('startup_ms')} | {median('server_cpu_us_per_request')} | {median('server_rss_kib')} |")
    lines += ['', 'Per-process CPU/RSS may be unavailable in a restricted PID namespace. Missing values are preserved, not replaced by zero. '
              'The load generator and server share the host; client capacity and scheduler interference still require controlled-host evaluation.','',
              '## Evidence and scope','',
              'Raw samples, generated summaries, correctness cases, per-case traces, HTTP configurations, wrk outputs, binary hashes, and environment metadata are retained under `evaluation/results/nginx-pcre/`. '
              'Every timed binary matches the correctness gate. The implementation and reproduction steps are in [NGINX_DEPLOYMENT.md](NGINX_DEPLOYMENT.md).','',
              'This deployment is PCRE8 without JIT. It does not complete PCRE2/OpenSSL/TLS evaluation, general threaded PCRE API support, or same-type object identity enforcement. ' +
              ('The worker/reload CI gate passed; controlled-hardware publication runs remain outstanding.' if gate['worker_reload_tested'] else
               'The nginx worker/reload CI gate and controlled-hardware publication runs remain separate from local functional completion.'),'']
    a.output.write_text('\n'.join(lines))


if __name__=='__main__': main()
