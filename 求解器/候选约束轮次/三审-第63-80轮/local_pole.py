"""三审自写：单根供电桩能为多少台在产制造单位供电的局部放宽模型。

放宽内容（真实布局中该桩覆盖的在产制造单位都满足以下条件，所以真实值不超过本模型的最大值）：
  * 机身与该桩供电范围相交、不碰桩身、落在可用格内、互不重叠；
  * 两条端口边外各至少有一个可用、不属桩身、未被所选机身占用的邻格（在产机器两侧都要有运输单位）；
  * 台数不超过给定上限（正式「供电下限」的 23 台 / 占边 14 台）。
其他单位、运输接法、物料全部删去。

用法：
  python local_pole.py general --obj weight --cap 23      # 普通单桩，删去全部边界
  python local_pole.py wall --obj weight --cap 14         # 占边单桩：桩身列 5..6，可用格 x<=6
  python local_pole.py wall --obj count --cap 14
"""
import argparse
import json
import sys
import time

from ortools.sat.python import cp_model

from geo import KINDS, WEIGHT, body, port_sides, pole_body, pole_range, rect_intersects


def enumerate_options(px, py, usable):
    """usable(cell) -> bool：机身格与端口邻格是否可用（桩身另行排除）。"""
    pb = set(pole_body(px, py))
    rng = pole_range(px, py)
    opts = []
    for kind, (cat, w, h, axis) in KINDS.items():
        for x in range(rng[0] - w + 1, rng[1] + 1):
            for y in range(rng[2] - h + 1, rng[3] + 1):
                if not rect_intersects(x, y, w, h, rng):
                    continue
                cells = body(x, y, w, h)
                if any((c in pb) or (not usable(c)) for c in cells):
                    continue
                sa, sb = port_sides(x, y, w, h, axis)
                sa = [c for c in sa if usable(c) and c not in pb]
                sb = [c for c in sb if usable(c) and c not in pb]
                if not sa or not sb:
                    continue
                opts.append(dict(kind=kind, cat=cat, x=x, y=y, w=w, h=h, cells=cells, sa=sa, sb=sb))
    return opts


def build(opts, obj, cap, extra_min=None):
    m = cp_model.CpModel()
    u = [m.NewBoolVar(f"u{i}") for i in range(len(opts))]
    cover = {}
    for i, o in enumerate(opts):
        for c in o['cells']:
            cover.setdefault(c, []).append(i)
    for c, lst in cover.items():
        if len(lst) > 1:
            m.Add(sum(u[i] for i in lst) <= 1)
    for i, o in enumerate(opts):
        for side in (o['sa'], o['sb']):
            occ = [j for c in side for j in cover.get(c, [])]
            if not occ:
                continue  # 该侧邻格没有任何选项能占，恒有空邻格
            # 选中时该侧至少一个邻格空着：u_i + sum_g o_g <= |A|
            m.Add(u[i] + sum(u[j] for j in occ) <= len(side))
    m.Add(sum(u) <= cap)
    if obj == 'weight':
        expr = sum(WEIGHT[o['cat']] * u[i] for i, o in enumerate(opts))
    else:
        expr = sum(u)
    if extra_min is not None:
        m.Add(expr >= extra_min)
    else:
        m.Maximize(expr)
    return m, u, expr


def solve(m, seconds, workers):
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = seconds
    s.parameters.num_workers = workers
    t = time.time()
    st = s.Solve(m)
    return s, st, time.time() - t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['general', 'wall'])
    ap.add_argument('--obj', choices=['count', 'weight'], default='weight')
    ap.add_argument('--cap', type=int, default=23)
    ap.add_argument('--atleast', type=int, default=None, help='只判断目标 >= 该值是否可行')
    ap.add_argument('--seconds', type=float, default=600)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    px = py = 5
    if a.mode == 'general':
        usable = lambda c: True
    else:
        usable = lambda c: c[0] <= 6
    opts = enumerate_options(px, py, usable)
    m, u, expr = build(opts, a.obj, a.cap, a.atleast)
    s, st, dt = solve(m, a.seconds, a.workers)
    res = dict(mode=a.mode, obj=a.obj, cap=a.cap, atleast=a.atleast, n_options=len(opts),
               status=s.StatusName(st), seconds=round(dt, 2))
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        sel = [dict(kind=o['kind'], x=o['x'], y=o['y']) for i, o in enumerate(opts) if s.Value(u[i])]
        res['value'] = sum((WEIGHT[KINDS[q['kind']][0]] if a.obj == 'weight' else 1) for q in sel)
        res['bound'] = s.BestObjectiveBound() if a.atleast is None else None
        res['selection'] = sel
    print(json.dumps({k: v for k, v in res.items() if k != 'selection'}, ensure_ascii=False))
    if a.out:
        with open(a.out, 'w') as f:
            json.dump(res, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
