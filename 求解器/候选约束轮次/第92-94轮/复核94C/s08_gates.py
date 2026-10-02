#!/usr/bin/env python3
"""线索核对：S08 进路里夹不设上限的物品准入口（单格元件）时，Φ 下界是否仍守住（自写模拟器）。"""
import json, random
from stepsim import World, Machine, Sink
from plant_unit import phi, rand_cache, S, P, D


def segs(rng, n_cells):
    out = []
    left = n_cells
    while left > 0:
        if rng.random() < 0.4:
            out.append(1)
            left -= 1
        else:
            L = rng.randint(1, left)
            out.append(L)
            left -= L
    return out


def run(nrun, steps, seed):
    rng = random.Random(seed)
    viol, hits, minslack = [], 0, 99
    for r in range(nrun):
        k = rng.choice([2, 3])
        L1, L2, LB, LK = (rng.randint(1, 6) for _ in range(4))
        w = World()
        C = Machine('C', [({P: 1}, S, 2, 8)], 1, rank=rng.randrange(1000))
        A = Machine('A', [({S: 1}, P, 1, 8)], 1, rank=rng.randrange(1000))
        B = Machine('B', [({S: 1}, P, 1, 8)], 1, rank=rng.randrange(1000))
        K = Machine('K', [({P: 1}, D, k, 8)], 1, rank=rng.randrange(1000))
        w.nts = [C, A, B, K]
        R = {}
        for nm, a, b, L in (('CA', C, A, L1), ('CB', C, B, LB), ('AC', A, C, L2), ('BK', B, K, LK)):
            sg = segs(rng, L)
            R[nm] = w.chain(a, b, sg, ranks=[rng.randrange(1000) for _ in sg],
                            out_rank=rng.randrange(1000), name=nm)
        rr = random.Random(rng.randrange(10**9))
        pf = rr.random()
        for j in range(k):
            seq = [rr.random() < pf for _ in range(steps + 5)]
            w.chain(K, Sink(f'Z{j}', lambda t, s=seq: s[t]), [rng.randint(1, 3)],
                    ranks=[rng.randrange(1000)], out_rank=rng.randrange(1000), name=f'KZ{j}')
        w.finalize()
        C.inp = [[P, rng.randint(47, 50)]]
        A.inp = [[S, rng.randint(47, 50)]]
        B.inp = [[S, rng.randint(0, 50)]] if rng.random() < 0.8 else []
        K.inp = [[P, rng.randint(1, 50)]]
        C.out = [S, rng.randint(46, 50)]
        A.out = [P, rng.randint(47, 50)]
        C.cache = ('done', S, 2) if rng.random() < 0.7 else rand_cache(rng, S, 2)
        A.cache = ('done', P, 1) if rng.random() < 0.7 else rand_cache(rng, P, 1)
        B.cache = rand_cache(rng, P, 1)
        K.cache = rand_cache(rng, D, k)
        for nm, kind in (('CA', S), ('CB', S), ('AC', P), ('BK', P)):
            for e in R[nm]:
                pfull = 0.97 if nm in ('CA', 'AC') else rng.random()
                e.cells = [([kind, -rng.randint(0, 20)] if rng.random() < pfull else None) for _ in e.cells]
        w.step()
        ps = phi(C, A, R)
        bound = min(ps - 0.5, L1 + L2 + 176)
        for t in range(1, steps):
            w.step()
            v = phi(C, A, R)
            minslack = min(minslack, v - bound)
            if v < bound - 1e-9:
                viol.append(dict(r=r, t=t, v=v, ps=ps, bound=bound))
                break
            if bound == L1 + L2 + 176 and v == bound:
                hits += 1
    return dict(runs=nrun, steps=steps, nviol=len(viol), viol=viol[:5], min_slack=minslack, hits_176=hits)


if __name__ == '__main__':
    res = run(4000, 300, 31)
    json.dump(res, open('s08_gates.json', 'w'), ensure_ascii=False, indent=1)
    print(res)
