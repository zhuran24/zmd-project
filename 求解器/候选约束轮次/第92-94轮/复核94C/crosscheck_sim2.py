#!/usr/bin/env python3
"""第二套编码：同一批采种单元起态分别在自写 stepsim 与项目 sim2（只读导入，不改）上逐步比较。
构型只含单种存货、产物与原料不同种、纯传送带，不触及 sim2 的两处已知错误。"""
import json, random, sys, importlib.util
from plant_unit import mk_unit, rand_cache, S, P, D, phi

SIM2 = '/home/zhuran24/zmd-research-fresh/求解器/规则修订/2026-09-30-迟滞/sim2/simulator.py'
spec = importlib.util.spec_from_file_location('sim2mod', SIM2)
s2 = importlib.util.module_from_spec(spec)
sys.modules['sim2mod'] = s2
sys.dont_write_bytecode = True
spec.loader.exec_module(s2)


def build_pair(seed):
    rng = random.Random(seed)
    k = rng.choice([2, 3])
    L1, L2, LB, LK, Lp = (rng.randint(1, 4) for _ in range(5))
    names = ['C', 'A', 'B', 'K', 'CA', 'CB'] + [f'K{j}' for j in range(k)]
    ranks = {n: rng.randrange(1000) for n in names}
    rr = random.Random(rng.randrange(10**9))
    pf = rr.random()
    seqs = [[rr.random() < pf for _ in range(2000)] for _ in range(k)]
    pats = [lambda t, s=s: s[t] for s in seqs]
    w, C, A, B, K, R, sinks = mk_unit(random.Random(seed + 1), L1, L2, LB, LK, k, Lp, ranks, pats)
    kv = {'C': 2, 'A': 1, 'B': 1, 'K': k}
    init = {}
    for m, kind, prod in ((C, P, S), (A, S, P), (B, S, P), (K, P, D)):
        n_in = rng.randint(0, 50)
        m.inp = [[kind, n_in]] if n_in else []
        n_out = rng.randint(0, 50)
        m.out = [prod, n_out] if n_out else None
        m.cache = rand_cache(rng, prod, kv[m.name])
    for e in w.elements:
        kind = S if e.name.startswith('C') else (P if e.name[0] in 'AB' else D)
        e.cells = [([kind, -rng.randint(0, 12)] if rng.random() < 0.6 else None) for _ in e.cells]
    # ---- sim2 镜像
    rec = {}
    mk = {}
    for m, mat, prod in ((C, P, S), (A, S, P), (B, S, P), (K, P, D)):
        r = s2.Recipe(m.name, ((mat, 1),), prod, kv[m.name], 8)
        x = s2.Machine(m.name, recipes=[r])
        x.slots[0] = [s2.Item(mat, -100) for _ in range(m.in_count(mat))]
        x.output = [s2.Item(prod, -100) for _ in range(m.out[1] if m.out else 0)]
        if m.cache is None:
            pass
        elif m.cache[0] == 'run':
            x.running, x.remaining = r, m.cache[1]
        else:
            x.cache = [s2.Item(prod, -100) for _ in range(m.cache[2])]
        mk[m.name] = x
    belts = {}
    for e in w.elements:
        b = s2.Belt(e.name, len(e.cells))
        b.cells = [None if c is None else s2.Item(c[0], c[1]) for c in e.cells]
        belts[e.name] = b
    sk2 = []
    # 接线：用与 stepsim 相同的接通 rank
    def conn(src_u, dst_u, rank):
        src_u.connect(dst_u, connected=rank)
    for m in (C, A, B, K):
        for e in m.out_routes:
            conn(mk[m.name], belts[e.name], m.out_rank[e])
    for e in w.elements:
        d = e.dst
        if hasattr(d, 'recipes'):
            conn(belts[e.name], mk[d.name], 0)
        else:
            j = int(d.name[1:])
            z = s2.Sink(d.name, every=0)
            z.can_accept = (lambda item, ww, s=seqs[j]: s[ww.t])
            sk2.append(z)
            conn(belts[e.name], z, 0)
    nodes = list(mk.values()) + list(belts.values()) + sk2
    order = [e.name for e in w.el_order] + [u.name for u in w.nt_order]
    lev = s2.layers_for(nodes)
    sched = dict(choices={}, layers={n: lev[n] for n in lev}, nontransport_order=[u.name for u in w.nt_order],
                 order=order)
    W2 = s2.World(nodes, schedule=sched)
    return w, (C, A, B, K), W2, mk, belts


def snap1(w, ms):
    out = []
    for m in ms:
        kind = list(m.recipes[0][0])[0]
        out.append((m.name, m.in_count(kind), m.out[1] if m.out else 0,
                    None if m.cache is None else (m.cache[0], m.cache[1] if m.cache[0] == 'run' else 0)))
    for e in sorted(w.elements, key=lambda e: e.name):
        out.append((e.name, tuple(None if c is None else (c[0], c[1]) for c in e.cells)))
    return out


def snap2(mk, belts):
    out = []
    for n in ('C', 'A', 'B', 'K'):
        x = mk[n]
        cache = None
        if x.running is not None:
            cache = ('run', x.remaining)
        elif x.cache:
            cache = ('done', 0)
        out.append((n, len(x.slots[0]), len(x.output), cache))
    for n in sorted(belts):
        b = belts[n]
        out.append((n, tuple(None if c is None else (c.kind, c.entered) for c in b.cells)))
    return out


if __name__ == '__main__':
    nrun, steps = int(sys.argv[1]), int(sys.argv[2])
    mism = []
    total = 0
    for seed in range(nrun):
        w, ms, W2, mk, belts = build_pair(seed)
        for t in range(steps):
            w.step()
            W2.step()
            a, b = snap1(w, ms), snap2(mk, belts)
            total += 1
            if a != b:
                mism.append(dict(seed=seed, t=t, mine=str(a)[:600], sim2=str(b)[:600]))
                break
    res = dict(runs=nrun, steps=steps, compared_step_states=total, mismatches=len(mism), first=mism[:2])
    json.dump(res, open('crosscheck_sim2.json', 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False)[:2000])
