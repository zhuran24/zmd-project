#!/usr/bin/env python3
"""复核83 编码一（CP-SAT）：单根供电桩覆盖的在产制造单位加权计数上界。

规则取法（快照规则）：供电桩 2x2，以中心为原点 12x12 范围内有需电单位一部分即供电。
平移后覆盖范围为 [0,11]^2，桩身 [5,6]^2。
在产机器两条端口边各需至少一个邻格是运输单位 -> 该邻格不被任一选中机身或桩身占据（放宽）。
小 3x3（权 2）、中 5x5（权 3）端口轴可横可竖；大 6x4 端口在长边（权 3）。
普通模型：平面无界；占边模型：机身与可用端口邻格都在 x<=6（第69列在右边界外，或第0列为仓库取货口）。
写法与推导81C不同：每格设“空”布尔量 free[g]，端口约束写成 x_i => OR(free[g])。
用法：pillar_cpsat.py <ordinary|edge> <objective: weight|count> <threshold> [cap]
  判定“是否存在目标值 >= threshold 的选法”。
"""
import sys, json, time, os
from ortools.sat.python import cp_model

mode, obj, thr = sys.argv[1], sys.argv[2], int(sys.argv[3])
cap = int(sys.argv[4]) if len(sys.argv) > 4 else (23 if mode == 'ordinary' else 14)
XMAX = 6 if mode == 'edge' else None
PILLAR = {(5, 5), (5, 6), (6, 5), (6, 6)}

shapes = []  # (name, w, h, weight, axis) axis 'H': ports on left/right edges; 'V': bottom/top
for ax in 'HV':
    shapes.append(('S', 3, 3, 2, ax))
    shapes.append(('M', 5, 5, 3, ax))
shapes.append(('L', 6, 4, 3, 'V'))  # 6 wide x 4 tall, long edges are top/bottom
shapes.append(('L', 4, 6, 3, 'H'))  # 4 wide x 6 tall, long edges are left/right

places = []
for name, w, h, wt, ax in shapes:
    for x0 in range(1 - w, 12):
        for y0 in range(1 - h, 12):
            body = {(x, y) for x in range(x0, x0 + w) for y in range(y0, y0 + h)}
            if body & PILLAR:
                continue
            if not any(0 <= x <= 11 and 0 <= y <= 11 for x, y in body):
                continue
            if XMAX is not None and max(x for x, _ in body) > XMAX:
                continue
            if ax == 'H':
                sides = [[(x0 - 1, y) for y in range(y0, y0 + h)], [(x0 + w, y) for y in range(y0, y0 + h)]]
            else:
                sides = [[(x, y0 - 1) for x in range(x0, x0 + w)], [(x, y0 + h) for x in range(x0, x0 + w)]]
            ok = True
            usable_sides = []
            for sd in sides:
                u = [g for g in sd if g not in PILLAR and (XMAX is None or g[0] <= XMAX)]
                if not u:
                    ok = False
                    break
                usable_sides.append(u)
            if not ok:
                continue
            places.append((name, wt, frozenset(body), usable_sides))

cells = set()
for _, _, body, sides in places:
    cells |= body
    for sd in sides:
        cells |= set(sd)
m = cp_model.CpModel()
x = [m.NewBoolVar(f'x{i}') for i in range(len(places))]
cover = {g: [] for g in cells}
for i, (_, _, body, _) in enumerate(places):
    for g in body:
        cover[g].append(i)
free = {}
for g in cells:
    free[g] = m.NewBoolVar(f'f{g}')
    if cover[g]:
        # free[g] == not any(x_i covering g); at most one covering
        m.AddAtMostOne([x[i] for i in cover[g]])
        m.Add(sum(x[i] for i in cover[g]) + free[g] == 1)
    else:
        m.Add(free[g] == 1)
for i, (_, _, _, sides) in enumerate(places):
    for sd in sides:
        m.AddBoolOr([free[g] for g in sd]).OnlyEnforceIf(x[i])
m.Add(sum(x) <= cap)
if obj == 'weight':
    m.Add(sum(places[i][1] * x[i] for i in range(len(places))) >= thr)
else:
    m.Add(sum(x) >= thr)
s = cp_model.CpSolver()
s.parameters.num_workers = int(os.environ.get('WORKERS', '4'))
s.parameters.max_time_in_seconds = float(os.environ.get('TLIM', '3000'))
t0 = time.time()
st = s.Solve(m)
res = {'mode': mode, 'objective': obj, 'threshold': thr, 'cap': cap, 'placements': len(places),
       'status': s.StatusName(st), 'wall': round(time.time() - t0, 1)}
if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
    sel = [i for i in range(len(places)) if s.Value(x[i])]
    res['found'] = [(places[i][0], sorted(places[i][2])[0]) for i in sel]
    res['weight'] = sum(places[i][1] for i in sel)
    res['count'] = len(sel)
print(json.dumps(res, ensure_ascii=False))
