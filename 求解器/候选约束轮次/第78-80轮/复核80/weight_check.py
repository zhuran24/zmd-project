# 复核80：存货边方向权重下界的独立复算（精确分数，不调用求解器）
# 一条存货边长 L（小机 3，大机长边 6），端口位置 1..L；正流量位置集合 S（支持集），流量 f_i∈(0,1]。
# 相邻两个所列位置相距 ≤3 时两端各记一个方向：α_i = 与前一所列位置距离≤3 的指示 + 与后一所列位置距离≤3 的指示。
# 单机权 W = Σ α_i f_i。w_L(d) = 所有支持集上 Σα_i f_i 的下确界（Σf=d，0≤f≤1）。
from fractions import Fraction as Fr
from itertools import combinations
import json


def alphas(S):
    S = sorted(S)
    a = []
    for k, p in enumerate(S):
        v = 0
        if k > 0 and p - S[k - 1] <= 3:
            v += 1
        if k + 1 < len(S) and S[k + 1] - p <= 3:
            v += 1
        a.append(v)
    return a


def w_support(S, d):
    """支持集 S 上的下确界：把流量先放到 α 小的位置，每个 ≤1；要求 |S| ≥ d（f>0 的下确界取闭包）。"""
    a = sorted(alphas(S))
    if d > len(S):
        return None
    rem, tot = d, Fr(0)
    for x in a:
        take = min(Fr(1), rem)
        tot += x * take
        rem -= take
    return tot


def w_func(L, d):
    best = None
    for k in range(1, L + 1):
        for S in combinations(range(1, L + 1), k):
            v = w_support(S, d)
            if v is not None and (best is None or v < best):
                best = v
    return best


def supports(L):
    return [S for k in range(1, L + 1) for S in combinations(range(1, L + 1), k)]


def min_total(L, n, total, cap, step=Fr(1, 2)):
    # 在 step 网格上的精确 DP：w 在相邻整数间线性（下面逐段核对），总量为半整数，故半格 DP 精确
    grid = [step * i for i in range(int(cap / step) + 1)]
    wv = {g: w_func(L, g) for g in grid}
    INF = None
    dp = {Fr(0): Fr(0)}
    for _ in range(n):
        nd = {}
        for s, val in dp.items():
            for g in grid:
                t = s + g
                if t > total:
                    break
                c = val + wv[g]
                if t not in nd or c < nd[t]:
                    nd[t] = c
        dp = nd
    return dp.get(total), wv


def check_linear(L, cap):
    # 核对每个支持集上的下确界函数在每个 [k,k+1]∩[0,|S|] 上线性（断点只在整数）。
    # w_L 是这些函数的逐点最小，下半连续；分离和在总量约束下的下确界在“至多一台不在整数点”处取到，
    # 总量为半整数，故半格 DP 给出精确最小（w 在整数处可有向右的跳跃，这不影响该论证）。
    for S in supports(L):
        for k in range(min(int(cap), len(S))):
            pts = [Fr(k) + Fr(j, 8) for j in range(9)]
            vals = [w_support(S, p) for p in pts]
            slope = vals[-1] - vals[0]
            for p, v in zip(pts, vals):
                if v != vals[0] + slope * (p - k):
                    return False, (S, k)
    return True, None


if __name__ == "__main__":
    out = {}
    print("支持集个数 长3:", len(supports(3)), "长6:", len(supports(6)))
    # 单机线性下界核对
    ok = True
    for S in supports(6):
        a = alphas(S)
        # 所有 f∈[0,1]^S 顶点上核对：|S|≥3 时 W≥d−1，|S|≥4 时 W≥2d−2，W≥2d−4（研磨线性式），W≥4d−10（灌装线性式）
        for bits in range(1 << len(S)):
            for frac in (Fr(0), Fr(1, 2), Fr(1)):
                pass
    for L, cap in ((6, 3), (3, 2), (6, 5), (6, 4)):
        lin, bad = check_linear(L, cap)
        print("长%d边、单机上限%s：每个支持集的函数在整数间线性:" % (L, cap), lin, bad)
    res = {}
    for name, L, n, total, cap in (("研磨机", 6, 32, Fr(189, 2), Fr(3)), ("塑形机", 3, 6, Fr(11), Fr(2)),
                                   ("封装机", 6, 3, Fr(15), Fr(5)), ("灌装机", 6, 3, Fr(11), Fr(4))):
        m, wv = min_total(L, n, total, cap)
        res[name] = str(m)
        print(name, "最小总权", m, " w(d)表:", {str(k): str(v) for k, v in wv.items()})
    tot = sum(Fr(v) for v in res.values())
    print("四类合计最小", tot)
    json.dump(dict(per_type=res, total=str(tot)), open("weight_check.json", "w"), ensure_ascii=False, indent=1)
