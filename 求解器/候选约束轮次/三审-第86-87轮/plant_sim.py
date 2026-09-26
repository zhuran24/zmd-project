#!/usr/bin/env python3
"""三审第 86—87 轮：采种单元回路存量下界的随机相位模拟（真实容量 50，本目录自写）。

整个单元都建出来：C、A、B、K 四台机器，进路 CA、AC、CB、BK 长 1—4，K 有 1—4 条取货通道各接一个运输物品格，
格后是下游（仓库或别的机器），下游随机长时间停收再恢复。B、K 随机断电再上电（进度保留）。
1 tick = D 个时间单位，D 每次随机取；各运输物品格里旧货的已停留时间、各缓存格的剩余加工时间随机，
所以四台机器与各格的事件落在不同相位上，停收恢复、断电上电又不断引入新相位。
每个时刻把能成功的移动、开批、整批进格按随机先后做到没有可动为止（随机先后即任意轮询、接通先后、判定次序）。

核：调试期结束那一刻判定全部完成后的 Φ0，此后每个事件时刻判定全部完成后 Φ ≥ min(Φ0−1/2, L1+L2+176)；
起态后满 1 tick、CA 首格是已满 1 tick 的旧货时 Φ ≥ L1+L2+176.5。
对照：把 Φ0 换成起态那一刻判定之前的值，看会不会违例（说明条文里「判定全部完成后」这半句是需要的）。
Φ 一律乘 2 存成整数。用法：python3 -B plant_sim.py 种子 次数
"""
import heapq
import json
import random
import sys

CAP = 50


def one_run(rng, horizon_ticks=2500):
    D = rng.choice([1, 2, 3, 4, 5, 6, 7, 8, 12, 60])
    L1, L2, L3, L4 = (rng.randint(1, 4) for _ in range(4))
    nk = rng.randint(1, 4)
    kbatch = rng.choice([2, 3])          # 荞花 2、砂叶 3
    T0 = 10 * D                          # 调试期结束时刻（留出负的已停留时间）
    H = T0 + horizon_ticks * D

    # 运输物品格：None 或进格时刻
    def rand_path(L):
        return [None if rng.random() < 0.4 else T0 - rng.randint(0, 2 * D) for _ in range(L)]
    CA, AC, CB, BK = rand_path(L1), rand_path(L2), rand_path(L3), rand_path(L4)
    KO = [None if rng.random() < 0.5 else T0 - rng.randint(0, 2 * D) for _ in range(nk)]

    mode = rng.random()
    def rc():
        if mode < 0.3:
            return rng.choice([0, CAP, CAP - 1, rng.randint(0, CAP)])
        return rng.randint(0, CAP)
    m = {
        'C': {'in': rc(), 'out': rc(), 'batch': 2},
        'A': {'in': rc(), 'out': rc(), 'batch': 1},
        'B': {'in': rc(), 'out': rc(), 'batch': 1},
        'K': {'in': rc(), 'out': rc(), 'batch': kbatch},
    }
    for u in m.values():
        if rng.random() < 0.5:
            u['cache'] = None            # 空
        else:
            u['cache'] = T0 + rng.randint(0, D)   # 完成时刻（≤T0 即已做好）
        u['on'] = True
        u['rem'] = None                  # 断电时保留的剩余加工时间
    if rng.random() < 0.15:
        # 回路几乎全满的起态（Φ0 在上界附近），检验 L1+L2+176 那一支
        for path in (CA, AC):
            for j in range(len(path)):
                path[j] = T0 - rng.randint(0, 2 * D)
        m['A']['in'] = m['A']['out'] = m['C']['in'] = CAP
        m['C']['out'] = rng.choice([CAP - 2, CAP - 1, CAP])
        m['A']['cache'] = T0 + rng.randint(0, D)
        m['C']['cache'] = T0 + rng.randint(0, D)
    sinks_open = [rng.random() < 0.5 for _ in range(nk)]

    heap = []
    def push(t):
        if t <= H:
            heapq.heappush(heap, t)

    # 下游停收/恢复、B/K 断电/上电的切换时刻
    toggles = []
    t = T0
    while t < H:
        t += rng.randint(1, rng.choice([5, 50, 400])) * D + rng.randint(0, D - 1)
        toggles.append((t, 'sink', rng.randrange(nk)))
    for name in ('B', 'K'):
        t = T0
        while t < H:
            t += rng.randint(1, rng.choice([20, 300])) * D + rng.randint(0, D - 1)
            toggles.append((t, 'pow', name))
    toggles.sort()
    for tt, _, _ in toggles:
        push(tt)
    tog_i = 0

    def phi2():
        n = sum(x is not None for x in CA) + m['A']['in'] + (m['A']['cache'] is not None) + m['A']['out']
        n += sum(x is not None for x in AC) + m['C']['in'] + (m['C']['cache'] is not None)
        return 2 * n + m['C']['out']

    def moves(t):
        mv = []
        C, A, B, K = m['C'], m['A'], m['B'], m['K']
        if C['out'] > 0 and CA[0] is None:
            mv.append(('take', CA))
        if C['out'] > 0 and CB[0] is None:
            mv.append(('take', CB))
        for path, dest in ((CA, A), (AC, C), (CB, B), (BK, K)):
            for j in range(len(path) - 1):
                if path[j] is not None and t - path[j] >= D and path[j + 1] is None:
                    mv.append(('adv', path, j))
            if path[-1] is not None and t - path[-1] >= D and dest['in'] < CAP:
                mv.append(('enter', path, dest))
        for name, u in m.items():
            if u['on'] and u['cache'] is None and u['in'] >= 1:
                mv.append(('start', name))
            if u['cache'] is not None and u['on'] and u['cache'] <= t and u['out'] + u['batch'] <= CAP:
                mv.append(('finish', name))
        for src, path in ((A, AC), (B, BK)):
            if src['out'] > 0 and path[0] is None:
                mv.append(('pick', src, path))
        for j in range(nk):
            if K['out'] > 0 and KO[j] is None:
                mv.append(('kpick', j))
            if KO[j] is not None and t - KO[j] >= D and sinks_open[j]:
                mv.append(('sink', j))
        return mv

    def apply(mvv, t):
        kind = mvv[0]
        if kind == 'take':
            m['C']['out'] -= 1; mvv[1][0] = t
        elif kind == 'adv':
            path, j = mvv[1], mvv[2]; path[j] = None; path[j + 1] = t; push(t + D)
        elif kind == 'enter':
            mvv[1][-1] = None; mvv[2]['in'] += 1
        elif kind == 'start':
            u = m[mvv[1]]; u['in'] -= 1; u['cache'] = t + D; push(t + D)
        elif kind == 'finish':
            u = m[mvv[1]]; u['out'] += u['batch']; u['cache'] = None
        elif kind == 'pick':
            mvv[1]['out'] -= 1; mvv[2][0] = t; push(t + D)
        elif kind == 'kpick':
            m['K']['out'] -= 1; KO[mvv[1]] = t; push(t + D)
        elif kind == 'sink':
            KO[mvv[1]] = None

    def closure(t):
        while True:
            mv = moves(t)
            if not mv:
                return
            apply(rng.choice(mv), t)

    # 起态各格已停留时间与加工完成时刻对应的事件
    for path in (CA, AC, CB, BK):
        for x in path:
            if x is not None:
                push(x + D)
    for x in KO:
        if x is not None:
            push(x + D)
    for u in m.values():
        if u['cache'] is not None:
            push(u['cache'])

    phi_pre = phi2()
    closure(T0)
    phi0 = phi2()
    bound2 = 2 * (L1 + L2) + 352
    stuck2 = bound2 + 1
    viol = 0
    viol_pre = 0
    stuck_seen = 0
    stuck_viol = 0
    min_margin = None
    events = 0
    last = T0
    while heap:
        t = heapq.heappop(heap)
        if t <= last:
            continue
        last = t
        while tog_i < len(toggles) and toggles[tog_i][0] == t:
            _, kind, arg = toggles[tog_i]
            tog_i += 1
            if kind == 'sink':
                sinks_open[arg] = not sinks_open[arg]
            else:
                u = m[arg]
                if u['on']:
                    u['on'] = False
                    if u['cache'] is not None:
                        u['rem'] = max(u['cache'] - t, 0)
                else:
                    u['on'] = True
                    if u['cache'] is not None:
                        u['cache'] = t + u['rem']; push(u['cache'])
        closure(t)
        events += 1
        p = phi2()
        need = min(phi0 - 1, bound2)
        if p < need:
            viol += 1
        if p < min(phi_pre - 1, bound2):
            viol_pre += 1
        mg = p - need
        min_margin = mg if min_margin is None else min(min_margin, mg)
        if t >= T0 + D and CA[0] is not None and t - CA[0] >= D:
            stuck_seen += 1
            if p < stuck2:
                stuck_viol += 1
    return {'D': D, 'L': [L1, L2, L3, L4], 'phi0_x2': phi0, 'phi_pre_x2': phi_pre, 'events': events,
            'viol': viol, 'viol_pre_reading': viol_pre, 'stuck_seen': stuck_seen, 'stuck_viol': stuck_viol,
            'min_margin_x2': min_margin}


def main():
    seed, runs = int(sys.argv[1]), int(sys.argv[2])
    rng = random.Random(seed)
    agg = {'runs': 0, 'events': 0, 'viol': 0, 'viol_runs': 0, 'viol_pre_runs': 0, 'stuck_seen': 0,
           'stuck_runs': 0, 'stuck_viol': 0, 'margin0_runs': 0, 'phi0_high_runs': 0, 'examples_pre': []}
    for r in range(runs):
        res = one_run(rng)
        agg['runs'] += 1
        agg['events'] += res['events']
        agg['viol'] += res['viol']
        agg['viol_runs'] += res['viol'] > 0
        agg['viol_pre_runs'] += res['viol_pre_reading'] > 0
        if res['viol_pre_reading'] and len(agg['examples_pre']) < 3:
            agg['examples_pre'].append(res)
        agg['stuck_seen'] += res['stuck_seen']
        agg['stuck_runs'] += res['stuck_seen'] > 0
        agg['stuck_viol'] += res['stuck_viol']
        agg['margin0_runs'] += res['min_margin_x2'] == 0
        agg['phi0_high_runs'] += res['phi0_x2'] >= 2 * (sum(res['L'][:2]) + 176)
    agg['seed'] = seed
    print(json.dumps(agg, ensure_ascii=False))


if __name__ == '__main__':
    main()
