#!/usr/bin/env python3
"""C 组修订候选「专用进路下缓存格不空的传递」的随机核对（纯传送带输入进路，临时规则）。
用法: python check_c24.py N STEPS SEED"""
from __future__ import annotations
import json, random, sys
from engine import Belt, Cell, Machine, Sink, Source, World, Item, link

CONFIGS = {
    # 名字: (X 配方 {原料: a}, 产物, 产量, d, 存货格数, {原料: c}, 原料来源 'ore' 或 'Y')
    '精炼炉←取货口': ({'蓝铁矿': 1}, '蓝铁块', 1, 1, 1, {'蓝铁矿': 1}, 'ore'),
    '粉碎机←精炼炉': ({'蓝铁块': 1}, '蓝铁粉末', 1, 1, 1, {'蓝铁块': 1}, 'Y'),
    '研磨机←粉碎机': ({'蓝铁粉末': 2, '砂叶粉末': 1}, '致密蓝铁粉末', 1, 1, 2,
                    {'蓝铁粉末': 2, '砂叶粉末': 1}, 'Y'),
    '封装机←两种': ({'钢制零件': 10, '致密源石粉末': 15}, '高容谷地电池', 1, 5, 2,
                  {'钢制零件': 2, '致密源石粉末': 3}, 'Y'),
    '灌装机←两种': ({'钢质瓶': 10, '细磨荞花粉末': 10}, '精选荞愈胶囊', 1, 5, 2,
                  {'钢质瓶': 2, '细磨荞花粉末': 2}, 'Y'),
    '研磨机多一路': ({'蓝铁粉末': 2, '砂叶粉末': 1}, '致密蓝铁粉末', 1, 1, 2,
                   {'蓝铁粉末': 3, '砂叶粉末': 1}, 'Y'),
}
Y_QTY = {'砂叶粉末': 3, '细磨荞花粉末': 1}


def build(rng, cfgname):
    ing, prod, qty, d, nsl, cs, srckind = CONFIGS[cfgname]
    X = Machine('X', (ing, prod, qty, 8 * d), nslots=nsl)
    nodes = [X]
    paths = []
    ys = []
    for kind, c in cs.items():
        for j in range(c):
            if srckind == 'ore':
                src = Source(f'S_{kind}_{j}', kind)
                nodes.append(src)
            else:
                raw = f'raw_{kind}'
                Y = Machine(f'Y_{kind}_{j}', ({raw: 1}, kind, Y_QTY.get(kind, 1), 8))
                ys.append(Y)
                rs = Source(f'R_{kind}_{j}', raw)
                rb = Belt(f'RB_{kind}_{j}', rng.randint(1, 5))
                link(rs, rb); link(rb, Y)
                nodes += [Y, rs, rb]
                src = Y
            b = Belt(f'P_{kind}_{j}', rng.randint(1, 8))
            link(src, b); link(b, X)
            nodes.append(b)
            paths.append((b, kind, src))
    # X 出口：d=1 时一条（检查附加结论），否则 1—2 条
    nout = 1 if (d == 1 and rng.random() < 0.7) else rng.randint(1, 2)
    outs, sinks = [], []
    for i in range(nout):
        sk = Sink(f'XS{i}')
        if rng.random() < 0.6:
            e = Belt(f'XO{i}', rng.randint(1, 4))
        else:
            e = Cell(f'XO{i}.h', unit=f'XO{i}')
        link(X, e); link(e, sk)
        nodes += [e, sk]
        outs.append(e); sinks.append(sk)
    w = World(nodes, rng)
    return w, X, ys, paths, outs, sinks, d, prod


def randomize(rng, w, X, ys, paths, outs, prod):
    for b, kind, src in paths:
        for j in range(len(b.cells)):
            b.cells[j] = Item(kind, rng.randint(-16, -1), None) if rng.random() < rng.random() else None
    for n in w.nodes:
        if isinstance(n, Belt) and n.name.startswith('RB_'):
            raw = 'raw_' + n.name.split('_')[1]
            for j in range(len(n.cells)):
                n.cells[j] = Item(raw, rng.randint(-16, -1), None) if rng.random() < 0.5 else None
    for m in [X] + ys:
        for s in m.slots:
            s[0], s[1] = None, 0
        for k in m.ing:
            if rng.random() < 0.6:
                for s in m.slots:
                    if s[1] == 0:
                        s[0], s[1] = k, rng.randint(1, 50)
                        break
        o = rng.choice([0, 0, rng.randint(1, 50), 50])
        m.out_kind, m.out_n = (m.prod if o else None), o
        r = rng.random()
        m.cache = None if r < 0.4 else (('run', rng.randint(1, m.dur)) if r < 0.8 else ('done',))


def run(rng, steps, warm):
    cfg = rng.choice(list(CONFIGS))
    w, X, ys, paths, outs, sinks, d, prod = build(rng, cfg)
    randomize(rng, w, X, ys, paths, outs, prod)
    p_off = rng.choice([0.0, 0.002, 0.02])
    p_tog = rng.choice([0.0, 0.005, 0.05])
    viol = []
    single = (d == 1 and len(outs) == 1)
    first = outs[0]
    for t in range(steps):
        if rng.random() < p_off:
            w.offline_build()
        for sk in sinks:
            if rng.random() < p_tog:
                sk.open = not sk.open
        w.step()
        if t >= warm:
            if not X.cache_nonempty():
                viol.append(('X缓存空', t))
            if single:
                fc = first.cells[0] if isinstance(first, Belt) else first.item
                if fc is None:
                    viol.append(('出口首格步末空', t))
            for y in ys:
                if not y.cache_nonempty():
                    viol.append(('Y缓存空', t, y.name))
        if len(viol) > 3:
            break
    return dict(cfg=cfg, ok=not viol, viol=viol[:3], single=single, nout=len(outs),
                lens=[len(b.cells) for b, _, _ in paths], ooo=w.log_out_of_order)


def main():
    N, steps, seed = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    rng = random.Random(seed)
    res = [run(random.Random(rng.getrandbits(64)), steps, steps // 2) for _ in range(N)]
    bad = [r for r in res if not r['ok']]
    per = {}
    for r in res:
        per.setdefault(r['cfg'], [0, 0])
        per[r['cfg']][0 if r['ok'] else 1] += 1
    print(json.dumps(dict(N=N, steps=steps, seed=seed, ok=N - len(bad), fail=len(bad), per_config=per,
                          single_output_cases=sum(r['single'] for r in res), first_fails=bad[:3]),
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
