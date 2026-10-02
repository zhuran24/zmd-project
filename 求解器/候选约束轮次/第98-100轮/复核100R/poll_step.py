"""编码一（逐步模拟）：分流器 S 三支各接一个物品准入口 g_i，g_i 直接送进各自的协议储存箱（总收得下）。
上游是一段满载的传送带 P（由仓库取货口供源矿）。
层数：g_i 送往非运输单位，层 1；S 送往 g_i，层 2；P 送往 S，层 3。每步：层 1 -> 层 2 -> 层 3。
准入口 g_i 只放行源矿，每 5 tick（W 步，取 40 或 41）收下上限 L_i；窗口从收下第一件起算，走完后下一件重新起算。
阻断时不收货。运输格滞留 8 步。
分流器轮询：按排法 pi 的接通先后循环；第一次从第二条（pi[1]）开始；之后从上次成功的下一条开始。
输出：进入循环后各支每 tick 的通过量（精确分数）。
"""
import itertools, json, sys
from fractions import Fraction

def run(L, pi, W=40, max_steps=200000):
    # 状态
    S_has, S_in = True, 0          # P 在第 0 步把首件送进 S（P 已满载）
    last = None                     # 上次成功的支序号（pi 中的位置）
    g_has = [False] * 3; g_in = [0] * 3
    w0 = [None] * 3; wc = [0] * 3
    deliv = [0] * 3
    seen = {}
    hist = []
    for t in range(1, max_steps):
        # 层 1：g_i 送进储存箱
        for i in range(3):
            if g_has[i] and t - g_in[i] >= 8:
                g_has[i] = False; deliv[i] += 1
        # 层 2：S
        if S_has and t - S_in >= 8:
            start = 1 if last is None else (last + 1) % 3
            for k in range(3):
                pos = (start + k) % 3
                i = pi[pos]
                blocked = (w0[i] is not None and t < w0[i] + W and wc[i] >= L[i])
                if (not g_has[i]) and not blocked:
                    g_has[i] = True; g_in[i] = t
                    if w0[i] is None or t >= w0[i] + W:
                        w0[i] = t; wc[i] = 1
                    else:
                        wc[i] += 1
                    S_has = False; last = pos
                    break
        # 层 3：P 补进 S
        if not S_has:
            S_has, S_in = True, t
        # 状态签名（相对时刻，截断）
        sig = (S_has, min(t - S_in, 8), last,
               tuple((g_has[i], min(t - g_in[i], 8) if g_has[i] else 0,
                      (min(t - w0[i], W) if w0[i] is not None else -1), wc[i] if (w0[i] is not None and t < w0[i] + W) else 0)
                     for i in range(3)))
        hist.append(tuple(deliv))
        if sig in seen:
            t0 = seen[sig]
            per = t - t0
            d = [hist[-1][i] - hist[t0 - 1][i] for i in range(3)]
            return {"period_steps": per, "rates_per_tick": [str(Fraction(8 * x, per)) for x in d], "enter_step": t0}
        seen[sig] = t
    return None

if __name__ == "__main__":
    W = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    res = {}
    for L in itertools.product(range(1, 6), repeat=3):
        row = {}
        for pi in itertools.permutations(range(3)):
            r = run(L, pi, W)
            row["".join("ABC"[i] for i in pi)] = r["rates_per_tick"]
        res["".join(map(str, L))] = row
    # 同一第二条（起点相同）、循环方向相反的排法：xyz 与 zyx
    diffs = []
    for Ls, row in res.items():
        for pi in itertools.permutations("ABC"):
            p = "".join(pi); q = p[::-1]
            if p < q and row[p] != row[q]:
                diffs.append({"L": Ls, "pi": p, "rates": row[p], "pi_rev": q, "rates_rev": row[q]})
    json.dump({"W": W, "results": res, "same_start_reversed_cycle_differs": diffs}, open(f"poll_step_W{W}.json", "w"), ensure_ascii=False, indent=1)
    print("W", W, "L-triples", len(res), "same-start pairs differing:", len(diffs))
    for d in diffs[:8]:
        print(d)
