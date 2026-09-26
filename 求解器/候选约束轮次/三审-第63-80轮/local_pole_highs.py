"""三审：local_pole.py 同一放宽的第二执行器（scipy.optimize.milp / HiGHS），线性矩阵自行展开。"""
import argparse
import json
import time

import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import lil_matrix

from geo import WEIGHT
from local_pole import enumerate_options


def run(opts, obj, cap, atleast):
    n = len(opts)
    cover = {}
    for i, o in enumerate(opts):
        for c in o['cells']:
            cover.setdefault(c, []).append(i)
    rows = []
    ub = []
    for c, lst in cover.items():
        if len(lst) > 1:
            rows.append({i: 1 for i in lst}); ub.append(1)
    for i, o in enumerate(opts):
        for side in (o['sa'], o['sb']):
            occ = [j for c in side for j in cover.get(c, [])]
            if not occ:
                continue
            r = {}
            for j in occ:
                r[j] = r.get(j, 0) + 1
            r[i] = r.get(i, 0) + 1
            rows.append(r); ub.append(len(side))
    rows.append({i: 1 for i in range(n)}); ub.append(cap)
    w = np.array([WEIGHT[o['cat']] if obj == 'weight' else 1 for o in opts], dtype=float)
    lb = [-np.inf] * len(rows)
    if atleast is not None:
        rows.append({i: w[i] for i in range(n)}); ub.append(np.inf); lb.append(atleast)
    A = lil_matrix((len(rows), n))
    for k, r in enumerate(rows):
        for j, v in r.items():
            A[k, j] = v
    cons = LinearConstraint(A.tocsr(), lb, ub)
    t = time.time()
    res = milp(c=-w if atleast is None else np.zeros(n), constraints=cons,
               integrality=np.ones(n), bounds=Bounds(0, 1), options=dict(time_limit=3600))
    return res, time.time() - t, len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['general', 'wall'])
    ap.add_argument('--obj', choices=['count', 'weight'], default='weight')
    ap.add_argument('--cap', type=int, default=23)
    ap.add_argument('--atleast', type=float, default=None)
    a = ap.parse_args()
    usable = (lambda c: True) if a.mode == 'general' else (lambda c: c[0] <= 6)
    opts = enumerate_options(5, 5, usable)
    res, dt, nrows = run(opts, a.obj, a.cap, a.atleast)
    out = dict(mode=a.mode, obj=a.obj, cap=a.cap, atleast=a.atleast, n_options=len(opts), n_rows=nrows,
               status=res.status, message=res.message, seconds=round(dt, 2),
               value=(None if res.x is None else float(-res.fun) if a.atleast is None else 'feasible'))
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
