#!/usr/bin/env python3
"""采种双出口专线单元：种群下界、循环态 C/B/K 不空手、K 出口单位时段保证（任意有理相位）。
用法：python3 -B unit_test.py SEED N [edge]
每次：随机容量 m、路长、K 出口数与长度、相位分母 Q；随机合法起态（只有本种植物的正确物品、缓存为空或本机一批）；
t=0 同刻闭合后取 Φ0；对手期随机判定次序与随机下游开关；之后固定次序、周期下游，跑到规范状态重复；
在循环里重放，逐事件时刻查 C/B/K 缓存非空，并对若干 θ 的每个单位时段查 K 出口保证。
edge：把起态补到 Φ0 恰好 ≥ S+1/2 附近（只加不减）。"""
import sys, json, random
sys.path.insert(0, __import__('os').path.dirname(__file__))
import evsim
from evsim import World, Cell, Line, Sink, make_machine, periodic_sched


def build(rng, edge=False):
    m = rng.choice([3, 4, 5, 8, 50])
    evsim.CAP = m
    plant = rng.choice(['荞花', '砂叶'])
    seed = plant + '种子'
    powder = plant + '粉末'
    k = 2 if plant == '荞花' else 3
    Q = rng.choice([1, 2, 3, 4, 5, 6, 12])
    L1, L2, L3, L4 = (rng.randint(1, 4) for _ in range(4))
    nK = rng.randint(1, 4)
    w = World(Q, seed=rng.randrange(1 << 30))
    C = w.add_machine(make_machine('C', '采种机'))
    A = w.add_machine(make_machine('A', '种植机'))
    B = w.add_machine(make_machine('B', '种植机'))
    K = w.add_machine(make_machine('K', '粉碎机'))
    CA = w.add_line(Line(C, [Cell('CA%d' % i) for i in range(L1)], A, 'CA'))
    CB = w.add_line(Line(C, [Cell('CB%d' % i) for i in range(L3)], B, 'CB'))
    AC = w.add_line(Line(A, [Cell('AC%d' % i) for i in range(L2)], C, 'AC'))
    BK = w.add_line(Line(B, [Cell('BK%d' % i) for i in range(L4)], K, 'BK'))
    sinks = []
    exits = []
    for j in range(nK):
        s = Sink(name='S%d' % j)
        ex = w.add_line(Line(K, [Cell('K%d_%d' % (j, i)) for i in range(rng.randint(1, 2))], s, 'KX%d' % j))
        sinks.append(s); exits.append(ex)
    # 随机合法起态
    def rnd_entry():
        return -rng.randint(0, 2 * Q)          # 进格时刻 ≤0，满 1 tick 的时刻在 (−Q, Q]
    def fill(line, kind, p):
        for c in line.cells:
            if rng.random() < p:
                c.kind, c.entry = kind, rnd_entry()
    p = rng.random()
    fill(CA, seed, p); fill(CB, seed, p); fill(AC, plant, p); fill(BK, plant, p)
    for ex in exits:
        fill(ex, powder, rng.random() * 0.5)
    def cnt():
        return rng.choice([0, 0, 1, rng.randint(0, m), m, m - 1])
    for mach, inkind in ((C, plant), (A, seed), (B, seed), (K, plant)):
        c = cnt()
        if c > 0:
            mach.grid[0] = [inkind, c]
    for mach, outk, n in ((C, seed, 2), (A, plant, 1), (B, plant, 1), (K, powder, k)):
        c = cnt()
        if c > 0:
            mach.out = [outk, c]
        if rng.random() < 0.6:
            r = [r for r in mach.recipes if r.out == outk][0]
            mach.cache = [r, rng.randint(-Q, Q)]
    return dict(w=w, m=m, plant=plant, k=k, Q=Q, L=(L1, L2, L3, L4), C=C, A=A, B=B, K=K,
                CA=CA, AC=AC, CB=CB, BK=BK, exits=exits, sinks=sinks, seed=seed)


def phi2(u):
    """2Φ（整数）。"""
    C, A = u['C'], u['A']
    v = 0
    v += 2 * sum(1 for c in u['CA'].cells if c.kind is not None)
    v += 2 * A.stock(u['seed'])
    v += 2 * (A.cache is not None)
    v += 2 * (A.out[1] if A.out else 0)
    v += 2 * sum(1 for c in u['AC'].cells if c.kind is not None)
    v += 2 * C.stock(u['plant'])
    v += 2 * (C.cache is not None)
    v += (C.out[1] if C.out else 0)
    return v


def top_up(u, target2):
    """edge 模式：往 CA/A 存货里补种子，直到 2Φ ≥ target2（只加）。"""
    A = u['A']
    for c in u['CA'].cells:
        if phi2(u) >= target2:
            return
        if c.kind is None:
            c.kind, c.entry = u['seed'], 0
    while phi2(u) < target2 and A.stock(u['seed']) < evsim.CAP:
        if A.grid[0] is None:
            A.grid[0] = [u['seed'], 0]
        A.grid[0][1] += 1


def random_toggles(rng, Q, T):
    ts = sorted(set(rng.randint(1, T) for _ in range(rng.randint(0, max(1, T // (3 * Q) + 1)))))
    state0 = rng.random() < 0.6
    def sched(t):
        import bisect
        i = bisect.bisect_right(ts, t)
        return state0 ^ (i % 2 == 1)
    def toggles(t):
        import bisect
        i = bisect.bisect_right(ts, t)
        return ts[i] if i < len(ts) else None
    return sched, toggles


def trial(rng, edge=False):
    u = build(rng, edge)
    w, Q, m = u['w'], u['Q'], u['m']
    L1, L2, L3, L4 = u['L']
    S2 = 2 * (L1 + L2 + 2)
    if edge:
        top_up(u, S2 + 1)
    w.t = 0
    Tadv = rng.randint(5, 60) * Q
    for s in u['sinks']:
        s.sched, s.toggles = random_toggles(rng, Q, Tadv)
    w.random_order = True
    w.closure()
    p0 = phi2(u)
    bound2 = min(p0 - 1, 2 * (L1 + L2) + 7 * m + 2)
    res = dict(m=m, Q=Q, L=u['L'], nK=len(u['exits']), plant=u['plant'], phi0_2=p0, S2=S2, viol_phi=0,
               min_margin2=None)
    def post(wd):
        v = phi2(u)
        mg = v - bound2
        if res['min_margin2'] is None or mg < res['min_margin2']:
            res['min_margin2'] = mg
        if v < bound2:
            res['viol_phi'] += 1
    w.post.append(post)
    w.run_until(Tadv)
    # 确定期：固定次序，下游周期
    w.random_order = False
    per_of = []
    for s in u['sinks']:
        if rng.random() < 0.4:
            s.sched, s.toggles = (lambda t: True), None
            per_of.append(None)
        else:
            P = rng.randint(1, 7) * Q
            on = rng.randint(1, P)
            ph = rng.randint(0, P - 1)
            s.sched, s.toggles = periodic_sched(Q, P, on, ph)
            per_of.append((P, ph))
    def extra(wd):
        # 周期下游的相位
        return tuple(0 if po is None else (wd.t - po[1]) % po[0] for po in per_of)
    cyc = w.find_cycle(w.t + 4000 * Q, extra)
    if cyc is None:
        res['cycle'] = None
        return res
    t1, per = cyc
    res['cycle'] = (t1, per)
    # 重放：从当前（与 t1 同态）起跑 per（至少 6 tick）并测量
    start = w.t
    span = max(per, 6 * Q) + 2 * Q
    thetas = sorted(set([0, Q // 3, Q // 2, (5 * Q) // 7, Q - 1] if Q > 1 else [0]))
    marks = set()
    for th in thetas:
        n = 0
        while start + th + n * Q <= start + span:
            marks.add(start + th + n * Q); n += 1
    w.marks = sorted(marks)
    ex_ids = [id(e) for e in u['exits']]
    exidx = {id(e): j for j, e in enumerate(u['exits'])}
    counted = [rng.random() < 0.75 for _ in u['exits']]
    all_counted = all(counted) and len(u['exits']) <= u['k']
    log = {}   # t -> [emptyflags, takes]
    def obs(wd, a):
        rec = log.setdefault(wd.t, [[False] * len(u['exits']), [0] * len(u['exits'])])
        for j, e in enumerate(u['exits']):
            if e.cells[0].kind is None:
                rec[0][j] = True
        if a is not None and a[0] == 0:
            l = wd.lines[a[1]]
            if id(l) in exidx:
                rec[1][exidx[id(l)]] += 1
    w.observers.append(obs)
    empt = {'C': 0, 'B': 0, 'K': 0}
    res_mod = set()
    def post2(wd):
        for nm in ('C', 'B', 'K'):
            if u[nm].cache is None:
                empt[nm] += 1
        for nm in ('C', 'A', 'B', 'K'):
            if u[nm].cache is not None:
                res_mod.add(u[nm].cache[1] % Q)
        for e in u['exits'] + [u['CA'], u['AC'], u['CB'], u['BK']]:
            for c in e.cells:
                if c.kind is not None:
                    res_mod.add(c.entry % Q)
    w.post.append(post2)
    # 起点时刻本身的状态也要记
    obs(w, None)
    post2(w)
    w.run_until(start + span)
    res['empty'] = empt
    res['phi_ok_for_nonstarve'] = p0 >= S2 + 1
    # 单位时段检查
    viol_min = viol_each = viol_le1 = n_int = 0
    times = sorted(log)
    for th in thetas:
        a = start + th + Q        # 跳过重放起点所在的一刻（起点时刻的取货发生在重放之前的闭合里，没记到）
        while a + Q <= start + span:
            b = a + Q
            ready = [False] * len(u['exits'])
            takes = [0] * len(u['exits'])
            for tt in times:
                if a <= tt < b:
                    fl, tk = log[tt]
                    for j in range(len(ready)):
                        ready[j] = ready[j] or fl[j]
                        takes[j] += tk[j]
            n_int += 1
            r = sum(1 for j in range(len(ready)) if ready[j] and counted[j])
            if sum(takes) < min(r, u['k']):
                viol_min += 1
            if max(takes) > 1:
                viol_le1 += 1
            if all_counted and any(ready[j] and takes[j] != 1 for j in range(len(ready))):
                viol_each += 1
            a = b
    res.update(n_int=n_int, viol_min=viol_min, viol_each=viol_each, viol_le1=viol_le1, all_counted=all_counted,
               mixed=len(res_mod) > 1)
    # 不同相位？
    phases = set()
    for mname in ('C', 'A', 'B', 'K'):
        pass
    return res


def main():
    seed = int(sys.argv[1]); N = int(sys.argv[2]); edge = len(sys.argv) > 3 and sys.argv[3] == 'edge'
    rng = random.Random(seed)
    agg = dict(runs=0, viol_phi=0, cycles=0, eligible=0, eligible_empty=[0, 0, 0], control=0, control_C_empty=0,
               n_int=0, viol_min=0, viol_each=0, viol_le1=0, min_margin2=None, frac_Q=0)
    bad = []
    for i in range(N):
        r = trial(rng, edge)
        agg['runs'] += 1
        agg['viol_phi'] += r['viol_phi']
        if r['min_margin2'] is not None:
            agg['min_margin2'] = r['min_margin2'] if agg['min_margin2'] is None else min(agg['min_margin2'], r['min_margin2'])
        if r['viol_phi']:
            bad.append(('phi', i, r))
        if r.get('cycle') is None:
            continue
        agg['cycles'] += 1
        if r['Q'] > 1:
            agg['frac_Q'] += 1
        agg['viol_le1'] += r['viol_le1']
        if r['viol_le1']:
            bad.append(('le1', i, r))
        if r['phi_ok_for_nonstarve']:
            agg['n_int'] += r['n_int']; agg['viol_min'] += r['viol_min']; agg['viol_each'] += r['viol_each']
            agg['eligible_mixed'] = agg.get('eligible_mixed', 0) + r['mixed']
            if r['viol_min'] or r['viol_each']:
                bad.append(('exit', i, r))
            agg['eligible'] += 1
            for j, nm in enumerate(('C', 'B', 'K')):
                if r['empty'][nm]:
                    agg['eligible_empty'][j] += 1
            if any(r['empty'].values()):
                bad.append(('starve', i, r))
        else:
            agg['control'] += 1
            agg['control_viol_min'] = agg.get('control_viol_min', 0) + r['viol_min']
            if r['empty']['C']:
                agg['control_C_empty'] += 1
    agg['bad'] = bad[:10]
    print(json.dumps(agg, ensure_ascii=False))


if __name__ == '__main__':
    main()
