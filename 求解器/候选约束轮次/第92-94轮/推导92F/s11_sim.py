#!/usr/bin/env python3
"""「全厂专用进路接法达标」的接法 + 本报告的调试办法，按步进规则（编码甲 stepsim.py）整厂模拟。

这是核对，不是证明：路长随机取，几何不画；看调试办法做出的起态之后，按现行规则跑出来的
电池、胶囊入库数和 52 条矿石通道的取货数是不是 S11 说的满速。
实验：
  E1 起态干净：一开始就按调试办法第 2、4 步设好、放好种。
  E2 蓝图建成时取货口设错（随机设成仓库里有的别的物品），跑一段后按第 2、3、4 步做：设对、
     分几次随机取出错物品直到没有、放种。
  E3 E1 之后协议核心停收很久再恢复。
  E4 E1 之后多次「离线」：全部通道的接通先后随机重排（轮询记录按通道对应过去）。
每个实验换几组随机接通先后与路长。窗口取最后 1600 步（200 tick）：满速应是电池 120、胶囊 110、
每条矿石通道 200。
用法：python3 s11_sim.py SEED_FROM SEED_TO
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stepsim import Net, Sim  # noqa: E402

CRUSH = [dict(**{'in': [('Si_ore', 1)]}, out='Si_pow', qty=1, dur=8),
         dict(**{'in': [('Fe_blk', 1)]}, out='Fe_pow', qty=1, dur=8),
         dict(**{'in': [('Q_plant', 1)]}, out='Q_pow', qty=2, dur=8),
         dict(**{'in': [('S_plant', 1)]}, out='S_pow', qty=3, dur=8)]
REFINE = [dict(**{'in': [('Fe_ore', 1)]}, out='Fe_blk', qty=1, dur=8),
          dict(**{'in': [('dFe', 1)]}, out='steel', qty=1, dur=8),
          dict(**{'in': [('Fe_pow', 1)]}, out='Fe_blk', qty=1, dur=8)]
GRIND = [dict(**{'in': [('Fe_pow', 2), ('S_pow', 1)]}, out='dFe', qty=1, dur=8),
         dict(**{'in': [('Si_pow', 2), ('S_pow', 1)]}, out='dSi', qty=1, dur=8),
         dict(**{'in': [('Q_pow', 2), ('S_pow', 1)]}, out='fQ', qty=1, dur=8)]
SHAPE = [dict(**{'in': [('steel', 2)]}, out='bottle', qty=1, dur=8)]
PART = [dict(**{'in': [('steel', 1)]}, out='part', qty=1, dur=8)]
PLANT = [dict(**{'in': [('Q_seed', 1)]}, out='Q_plant', qty=1, dur=8),
         dict(**{'in': [('S_seed', 1)]}, out='S_plant', qty=1, dur=8)]
SEEDP = [dict(**{'in': [('Q_plant', 1)]}, out='Q_seed', qty=2, dur=8),
         dict(**{'in': [('S_plant', 1)]}, out='S_seed', qty=2, dur=8)]
PACK = [dict(**{'in': [('part', 10), ('dSi', 15)]}, out='BAT', qty=1, dur=40)]
FILL = [dict(**{'in': [('bottle', 10), ('fQ', 10)]}, out='CAP', qty=1, dur=40)]
WAREHOUSE_KINDS = ['Fe_ore', 'Si_ore', 'Q_plant', 'S_plant', 'Q_seed', 'S_seed']


def build(seed, core_open, core_ports=True):
    rng = random.Random(seed)
    U, ch = {}, []
    line_in, line_out, route_kind = {}, {}, {}
    units_order = []

    def mach(name, recipes, nslots, ins, out):
        U[name] = dict(type='mach', nslots=nslots, recipes=recipes)
        line_in[name], line_out[name] = set(ins), out

    def route(a, b, kind, maxlen=3, short=False):
        n = 1 if short else rng.randint(1, maxlen)
        es = []
        for _ in range(n):
            r = rng.random()
            nm = f'e{len(U)}'
            if r < 0.75 or short:
                U[nm] = dict(type='belt', length=rng.randint(1, 2 if short else 4))
            elif r < 0.9:
                U[nm] = dict(type='baxis')
            else:
                U[nm] = dict(type='gate', allow=None, quota=None)
            route_kind[nm] = kind
            es.append(nm)
        chain = [a] + es + [b]
        for x, y in zip(chain, chain[1:]):
            ch.append([x, y])
        if a == 'core_out':
            U['core_out']['port_kinds'][es[0]] = kind

    # 协议核心：收货一侧记作 core（终点），6 个取货端口记作一个非运输单位 core_out（每步至多送出一件）
    U['core'] = dict(type='sink', open=core_open)
    if core_ports:
        U['core_out'] = dict(type='src', kinds=['Fe_ore'], port_kinds={})
    for i in range(34):
        src = 'core_out' if (i < 3 and core_ports) else f'oFe{i}'
        if src != 'core_out':
            U[src] = dict(type='src', kinds=['Fe_ore'])
        mach(f'R1_{i}', REFINE, 1, ['Fe_ore'], 'Fe_blk')
        mach(f'C1_{i}', CRUSH, 1, ['Fe_blk'], 'Fe_pow')
        route(src, f'R1_{i}', 'Fe_ore')
        route(f'R1_{i}', f'C1_{i}', 'Fe_blk')
    for j in range(18):
        src = 'core_out' if (j < 3 and core_ports) else f'oSi{j}'
        if src != 'core_out':
            U[src] = dict(type='src', kinds=['Si_ore'])
        mach(f'C2_{j}', CRUSH, 1, ['Si_ore'], 'Si_pow')
        route(src, f'C2_{j}', 'Si_ore')
    grinders = []
    for k in range(17):
        g = f'GFe{k}'
        mach(g, GRIND, 2, ['Fe_pow', 'S_pow'], 'dFe')
        route(f'C1_{2*k}', g, 'Fe_pow')
        route(f'C1_{2*k+1}', g, 'Fe_pow')
        grinders.append(g)
    for m in range(9):
        g = f'GSi{m}'
        mach(g, GRIND, 2, ['Si_pow', 'S_pow'], 'dSi')
        route(f'C2_{2*m}', g, 'Si_pow')
        route(f'C2_{2*m+1}', g, 'Si_pow')
        grinders.append(g)
    for q in range(6):
        mach(f'GQ{q}', GRIND, 2, ['Q_pow', 'S_pow'], 'fQ')
        grinders.append(f'GQ{q}')
    units = []
    for u in range(17):
        p = 'S' if u < 11 else 'Q'
        C, A, B, K = f'C{u}', f'A{u}', f'B{u}', f'K{u}'
        mach(C, SEEDP, 1, [f'{p}_plant'], f'{p}_seed')
        mach(A, PLANT, 1, [f'{p}_seed'], f'{p}_plant')
        mach(B, PLANT, 1, [f'{p}_seed'], f'{p}_plant')
        mach(K, CRUSH, 1, [f'{p}_plant'], f'{p}_pow')
        route(C, A, f'{p}_seed', short=True)     # CA
        route(A, C, f'{p}_plant', short=True)    # AC
        route(C, B, f'{p}_seed')                 # CB
        route(B, K, f'{p}_plant')                # BK
        units.append((C, A, B, K, p))
    # 砂叶粉末：10 台 K 各 3 条、1 台 2 条，共 32 条，各进一台研磨机
    gi = 0
    for u in range(11):
        for _ in range(3 if u < 10 else 2):
            route(f'K{u}', grinders[gi], 'S_pow')
            gi += 1
    assert gi == 32
    for q in range(6):
        route(f'K{11+q}', f'GQ{q}', 'Q_pow')
        route(f'K{11+q}', f'GQ{q}', 'Q_pow')
    for k in range(17):
        mach(f'R2_{k}', REFINE, 1, ['dFe'], 'steel')
        route(f'GFe{k}', f'R2_{k}', 'dFe')
    for i in range(6):
        mach(f'P{i}', PART, 1, ['steel'], 'part')
        route(f'R2_{i}', f'P{i}', 'steel')
    for f in range(6):
        mach(f'F{f}', SHAPE, 1, ['steel'], 'bottle')
    for f in range(5):
        route(f'R2_{6+2*f}', f'F{f}', 'steel')
        route(f'R2_{7+2*f}', f'F{f}', 'steel')
    route('R2_16', 'F5', 'steel')
    for e in range(3):
        mach(f'E{e}', PACK, 2, ['part', 'dSi'], 'BAT')
        route(f'P{2*e}', f'E{e}', 'part')
        route(f'P{2*e+1}', f'E{e}', 'part')
        for m in range(3):
            route(f'GSi{3*e+m}', f'E{e}', 'dSi')
        route(f'E{e}', 'core', 'BAT')
    fill_src = [(['F0', 'F1'], ['GQ0', 'GQ1']), (['F2', 'F3'], ['GQ2', 'GQ3']), (['F4', 'F5'], ['GQ4', 'GQ5'])]
    for v, (fs, gs) in enumerate(fill_src):
        mach(f'V{v}', FILL, 2, ['bottle', 'fQ'], 'CAP')
        for x in fs:
            route(x, f'V{v}', 'bottle')
        for x in gs:
            route(x, f'V{v}', 'fQ')
        route(f'V{v}', 'core', 'CAP')
    ranks = list(range(len(ch)))
    rng.shuffle(ranks)
    channels = [(a, b, r) for (a, b), r in zip(ch, ranks)]
    return U, channels, dict(line_in=line_in, line_out=line_out, route_kind=route_kind, units=units)


def reconnect(sim, rng):
    """离线：全部通道的接通先后随机重排。轮询记录按通道（起点、终点）对应过去。"""
    old = sim.net
    pairs = [(c[0], c[1]) for c in old.channels]
    ranks = list(range(len(pairs)))
    rng.shuffle(ranks)
    # 同一对单位之间可能有两条通道（荞花粉碎机两条进同一台研磨机）：按出现次序对应
    newch = [(a, b, r) for (a, b), r in zip(pairs, ranks)]
    newnet = Net(old.units, newch)
    old_by = {}
    for c in old.channels:
        old_by.setdefault((c[0], c[1]), []).append(c)
    new_by = {}
    for c in newnet.channels:
        new_by.setdefault((c[0], c[1]), []).append(c)
    mapping = {}
    for key, lst in old_by.items():
        for o, n in zip(sorted(lst, key=lambda c: c[2]), sorted(new_by[key], key=lambda c: c[2])):
            mapping[o] = n
    newlast = {mapping[c]: v for c, v in sim.last.items()}
    newcursor = {}
    for u in old.units:
        arr_o, arr_n = old.inp[u], newnet.inp[u]
        if len(arr_o) <= 1:
            newcursor[u] = sim.cursor[u]
            continue
        cur = sim.cursor[u] % len(arr_o)
        last_ok = arr_o[cur - 1]           # 上次成功的那条
        newcursor[u] = (arr_n.index(mapping[last_ok]) + 1) % len(arr_n)
    sim.net, sim.last, sim.cursor = newnet, newlast, newcursor
    # 判定先后按新层数（层数不变）重排：按引理无关，随机给一个
    lay = newnet.layer
    order = []
    for L in sorted(set(lay.values())):
        g = [e for e in newnet.elements if lay[e] == L]
        rng.shuffle(g)
        order += g
    nts = list(newnet.nontransport)
    rng.shuffle(nts)
    sim.order = order + nts


def wrong_items(sim, info):
    """不属本线的物品所在之处。"""
    bad = []
    for e, cells in sim.cells.items():
        for j, it in enumerate(cells):
            if it is not None and it.kind != info['route_kind'][e]:
                bad.append(('cell', e, j))
    for m in sim.slots:
        for j, s in enumerate(sim.slots[m]):
            if s[0] is not None and s[0] not in info['line_in'][m]:
                bad.append(('slot', m, j))
        if sim.outslot[m][0] is not None and sim.outslot[m][0] != info['line_out'][m]:
            bad.append(('out', m))
        rec = sim.net.units[m]['recipes']
        if sim.run[m] is not None and rec[sim.run[m][0]]['out'] != info['line_out'][m]:
            bad.append(('run', m))
        if sim.cache[m] is not None and sim.cache[m][0] != info['line_out'][m]:
            bad.append(('cache', m))
    return bad


def remove(sim, where):
    if where[0] == 'cell':
        sim.cells[where[1]][where[2]] = None
    elif where[0] == 'slot':
        sim.slots[where[1]][where[2]] = [None, 0]
    elif where[0] == 'out':
        sim.outslot[where[1]] = [None, 0]
    elif where[0] == 'run':
        sim.run[where[1]] = None
    elif where[0] == 'cache':
        sim.cache[where[1]] = None


def seed_units(sim, info):
    for (C, A, B, K, p) in info['units']:
        assert all(s[0] is None for s in sim.slots[A]) and all(s[0] is None for s in sim.slots[C])
        sim.slots[A][0] = [f'{p}_seed', 50]
        sim.slots[C][0] = [f'{p}_plant', 50]


def phi_min_margin(sim, info):
    """各采种单元 Φ−(L1+L2) 的最小值。"""
    worst = None
    net = sim.net
    for (C, A, B, K, p) in info['units']:
        def elems(a, b):
            # a 到 b 的专用进路上的元件
            x = [c[1] for c in net.out[a] if c[1] in net.layer]
            path = []
            for start in x:
                cur, pth = start, [start]
                while True:
                    nxt = net.out[cur][0][1]
                    if nxt == b:
                        return pth
                    if nxt not in net.layer:
                        break
                    cur = nxt
                    pth.append(cur)
            return None
        ca, ac = elems(C, A), elems(A, C)
        L1 = sum(len(sim.cells[e]) for e in ca)
        L2 = sum(len(sim.cells[e]) for e in ac)
        seeds_ca = sum(1 for e in ca for i in sim.cells[e] if i is not None)
        pl_ac = sum(1 for e in ac for i in sim.cells[e] if i is not None)
        sA = sum(s[1] for s in sim.slots[A] if s[0] == f'{p}_seed')
        oA = sim.outslot[A][1] if sim.outslot[A][0] == f'{p}_plant' else 0
        sC = sum(s[1] for s in sim.slots[C] if s[0] == f'{p}_plant')
        oC = sim.outslot[C][1] if sim.outslot[C][0] == f'{p}_seed' else 0
        bA = 1 if (sim.run[A] is not None or sim.cache[A] is not None) else 0
        bC = 1 if (sim.run[C] is not None or sim.cache[C] is not None) else 0
        phi = seeds_ca + sA + bA + oA + pl_ac + sC + bC + oC / 2
        m = phi - (L1 + L2)
        worst = m if worst is None else min(worst, m)
    return worst


def measure(sim, steps_window):
    got0 = list(sim.sink_got['core'])
    src0 = {s: v for s, v in sim.src_seq.items() if s != 'core_out'}
    port0 = {c: v for c, v in sim.chan_count.items() if c[0] == 'core_out'}
    has_core = 'core_out' in sim.net.units
    for _ in range(steps_window):
        sim.step()
    new = sim.sink_got['core'][len(got0):]
    bat = sum(1 for _, k in new if k == 'BAT')
    cap = sum(1 for _, k in new if k == 'CAP')
    ores = [sim.src_seq[s] - src0[s] for s in src0]
    ports = [sim.chan_count.get((c[0], c[1]), 0) - port0.get((c[0], c[1]), 0)
             for c in sim.net.out['core_out']] if has_core else []
    assert len(ports) + len(ores) == 52
    ores += ports
    return dict(BAT=bat, CAP=cap, ore_min=min(ores), ore_max=max(ores))


def experiment(name, seed):
    rng = random.Random(10_000 + seed)
    closed = [None]
    core_open = (lambda t: closed[0] is None or not (closed[0][0] <= t < closed[0][1]))
    U, channels, info = build(seed, core_open)
    net = Net(U, [tuple(c) for c in channels])
    sim = Sim(net, {}, order_seed=seed)
    log = dict(exp=name, seed=seed)
    if name == 'E2':
        right = dict(U['core_out']['port_kinds']) if 'core_out' in U else {}
        for s in [u for u in U if U[u]['type'] == 'src']:
            U[s]['kinds'] = [rng.choice(WAREHOUSE_KINDS)]
        for e in right:
            U['core_out']['port_kinds'][e] = rng.choice(WAREHOUSE_KINDS)
        for _ in range(rng.randint(40, 200)):
            sim.step()
        for s in [u for u in U if U[u]['type'] == 'src']:
            U[s]['kinds'] = ['Fe_ore'] if s.startswith('oFe') else ['Si_ore']
            sim.src_seq[s] = 0
        if right:
            U['core_out']['port_kinds'].update(right)
        sweeps, removed = 0, 0
        while True:
            for _ in range(rng.randint(1, 30)):       # 操作之间隔多少步不可控
                sim.step()
            bad = wrong_items(sim, info)
            if not bad:
                break
            sweeps += 1
            pick = bad if rng.random() < 0.5 else rng.sample(bad, max(1, len(bad) // 2))
            for w in pick:
                remove(sim, w)
                removed += 1
            assert sweeps < 500
        log.update(sweeps=sweeps, removed=removed)
    # 第 4 步：放种
    seed_units(sim, info)
    margin = phi_min_margin(sim, info)
    for _ in range(rng.randint(0, 40)):           # 放种到结束调试之间
        sim.step()
    log['phi_margin_at_end_of_debug'] = phi_min_margin(sim, info)
    assert not wrong_items(sim, info)
    t_end = sim.t
    if name == 'E3':
        a = t_end + rng.randint(400, 1200)
        closed[0] = (a, a + rng.randint(800, 4000))
        log['stop'] = closed[0]
    phi_track = margin
    run_to = t_end + 2400 + (closed[0][1] - t_end if closed[0] else 0)
    next_off = t_end + rng.randint(100, 600)
    offs = 0
    while sim.t < run_to:
        if name == 'E4' and sim.t >= next_off and offs < 6:
            reconnect(sim, rng)
            offs += 1
            next_off = sim.t + rng.randint(100, 600)
        sim.step()
        if sim.t % 8 == 0:
            phi_track = min(phi_track, phi_min_margin(sim, info))
    if name == 'E4':
        log['offline_events'] = offs
    log['phi_margin_min_after_seeding'] = phi_track
    log['window'] = measure(sim, 1600)
    log['wrong_items_end'] = len(wrong_items(sim, info))
    w = log['window']
    log['full_rate'] = (w['BAT'] == 120 and w['CAP'] == 110 and w['ore_min'] == 200 and w['ore_max'] == 200)
    return log


def main():
    a, b = int(sys.argv[1]), int(sys.argv[2])
    out = []
    for seed in range(a, b):
        for name in ['E1', 'E2', 'E3', 'E4']:
            out.append(experiment(name, seed))
            print(json.dumps(out[-1], ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
