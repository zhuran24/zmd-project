#!/usr/bin/env python3
"""D 组两条修订候选的随机核对（含同轴相邻桥，按临时规则）。
用法: python check_d.py MODE N STEPS SEED
MODE: d25 | d26 | d25_reset_poll | d25_reset_prev | d26_cross_unit | d26_cross_axis | d26_kout_cross
"""
from __future__ import annotations
import json, random, sys
from seedunit import Unit, SEED, PLANT, POWDER, put, get
from engine import Item, Belt, Cell


def run_d25(rng, steps, reset_poll=False, reset_prev=False):
    k = rng.choice([2, 3])
    u = Unit(rng, k=k)
    high = rng.random() < 0.6
    pf = rng.choice([0.9, 1.0]) if high else rng.random()
    u.fill_path('CA', SEED, pf)
    u.fill_path('AC', PLANT, pf)
    u.fill_path('CB', SEED, rng.random())
    u.fill_path('BK', PLANT, rng.random())
    u.rand_machine(u.C, PLANT, SEED, full=high and rng.random() < 0.5)
    u.rand_machine(u.A, SEED, PLANT, full=high and rng.random() < 0.5)
    u.rand_machine(u.B, SEED, PLANT)
    u.rand_machine(u.K, PLANT, POWDER)
    for e in u.kout:
        pass
    w = u.w
    phi_s = u.phi2()
    bound = min(phi_s - 1, 2 * (u.L1 + u.L2 + 150))
    minslack = 10**9
    p_off = rng.choice([0.0, 0.002, 0.02])
    p_tog = rng.choice([0.0, 0.01, 0.05])
    for t in range(steps):
        # 玩家/外部在两步之间：离线、B/K 开关、下游停收
        if rng.random() < p_off:
            w.offline_build(reset_poll=reset_poll, reset_prev=reset_prev)
        if rng.random() < p_tog:
            u.B.powered = not u.B.powered
        if rng.random() < p_tog:
            u.K.powered = not u.K.powered
        for sk in u.sinks:
            if rng.random() < p_tog:
                sk.open = not sk.open
        w.step()
        ph = u.phi2()
        minslack = min(minslack, ph - bound)
        if ph < bound:
            return dict(ok=False, t=w.t, phi2=ph, bound2=bound, phi_s2=phi_s, L1=u.L1, L2=u.L2,
                        segs=u.segs, k=k)
    return dict(ok=True, minslack2=minslack, L1=u.L1, L2=u.L2, segs=u.segs,
                bridges=sum(1 for p in u.segs.values() for s in p if s[0] == 'br'),
                adj=sum(1 for p in u.segs.values() for s in p if s[0] == 'br' and s[1] >= 2))


def full_start(u, rng):
    for p, kind in (('CA', SEED), ('AC', PLANT), ('CB', SEED), ('BK', PLANT)):
        u.fill_path(p, kind, 1.0)
    for m, i, o in ((u.C, PLANT, SEED), (u.A, SEED, PLANT), (u.B, SEED, PLANT), (u.K, PLANT, POWDER)):
        u.rand_machine(m, i, o, full=True)
    for e in u.kout:
        put(e, 0, None) if isinstance(e, Cell) else None
        if isinstance(e, Belt):
            for j in range(len(e.cells)):
                e.cells[j] = Item(POWDER, rng.randint(-15, 0), None) if rng.random() < 0.5 else None
        else:
            e.item = Item(POWDER, rng.randint(-15, 0), 'K') if rng.random() < 0.5 else None


def run_d26(rng, steps, cross=False, unit_reading=False, kout_cross=False, reset_poll=False):
    k = rng.choice([2, 3])
    segs = None
    if cross:
        segs = {p: [('belt', rng.randint(1, 4))] for p in ('CA', 'AC', 'CB')}
        # BK：带 → 交叉桥 X → 带 → 桥 Y → 带 → K，使 X 轴的层数高于 Z 上游带
        segs['BK'] = [('belt', 1), ('br', 1), ('belt', 1), ('br', 1), ('belt', 1)]
    u = Unit(rng, k=k, segs=segs, cross=cross, bridge_unit_reading=unit_reading,
             kout_bridge_cross=kout_cross, n_out=(k if cross else None))
    full_start(u, rng)
    w = u.w
    if cross:
        # Z 路初始满且成熟、出口堵死：Z 上游带每步都有成熟货“往 X 送”
        u.cross_nodes[1].cells[0] = Item('z', -20, 'Zs')
        u.cross_nodes[2].item = Item('z', -20, 'Z.in#0')
        u.cross_nodes[3].cells[0] = Item('z', -20, u.cross_nodes[2].unit)
    assert u.phi2() == 2 * (u.L1 + u.L2 + 177), (u.phi2(), u.L1, u.L2)
    p_off = rng.choice([0.0, 0.002, 0.02])
    p_tog = 0.0 if cross else rng.choice([0.0, 0.01, 0.05, 0.2])
    n = len(u.kout)
    wait_since = [None] * n
    last_item = [u.first_cell(e) for e in u.kout]
    maxwait = -1
    cb_first = u.paths['CB'][0][0]
    bk_first = u.paths['BK'][0][0]
    for t in range(steps):
        if rng.random() < p_off:
            w.offline_build(reset_poll=reset_poll)
        for sk in u.sinks:
            if rng.random() < p_tog:
                sk.open = not sk.open
        w.step()
        T = w.t - 1
        errs = []
        for m in (u.A, u.B, u.C, u.K):
            if not m.cache_nonempty():
                errs.append(f'{m.name}缓存空')
        if u.B.inv(SEED) < 49: errs.append('B存货<49')
        if u.K.inv(PLANT) < 49: errs.append('K存货<49')
        if u.B.out_n < 49: errs.append('B取货<49')
        if u.K.out_n < 50 - k: errs.append('K取货<50-k')
        if u.first_cell(cb_first) is None: errs.append('CB首格步末空')
        if u.first_cell(bk_first) is None: errs.append('BK首格步末空')
        for i, e in enumerate(u.kout):
            it = u.first_cell(e)
            if it is None:
                if wait_since[i] is None:
                    wait_since[i] = T
            else:
                if it is not last_item[i]:
                    if wait_since[i] is not None:
                        wt = T - wait_since[i]
                        maxwait = max(maxwait, wt)
                        if wt > n - 1:
                            errs.append(f'K出口{i}等待{wt}>n-1')
                    wait_since[i] = None
            last_item[i] = it
        if errs:
            return dict(ok=False, t=T, errs=errs, segs=u.segs, k=k, n=n,
                        Kin=u.K.inv(PLANT), Kout=u.K.out_n, Bin=u.B.inv(SEED), Bout=u.B.out_n)
    return dict(ok=True, k=k, n=n, maxwait=maxwait, segs=u.segs,
                adj=sum(1 for p in u.segs.values() for s in p if s[0] == 'br' and s[1] >= 2),
                ooo=w.log_out_of_order)


def main():
    mode, N, steps, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    rng = random.Random(seed)
    fails, oks, info = [], 0, {}
    adj_cases = 0
    for i in range(N):
        r = random.Random(rng.getrandbits(64))
        if mode == 'd25':
            res = run_d25(r, steps)
        elif mode == 'd25_reset_poll':
            res = run_d25(r, steps, reset_poll=True)
        elif mode == 'd25_reset_prev':
            res = run_d25(r, steps, reset_prev=True)
        elif mode == 'd26':
            res = run_d26(r, steps)
        elif mode == 'd26_reset_poll':
            res = run_d26(r, steps, reset_poll=True)
        elif mode == 'd26_cross_unit':
            res = run_d26(r, steps, cross=True, unit_reading=True)
        elif mode == 'd26_cross_axis':
            res = run_d26(r, steps, cross=True, unit_reading=False)
        elif mode == 'd26_kout_cross_unit':
            res = run_d26(r, steps, kout_cross=True, unit_reading=True)
        else:
            raise SystemExit('bad mode')
        if res.get('adj'):
            adj_cases += 1
        if res['ok']:
            oks += 1
        else:
            fails.append(res)
    out = dict(mode=mode, N=N, steps=steps, seed=seed, ok=oks, fail=len(fails),
               cases_with_adjacent_bridges=adj_cases, first_fails=fails[:3])
    print(json.dumps(out, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
