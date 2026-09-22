#!/usr/bin/env python3
"""异源核查：把 strip_model 的同一组必要条件写成 0-1 整数规划，用 HiGHS（scipy.milp）
求 S=16P-2J+X+Y 的最小值，作为与 CP-SAT 无关的第二个求解器复算。

用法：python mip_check.py 49 14 21 53 [--forbid-edge0]
"""
import argparse, json, time
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import coo_array
from strip_model import rect_cells, inside, hit, edges, pole_loss, N, HERE


def candidates(R, forbid_edge0):
    a, b, w, h = R
    xcells = [c for c in [(69, k) for k in range(1, 69)] + [(k, 69) for k in range(1, 69)] if not inside(c, R)]
    ring = ([(a - 1, k) for k in range(b, b + h)] if a > 0 else []) + \
           ([(a + w, k) for k in range(b, b + h)] if a + w < N else []) + \
           ([(k, b - 1) for k in range(a, a + w)] if b > 0 else []) + \
           ([(k, b + h) for k in range(a, a + w)] if b + h < N else [])
    touch = set(xcells) | set(ring) | {(69, 69)}
    lo = 1 if forbid_edge0 else 0
    usable = lambda c: lo <= c[0] < N and lo <= c[1] < N and not inside(c, R)
    bodies = []  # dict(kind, rect, need=[(k, cells)], outs, ins, loss, edge)
    for kind, W, H, axis in [('small', 3, 3, 'EW'), ('small', 3, 3, 'NS'), ('medium', 5, 5, 'EW'),
                             ('medium', 5, 5, 'NS'), ('large', 6, 4, 'NS'), ('large', 4, 6, 'EW')]:
        for x in range(1, N - W + 1):
            for y in range(1, N - H + 1):
                rect = (x, y, W, H)
                if hit(rect, R) or not (set(rect_cells(*rect)) & touch):
                    continue
                es = [[c for c in e if usable(c)] for e in edges(x, y, W, H, axis)]
                if all(es):
                    bodies.append(dict(kind=kind, rect=rect, need=[(1, e) for e in es]))
    for x in range(1, N - 8):
        for y in range(1, N - 8):
            rect = (x, y, 9, 9)
            if hit(rect, R) or not (set(rect_cells(*rect)) & touch):
                continue
            for axis in ('EW', 'NS'):
                outs = [e[k] for e in edges(x, y, 9, 9, axis) for k in (1, 4, 7)]
                ins = [e[k] for e in edges(x, y, 9, 9, 'NS' if axis == 'EW' else 'EW') for k in range(1, 8)]
                if not all(usable(c) for c in outs):
                    continue
                ins = [c for c in ins if usable(c)]
                if len(ins) >= 2:
                    bodies.append(dict(kind='core', rect=rect, need=[(1, [c]) for c in outs] + [(2, ins)]))
    for x in range(1, N - 1):
        for y in range(1, N - 1):
            rect = (x, y, 2, 2)
            if hit(rect, R) or not (set(rect_cells(*rect)) & touch):
                continue
            e = int(bool({x, x + 1} & {1, 69})) + int(bool({y, y + 1} & {1, 69}))
            bodies.append(dict(kind='pole', rect=rect, need=[], loss=pole_loss(x, y, R), edge=e > 0))
    return bodies, xcells, ring


def solve(R, forbid_edge0=False, time_limit=600):
    bodies, xcells, ring = candidates(R, forbid_edge0)
    nb = len(bodies)
    # 变量：body[0..nb)，y10,y11,y12，hid_edge，hid_all，J
    iy = nb; ihe = nb + 3; iha = nb + 4; iJ = nb + 5; n = nb + 6
    cov = {}
    for i, bd in enumerate(bodies):
        for c in rect_cells(*bd['rect']):
            cov.setdefault(c, []).append(i)
    rows, cols, vals, lo, hi = [], [], [], [], []
    r = 0
    def add(terms, l, u):
        nonlocal r
        for j, v in terms:
            rows.append(r); cols.append(j); vals.append(v)
        lo.append(l); hi.append(u); r += 1
    for c, ids in cov.items():
        if len(ids) > 1:
            add([(i, 1) for i in ids], -np.inf, 1)
    # need (k, cells)：k*body <= sum_{c} (1-occ(c))  ->  k*body + sum occ <= |cells|
    for i, bd in enumerate(bodies):
        for k, cells in bd['need']:
            terms = {i: k}
            for c in cells:
                for j in cov.get(c, []):
                    terms[j] = terms.get(j, 0) + 1
            add(list(terms.items()), -np.inf, len(cells))
    for kind, cap in (('small', 131), ('medium', 48), ('large', 38), ('core', 1)):
        add([(i, 1) for i, bd in enumerate(bodies) if bd['kind'] == kind], -np.inf, cap)
    add([(iy, 1), (iy + 1, 1), (iy + 2, 1)], 1, 1)
    poles = [i for i, bd in enumerate(bodies) if bd['kind'] == 'pole']
    # sum poles + hid_all - P = 0
    add([(i, 1) for i in poles] + [(iha, 1), (iy, -10), (iy + 1, -11), (iy + 2, -12)], 0, 0)
    add([(iha, 1), (ihe, -1)], 0, np.inf)
    # J - sum edge poles - hid_edge = 0
    add([(iJ, 1)] + [(i, -1) for i in poles if bodies[i]['edge']] + [(ihe, -1)], 0, 0)
    # sum loss + 9 hid_edge - 23P <= -217
    add([(i, bodies[i]['loss']) for i in poles if bodies[i]['loss']] + [(ihe, 9)] +
        [(iy, -230), (iy + 1, -253), (iy + 2, -276)], -np.inf, -217)
    # 目标 S = 16P - 2J + X + Y，X = |xcells| - sum occ + 2(1 - corner pole)，Y = |ring| - sum occ
    cost = np.zeros(n)
    const = len(xcells) + len(ring)
    for c in xcells + ring:
        for j in cov.get(c, []):
            cost[j] -= 1
    if not inside((69, 69), R):
        const += 2
        for i in poles:
            if bodies[i]['rect'] == (68, 68, 2, 2):
                cost[i] -= 2
    cost[iy] += 160; cost[iy + 1] += 176; cost[iy + 2] += 192; cost[iJ] -= 2
    A = coo_array((np.array(vals, float), (np.array(rows), np.array(cols))), shape=(r, n)).tocsc()
    lb = np.zeros(n); ub = np.ones(n)
    ub[ihe] = ub[iha] = ub[iJ] = 12
    t0 = time.monotonic()
    res = milp(cost, integrality=np.ones(n), bounds=Bounds(lb, ub), constraints=LinearConstraint(A, lo, hi),
               options=dict(time_limit=time_limit, mip_rel_gap=0, disp=False))
    out = dict(rect=list(R), forbid_edge0=forbid_edge0, backend='HiGHS', status=int(res.status),
               message=res.message, seconds=round(time.monotonic() - t0, 2), n_bodies=nb, n_rows=r)
    if res.x is not None:
        out['S_min'] = round(res.fun + const, 6)
        out['dual_bound'] = round(getattr(res, 'mip_dual_bound', float('nan')) + const, 6)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('rect', type=int, nargs=4)
    ap.add_argument('--forbid-edge0', action='store_true')
    ap.add_argument('--time', type=float, default=600)
    args = ap.parse_args()
    R = tuple(args.rect)
    out = solve(R, args.forbid_edge0, args.time)
    tag = f"mip_{'edge0' if args.forbid_edge0 else 'weak'}_W{R[2]}H{R[3]}_x{R[0]}y{R[1]}"
    (HERE / 'results' / f'{tag}.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps(out, ensure_ascii=False))
