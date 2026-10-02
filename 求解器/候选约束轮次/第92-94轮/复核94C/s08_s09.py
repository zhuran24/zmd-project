#!/usr/bin/env python3
"""S08 Φ 下界随机核对与 S09 最小存量长期批率（自写模拟器）。"""
import json, random, sys
from plant_unit import mk_unit, fill, phi, rand_cache, S, P, D


def s08_random(nrun, steps, seed, mode):
    rng = random.Random(seed)
    viol = []
    tight = 0
    minslack = 99
    for r in range(nrun):
        k = rng.choice([2, 3])
        L1, L2, LB, LK, Lp = (rng.randint(1, 4) for _ in range(5))
        names = ['C', 'A', 'B', 'K', 'CA', 'CB'] + [f'K{j}' for j in range(k)]
        ranks = {n: rng.randrange(1000) for n in names}
        rr = random.Random(rng.randrange(10**9))
        pf = rr.random()
        seqs = [[rr.random() < pf for _ in range(steps + 10)] for _ in range(k)]
        pats = [lambda t, s=s: s[t] for s in seqs]
        w, C, A, B, K, R, sinks = mk_unit(rng, L1, L2, LB, LK, k, Lp, ranks, pats)
        # 起态
        def amt(hi):
            if mode == 'near':
                return rng.randint(max(0, hi - 3), hi)
            return rng.randint(0, hi)
        C.inp = [[P, amt(50)]] if amt(50) else []
        A.inp = [[S, amt(50)]] if True else []
        if A.inp[0][1] == 0:
            A.inp = []
        B.inp = [[S, rng.randint(0, 50)]]
        if B.inp[0][1] == 0:
            B.inp = []
        K.inp = [[P, rng.randint(0, 50)]]
        if K.inp[0][1] == 0:
            K.inp = []
        co = amt(50); C.out = [S, co] if co else None
        ao = amt(50); A.out = [P, ao] if ao else None
        bo = rng.randint(0, 50); B.out = [P, bo] if bo else None
        C.cache = rand_cache(rng, S, 2) if mode != 'near' or rng.random() < 0.3 else ('done', S, 2)
        A.cache = rand_cache(rng, P, 1) if mode != 'near' or rng.random() < 0.3 else ('done', P, 1)
        B.cache = rand_cache(rng, P, 1)
        K.cache = rand_cache(rng, D, k)
        for nm, kind in (('CA', S), ('CB', S), ('AC', P), ('BK', P)):
            for e in R[nm]:
                pfull = 0.97 if (mode == 'near' and nm in ('CA', 'AC')) else rng.random()
                e.cells = [([kind, -rng.randint(0, 20)] if rng.random() < pfull else None)
                           for _ in e.cells]
        # B、K 随机停开（S08 不要求它们运行）
        tog = [rng.random() < 0.3 for _ in range(steps + 5)]
        tog2 = [rng.random() < 0.3 for _ in range(steps + 5)]
        w.step()  # 第 0 步：C、A 开着；s 取其步末
        ph_s = phi(C, A, R)
        bound = min(ph_s - 0.5, L1 + L2 + 176)
        for t in range(1, steps):
            if mode != 'near':
                if tog[t]:
                    B.on = not B.on
                if tog2[t]:
                    K.on = not K.on
            w.step()
            v = phi(C, A, R)
            minslack = min(minslack, v - bound)
            if v < bound - 1e-9:
                viol.append(dict(r=r, t=t, phi=v, phi_s=ph_s, bound=bound))
                break
            if abs(v - (L1 + L2 + 176)) < 1e-9 and bound == L1 + L2 + 176:
                tight += 1
    return dict(mode=mode, runs=nrun, steps=steps, nviol=len(viol), viol=viol[:5],
                min_slack=minslack, hits_176=tight)


def s09_min_phi(nrun, steps, seed):
    """Φ(s)=L1+L2+5/2 的最小存量起态，K 下游总能收（K 的批从不因取货格放不下而等待）。
    看后段四机批率是否都是每 8 步一批、步末缓存是否都非空。"""
    rng = random.Random(seed)
    res = []
    for r in range(nrun):
        k = rng.choice([2, 3])
        L1, L2, LB, LK, Lp = (rng.randint(1, 4) for _ in range(5))
        names = ['C', 'A', 'B', 'K', 'CA', 'CB'] + [f'K{j}' for j in range(k)]
        ranks = {n: rng.randrange(1000) for n in names}
        pats = [lambda t: True for _ in range(k)]
        w, C, A, B, K, R, sinks = mk_unit(rng, L1, L2, LB, LK, k, Lp, ranks, pats)
        C.inp = []; A.inp = []
        C.out = [S, 1]; A.out = None
        C.cache = ('run', rng.randint(1, 8), S, 2)
        A.cache = ('run', rng.randint(1, 8), P, 1)
        fill(R['CA'], S, -rng.randint(0, 8)); fill(R['AC'], P, -rng.randint(0, 8))
        # B 侧随意
        B.inp = [[S, rng.randint(1, 50)]]
        B.out = None
        B.cache = rand_cache(rng, P, 1)
        K.inp = [[P, rng.randint(1, 50)]]
        K.out = None
        K.cache = rand_cache(rng, D, k)
        for nm, kind in (('CB', S), ('BK', P)):
            for e in R[nm]:
                e.cells = [([kind, -rng.randint(0, 9)] if rng.random() < 0.5 else None)
                           for _ in e.cells]
        ph0 = phi(C, A, R)
        empty_ends = {m.name: 0 for m in (C, A, B, K)}
        kwait = 0
        for t in range(steps):
            w.step()
            if t >= steps - 4000:
                for m in (C, A, B, K):
                    if m.cache is None:
                        empty_ends[m.name] += 1
                if K.cache is not None and K.cache[0] == 'done':
                    kwait += 1
        starts = {m.name: len([x for x in m.starts if x >= steps - 4000]) for m in (C, A, B, K)}
        res.append(dict(r=r, k=k, L=(L1, L2, LB, LK, Lp), phi0=ph0,
                        starts_last4000=starts, empty_step_ends_last4000=empty_ends,
                        K_wait_steps=kwait))
    full = sum(1 for x in res if all(v == 500 for v in x['starts_last4000'].values()))
    return dict(runs=nrun, steps=steps, full_rate_runs=full,
                not_full=[x for x in res if not all(v == 500 for v in x['starts_last4000'].values())][:8],
                any_empty_cache=[x for x in res if any(x['empty_step_ends_last4000'].values())][:5])


if __name__ == '__main__':
    out = {}
    out['s08_near'] = s08_random(4000, 300, 11, 'near')
    print(out['s08_near'], flush=True)
    out['s08_wide'] = s08_random(4000, 400, 12, 'wide')
    print(out['s08_wide'], flush=True)
    out['s09_min'] = s09_min_phi(300, 12000, 13)
    print(json.dumps(out['s09_min'], default=str)[:2500], flush=True)
    json.dump(out, open('s08_s09.json', 'w'), ensure_ascii=False, indent=1, default=str)
