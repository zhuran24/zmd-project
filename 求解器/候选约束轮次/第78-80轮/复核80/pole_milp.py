# 复核80 编码二：线性整数规划（HiGHS，经 scipy.optimize.milp）
# 与编码一不同：几何另写一遍（按机身范围区间判相交、端口边用坐标区间生成），
# 空邻格用连续变量 f_g∈[0,1]，f_g + Σ_{覆盖 g 的选项} u ≤ 1，选项 i 每条端口边 u_i ≤ Σ f_g。
import argparse, json, time
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import lil_matrix, csr_matrix

SPECS = [  # 类别, 宽, 高, 端口轴, 权重
    ("S", 3, 3, 0, 2), ("S", 3, 3, 1, 2), ("M", 5, 5, 0, 3), ("M", 5, 5, 1, 3),
    ("L", 6, 4, 1, 3), ("L", 4, 6, 0, 3)]  # 轴 0：端口在 x=左右两侧；轴 1：端口在 y=上下两侧


def gen(wall):
    pole_x, pole_y = (5, 6), (5, 6)
    out = []
    for cat, w, h, ax, wt in SPECS:
        # 与 [0,11]^2 相交 <=> x∈[1-w,11], y∈[1-h,11]
        for x in range(1 - w, 12):
            for y in range(1 - h, 12):
                x2, y2 = x + w - 1, y + h - 1
                if x <= pole_x[1] and x2 >= pole_x[0] and y <= pole_y[1] and y2 >= pole_y[0]:
                    continue
                if wall and x2 > 6:
                    continue
                if ax == 0:
                    sides = [[(x - 1, yy) for yy in range(y, y2 + 1)], [(x2 + 1, yy) for yy in range(y, y2 + 1)]]
                else:
                    sides = [[(xx, y - 1) for xx in range(x, x2 + 1)], [(xx, y2 + 1) for xx in range(x, x2 + 1)]]
                good = []
                for sd in sides:
                    v = [(a, b) for (a, b) in sd
                         if not (pole_x[0] <= a <= pole_x[1] and pole_y[0] <= b <= pole_y[1])
                         and (not wall or a <= 6)]
                    good.append(v)
                if any(len(v) == 0 for v in good):
                    continue
                out.append((cat, w, h, ax, wt, x, y, good))
    return out


def solve(wall, cap, threshold=None, maximize=True, seconds=600, unit=False):
    opts = gen(wall)
    if unit:
        opts = [(o[0], o[1], o[2], o[3], 1) + tuple(o[5:]) for o in opts]
    n = len(opts)
    occ = {}
    for i, (cat, w, h, ax, wt, x, y, good) in enumerate(opts):
        for a in range(x, x + w):
            for b in range(y, y + h):
                occ.setdefault((a, b), []).append(i)
    nbr = sorted({g for o in opts for sd in o[7] for g in sd if g in occ})
    fidx = {g: n + k for k, g in enumerate(nbr)}
    nv = n + len(nbr)
    rows, lo, hi = [], [], []
    # 占格
    for g, lst in occ.items():
        if g in fidx:
            continue  # 由 f_g + Σu ≤ 1 同时给出
        if len(lst) > 1:
            rows.append({i: 1 for i in lst}); lo.append(-np.inf); hi.append(1)
    for g, k in fidx.items():
        r = {i: 1 for i in occ[g]}; r[k] = 1
        rows.append(r); lo.append(-np.inf); hi.append(1)
    # 端口邻格
    for i, o in enumerate(opts):
        for sd in o[7]:
            if any(g not in occ for g in sd):
                continue
            r = {i: 1}
            for g in sd:
                r[fidx[g]] = r.get(fidx[g], 0) - 1
            rows.append(r); lo.append(-np.inf); hi.append(0)
    rows.append({i: 1 for i in range(n)}); lo.append(-np.inf); hi.append(cap)
    wts = np.zeros(nv)
    for i, o in enumerate(opts):
        wts[i] = o[4]
    if threshold is not None:
        rows.append({i: o[4] for i, o in enumerate(opts)}); lo.append(threshold); hi.append(np.inf)
    A = lil_matrix((len(rows), nv))
    for r_i, r in enumerate(rows):
        for j, v in r.items():
            A[r_i, j] = v
    integrality = np.zeros(nv); integrality[:n] = 1
    bounds = Bounds(np.zeros(nv), np.ones(nv))
    c = -wts if maximize else np.zeros(nv)
    t0 = time.time()
    res = milp(c, constraints=LinearConstraint(csr_matrix(A), lo, hi), integrality=integrality,
               bounds=bounds, options=dict(time_limit=seconds, disp=True, mip_rel_gap=0))
    dt = time.time() - t0
    out = dict(wall=wall, cap=cap, threshold=threshold, maximize=maximize, n_options=n,
               n_free_vars=len(nbr), n_rows=len(rows), status=int(res.status), message=res.message,
               seconds=dt)
    if res.x is not None:
        chosen = [i for i in range(n) if res.x[i] > 0.5]
        out["objective"] = float(sum(opts[i][4] for i in chosen))
        out["count"] = len(chosen)
        out["solution"] = [dict(cat=opts[i][0], w=opts[i][1], h=opts[i][2], axis="HV"[opts[i][3]],
                                x=opts[i][5], y=opts[i][6]) for i in chosen]
    if hasattr(res, "mip_dual_bound"):
        out["dual_bound"] = None if res.mip_dual_bound is None else float(-res.mip_dual_bound)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--wall", action="store_true")
    ap.add_argument("--cap", type=int, default=None)
    ap.add_argument("--threshold", type=int, default=None)
    ap.add_argument("--feas", action="store_true")
    ap.add_argument("--seconds", type=float, default=600)
    ap.add_argument("--name", default="milp")
    ap.add_argument("--unit", action="store_true")
    a = ap.parse_args()
    cap = a.cap if a.cap is not None else (14 if a.wall else 23)
    out = solve(a.wall, cap, a.threshold, maximize=not a.feas, seconds=a.seconds, unit=a.unit)
    out["unit"] = a.unit
    out["name"] = a.name
    json.dump(out, open(f"{a.name}.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "solution"}, ensure_ascii=False))
