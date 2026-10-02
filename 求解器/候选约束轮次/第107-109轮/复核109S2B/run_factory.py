#!/usr/bin/env python3
"""整厂复核：桥接器版与同长纯带版逐步对照 + 恢复后循环态交付率。

用法: python3 -B run_factory.py SEED MAXLEN keep|clear|mix [core_per_side]
扰动期：随机全厂重建（离线）、两种成品各自随机停收；之后不再扰动、两种成品一直收，
找到状态重复后量一个周期的交付与各矿口出量。
"""
import json
import sys
import time
from fractions import Fraction

from engine_x import Factory, FINISHED, DWELL


def main():
    seed = int(sys.argv[1]); maxlen = int(sys.argv[2]); hist = sys.argv[3]
    cps = len(sys.argv) > 4 and sys.argv[4] == 'core_per_side'
    pb = float(sys.argv[5]) if len(sys.argv) > 5 else 0.6
    lmode = sys.argv[6] if len(sys.argv) > 6 else 'axis'
    use_budget = len(sys.argv) > 7 and sys.argv[7] == 'budget'
    t0 = time.time()
    keep = hist != 'clear'
    fb = Factory(seed, 'bridge', maxlen, pbridge=pb, keep=keep, core_per_side=cps, layer_mode=lmode)
    fr = Factory(seed + 7777, 'belt', maxlen, keep=keep, core_per_side=cps, layout=fb.layout)
    def share():
        sh = {k: v for k, v in fb.conn.items() if k[0] in ('h', 't')}
        fr.rebuild(shared=sh)
    share()
    rng = fb.rng
    nb_cells = sum(1 for p in range(len(fb.P)) for i in range(fb.lengths[p]) if fb.kinds[p][i] == 'bridge')
    phys_br = {fb.phys[(p, i)] for p in range(len(fb.P)) for i in range(fb.lengths[p]) if fb.kinds[p][i] == 'bridge'}
    crossed = nb_cells - len(phys_br)
    # 最长同轴相邻桥串
    longest = 0
    for p in range(len(fb.P)):
        run = 0
        for i in range(fb.lengths[p]):
            run = run + 1 if fb.kinds[p][i] == 'bridge' else 0
            longest = max(longest, run)
    T1 = 3000
    rebuilds = 0
    stops = {f: 0 for f in FINISHED}
    diffs = 0
    first_diff = None
    stop_until = {f: -1 for f in FINISHED}
    for step in range(T1):
        if rng.random() < 0.08:
            if hist == 'mix':
                fb.keep = fr.keep = rng.random() < 0.5
            fb.rebuild(); share(); rebuilds += 1
        for f in FINISHED:
            if use_budget:
                # 仓库只余少量库位：停收期间每步随机只收 0 或 1 件
                if not fb.accept[f] and fb.t < stop_until[f]:
                    pass
                bud = rng.choice([0, 0, 0, 1]) if (fb.t < stop_until[f]) else None
                fb.budget[f] = fr.budget[f] = bud
            if fb.t >= stop_until[f] and not fb.accept[f]:
                fb.accept[f] = fr.accept[f] = True
            if fb.accept[f] and rng.random() < 0.002 and step < T1 - 600:
                dur = rng.randint(50, 900)
                stop_until[f] = fb.t + dur
                if not use_budget:
                    fb.accept[f] = fr.accept[f] = False
                stops[f] += 1
        fb.step(); fr.step()
        if fb.snapshot() != fr.snapshot():
            diffs += 1
            if first_diff is None:
                first_diff = fb.t
    for f in FINISHED:
        fb.accept[f] = fr.accept[f] = True
        fb.budget[f] = fr.budget[f] = None
    seen = {}
    period = None
    snaps = {}
    for k in range(20000):
        key = fb.state_key()
        if key in seen:
            period = (seen[key], fb.t)
            break
        seen[key] = fb.t
        snaps[fb.t] = (dict(fb.delivered), list(fb.oresent))
        fb.step(); fr.step()
        if fb.snapshot() != fr.snapshot():
            diffs += 1
            if first_diff is None:
                first_diff = fb.t
    res = {'seed': seed, 'maxlen': maxlen, 'hist': hist, 'core_per_side': cps, 'pbridge': pb,
           'layer_mode': lmode, 'budget_stops': use_budget,
           'paths': len(fb.P), 'elements': len(fb.elems), 'bridge_cells': nb_cells,
           'crossed_bridges': crossed, 'longest_adjacent_bridge_run': longest,
           'rebuilds': rebuilds, 'stops': stops, 'steps_compared': fb.t,
           'state_diffs_vs_belt': diffs, 'first_diff_step': first_diff,
           'anomalies': fb.anom, 'machines': len(fb.M)}
    if period:
        a, b = period
        P = b - a
        d0, o0 = snaps[a]
        res['period_steps'] = P
        res['cycle_start'] = a
        dl = {f: fb.delivered[f] - d0[f] for f in FINISHED}
        res['delivered_in_period'] = dl
        ticks = Fraction(P, DWELL)
        res['rate_per_tick'] = {f: str(Fraction(dl[f]) / ticks) for f in FINISHED}
        ore = [fb.oresent[p] - o0[p] for p in range(len(fb.P)) if fb.P[p][0] == 'CORE' or fb.P[p][0].startswith('PORT')]
        res['ore_paths'] = len(ore)
        res['ore_rate_set'] = sorted({str(Fraction(x) / ticks) for x in ore})
        watch = [p for p, (sr, d, it) in enumerate(fb.P) if sr == 'CORE' or
                 (sr.startswith('S') and len(fb.outpaths[sr]) > 1) or (sr.startswith('K') and len(fb.outpaths[sr]) > 1)]
        fb.rejects = {}
        for _ in range(P):
            fb.step()
        rej = {p: fb.rejects.get(p, 0) for p in watch}
        res['watched_multi_exit_paths'] = len(watch)
        res['watched_rejects_next_period'] = sum(rej.values())
        res['all_rejects_next_period'] = sum(fb.rejects.values())
        res['ok'] = (res['watched_rejects_next_period'] == 0 and res['rate_per_tick']['高容谷地电池'] == '3/5' and res['rate_per_tick']['精选荞愈胶囊'] == '11/20'
                     and res['ore_rate_set'] == ['1'] and diffs == 0
                     and all(v == 0 for k, v in fb.anom.items() if k != 'reverse_checks'))
    else:
        res['ok'] = False
    res['wall_s'] = round(time.time() - t0, 1)
    print(json.dumps(res, ensure_ascii=False))


if __name__ == '__main__':
    main()
