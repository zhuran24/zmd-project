#!/usr/bin/env python3
"""方向预算 独立复核脚本（只读，不碰仓库）。
1. 四类机器存货边方向权函数 W(d)：两种独立方法（支持集+贪心 LP；逐口流量 1/4 格暴力）
2. 机群最小 Σ W：半格 DP（精确）与 1/4 格 DP 交叉
3. 与条文 f研、f塑、f封、f灌 逐项比对；Ω=109.5；逐台 4E+Ω 增量
4. 常数 3291、1390、717、809、4751、1005
5. 边带 47 种排布：92 个矿源切向能接端口的个数、内带 U 被 >=3 单位可占格并、桩占内带格数
6. 夹心桥接器（现行四格定向规则）对上下两台机器的可供流量
"""
from fractions import Fraction as Fr
from itertools import combinations, product
from functools import lru_cache

# ---------- 1. 单机权函数 ----------
# 机型: (存货边长, 单机每 tick 最大进料, 全类每 tick 总进料)
TYPES = {
    '研磨': (6, Fr(3), Fr(63, 2) * 3),      # 31.5 批 × 3 件
    '塑形': (3, Fr(2), Fr(11, 2) * 2),      # 5.5 批 × 2 件
    '封装': (6, Fr(5), Fr(3, 5) * 25),      # 0.6 批 × 25 件，5 tick 一批 → 5 件/tick
    '灌装': (6, Fr(4), Fr(11, 20) * 20),    # 0.55 批 × 20 件 → 4 件/tick
}

def coeffs(support):
    """支持集（排好序的端口位置）→ 每口在权中的系数：相邻正流量口距离<=3 时两端各记本口流量"""
    s = sorted(support)
    c = {p: 0 for p in s}
    for a, b in zip(s, s[1:]):
        if b - a <= 3:
            c[a] += 1
            c[b] += 1
    return c

def W_lp(L, d):
    """方法 A：穷尽支持集，固定支持集时权是流量的线性函数，0<=phi<=1、和=d，按系数从低到高贪心灌满即 LP 最优。
    闭包上取最优是安全的：某口流量降到 0 时真实权只会更小（见报告说明），故 min_S LP_S = 真实下确界且可达。"""
    best = None
    for k in range(0, L + 1):
        for S in combinations(range(1, L + 1), k):
            if k < d:   # 每口至多 1
                continue
            c = coeffs(S)
            order = sorted(S, key=lambda p: c[p])
            rem, w = d, Fr(0)
            for p in order:
                x = min(Fr(1), rem)
                w += c[p] * x
                rem -= x
            if rem == 0 and (best is None or w < best):
                best = w
    return best

def W_brute(L, step):
    """方法 B：逐口流量取 0, step, ..., 1 暴力，按实际正流量支持算权。返回 {d: 最小权}"""
    vals = [Fr(i) * step for i in range(int(1 / step) + 1)]
    res = {}
    for phi in product(vals, repeat=L):
        S = [i + 1 for i in range(L) if phi[i] > 0]
        c = coeffs(S)
        w = sum(c[p] * phi[p - 1] for p in S)
        d = sum(phi)
        if d not in res or w < res[d]:
            res[d] = w
    return res

def closed_form_W(name, d):
    """手推的单机权：研磨/封装/灌装（长 6）：d<=2 为 0；(2,3] 为 d-1；(3,6] 为 2d-2。塑形（长 3）：d<=1 为 0；(1,2] 为 d（3 口时 d+phi2>=d）"""
    if name == '塑形':
        return Fr(0) if d <= 1 else d
    if d <= 2:
        return Fr(0)
    if d <= 3:
        return d - 1
    return 2 * d - 2

single = {}
ok_single = True
for name, (L, cap, tot) in TYPES.items():
    grid = [Fr(i, 2) for i in range(int(cap * 2) + 1)]
    wa = {d: W_lp(L, d) for d in grid}
    wb = W_brute(L, Fr(1, 4))
    for d in grid:
        if wa[d] != wb[d] or wa[d] != closed_form_W(name, d):
            ok_single = False
            print('单机不一致', name, d, wa[d], wb[d], closed_form_W(name, d))
    # 1/4 格上 LP 与暴力也对
    for i in range(int(cap * 4) + 1):
        d = Fr(i, 4)
        if W_lp(L, d) != wb[d]:
            ok_single = False
            print('1/4 格不一致', name, d)
    single[name] = wa
    print(name, '单机 W(d) 半格表:', {str(k): str(v) for k, v in wa.items()})
print('单机权两法与手推闭式一致:', ok_single)

# ---------- 2. 机群最小 ----------
def group_min(name, n, step):
    L, cap, tot = TYPES[name]
    m = int(1 / step)
    capu, totu = int(cap * m), int(tot * m)
    w = [W_lp(L, Fr(i, m)) for i in range(capu + 1)]
    INF = None
    # dp[t] = 用若干台凑出总量 t 的最小权（逐台加入）
    dp = [Fr(0)] + [INF] * totu
    for _ in range(n):
        nd = [INF] * (totu + 1)
        for t in range(totu + 1):
            if dp[t] is None:
                continue
            for x in range(0, min(capu, totu - t) + 1):
                v = dp[t] + w[x]
                if nd[t + x] is None or v < nd[t + x]:
                    nd[t + x] = v
        dp = nd
    return dp[totu]  # None 表示装不下

def f_formula(name, n):
    if name == '研磨':
        return Fr(379 - 8 * n, 2) if n <= 47 else Fr(0)
    if name == '塑形':
        return Fr(max(0, 22 - 2 * n))
    if name == '封装':
        return Fr({3: 24, 4: 18, 5: 10, 6: 6, 7: 2}.get(n, 0))
    if name == '灌装':
        return Fr({3: 14, 4: 6, 5: 2}.get(n, 0))

RANGES = {'研磨': range(32, 56), '塑形': range(6, 20), '封装': range(3, 14), '灌装': range(3, 12)}
ok_group = True
gm = {}
for name, rg in RANGES.items():
    row = []
    for n in rg:
        a = group_min(name, n, Fr(1, 2))
        b = group_min(name, n, Fr(1, 4)) if n <= 40 else a
        f = f_formula(name, n)
        gm[(name, n)] = a
        row.append((n, str(a)))
        if a != b or a != f:
            ok_group = False
            print('机群不一致', name, n, a, b, f)
    print(name, '机群最小 Σ W:', row)
print('机群最小与条文 f 表逐项一致:', ok_group)

# 下限以下装不下（验证机型下限也自洽）
for name, n in [('研磨', 31), ('塑形', 5), ('封装', 2), ('灌装', 2)]:
    print('台数', name, n, '能否装下总量:', group_min(name, n, Fr(1, 2)) is not None)

Omega0 = sum(f_formula(nm, n) for nm, n in [('研磨', 32), ('塑形', 6), ('封装', 3), ('灌装', 3)])
print('最低配置 Ω =', Omega0, float(Omega0))

# ---------- 3. 逐台 4E+Ω 增量 ----------
AREA = {'粉碎': 9, '精炼': 9, '配件': 9, '塑形': 9, '种植': 25, '采种': 25, '研磨': 24, '封装': 24, '灌装': 24, '箱': 9}
BASE = {'研磨': 32, '塑形': 6, '封装': 3, '灌装': 3}
inc = {}
for k, a in AREA.items():
    if k in BASE:
        steps = [4 * a + f_formula(k, n + 1) - f_formula(k, n) for n in range(BASE[k], BASE[k] + 60)]
        inc[k] = (min(steps), steps[0])
    else:
        inc[k] = (4 * a, 4 * a)
print('逐台 4E+Ω 增量（最小, 首台）:', {k: (str(v[0]), str(v[1])) for k, v in inc.items()})
print('总体最小增量:', min(v[0] for v in inc.values()))

# ---------- 4. 常数 ----------
mins = {'粉碎': 68, '精炼': 51, '研磨': 32, '塑形': 6, '配件': 6, '种植': 32, '采种': 16, '封装': 3, '灌装': 3}
area_min = sum(mins[k] * AREA[k] for k in mins)
TF = 4900 - area_min - 81 - 46 * 3
print('机型下限占地', area_min, ' T+F 常数', TF)
print('717 = 619+90+8 ->', 619 + 90 + 8, ';  809 = 717+88+4 ->', 717 + 88 + 4)
print('4751 = 4*1390-809 ->', 4 * TF - 809)
print('矩形离带: a=2 最大', 9 * 68, ' a=3 最大', 15 * 67)

# ---------- 5. 边带排布 ----------
N = 70
def arrangements():
    out = []
    # 角 (0,0) 为空格 q
    out.append(('corner_q', [(0, 1 + 3 * i) for i in range(23)], [(1 + 3 * i, 0) for i in range(23)], (0, 0)))
    # 角属左边取货口：左边 70 格 23 个 + 1 空，空在第 3k 行 (k=1..23)；下边 1..69
    for k in range(1, 24):
        ys = [3 * i for i in range(k)] + [3 * i + 1 for i in range(k, 23)]
        out.append(('L%d' % k, [(0, y) for y in ys], [(1 + 3 * i, 0) for i in range(23)], (0, 3 * k)))
    for k in range(1, 24):
        xs = [3 * i for i in range(k)] + [3 * i + 1 for i in range(k, 23)]
        out.append(('B%d' % k, [(0, 1 + 3 * i) for i in range(23)], [(x, 0) for x in xs], (3 * k, 0)))
    return out

def check_arr(arr):
    name, left, bottom, q = arr
    occ = set()
    ore = []
    for (x, y) in left:      # 竖放 3×1 于第 0 列 y..y+2，取货端口朝 +x 于中格
        cells = {(0, y + t) for t in range(3)}
        assert not (cells & occ) and all(0 <= c[1] < N for c in cells)
        occ |= cells
        ore.append(((1, y + 1), 'L'))
    for (x, y) in bottom:
        cells = {(x + t, 0) for t in range(3)}
        assert not (cells & occ) and all(0 <= c[0] < N for c in cells)
        occ |= cells
        ore.append(((x + 1, 1), 'B'))
    boundary = {(0, y) for y in range(N)} | {(x, 0) for x in range(N)}
    assert boundary - occ == {q}, (name, boundary - occ)
    orecells = {c for c, _ in ore}
    assert len(orecells) == 46
    blocked = occ | orecells | {q}   # q 夹在取货口短边之间，任何 >=2 宽单位都放不进
    def free_block(x0, y0, w, h):
        if x0 < 0 or y0 < 0 or x0 + w > N or y0 + h > N:
            return False
        return all((x, y) not in blocked for x in range(x0, x0 + w) for y in range(y0, y0 + h))
    # (i) 矿源切向：沿边方向的邻格 n，存在以 n 为近端、沿该方向伸 >=3 的 3×3 块（更大单位必含这样的 3×3 子块）
    iface = 0
    for (cx, cy), side in ore:
        dirs = [(0, 1), (0, -1)] if side == 'L' else [(1, 0), (-1, 0)]
        for dx, dy in dirs:
            nx, ny = cx + dx, cy + dy
            found = False
            for off in range(3):  # 横向偏移
                if dx == 0:
                    x0 = nx - off
                    y0 = ny if dy == 1 else ny - 2
                else:
                    y0 = ny - off
                    x0 = nx if dx == 1 else nx - 2
                if free_block(x0, y0, 3, 3):
                    found = True
            iface += found
    # (ii) 内带 I 与 U
    I = {(1, y) for y in range(1, N)} | {(x, 1) for x in range(2, N)}
    U = I - orecells
    cover = set()
    for x0 in range(0, N - 2):
        for y0 in range(0, N - 2):
            if free_block(x0, y0, 3, 3):
                cover |= {(x, y) for x in range(x0, x0 + 3) for y in range(y0, y0 + 3)} & U
    pole_max = 0
    for x0 in range(0, N - 1):
        for y0 in range(0, N - 1):
            if free_block(x0, y0, 2, 2):
                pole_max = max(pole_max, len({(x, y) for x in range(x0, x0 + 2) for y in range(y0, y0 + 2)} & I))
    return iface, len(I), len(U), len(cover), pole_max

arrs = arrangements()
print('边带排布种数', len(arrs))
res = [check_arr(a) for a in arrs]
print('矿源切向可接端口数 最大', max(r[0] for r in res), '; |I|', set(r[1] for r in res), '; |U|', set(r[2] for r in res))
print('U 中可被 >=3×3 单位占的格之并 最大', max(r[3] for r in res), '; 单桩占 I 格数 最大', max(r[4] for r in res))

# ---------- 6. 夹心桥接器（现行规则：4 格，各连一边存货口与对边取货口） ----------
# 上下两边紧贴两台机器的存货边（只有存货端口），左右任意（可有取货端口供货）。
# 物品格 (in, out)：in 边须对着别单位的取货端口才可能收货；out 边对着机器存货端口才算给该机供货。
cells = [('N', 'S'), ('S', 'N'), ('E', 'W'), ('W', 'E')]
neighbor_has_output = {'N': False, 'S': False, 'E': True, 'W': True}   # N/S 是机器存货边
feeds = {'N': 0, 'S': 0}
for inn, out in cells:
    if out in feeds and neighbor_has_output[inn]:
        feeds[out] += 1
print('夹心桥接器能给上/下机器供货的物品格数:', feeds)
