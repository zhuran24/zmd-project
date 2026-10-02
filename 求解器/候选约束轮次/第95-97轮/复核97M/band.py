"""复核97M：内带缺口 N+w(+d)<=91 的独立重算。
编码 A：scipy.optimize.milp（HiGHS），按格互斥的 0-1 模型。
编码 B：组合动态规划：左侧消费机占第 2..4 列、下侧占第 2..4 行，二者只在角上冲突，
        故总数 = max(左(全)+下(起点>=5), 左(起点>=5)+下(全))，各侧用一维区间 DP。
放宽口径（本席自行推出，见报告）：
  * 法向消费机：3x3，存货边正对一个矿石格，每格至多一台；不压矿石格、缺口机、矩形；
  * 每侧至多 22 台（23 台必须占满 69 行，只有对边缺格在 3 时可能，此时第 1 列/行被封，24 股满速矿 > 23）；
  * 缺口机（3x3 占唯一非角缺格处 3 个内带格）：与矿石格的正流量接口至多 2；
  * 缺口机为塑形机时另有 w<=1，要求它存货边前另一格（第 2 或 3 列/行）是运输格；
    缺格在 3 时塑形机不可行（角上矿石格唯一出口是缺口机），仍按上界计入，结果另报。
"""
import json, sys, time
import numpy as np
from pathlib import Path
from scipy.optimize import milp, LinearConstraint, Bounds
OUT = Path(__file__).resolve().parent

def centers(gap):
    """一条边 70 格，23 个 3 格取货口，空 gap 格；返回各口中心坐标。"""
    cs, x = [], 0
    while x < 70:
        if x == gap: x += 1; continue
        cs.append(x+1); x += 3
    assert len(cs) == 23 and x == 70
    return cs

def configs():
    out = []
    for gl in range(0, 70, 3):
        for gb in range(0, 70, 3):
            if gl and gb: continue
            out.append((gl, gb))
    return out

def gap_machine(gl, gb):
    """唯一非角三格缺口处的缺口机格集与所在侧；没有则 None。"""
    if 0 < gl < 69: return 'L', gl, {(1+i, gl-1+j) for i in range(3) for j in range(3)}
    if 0 < gb < 69: return 'B', gb, {(gb-1+i, 1+j) for i in range(3) for j in range(3)}
    return None

def setup(gl, gb, mode, rect, wvariant=None):
    L = centers(gl); Bc = centers(gb)
    O = {(1, y) for y in L} | {(x, 1) for x in Bc}
    assert len(O) == 46
    forb = set(O)
    gm = gap_machine(gl, gb)
    extra = 0
    need_free = None
    if mode != '0':
        if gm is None: return None
        side, g, cells = gm
        if rect and any(rect[0] <= x < rect[0]+rect[2] and rect[1] <= y < rect[1]+rect[3] for x, y in cells):
            return None
        forb |= cells
        extra = 2
        if mode == 'S':
            # wvariant: (端, 列/行坐标)；端 -2 或 +2 表示存货边朝下/朝上（左侧缺口），坐标 2 或 3
            if wvariant is not None:
                end, coord = wvariant
                cell = (coord, g+end) if side == 'L' else (g+end, coord)
                if cell in forb: return None
                if rect and rect[0] <= cell[0] < rect[0]+rect[2] and rect[1] <= cell[1] < rect[1]+rect[3]:
                    return None
                need_free = cell
                extra += 1
    if rect:
        rx, ry, rw, rh = rect
        forb |= {(rx+i, ry+j) for i in range(rw) for j in range(rh)}
    if need_free: forb = forb | {need_free}
    # 候选消费机
    cand = []
    for y in L:
        for r in (y-2, y-1, y):
            cells = {(2+i, r+j) for i in range(3) for j in range(3)}
            if r < 1 or r+2 > 69 or cells & forb: continue
            cand.append(('L', y, r, cells))
    for x in Bc:
        for c in (x-2, x-1, x):
            cells = {(c+i, 2+j) for i in range(3) for j in range(3)}
            if c < 1 or c+2 > 69 or cells & forb: continue
            cand.append(('B', x, c, cells))
    return cand, extra

def solve_A(cand, extra):
    n = len(cand)
    if n == 0: return 46 + extra
    rows, lo, hi = [], [], []
    cellidx = {}
    for i, (_, _, _, cells) in enumerate(cand):
        for cl in cells: cellidx.setdefault(cl, []).append(i)
    srcidx = {}
    for i, (s, o, _, _) in enumerate(cand): srcidx.setdefault((s, o), []).append(i)
    A = []
    for lst in list(cellidx.values()) + list(srcidx.values()):
        if len(lst) > 1:
            row = np.zeros(n); row[lst] = 1; A.append(row); hi.append(1)
    for side in 'LB':
        row = np.array([1.0 if c[0] == side else 0.0 for c in cand]); A.append(row); hi.append(22)
    cons = LinearConstraint(np.array(A), -np.inf, np.array(hi, float))
    r = milp(-np.ones(n), constraints=cons, integrality=np.ones(n), bounds=Bounds(0, 1),
             options={'presolve': True})
    assert r.status == 0, r.message
    return 46 + extra + int(round(-r.fun))

def solve_B(cand, extra):
    left = sorted((c[2], c[1]) for c in cand if c[0] == 'L')   # (起点行, 矿石行)
    bot = sorted((c[2], c[1]) for c in cand if c[0] == 'B')
    def dp(ivs, minstart):
        # 区间 [s, s+2] 两两不交；矿石行各不同（不交的区间必各含不同矿石格，仍显式检查）
        ivs = [iv for iv in ivs if iv[0] >= minstart]
        best = {}  # 末端 -> (数目)
        from functools import lru_cache
        ivs.sort()
        @lru_cache(None)
        def f(i, last_end):
            if i == len(ivs): return 0
            s, o = ivs[i]
            r = f(i+1, last_end)
            if s > last_end: r = max(r, 1 + f(i+1, s+2))
            return r
        return f(0, -10)
    t1 = min(dp(left, 1), 22) + min(dp(bot, 5), 22)
    t2 = min(dp(left, 5), 22) + min(dp(bot, 1), 22)
    return 46 + extra + max(t1, t2)

def branch_value(gl, gb, mode, rect, solver):
    if mode == 'S':
        vals = []
        gm = gap_machine(gl, gb)
        if gm is None: return None
        # 不计 w 的塑形机等同缺口机（extra=2）；计 w 时枚举存货边方向与第二进料格
        base = setup(gl, gb, 'S', rect, None)
        if base is None: return None
        vals.append(solver(*base))
        for end in (-2, 2):
            for coord in (2, 3):
                s = setup(gl, gb, 'S', rect, (end, coord))
                if s is not None: vals.append(solver(*s))
        return max(vals)
    s = setup(gl, gb, mode, rect)
    if s is None: return None
    return solver(*s)

def run(enc, with_rect):
    solver = solve_A if enc == 'a' else solve_B
    rows = []
    t0 = time.monotonic()
    for gl, gb in configs():
        modes = ['0', 'G', 'S'] if gap_machine(gl, gb) else ['0']
        if not with_rect:
            for m in modes:
                v = branch_value(gl, gb, m, None, solver)
                rows.append([gl, gb, m, v])
        else:
            Lc = centers(gl)
            for h in range(6, 10):
                for b in range(3, 70-h):
                    d = sum(b <= y < b+h for y in Lc)
                    if d > 2: continue
                    for m in modes:
                        v = branch_value(gl, gb, m, (2, b, 6, h), solver)
                        rows.append([gl, gb, h, b, m, v, d, None if v is None else v+d])
    return rows, time.monotonic()-t0

if __name__ == '__main__':
    enc = sys.argv[1]; part = sys.argv[2]
    rows, sec = run(enc, part == 'rect')
    if part == 'base':
        mx = max(r[3] for r in rows if r[3] is not None)
        mx3 = max((r[3] for r in rows if r[3] is not None and not (r[2] == 'S' and 3 in (r[0], r[1]))), default=None)
        summary = dict(encoding=enc, part=part, branches=len(rows), max=mx, max_excluding_infeasible_S3=mx3, seconds=sec)
    else:
        valid = [r for r in rows if r[5] is not None]
        summary = dict(encoding=enc, part=part, branches=len(rows), infeasible=len(rows)-len(valid), solved=len(valid),
                       max_sum=max(r[7] for r in valid),
                       max_sum_excluding_S3=max(r[7] for r in valid if not (r[4] == 'S' and 3 in (r[0], r[1]))),
                       over91=[r for r in valid if r[7] > 91][:20], seconds=sec)
    (OUT/f'band_{enc}_{part}.json').write_text(json.dumps(dict(summary=summary, rows=rows), ensure_ascii=False)+'\n')
    print(json.dumps(summary, ensure_ascii=False))
