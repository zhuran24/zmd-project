#!/usr/bin/env python3
"""关键数字两套编码：公式一套，枚举/状态搜索一套。"""
import json, itertools
from collections import deque
from fractions import Fraction as F

out = {}

# ---- S01：协议储存箱 3 个存货端口，每条存货通道两次送入至少隔 8 步，冷却 40 步内最多新进几件
f1 = 3 * (40 // 8)
best = 0
for ph in range(8):  # 枚举首件相位，贪心每 8 步一件（单通道最多次数），窗口为相邻两次传输之间的 T+1..T+40
    n = len([t for t in range(1, 41) if (t - ph) % 8 == 0 and t >= ph])
    best = max(best, n)
out['S01_new_products_per_cooldown'] = dict(formula=f1, enum=3 * best)

# ---- S03：表格
rows = {}
for name, a, b, m in (('研磨机', 2, 1, 6), ('封装机', 10, 15, 5), ('灌装机', 10, 10, 6)):
    from math import gcd
    g = gcd(a, b)
    Z0 = 50 * (b - a); L = b * (a - 1) - 50 * a; U = 50 * b - a * (b - 1)
    C = min(Z0 - L, U - Z0)
    dev = 2 * m * a * b // g
    # 枚举：危险态 (A 格满50且 B<b) 或 (B 满50且 A<a) 的 Z=b*A-a*B 的范围
    dz = [b * A - a * B for A in range(51) for B in range(51) if (A == 50 and B < b) or (B == 50 and A < a)]
    lo_bad = max(z for z in dz if z <= Z0)
    hi_bad = min(z for z in dz if z >= Z0)
    C_enum = min(Z0 - lo_bad, hi_bad - Z0)
    # 枚举单段前缀偏移
    seg = ['A'] * (a // g) + ['B'] * (b // g)
    pref = set()
    for perm in set(itertools.permutations(seg)):
        for i in range(len(perm) + 1):
            pa = perm[:i].count('A'); pb = perm[:i].count('B')
            pref.add(b * pa - a * pb)
    one = max(abs(x) for x in pref)
    dev_enum = m * (max(pref) - min(pref))
    rows[name] = dict(Z0=Z0, L=L, U=U, C=C, C_enum=C_enum, dev=dev, dev_enum_max=dev_enum,
                      ok=dev < C and dev_enum < C_enum)
out['S03_table'] = rows

# ---- S07：400 步；取货格下界 50-3k_v（公式）与抽象最坏情形搜索
out['S07_steps'] = dict(formula=8 * 50, last_start=8 * 49)


def worst_output(kv, init_min):
    """抽象：机器每 8 步可完成一批 kv 件（原料不缺），取货格 o；kv 条首格，每条收件后至少 8 步才能再收；
    下游何时腾空首格由对手决定。机器每步判定至多送一件。求可达的 o 最小值。
    缓存：('run',r) r=1..8 剩余步；('done',)。阶段：完成→判定→开批。"""
    starts = set()
    for o in range(init_min, 51):
        for cache in [('none',)] + [('run', r) for r in range(1, 9)] + [('done',)]:
            for cd in itertools.product(range(0, 9), repeat=kv):
                starts.add((o, cache, cd))
    seen = set(starts)
    dq = deque(starts)
    mn = 99
    while dq:
        o, cache, cd = dq.popleft()
        mn = min(mn, o)
        # 阶段1：完成
        c = cache
        if c[0] == 'run':
            c = ('done',) if c[1] == 1 else ('run', c[1] - 1)
        oo = o
        if c[0] == 'done' and oo + kv <= 50:
            oo += kv; c = ('none',)
        # 阶段2：首格腾空由对手选（cd=0 表示可收；cd>0 表示还在滞留中，到 0 才可被腾空）
        # cd 语义：距离首格物品成熟还差几步；0 且对手选择腾空 -> 空
        opts = []
        for i in range(kv):
            opts.append([True, False] if cd[i] == 0 else [False])
        for emp in itertools.product(*opts):
            if any(emp) and oo > 0:
                choices = [i for i in range(kv) if emp[i]]
            else:
                choices = [None]
            for ch in choices:
                o2 = oo
                c2 = c
                cd2 = list(cd)
                if ch is not None:
                    o2 -= 1
                    cd2[ch] = 8
                    mn = min(mn, o2)
                    if c2[0] == 'done' and o2 + kv <= 50:
                        o2 += kv; c2 = ('none',)
                # 未被选中的空首格保持空（cd=0），下一步对手仍可“腾空”=保持可收
                # 阶段3：开批（原料不缺）
                if c2[0] == 'none':
                    c2 = ('run', 8)
                cd3 = tuple(max(0, x - 1) if x > 0 else 0 for x in cd2)
                st = (o2, c2, cd3)
                if st not in seen:
                    seen.add(st)
                    dq.append(st)
    return mn, len(seen)


s07 = {}
for kv in (1, 2, 3):
    mn, n = worst_output(kv, 50 - kv)
    s07[kv] = dict(formula_bound=50 - 3 * kv, abstract_min=mn, states=n, bound_holds=mn >= 50 - 3 * kv)
out['S07_output_floor'] = s07

# ---- S08：176 常数
L1 = L2 = 0
cap = F(50) + 1 + 50 + 50 + 1 + F(50, 2)  # A存货+A缓存+A取货+C存货+C缓存+C取货/2（不含两条带）
sat = F(50) + 50 + 1 + 50 + 1 + F(49, 2)
out['S08_const'] = dict(max_phi_minus_L=str(cap), saturated_u=str(sat), bound=str(sat - F(1, 2)))

json.dump(out, open('key_numbers.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
