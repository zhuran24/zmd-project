# 复核80：指定桩位的在产台数局部上界（全局坐标，HiGHS）
# 桩左下角 (u,v)，桩身 [u,u+1]x[v,v+1]，供电范围 [u-5,u+6]x[v-5,v+6]。
# 放松模型：机身在第 1..69 列、行内（第 0 列/行为仓库取货口带，机身至少宽 3，放不进），
# 不碰指定空矩形 R=[49,69]x[17,69]、不碰桩身；与供电范围相交；两条端口边各至少一个
# 邻格在第 1..69 列、行内、不在 R、不在桩身、不被所选机身占用（第 0 列/行唯一空格不能承载循环正流量）。
# 不加其他单位、矿石首格等限制（只会放宽）。目标：台数最大。
import sys, json, time
import numpy as np
from multiprocessing import Pool
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import lil_matrix, csr_matrix

SPECS = [(3, 3, 0), (3, 3, 1), (5, 5, 0), (5, 5, 1), (6, 4, 1), (4, 6, 0)]
RX, RY = (49, 69), (17, 69)


def inR(a, b):
    return RX[0] <= a <= RX[1] and RY[0] <= b <= RY[1]


def inbase(a, b):
    return 1 <= a <= 69 and 1 <= b <= 69


def solve(pos):
    u, v = pos
    pole = {(u, v), (u + 1, v), (u, v + 1), (u + 1, v + 1)}
    for (a, b) in pole:
        assert inbase(a, b) and not inR(a, b)
    rx, ry = (u - 5, u + 6), (v - 5, v + 6)
    opts = []
    for w, h, ax in SPECS:
        for x in range(rx[0] - w + 1, rx[1] + 1):
            for y in range(ry[0] - h + 1, ry[1] + 1):
                cells = [(x + i, y + j) for i in range(w) for j in range(h)]
                if any((not inbase(a, b)) or inR(a, b) or (a, b) in pole for (a, b) in cells):
                    continue
                if ax == 0:
                    sides = [[(x - 1, y + j) for j in range(h)], [(x + w, y + j) for j in range(h)]]
                else:
                    sides = [[(x + i, y - 1) for i in range(w)], [(x + i, y + h) for i in range(w)]]
                good = [[g for g in sd if inbase(*g) and not inR(*g) and g not in pole] for sd in sides]
                if any(not s for s in good):
                    continue
                opts.append((cells, good))
    n = len(opts)
    if n == 0:
        return dict(pos=pos, n=0, max=0)
    occ = {}
    for i, (cells, good) in enumerate(opts):
        for c in cells:
            occ.setdefault(c, []).append(i)
    nb = sorted({g for (_, good) in opts for sd in good for g in sd if g in occ})
    fi = {g: n + k for k, g in enumerate(nb)}
    nv = n + len(nb)
    rows, hi = [], []
    for c, lst in occ.items():
        r = {i: 1 for i in lst}
        if c in fi:
            r[fi[c]] = 1
        if len(r) > 1:
            rows.append(r); hi.append(1)
    for i, (cells, good) in enumerate(opts):
        for sd in good:
            if any(g not in occ for g in sd):
                continue
            r = {i: 1}
            for g in sd:
                r[fi[g]] = -1
            rows.append(r); hi.append(0)
    A = lil_matrix((len(rows), nv))
    for k, r in enumerate(rows):
        for j, val in r.items():
            A[k, j] = val
    c = np.zeros(nv); c[:n] = -1
    integ = np.zeros(nv); integ[:n] = 1
    res = milp(c, constraints=LinearConstraint(csr_matrix(A), -np.inf, np.array(hi, float)),
               integrality=integ, bounds=Bounds(0, 1), options=dict(time_limit=300, mip_rel_gap=0))
    ok = res.status == 0
    best = int(round(-res.fun)) if res.x is not None else None
    bound = getattr(res, "mip_dual_bound", None)
    return dict(pos=pos, n=n, status=int(res.status), max=best,
                dual=(None if bound is None else float(-bound)), optimal=ok)


if __name__ == "__main__":
    which = sys.argv[1]
    if which == "yedge":
        # 非占边桩接触 Y 计数边：Y 左 (48,y) y=17..69；Y 下 (x,16) x=49..69
        P = [(47, v) for v in range(16, 68)] + [(u, 15) for u in range(48, 68)]
    elif which == "wall":
        # 占第 1 列 / 第 1 行的单边桩：(1,t) 与 (t,1)，t=2..67（t=1、68 占两边）
        P = [(1, t) for t in range(2, 68)] + [(t, 1) for t in range(2, 68)]
    else:
        raise SystemExit
    t0 = time.time()
    with Pool(int(sys.argv[2]) if len(sys.argv) > 2 else 4) as pool:
        out = pool.map(solve, P)
    json.dump(dict(set=which, results=out, seconds=time.time() - t0), open(f"pos_cap_{which}.json", "w"), indent=1)
    for r in out:
        print(r)
