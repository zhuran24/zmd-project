#!/usr/bin/env python3
"""复核 94F：随机生成满足候选「无分流网络的判定先后无关」前提的网络（编码丙用，纯数据）。

前提：没有分流器、协议储存箱；每个运输单位（桥接器每轴算一个）以它为起点的通道至多一条、至多一个非运输单位往它送货；
没有只由运输单位连成的环；取货端口只设两种「矿」o1、o2（货源不断）。
另可选：桥接器两轴分属两条线（同一桥接器单位）；末端没有送货通道的死路（含两格以上的传送带段）；经机器的回路。
"""
import random

ORES = ['o1', 'o2']
PRODS = ['p1', 'p2', 'p3', 'p4']
KINDS = ORES + PRODS


def gen(seed, deadends=True, shared_bridges=True):
    rng = random.Random(seed)
    U, C = {}, []
    cnt = [0]

    def new(p, **d):
        cnt[0] += 1
        u = f'{p}{cnt[0]}'
        U[u] = d
        return u

    srcs = []
    for _ in range(rng.randint(1, 3)):
        k = rng.randint(1, 2)
        srcs.append(new('S', type='src', kinds=[rng.choice(ORES) for _ in range(k)], nports=k))
    machs = []
    for _ in range(rng.randint(2, 5)):
        ns = rng.choice([1, 1, 2])
        recs = []
        for _ in range(rng.randint(1, 2)):
            if ns == 1:
                ins = [[rng.choice(KINDS), rng.choice([1, 1, 2])]]
            else:
                a, b = rng.sample(KINDS, 2)
                ins = [[a, rng.choice([1, 2])], [b, rng.choice([1, 2, 3])]]
            recs.append({'in': ins, 'out': rng.choice(PRODS), 'qty': rng.choice([1, 2, 3]),
                         'dur': rng.choice([8, 8, 16, 40])})
        machs.append(new('M', type='mach', nslots=ns, recipes=recs))
    sinks = []
    for _ in range(rng.randint(1, 2)):
        r = rng.random()
        if r < 0.4:
            sp = ('always',)
        elif r < 0.7:
            sp = ('period', rng.randint(2, 24), rng.randint(1, 12))
        else:
            sp = ('window', rng.randint(10, 200), rng.randint(10, 200))
        sinks.append(new('K', type='sink', open=sp))
    dests = machs + sinks
    bridges = []          # [bridge_id, used_axes]
    hubs = []             # [merger, n_in, has_nont]

    def mk_elem(prev_ty):
        while True:
            ty = rng.choice(['seg', 'seg', 'gate', 'bax'])
            if ty == prev_ty and ty in ('seg', 'bax'):
                continue
            break
        if ty == 'seg':
            return new('B', type='seg', len=rng.randint(1, 4))
        if ty == 'gate':
            d = dict(type='gate', allow=None, q5=None)
            if rng.random() < 0.35:
                d['allow'] = rng.choice(KINDS)
            if rng.random() < 0.35:
                d['q5'] = rng.randint(1, 5)
            return new('G', **d)
        free = [b for b in bridges if b[1] == 1]
        if shared_bridges and free and rng.random() < 0.6:
            b = rng.choice(free)
            b[1] = 2
            bid = b[0]
        else:
            cnt[0] += 1
            bid = f'R{cnt[0]}'
            bridges.append([bid, 1])
        return new('X', type='bax', bridge=bid)

    def chain(n):
        es, pt = [], None
        for _ in range(n):
            e = mk_elem(pt)
            pt = U[e]['type']
            es.append(e)
        for a, b in zip(es, es[1:]):
            C.append([a, b])
        return es

    for _ in range(rng.randint(0, 2)):
        h = new('H', type='mer')
        tail = chain(rng.randint(0, 2))
        d = rng.choice(dests)
        if tail:
            C.append([h, tail[0]])
            C.append([tail[-1], d])
        else:
            C.append([h, d])
        hubs.append([h, 0, False])

    def route(start, from_nont):
        es = chain(rng.randint(1, 3))
        C.append([start, es[0]])
        r = rng.random()
        if deadends and r < 0.12:
            # 死路：末端再接一段两格以上的传送带，没有送货通道
            if U[es[-1]]['type'] == 'seg':
                U[es[-1]]['len'] = max(U[es[-1]]['len'], 2)
            else:
                dd = new('B', type='seg', len=rng.randint(2, 4))
                C.append([es[-1], dd])
            return
        free = [hb for hb in hubs if hb[1] < 3]
        if free and r < 0.5:
            hb = rng.choice(free)
            C.append([es[-1], hb[0]])
            hb[1] += 1
        else:
            C.append([es[-1], rng.choice(dests)])

    for s in srcs:
        for _ in range(U[s]['nports']):
            route(s, True)
    for m in machs:
        for _ in range(rng.randint(1, 3)):
            if rng.random() < 0.15:
                free = [hb for hb in hubs if hb[1] < 3 and not hb[2]]
                if free:
                    hb = rng.choice(free)
                    C.append([m, hb[0]])
                    hb[1] += 1
                    hb[2] = True
                    continue
            route(m, True)
    # src 的通道数与设定物品数对齐
    for s in srcs:
        n = sum(1 for c in C if c[0] == s)
        U[s]['kinds'] = (U[s]['kinds'] * 3)[:n]
    ranks = list(range(len(C)))
    rng.shuffle(ranks)
    chans = [[a, b, r] for (a, b), r in zip(C, ranks)]

    init = {'cell': {}, 'slot': {}, 'take': {}, 'cache': {}, 'run': {}, 'gwin': {}}
    for u, d in U.items():
        ty = d['type']
        if ty in ('seg', 'gate', 'bax', 'mer'):
            L = d.get('len', 1)
            init['cell'][u] = [[rng.choice(KINDS), -rng.randint(0, 9), None] if rng.random() < 0.6 else None
                               for _ in range(L)]
        if ty == 'gate' and d.get('q5') and rng.random() < 0.5:
            init['gwin'][u] = [-rng.randint(0, 39), rng.randint(1, d['q5'])]
        if ty == 'mach':
            ks = rng.sample(KINDS, d['nslots'])
            init['slot'][u] = [[k, rng.choice([1, 2, 30, 48, 49, 50, rng.randint(1, 50)])] if rng.random() < 0.7
                               else [None, 0] for k in ks]
            if rng.random() < 0.6:
                init['take'][u] = [rng.choice(PRODS), rng.choice([1, 2, 3, 48, 49, 50, rng.randint(1, 50)])]
            r = rng.random()
            if r < 0.3:
                rec = rng.choice(d['recipes'])
                init['cache'][u] = [rec['out'], rec['qty']]
                init['run'][u] = [rec['out'], rng.randint(1, rec['dur'])]
            elif r < 0.45:
                rec = rng.choice(d['recipes'])
                init['cache'][u] = [rec['out'], rec['qty']]
    return {'units': U, 'chans': chans, 'init': init, 'seed': seed}


def features(net_desc):
    U, C = net_desc['units'], net_desc['chans']
    outs = {u: [c for c in C if c[0] == u] for u in U}
    ins = {u: [c for c in C if c[1] == u] for u in U}
    elem = ('seg', 'gate', 'bax', 'mer')
    dead_multi = any(U[u]['type'] == 'seg' and U[u]['len'] >= 2 and not outs[u]
                     and any(U[c[0]]['type'] in elem for c in ins[u]) for u in U)
    br = {}
    for u, d in U.items():
        if d['type'] == 'bax' and any(U[c[0]]['type'] in elem for c in ins[u]):
            br.setdefault(d['bridge'], []).append(u)
    shared = any(len(v) >= 2 for v in br.values())
    br2 = {}
    for u, d in U.items():
        if d['type'] == 'bax' and ins[u]:
            br2.setdefault(d['bridge'], []).append(u)
    shared_any = any(len(v) >= 2 for v in br2.values())
    return {'dead_multi': dead_multi, 'shared_bridge': shared, 'shared_bridge_any': shared_any}
