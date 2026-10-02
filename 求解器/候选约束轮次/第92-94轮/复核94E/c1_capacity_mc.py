#!/usr/bin/env python3
"""复核94E 编码一：分流器 X + n 格传送带元件 B 的放宽状态图，求 B 长期出货率的精确上界。

只用标准库 + numpy；不导入推导席脚本或 sim2。
模型（按快照规则第 23—27、29、31、60—61 行）：
- 一步 1/8 tick。运输物品格容量 1；物品进格后年龄 0，每过一步加 1（封顶 8），年龄 8 才能离格（滞留 1 tick）。
- X 每步判定一次，至多送出一件；B 的判定是从末格送出一件。B 只从 X 收货。
- 放宽（取超集，得上界）：X 的物品成熟时可送进 B 首格（若空）、送往其他支、或不送；
  B 末格成熟时下游可收可不收；X 空时源头可在 X 判定后补一件或不补；
  带内前挪：ASAP（每个微相位后从后往前级联），或 n<=3 时每个微相位每个可挪格任选挪不挪。
- 两种次序：XB（X 每步先于 B 判定）、BX（B 先）。
权重：B 本步送出件数。最大平均权重用整数势函数证书核验：
  λ=p/q（每步），w'=q·w−p，若存在 h 使每条边 h(s) ≥ w'+h(s')，则一切循环平均 ≤ λ。
达到性：确定性贪心策略（全部 ASAP、X 优先送 B、源头总补、下游总收）跑出循环，求其平均。
"""
import itertools, json, sys
from fractions import Fraction
import numpy as np

EMPTY = -1


def age_all(t):
    return tuple(a if a == EMPTY else min(a + 1, 8) for a in t)


def moves_asap(cells):
    c = list(cells)
    for i in range(len(c) - 2, -1, -1):
        if c[i] == 8 and c[i + 1] == EMPTY:
            c[i + 1] = 0
            c[i] = EMPTY
    return [tuple(c)]


def moves_nd(cells):
    """每个可挪格（从后往前）任选挪或不挪；返回全部结果。"""
    res = []
    def rec(c, i):
        if i < 0:
            res.append(tuple(c)); return
        if c[i] == 8 and c[i + 1] == EMPTY:
            c2 = list(c); c2[i + 1] = 0; c2[i] = EMPTY
            rec(c2, i - 1)
        rec(list(c), i - 1)
    rec(list(cells), len(cells) - 2)
    return list(set(res))


def transitions(state, n, order, nd):
    x, cells = state[0], state[1:]
    mv = moves_nd if nd else moves_asap
    out = set()
    x0 = x if x == EMPTY else min(x + 1, 8)
    c0 = age_all(cells)

    def x_judge(x, c):
        res = [(x, c)]  # 不送
        if x == 8:
            res.append((EMPTY, c))  # 送往其他支
            if c[0] == EMPTY:
                res.append((EMPTY, (0,) + c[1:]))
        return res

    def b_judge(c):
        res = [(c, 0)]
        if c[-1] == 8:
            res.append((c[:-1] + (EMPTY,), 1))
        return res

    for c1 in mv(c0):
        if order == 'XB':
            for (x1, c2) in x_judge(x0, c1):
                for c3 in mv(c2):
                    for (c4, w) in b_judge(c3):
                        for c5 in mv(c4):
                            for x2 in ([x1, 0] if x1 == EMPTY else [x1]):
                                out.add(((x2,) + c5, w))
        else:
            for (c2, w) in b_judge(c1):
                for c3 in mv(c2):
                    for (x1, c4) in x_judge(x0, c3):
                        for c5 in mv(c4):
                            for x2 in ([x1, 0] if x1 == EMPTY else [x1]):
                                out.add(((x2,) + c5, w))
    return out


def build(n, order, nd):
    vals = [EMPTY] + list(range(9))
    states = list(itertools.product(vals, repeat=n + 1))
    idx = {s: i for i, s in enumerate(states)}
    src, dst, w = [], [], []
    for s in states:
        for (t, ww) in transitions(s, n, order, nd):
            src.append(idx[s]); dst.append(idx[t]); w.append(ww)
    return states, idx, np.array(src), np.array(dst), np.array(w, dtype=np.int64)


def potential(nv, src, dst, wp, maxit=None):
    """最长路势函数；返回 (h, 迭代次数) 或 (None, it) 表示有正环。"""
    h = np.zeros(nv, dtype=np.int64)
    maxit = maxit or nv + 5
    for it in range(maxit):
        cand = wp + h[dst]
        nh = h.copy()
        np.maximum.at(nh, src, cand)
        if np.array_equal(nh, h):
            return h, it
        h = nh
    return None, maxit


def verify_potential(h, src, dst, wp):
    return bool(np.all(h[src] >= wp + h[dst]))


def greedy_cycle(n, order):
    """确定性贪心：ASAP、X 优先送 B、源头总补、下游总收。"""
    st = (EMPTY,) * (n + 1)
    seen = {}
    ws = []
    t = 0
    while st not in seen:
        seen[st] = t
        x, cells = st[0], st[1:]
        x = x if x == EMPTY else min(x + 1, 8)
        c = moves_asap(age_all(cells))[0]
        w = 0
        def xj(x, c):
            if x == 8 and c[0] == EMPTY:
                return EMPTY, (0,) + c[1:]
            return x, c
        def bj(c):
            if c[-1] == 8:
                return c[:-1] + (EMPTY,), 1
            return c, 0
        if order == 'XB':
            x, c = xj(x, c); c = moves_asap(c)[0]; c, w = bj(c); c = moves_asap(c)[0]
        else:
            c, w = bj(c); c = moves_asap(c)[0]; x, c = xj(x, c); c = moves_asap(c)[0]
        if x == EMPTY:
            x = 0
        ws.append(w)
        st = (x,) + c
        t += 1
    start = seen[st]
    cyc = ws[start:]
    return Fraction(8 * sum(cyc), len(cyc)), len(cyc)


def main():
    nmax = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    out = []
    for n in range(1, nmax + 1):
        for order in ('XB', 'BX'):
            for nd in ([False, True] if n <= 3 else [False]):
                states, idx, src, dst, w = build(n, order, nd)
                if order == 'XB':
                    lam = Fraction(n, 8 * n + 1)  # 每步
                else:
                    lam = Fraction(1, 8)
                wp = lam.denominator * w - lam.numerator
                h, it = potential(len(states), src, dst, wp)
                ok = h is not None and verify_potential(h, src, dst, wp)
                # 严格更小的 λ 应出现正环（说明上界不是空洞的）：用贪心循环直接给达到性
                gr, glen = greedy_cycle(n, order)
                rec = dict(n=n, order=order, nd_internal=nd, states=len(states), edges=int(len(src)),
                           claimed_bound_per_tick=str(lam * 8), certificate_ok=ok, bf_iterations=it,
                           greedy_rate_per_tick=str(gr), greedy_cycle_steps=glen,
                           tight=(gr == lam * 8))
                print(rec, flush=True)
                out.append(rec)
    json.dump(out, open(__file__.replace('.py', '.json'), 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
