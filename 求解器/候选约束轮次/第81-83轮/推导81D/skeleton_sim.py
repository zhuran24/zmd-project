#!/usr/bin/env python3
"""全厂专线骨架（第 1 节第 5 条）的逐刻模拟核对。不是证明，是对证明的整体检验。

骨架：52 个矿源 -> 34 精炼炉(蓝铁矿) -> 34 粉碎机(蓝铁块) -> 17 研磨机(铁) -> 17 精炼炉(钢)
      -> 6 配件机 + 5 塑形机(两路钢) + 1 塑形机(一路钢) -> 3 封装机 + 3 灌装机 -> 协议核心；
      18 粉碎机(源矿) -> 9 研磨机(源石) -> 封装机；
      11 个砂叶单元（K 共 32 条砂叶粉末通道）-> 32 台研磨机各 1 条；
      6 个荞花单元（K 各 2 条）-> 6 台研磨机(荞花) -> 灌装机。
路长随机，机器物品格上限 m。对手：每刻打乱判定次序、随时改多出口机器的轮询指针（离线）、
一段时间里让协议核心拒收电池/胶囊（仓库满）。然后对手停手（成品全收、次序与指针固定），
跑到状态重复，核循环态：52 条矿石通道每条每 tick 1 件，电池 0.6/tick、胶囊 0.55/tick。
"""
import json, random, sys, time

IDLE, WORK, DONE = 0, 1, 2


class Net:
    def __init__(self, rng, m, Lmax, cell_seed_extra):
        self.rng = rng
        self.m = m
        self.mach = []   # dict: name, rec(in dict), out(item,count), dur, inp{item:cnt}, st, t0, out_cnt, outs[pids], ptr
        self.paths = []  # dict: slots[list], src(('m',i)|('ore',)), dst(('m',i)|('core',item))
        self.Lmax = Lmax
        self.ore_paths = []
        self.core_paths = {'电池': [], '胶囊': []}
        self.cells = []

    def M(self, name, rec, out, dur):
        self.mach.append(dict(name=name, rec=rec, out=out, dur=dur, inp={k: 0 for k in rec}, st=IDLE, t0=0,
                              oc=0, outs=[], ptr=0))
        return len(self.mach) - 1

    def P(self, src, dst, L=None):
        L = L or self.rng.randint(1, self.Lmax)
        self.paths.append(dict(sl=[None] * L, src=src, dst=dst))
        pid = len(self.paths) - 1
        if src[0] == 'm':
            self.mach[src[1]]['outs'].append(pid)
        return pid


def build(rng, m, Lmax):
    n = Net(rng, m, Lmax, 0)
    ore_ref = []; iron_cr = []
    for i in range(34):
        r = n.M('精炼炉矿%d' % i, {'蓝铁矿': 1}, ('蓝铁块', 1), 1)
        n.ore_paths.append(n.P(('ore', '蓝铁矿'), ('m', r)))
        c = n.M('粉碎机铁%d' % i, {'蓝铁块': 1}, ('蓝铁粉末', 1), 1)
        n.P(('m', r), ('m', c)); iron_cr.append(c)
    src_cr = []
    for i in range(18):
        c = n.M('粉碎机源%d' % i, {'源矿': 1}, ('源石粉末', 1), 1)
        n.ore_paths.append(n.P(('ore', '源矿'), ('m', c))); src_cr.append(c)
    Gi = [n.M('研磨机铁%d' % j, {'蓝铁粉末': 2, '砂叶粉末': 1}, ('致密蓝铁粉末', 1), 1) for j in range(17)]
    Gs = [n.M('研磨机源%d' % j, {'源石粉末': 2, '砂叶粉末': 1}, ('致密源石粉末', 1), 1) for j in range(9)]
    F = [n.M('研磨机荞%d' % j, {'荞花粉末': 2, '砂叶粉末': 1}, ('细磨荞花粉末', 1), 1) for j in range(6)]
    for j in range(17):
        n.P(('m', iron_cr[2 * j]), ('m', Gi[j])); n.P(('m', iron_cr[2 * j + 1]), ('m', Gi[j]))
    for j in range(9):
        n.P(('m', src_cr[2 * j]), ('m', Gs[j])); n.P(('m', src_cr[2 * j + 1]), ('m', Gs[j]))

    def cell(plant, powder, k, targets):
        seed = plant + '种子'
        C = n.M('采种机' + plant, {plant: 1}, (seed, 2), 1)
        A = n.M('种植机回' + plant, {seed: 1}, (plant, 1), 1)
        B = n.M('种植机出' + plant, {seed: 1}, (plant, 1), 1)
        K = n.M('粉碎机' + plant, {plant: 1}, (powder, k), 1)
        pCA = n.P(('m', C), ('m', A)); pCB = n.P(('m', C), ('m', B))
        pAC = n.P(('m', A), ('m', C)); n.P(('m', B), ('m', K))
        for tgt in targets:
            n.P(('m', K), ('m', tgt))
        n.cells.append((C, A, B, K, pCA, pAC))
    for j in range(6):
        cell('荞花', '荞花粉末', 2, [F[j], F[j]])
    sand_targets = Gi + Gs + F  # 32
    idx = 0
    for i in range(11):
        tg = sand_targets[idx: idx + 3]; idx += 3
        cell('砂叶', '砂叶粉末', 3, tg)
    Rs = []
    for j in range(17):
        r = n.M('精炼炉钢%d' % j, {'致密蓝铁粉末': 1}, ('钢块', 1), 1)
        n.P(('m', Gi[j]), ('m', r)); Rs.append(r)
    Pm = []
    for i in range(6):
        p = n.M('配件机%d' % i, {'钢块': 1}, ('钢制零件', 1), 1); n.P(('m', Rs[i]), ('m', p)); Pm.append(p)
    Sh = []
    for i in range(5):
        s = n.M('塑形机%d' % i, {'钢块': 2}, ('钢质瓶', 1), 1)
        n.P(('m', Rs[6 + 2 * i]), ('m', s)); n.P(('m', Rs[7 + 2 * i]), ('m', s)); Sh.append(s)
    s = n.M('塑形机5', {'钢块': 2}, ('钢质瓶', 1), 1); n.P(('m', Rs[16]), ('m', s)); Sh.append(s)
    for i in range(3):
        pk = n.M('封装机%d' % i, {'钢制零件': 10, '致密源石粉末': 15}, ('电池', 1), 5)
        n.P(('m', Pm[2 * i]), ('m', pk)); n.P(('m', Pm[2 * i + 1]), ('m', pk))
        for j in range(3):
            n.P(('m', Gs[3 * i + j]), ('m', pk))
        n.core_paths['电池'].append(n.P(('m', pk), ('core', '电池')))
    for i in range(3):
        fl = n.M('灌装机%d' % i, {'钢质瓶': 10, '细磨荞花粉末': 10}, ('胶囊', 1), 5)
        n.P(('m', Sh[2 * i]), ('m', fl)); n.P(('m', Sh[2 * i + 1]), ('m', fl))
        n.P(('m', F[2 * i]), ('m', fl)); n.P(('m', F[2 * i + 1]), ('m', fl))
        n.core_paths['胶囊'].append(n.P(('m', fl), ('core', '胶囊')))
    return n


def phi_cell(n, cell):
    C, A, B, K, pCA, pAC = [n.mach[x] if i < 4 else x for i, x in enumerate(cell)]
    v = sum(1 for s in n.paths[pCA]['sl'] if s is not None) + sum(A['inp'].values()) + (A['st'] != IDLE) + A['oc']
    v += sum(1 for s in n.paths[pAC]['sl'] if s is not None) + sum(C['inp'].values()) + (C['st'] != IDLE)
    return v + C['oc'] / 2.0


def init_state(n, rng):
    # 调试期结束：各格只放本线的物品（随机多少）；然后给每个植物单元的 A 存货格补种子，使 Φ ≥ S+1/2
    for mc in n.mach:
        if rng.random() < 0.3:
            for k in mc['inp']:
                mc['inp'][k] = rng.randint(0, n.m)
        if rng.random() < 0.2:
            mc['oc'] = rng.randint(0, n.m - mc['out'][1])
    for cell in n.cells:
        C, A, B, K, pCA, pAC = cell
        S = len(n.paths[pCA]['sl']) + len(n.paths[pAC]['sl']) + 2
        seedname = list(n.mach[A]['inp'].keys())[0]
        extra = rng.randint(0, 3)
        while phi_cell(n, cell) < S + 0.5 + extra and n.mach[A]['inp'][seedname] < n.m:
            n.mach[A]['inp'][seedname] += 1
        assert phi_cell(n, cell) >= S + 0.5


def step(n, t, order, accept, flips):
    m = n.m
    for i, mc in enumerate(n.mach):
        if mc['st'] == WORK and t - mc['t0'] >= mc['dur']:
            mc['st'] = DONE
        if i in flips and len(mc['outs']) > 1:
            mc['ptr'] = n.rng.randrange(len(mc['outs']))
    ore_taken = [0] * len(n.ore_paths)
    prod = {'电池': 0, '胶囊': 0}
    changed = True
    while changed:
        changed = False
        for kind, i in order:
            if kind == 0:  # machine
                mc = n.mach[i]
                it, cnt = mc['out']
                if mc['st'] == DONE and mc['oc'] + cnt <= m:
                    mc['oc'] += cnt; mc['st'] = IDLE; changed = True
                if mc['st'] == IDLE and all(mc['inp'][k] >= a for k, a in mc['rec'].items()):
                    for k, a in mc['rec'].items():
                        mc['inp'][k] -= a
                    mc['st'] = WORK; mc['t0'] = t; changed = True
            else:  # path i: exit, moves, entry
                p = n.paths[i]
                sl = p['sl']
                if sl[-1] is not None and sl[-1] < t:
                    d = p['dst']
                    if d[0] == 'm':
                        mc = n.mach[d[1]]
                        item = n.mach[p['src'][1]]['out'][0] if p['src'][0] == 'm' else p['src'][1]
                        if mc['inp'][item] < m:
                            mc['inp'][item] += 1; sl[-1] = None; changed = True
                    else:
                        if accept[d[1]]:
                            prod[d[1]] += 1; sl[-1] = None; changed = True
                for j in range(len(sl) - 2, -1, -1):
                    if sl[j] is not None and sl[j] < t and sl[j + 1] is None:
                        sl[j + 1] = t; sl[j] = None; changed = True
                if sl[0] is None:
                    s = p['src']
                    if s[0] == 'ore':
                        sl[0] = t; changed = True
                        ore_taken[n.ore_idx[i]] += 1
                    else:
                        mc = n.mach[s[1]]
                        if mc['oc'] >= 1:
                            outs = mc['outs']
                            if len(outs) == 1:
                                mc['oc'] -= 1; sl[0] = t; changed = True
                            else:
                                # 分级侧：从指针起第一条能动的
                                kk = len(outs)
                                first = None
                                for dd in range(kk):
                                    c = outs[(mc['ptr'] + dd) % kk]
                                    if n.paths[c]['sl'][0] is None:
                                        first = c; break
                                if first == i:
                                    mc['oc'] -= 1; sl[0] = t; changed = True
                                    mc['ptr'] = (outs.index(i) + 1) % kk
    return ore_taken, prod


def key(n, t):
    ms = tuple((tuple(mc['inp'].values()), mc['st'], (t - mc['t0']) if mc['st'] == WORK else -1, mc['oc'], mc['ptr'])
               for mc in n.mach)
    ps = tuple(tuple(s is not None for s in p['sl']) for p in n.paths)
    return (ms, ps)


def trial(seed, m, Lmax, prefix, max_ticks):
    rng = random.Random(seed)
    n = build(rng, m, Lmax)
    n.ore_idx = {pid: j for j, pid in enumerate(n.ore_paths)}
    init_state(n, rng)
    order = [(0, i) for i in range(len(n.mach))] + [(1, i) for i in range(len(n.paths))]
    phis0 = [phi_cell(n, c) for c in n.cells]
    minphi_margin = 1e9
    t = 0
    full_mode = None
    period = rng.choice([50, 300])
    for t in range(prefix):
        if t % period == 0:
            full_mode = rng.choice(['ok', 'ok', 'bat', 'cap', 'both'])
        accept = {'电池': full_mode not in ('bat', 'both'), '胶囊': full_mode not in ('cap', 'both')}
        rng.shuffle(order)
        flips = set(i for i in range(len(n.mach)) if rng.random() < 0.02)
        step(n, t, order, accept, flips)
        for ci, c in enumerate(n.cells):
            C, A, B, K, pCA, pAC = c
            S = len(n.paths[pCA]['sl']) + len(n.paths[pAC]['sl']) + 2
            minphi_margin = min(minphi_margin, phi_cell(n, c) - S)
    rng.shuffle(order)
    accept = {'电池': True, '胶囊': True}
    seen = {}
    hist = []
    for tt in range(prefix, prefix + max_ticks):
        k = key(n, tt)
        if k in seen:
            cyc = hist[seen[k]:]
            L = len(cyc)
            ore_rates = [sum(h[0][j] for h in cyc) / L for j in range(len(n.ore_paths))]
            bat = sum(h[1]['电池'] for h in cyc) / L
            cap = sum(h[1]['胶囊'] for h in cyc) / L
            return dict(seed=seed, m=m, Lmax=Lmax, cycle_start=seen[k] + prefix, cycle_len=L,
                        ore_min=min(ore_rates), ore_max=max(ore_rates), battery=bat, capsule=cap,
                        cell_phi_margin_min=minphi_margin,
                        ok=(min(ore_rates) == 1.0 and abs(bat - 0.6) < 1e-9 and abs(cap - 0.55) < 1e-9))
        seen[k] = len(hist)
        ore_taken, prod = step(n, tt, order, accept, set())
        hist.append((ore_taken, prod))
    return dict(seed=seed, m=m, Lmax=Lmax, nocycle=True, cell_phi_margin_min=minphi_margin)


if __name__ == '__main__':
    n_trials = int(sys.argv[1]); base = int(sys.argv[2])
    t0 = time.time()
    out = []
    rng = random.Random(base)
    for i in range(n_trials):
        m = rng.choice([20, 20, 50])
        Lmax = rng.choice([2, 4])
        prefix = rng.choice([200, 600, 1500])
        out.append(trial(base * 1000 + i, m, Lmax, prefix, 20000))
        sys.stderr.write('%s\n' % json.dumps(out[-1], ensure_ascii=False))
    json.dump(dict(trials=len(out), ok=sum(1 for o in out if o.get('ok')),
                   nocycle=sum(1 for o in out if o.get('nocycle')),
                   bad=[o for o in out if not o.get('ok') and not o.get('nocycle')],
                   all=out, seconds=round(time.time() - t0, 1)), sys.stdout, ensure_ascii=False, indent=1)
