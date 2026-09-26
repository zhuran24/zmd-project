"""三审自写：proj1113.py 同一边段投影放宽的第二套编码（线性整数矩阵，交 scipy.optimize.milp / HiGHS）。

与 proj1113.py 的区别：不复用其建模函数；单位选项由本文件独立枚举（只共用 geo.py 的尺寸/端口表、
field.py 的场地定义与 site_power 的逐桩上限）。每个相关格设占用变量 o_g（等式：o_g = 覆盖它的选项之和 ≤1），
每个制造单位选项设「被覆盖桩数」整数变量 k_i 与重复变量 r_i（r_i >= k_i - 1 - M(1-u_i)），
X、Y 用 o_g 线性表示。
"""
import argparse
import json
import time

import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import coo_matrix

import field as S
from geo import KINDS, body, port_sides, pole_body, pole_range

CAP = {'S': 131, 'M': 48, 'L': 38}


def enumerate_units(b, power, P, jmax):
    budget = 23 * P - 217
    Xc, Yc, corner = S.count_cells(b)
    cnt = set(Xc) | set(Yc)
    ok = lambda c: S.usable(c, b)
    units = []  # dict(type='mach'|'core'|'pole', cells, ...)
    # 制造单位：逐格反推锚点（与 proj1113 的逐锚点扫描不同）
    seen = set()
    for (cx, cy) in cnt:
        for kind, (cat, w, h, axis) in KINDS.items():
            for x in range(cx - w + 1, cx + 1):
                for y in range(cy - h + 1, cy + 1):
                    key = (kind, x, y)
                    if key in seen:
                        continue
                    seen.add(key)
                    cells = body(x, y, w, h)
                    if not all(ok(c) for c in cells):
                        continue
                    A, B = port_sides(x, y, w, h, axis)
                    A = [c for c in A if ok(c)]
                    B = [c for c in B if ok(c)]
                    if not A or not B:
                        continue
                    if cat == 'L':
                        for inp, out in ((A, B), (B, A)):
                            if len(inp) >= 2:
                                units.append(dict(type='mach', cat=cat, x=x, y=y, w=w, h=h, cells=cells,
                                                  need=[(inp, 2), (out, 1)], inp=inp))
                    else:
                        units.append(dict(type='mach', cat=cat, x=x, y=y, w=w, h=h, cells=cells,
                                          need=[(A, 1), (B, 1)], inp=None))
    # 协议核心
    for x in range(1, 62):
        for y in range(1, 62):
            cells = body(x, y, 9, 9)
            if not any(c in cnt for c in cells) or not all(ok(c) for c in cells):
                continue
            if x <= 3 and y <= 3:
                continue
            for axis in ('LR', 'BT'):
                if axis == 'LR':
                    pick = [(x - 1, y + k) for k in (1, 4, 7)] + [(x + 9, y + k) for k in (1, 4, 7)]
                    inp = [(x + k, y - 1) for k in range(1, 8)] + [(x + k, y + 9) for k in range(1, 8)]
                    if x < 4:      # 取货边朝左带：2+3<=2(x-1)
                        continue
                    if y < 2:
                        continue
                else:
                    pick = [(x + k, y - 1) for k in (1, 4, 7)] + [(x + k, y + 9) for k in (1, 4, 7)]
                    inp = [(x - 1, y + k) for k in range(1, 8)] + [(x + 9, y + k) for k in range(1, 8)]
                    if y < 4 or x < 2:
                        continue
                if not all(ok(c) for c in pick):
                    continue
                inp = [c for c in inp if ok(c)]
                if len(inp) < 2:
                    continue
                units.append(dict(type='core', x=x, y=y, cells=cells, pick=pick, inp=inp))
    machs = [u for u in units if u['type'] == 'mach']
    for px in range(1, 69):
        for py in range(1, 69):
            cells = pole_body(px, py)
            if not all(ok(c) for c in cells):
                continue
            edge = S.is_edge_pole(px, py)
            L = 23 - power[f'{px},{py}']['c']
            if L > budget or (edge and jmax == 0):
                continue
            x0, x1, y0, y1 = pole_range(px, py)
            cov = [k for k, m in enumerate(machs)
                   if m['x'] <= x1 and m['x'] + m['w'] - 1 >= x0 and m['y'] <= y1 and m['y'] + m['h'] - 1 >= y0]
            touches = any(c in cnt for c in cells) or (corner and (69, 69) in cells)
            if not edge and not cov and not touches:
                continue
            units.append(dict(type='pole', px=px, py=py, cells=cells, L=L, edge=edge, cov=cov))
    return units, Xc, Yc, corner


def build_and_solve(b, power, P, jmin, jmax, cap, seconds, engine='highs', workers=6):
    budget = 23 * P - 217
    units, Xc, Yc, corner = enumerate_units(b, power, P, jmax)
    machs = [u for u in units if u['type'] == 'mach']
    cores = [u for u in units if u['type'] == 'core']
    poles = [u for u in units if u['type'] == 'pole']
    bands = S.band_arrangements()
    # 变量布局
    names = []
    def new(n):
        names.append(n); return len(names) - 1
    iu = [new(('u', k)) for k in range(len(machs))]
    iw = [new(('w', k)) for k in range(len(cores))]
    iv = [new(('v', k)) for k in range(len(poles))]
    iz = [new(('z', a)) for a in range(len(bands))]
    it = {k: new(('t', k)) for k, m in enumerate(machs) if m['cat'] == 'L'}
    # 格占用
    cellset = set()
    for m in machs:
        cellset.update(m['cells'])
        for side, _ in m['need']:
            cellset.update(side)
    for c in cores:
        cellset.update(c['cells']); cellset.update(c['pick']); cellset.update(c['inp'])
    for p in poles:
        cellset.update(p['cells'])
    cellset.update(Xc); cellset.update(Yc)
    io = {g: new(('o', g)) for g in sorted(cellset)}
    ik = {k: new(('k', k)) for k in range(len(machs))}
    ir = {k: new(('r', k)) for k in range(len(machs))}
    nvar = len(names)
    lo = np.zeros(nvar); hi = np.ones(nvar); integ = np.ones(nvar)
    for k in range(len(machs)):
        hi[ik[k]] = len(poles); hi[ir[k]] = len(poles)
    R, C, V, LB, UB = [], [], [], [], []
    row = [0]
    def add(coefs, lb, ub):
        for j, a in coefs:
            R.append(row[0]); C.append(j); V.append(a)
        LB.append(lb); UB.append(ub); row[0] += 1
    INF = np.inf
    # o_g = Σ 覆盖它的单位
    cover = {g: [] for g in io}
    for k, m in enumerate(machs):
        for g in m['cells']:
            cover[g].append(iu[k])
    for k, c in enumerate(cores):
        for g in c['cells']:
            cover[g].append(iw[k])
    for k, p in enumerate(poles):
        for g in p['cells']:
            cover[g].append(iv[k])
    for g, lst in cover.items():
        add([(io[g], 1)] + [(j, -1) for j in lst], 0, 0)
    # 矿石首运输格不能被占：o_g + Σ_{a: g 是首格} z_a <= 1
    orecells = {}
    for a, (eL, eB) in enumerate(bands):
        for g in [(1, r) for r in S.band_ports(eL)] + [(c, 1) for c in S.band_ports(eB)]:
            orecells.setdefault(g, []).append(iz[a])
    for g, lst in orecells.items():
        if g in io:
            add([(io[g], 1)] + [(j, 1) for j in lst], 0, 1)
    add([(j, 1) for j in iz], 1, 1)
    # 端口邻格：need 个空格 → need*u + Σ o_g <= |side|
    for k, m in enumerate(machs):
        for side, need in m['need']:
            add([(iu[k], need)] + [(io[g], 1) for g in side], -INF, len(side))
        if m['cat'] == 'L':
            # 3u - t + Σ o <= |inp|，t <= u，Σ t <= 1
            add([(iu[k], 3), (it[k], -1)] + [(io[g], 1) for g in m['inp']], -INF, len(m['inp']))
            add([(it[k], 1), (iu[k], -1)], -INF, 0)
    if it:
        add([(j, 1) for j in it.values()], -INF, 1)
    for k, c in enumerate(cores):
        for g in c['pick']:
            add([(iw[k], 1), (io[g], 1)], -INF, 1)
        add([(iw[k], 2)] + [(io[g], 1) for g in c['inp']], -INF, len(c['inp']))
    if iw:
        add([(j, 1) for j in iw], -INF, 1)
    for cat, n in CAP.items():
        add([(iu[k], 1) for k, m in enumerate(machs) if m['cat'] == cat], -INF, n)
    # 覆盖：k_i = Σ 覆盖它的桩；k_i >= u_i；r_i >= k_i - 1 - M(1-u_i)
    covby = {k: [] for k in range(len(machs))}
    for q, p in enumerate(poles):
        for k in p['cov']:
            covby[k].append(iv[q])
    for k in range(len(machs)):
        M = len(covby[k])
        add([(ik[k], 1)] + [(j, -1) for j in covby[k]], 0, 0)
        add([(ik[k], 1), (iu[k], -1)], 0, INF)
        # r - k - M u >= -1 - M
        add([(ir[k], 1), (ik[k], -1), (iu[k], -M)], -1 - M, INF)
    add([(iv[q], p['L']) for q, p in enumerate(poles) if p['L']] + [(ir[k], 1) for k in range(len(machs))], -INF, budget)
    add([(j, 1) for j in iv], -INF, P)
    jidx = [iv[q] for q, p in enumerate(poles) if p['edge']]
    if jidx:
        add([(j, 1) for j in jidx], jmin, jmax)
    elif jmin > 0:
        return dict(status='INFEASIBLE-trivial')
    # S = 16P - 2J + X + Y <= cap
    coef = {}
    for j in jidx:
        coef[j] = coef.get(j, 0) - 2
    const = 16 * P + len(Xc) + len(Yc)
    for g in Xc:
        coef[io[g]] = coef.get(io[g], 0) - 1
    for g in Yc:
        coef[io[g]] = coef.get(io[g], 0) - 1
    if corner:
        const += 2
        for q, p in enumerate(poles):
            if (69, 69) in p['cells']:
                coef[iv[q]] = coef.get(iv[q], 0) - 2
    add(list(coef.items()), -INF, cap - const)
    A = coo_matrix((V, (R, C)), shape=(row[0], nvar)).tocsr()
    t0 = time.time()
    if engine == 'cpsat':
        # 同一线性整数矩阵交 CP-SAT（执行器交叉检查，不是第三套编码）
        from ortools.sat.python import cp_model
        m = cp_model.CpModel()
        x = [m.NewIntVar(int(lo[j]), int(hi[j]), f'x{j}') for j in range(nvar)]
        for k in range(row[0]):
            a, bnd = A.getrow(k), None
            terms = [(int(c_), int(v_)) for c_, v_ in zip(a.indices, a.data)]
            lbk = None if LB[k] == -np.inf else int(np.ceil(LB[k] - 1e-9))
            ubk = None if UB[k] == np.inf else int(np.floor(UB[k] + 1e-9))
            expr = sum(v_ * x[c_] for c_, v_ in terms)
            if lbk is not None and ubk is not None and lbk == ubk:
                m.Add(expr == lbk)
            else:
                if lbk is not None:
                    m.Add(expr >= lbk)
                if ubk is not None:
                    m.Add(expr <= ubk)
        sv = cp_model.CpSolver()
        sv.parameters.max_time_in_seconds = seconds
        sv.parameters.num_workers = workers
        st = sv.Solve(m)
        return dict(b=b, P=P, J=[jmin, jmax], cap=cap, engine='cpsat-linear', status=sv.StatusName(st),
                    seconds=round(time.time() - t0, 1), n_mach=len(machs), n_core=len(cores), n_poles=len(poles),
                    n_var=nvar, n_row=row[0])
    res = milp(c=np.zeros(nvar), constraints=LinearConstraint(A, LB, UB), integrality=integ,
               bounds=Bounds(lo, hi), options=dict(time_limit=seconds, disp=False))
    return dict(b=b, P=P, J=[jmin, jmax], cap=cap, status=int(res.status), message=res.message,
                seconds=round(time.time() - t0, 1), n_mach=len(machs), n_core=len(cores), n_poles=len(poles),
                n_var=nvar, n_row=row[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('b', type=int)
    ap.add_argument('P', type=int)
    ap.add_argument('--jmin', type=int, default=0)
    ap.add_argument('--jmax', type=int, default=0)
    ap.add_argument('--cap', type=int, default=187)
    ap.add_argument('--seconds', type=float, default=3600)
    ap.add_argument('--engine', choices=['highs', 'cpsat'], default='highs')
    ap.add_argument('--workers', type=int, default=6)
    a = ap.parse_args()
    power = json.load(open(f'out/site_power_b{a.b}.json'))
    r = build_and_solve(a.b, power, a.P, a.jmin, a.jmax, a.cap, a.seconds, a.engine, a.workers)
    print(json.dumps(r, ensure_ascii=False))
    suffix = '' if a.engine == 'highs' else '_cpsat'
    json.dump(r, open(f'out/milp_b{a.b}_P{a.P}_J{a.jmin}-{a.jmax}_cap{a.cap}{suffix}.json', 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
