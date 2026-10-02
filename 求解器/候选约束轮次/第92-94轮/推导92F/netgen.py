#!/usr/bin/env python3
"""随机生成满足引理前提的网络与初态（两套编码共用的纯数据描述）。

前提：没有分流器、协议储存箱；每个运输物品格至多一条送货通道、至多一个非运输单位往它送货；
没有只由运输单位组成的环；仓库取货口的货源不断。
描述是纯 JSON 数据，编码甲（stepsim.py）与编码乙（sim2/simulator.py）各自从它搭网络。
"""
import random

KINDS = ['a', 'b', 'c', 'd']


def gen(seed, allow_gate_filters=True, max_mach=5):
    rng = random.Random(seed)
    units, chans = {}, []
    nid = [0]

    def new(prefix, **d):
        nid[0] += 1
        u = f'{prefix}{nid[0]}'
        units[u] = d
        return u

    nsrc = rng.randint(1, 3)
    nm = rng.randint(2, max_mach)
    nsink = rng.randint(1, 2)
    srcs = [new('S', type='src', kinds=[rng.choice(KINDS) for _ in range(rng.randint(1, 2))]) for _ in range(nsrc)]
    machs = []
    for _ in range(nm):
        nslots = rng.choice([1, 1, 2])
        recs = []
        for _ in range(rng.randint(1, 2)):
            if nslots == 1:
                ins = [(rng.choice(KINDS), rng.choice([1, 1, 2]))]
            else:
                k1, k2 = rng.sample(KINDS, 2)
                ins = [(k1, rng.choice([1, 2])), (k2, rng.choice([1, 2, 3]))]
            recs.append(dict(**{'in': ins}, out=rng.choice(KINDS), qty=rng.choice([1, 2, 3]),
                             dur=rng.choice([8, 8, 16, 40])))
        machs.append(new('M', type='mach', nslots=nslots, recipes=recs))
    sinks = []
    for _ in range(nsink):
        mode = rng.choice(['always', 'period', 'window'])
        if mode == 'always':
            spec = ('always',)
        elif mode == 'period':
            spec = ('period', rng.randint(2, 20), rng.randint(1, 10))
        else:
            spec = ('window', rng.randint(20, 150), rng.randint(20, 150))
        sinks.append(new('K', type='sink', spec=spec))
    dests = machs + sinks
    hubs = []          # (merger, has_nt_input)

    def chain(n):
        es = []
        for _ in range(n):
            ty = rng.choice(['belt', 'belt', 'gate', 'baxis'])
            if ty == 'belt':
                es.append(new('B', type='belt', length=rng.randint(1, 4)))
            elif ty == 'gate':
                d = dict(type='gate', allow=None, quota=None)
                if allow_gate_filters and rng.random() < 0.4:
                    d['allow'] = rng.choice(KINDS)
                if allow_gate_filters and rng.random() < 0.4:
                    d['quota'] = rng.randint(1, 5)
                es.append(new('G', **d))
            else:
                es.append(new('X', type='baxis'))
        for a, b in zip(es, es[1:]):
            chans.append([a, b])
        return es

    # 若干汇流器枢纽：枢纽 -> 一段链 -> 终点
    for _ in range(rng.randint(0, 2)):
        h = new('H', type='merger')
        tail = chain(rng.randint(0, 2))
        dst = rng.choice(dests)
        if tail:
            chans.append([h, tail[0]])
            chans.append([tail[-1], dst])
        else:
            chans.append([h, dst])
        hubs.append([h, False, 0])

    def route(start):
        es = chain(rng.randint(1, 3))
        chans.append([start, es[0]])
        free = [hb for hb in hubs if hb[2] < 3]
        if free and rng.random() < 0.4:
            hb = rng.choice(free)
            chans.append([es[-1], hb[0]])
            hb[2] += 1
        else:
            chans.append([es[-1], rng.choice(dests)])

    for s in srcs:
        for _ in range(rng.randint(1, 2)):
            route(s)
    for m in machs:
        for _ in range(rng.randint(1, 3)):
            if rng.random() < 0.15:
                free = [hb for hb in hubs if hb[2] < 3 and not hb[1]]
                if free:
                    hb = rng.choice(free)
                    chans.append([m, hb[0]])
                    hb[1] = True
                    hb[2] += 1
                    continue
            route(m)
    # 没有任何上游的枢纽删掉不要紧，留着（空元件）
    ranks = list(range(len(chans)))
    rng.shuffle(ranks)
    channels = [(a, b, r) for (a, b), r in zip(chans, ranks)]

    # 初态
    init = dict(cells={}, slots={}, outslot={}, cache={}, run={}, cursor={}, gate={})
    for u, d in units.items():
        ty = d['type']
        if ty in ('belt', 'gate', 'baxis', 'merger'):
            L = d.get('length', 1)
            init['cells'][u] = [([rng.choice(KINDS), -rng.randint(0, 9)] if rng.random() < 0.6 else None)
                                for _ in range(L)]
        if ty == 'gate' and d.get('quota') and rng.random() < 0.5:
            init['gate'][u] = [-rng.randint(0, 39), rng.randint(1, d['quota'])]
        if ty == 'mach':
            ks = rng.sample(KINDS, d['nslots'])
            sl = []
            for k in ks:
                if rng.random() < 0.7:
                    sl.append([k, rng.choice([1, 2, 30, 48, 49, 50, rng.randint(1, 50)])])
                else:
                    sl.append([None, 0])
            init['slots'][u] = sl
            if rng.random() < 0.6:
                init['outslot'][u] = [rng.choice(KINDS), rng.choice([1, 2, 3, 47, 49, 50, rng.randint(1, 50)])]
            r = rng.random()
            if r < 0.3:
                ri = rng.randrange(len(d['recipes']))
                init['run'][u] = [ri, rng.randint(1, d['recipes'][ri]['dur'])]
            elif r < 0.45:
                ri = rng.randrange(len(d['recipes']))
                init['cache'][u] = [d['recipes'][ri]['out'], d['recipes'][ri]['qty']]
    for u in units:
        nin = sum(1 for c in channels if c[1] == u)
        if nin > 1:
            init['cursor'][u] = rng.randrange(nin)
    return dict(units=units, channels=channels, init=init, seed=seed)


def sink_open(spec):
    if spec[0] == 'always':
        return lambda t: True
    if spec[0] == 'period':
        p, q = spec[1], spec[2]
        return lambda t: (t % p) < q
    a, b = spec[1], spec[2]
    return lambda t: not (a <= t < a + b)
