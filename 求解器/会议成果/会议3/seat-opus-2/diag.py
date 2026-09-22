import json, sys
import networkx as nx
import flowcheck as F
res = json.load(open(sys.argv[1]))
# fill every free cell with transport
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
print('bad', bad)
ok, S, deficit = F.feasible(arcs)
print('all-free-transport+bridges:', ok, deficit)
if not ok:
    # which demand nodes are in T side
    G = nx.DiGraph()
    ms = [x for x in S if isinstance(x, tuple) and x[0] in ('mi','mo')]
    print('S side sample', [x for x in S if not (isinstance(x, tuple) and x[0] in ('ci','co'))][:40])
