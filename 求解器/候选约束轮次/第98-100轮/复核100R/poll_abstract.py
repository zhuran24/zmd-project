"""抽象检验：分流器三支，第 i 支在第 t 步收得下当且仅当 avail_i(t)（外部给定的周期样式）。
S 的物品放满 8 步后每步尝试；送出后同步补货。比较同一起点（第二条）、循环方向相反的两种排法的长期分配。
只用来看循环方向能不能单独影响分配；不是游戏构型。"""
import itertools, json
from fractions import Fraction

def run(av, pi, P):
    S_in = 0; last = None; deliv = [0, 0, 0]
    seen = {}; hist = []
    for t in range(1, 50 * P + 2000):
        if t - S_in >= 8:
            start = 1 if last is None else (last + 1) % 3
            for kk in range(3):
                pos = (start + kk) % 3; i = pi[pos]
                if av[i][t % len(av[i])]:
                    deliv[i] += 1; last = pos; S_in = t; break
        sig = (t % P, min(t - S_in, 8), last)
        hist.append(tuple(deliv))
        if sig in seen:
            t0 = seen[sig]; per = t - t0
            return tuple(Fraction(8 * (hist[-1][i] - hist[t0 - 1][i]), per) for i in range(3))
        seen[sig] = t

# 三支：A 总收得下；B、C 按周期 p 在一段窗口内收得下
res = []
for pB in (16, 24, 40):
    for pC in (16, 24, 40):
        for onB in range(1, pB):
            for onC in range(1, pC, 3):
                for phC in range(0, pC, 4):
                    avA = [True]
                    avB = [(s % pB) < onB for s in range(pB)]
                    avC = [((s + phC) % pC) < onC for s in range(pC)]
                    P = pB * pC // __import__('math').gcd(pB, pC)
                    av = [avA, avB, avC]
                    r1 = run(av, (0, 1, 2), P); r2 = run(av, (2, 1, 0), P)
                    if r1 != r2:
                        res.append({"pB": pB, "onB": onB, "pC": pC, "onC": onC, "phC": phC,
                                    "ABC": [str(x) for x in r1], "CBA": [str(x) for x in r2]})
print("differing cases:", len(res))
for r in res[:5]: print(r)
json.dump({"differing": len(res), "examples": res[:50]}, open("poll_abstract.json", "w"), ensure_ascii=False, indent=1)
