"""Compare SP3 field classes of the tables' analysis (old) and variant paper_counting_rule_sp3_opacity (new).
usage: sp3op_compare.py BENCHMARK OLD_CSV[.gz] NEW_CSV [--list N]"""
import collections, csv, gzip, sys
def load(path):
    rows = csv.DictReader(gzip.open(path, 'rt') if path.endswith('.gz') else open(path))
    slots = {}
    for r in rows:
        k = (r['function'], r['binding_kind'], r['binding_id'], r['slot_path'])
        s = slots.setdefault(k, dict(u=False, t=False, cut=False, T=False, U=False, N=False, ptrs=0))
        s['u'] |= r['u_influenced'] == '1'; s['t'] |= r['t_uses'] == '1'; s['cut'] |= r['flow_cut'] == '1'
        s['T'] |= r['sp3_target_t'] == '1'; s['U'] |= r['sp3_target_u'] == '1'; s['N'] |= r['sp3_target_null'] == '1'
    return slots
def classes(slots):
    sp3 = {k: v for k, v in slots.items() if v['u'] and v['t']}
    by = collections.defaultdict(list)
    for (f, bk, bi, p), v in sp3.items(): by[(f, bk, bi)].append((p, v))
    out = {}
    for (f, bk, bi, p) in slots:
        below = [x for q, x in by.get((f, bk, bi), []) if p == '' or q == p or q.startswith(p + '/')]
        if not below: continue
        unknown = any(not (x['T'] or x['U'] or x['N']) for x in below); cut = any(x['cut'] for x in below)
        mixed = any(x['T'] and x['U'] for x in below)
        out[(f, bk, bi, p)] = ('unresolved' if unknown or cut else ('inferred, mixed T and U' if mixed else 'inferred'))
    return out
b, old_path, new_path = sys.argv[1:4]
n = int(sys.argv[sys.argv.index('--list') + 1]) if '--list' in sys.argv else 0
old, new = classes(load(old_path)), classes(load(new_path))
co, cn = collections.Counter(old.values()), collections.Counter(new.values())
print(f"{b}: old need SP3 {len(old)} {dict(co)} | new need SP3 {len(new)} {dict(cn)}")
moves = collections.Counter((c, new.get(k, 'no longer needs SP3')) for k, c in old.items())
for (a, c), v in sorted(moves.items()): print(f"   {a:26s} -> {c:26s} {v}")
extra = [k for k in new if k not in old]
if extra: print(f"   needs SP3 only in new: {len(extra)}")
if n:
    left = [k for k, c in new.items() if c != 'inferred']
    for k in sorted(left)[:n]: print('   left:', new[k], k)
