"""三审自写：存货边方向权重 f 表（第 81 轮 C 组「任意增配的运输与面积方向预算」）。

一台机器的存货边长 L（研磨、封装、灌装为 6，塑形为 3），各位置端口的周期平均流量 0≤f≤1，
单机总进料 d≤dmax（研磨 3、塑形 2、封装 5、灌装 4）。把有正流量的端口按位置排序，相邻两个
位置差 ≤3 时，两端各记本端口流量。单机权重 W(d)=给定 d 时的最小记权；机群最小
Σ W(d_j)，Σ d_j = 全类总进料（研磨 94.5、塑形 11、封装 15、灌装 11），每台 0≤d_j≤dmax。

两套写法：
  甲：枚举端口支持集，按记权系数从小到大灌满（线性规划的贪心解），得单机 W；机群在半件格上动态规划。
  乙：不用支持集，直接枚举每口 0、1/4、…、1 的全部流量向量算记权，得单机 W；机群在 1/4 件格上动态规划。
甲的半件格是精确的：W 分段线性、断点在整数，最优解可取至多一台非整数（交换论证），总量是半整数；
乙在更细的格上独立复算，两者逐项一致即说明没有漏掉更小值。
"""
from fractions import Fraction as Fr
from itertools import combinations, product
import json, pathlib

OUT = pathlib.Path(__file__).with_name("out") / "weights.json"

TYPES = {  # 边长, 单机上限, 全类总进料, 最低台数
    "研磨机": (6, 3, Fr(189, 2), 32),
    "塑形机": (3, 2, Fr(11), 6),
    "封装机": (6, 5, Fr(15), 3),
    "灌装机": (6, 4, Fr(11), 3),
}
CLAIM = {
    "研磨机": lambda n: Fr(379 - 8 * n, 2) if n <= 47 else Fr(0),
    "塑形机": lambda n: Fr(max(0, 22 - 2 * n)),
    "封装机": lambda n: Fr({3: 24, 4: 18, 5: 10, 6: 6, 7: 2}.get(n, 0)),
    "灌装机": lambda n: Fr({3: 14, 4: 6, 5: 2}.get(n, 0)),
}


def coeffs(support):
    """支持集（位置升序）中每个端口被记权的次数。"""
    c = [0] * len(support)
    for i in range(len(support) - 1):
        if support[i + 1] - support[i] <= 3:
            c[i] += 1
            c[i + 1] += 1
    return c


def W_greedy(L, d):
    """甲：min over 支持集 of 贪心灌满（系数小的先满）。支持集大小须 ≥ d。"""
    best = None
    for k in range(0, L + 1):
        if k < d:
            continue
        for S in combinations(range(1, L + 1), k):
            c = sorted(coeffs(S))
            rem, w = d, Fr(0)
            for ci in c:
                take = min(Fr(1), rem)
                w += ci * take
                rem -= take
            if rem == 0 and (best is None or w < best):
                best = w
    return best


def W_brute(L, dmax, q):
    """乙：直接枚举每口流量 0..1 步长 1/q，按实际正流量端口算记权；返回 d(以 1/q 为单位)→最小权。"""
    best = {}
    for vec in product(range(q + 1), repeat=L):
        tot = sum(vec)
        if tot > dmax * q:
            continue
        pos = [i for i, v in enumerate(vec) if v > 0]
        w = 0
        for a, b in zip(pos, pos[1:]):
            if b - a <= 3:
                w += vec[a] + vec[b]
        if tot not in best or w < best[tot]:
            best[tot] = w
    return {t: Fr(w, q) for t, w in best.items()}


def fleet(single, step, total, n):
    """机群最小：single[k]=W(k·step)，k=0..K；Σ k_j·step = total。动态规划。"""
    K = max(single)
    T = int(total / step)
    assert Fr(T) * step == total
    INF = None
    dp = [INF] * (T + 1)
    dp[0] = Fr(0)
    for _ in range(n):
        nd = [INF] * (T + 1)
        for t in range(T + 1):
            if dp[t] is None:
                continue
            for k in range(0, K + 1):
                if t + k > T:
                    break
                v = dp[t] + single[k]
                if nd[t + k] is None or v < nd[t + k]:
                    nd[t + k] = v
        dp = nd
    return dp[T]


def main():
    res = {"单机": {}, "机群": {}, "增配净增": {}}
    for name, (L, dmax, total, nmin) in TYPES.items():
        # 甲：半件格
        sA = {k: W_greedy(L, Fr(k, 2)) for k in range(0, 2 * dmax + 1)}
        # 乙：1/4 件格，直接枚举流量向量
        sB = W_brute(L, dmax, 4)
        # 单机逐点比：甲在半件点 = 乙在同一点
        for k, v in sA.items():
            assert sB[2 * k] == v, (name, k, v, sB[2 * k])
        res["单机"][name] = {str(Fr(k, 2)): str(v) for k, v in sA.items()}
        res["机群"][name] = {}
        hi = nmin + 20
        for n in range(nmin, hi + 1):
            fa = fleet(sA, Fr(1, 2), total, n)
            fb = fleet(sB, Fr(1, 4), total, n)
            claim = CLAIM[name](n)
            assert fa == fb == claim, (name, n, fa, fb, claim)
            res["机群"][name][n] = str(fa)
    # 首台及逐台增配净增 4×占地 + Ω 变化（其余机型不变）
    area = {"研磨机": 24, "塑形机": 9, "封装机": 24, "灌装机": 24}
    for name, (L, dmax, total, nmin) in TYPES.items():
        steps = []
        for n in range(nmin, nmin + 20):
            steps.append(4 * area[name] + CLAIM[name](n + 1) - CLAIM[name](n))
        res["增配净增"][name] = {"首台": str(steps[0]), "最小一步": str(min(steps))}
    for name, a in (("粉碎机", 9), ("精炼炉", 9), ("配件机", 9), ("种植机", 25), ("采种机", 25), ("协议储存箱", 9)):
        res["增配净增"][name] = {"首台": str(4 * a), "最小一步": str(4 * a)}
    omega_min = sum(CLAIM[k](TYPES[k][3]) for k in TYPES)
    res["最低配置Ω"] = str(omega_min)
    res["全部增配最小一步"] = str(min(Fr(v["最小一步"]) for v in res["增配净增"].values()))
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("单机", "增配净增", "最低配置Ω", "全部增配最小一步")}, ensure_ascii=False, indent=1))
    print("机群表与条文 f 逐项一致（甲半件格、乙 1/4 件格），n 至下限+20")


if __name__ == "__main__":
    main()
