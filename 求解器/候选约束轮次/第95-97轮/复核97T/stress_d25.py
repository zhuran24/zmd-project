#!/usr/bin/env python3
"""150 下界的贴边压力测试：高存量起态（Φ(s) 接近上限）、B 满速取料、离线与下游停收随机，
统计 Φ−(L1+L2+150) 的最小值（以半件为单位）。"""
import json, random, sys
from seedunit import Unit, SEED, PLANT, POWDER
def one(rng, steps):
    k = rng.choice([2, 3])
    u = Unit(rng, k=k, n_out=k)
    u.fill_path('CA', SEED, 1.0); u.fill_path('AC', PLANT, 1.0)
    u.fill_path('CB', SEED, rng.random()); u.fill_path('BK', PLANT, rng.random())
    for m, i, o in ((u.C, PLANT, SEED), (u.A, SEED, PLANT)):
        u.rand_machine(m, i, o, full=True)
        if rng.random() < 0.5:
            m.out_n = rng.randint(40, 50)
    u.C.out_n = rng.choice([50, 49, 48, rng.randint(30, 50)])
    u.rand_machine(u.B, SEED, PLANT); u.rand_machine(u.K, PLANT, POWDER)
    u.B.slots[0] = [None, 0] if rng.random() < 0.5 else u.B.slots[0]
    w = u.w
    phi_s = u.phi2(); floor = 2 * (u.L1 + u.L2 + 150)
    bound = min(phi_s - 1, floor)
    mn = 10**9; mnfloor = 10**9
    p_off = rng.choice([0.0, 0.005, 0.05]); p_tog = rng.choice([0.0, 0.002, 0.02])
    for t in range(steps):
        if rng.random() < p_off: w.offline_build()
        for sk in u.sinks:
            if rng.random() < p_tog: sk.open = not sk.open
        if rng.random() < p_tog: u.K.powered = not u.K.powered
        w.step()
        ph = u.phi2()
        mn = min(mn, ph - bound); mnfloor = min(mnfloor, ph - floor)
        if ph < bound:
            return dict(ok=False, t=w.t, ph=ph, bound=bound, segs=u.segs)
    return dict(ok=True, slack2=mn, floorslack2=mnfloor, phis_minus_floor2=phi_s - floor)
N, steps, seed = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
rng = random.Random(seed)
res = [one(random.Random(rng.getrandbits(64)), steps) for _ in range(N)]
bad = [r for r in res if not r['ok']]
good = [r for r in res if r['ok']]
hist = {}
for r in good:
    hist[r['floorslack2']] = hist.get(r['floorslack2'], 0) + 1
print(json.dumps(dict(N=N, steps=steps, fail=len(bad), first_fails=bad[:2],
      min_floorslack2=min(r['floorslack2'] for r in good),
      floorslack2_hist=dict(sorted(hist.items())[:10]),
      runs_where_floor_binds=sum(1 for r in good if r['phis_minus_floor2'] > 1)), ensure_ascii=False))
