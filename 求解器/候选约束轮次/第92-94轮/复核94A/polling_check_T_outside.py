#!/usr/bin/env python3
"""复核94A：运输单位（按接通先后循环、从上次成功的下一条开始）在 k 条考察通道之外
还有同级「外通道」时，k 条内成功序列仍按接通先后循环。外通道空不空由对手随机定。"""
import random, json
from polling_check import group_words

def run(k, m, before, words, delays, ptr, out_free, pos):
    # 全部 k+m 条按接通先后排成环；考察通道编号 0..k-1 依次插在环里，外通道插在 pos 指定位置
    ring = list(range(k))
    for j, p in enumerate(pos):
        ring.insert(p, ('o', j))
    n = len(ring)
    busy = {}
    pending = sorted(8 * i + delays[i] for i, g in enumerate(words) for _ in range(g))
    seq = []
    for t in range(8 * len(words) + 30):
        av = [p for p in pending if p <= t]
        if not av:
            continue
        for i in range(n):
            c = ring[(ptr + i) % n]
            if isinstance(c, tuple):
                if t in out_free[c[1]]:
                    ptr = (ptr + i + 1) % n; pending.remove(av[0]); break
                continue
            r = busy.get(c)
            if r is None or t >= r + (8 if before[c] else 9):
                busy[c] = t; seq.append(c); ptr = (ptr + i + 1) % n; pending.remove(av[0]); break
    return seq

rng = random.Random(9402)
bad = 0; N = 0
for _ in range(60000):
    k = rng.randint(2, 4); m = rng.randint(1, 6 - k) if k < 6 else 0
    if m == 0: continue
    words = rng.choice(group_words(k, 6))
    delays = [rng.randint(0, 1) for _ in words]
    before = [rng.random() < 0.5 for _ in range(k)]
    pos = sorted(rng.randint(0, k + j) for j in range(m))
    out_free = [{t for t in range(100) if rng.random() < 0.4} for _ in range(m)]
    ptr = rng.randrange(k + m)
    seq = run(k, m, before, words, delays, ptr, out_free, pos)
    # 期望：考察通道之间按 0..k-1 的环序，从第一个成功者起
    if seq:
        s0 = seq[0]
        ok = all(seq[i] == (s0 + i) % k for i in range(len(seq)))
        bad += (not ok)
    N += 1
res = dict(cases=N, bad=bad)
json.dump(res, open('polling_check_T_outside.json', 'w'))
print(res)
