#!/usr/bin/env python3
"""异源核查：独立写的边界带放松模型（不导入 1113放松/ 下任何脚本）。

只显式放置「碰到 X 格、Y 格或右上角格」的单位，其余单位全部放任（存在即可、
不约束）。条件逐条对应正式文件，见同目录 ../异源核查.md 第 3 节。

坐标：左下角格 (0,0)，格 (x,y)，0<=x,y<=69。矩形一律 (x,y,w,h) 表示
[x,x+w)×[y,y+h)。

用法：
  python strip_model.py 49 13 21 53 --P 10,11,12 --seconds 120 --workers 6
  --forbid-edge0   端口对接格不得在第 0 行/列（更强，默认关闭＝更弱）
  --minimize X|Y|S 不加 X+Y 预算，改为在资源预算下求 X、Y 或 S=16P-2J+X+Y 的最小值
"""
import argparse, json, time, sys
from pathlib import Path
from ortools.sat.python import cp_model

N = 70
HERE = Path(__file__).resolve().parent


def rect_cells(x, y, w, h):
    return [(i, j) for i in range(x, x + w) for j in range(y, y + h)]


def inside(pt, r):
    x, y = pt
    a, b, w, h = r
    return a <= x < a + w and b <= y < b + h


def hit(r1, r2):
    x, y, w, h = r1
    X, Y, W, H = r2
    return x < X + W and X < x + w and y < Y + H and Y < y + h


# 侧旁供电 c_g=(13,14,14,17,18,19,22) -> 亏额 23-c_g
SIDE_LOSS = [23 - c for c in (13, 14, 14, 17, 18, 19, 22)]


def pole_loss(px, py, R):
    """一个 2x2 桩（左下 (px,py)）的容量亏额下界：各条正式上界取最大值。"""
    a, b, w, h = R
    # 供电下限：占格含第 1 列/第 69 列、第 1 行/第 69 行
    cols = {px, px + 1}
    rows = {py, py + 1}
    e = int(bool(cols & {1, 69})) + int(bool(rows & {1, 69}))
    loss = {0: 0, 1: 23 - 14, 2: 23 - 8}[e]
    # 覆盖 12x12：以 2x2 中心为原点，格 px-5 .. px+6
    cx0, cx1 = px - 5, px + 7
    cy0, cy1 = py - 5, py + 7
    # 左、右侧：覆盖的行投影完全落在 [b,b+h)
    if b <= cy0 and cy1 <= b + h:
        if px + 2 <= a:
            g = a - (px + 2)
            if 0 <= g <= 6:
                loss = max(loss, SIDE_LOSS[g])
        if px >= a + w:
            g = px - (a + w)
            if 0 <= g <= 6:
                loss = max(loss, SIDE_LOSS[g])
    # 下、上侧：覆盖的列投影完全落在 [a,a+w)
    if a <= cx0 and cx1 <= a + w:
        if py + 2 <= b:
            g = b - (py + 2)
            if 0 <= g <= 6:
                loss = max(loss, SIDE_LOSS[g])
        if py >= b + h:
            g = py - (b + h)
            if 0 <= g <= 6:
                loss = max(loss, SIDE_LOSS[g])
    return loss


def edges(x, y, w, h, axis):
    """端口边外侧格。axis 'EW'：左右两边；'NS'：下上两边。"""
    if axis == 'EW':
        return [[(x - 1, y + k) for k in range(h)], [(x + w, y + k) for k in range(h)]]
    return [[(x + k, y - 1) for k in range(w)], [(x + k, y + h) for k in range(w)]]


def build(R, Ps, forbid_edge0=False, minimize=None):
    a, b, w, h = R
    model = cp_model.CpModel()
    # --- 目标格 ---
    xcells = [(69, k) for k in range(1, 69)] + [(k, 69) for k in range(1, 69)]
    xcells = [c for c in xcells if not inside(c, R)]
    ring = [(a - 1, k) for k in range(b, b + h)] if a > 0 else []
    ring += [(a + w, k) for k in range(b, b + h)] if a + w < N else []
    ring += [(k, b - 1) for k in range(a, a + w)] if b > 0 else []
    ring += [(k, b + h) for k in range(a, a + w)] if b + h < N else []
    corner_in_R = inside((69, 69), R)
    touch = set(xcells) | set(ring) | {(69, 69)}

    def usable(pt):
        x, y = pt
        lo = 1 if forbid_edge0 else 0
        return lo <= x < N and lo <= y < N and not inside(pt, R)

    cover = {}  # cell -> list of body literals
    bodies = []  # (kind, rect, axis, var, extra)

    def add_body(kind, rect, axis):
        v = model.new_bool_var(f'{kind}_{rect}_{axis}')
        bodies.append((kind, rect, axis, v))
        for c in rect_cells(*rect):
            cover.setdefault(c, []).append(v)
        return v

    # --- 制造单位（机身不可入第 0 行/列：该 L 形只剩 1 格非取货口） ---
    shapes = [('small', 3, 3, 'EW'), ('small', 3, 3, 'NS'),
              ('medium', 5, 5, 'EW'), ('medium', 5, 5, 'NS'),
              ('large', 6, 4, 'NS'), ('large', 4, 6, 'EW')]
    machine_edges = []
    for kind, W, H, axis in shapes:
        for x in range(1, N - W + 1):
            for y in range(1, N - H + 1):
                rect = (x, y, W, H)
                if hit(rect, R):
                    continue
                if not (set(rect_cells(*rect)) & touch):
                    continue
                es = [[c for c in e if usable(c)] for e in edges(x, y, W, H, axis)]
                if not all(es):
                    continue
                v = add_body(kind, rect, axis)
                machine_edges.append((v, es))
    # --- 协议核心：6 个取货端口对面格、至少 2 个存货端口对面格可作运输格 ---
    core_req = []
    for x in range(1, N - 9 + 1):
        for y in range(1, N - 9 + 1):
            rect = (x, y, 9, 9)
            if hit(rect, R) or not (set(rect_cells(*rect)) & touch):
                continue
            for axis in ('EW', 'NS'):
                full = edges(x, y, 9, 9, axis)
                outs = [e[k] for e in full for k in (1, 4, 7)]
                other = edges(x, y, 9, 9, 'NS' if axis == 'EW' else 'EW')
                ins = [e[k] for e in other for k in range(1, 8)]
                if not all(usable(c) for c in outs):
                    continue
                ins = [c for c in ins if usable(c)]
                if len(ins) < 2:
                    continue
                v = add_body('core', rect, axis)
                core_req.append((v, outs, ins))
    # --- 供电桩 ---
    pole_terms = []
    for x in range(1, N - 2 + 1):
        for y in range(1, N - 2 + 1):
            rect = (x, y, 2, 2)
            if hit(rect, R) or not (set(rect_cells(*rect)) & touch):
                continue
            v = add_body('pole', rect, None)
            edge = int(bool({x, x + 1} & {1, 69})) + int(bool({y, y + 1} & {1, 69}))
            pole_terms.append((v, pole_loss(x, y, R), edge > 0, rect))

    # --- 不重叠；占用布尔 ---
    occ = {}
    for c, vs in cover.items():
        o = model.new_bool_var(f'occ_{c}')
        model.add(sum(vs) == o)
        occ[c] = o

    def free_lit(c):
        return occ[c].Not() if c in occ else None  # None = 必空闲（无候选覆盖）

    # 制造单位：每条端口边至少一格未被任何显式单位占据
    for v, es in machine_edges:
        for e in es:
            lits = []
            ok = False
            for c in e:
                fl = free_lit(c)
                if fl is None:
                    ok = True
                    break
                lits.append(fl)
            if not ok:
                model.add_bool_or(lits).only_enforce_if(v)
    for v, outs, ins in core_req:
        for c in outs:
            fl = free_lit(c)
            if fl is not None:
                model.add_implication(v, fl)
        terms = []
        const = 0
        for c in ins:
            if c in occ:
                terms.append(1 - occ[c])
            else:
                const += 1
        if const < 2:
            model.add(sum(terms) + const >= 2).only_enforce_if(v)

    # --- 数量上界 ---
    for kind, n in (('small', 131), ('medium', 48), ('large', 38), ('core', 1)):
        vs = [v for k, _, _, v in bodies if k == kind]
        if vs:
            model.add(sum(vs) <= n)

    # --- P、J、亏额预算 ---
    P = model.new_int_var_from_domain(cp_model.Domain.from_values(Ps), 'P')
    hid_edge = model.new_int_var(0, 12, 'hidden_edge_poles')
    hid_all = model.new_int_var(0, 12, 'hidden_poles')
    model.add(hid_all >= hid_edge)
    model.add(sum(v for v, *_ in pole_terms) + hid_all == P)
    J = model.new_int_var(0, 12, 'J')
    model.add(J == sum(v for v, _, e, _ in pole_terms if e) + hid_edge)
    budget = 23 * P - 217
    model.add(sum(l * v for v, l, _, _ in pole_terms) + 9 * hid_edge <= budget)
    model.add(9 * J <= budget)

    # --- X、Y ---
    X = sum(1 - occ[c] if c in occ else 1 for c in xcells)
    if not corner_in_R:
        cp = [v for v, _, _, rect in pole_terms if rect == (68, 68, 2, 2)]
        X = X + 2 * (1 - sum(cp))
    Y = sum(1 - occ[c] if c in occ else 1 for c in ring)
    Xv = model.new_int_var(0, 400, 'X')
    Yv = model.new_int_var(0, 400, 'Y')
    model.add(Xv == X)
    model.add(Yv == Y)
    if minimize is None:
        model.add(16 * P - 2 * J + Xv + Yv <= 187)
    elif minimize == 'X':
        model.minimize(Xv)
    elif minimize == 'Y':
        model.minimize(Yv)
    elif minimize == 'S':  # 面积缺口式左端 16P-2J+X+Y，达标须 <=187
        model.minimize(16 * P - 2 * J + Xv + Yv)
    meta = dict(bodies=bodies, P=P, J=J, X=Xv, Y=Yv, hid_edge=hid_edge, hid_all=hid_all,
                n_bodies=len(bodies), n_xcells=len(xcells), n_ring=len(ring))
    return model, meta


def check_solution(R, sol, forbid_edge0):
    """用直接格集合复核一个解（与 CP-SAT 编码无关）。"""
    a, b, w, h = R
    used = {}
    for kind, rect, axis in sol:
        for c in rect_cells(*rect):
            assert not inside(c, R), ('in R', kind, rect)
            assert c not in used, ('overlap', kind, rect, used[c])
            used[c] = kind
    lo = 1 if forbid_edge0 else 0
    ok = lambda c: lo <= c[0] < N and lo <= c[1] < N and not inside(c, R) and c not in used
    for kind, rect, axis in sol:
        if kind in ('small', 'medium', 'large'):
            for e in edges(*rect, axis):
                assert any(ok(c) for c in e), ('blocked edge', kind, rect, axis)
        if kind == 'core':
            full = edges(*rect, axis)
            assert all(ok(e[k]) for e in full for k in (1, 4, 7)), ('core out', rect)
            other = edges(*rect, 'NS' if axis == 'EW' else 'EW')
            assert sum(ok(e[k]) for e in other for k in range(1, 8)) >= 2, ('core in', rect)
    return True


def run(R, Ps, seconds, workers, forbid_edge0=False, minimize=None, tag=None, seed=7):
    t0 = time.monotonic()
    model, meta = build(R, Ps, forbid_edge0, minimize)
    bt = time.monotonic() - t0
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = seconds
    s.parameters.num_workers = workers
    s.parameters.random_seed = seed
    st = s.solve(model)
    out = dict(rect=list(R), P_domain=Ps, forbid_edge0=forbid_edge0, minimize=minimize,
               status=s.status_name(st), wall=round(s.wall_time, 3), build=round(bt, 3),
               workers=workers, seed=seed, n_bodies=meta['n_bodies'],
               n_xcells=meta['n_xcells'], n_ring=meta['n_ring'])
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        sol = [(k, r, ax) for k, r, ax, v in meta['bodies'] if s.value(v)]
        check_solution(R, sol, forbid_edge0)
        out.update(P=s.value(meta['P']), J=s.value(meta['J']), X=s.value(meta['X']),
                   Y=s.value(meta['Y']), hidden_edge=s.value(meta['hid_edge']),
                   hidden=s.value(meta['hid_all']),
                   bound=s.best_objective_bound if minimize else None,
                   bodies=[dict(kind=k, rect=list(r), axis=ax) for k, r, ax in sol])
    elif minimize and st == cp_model.UNKNOWN:
        out['bound'] = s.best_objective_bound
    if tag:
        (HERE / 'results' / f'{tag}.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('rect', type=int, nargs=4)
    ap.add_argument('--P', default='10,11,12')
    ap.add_argument('--seconds', type=float, default=120)
    ap.add_argument('--workers', type=int, default=6)
    ap.add_argument('--forbid-edge0', action='store_true')
    ap.add_argument('--minimize', choices=['X', 'Y', 'S'])
    ap.add_argument('--seed', type=int, default=7)
    ap.add_argument('--tag')
    args = ap.parse_args()
    out = run(tuple(args.rect), [int(p) for p in args.P.split(',')], args.seconds, args.workers,
              args.forbid_edge0, args.minimize, args.tag, args.seed)
    print(json.dumps({k: v for k, v in out.items() if k != 'bodies'}, ensure_ascii=False))
