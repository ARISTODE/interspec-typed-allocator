"""Pointer columns of the paper's integrity table (tracker C2, run 20) from pointer_slots_classification.csv of each boundary.
Need SP3: fields with a pointer at or below them that U may modify and T dereferences.
Inferred: every such pointer has one expected domain (T or U, possibly also NULL) and is not at the depth limit.
usage: sp3_table.py OUT_DIR BOUNDARY=CSV ..."""
import collections, csv, gzip, json, sys
from pathlib import Path
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
rows = []
for arg in sys.argv[2:]:
    b, path = arg.split('=', 1)
    slots = {}
    for r in csv.DictReader(gzip.open(path, 'rt') if path.endswith('.gz') else open(path)):
        k = (r['function'], r['binding_kind'], r['binding_id'], r['slot_path'])
        s = slots.setdefault(k, dict(u=False, t=False, cut=False, T=False, U=False, N=False))
        s['u'] |= r['u_influenced'] == '1'; s['t'] |= r['t_uses'] == '1'; s['cut'] |= r['flow_cut'] == '1'
        s['T'] |= r['sp3_target_t'] == '1'; s['U'] |= r['sp3_target_u'] == '1'; s['N'] |= r['sp3_target_null'] == '1'
    sp3 = {k: v for k, v in slots.items() if v['u'] and v['t']}
    by = collections.defaultdict(list)
    for (f, bk, bi, p), v in sp3.items(): by[(f, bk, bi)].append((p, v))
    need, inferred, other = 0, 0, []
    for k in slots:
        f, bk, bi, p = k
        below = [x for q, x in by.get((f, bk, bi), []) if p == '' or q == p or q.startswith(p + '/')]
        if not below: continue
        need += 1
        single = all((x['T'] or x['U']) and not (x['T'] and x['U']) and not x['cut'] for x in below)
        if single: inferred += 1
        else:
            kind = 'depth limit' if any(x['cut'] for x in below) else ('T and U' if any(x['T'] and x['U'] for x in below) else 'no domain')
            other.append((f, bk, bi, p, kind))
    ptrs = len(slots)
    rows.append(dict(boundary=b, pointer_fields=ptrs, need_sp3=need, inferred=inferred, not_inferred=need - inferred,
                     pointer_coverage=(ptrs - (need - inferred)) / ptrs if ptrs else 1.0, others=other))
with open(out / 'sp3_columns.csv', 'w', newline='') as h:
    w = csv.writer(h); w.writerow(['boundary', 'pointer_fields', 'need_sp3', 'inferred', 'domain_stated_by_developer', 'pointer_coverage'])
    for r in rows: w.writerow([r['boundary'], r['pointer_fields'], r['need_sp3'], r['inferred'], r['not_inferred'], f"{r['pointer_coverage']:.6f}"])
with open(out / 'not_inferred_fields.txt', 'w') as h:
    for r in rows:
        for o in r['others']: h.write(f"{r['boundary']}\t" + "\t".join(o) + "\n")
for r in rows:
    print(f"{r['boundary']:20s} ptrs {r['pointer_fields']:7d} need {r['need_sp3']:4d} inferred {r['inferred']:4d} other {r['not_inferred']:3d} cov {100*r['pointer_coverage']:.4f}%")
print('total need', sum(r['need_sp3'] for r in rows), 'inferred', sum(r['inferred'] for r in rows), 'other', sum(r['not_inferred'] for r in rows),
      'mean cov', f"{100*sum(r['pointer_coverage'] for r in rows)/len(rows):.4f}%")
