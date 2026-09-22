import json, sys
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
# count per type: number of machines, in-adjacent free cells
from collections import Counter
T = set(free)
for k in F.BOUNDS:
    cnt=0; tot_in=0; tot_out=0
    for i,(kk, ax, ay, w, h, s) in enumerate(res['units']):
        if kk!=k: continue
        cnt+=1
        so=F.OPP[s]
        ni=sum(1 for (ex,ey) in F.edge_cells(ax,ay,w,h,s) if (ex+F.DIRS[s][0],ey+F.DIRS[s][1]) in T)
        no=sum(1 for (ex,ey) in F.edge_cells(ax,ay,w,h,so) if (ex+F.DIRS[so][0],ey+F.DIRS[so][1]) in T)
        tot_in+=min(ni*20, F.BOUNDS[k][1]); tot_out+=min(no*20,F.BOUNDS[k][3])
    print(k, cnt, 'max in', tot_in, 'need', F.TOT[k][0], 'max out', tot_out, 'need', F.TOT[k][1])
def test(name, arcs2):
    ok, S, d = F.feasible(arcs2); print(name, ok, d)
test('all', arcs)
test('no TOT lower', [(u,v,(0 if (u in ('S','T') or v in ('S','T')) and not (isinstance(v,tuple) and v[0]=='ci') else lo),hi) for (u,v,lo,hi) in arcs])
test('no machine lower', [(u,v,(0 if (isinstance(u,tuple) and u[0] in ('mi','Kout')) else lo),hi) for (u,v,lo,hi) in arcs])
