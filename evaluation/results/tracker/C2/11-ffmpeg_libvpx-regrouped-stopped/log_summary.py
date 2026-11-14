import re,sys
prev=None;prevline='';gaps=[]
big=[]
for line in open(sys.argv[1],errors='replace'):
    m=re.match(r'\[[^\]]+\] \((\d+)s\)\s*(.*)',line)
    if not m: continue
    t=int(m.group(1)); txt=m.group(2)
    if prev is not None and t-prev>=20: gaps.append((t-prev,prev,prevline[:230]))
    if not txt.startswith('Pausing') and not txt.startswith('Unpausing'):
        prevline=txt
    prev=t
    r=re.search(r'(\S+) (?:has|with) (\d+) rows',txt)
    if r and int(r.group(2))>3_000_000: big.append((int(r.group(2)),t,r.group(1)[:150]))
print('GAPS');[print(g) for g in sorted(gaps,reverse=True)[:14]]
print('BIG');[print(b) for b in sorted(big,reverse=True)[:25]]
