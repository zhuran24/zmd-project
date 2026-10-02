"""复核97M 第二套内带缺口编码（与 band.py 不共用任何函数）。
几何与分支按本席自己的推理（报告 §4）：
  * 左边 23 个仓库取货口占第 0 列，缺格行 gl∈{0,3,…,69}；下边同理 gb；gl、gb 至少一个为 0。
  * 矿石格 O：取货口中间格正对的第 1 列/第 1 行格，共 46 个。
  * 法向消费机：3×3 粉碎机/精炼炉，存货边贴第 1 列（占第 2..4 列）或贴第 1 行（占第 2..4 行），
    存货边正对一个 O；一台机器只有一条存货边，至多计 1。
  * 缺口机：唯一非角三格空当处的 3×3（位置唯一）。
      - 角上（gl=3 或 gb=3）：本席证明非耗矿机不可行，耗矿机与 O 的正流量接口至多 1；塑形机不可行。
        另报「放宽」口径：接口按 2 计（与推导席同口径）。
      - 非角：与 O 的正流量接口至多 2；塑形机时另加 w≤1，且存货边上另一端口格须为运输格。
  * 每侧消费机至多 22 台（23 台时窄条封闭，进 24 股满速矿、出至多 23）。
  * 矩形：左下角 (2,b)，宽 6，高 H=6..9，3≤b≤69−H，d=左带 O 落在行 b..b+H−1 的个数，只取 d≤2。
求解：OR-Tools CP-SAT，单线程，按格互斥的 0-1 模型。
输出：band2_{base,rect}.json，逐支 (gl,gb,H,b,分支,N+w,d)。
"""
import json, sys, time
from pathlib import Path
from ortools.sat.python import cp_model

OUT = Path(__file__).resolve().parent


def ore_cells(gl, gb):
    O = set()
    starts_l = [s for s in range(70) if s != gl]
    # 把 0..69 去掉 gl 后每 3 格一组
    def groups(skip):
        seq = [s for s in range(70) if s != skip]
        assert len(seq) == 69
        return [seq[i:i + 3] for i in range(0, 69, 3)]
    for g in groups(gl):
        assert g[2] - g[0] == 2, (gl, g)
        O.add((1, g[1]))
    for g in groups(gb):
        assert g[2] - g[0] == 2, (gb, g)
        O.add((g[1], 1))
    return O


def gap_info(gl, gb):
    """返回 (缺口机占格, 侧, 是否角上, 两条端口边各自对着的三格)；没有非角三格空当时 None。"""
    if 0 < gl < 69:
        cells = {(x, y) for x in (1, 2, 3) for y in (gl - 1, gl, gl + 1)}
        low = [(x, gl - 2) for x in (1, 2, 3)]
        high = [(x, gl + 2) for x in (1, 2, 3)]
        return cells, 'L', gl == 3, low, high
    if 0 < gb < 69:
        cells = {(x, y) for y in (1, 2, 3) for x in (gb - 1, gb, gb + 1)}
        low = [(gb - 2, y) for y in (1, 2, 3)]
        high = [(gb + 2, y) for y in (1, 2, 3)]
        return cells, 'B', gb == 3, low, high
    return None


def consumers(O):
    out = []  # (侧, 对着的 O, 占格 frozenset)
    for (x, y) in O:
        if x == 1:
            for r in (y - 2, y - 1, y):
                if r >= 1 and r + 2 <= 69:
                    out.append(('L', (x, y), frozenset((cx, cy) for cx in (2, 3, 4) for cy in range(r, r + 3))))
        if y == 1:
            for c in (x - 2, x - 1, x):
                if c >= 1 and c + 2 <= 69:
                    out.append(('B', (x, y), frozenset((cx, cy) for cy in (2, 3, 4) for cx in range(c, c + 3))))
    # 同一占格按一台机器计一次
    seen = {}
    for side, o, cells in out:
        seen.setdefault(cells, set()).add(side)
    return [(cells, sides) for cells, sides in seen.items()]


def solve(cands, blocked):
    m = cp_model.CpModel()
    use = []
    for cells, sides in cands:
        if cells & blocked:
            continue
        use.append((m.NewBoolVar(''), cells, sides))
    by_cell = {}
    for v, cells, _ in use:
        for c in cells:
            by_cell.setdefault(c, []).append(v)
    for vs in by_cell.values():
        if len(vs) > 1:
            m.AddAtMostOne(vs)
    # 每侧至多 22：一台机器若两侧都可算，按它真实贴的那一侧（存货边只有一条），取保守：可算任一侧
    side_vars = {}
    for v, cells, sides in use:
        for s in sides:
            side_vars.setdefault(s, []).append(v)
    # 两侧都可算的机器只能选一侧计入每侧上限；引入选择变量
    tot = []
    cnt = {'L': [], 'B': []}
    for v, cells, sides in use:
        if len(sides) == 1:
            s = next(iter(sides)); cnt[s].append(v); tot.append(v)
        else:
            a = m.NewBoolVar(''); b = m.NewBoolVar('')
            m.Add(a + b == v)
            cnt['L'].append(a); cnt['B'].append(b); tot.append(v)
    for s in 'LB':
        m.Add(sum(cnt[s]) <= 22)
    m.Maximize(sum(tot))
    sol = cp_model.CpSolver()
    sol.parameters.num_workers = 1
    st = sol.Solve(m)
    assert st == cp_model.OPTIMAL, st
    return int(round(sol.ObjectiveValue()))


def branches(gl, gb, rect, relaxed_corner):
    O = ore_cells(gl, gb)
    assert len(O) == 46
    cands = consumers(O)
    rect_cells = set()
    if rect:
        rx, ry, rw, rh = rect
        rect_cells = {(rx + i, ry + j) for i in range(rw) for j in range(rh)}
        assert not (rect_cells & O)
    base_block = O | rect_cells
    res = [('0', 46 + solve(cands, base_block))]
    gi = gap_info(gl, gb)
    if gi is None:
        return res
    cells, side, corner, low, high = gi
    if cells & rect_cells:
        return res
    adjO = {(x + dx, y + dy) for (x, y) in cells for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))} & O
    if corner:
        extra = 2 if relaxed_corner else 1
        res.append(('G', 46 + extra + solve(cands, base_block | cells)))
        return res   # 角上塑形机不可行
    assert len(adjO) == 2, (gl, gb, adjO)
    res.append(('G', 46 + 2 + solve(cands, base_block | cells)))
    best = None
    for edge in (low, high):
        o = edge[0]
        assert o in O
        for free in edge[1:]:
            if free in O or free in rect_cells:
                continue
            v = 46 + 3 + solve(cands, base_block | cells | {free})
            best = v if best is None else max(best, v)
    if best is not None:
        res.append(('S', best))
    return res


def configs():
    return [(gl, gb) for gl in range(0, 70, 3) for gb in range(0, 70, 3) if gl == 0 or gb == 0]


def main(part, relaxed):
    t0 = time.monotonic()
    rows = []
    for gl, gb in configs():
        if part == 'base':
            for br, v in branches(gl, gb, None, relaxed):
                rows.append([gl, gb, None, None, br, v, 0])
        else:
            O = ore_cells(gl, gb)
            for H in range(6, 10):
                for b in range(3, 70 - H):
                    d = sum(1 for (x, y) in O if x == 1 and b <= y < b + H)
                    if d > 2:
                        continue
                    for br, v in branches(gl, gb, (2, b, 6, H), relaxed):
                        rows.append([gl, gb, H, b, br, v, d])
    mx = max(r[5] + r[6] for r in rows)
    worst = [r for r in rows if r[5] + r[6] == mx][:10]
    summ = dict(part=part, relaxed_corner=relaxed, rows=len(rows), max_N_w_d=mx, worst=worst,
                n_configs=len(configs()), seconds=round(time.monotonic() - t0, 1))
    tag = f"band2_{part}{'_relaxed' if relaxed else ''}"
    (OUT / f'{tag}.json').write_text(json.dumps(dict(summary=summ, rows=rows), ensure_ascii=False) + '\n')
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == '__main__':
    main(sys.argv[1], len(sys.argv) > 2 and sys.argv[2] == 'relaxed')
