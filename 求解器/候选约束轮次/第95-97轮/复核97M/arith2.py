"""复核97M：面积预算、换料余量、调试装料等数字的第二套编码（闭式公式，不与 arith.py 共用代码）。
单机最小权重用本席推出的闭式：存货边 ℓ 格、k 个正流量端口时，若能让某个相邻间距 >3 则该对不记权。
  ℓ=6：k≤2 时 0；k=3 时 f−1；k≥4 时 2f−2（端点记一次、内点记两次，内点合计 ≥f−2）。
  ℓ=3：k≤1 时 0；k=2 时 f。
机群最小：在半整数格上枚举台数分配（多重集合），取最小。
"""
import json, itertools
from fractions import Fraction as Fr
from functools import lru_cache
from math import floor, ceil
from pathlib import Path
OUT = Path(__file__).resolve().parent
H = Fr(1, 2)


def w6(f):
    if f <= 2: return Fr(0)
    if f <= 3: return f - 1
    return 2 * f - 2


def w3(f):
    if f <= 1: return Fr(0)
    return f


def group(total, n, cap, w):
    """n 台、每台 ≤cap、合计 total（半整数格），Σw 最小。"""
    levels = [Fr(i, 2) for i in range(0, int(2 * cap) + 1)]
    @lru_cache(None)
    def go(i, rem, lo):  # 非降序枚举
        if i == n:
            return Fr(0) if rem == 0 else None
        best = None
        for L in levels:
            if L < lo or L > rem: continue
            if rem - L > cap * (n - i - 1): continue
            r = go(i + 1, rem - L, L)
            if r is None: continue
            v = w(L) + r
            best = v if best is None or v < best else best
        return best
    return go(0, Fr(total), Fr(0))


res = {}
grind = {n: group(Fr(189, 2), n, 3, w6) for n in range(32, 49)}
shape = {n: group(11, n, 2, w3) for n in range(6, 12)}
pack = {n: group(15, n, 5, w6) for n in range(3, 9)}
fill = {n: group(11, n, 4, w6) for n in range(3, 7)}
for n, v in grind.items():
    assert v == (max(Fr(0), Fr(379 - 8 * n, 2)) if n <= 47 else 0), (n, v)
for n, v in shape.items():
    assert v == max(0, 22 - 2 * n), (n, v)
assert [pack[n] for n in range(3, 9)] == [24, 18, 10, 6, 2, 0]
assert [fill[n] for n in range(3, 7)] == [14, 6, 2, 0]
Omega = grind[32] + shape[6] + pack[3] + fill[3]
assert Omega == Fr(219, 2)
res['Ω'] = str(Omega)
# 增配一台时 4E+Ω 的增量
inc = dict(研磨=4 * 24 + grind[33] - grind[32], 塑形=4 * 9 + shape[7] - shape[6],
           封装=4 * 24 + pack[4] - pack[3], 封装第二台=4 * 24 + pack[5] - pack[4],
           灌装=4 * 24 + fill[4] - fill[3], 小机或箱=36, 种植采种=100)
res['增配增量'] = {k: str(v) for k, v in inc.items()}
assert min(inc.values()) == 34

# 占地与面积式
occ = 68 * 9 + 51 * 9 + 32 * 24 + 6 * 9 + 6 * 9 + 32 * 25 + 16 * 25 + 3 * 24 + 3 * 24
assert occ == 3291
rest = 4900 - occ - 81 - 46 * 3
assert rest == 1390
assert 4 * rest - 921 == 4639
# 619 = 305 + 260 + 52 + 2
inp = 68 + 51 + ceil(Fr(189, 2)) + 11 + 6 + 32 + 16 + 15 + 11
outp = ceil(18 + 34 + 11 + Fr(63, 2)) + 51 + 32 + 6 + 6 + 32 + 32 + 3 + 3
assert (inp, outp, inp + outp + 54) == (305, 260, 619)
# 921 链
assert 619 + 184 + 8 + 109 + 88 + 4 - 91 == 921
assert 619 + 90 + 8 == 717 and 717 + 88 + 4 == 809
# T≥208 与 1182
assert ceil(Fr(829, 4)) == 208 and 1390 - 208 == 1182
assert Fr(717) + Fr(219, 2) + 34 > 4 * 208
res['常数'] = dict(占地=occ, 余=rest, 面积式=4 * rest - 921, 接口=619)

# A=1110：P、J 分支
A = 1110
pj = {}
for P in range(10, 20):
    for J in range(0, P + 1):
        if 23 * P - 10 * J < 217 or 54 * P - 25 * J < 520: continue
        slack = 4639 - 4 * A - 16 * P + 2 * J   # X+Y 上限
        if slack < 0: continue
        pj.setdefault(P, {})[J] = slack
assert max(pj) == 13 and sorted(pj[13]) == [5, 6, 7] and pj[13][5] == 1
assert pj[12][0] == 7 and pj[10] == {0: 39}
res['A1110'] = {P: v for P, v in pj.items()}
# 增配：P=10,J=0 时 4E+Ω+X0+Y0 ≤ 4751−4A−16P+2J
cap10 = 4751 - 4 * A - 160
assert cap10 == 151
assert cap10 - Omega - 34 == Fr(15, 2) and cap10 - Omega - 36 == Fr(11, 2)
for P in (11, 12, 13):
    Jmax = max(J for J in range(P + 1) if 23 * P - 10 * J >= 217 and 54 * P - 25 * J >= 520)
    assert 4751 - 4 * A - 16 * P + 2 * Jmax - Omega < 34, P
# 外边表：ℓ ≤ 6X0+14c+8t+5k，取 c=1
def x0_min(l, k, t):
    return max(0, ceil(Fr(l - 14 - 8 * t - 5 * k, 6)))
table = {'贴右上': (71, 2, 1), '只贴一边': (101, 3, 2), '都不贴': (138, 2, 2)}
tab = {k: dict(单增配=x0_min(l, kk, t), 无增配=x0_min(l, kk, 0)) for k, (l, kk, t) in table.items()}
assert tab == {'贴右上': dict(单增配=7, 无增配=8), '只贴一边': dict(单增配=10, 无增配=12), '都不贴': dict(单增配=17, 无增配=19)}
res['外边表'] = tab
# 30×37 时 ℓ：两边各 69 格（角格各算一次）
assert 138 - 30 - 37 == 71 and 138 - 37 == 101
# 有增配时 A 上界与尺寸
Amax = Fr(4751 - 160 - 143, 1) / 4 - Fr(1, 8)
assert Fr(4751 - 160) - Fr(287, 2) == Fr(8895, 2) and Fr(8895, 8) == Fr(4447.5) / 4
def dims(a):
    return [(w, a // w) for w in range(6, 69) if a % w == 0 and 6 <= a // w <= 68]
res['尺寸'] = {a: dims(a) for a in (1111, 1110, 1109, 1108, 1107)}
assert dims(1111) == dims(1109) == dims(1108) == [] and dims(1110) == [(30, 37), (37, 30)] and dims(1107) == [(27, 41), (41, 27)]

# §8：研磨批次与换料余量
batt, caps = Fr(12), Fr(11)              # 每 20 tick
dense_src = 15 * batt; fine = 10 * caps
steel = 10 * batt + 2 * 10 * caps
batches20 = steel + dense_src + fine
assert batches20 == 630
rate = batches20 / 20
assert rate == Fr(63, 2)
sec8 = {}
for N in (32, 33):
    Wmax = 8 * (N - rate)                  # 次/tick
    amax = floor(9 * (N - rate))
    sec8[N] = dict(W每tick上限=str(Wmax), a上限=amax)
assert sec8[32] == dict(W每tick上限='4', a上限=4) and sec8[33]['a上限'] == 13
res['§8'] = sec8

# §10：装料数
take = 52 * 50 + 18 * (50 + 3) + 9 * (100 + 50 + 3) + 3 * 100 + 2 * 70 * 70
assert take == 15031 and 80000 - take == 64969 and 550 + 9800 == 10350
# Φ=100 ≥ L+5/2 ⇔ L≤97
assert max(L for L in range(0, 300) if 100 >= L + Fr(5, 2)) == 97
res['§10'] = dict(取出上界=take, 余量=80000 - take, 补装上界=10350, L上界=97)
(OUT / 'arith2.json').write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str) + '\n')
print(json.dumps(res, ensure_ascii=False, default=str)[:1500])
