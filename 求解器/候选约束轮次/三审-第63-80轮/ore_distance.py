"""三审自写：第 63 轮「无协议储存箱的运输过站下限」的额外访问下界。

对 47 种共同边带排布，46 个边界原矿源口的首运输格为 (1,y)（左带）与 (x,1)（下带）。
原矿只能被 3x3 的粉碎机或精炼炉消耗，每台平均至多 1 件/tick。取任意互不重叠、避开 46 个首运输格、
左下角在 1..67 的 3x3 机身，把 46 个源口一一配到不同机身，费用为 Σ(源口首格到机身的曼哈顿距离 − 1)。
证明「费用 <= 7 不可行」：每项非负，只需考虑距离 <= 8 的配对。

两种编码：
  cpsat：机身选择变量 + 配对变量，逐格不重叠；
  highs：只建「源口 i 配机身 j」变量，逐格至多一个被选机身覆盖（scipy.optimize.milp）。
"""
import argparse
import json
import sys
import time

import field as S


def sources(eL, eB):
    return [(1, r) for r in S.band_ports(eL)] + [(c, 1) for c in S.band_ports(eB)]


def dist_to_body(s, x, y):
    dx = 0 if x <= s[0] <= x + 2 else (x - s[0] if s[0] < x else s[0] - (x + 2))
    dy = 0 if y <= s[1] <= y + 2 else (y - s[1] if s[1] < y else s[1] - (y + 2))
    return dx + dy


def domain(eL, eB, maxcost):
    src = sources(eL, eB)
    srcset = set(src)
    bodies = []
    for x in range(1, 68):
        for y in range(1, 68):
            cells = [(x + i, y + j) for i in range(3) for j in range(3)]
            if any(c in srcset for c in cells):
                continue
            ds = [dist_to_body(s, x, y) - 1 for s in src]
            if min(ds) > maxcost:
                continue
            bodies.append((x, y, cells, ds))
    return src, bodies


def solve_cpsat(eL, eB, budget, seconds, workers):
    from ortools.sat.python import cp_model
    src, bodies = domain(eL, eB, budget)
    m = cp_model.CpModel()
    u = [m.NewBoolVar('') for _ in bodies]
    a = {}
    for j, (x, y, cells, ds) in enumerate(bodies):
        for i, d in enumerate(ds):
            if d <= budget:
                a[i, j] = m.NewBoolVar('')
                m.AddImplication(a[i, j], u[j])
    for i in range(len(src)):
        m.AddExactlyOne([a[i, j] for j in range(len(bodies)) if (i, j) in a])
    for j in range(len(bodies)):
        m.Add(sum(a[i, j] for i in range(len(src)) if (i, j) in a) <= 1)
    occ = {}
    for j, (x, y, cells, ds) in enumerate(bodies):
        for c in cells:
            occ.setdefault(c, []).append(u[j])
    for c, lst in occ.items():
        if len(lst) > 1:
            m.AddAtMostOne(lst)
    m.Add(sum(bodies[j][3][i] * v for (i, j), v in a.items()) <= budget)
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = seconds
    s.parameters.num_workers = workers
    st = s.Solve(m)
    return s.StatusName(st), len(bodies)


def solve_highs(eL, eB, budget, seconds, minimize=False):
    import numpy as np
    from scipy.optimize import milp, LinearConstraint, Bounds
    from scipy.sparse import lil_matrix
    src, bodies = domain(eL, eB, budget)
    pairs = [(i, j, ds[i]) for j, (x, y, cells, ds) in enumerate(bodies) for i in range(len(src)) if ds[i] <= budget]
    n = len(pairs)
    rows, lb, ub = [], [], []
    by_src = {}
    for k, (i, j, d) in enumerate(pairs):
        by_src.setdefault(i, []).append(k)
    for i in range(len(src)):
        rows.append(by_src.get(i, [])); lb.append(1); ub.append(1)
    cell_pairs = {}
    for k, (i, j, d) in enumerate(pairs):
        for c in bodies[j][2]:
            cell_pairs.setdefault(c, []).append(k)
    for c, ks in cell_pairs.items():
        rows.append(ks); lb.append(0); ub.append(1)
    A = lil_matrix((len(rows) + (0 if minimize else 1), n))
    for r, ks in enumerate(rows):
        for k in ks:
            A[r, k] = 1
    cost = np.array([d for (i, j, d) in pairs], dtype=float)
    if not minimize:
        for k in range(n):
            A[len(rows), k] = cost[k]
        lb.append(0); ub.append(budget)
    res = milp(c=cost if minimize else np.zeros(n), constraints=LinearConstraint(A.tocsr(), lb, ub),
               integrality=np.ones(n), bounds=Bounds(0, 1), options=dict(time_limit=seconds))
    return res, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('engine', choices=['cpsat', 'highs', 'highs-min'])
    ap.add_argument('--budget', type=int, default=7)
    ap.add_argument('--seconds', type=float, default=600)
    ap.add_argument('--workers', type=int, default=8)
    a = ap.parse_args()
    out = []
    for (eL, eB) in S.band_arrangements():
        t = time.time()
        if a.engine == 'cpsat':
            st, nb = solve_cpsat(eL, eB, a.budget, a.seconds, a.workers)
            r = dict(eL=eL, eB=eB, status=st, bodies=nb)
        elif a.engine == 'highs':
            res, n = solve_highs(eL, eB, a.budget, a.seconds)
            r = dict(eL=eL, eB=eB, status=res.status, message=res.message, pairs=n)
        else:
            res, n = solve_highs(eL, eB, 12, a.seconds, minimize=True)
            r = dict(eL=eL, eB=eB, status=res.status, min_cost=(None if res.x is None else round(res.fun, 6)), pairs=n)
        r['seconds'] = round(time.time() - t, 2)
        print(json.dumps(r, ensure_ascii=False), flush=True)
        out.append(r)
    json.dump(out, open(f'out/ore_distance_{a.engine}_b{a.budget}.json', 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
