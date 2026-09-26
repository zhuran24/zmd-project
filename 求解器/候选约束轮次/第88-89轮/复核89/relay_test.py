#!/usr/bin/env python3
"""专线制造单位不空手的传递：任意有理相位、X 出口被下游回压、源头另有出口争货。
用法：python3 -B relay_test.py SEED N
X 取精炼炉（矿）、粉碎机（蓝铁块）、三种研磨机、双路塑形机、配件机、封装机、灌装机之一；
每种原料 c_i 条纯料专线（d*c_i ≥ a_i），源头是无限供货的仓库出口，或只做相应 1tick 配方、
自身由无限源喂的制造单位（出口总数 ≤ 每批件数，多余出口接随机开关的下游）。
对手期随机次序、随机下游；确定期固定次序、周期下游；循环里逐闭合时刻查：X 缓存非空、
各源头首格非空、源头缓存非空；X 若是 1tick 且出口 ≤ 批量，X 的出口首格也非空。"""
import sys, json, random
sys.path.insert(0, __import__('os').path.dirname(__file__))
import evsim
from evsim import World, Cell, Line, Sink, Source, make_machine, periodic_sched
from unit_test import random_toggles

# X 的类型：(机型, {原料: 用量}, 产物, 每批件数, d)
XTYPES = [
    ('精炼炉', {'蓝铁矿': 1}, 1, 1),
    ('粉碎机', {'蓝铁块': 1}, 1, 1),
    ('研磨机', {'蓝铁粉末': 2, '砂叶粉末': 1}, 1, 1),
    ('研磨机', {'源石粉末': 2, '砂叶粉末': 1}, 1, 1),
    ('研磨机', {'荞花粉末': 2, '砂叶粉末': 1}, 1, 1),
    ('塑形机', {'钢块': 2}, 1, 1),
    ('配件机', {'钢块': 1}, 1, 1),
    ('封装机', {'钢制零件': 10, '致密源石粉末': 15}, 1, 5),
    ('灌装机', {'钢质瓶': 10, '细磨荞花粉末': 10}, 1, 5),
]
# 原料 -> 产它的 1tick 源头机型、源头原料、每批件数
SRC = {
    '蓝铁块': ('精炼炉', '蓝铁矿', 1), '蓝铁粉末': ('粉碎机', '蓝铁块', 1), '源石粉末': ('粉碎机', '源矿', 1),
    '砂叶粉末': ('粉碎机', '砂叶', 3), '荞花粉末': ('粉碎机', '荞花', 2), '钢块': ('精炼炉', '致密蓝铁粉末', 1),
    '钢制零件': ('配件机', '钢块', 1), '致密源石粉末': ('研磨机', None, 1), '细磨荞花粉末': ('研磨机', None, 1),
    '钢质瓶': ('塑形机', '钢块', 1), '蓝铁矿': None, '源矿': None,
}
GRIND_IN = {'致密源石粉末': {'源石粉末': 2, '砂叶粉末': 1}, '细磨荞花粉末': {'荞花粉末': 2, '砂叶粉末': 1}}


def cells(n, name):
    return [Cell('%s%d' % (name, i)) for i in range(n)]


def trial(rng):
    evsim.CAP = 50
    Q = rng.choice([1, 2, 3, 4, 5, 6, 7, 12])
    w = World(Q, seed=rng.randrange(1 << 30))
    typ, ins, nout, d = rng.choice(XTYPES)
    X = w.add_machine(make_machine('X', typ))
    sinks = []
    srcs = []          # (源头机器, 首格)
    feeders = []
    def feed_machine(m, need):
        """给源头机器 m 接无限供货（每种原料 c 条，保证 1tick 足量）。"""
        for it, a in need.items():
            for j in range(a):
                w.add_line(Line(Source(it), cells(rng.randint(1, 3), 'F'), m, 'F'))
    for it, a in ins.items():
        c = -(-a // d) + rng.choice([0, 0, 0, 1])
        for j in range(c):
            L = rng.randint(1, 4)
            spec = SRC.get(it)
            if spec is None or rng.random() < 0.15 and it in ('蓝铁矿', '源矿'):
                ln = w.add_line(Line(Source(it), cells(L, 'L'), X, 'L'))
                continue
            styp, sin, k = spec
            S = w.add_machine(make_machine('S', styp))
            if styp == '研磨机':
                feed_machine(S, GRIND_IN[it])
            elif styp == '塑形机':
                feed_machine(S, {sin: 2})          # 双路供钢：1tick 足量
            else:
                feed_machine(S, {sin: 1})
            ln = w.add_line(Line(S, cells(L, 'L'), X, 'L'))
            srcs.append((S, ln.cells[0], k, it))
            # 额外出口（出口总数 ≤ k）
            extra = rng.randint(0, k - 1)
            for e in range(extra):
                sk = Sink(name='E')
                w.add_line(Line(S, cells(rng.randint(1, 2), 'E'), sk, 'E'))
                sinks.append(sk)
    # X 的出口
    nx = rng.randint(1, max(1, nout if d == 1 else 2))
    xfirst = []
    for e in range(nx):
        sk = Sink(name='XS')
        ln = w.add_line(Line(X, cells(rng.randint(1, 2), 'XO'), sk, 'XO'))
        sinks.append(sk); xfirst.append(ln.cells[0])
    # 随机合法起态：每台机器只留实际凑得齐的那个配方（纯料专线），存货、取货、缓存都只放它的合法物品
    for m in w.machines:
        if m is X:
            r = [r for r in m.recipes if set(r.ins) == set(ins)][0]
        else:
            r = [r for r in m.recipes if set(r.ins) <= feeds_of(w, m)][0]
        m.recipes = [r]
        for gi, (k0, a) in enumerate(r.ins.items()):
            if rng.random() < 0.7:
                m.grid[gi] = [k0, rng.randint(1, 50)]
        if rng.random() < 0.6:
            m.out = [r.out, rng.randint(1, 50 - r.n + 1)]
        if rng.random() < 0.6:
            m.cache = [r, rng.randint(-Q, r.d * Q)]
    # 线上物品：按源头产物
    for l in w.lines:
        kind = l.src.kind if isinstance(l.src, Source) else l.src.recipes[0].out
        for c in l.cells:
            if rng.random() < 0.6:
                c.kind, c.entry = kind, -rng.randint(0, 2 * Q)
            else:
                c.kind, c.entry = None, None
    Tadv = rng.randint(10, 80) * Q
    for s in sinks:
        s.sched, s.toggles = random_toggles(rng, Q, Tadv)
    w.random_order = True
    w.t = 0
    w.closure()
    w.run_until(Tadv)
    w.random_order = False
    per_of = []
    for s in sinks:
        if rng.random() < 0.3:
            s.sched, s.toggles = (lambda t: True), None
            per_of.append(None)
        else:
            P = rng.randint(2, 30) * Q
            on = rng.randint(1, P)
            ph = rng.randint(0, P - 1)
            s.sched, s.toggles = periodic_sched(Q, P, on, ph)
            per_of.append((P, ph))
    extra = lambda wd: tuple(0 if po is None else (wd.t - po[1]) % po[0] for po in per_of)
    cyc = w.find_cycle(w.t + 6000 * Q, extra)
    res = dict(typ=typ, ins=list(ins), d=d, Q=Q, cycle=cyc)
    if cyc is None:
        return res
    t1, per = cyc
    start = w.t
    st = dict(x_empty=0, src_first_empty=0, src_cache_empty=0, x_first_empty=0, backpressure=False, closures=0,
              mixed=set())
    xone = d == 1 and len(xfirst) <= nout
    def post(wd):
        st['closures'] += 1
        if X.cache is None:
            st['x_empty'] += 1
        for S, c0, k, it in srcs:
            if c0.kind is None:
                st['src_first_empty'] += 1
            if S.cache is None:
                st['src_cache_empty'] += 1
        if xone:
            for c0 in xfirst:
                if c0.kind is None:
                    st['x_first_empty'] += 1
        for g in X.grid:
            if g is not None and g[1] >= 50:
                st['backpressure'] = True
        if X.cache is not None:
            st['mixed'].add(X.cache[1] % Q)
        for S, c0, k, it in srcs:
            if S.cache is not None:
                st['mixed'].add(S.cache[1] % Q)
    w.post.append(post)
    post(w)
    w.run_until(start + per)
    st['mixed'] = len(st['mixed']) > 1
    res.update(st)
    return res


def feeds_of(w, m):
    ks = set()
    for l in w.lines:
        if l.dst is m:
            if isinstance(l.src, Source):
                ks.add(l.src.kind)
            else:
                ks.add(l.src.recipes[0].out)
    return ks


def main():
    seed = int(sys.argv[1]); N = int(sys.argv[2])
    rng = random.Random(seed)
    agg = dict(runs=0, cycles=0, x_empty_runs=0, src_first_empty_runs=0, src_cache_empty_runs=0,
               x_first_empty_runs=0, backpressure_runs=0, mixed_runs=0, by_type={})
    bad = []
    for i in range(N):
        r = trial(rng)
        agg['runs'] += 1
        if r['cycle'] is None:
            continue
        agg['cycles'] += 1
        bt = agg['by_type'].setdefault(r['typ'] + '+'.join(r['ins']), 0)
        agg['by_type'][r['typ'] + '+'.join(r['ins'])] = bt + 1
        for kk in ('x_empty', 'src_first_empty', 'src_cache_empty', 'x_first_empty'):
            if r[kk]:
                agg[kk + '_runs'] += 1
        if r['backpressure']:
            agg['backpressure_runs'] += 1
        if r['mixed']:
            agg['mixed_runs'] += 1
        if r['x_empty'] or r['src_first_empty'] or r['x_first_empty']:
            bad.append((i, r))
    agg['bad'] = bad[:10]
    print(json.dumps(agg, ensure_ascii=False))


if __name__ == '__main__':
    main()
