#!/usr/bin/env python3
"""依赖核对（不是快照规则下的反例）：若离线会清掉“上次成功”记录（临时规则第 4 条“全部单位重建一遍”的一种读法），
S08 的 Φ 下界还守不守得住。模型：在随机步之间把 C 的成功记录清空，且 CB 接通早于 CA。
快照只说离线改变接通先后，不清记录；本脚本只量化这一读法下的敏感性。"""
import json, random
from plant_unit import mk_unit, fill, phi, S, P, D


def run(nrun, steps, seed, reset_every):
    rng = random.Random(seed)
    worst = []
    for r in range(nrun):
        k = 3
        L1, L2 = rng.randint(1, 4), rng.randint(1, 4)
        ranks = {'C': 0, 'A': 1, 'B': 2, 'K': 3, 'CA': 1, 'CB': 0, 'K0': 0, 'K1': 1, 'K2': 2}
        pats = [lambda t: True] * k
        w, C, A, B, K, R, sinks = mk_unit(rng, L1, L2, 1, 1, k, 1, ranks, pats)
        # 饱和起态
        C.inp = [[P, 50]]; A.inp = [[S, 50]]; B.inp = [[S, 50]]; K.inp = [[P, 50]]
        C.out = [S, 50]; A.out = [P, 50]; B.out = None; K.out = None
        C.cache = ('done', S, 2); A.cache = ('done', P, 1)
        fill(R['CA'], S, -8); fill(R['AC'], P, -8)
        w.step()
        ps = phi(C, A, R)
        bound = min(ps - 0.5, L1 + L2 + 176)
        lo = ps
        nres = 0
        for t in range(1, steps):
            if t % reset_every == 0:
                C.last_succ = {}
                nres += 1
            w.step()
            lo = min(lo, phi(C, A, R))
        worst.append(dict(L1=L1, L2=L2, phi_s=ps, bound=bound, min_phi=lo, resets=nres,
                          below_bound=lo < bound, final_C_in=C.in_count(P)))
    return worst


if __name__ == '__main__':
    out = {}
    for every in (5, 23, 200):
        res = run(20, 6000, 41 + every, every)
        out[f'reset_every_{every}'] = dict(runs=len(res), below=sum(x['below_bound'] for x in res),
                                           min_gap=min(x['min_phi'] - x['bound'] for x in res),
                                           sample=res[:3])
        print(every, out[f'reset_every_{every}']['below'], out[f'reset_every_{every}']['min_gap'],
              res[0])
    json.dump(out, open('s08_reset.json', 'w'), ensure_ascii=False, indent=1)
