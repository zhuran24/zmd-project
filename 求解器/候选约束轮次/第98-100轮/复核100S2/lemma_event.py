#!/usr/bin/env python3
"""复核100S2：第5节补货引理的第二套编码——首格事件递推 vs 逐格模拟。

逐格：路长随机 1—12，源每步在空首格里随机选一条补（随机代替对手）。
递推：首格就绪 r_i(j)=max(x_j+δ_i+1, S_i(j−1)+8)，与路长无关；源每步按同一选择规则服务就绪者。
核对：两套给出的每次首格补货步号 S_i(j) 逐项相同；且 S_i(j) ≤ x_j+D+n；接收格消费前已满。
"""
import json, random

def cell_level(L, deltas, xs, choose):
    n = len(L)
    cells = [[-8] * l for l in L]
    deficit = [0] * n
    S = [[] for _ in range(n)]
    cons = {}
    for j, x in enumerate(xs):
        for i in range(n):
            cons.setdefault(x + deltas[i], []).append(i)
    T = xs[-1] + 40
    bad = []
    for t in range(T):
        for c in cells:
            for k in range(len(c) - 2, -1, -1):
                if c[k] is not None and c[k + 1] is None and t - c[k] >= 8:
                    c[k + 1], c[k] = t, None
        for i in range(n):
            c = cells[i]
            if c[-1] is not None and t - c[-1] >= 8 and deficit[i] > 0:
                deficit[i] -= 1
                c[-1] = None
                for k in range(len(c) - 2, -1, -1):
                    if c[k] is not None and c[k + 1] is None and t - c[k] >= 8:
                        c[k + 1], c[k] = t, None
        empties = [i for i in range(n) if cells[i][0] is None]
        if empties:
            i = choose(t, empties)
            cells[i][0] = t
            S[i].append(t)
        for i in cons.get(t, []):
            if deficit[i] > 0:
                bad.append(('consume_before_refill', t, i))
            deficit[i] += 1
    return S, bad

def event_level(n, deltas, xs, choose):
    S = [[] for _ in range(n)]
    last = [-10**6] * n
    T = xs[-1] + 40
    pending = {}
    for j, x in enumerate(xs):
        for i in range(n):
            r = max(x + deltas[i] + 1, last[i] + 8) if j > 0 else x + deltas[i] + 1
            pending.setdefault(i, []).append(None)  # placeholder
    # 按步推进：就绪集合 = 已到就绪时刻且本轮未服务者
    ready_at = {}
    served = [0] * n
    rounds = len(xs)
    t = 0
    while t < T:
        cand = []
        for i in range(n):
            j = served[i]
            if j >= rounds:
                continue
            x = xs[j]
            r = x + deltas[i] + 1 if j == 0 else max(x + deltas[i] + 1, last[i] + 8)
            if r <= t:
                cand.append(i)
        if cand:
            i = choose(t, sorted(cand))
            S[i].append(t)
            last[i] = t
            served[i] += 1
        t += 1
    return S

def main():
    rng = random.Random(100)
    stats = dict(cases=0, rounds=0, same=0, bound_ok=0, bad=0)
    examples = []
    for case in range(3000):
        kind = rng.choice(['core6', 'sand3', 'two', 'one'])
        if kind == 'core6':
            deltas = [0] * 6
        elif kind == 'sand3':
            deltas = rng.choice([[2, 2, 0], [2, 0, 0], [2, 2, 2], [0, 2, 1]])
        elif kind == 'two':
            deltas = [0, 0]
        else:
            deltas = [0]
        n = len(deltas)
        D = max(deltas)
        L = [rng.randint(1, 12) for _ in range(n)]
        xs = [rng.randint(0, 5)]
        for _ in range(rng.randint(3, 40)):
            xs.append(xs[-1] + rng.choice([8, 8, 8, 9, 10, 13, 20, 47]))
        seed = rng.random()
        def mk():
            r2 = random.Random(seed)
            return lambda t, e: r2.choice(sorted(e))
        Sc, bad = cell_level(L, deltas, xs, mk())
        # 初始全满：第一次补货对应第一次消费；逐格模型里首格补货列即 S
        Se = event_level(n, deltas, xs, mk())
        stats['cases'] += 1
        stats['rounds'] += len(xs)
        if Sc == Se:
            stats['same'] += 1
        elif len(examples) < 3:
            examples.append(dict(L=L, deltas=deltas, xs=xs[:6], Sc=[s[:6] for s in Sc], Se=[s[:6] for s in Se]))
        ok = all(len(Sc[i]) == len(xs) and all(Sc[i][j] <= xs[j] + D + n for j in range(len(xs))) for i in range(n))
        stats['bound_ok'] += ok
        stats['bad'] += len(bad)
    out = dict(stats=stats, examples=examples)
    json.dump(out, open('lemma_event.json', 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False))

if __name__ == '__main__':
    main()
