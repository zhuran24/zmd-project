"""第二轮独立复算「运输下限」「运输降幅」里的数。"""
import itertools, math
from fractions import Fraction as Fr

# 1. 物料合计
flows = dict(蓝铁矿=34, 源矿=18, 蓝铁块=34, 蓝铁粉末=34, 源石粉末=18, 砂叶粉末=Fr(63, 2), 砂叶=21, 砂叶种子=21,
             荞花=11, 荞花种子=11, 荞花粉末=11, 致密蓝铁粉末=17, 钢块=17, 致密源石粉末=9, 细磨荞花粉末=Fr(11, 2),
             钢制零件=6, 钢质瓶=Fr(11, 2), 电池=Fr(3, 5), 胶囊=Fr(11, 20))
tot = sum(flows.values()); print('物料合计', float(tot), '取整', math.ceil(tot))

# 2. 边长 L、选 k 个位置的最小「非端口方向」数：相邻选中位置距离<=3 记 2
def f(L):
    best = {}
    for k in range(0, L + 1):
        b = None
        for S in itertools.combinations(range(L), k):
            c = sum(2 for a, bb in zip(S, S[1:]) if bb - a <= 3)
            b = c if b is None else min(b, c)
        best[k] = b
    return best
F = {L: f(L) for L in (3, 5, 6)}
print('f3', F[3], 'f5', F[5], 'f6', F[6])

# 3. 逐机型最小关联：n 台、每台选 k（0=闲置），有效口数 min(k,cap)，合计 >= need
def min_inc(n, L, cap, need):
    INF = 10 ** 9
    dp = [0] + [INF] * need  # dp[x]=达到有效口数 min(x,need) 的最小关联
    for _ in range(n):
        nd = [INF] * (need + 1)
        for x in range(need + 1):
            if dp[x] >= INF: continue
            for k in range(0, L + 1):
                y = min(need, x + min(k, cap))
                nd[y] = min(nd[y], dp[x] + F[L][k])
        dp = nd
    return dp[need]
types = {'粉碎(出)': (68, 3, 3, 95), '研磨(入)': (32, 6, 3, 95), '塑形(入)': (6, 3, 2, 11), '灌装(入)': (3, 6, 4, 11), '封装(入)': (3, 6, 5, 15)}
base_total = 0
for name, (n0, L, cap, need) in types.items():
    b = min_inc(n0, L, cap, need); base_total += b
    seq = []
    extra = 0
    while True:
        extra += 1
        v = min_inc(n0 + extra, L, cap, need)
        seq.append(Fr(b - v, 8))
        if v == 0: break
    print(name, '基准', b, '累计降幅', [str(x) for x in seq[:6]], '... 最多', str(seq[-1]), '于加', extra, '台')
print('五项合计', base_total, '/8 =', base_total / 8, ' 200 推导 (718+82)/4 =', (718 + base_total / 2) / 4)

# 4. 存货边加权 W 的最小值（每口流量 0..1、按正流量位置相邻距离<=3 记两端流量）
import numpy as np
def minW(L, d, grid=40):
    best = None
    for k in range(1, L + 1):
        for S in itertools.combinations(range(L), k):
            c = [0] * k
            for i in range(k - 1):
                if S[i + 1] - S[i] <= 3:
                    c[i] += 1; c[i + 1] += 1
            if d > k + 1e-12 or d <= k - 1 - 1e-12 and k > 1:
                # 需要每个位置都正，故 d>k-1 才必须用 k 个；更少位置的子集另行枚举
                pass
            if d > k + 1e-12: continue
            # 正流量 f_i in (0,1]，sum=d：贪心把流量放到系数小的
            order = sorted(range(k), key=lambda i: c[i])
            rem = d; val = 0; eps = 1e-9
            # 每个至少 eps
            rem -= eps * k; val += eps * sum(c)
            if rem < -1e-12: continue
            for i in order:
                t = min(1 - eps, rem); val += c[i] * t; rem -= t
            if rem > 1e-9: continue
            best = val if best is None else min(best, val)
    return best
for L, cap, lin in ((6, 3, lambda d: 2 * d - 4), (3, 2, lambda d: 2 * d - 2), (6, 4, lambda d: 4 * d - 10), (6, 5, None)):
    ok = True; pts = []
    for i in range(1, cap * 20 + 1):
        d = i / 20; w = minW(L, d)
        pts.append((d, round(w, 6)))
        if lin and w < lin(d) - 1e-6: ok = False
    print('L', L, 'cap', cap, '线性下界成立' if ok else '线性下界不成立', '端点', pts[-1], [p for p in pts if abs(p[0] - round(p[0])) < 1e-9])
print('四类 W 合计', 2 * Fr(189, 2) - 4 * 32, 2 * 11 - 2 * 6, 4 * 11 - 10 * 3, 3 * 8, '=', 2 * Fr(189, 2) - 4 * 32 + 2 * 11 - 2 * 6 + 4 * 11 - 10 * 3 + 3 * 8)

# 5. 计数
S, R = 52 + 260, 305 + 2
print('S+R', S + R, '180:', math.ceil(Fr(S + R + 91 + 8, 4)), '200:', Fr(S + R + 99 + 82, 4),
      '207:', math.ceil(Fr(619 + 90 + 8 + 109, 4)), '208:', math.ceil(Fr(619 + 184 + 8 + 109 - 91, 4)),
      '209:', math.ceil(Fr(619 + 184 + 8 + 109 - 91 + 4, 4)), '306:', math.ceil(tot))
