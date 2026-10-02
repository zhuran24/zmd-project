#!/usr/bin/env python3
"""S07 旧条文无限期部分的线索（n=2 交叉接法）：C1→A1→C1 自环、C1→A2→C2、C2→B1→K1、C2→B2→K2。
满起态长跑，看有没有机器步末缓存空、存货见底。"""
import json, random
from stepsim import World, Machine, Sink

S, P, D = 'seed', 'plant', 'powder'


def build(rng, k, ranks, pats):
    w = World()
    C1 = Machine('C1', [({P: 1}, S, 2, 8)], 1, rank=ranks.pop())
    C2 = Machine('C2', [({P: 1}, S, 2, 8)], 1, rank=ranks.pop())
    A1 = Machine('A1', [({S: 1}, P, 1, 8)], 1, rank=ranks.pop())
    A2 = Machine('A2', [({S: 1}, P, 1, 8)], 1, rank=ranks.pop())
    B1 = Machine('B1', [({S: 1}, P, 1, 8)], 1, rank=ranks.pop())
    B2 = Machine('B2', [({S: 1}, P, 1, 8)], 1, rank=ranks.pop())
    K1 = Machine('K1', [({P: 1}, D, k, 8)], 1, rank=ranks.pop())
    K2 = Machine('K2', [({P: 1}, D, k, 8)], 1, rank=ranks.pop())
    ms = [C1, C2, A1, A2, B1, B2, K1, K2]
    w.nts = ms
    R = []
    for a, b, kind in ((C1, A1, S), (C1, A2, S), (A1, C1, P), (A2, C2, P), (C2, B1, S), (C2, B2, S),
                       (B1, K1, P), (B2, K2, P)):
        R.append((w.chain(a, b, [rng.randint(1, 5)], ranks=[rng.randrange(1000)],
                          out_rank=rng.randrange(1000), name=f'{a.name}{b.name}'), kind))
    j = 0
    for Kx in (K1, K2):
        for i in range(k):
            w.chain(Kx, Sink(f'Z{j}', pats[j]), [rng.randint(1, 3)], ranks=[rng.randrange(1000)],
                    out_rank=rng.randrange(1000), name=f'{Kx.name}Z{i}')
            j += 1
    w.finalize()
    kv = {'C': 2, 'A': 1, 'B': 1, 'K': k}
    for m in ms:
        mat = list(m.recipes[0][0])[0]
        prod = m.recipes[0][1]
        q = kv[m.name[0]]
        m.inp = [[mat, 50]]
        m.out = [prod, rng.randint(50 - q, 50)]
        rc = rng.randrange(3)
        m.cache = None if rc == 0 else (('run', rng.randint(1, 8), prod, q) if rc == 1 else ('done', prod, q))
    for els, kind in R:
        for e in els:
            e.cells = [[kind, -rng.randint(8, 20)] for _ in e.cells]
    for e in w.elements:
        if 'Z' in e.name:
            e.cells = [[D, -rng.randint(8, 20)] for _ in e.cells]
    return w, ms


def run(nrun, steps, seed, mode):
    rng = random.Random(seed)
    out = []
    for r in range(nrun):
        k = rng.choice([2, 3])
        ranks = [rng.randrange(1000) for _ in range(8)]
        if mode == 'free':
            pats = [lambda t: True] * (2 * k)
        else:
            pats = []
            for j in range(2 * k):
                per = rng.randint(8, 11)
                pats.append(lambda t, per=per: t % per == 0)
        w, ms = build(rng, k, ranks, pats)
        first_empty = {}
        mins = {m.name: 50 for m in ms}
        for t in range(steps):
            w.step()
            for m in ms:
                mat = list(m.recipes[0][0])[0]
                mins[m.name] = min(mins[m.name], m.in_count(mat))
                if m.cache is None and m.name not in first_empty:
                    first_empty[m.name] = t
        starts = {m.name: len([x for x in m.starts if x >= steps - 8000]) for m in ms}
        out.append(dict(r=r, k=k, first_cache_empty=first_empty, min_input=mins, starts_last8000=starts))
    return dict(runs=nrun, steps=steps, runs_with_empty=sum(1 for x in out if x['first_cache_empty']),
                min_input=min(min(x['min_input'].values()) for x in out), detail=out)


if __name__ == '__main__':
    res = dict(free=run(30, 30000, 91, 'free'), periodic=run(30, 30000, 92, 'periodic'))
    json.dump(res, open('s07_n2.json', 'w'), ensure_ascii=False, indent=1)
    for kx in res:
        print(kx, res[kx]['runs_with_empty'], res[kx]['min_input'], res[kx]['detail'][0]['starts_last8000'])
