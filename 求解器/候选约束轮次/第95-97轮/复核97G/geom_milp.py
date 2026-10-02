#!/usr/bin/env python3
"""复核97G 编码甲：显式 70x70 格、逐格占用不等式的 0-1 整数规划（scipy HiGHS）。

只依赖规则推出的局部必要条件（见复核97G.md 第3节），不导入任何其他席位脚本。
对 47 种联合边带 x 缺格小制造单位分支，求矿石格接口数 N 加 O 上权重 w 的最大值；
近边分支（a=2，转置另算一遍核对）再加周圈矿石格数 d。
"""
import json, os, sys, time, itertools
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds

S = 70

def border_layout(gl, gb):
    """按格子显式铺仓库取货口：左边 col 0、下边 row 0，各留一个空格。返回 (ore 左, ore 下, q)."""
    occ = {}
    # 左边：col 0 的 rows 0..69 去掉 gl；(0,0) 只在 gl!=0 且 gb==0 时归左边
    left_rows = [y for y in range(S) if y != gl]
    bot_cols = [x for x in range(S) if x != gb]
    if gl == 0 and gb != 0:
        pass  # (0,0) 归下边，左边本来就不含 row 0
    if gb == 0 and gl != 0:
        pass  # (0,0) 归左边，下边本来就不含 col 0
    if gl != 0 and gb != 0:
        raise ValueError
    # 去掉共有角格的重复：两边都不留角时不可能（gl、gb 至少一个为 0）
    if gl != 0:
        bot_cols = [x for x in bot_cols if x != 0]
    if gb != 0:
        left_rows = [y for y in left_rows if y != 0]
    def triples(seq):
        runs, cur = [], [seq[0]]
        for v in seq[1:]:
            if v == cur[-1] + 1:
                cur.append(v)
            else:
                runs.append(cur); cur = [v]
        runs.append(cur)
        mids = []
        for r in runs:
            assert len(r) % 3 == 0, (gl, gb, r)
            for k in range(0, len(r), 3):
                mids.append(r[k + 1])
        return mids
    lm = triples(left_rows)
    bm = triples(bot_cols)
    assert len(lm) == 23 and len(bm) == 23
    ore_left = [(1, y) for y in lm]
    ore_bot = [(x, 1) for x in bm]
    border = set((0, y) for y in left_rows) | set((x, 0) for x in bot_cols)
    q = [c for c in [(0, y) for y in range(S)] + [(x, 0) for x in range(S)] if c not in border]
    q = sorted(set(q))
    assert len(q) == 1
    return ore_left, ore_bot, q[0]

def configs():
    out = []
    for gl in range(0, S, 3):
        for gb in range(0, S, 3):
            if gl == 0 or gb == 0:
                out.append((gl, gb))
    return out

def body(x0, y0, w=3, h=3):
    return frozenset((x, y) for x in range(x0, x0 + w) for y in range(y0, y0 + h))

def gap_unit(gl, gb):
    """非角缺格处唯一可放的 3x3 机身，及其端口边朝向的矿石格。"""
    if gl != 0 and gl != 69:
        g = gl
        return body(1, g - 1), 'L', g
    if gb != 0 and gb != 69:
        g = gb
        return body(g - 1, 1), 'B', g
    return None, None, None

def normal_options(ore_left, ore_bot, O):
    opts = []
    for (x, y) in ore_left:
        for i in range(3):
            b = body(2, y - i)
            opts.append(('L', (x, y), b))
    for (x, y) in ore_bot:
        for i in range(3):
            b = body(x - i, 2)
            opts.append(('B', (x, y), b))
    good = []
    for side, src, b in opts:
        if any(not (1 <= cx <= 69 and 1 <= cy <= 69) for cx, cy in b):
            continue
        if b & O:
            continue
        good.append((side, src, b))
    return good

def solve_count(opts, forbidden, cap=None):
    """最大互不重叠的法向消费机台数；cap=(side, k) 时该侧台数 <= k。"""
    use = [o for o in opts if not (o[2] & forbidden)]
    n = len(use)
    if n == 0:
        return 0, []
    cells = sorted(set().union(*[o[2] for o in use]))
    idx = {c: i for i, c in enumerate(cells)}
    rows = []
    for c in cells:
        r = np.zeros(n)
        for j, o in enumerate(use):
            if c in o[2]:
                r[j] = 1
        rows.append(r)
    A = [np.array(rows)]
    lb = [np.full(len(rows), -np.inf)]
    ub = [np.ones(len(rows))]
    if cap is not None:
        side, k = cap
        r = np.array([1.0 if o[0] == side else 0.0 for o in use])
        A.append(r[None, :]); lb.append(np.array([-np.inf])); ub.append(np.array([k]))
    A = np.vstack(A); lb = np.concatenate(lb); ub = np.concatenate(ub)
    res = milp(c=-np.ones(n), constraints=LinearConstraint(A, lb, ub),
               integrality=np.ones(n), bounds=Bounds(0, 1),
               options={'disp': False, 'presolve': True})
    assert res.status == 0, res.message
    val = int(round(-res.fun))
    chosen = [(use[j][0], use[j][1], min(use[j][2])) for j in range(n) if res.x[j] > 0.5]
    assert len(chosen) == val
    return val, chosen

def branch_values(gl, gb, R=frozenset()):
    """返回各分支的 N+w 上界：{'none':..., 'unit':..., 'shape':...}（不可行或不存在时为 None）。"""
    ore_left, ore_bot, q = border_layout(gl, gb)
    O = set(ore_left) | set(ore_bot)
    opts = normal_options(ore_left, ore_bot, O)
    G, gside, g = gap_unit(gl, gb)
    out = {}
    base_forbid = frozenset(R)
    if G is None:
        v, ch = solve_count(opts, base_forbid)
        out['none'] = (46 + v, ch)
        return out
    # 不放缺格机：任何机身都不能盖缺格的三个内带格（第 1 列或第 1 行上的三格）
    gap_cells = frozenset(c for c in G if (c[0] == 1 if gside == 'L' else c[1] == 1))
    assert len(gap_cells) == 3
    v, ch = solve_count(opts, base_forbid | gap_cells)
    out['none'] = (46 + v, ch)
    if G & R:
        out['unit'] = None
        out['shape'] = None
        return out
    # 放缺格机：G 固定，其与矿石格的接口至多 2
    cap = None
    if g == 3:
        # 封住条带：G 与对边其余 22 台不能同时铺满第 2..4 行（列）
        cap = ('B' if gside == 'L' else 'L', 21)
    v, ch = solve_count(opts, base_forbid | G, cap)
    out['unit'] = (46 + v + 2, ch)
    # 塑形机且计 w：g=3 时 G 必须吃原矿（见报告），不可能是塑形机
    if g == 3:
        out['shape'] = None
        return out
    best = None
    if gside == 'L':
        feeders = [(2, g + 2), (3, g + 2), (2, g - 2), (3, g - 2)]
    else:
        feeders = [(g + 2, 2), (g + 2, 3), (g - 2, 2), (g - 2, 3)]
    for f in feeders:
        if f in R:
            continue
        v, ch = solve_count(opts, base_forbid | G | {f})
        val = 46 + v + 2 + 1
        if best is None or val > best[0]:
            best = (val, ch)
    out['shape'] = best
    return out

def main():
    t0 = time.time()
    res = {'encoding': 'A: explicit grid + cell-occupancy 0-1 IP (scipy HiGHS)', 'baseline': [], 'near': []}
    for gl, gb in configs():
        bv = branch_values(gl, gb)
        rec = {'gl': gl, 'gb': gb}
        for k in ('none', 'unit', 'shape'):
            if k in bv:
                rec[k] = None if bv[k] is None else bv[k][0]
        res['baseline'].append(rec)
    res['baseline_max'] = max(max(v for k, v in r.items() if k in ('none', 'unit', 'shape') and v is not None)
                              for r in res['baseline'])
    # 近边：a=2，R 取宽 6 的子矩形 [2,7]x[b,b+H-1]；b>=3，b+H-1<=69（不预设矩形离带的 H<=9、m<=2、不贴上边）
    Hlo, Hhi = int(sys.argv[1]), int(sys.argv[2])
    near_max = None
    for gl, gb in configs():
        ore_left, ore_bot, q = border_layout(gl, gb)
        lys = set(y for _, y in ore_left)
        for H in range(Hlo, Hhi + 1):
            for b in range(3, 70 - H + 1):
                R = body(2, b, 6, H)
                d = sum(1 for y in range(b, b + H) if y in lys)
                bv = branch_values(gl, gb, R)
                rec = {'gl': gl, 'gb': gb, 'b': b, 'H': H, 'd': d}
                for k in ('none', 'unit', 'shape'):
                    if k in bv:
                        rec[k] = None if bv[k] is None else bv[k][0] + d
                res['near'].append(rec)
                m = max(v for k, v in rec.items() if k in ('none', 'unit', 'shape') and v is not None)
                if near_max is None or m > near_max:
                    near_max = m
    res['H_range'] = [Hlo, Hhi]
    res['near_max'] = near_max
    res['seconds'] = time.time() - t0
    json.dump(res, open(os.path.join(os.path.dirname(__file__), 'geom_milp_H%d_%d.json' % (Hlo, Hhi)), 'w'), ensure_ascii=False)
    print('baseline_max', res['baseline_max'], 'near_max', near_max, 'n_near', len(res['near']), 'sec', res['seconds'])

if __name__ == '__main__':
    main()
