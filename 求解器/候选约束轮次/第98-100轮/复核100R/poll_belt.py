"""编码一（逐步模拟），推广：分流器 S 第 i 支 = 长 k_i 格的传送带段 -> 物品准入口 g_i（每 W 步收下上限 L_i）-> 协议储存箱（总收得下）。
层数：g_i 层 1，传送带段 层 2，S 层 3，上游满载传送带 P 层 4。
带段的判定：从出口往回逐格处理：出口格的物品放满 8 步且 g_i 收得下就送出；其余各格物品放满 8 步且前一格空着就前移。
S 送进带段的入口格（入口格空着才收）。
分流器轮询按排法 pi 循环；第一次从第二条开始；之后从上次成功的下一条开始。
"""
import itertools, json, sys
from fractions import Fraction

def run(k, L, pi, W=40, max_steps=400000):
    S_has, S_in = True, 0
    last = None
    belts = [[None] * k[i] for i in range(3)]   # 每格：进入时刻或 None；下标 0 为入口格
    g_has = [False] * 3; g_in = [0] * 3
    w0 = [None] * 3; wc = [0] * 3
    deliv = [0] * 3
    seen = {}; hist = []
    for t in range(1, max_steps):
        # 层 1：准入口送进储存箱
        for i in range(3):
            if g_has[i] and t - g_in[i] >= 8:
                g_has[i] = False; deliv[i] += 1
        # 层 2：带段
        for i in range(3):
            b = belts[i]; n = len(b)
            # 出口格
            if b[n - 1] is not None and t - b[n - 1] >= 8:
                blocked = (w0[i] is not None and t < w0[i] + W and wc[i] >= L[i])
                if (not g_has[i]) and not blocked:
                    g_has[i] = True; g_in[i] = t
                    if w0[i] is None or t >= w0[i] + W:
                        w0[i] = t; wc[i] = 1
                    else:
                        wc[i] += 1
                    b[n - 1] = None
            for j in range(n - 2, -1, -1):
                if b[j] is not None and t - b[j] >= 8 and b[j + 1] is None:
                    b[j + 1] = t; b[j] = None
        # 层 3：S
        if S_has and t - S_in >= 8:
            start = 1 if last is None else (last + 1) % 3
            for kk in range(3):
                pos = (start + kk) % 3
                i = pi[pos]
                if belts[i][0] is None:
                    belts[i][0] = t
                    S_has = False; last = pos
                    break
        # 层 4：P 补进 S
        if not S_has:
            S_has, S_in = True, t
        sig = (min(t - S_in, 8), last,
               tuple(tuple(-1 if x is None else min(t - x, 8) for x in belts[i]) for i in range(3)),
               tuple((min(t - g_in[i], 8) if g_has[i] else -1,
                      (min(t - w0[i], W) if w0[i] is not None else -1),
                      wc[i] if (w0[i] is not None and t < w0[i] + W) else 0) for i in range(3)))
        hist.append(tuple(deliv))
        if sig in seen:
            t0 = seen[sig]; per = t - t0
            d = [hist[-1][i] - hist[t0 - 1][i] for i in range(3)]
            return [Fraction(8 * x, per) for x in d], per
        seen[sig] = t
    raise RuntimeError("no cycle")

if __name__ == "__main__":
    W = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    diffs = []; anydiff = 0; total = 0
    for k in itertools.product((1, 2, 3), repeat=3):
        for L in itertools.product(range(1, 6), repeat=3):
            total += 1
            row = {}
            for pi in itertools.permutations(range(3)):
                r, per = run(k, L, pi, W)
                row["".join("ABC"[i] for i in pi)] = ([str(x) for x in r], per)
            if len({tuple(v[0]) for v in row.values()}) > 1:
                anydiff += 1
            for p in list(row):
                q = p[::-1]
                if p < q and row[p][0] != row[q][0]:
                    diffs.append({"k": k, "L": L, "pi": p, "rates": row[p][0], "pi_rev": q, "rates_rev": row[q][0]})
    json.dump({"W": W, "configs": total, "configs_any_arrangement_diff": anydiff,
               "same_start_reversed_cycle_differs": diffs}, open(f"poll_belt_W{W}.json", "w"), ensure_ascii=False, indent=1)
    print("W", W, "configs", total, "any diff", anydiff, "same-start reversed differs", len(diffs))
    for d in diffs[:10]:
        print(d)
