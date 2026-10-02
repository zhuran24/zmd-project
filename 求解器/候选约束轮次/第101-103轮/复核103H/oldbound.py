#!/usr/bin/env python3
"""复核103H：一次清空离线是否足以打破旧版（92C/92D/95T）跨离线起值支 Φ>=min(Φ(s)-1/2, L+150)。
用本席 plant.py 的两套编码；对找到的见证，同一日程改成保留读法再跑一遍作对照。
另做贪心对手（每步前都离线清空、CB 先接通）的压力测试，核累计界 min(Φ(s)-(m+1)/2, H-m/2) 与 Φ>=1/2。"""
import json, random, sys
from fractions import Fraction as Fr
import plant

def replay(cfg, st, offl, acc, horizon, dual=True):
    A = plant.EngA(cfg, st)
    B = plant.EngB(cfg, {'belts': A.belts, 'm': A.m, 'connC': A.connC, 'lastC': A.lastC,
                         'connK': A.connK, 'lastK': A.lastK}, 0) if dual else None
    traj = []; ok = True
    for t in range(1, horizon):
        if t in offl:
            A.offline(*offl[t])
            if B: B.offline(*offl[t])
        if B: B.tick_clock()
        s = A.step(t, acc[t])
        if B:
            B.step(acc[t])
            if A.snapshot(t) != B.snapshot(): ok = False
        traj.append((t, s.get('C'), A.phi()))
    return traj, ok

def main():
    rng = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else 5)
    res = {}
    found = None; ncase = 0; nbreak = 0
    for it in range(20000):
        cfg = dict(k=2, n=0, L=[rng.randrange(1, 4), rng.randrange(1, 4), rng.randrange(1, 3), 1], Bmode='adv')
        st = plant.gen_state(rng, cfg, rng.choice(['low', 'high']))
        x = rng.randrange(2, 30)
        offl = {x: ('clear', [1, 0], [])}
        acc = [{'sinkB': True} for _ in range(80)]
        A = plant.EngA(cfg, st); phis = A.phi(); L = cfg['L'][0] + cfg['L'][1]
        ncase += 1
        brk = None
        for t in range(1, 70):
            if t in offl: A.offline(*offl[t])
            A.step(t, acc[t])
            if A.phi() < min(phis - Fr(1, 2), L + 150):
                brk = t; break
        if brk:
            nbreak += 1
            if found is None or L < found['L']:
                found = dict(cfg=cfg, st=st, x=x, L=L, t=brk, phis=phis)
    res['single_clear_search'] = dict(cases=ncase, breaks=nbreak)
    if found:
        cfg, st, x = found['cfg'], found['st'], found['x']
        acc = [{'sinkB': True} for _ in range(80)]
        tr_c, ok_c = replay(cfg, st, {x: ('clear', [1, 0], [])}, acc, found['t'] + 1)
        tr_k, ok_k = replay(cfg, st, {x: ('keep', [1, 0], [])}, acc, found['t'] + 1)
        L = found['L']; phis = found['phis']
        res['witness'] = dict(cfg=cfg, start=st, offline_before_step=x, L=L, phi_s=str(phis),
                              old_bound=str(min(phis - Fr(1, 2), L + 150)),
                              clear_sends=[(t, c) for t, c, _ in tr_c if c is not None],
                              clear_phi_end=str(tr_c[-1][2]), clear_dual_ok=ok_c,
                              keep_sends=[(t, c) for t, c, _ in tr_k if c is not None],
                              keep_phi_min=str(min(p for _, _, p in tr_k)), keep_dual_ok=ok_k,
                              cum_bound_m1=str(min(phis - 1, L + 150 - Fr(1, 2))))
    # 贪心对手压力：每步前离线清空、CB 先接通
    viol_cum = 0; viol_half = 0; nst = 0; min_drop_per_off = None
    for it in range(1500):
        cfg = dict(k=2, n=0, L=[rng.randrange(1, 6), rng.randrange(1, 6), rng.randrange(1, 4), 1], Bmode='adv')
        st = plant.gen_state(rng, cfg, rng.choice(['low', 'high']))
        A = plant.EngA(cfg, st); phis = A.phi(); L = cfg['L'][0] + cfg['L'][1]
        m = 0
        for t in range(1, 400):
            if rng.random() < 0.8:
                A.offline('clear', [1, 0], []); m += 1
            A.step(t, {'sinkB': rng.random() < 0.9})
            ph = A.phi()
            if ph < min(phis - Fr(m + 1, 2), L + 150 - Fr(m, 2)): viol_cum += 1
            if phis >= 1 and ph < Fr(1, 2): viol_half += 1
        nst += 1
    res['greedy_clear_stress'] = dict(cases=nst, viol_cum=viol_cum, viol_half=viol_half)
    json.dump(res, open(sys.argv[1], 'w'), ensure_ascii=False, indent=1, default=str)
    print(json.dumps({k: v for k, v in res.items() if k != 'witness'}, ensure_ascii=False, default=str))
    if 'witness' in res:
        w = res['witness']; print({k: w[k] for k in w if k != 'start'}); print(w['start'])

if __name__ == '__main__':
    main()
