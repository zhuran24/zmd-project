"""第二轮独立复算：单根供电桩覆盖的在产制造单位台数 / 加权数上界（局部放宽）。
桩身格 (5..6)x(5..6)，供电范围格 0..11 x 0..11。
机身：3x3、5x5（两种端口轴），6x4（上下长边端口）、4x6（左右长边端口）。
在产机器：两条端口边外侧各至少一个邻格既非桩身、又不被所选机身占用、且可用。
mode general：全平面可用；wall：只有 x<=6 的格可用（占第 69 列/第 1 列等经平移反射）；
corner：x<=6 且 y<=6。
不加任何台数上限（除非 --cap）。
"""
import sys, itertools, json
from ortools.sat.python import cp_model

mode = sys.argv[1]
obj = sys.argv[2]           # count / weight
cap = int(sys.argv[3]) if len(sys.argv) > 3 else None
atleast = int(sys.argv[4]) if len(sys.argv) > 4 else None

POLE = {(5, 5), (6, 5), (5, 6), (6, 6)}
def usable(c):
    x, y = c
    if mode == 'general':
        return True
    if mode == 'wall':
        return x <= 6
    if mode == 'corner':
        return x <= 6 and y <= 6
shapes = []  # (cat, w, h, sides_fn)
for cat, s in (('S', 3), ('M', 5)):
    shapes.append((cat, s, s, 'H'))  # ports on left/right
    shapes.append((cat, s, s, 'V'))  # ports on bottom/top
shapes.append(('L', 6, 4, 'V'))
shapes.append(('L', 4, 6, 'H'))
W = {'S': 2, 'M': 3, 'L': 3}
opts = []
for cat, w, h, ax in shapes:
    for x in range(-w + 1, 12):
        for y in range(-h + 1, 12):
            cells = [(x + i, y + j) for i in range(w) for j in range(h)]
            if not any(0 <= a <= 11 and 0 <= b <= 11 for a, b in cells):
                continue
            if any(c in POLE or not usable(c) for c in cells):
                continue
            if ax == 'H':
                s1 = [(x - 1, y + j) for j in range(h)]; s2 = [(x + w, y + j) for j in range(h)]
            else:
                s1 = [(x + i, y - 1) for i in range(w)]; s2 = [(x + i, y + h) for i in range(w)]
            s1 = [c for c in s1 if usable(c) and c not in POLE]
            s2 = [c for c in s2 if usable(c) and c not in POLE]
            if s1 and s2:
                opts.append((cat, cells, s1, s2))
m = cp_model.CpModel()
u = [m.NewBoolVar('') for _ in opts]
covers = {}
for i, (_, cells, _, _) in enumerate(opts):
    for c in cells:
        covers.setdefault(c, []).append(i)
occ = {}
for c, l in covers.items():
    v = m.NewBoolVar('')
    m.Add(sum(u[i] for i in l) == v)
    occ[c] = v
for i, (_, _, s1, s2) in enumerate(opts):
    for s in (s1, s2):
        free = [occ[c].Not() for c in s if c in occ]
        if len(free) < len(s):
            continue  # 有格从不被占
        m.AddBoolOr(free).OnlyEnforceIf(u[i])
cnt = sum(u)
wt = sum(W[o[0]] * u[i] for i, o in enumerate(opts))
if cap is not None:
    m.Add(cnt <= cap)
e = cnt if obj == 'count' else wt
if atleast is not None:
    m.Add(e >= atleast)
else:
    m.Maximize(e)
s = cp_model.CpSolver(); s.parameters.num_workers = 8; s.parameters.max_time_in_seconds = 1800
st = s.Solve(m)
out = dict(mode=mode, obj=obj, cap=cap, atleast=atleast, n=len(opts), status=s.StatusName(st))
if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
    out['value'] = s.Value(e); out['bound'] = s.BestObjectiveBound() if atleast is None else None
    out['count'] = s.Value(cnt); out['weight'] = s.Value(wt)
    out['sel'] = sorted((o[0], o[1][0]) for i, o in enumerate(opts) if s.Value(u[i]))
print(json.dumps(out, ensure_ascii=False))
