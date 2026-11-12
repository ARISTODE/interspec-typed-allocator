#!/usr/bin/env python3
"""Validate retained runtime process output, exact grid and derived arithmetic.

This checks data integrity, not instruction retention. Archive disassembly and
inspect the timing loops separately when collecting a new compiler/build.
"""
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import median


def verify(root):
    root = Path(root)
    env = json.loads((root / 'environment.json').read_text())
    reps, iterations = env['repetitions'], env['iterations']
    if reps < 3 or iterations < 1:
        raise ValueError('invalid protocol')
    cells = {(m, p, 1) for m in ('shared_lock', 'metadata_lookup', 'check_live',
             'check_interior', 'check_wrong_type', 'remaining_bytes')
             for p in (2, 16, 256, 4096, 16384)}
    cells |= {(m, 2, 1) for m in ('type_compare', 'bounds_check')}
    cells |= {(m, 16384, 1) for m in ('allocate', 'allocate_from_site', 'release')}
    cells |= {('check_concurrent', 4096, t) for t in (1, 2, 4, 8)}
    def read(path):
        with path.open() as stream:
            return list(csv.DictReader(stream))
    rows = read(root / 'raw.csv')
    index = {(r['metric'], int(r['population']), int(r['threads']), int(r['repetition'])): r for r in rows}
    if len(rows) != len(index) or set(index) != {(*c, rep) for c in cells for rep in range(reps)}:
        raise ValueError('missing or duplicate cell')
    for rep in range(reps):
        if (root / f'{rep}.stderr').read_bytes():
            raise ValueError('unexpected process stderr')
        process = read(root / f'{rep}.stdout')
        saved = [r for r in rows if int(r['repetition']) == rep]
        if len(process) != len(saved):
            raise ValueError('process output count')
        for a, b in zip(process, saved):
            for key, value in a.items():
                differs = value != b[key] if key == 'metric' else float(value) != float(b[key])
                if differs:
                    raise ValueError('process output differs')
    groups = {}
    for r in rows:
        m, p, t = r['metric'], int(r['population']), int(r['threads'])
        count = 16384 if m in ('allocate', 'allocate_from_site', 'release') else (iterations // 4 + 1) * t if m == 'check_concurrent' else iterations
        ns = int(r['total_ns'])
        if int(r['operations']) != count or ns <= 0:
            raise ValueError('invalid operations or timer')
        if not math.isclose(float(r['ns_per_op']), ns / count, rel_tol=0, abs_tol=5.01e-10):
            raise ValueError('ns/op arithmetic')
        if not math.isclose(float(r['ops_per_sec']), count * 1e9 / ns, rel_tol=1e-14, abs_tol=.501):
            raise ValueError('ops/sec arithmetic')
        groups.setdefault((m, p, t), []).append(float(r['ns_per_op']))
    summaries = json.loads((root / 'summary.json').read_text())
    seen = set()
    for s in summaries:
        key = s['metric'], s['population'], s['threads']
        if key not in cells or key in seen or s['n'] != reps:
            raise ValueError('summary coverage')
        seen.add(key)
        for field, fn in (('median', median), ('min', min), ('max', max)):
            if not math.isclose(s['ns_per_op_' + field], fn(groups[key]), rel_tol=0, abs_tol=1e-10):
                raise ValueError('summary arithmetic')
    if seen != cells:
        raise ValueError('summary coverage')
    files = [root / name for name in ('raw.csv', 'summary.json', 'environment.json')]
    files += [root / f'{rep}.{ext}' for rep in range(reps) for ext in ('stdout', 'stderr')]
    return dict(validated=True, samples=len(rows), configurations=len(cells), repetitions=reps,
                publication_ready=False, instruction_retention='requires separate disassembly review',
                sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
