#!/usr/bin/env python3
"""复核103H：从实际运行过的完整步末 s 起，一次清空离线打破旧版跨离线起值支（92C 第22条的 176 版同样适用）。
先从准备截面实际运行第 1 步，s 取第 1 步末；离线只在 s 之后。两套编码复放；同一日程改保留读法作对照。"""
import json, random, sys
from fractions import Fraction as Fr
import plant

def run(cfg, st, offl, steps, dual=True):
    A = plant.EngA(cfg, st)
    A.step(1, {'sinkB': True})
    B = plant.EngB(cfg, {'belts': A.belts, 'm': A.m, 'connC': A.connC, 'lastC': A.lastC, 'connK': [], 'lastK': []}, 1) if dual else None
    phis = A.phi(); tr = []; ok = True
    for t in range(2, steps):
        if t in offl:
            A.offline(*offl[t])
            if B: B.offline(*offl[t])
        if B: B.tick_clock()
        s = A.step(t, {'sinkB': True})
        if B:
            B.step({'sinkB': True})
            if A.snapshot(t) != B.snapshot(): ok = False
        tr.append((t, s.get('C'), A.phi()))
    return phis, tr, ok

FIXED_L = [int(v) for v in sys.argv[2].split(",")] if len(sys.argv) > 2 else None
rng = random.Random(77)
best = None; nb = 0; nc = 0
for it in range(30000):
    cfg = dict(k=2, n=0, L=FIXED_L or [rng.randrange(1, 4), rng.randrange(1, 4), rng.randrange(1, 3), 1], Bmode="adv")
    st = plant.gen_state(rng, cfg, rng.choice(['low', 'high']))
    x = rng.randrange(3, 30)
    offl = {x: ('clear', [1, 0], [])}
    phis, tr, _ = run(cfg, st, offl, 70, dual=False)
    L = cfg['L'][0] + cfg['L'][1]; nc += 1
    brk = [t for t, c, p in tr if p < min(phis - Fr(1, 2), L + 176)]
    if brk:
        nb += 1
        key = (L, brk[0])
        if best is None or key < best[0]:
            best = (key, cfg, st, x, brk[0])
res = dict(cases=nc, breaks=nb)
if best:
    _, cfg, st, x, tb = best
    phis, trc, okc = run(cfg, st, {x: ('clear', [1, 0], [])}, tb + 1)
    _, trk, okk = run(cfg, st, {x: ('keep', [1, 0], [])}, tb + 1)
    L = cfg['L'][0] + cfg['L'][1]
    res['witness'] = dict(cfg=cfg, prep_state=st, s='第 1 步末', phi_s=str(phis), offline_before_step=x,
                          old_bound=str(min(phis - Fr(1, 2), L + 176)),
                          clear_sends=[(t, c) for t, c, _ in trc if c is not None], clear_phi_end=str(trc[-1][2]), clear_dual_ok=okc,
                          keep_sends=[(t, c) for t, c, _ in trk if c is not None], keep_phi_min=str(min(p for _, _, p in trk)), keep_dual_ok=okk,
                          cum_bound_m1=str(min(phis - 1, L + 176 - Fr(1, 2))))
json.dump(res, open(sys.argv[1], 'w'), ensure_ascii=False, indent=1, default=str)
print(json.dumps(res, ensure_ascii=False, default=str))
