#!/usr/bin/env python3
"""Split the pointer fields that need SP3 by why they are resolved or not.
usage: unresolved_causes.py pointer_slots_classification.csv[.gz]
Reproduces export_node_policy_surface.py's sp3_pointer_* counts and adds the cause."""
import csv, gzip, collections, sys
path=sys.argv[1]
rows=csv.DictReader(gzip.open(path,'rt') if path.endswith('.gz') else open(path))
slots={}
for r in rows:
    k=(r['function'],r['binding_kind'],r['binding_id'],r['slot_path'])
    s=slots.setdefault(k, dict(u_infl=False,t_uses=False,cut=False,known=False))
    s['u_infl']|=r['u_influenced']=='1'; s['t_uses']|=r['t_uses']=='1'; s['cut']|=r['flow_cut']=='1'
    s['known']|=(r['sp3_target_t']=='1' or r['sp3_target_u']=='1' or r['sp3_target_null']=='1')
sp3={k:v for k,v in slots.items() if v['u_infl'] and v['t_uses']}
by=collections.defaultdict(list)
for (f,bk,bi,p),v in sp3.items(): by[(f,bk,bi)].append((p,v))
def anc(a,d): return a=='' or d==a or d.startswith(a+'/')
res=collections.Counter(); perfn=collections.defaultdict(collections.Counter)
for (f,bk,bi,p),v in slots.items():
    d=[x for q,x in by.get((f,bk,bi),[]) if anc(p,q)]
    if not d: continue
    unk=any(not x['known'] for x in d); cut=any(x['cut'] for x in d)
    c='resolved' if not unk and not cut else ('unknown domain and depth limit' if unk and cut else ('unknown domain only' if unk else 'depth limit only'))
    res[c]+=1; perfn[f][c]+=1
print(f"pointer fields {len(slots):,}; need SP3 {sum(res.values()):,}; " + "; ".join(f"{k} {v:,}" for k,v in sorted(res.items())))
print(f"SP3 pointers: {len(sp3):,}; at depth limit {sum(v['cut'] for v in sp3.values()):,}; unknown domain {sum(not v['known'] for v in sp3.values()):,}")
for f,c in sorted(perfn.items(), key=lambda kv:-(sum(kv[1].values())-kv[1]['resolved'])):
    if sum(c.values())-c['resolved']: print(f"  {f}: " + ", ".join(f"{k} {v}" for k,v in sorted(c.items())))
