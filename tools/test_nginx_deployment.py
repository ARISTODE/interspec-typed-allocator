#!/usr/bin/env python3
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from nginx_common import Server, request


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--work', type=Path, default=Path('/tmp/interspec-nginx-deployment'))
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--workers', type=int, default=0)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    cases = []
    variants = ['native', 'rlbox-only', 'tracked-no-check', 'interspec', 'diagnostics']
    paths = {'/items/123/alpha': (200, 'item:123:alpha'), '/items/0/z': (200, 'item:0:z'),
             '/CASE/AbC': (200, 'case:AbC'), '/optional/b': (200, 'optional::b'),
             '/optional/ab': (200, 'optional:a:b'), '/rewrite/hello': (200, 'rewrite:hello'),
             '/map/hello': (200, 'map:hello'), '/not-found': (404, 'missing'),
             '/items/no/alpha': (404, 'missing'), '/items/123/alpha?q=1': (200, 'item:123:alpha')}
    def record(name, fn):
        try:
            detail = fn()
            cases.append({'name': name, 'passed': True, 'detail': detail})
        except Exception as e:
            cases.append({'name': name, 'passed': False, 'error': str(e)})
        print(json.dumps(cases[-1]), flush=True)
    def normal(variant, workers=0):
        with Server(a.work/'bin'/f'nginx-{variant}', a.out/f'{variant}-w{workers}', workers=workers,
                    trace=variant == 'diagnostics') as server:
            for path, expected in paths.items():
                assert request(server.port, path) == expected, path
            assert request(server.port, '/items/7/alpha', 'HEAD') == (200, '')
            c = http.client.HTTPConnection('127.0.0.1', server.port)
            for i in range(20):
                c.request('GET', f'/items/{i}/alpha')
                r=c.getresponse()
                assert r.status == 200 and r.read() == f'item:{i}:alpha'.encode()
            c.close()
            def client(i):
                for j in range(30):
                    value=i*30+j
                    assert request(server.port, f'/items/{value}/alpha') == (200, f'item:{value}:alpha')
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(client, range(8)))
            if workers:
                original = server.conf.read_text()
                generations = []
                def worker_pids():
                    return re.findall(r'start worker process (\d+)', server.logpath.read_text())
                assert len(worker_pids()) == workers, server.logpath.read_text()[-4000:]
                generations.append(worker_pids())
                for generation in range(1, 3):
                    # A response on a new regex route proves the new configuration
                    # was loaded; a request to an unchanged route would not.
                    server.conf.write_text(original.replace('^/items/', f'^/generation{generation}/items/'))
                    server.proc.send_signal(signal.SIGHUP)
                    deadline = time.monotonic() + 10
                    while time.monotonic() < deadline:
                        assert server.proc.poll() is None, 'master exited during reload'
                        if (request(server.port, f'/generation{generation}/items/123/alpha') == (200, 'item:123:alpha')
                                and len(worker_pids()) == workers * (generation + 1)):
                            break
                        time.sleep(.05)
                    else:
                        raise AssertionError('new worker generation did not serve the updated regex route')
                    generations.append(worker_pids()[-workers:])
                    assert not set(generations[-1]).intersection(pid for group in generations[:-1] for pid in group)
                    # Exercise every fresh configuration with concurrent clients.
                    with ThreadPoolExecutor(max_workers=8) as pool:
                        replies = list(pool.map(lambda _: request(server.port, f'/generation{generation}/items/123/alpha'), range(80)))
                    assert all(reply == (200, 'item:123:alpha') for reply in replies)
                    assert request(server.port, '/items/123/alpha') == (404, 'missing')
            assert server.proc.poll() is None
        text = server.logpath.read_text()
        assert 'INTERSPEC_REJECT' not in text
        assert 'could not build' not in text and 'exited on signal' not in text
        assert '[emerg]' not in text and '[alert]' not in text
        if workers:
            started = worker_pids()
            exited = re.findall(r'worker process (\d+) exited with code 0', text)
            assert sorted(started) == sorted(exited), 'worker cleanup was incomplete'
        if variant == 'diagnostics':
            assert 'event=check' in text and 'event=allocate_from_site' in text
        return {'http_cases': len(paths) + 1, 'keepalive_requests': 20, 'concurrent_requests': 240,
                'reloads': 2 if workers else 0, 'startup_ms': server.startup_ms,
                'worker_generations': generations if workers else [],
                'concurrent_requests_after_reload': 160 if workers else 0}
    for v in variants:
        record(f'normal/{v}', lambda v=v: normal(v))
    if a.workers:
        for v in ['native', 'interspec']:
            record(f'workers-reload/{v}', lambda v=v: normal(v, a.workers))
    def invalid_config(variant):
        directory=a.out/f'invalid-{variant}'
        directory.mkdir(exist_ok=True)
        conf=directory/'nginx.conf'
        conf.write_text('events {} http { server { location ~ "[" { return 200; } } }')
        result=subprocess.run([str(a.work/'bin'/f'nginx-{variant}'), '-t', '-p', str(directory.resolve())+'/', '-c', str(conf.resolve())],capture_output=True,text=True)
        (directory/'stderr.log').write_text(result.stderr)
        assert result.returncode != 0 and 'pcre_compile() failed' in result.stderr
    for v in variants:
        record(f'invalid-config/{v}', lambda v=v: invalid_config(v))
    def fault(path, kind):
        expected={1:'wrong_type',2:'untracked',3:'untracked',4:'out_of_bounds',6:'malformed_offsets'}
        name=f'fault-{path}-{kind}'
        with Server(a.work/'bin/nginx-diagnostics',a.out/name,fault=(path,kind),trace=True,wait=path != 1 or kind == 5) as server:
            if path == 2 or kind == 5:
                try:
                    got=request(server.port, '/items/123/alpha')
                except (OSError, http.client.HTTPException):
                    got=None
                if kind == 5:
                    assert got == (200,'item:123:alpha')
                    assert server.proc.poll() is None
                    return 'same-type substitution accepted with preserved contents'
            server.proc.wait(timeout=5)
            text=server.logpath.read_text()
            assert server.proc.returncode == -signal.SIGABRT, server.proc.returncode
            assert f'reason={expected[kind]}' in text, text[-2000:]
            if kind == 3:
                assert 'event=release' in text
            return expected[kind]
    for path in [1,2]:
        for kind in [1,2,3,4,5]:
            record(f'fault/{path}/{kind}', lambda path=path,kind=kind: fault(path,kind))
    record('fault/2/6', lambda: fault(2,6))
    def profile():
        with Server(a.work/'bin/nginx-diagnostics',a.out/'check-frequency',trace=True) as server:
            start=server.logpath.stat().st_size
            for _ in range(100):
                assert request(server.port,'/items/123/alpha') == (200,'item:123:alpha')
            end=server.logpath.stat().st_size
            with server.logpath.open('rb') as f:
                f.seek(start)
                text=f.read(end-start).decode()
            checks=sum('event=check ' in line and 'result=ok' in line for line in text.splitlines())
            allocations=sum('event=allocate_from_site ' in line for line in text.splitlines())
            assert checks > 0 and allocations == 0
            return {'requests':100,'sp3_checks':checks,'checks_per_request':checks/100,
                    'typed_allocations_during_requests':allocations}
    record('check-frequency',profile)
    hashes={v:hashlib.sha256((a.work/'bin'/f'nginx-{v}').read_bytes()).hexdigest() for v in variants}
    summary={'passed': all(c['passed'] for c in cases), 'cases':cases, 'binary_sha256':hashes,
             'worker_reload_tested':bool(a.workers)}
    (a.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(f"nginx deployment: {sum(c['passed'] for c in cases)}/{len(cases)} cases passed",flush=True)
    if not summary['passed']: raise SystemExit(1)


if __name__ == '__main__': main()
