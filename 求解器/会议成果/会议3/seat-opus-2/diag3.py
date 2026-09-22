import json, sys
from collections import Counter
import flowcheck as F
res = json.load(open(sys.argv[1]))
occ = set()
for (k, ax, ay, w, h, s) in res['units']:
    for x in range(ax, ax+w):
        for y in range(ay, ay+h):
            occ.add((x, y))
ori, cx, cy = res['core']
for x in range(cx, cx+9):
    for y in range(cy, cy+9):
        occ.add((x, y))
blocked = set((0, y) for y in range(70)) | set((x, 0) for x in range(70))
free = [(x, y) for x in range(70) for y in range(70) if (x, y) not in occ and (x, y) not in blocked]
res2 = dict(res); res2['transport'] = free; res2['bridge_cells'] = free
arcs, bad = F.build(res2)
ok, S, d = F.feasible(arcs)
print(ok, d)
units = res['units']
c = Counter()
for x in S:
    if isinstance(x, tuple):
        if x[0] in ('mi','mo'): c[(x[0], units[x[1]][0])]+=1
        elif x[0] in ('ci','co'): c[x[0]]+=1
        else: c[x]+=1
    else: c[x]+=1
for k,v in sorted(c.items(), key=str): print(k, v)
