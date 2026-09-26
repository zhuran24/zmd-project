#!/usr/bin/env python3
"""复核83 编码二（scipy.optimize.milp / HiGHS）：同一单桩上界，另一套写法。
机身按“中心坐标+半宽”生成，端口邻格用机身外侧一圈按方向筛；
约束写成线性：x_i + sum_{g in S} occ(g) <= |S|，occ(g)=sum x_j（j 盖住 g）。
另设 occ(g)<=1。目标直接最大化加权计数（普通模型）或台数，报告最优值与界。
用法：pillar_milp.py <ordinary|edge> <weight|count> [cap] """
import sys, json, time
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import lil_matrix

mode, obj = sys.argv[1], sys.argv[2]
cap = int(sys.argv[3]) if len(sys.argv) > 3 else (23 if mode == 'ordinary' else 14)
lim = 6 if mode == 'edge' else 10 ** 9
pil = {(x, y) for x in (5, 6) for y in (5, 6)}
cov = {(x, y) for x in range(12) for y in range(12)}

kinds = [(3, 3, 2, 'lr'), (3, 3, 2, 'bt'), (5, 5, 3, 'lr'), (5, 5, 3, 'bt'), (6, 4, 3, 'bt'), (4, 6, 3, 'lr')]
P = []
for (w, h, wt, ax) in kinds:
    for cx in range(-w, 12 + w):
        for cy in range(-h, 12 + h):
            body = frozenset((cx + i, cy + j) for i in range(w) for j in range(h))
            if not (body & cov) or (body & pil):
                continue
            if max(x for x, _ in body) > lim:
                continue
            ring = {(x + dx, y + dy) for (x, y) in body for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))} - body
            if ax == 'lr':
                s1 = [g for g in ring if g[0] == cx - 1]
                s2 = [g for g in ring if g[0] == cx + w]
            else:
                s1 = [g for g in ring if g[1] == cy - 1]
                s2 = [g for g in ring if g[1] == cy + h]
            s1 = [g for g in s1 if g not in pil and g[0] <= lim]
            s2 = [g for g in s2 if g not in pil and g[0] <= lim]
            if not s1 or not s2:
                continue
            P.append((wt, body, s1, s2))
n = len(P)
cells = sorted({g for p in P for g in p[1]})
cid = {g: k for k, g in enumerate(cells)}
rows = []
# occ <= 1
A1 = lil_matrix((len(cells), n))
for i, p in enumerate(P):
    for g in p[1]:
        A1[cid[g], i] = 1
cons = [LinearConstraint(A1.tocsr(), -np.inf, 1)]
# port side constraints
nside = 2 * n
A2 = lil_matrix((nside, n))
ub2 = np.zeros(nside)
r = 0
cover = {}
for i, p in enumerate(P):
    for g in p[1]:
        cover.setdefault(g, []).append(i)
for i, p in enumerate(P):
    for S in (p[2], p[3]):
        A2[r, i] += 1
        for g in S:
            for j in cover.get(g, []):
                A2[r, j] += 1
        ub2[r] = len(S)
        r += 1
cons.append(LinearConstraint(A2.tocsr(), -np.inf, ub2))
cons.append(LinearConstraint(np.ones((1, n)), -np.inf, cap))
c = -np.array([p[0] if obj == 'weight' else 1 for p in P], dtype=float)
t0 = time.time()
res = milp(c, constraints=cons, integrality=np.ones(n), bounds=Bounds(0, 1),
           options={'time_limit': float(sys.argv[4]) if len(sys.argv) > 4 else 2400, 'disp': False})
out = {'mode': mode, 'objective': obj, 'cap': cap, 'placements': n, 'status': res.status, 'message': res.message,
       'best': (-res.fun if res.x is not None else None), 'dual_bound': getattr(res, 'mip_dual_bound', None),
       'wall': round(time.time() - t0, 1)}
if out['dual_bound'] is not None:
    out['dual_bound'] = -out['dual_bound']
print(json.dumps(out, ensure_ascii=False))
