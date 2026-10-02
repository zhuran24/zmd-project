"""复核97M：§7 首段带容量的状态图上界核验（本席独立编码，与 stepsim/dyn_checks 无共用）。
构型：分流器 S 每步先于 B 判定；S 送出后同一步即可从上游补入一件（对 B 最有利）；
S 的成熟物品可送 B 首格（空时）、送其他支（对手总收）或不送；B 为 n 格连续带，
物品成熟（停留≥8步）且前格空即前移（步首与每次移出后都移），末格成熟即送出（下游总收）。
状态：S 物品年龄（0..8，8 表示已成熟）、B 各格（None 或年龄 0..8）。
对每个 n 用两种算法求每步 B 出货的最大平均：
  A：值迭代 V_k，取 (V_k − V_{k−P})/P；
  B：在状态图上枚举从所有状态出发的贪心无关的全部简单环（Karp 最大平均环，整数权）。
"""
import json, itertools
from fractions import Fraction as Fr
from pathlib import Path
OUT = Path(__file__).resolve().parent
CAP = 8


def settle(cells):
    cells = list(cells)
    changed = True
    while changed:
        changed = False
        for j in range(len(cells) - 2, -1, -1):
            a = cells[j]
            if a is not None and a >= CAP and cells[j + 1] is None:
                cells[j + 1], cells[j] = 0, None
                changed = True
    return cells


def step(state, choice):
    s_age, cells = state
    cells = settle(cells)
    out = 0
    # S 判定
    if s_age >= CAP and choice != 'hold':
        if choice == 'B':
            if cells[0] is not None:
                return None
            cells[0] = 0
        s_age = None  # 送出（送 B 或其他支）
    elif choice != 'hold':
        return None
    # B 判定：末格成熟即送出，然后前移
    if cells[-1] is not None and cells[-1] >= CAP:
        cells[-1] = None
        out = 1
        cells = settle(cells)
    # 非运输/上游补 S（最有利：当步补入）
    if s_age is None:
        s_age = 0  # 本步补入（进入步记 0）
    # 进入下一步：年龄 +1
    s_age = min(CAP, s_age + 1)
    cells = tuple(None if c is None else min(CAP, c + 1) for c in cells)
    # 同一步新进的物品年龄记 0→下一步为 1：上面已 +1，进入步记 0 的物品在 8 步后为 8
    return (s_age, cells), out


def build(n):
    ages = [None] + list(range(0, CAP + 1))
    states = [(a, c) for a in range(0, CAP + 1) for c in itertools.product(ages, repeat=n)]
    idx = {s: i for i, s in enumerate(states)}
    edges = []
    for s in states:
        for ch in ('B', 'other', 'hold'):
            r = step(s, ch)
            if r is None:
                continue
            t, w = r
            edges.append((idx[s], idx[t], w))
    return states, edges


def value_iter(nst, edges, K, P):
    V = [0] * nst
    hist = []
    for k in range(K):
        W = [-10 ** 9] * nst
        for a, b, w in edges:
            v = w + V[b]
            if v > W[a]:
                W[a] = v
        V = W
        hist.append(max(V))
    return Fr(hist[-1] - hist[-1 - P], P)


def karp(nst, edges):
    # 最大平均环：对每个强连通的可达部分做 Karp（这里图小，直接全图，起点用超源）
    NEG = None
    D = [[NEG] * nst for _ in range(nst + 1)]
    D[0] = [0] * nst  # 超源到各点 0
    for k in range(1, nst + 1):
        Dk, Dp = D[k], D[k - 1]
        for a, b, w in edges:
            if Dp[a] is not None:
                v = Dp[a] + w
                if Dk[b] is None or v > Dk[b]:
                    Dk[b] = v
    best = None
    for v in range(nst):
        if D[nst][v] is None:
            continue
        worst = None
        for k in range(nst):
            if D[k][v] is None:
                continue
            r = Fr(D[nst][v] - D[k][v], nst - k)
            worst = r if worst is None or r < worst else worst
        best = worst if best is None or worst > best else best
    return best


res = {}
for n in (1, 2, 3):
    states, edges = build(n)
    bound = Fr(n, 8 * n + 1)
    P = (8 * n + 1) * 8
    vi = value_iter(len(states), edges, 3 * P, P)
    row = dict(状态数=len(states), 边数=len(edges), 值迭代每步=str(vi), 上界每步=str(bound),
               值迭代每tick=str(8 * vi), 上界每tick=str(8 * bound))
    if n <= 2:
        kp = karp(len(states), edges)
        row['Karp每步'] = str(kp)
        assert kp == bound, (n, kp, bound)
    assert vi == bound, (n, vi, bound)
    res[n] = row
    print(n, row, flush=True)
(OUT / 'sec7.json').write_text(json.dumps(res, ensure_ascii=False, indent=1) + '\n')
