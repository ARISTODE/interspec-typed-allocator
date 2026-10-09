#!/usr/bin/env python3
"""Four-way paired wrk measurements, gated by binary-matched correctness."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
from nginx_common import Server

VARIANTS = ['native', 'rlbox-only', 'tracked-no-check', 'interspec']


def process_stats(pid):
    """Aggregate the live nginx master/worker process tree (RSS includes sharing)."""
    # A shared procfs may expose host PIDs while Popen returns namespace PIDs.
    # Never accidentally measure an unrelated process with the same number.
    if int(Path('/proc/self/stat').read_text().split()[0]) != os.getpid():
        return {'cpu_s':None,'rss_kib':None,'processes':None,
                'unavailable':'procfs exposes a different PID namespace'}
    pids = [pid]
    cpu = 0.0
    rss = 0
    for process in pids:
        base = Path('/proc') / str(process)
        try:
            fields = (base/'stat').read_text().rsplit(')', 1)[1].split()
            status = (base/'status').read_text()
            children = (base / 'task' / str(process) / 'children').read_text()
        except (FileNotFoundError, PermissionError):
            return {'cpu_s':None,'rss_kib':None,'processes':None,
                    'unavailable':'process counters not exposed in this PID namespace'}
        cpu += (int(fields[11]) + int(fields[12])) / os.sysconf('SC_CLK_TCK')
        for line in status.splitlines():
            if line.startswith('VmRSS:'): rss += int(line.split()[1])
        pids.extend(int(child) for child in children.split())
    return {'cpu_s':cpu,'rss_kib':rss,'processes':len(pids)}


LUA = '''threads = {}
function setup(thread) table.insert(threads, thread) end
function init(args) bad = 0; validated = 0 end
function response(status, headers, body)
  validated = validated + 1
  if status ~= 200 or body ~= "item:123:alpha" then bad = bad + 1 end
end
function done(summary, latency, requests)
  local failed = 0; local checked = 0
  for _, t in ipairs(threads) do
    failed = failed + t:get("bad"); checked = checked + t:get("validated")
  end
  io.write(string.format('INTERSPEC_WRK {"requests":%d,"duration_us":%d,"validated":%d,"bad":%d,"p50_us":%.3f,"p99_us":%.3f,"connect_errors":%d,"read_errors":%d,"write_errors":%d,"status_errors":%d,"timeouts":%d}\\n',
    summary.requests, summary.duration, checked, failed, latency:percentile(50), latency:percentile(99),
    summary.errors.connect, summary.errors.read, summary.errors.write, summary.errors.status, summary.errors.timeout))
end
'''


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--work', type=Path, default=Path('/tmp/interspec-nginx-deployment'))
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--correctness', type=Path, required=True)
    p.add_argument('--wrk', default='wrk')
    p.add_argument('--seconds', type=int, default=30)
    p.add_argument('--repetitions', type=int, default=5)
    p.add_argument('--warmup-seconds', type=int, default=3)
    p.add_argument('--threads', type=int, nargs='+', default=[4,8])
    p.add_argument('--connections', type=int, default=100)
    p.add_argument('--workers', type=int, default=0)
    p.add_argument('--server-cpus')
    p.add_argument('--client-cpus')
    a = p.parse_args()
    assert a.seconds > 0 and a.repetitions > 0 and a.warmup_seconds >= 0
    assert all(t > 0 and t <= a.connections for t in a.threads)
    a.out.mkdir(parents=True, exist_ok=True)
    gate=json.loads(a.correctness.read_text())
    assert gate['passed'] and len(gate['cases']) >= 21 and all(c['passed'] for c in gate['cases'])
    hashes={v:hashlib.sha256((a.work/'bin'/f'nginx-{v}').read_bytes()).hexdigest() for v in VARIANTS}
    assert all(gate['binary_sha256'][v] == hashes[v] for v in VARIANTS), 'binaries differ from correctness gate'
    script=a.out/'validate.lua'
    script.write_text(LUA)
    metadata={**vars(a), 'platform':platform.platform(), 'cpu_count':os.cpu_count(),
              'affinity': sorted(os.sched_getaffinity(0)), 'binary_sha256':hashes,
              'hosted_ci':os.environ.get('GITHUB_ACTIONS','false'),
              'measurement':'closed-loop wrk with every response body checked; 16 preceding regex locations',
              'publication_ready':False, 'build_manifest':json.loads((a.work/'build-manifest.json').read_text())}
    for name in ['/sys/fs/cgroup/cpu.max','/sys/fs/cgroup/memory.max']:
        try: metadata[name]=Path(name).read_text().strip()
        except OSError: pass
    (a.out/'environment.json').write_text(json.dumps(metadata,default=str,indent=2)+'\n')
    rows=[]
    rng=random.Random(1729)
    def wrk(server, threads, seconds, directory, label):
        command=[a.wrk,'--latency',f'-t{threads}',f'-c{a.connections}',f'-d{seconds}s',
                 '-s',str(script.resolve()),f'http://127.0.0.1:{server.port}/items/123/alpha']
        if a.client_cpus: command=['taskset','-c',a.client_cpus,*command]
        result=subprocess.run(command,text=True,capture_output=True,timeout=seconds+30)
        (directory/f'{label}.stdout').write_text(result.stdout)
        (directory/f'{label}.stderr').write_text(result.stderr)
        assert result.returncode == 0, result.stderr
        values=[json.loads(line.removeprefix('INTERSPEC_WRK ')) for line in result.stdout.splitlines() if line.startswith('INTERSPEC_WRK ')]
        assert len(values) == 1, result.stdout
        data=values[0]
        assert data['requests'] > 0 and data['validated'] == data['requests'], data
        assert all(data[k] == 0 for k in ['bad','connect_errors','read_errors','write_errors','status_errors','timeouts']), data
        assert server.proc.poll() is None
        return data
    for threads in a.threads:
        for repetition in range(a.repetitions):
            order=VARIANTS.copy(); rng.shuffle(order)
            for position,variant in enumerate(order):
                directory=a.out/f't{threads}-r{repetition}-{variant}'
                with Server(a.work/'bin'/f'nginx-{variant}', directory,workers=a.workers,cpu=a.server_cpus) as server:
                    if a.warmup_seconds: wrk(server,threads,a.warmup_seconds,directory,'warmup')
                    before=process_stats(server.proc.pid)
                    data=wrk(server,threads,a.seconds,directory,'measurement')
                    after=process_stats(server.proc.pid)
                    row={'threads':threads,'repetition':repetition,'order':position,'variant':variant,
                         'requests_per_s':data['requests']*1e6/data['duration_us'],
                         'server_cpu_us_per_request':(1e6*(after['cpu_s']-before['cpu_s'])/data['requests']
                             if after['cpu_s'] is not None and before['cpu_s'] is not None else None),
                         'server_rss_kib':after['rss_kib'],
                         'process_stats_unavailable':after.get('unavailable',''),
                         'startup_ms':server.startup_ms,**data}
                assert 'INTERSPEC_REJECT' not in server.logpath.read_text()
                rows.append(row)
                with (a.out/'samples.csv').open('w') as f:
                    writer=csv.DictWriter(f,fieldnames=rows[0].keys()); writer.writeheader(); writer.writerows(rows)
                print(json.dumps(row),flush=True)
    summaries=[]
    for threads in a.threads:
        subset=[r for r in rows if r['threads'] == threads]
        paired={rep:{r['variant']:r['requests_per_s'] for r in subset if r['repetition'] == rep} for rep in range(a.repetitions)}
        assert all(set(p) == set(VARIANTS) for p in paired.values())
        def loss(target,baseline):
            return statistics.median(100*(1-p[target]/p[baseline]) for p in paired.values())
        summaries.append({'threads':threads,'repetitions':a.repetitions,
            'median_requests_per_s':{v:statistics.median(r['requests_per_s'] for r in subset if r['variant']==v) for v in VARIANTS},
            'rlbox_vs_native_pct':loss('rlbox-only','native'),
            'tracking_vs_rlbox_pct':loss('tracked-no-check','rlbox-only'),
            'validation_vs_tracking_pct':loss('interspec','tracked-no-check'),
            'interspec_vs_rlbox_pct':loss('interspec','rlbox-only'),
            'interspec_vs_native_pct':loss('interspec','native'),
            'interspec_vs_rlbox_paired_pct':[100*(1-p['interspec']/p['rlbox-only']) for p in paired.values()]})
    (a.out/'summary.json').write_text(json.dumps(summaries,indent=2)+'\n')
    print(json.dumps(summaries,indent=2),flush=True)


if __name__ == '__main__': main()
