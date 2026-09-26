#!/usr/bin/env python3
"""全厂专线骨架（221 台）逐事件模拟：随机有理相位、随机合法起态（各植物单元 Φ ≥ S+1/2）、
对手期随机判定次序与成品停收/恢复，之后固定次序、核心一直收，跑到规范状态重复，量一个周期的交付与矿路流量。
用法：python3 -B skeleton_test.py SEED N"""
import sys, json, random
sys.path.insert(0, __import__('os').path.dirname(__file__))
import evsim
from evsim import World, Cell, Line, Sink, Source, make_machine
from unit_test import random_toggles


def cells(rng, name, lo=1, hi=2):
    return [Cell('%s%d' % (name, i)) for i in range(rng.randint(lo, hi))]


def build(rng, Q):
    evsim.CAP = 50
    w = World(Q, seed=rng.randrange(1 << 30))
    M = {}
    def mk(name, typ):
        M[name] = w.add_machine(make_machine(name, typ)); return M[name]
    ore = []
    for j in range(34):
        R = mk('R%d' % j, '精炼炉'); KB = mk('KB%d' % j, '粉碎机')
        ore.append(w.add_line(Line(Source('蓝铁矿'), cells(rng, 'o'), R, 'ore')))
        w.add_line(Line(R, cells(rng, 'b'), KB, 'x'))
    for j in range(18):
        KY = mk('KY%d' % j, '粉碎机')
        ore.append(w.add_line(Line(Source('源矿'), cells(rng, 'o'), KY, 'ore')))
    units = []
    for u in range(17):
        plant = '砂叶' if u < 11 else '荞花'
        C = mk('C%d' % u, '采种机'); A = mk('A%d' % u, '种植机'); B = mk('B%d' % u, '种植机'); K = mk('K%d' % u, '粉碎机')
        CA = w.add_line(Line(C, cells(rng, 'CA', 1, 3), A, 'CA'))
        CB = w.add_line(Line(C, cells(rng, 'CB', 1, 3), B, 'CB'))
        AC = w.add_line(Line(A, cells(rng, 'AC', 1, 3), C, 'AC'))
        BK = w.add_line(Line(B, cells(rng, 'BK', 1, 3), K, 'BK'))
        units.append(dict(plant=plant, C=C, A=A, B=B, K=K, CA=CA, CB=CB, AC=AC, BK=BK))
    GB = [mk('GB%d' % j, '研磨机') for j in range(17)]
    GY = [mk('GY%d' % j, '研磨机') for j in range(9)]
    GQ = [mk('GQ%d' % j, '研磨机') for j in range(6)]
    for j in range(17):
        for i in (2 * j, 2 * j + 1):
            w.add_line(Line(M['KB%d' % i], cells(rng, 'p'), GB[j], 'x'))
    for j in range(9):
        for i in (2 * j, 2 * j + 1):
            w.add_line(Line(M['KY%d' % i], cells(rng, 'p'), GY[j], 'x'))
    sandK = [x['K'] for x in units if x['plant'] == '砂叶']
    qiaoK = [x['K'] for x in units if x['plant'] == '荞花']
    grinders = GB + GY + GQ
    perm = list(range(32)); rng.shuffle(perm)
    for n, g in enumerate(grinders):
        w.add_line(Line(sandK[perm[n] // 3], cells(rng, 's'), g, 'x'))
    for j in range(6):
        for _ in range(2):
            w.add_line(Line(qiaoK[j], cells(rng, 'q'), GQ[j], 'x'))
    RS = [mk('RS%d' % j, '精炼炉') for j in range(17)]
    for j in range(17):
        w.add_line(Line(GB[j], cells(rng, 'd'), RS[j], 'x'))
    PJ = [mk('PJ%d' % j, '配件机') for j in range(6)]
    SX = [mk('SX%d' % j, '塑形机') for j in range(6)]
    for j in range(6):
        w.add_line(Line(RS[j], cells(rng, 'g'), PJ[j], 'x'))
    for j in range(5):
        w.add_line(Line(RS[6 + 2 * j], cells(rng, 'g'), SX[j], 'x'))
        w.add_line(Line(RS[7 + 2 * j], cells(rng, 'g'), SX[j], 'x'))
    w.add_line(Line(RS[16], cells(rng, 'g'), SX[5], 'x'))
    FZ = [mk('FZ%d' % j, '封装机') for j in range(3)]
    GZ = [mk('GZ%d' % j, '灌装机') for j in range(3)]
    for j in range(3):
        for i in (2 * j, 2 * j + 1):
            w.add_line(Line(PJ[i], cells(rng, 'z'), FZ[j], 'x'))
        for i in range(3):
            w.add_line(Line(GY[3 * j + i], cells(rng, 'y'), FZ[j], 'x'))
    for j, (s1, s2, q1, q2) in enumerate(((0, 1, 0, 1), (2, 3, 2, 3), (4, 5, 4, 5))):
        w.add_line(Line(SX[s1], cells(rng, 'v'), GZ[j], 'x'))
        w.add_line(Line(SX[s2], cells(rng, 'v'), GZ[j], 'x'))
        w.add_line(Line(GQ[q1], cells(rng, 'f'), GZ[j], 'x'))
        w.add_line(Line(GQ[q2], cells(rng, 'f'), GZ[j], 'x'))
    battery = Sink(name='电池'); capsule = Sink(name='胶囊')
    for m in FZ:
        w.add_line(Line(m, cells(rng, 'e'), battery, 'prod'))
    for m in GZ:
        w.add_line(Line(m, cells(rng, 'e'), capsule, 'prod'))
    return w, M, ore, units, battery, capsule


def feeds_of(w, m):
    ks = set()
    for l in w.lines:
        if l.dst is m:
            ks.add(l.src.kind if isinstance(l.src, Source) else l.src.recipes[0].out)
    return ks


def randomize(w, rng, Q, units):
    # 每台机器确定唯一配方（纯料），随机合法库存与缓存
    # 先定采种单元（它们的来料是自环），再按拓扑逐台定
    for u in units:
        p = u['plant']
        for nm, out in (('C', p + '种子'), ('A', p), ('B', p), ('K', p + '粉末')):
            m = u[nm]
            m.recipes = [r for r in m.recipes if r.out == out]
    changed = True
    while changed:
        changed = False
        for m in w.machines:
            if len(m.recipes) > 1:
                try:
                    f = feeds_of(w, m)
                except Exception:
                    continue
                if any(isinstance(l.src, Machine_) and len(l.src.recipes) > 1 for l in w.lines if l.dst is m):
                    continue
                rs = [r for r in m.recipes if set(r.ins) <= f]
                if rs:
                    m.recipes = [rs[0]]; changed = True
    for m in w.machines:
        assert len(m.recipes) == 1, m.name
        r = m.recipes[0]
        for gi, (k0, a) in enumerate(r.ins.items()):
            if rng.random() < 0.7:
                m.grid[gi] = [k0, rng.randint(1, 50)]
        if rng.random() < 0.5:
            m.out = [r.out, rng.randint(1, 50 - r.n + 1)]
        if rng.random() < 0.6:
            m.cache = [r, rng.randint(-Q, r.d * Q)]
    for l in w.lines:
        kind = l.src.kind if isinstance(l.src, Source) else l.src.recipes[0].out
        for c in l.cells:
            if rng.random() < 0.6:
                c.kind, c.entry = kind, -rng.randint(0, 2 * Q)
    # 植物单元起态补到 Φ ≥ S+1/2
    for u in units:
        seed = u['plant'] + '种子'
        S2 = 2 * (len(u['CA'].cells) + len(u['AC'].cells) + 2)
        while phi2(u) < S2 + 1:
            A = u['A']
            if A.grid[0] is None:
                A.grid[0] = [seed, 0]
            A.grid[0][1] += 1


Machine_ = evsim.Machine


def phi2(u):
    C, A = u['C'], u['A']
    p = u['plant']
    v = 2 * sum(1 for c in u['CA'].cells if c.kind is not None)
    v += 2 * A.stock(p + '种子') + 2 * (A.cache is not None) + 2 * (A.out[1] if A.out else 0)
    v += 2 * sum(1 for c in u['AC'].cells if c.kind is not None)
    v += 2 * C.stock(p) + 2 * (C.cache is not None) + (C.out[1] if C.out else 0)
    return v


LONGSTOP = False


def trial(rng):
    Q = rng.choice([1, 2, 3, 4, 6])
    w, M, ore, units, battery, capsule = build(rng, Q)
    randomize(w, rng, Q, units)
    Tadv = rng.randint(20, 120) * Q
    battery.sched, battery.toggles = random_toggles(rng, Q, Tadv)
    capsule.sched, capsule.toggles = random_toggles(rng, Q, Tadv)
    w.random_order = True
    w.t = 0
    w.closure()
    minphi = [min(phi2(u) - 2 * (len(u['CA'].cells) + len(u['AC'].cells) + 2) for u in units)]
    def post(wd):
        m = min(phi2(u) - 2 * (len(u['CA'].cells) + len(u['AC'].cells) + 2) for u in units)
        minphi[0] = min(minphi[0], m)
    w.post.append(post)
    if LONGSTOP:
        # 先长时间停收（两种都停，或只停一种），让回压传遍全厂，再恢复，之后接随机开关
        which = rng.choice(['both', 'battery', 'capsule'])
        Tstop = rng.randint(200, 500) * Q
        bs, cs = battery.sched, capsule.sched
        battery.sched, battery.toggles = ((lambda t: False) if which in ('both', 'battery') else (lambda t: True)), None
        capsule.sched, capsule.toggles = ((lambda t: False) if which in ('both', 'capsule') else (lambda t: True)), None
        w.run_until(Tstop)
        sb, tb = random_toggles(rng, Q, Tadv)
        sc, tc = random_toggles(rng, Q, Tadv)
        off = w.t
        battery.sched, battery.toggles = (lambda t, f=sb: f(t - off)), (lambda t, f=tb: (None if f(t - off) is None else f(t - off) + off))
        capsule.sched, capsule.toggles = (lambda t, f=sc: f(t - off)), (lambda t, f=tc: (None if f(t - off) is None else f(t - off) + off))
        Tadv = off + Tadv
    w.run_until(Tadv)
    w.post.remove(post)
    w.random_order = False
    battery.sched, battery.toggles = (lambda t: True), None
    capsule.sched, capsule.toggles = (lambda t: True), None
    cyc = w.find_cycle(w.t + 30000 * Q)
    res = dict(Q=Q, Tadv=Tadv, min_phi_minus_S_x2=minphi[0], cycle=cyc)
    if cyc is None:
        return res
    t1, per = cyc
    b0, c0 = battery.got, capsule.got
    o0 = [l.moved_in for l in ore]
    starts0 = {n: m.starts for n, m in M.items()}
    phases = set()
    def post2(wd):
        for m in wd.machines:
            if m.cache is not None:
                phases.add(m.cache[1] % Q)
    w.post.append(post2)
    start = w.t
    w.run_until(start + per)
    res['period_ticks'] = per / Q
    res['battery'] = battery.got - b0
    res['capsule'] = capsule.got - c0
    ticks = per // Q if per % Q == 0 else per / Q
    res['ore_per_tick'] = sorted(set((l.moved_in - o) / (per / Q) for l, o in zip(ore, o0)))
    res['battery_rate'] = (battery.got - b0) / (per / Q)
    res['capsule_rate'] = (capsule.got - c0) / (per / Q)
    res['mixed_phases'] = len(phases) > 1
    return res


def main():
    global LONGSTOP
    seed = int(sys.argv[1]); N = int(sys.argv[2])
    LONGSTOP = len(sys.argv) > 3 and sys.argv[3] == 'longstop'
    rng = random.Random(seed)
    out = []
    for i in range(N):
        r = trial(rng)
        out.append(r)
        print(json.dumps(r, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
