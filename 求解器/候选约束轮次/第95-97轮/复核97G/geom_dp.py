#!/usr/bin/env python3
"""复核97G 编码乙：取货端口坐标公式 + 一维区间动态规划（纯 Python，无求解器）。

与编码甲（geom_milp.py）不共享任何代码。模型含义见复核97G.md 第3节：
左带法向消费机机身是第 2..4 列上的行区间 [r,r+2]，下带是第 2..4 行上的列区间 [c,c+2]；
两带区间只在 r<=4 且 c<=4 时相交（共用 [2,4]x[2,4]），其余冲突都是同一带内区间重叠。
"""
import json, os, sys, time
from functools import lru_cache

def mids(gap, other_gap):
    # 本边留空格在 gap（3 的倍数）；gap==0 时本边从第 1 格起铺，(0,0) 若被对边占用也不影响本边
    if gap == 0:
        return [2 + 3 * k for k in range(23)]
    return [1 + 3 * k for k in range(gap // 3)] + [gap + 2 + 3 * k for k in range((69 - gap) // 3)]

def all_configs():
    return [(gl, gb) for gl in range(0, 70, 3) for gb in range(0, 70, 3) if gl == 0 or gb == 0]

def max_disjoint(intervals, lo_free):
    """intervals: 闭区间列表；只允许起点 >= lo_free。返回最多互不重叠区间数（按右端排序 DP）。"""
    iv = sorted(set(i for i in intervals if i[0] >= lo_free), key=lambda t: (t[1], t[0]))
    # 经典 DP：best[k] = 前 k 个（按右端）里的最优
    ends = [e for _, e in iv]
    import bisect
    best = [0] * (len(iv) + 1)
    for k, (s, e) in enumerate(iv, 1):
        j = bisect.bisect_left(ends, s, 0, k - 1)  # 右端 < s 的个数
        best[k] = max(best[k - 1], best[j] + 1)
    return best[-1]

def solve(gl, gb, forbid_rect=None, mode='none', feeder=None, capB=None, capL=None):
    """返回法向消费机最多台数（不含 46 与缺格机常数）。forbid_rect 为矩形列表 (x0,x1,y0,y1)。"""
    ly = mids(gl, gb)
    bx = mids(gb, gl)
    Lset, Bset = set(ly), set(bx)
    rects = list(forbid_rect or [])
    g_side = 'L' if gl not in (0, 69) else ('B' if gb not in (0, 69) else None)
    g = gl if g_side == 'L' else gb
    if mode in ('unit', 'shape'):
        if g_side == 'L':
            rects.append((1, 3, g - 1, g + 1))
        else:
            rects.append((g - 1, g + 1, 1, 3))
    cells = set()
    if feeder is not None:
        cells.add(feeder)
    def hits(x0, x1, y0, y1):
        for (a0, a1, c0, c1) in rects:
            if x0 <= a1 and a0 <= x1 and y0 <= c1 and c0 <= y1:
                return True
        for (cx, cy) in cells:
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                return True
        return False
    left = []   # (r, r+2)
    for y in ly:
        for i in range(3):
            r = y - i
            if r < 1 or r + 2 > 69:
                continue
            if r == 1:
                # 机身含 (2..4,1)；只有下带 gb=3 时这三格都不是矿石格——那就是缺格机本身，不作法向选项
                continue
            if hits(2, 4, r, r + 2):
                continue
            left.append((r, r + 2))
    bottom = []
    for x in bx:
        for i in range(3):
            c = x - i
            if c < 1 or c + 2 > 69:
                continue
            if c == 1:
                continue
            if hits(c, c + 2, 2, 4):
                continue
            bottom.append((c, c + 2))
    # 角上至多各选一个 r<=4 / c<=4 的区间，且两者必相交
    Lc = [iv for iv in left if iv[0] <= 4]
    Bc = [iv for iv in bottom if iv[0] <= 4]
    Lr = [iv for iv in left if iv[0] > 4]
    Br = [iv for iv in bottom if iv[0] > 4]
    best = -1
    choices = [(None, None)] + [(l, None) for l in Lc] + [(None, b) for b in Bc]
    for l, b in choices:
        nl = (1 + max_disjoint(Lr, l[1] + 1)) if l else max_disjoint(Lr, 0)
        nb = (1 + max_disjoint(Br, b[1] + 1)) if b else max_disjoint(Br, 0)
        if capL is not None:
            nl = min(nl, capL)
        if capB is not None:
            nb = min(nb, capB)
        best = max(best, nl + nb)
    return best

def branches(gl, gb, R=None, d=0, sealing=True):
    """各分支的 N+w(+d)。R=(x0,x1,y0,y1) 或 None。"""
    rects = [R] if R else []
    out = {}
    g_side = 'L' if gl not in (0, 69) else ('B' if gb not in (0, 69) else None)
    out['none'] = 46 + solve(gl, gb, rects, 'none') + d
    if g_side is None:
        return out
    g = gl if g_side == 'L' else gb
    Gr = (1, 3, g - 1, g + 1) if g_side == 'L' else (g - 1, g + 1, 1, 3)
    def inter(A, B):
        return A[0] <= B[1] and B[0] <= A[1] and A[2] <= B[3] and B[2] <= A[3]
    if R and inter(Gr, R):
        out['unit'] = None
        out['shape'] = None
        return out
    caps = {}
    if g == 3 and sealing:
        caps = {'capB': 21} if g_side == 'L' else {'capL': 21}
    out['unit'] = 46 + solve(gl, gb, rects, 'unit', **caps) + 2 + d
    out['unit_nocap'] = 46 + solve(gl, gb, rects, 'unit') + 2 + d
    if g == 3:
        out['shape'] = None
        # 推导席的较弱限制：g=3 塑形机只计上端 1 个接口，w 只能借上端
        fs = [(2, 5), (3, 5)] if g_side == 'L' else [(5, 2), (5, 3)]
        vals = []
        for f in fs:
            if R and R[0] <= f[0] <= R[1] and R[2] <= f[1] <= R[3]:
                continue
            vals.append(46 + solve(gl, gb, rects, 'shape', feeder=f) + 1 + 1 + d)
        out['shape_weak'] = max(vals) if vals else None
        return out
    fs = ([(2, g + 2), (3, g + 2), (2, g - 2), (3, g - 2)] if g_side == 'L'
          else [(g + 2, 2), (g + 2, 3), (g - 2, 2), (g - 2, 3)])
    vals = []
    for f in fs:
        if R and R[0] <= f[0] <= R[1] and R[2] <= f[1] <= R[3]:
            continue
        vals.append(46 + solve(gl, gb, rects, 'shape', feeder=f) + 2 + 1 + d)
    out['shape'] = max(vals) if vals else None
    return out

def main():
    t0 = time.time()
    Hlo, Hhi = int(sys.argv[1]), int(sys.argv[2])
    side = sys.argv[3] if len(sys.argv) > 3 else 'a2'
    res = {'encoding': 'B: port formula + interval DP (pure python)', 'baseline': [], 'near': [], 'side': side}
    for gl, gb in all_configs():
        r = branches(gl, gb)
        r.update(gl=gl, gb=gb)
        res['baseline'].append(r)
    keys = ('none', 'unit', 'shape', 'unit_nocap', 'shape_weak')
    res['baseline_max'] = max(v for r in res['baseline'] for k, v in r.items() if k in keys and v is not None)
    nm = {k: None for k in keys}
    for gl, gb in all_configs():
        for H in range(Hlo, Hhi + 1):
            for b in range(3, 70 - H + 1):
                if side == 'a2':
                    ly = set(mids(gl, gb))
                    R = (2, 7, b, b + H - 1)
                    d = sum(1 for y in range(b, b + H) if y in ly)
                    r = branches(gl, gb, R, d)
                else:
                    # b=2 直接算：R=[b',b'+H-1]x[2,7]，这里 b 作列起点 a，H 作宽；周圈下侧是第 1 行
                    bx = set(mids(gb, gl))
                    R = (b, b + H - 1, 2, 7)
                    d = sum(1 for x in range(b, b + H) if x in bx)
                    r = branches(gl, gb, R, d)
                r.update(gl=gl, gb=gb, b=b, H=H, d=d)
                res['near'].append(r)
                for k in keys:
                    v = r.get(k)
                    if v is not None and (nm[k] is None or v > nm[k]):
                        nm[k] = v
    res['near_max_by_mode'] = nm
    res['H_range'] = [Hlo, Hhi]
    res['seconds'] = time.time() - t0
    fn = 'geom_dp_%s_H%d_%d.json' % (side, Hlo, Hhi)
    json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), fn), 'w'), ensure_ascii=False)
    print('baseline_max', res['baseline_max'], 'near_max_by_mode', nm, 'n', len(res['near']), 'sec', round(res['seconds'], 1))

if __name__ == '__main__':
    main()
