#!/usr/bin/env python3
"""复核103H：关键常数两套编码互核（分数编码；整数×2 编码）。"""
import json, sys
from fractions import Fraction as F

def frac():
    r = {}
    r['phi_max_minus_L'] = 3 * 50 + 2 + F(50, 2)            # CA/AC 满另计 L；A 存、A 取、C 存 各 50；两缓存；C 取 50 件记一半
    r['H150'] = 49 + 50 + 49 + 1 + 1                       # A 存>=49、A 取 50、C 存>=49、两缓存
    r['phi_b1_176'] = 50 + 50 + 50 + 1 + 1 + F(49, 2)       # 第一次 B 后
    r['H176'] = r['phi_b1_176'] - F(1, 2)
    r['box_15'] = 3 * (40 // 8)                            # 40 步内每口至多 5 件
    r['box_18_old'] = 3 * (40 // 8 + 1)                     # 闭区间 41 个步位
    r['Kout_min'] = {k: 50 - k for k in (2, 3)}
    r['steps_per_tick'] = 8; r['cooldown_steps'] = 5 * 8
    # 累计界：f(x)=min(x-1/2,H) 复合 n 次 = min(x-n/2, H-(n-1)/2)
    ok = True
    for H in (F(150), F(176)):
        for x2 in range(0, 500):
            x = F(x2, 2)
            v = x
            for n in range(1, 8):
                v = min(v - F(1, 2), H)
                if v != min(x - F(n, 2), H - F(n - 1, 2)): ok = False
    r['composition_ok'] = ok
    return r

def int2():
    """全部量乘 2 的整数编码。"""
    r = {}
    r['phi_max_minus_L'] = 2 * (3 * 50 + 2) + 50
    r['H150'] = 2 * (49 + 50 + 49 + 1 + 1)
    r['phi_b1_176'] = 2 * (50 * 3 + 2) + 49
    r['H176'] = r['phi_b1_176'] - 1
    r['box_15'] = 2 * 15
    r['box_18_old'] = 2 * 18
    r['Kout_min'] = {k: 2 * (50 - k) for k in (2, 3)}
    r['steps_per_tick'] = 16; r['cooldown_steps'] = 80
    ok = True
    for H in (300, 352):
        for x in range(0, 500):
            v = x
            for n in range(1, 8):
                v = min(v - 1, H)
                if v != min(x - n, H - (n - 1)): ok = False
    r['composition_ok'] = ok
    return r

a = frac(); b = int2()
cmp = {}
for k in a:
    if isinstance(a[k], dict):
        cmp[k] = all(2 * a[k][j] == b[k][j] for j in a[k])
    elif isinstance(a[k], bool):
        cmp[k] = a[k] and b[k]
    else:
        cmp[k] = (2 * a[k] == b[k])
out = dict(fraction={k: str(v) for k, v in a.items()}, agree=cmp)
json.dump(out, open(sys.argv[1], 'w'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False))
