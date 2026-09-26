#!/usr/bin/env python3
"""反面对照：同一骨架，但调试期结束时植物单元的回路存量不够（Φ < S），看模拟能不能查出不达标。
用来说明 skeleton_sim.py 查得出问题，不是什么都判「达标」。"""
import json, random, sys
sys.path.insert(0, '.')
import skeleton_sim as ss


def trial(seed):
    rng = random.Random(seed)
    m = rng.choice([20, 50]); Lmax = rng.choice([2, 4])
    n = ss.build(rng, m, Lmax)
    n.ore_idx = {pid: j for j, pid in enumerate(n.ore_paths)}
    # 只给回路放很少的种子
    low = []
    for cell in n.cells:
        C, A, B, K, pCA, pAC = cell
        seedname = list(n.mach[A]['inp'].keys())[0]
        n.mach[A]['inp'][seedname] = rng.randint(1, 3)
        S = len(n.paths[pCA]['sl']) + len(n.paths[pAC]['sl']) + 2
        low.append(ss.phi_cell(n, cell) - S)
    order = [(0, i) for i in range(len(n.mach))] + [(1, i) for i in range(len(n.paths))]
    rng.shuffle(order)
    accept = {'电池': True, '胶囊': True}
    seen = {}; hist = []
    for t in range(20000):
        k = ss.key(n, t)
        if k in seen:
            cyc = hist[seen[k]:]; L = len(cyc)
            ore = [sum(h[0][j] for h in cyc) / L for j in range(len(n.ore_paths))]
            return dict(seed=seed, m=m, Lmax=Lmax, min_margin=min(low), cycle_len=L, ore_min=min(ore),
                        battery=sum(h[1]['电池'] for h in cyc) / L, capsule=sum(h[1]['胶囊'] for h in cyc) / L)
        seen[k] = len(hist)
        hist.append(ss.step(n, t, order, accept, set()))
    return dict(seed=seed, nocycle=True)


if __name__ == '__main__':
    out = [trial(70000 + i) for i in range(40)]
    fails = [o for o in out if not o.get('nocycle') and (o['ore_min'] < 1 or o['battery'] < 0.6 or o['capsule'] < 0.55)]
    json.dump(dict(trials=len(out), fails=len(fails), nocycle=sum(1 for o in out if o.get('nocycle')), all=out),
              sys.stdout, ensure_ascii=False, indent=1)
