#!/usr/bin/env python3
"""采种单元不断料：随机相位逐事件模拟（三审自写）。

用法：python3 -B unit_sim.py 种子 次数 [edge]

每次随机建一个采种单元（C 采种机、A、B 种植机、K 粉碎机，四条进路长 1—4，K 有 1—4 条取货通道，
各经 1—3 格进一个随机开关的收货端），1 tick 取 Q 个时间单位（Q 在 1、2、3、5、7、12 里随机），
起态各格物品都对（件数、已停留时间、缓存格剩余加工时间随机），在 0 时刻闭合后取 Φ(s)。
对手期：判定先后随机（含轮询、离线改接通先后），收货端随机停收再恢复；
确定期：判定先后固定、轮询按指针，收货端按整数 tick 的固定节奏开关，跑到状态重复，再走一整个周期核：
  1. Φ(s) ≥ L1+L2+5/2 时，C、A、B、K 在周期里每个时刻闭合后缓存格都不空；
  2. 取 6 个起点 θ，每个 [θ+n, θ+n+1) 里 K 送出 ≥ min(就绪通道数, k)；取货通道不多于 k 条时，
     每条就绪通道恰取 1 件，首运输物品格在每个时刻闭合后都不空；
  3. K 做好的一批从不等待时，C、B、K 在周期里各每 tick 一批；
  4. 对手期与确定期全程：Φ(t) ≥ min(Φ(s)−1/2, L1+L2+176)（已采纳的回路存量下界，作对照）。
Φ(s) < L1+L2+5/2 的对照组只数空手，说明检查查得出失败。
"""
import json
import random
import sys
from fractions import Fraction

from engine import Net

PLANTS = {'荞花': ('荞花种子', '荞花粉末', 2), '砂叶': ('砂叶种子', '砂叶粉末', 3)}


class Unit(Net):
    def __init__(self, Q, rng):
        super().__init__(Q, rng)
        self.watch = []          # K 取货通道首格
        self.log = None          # 确定期周期内的事件记录
        self.any_empty = set()
        self.takes = {}
        self.leaves = set()
        self.on_leave = self._leave
        self.on_take = self._take
        self.phi_min_viol = 0
        self.phi_bound = None

    def _leave(self, c):
        if c in self.watchset:
            self.any_empty.add(c)

    def _take(self, m, c):
        if c in self.watchset:
            self.takes[c] = self.takes.get(c, 0) + 1

    def pre_closure(self):
        self.any_empty = {c for c in self.watch if self.cells[c][0] is None}
        self.takes = {}

    def phi(self):
        C, A = self.C, self.A
        mc, ma = self.machs[C], self.machs[A]
        v = Fraction(0)
        v += sum(1 for c in self.CA if self.cells[c][0] is not None)
        v += sum(1 for c in self.AC if self.cells[c][0] is not None)
        v += sum(ma['store'].values()) + (1 if ma['cache'] else 0) + ma['pk_n']
        v += sum(mc['store'].values()) + (1 if mc['cache'] else 0)
        v += Fraction(mc['pk_n'], 2)
        return v

    def post_closure(self):
        if self.phi_bound is not None and self.phi() < self.phi_bound:
            self.phi_min_viol += 1
        if self.log is not None:
            after = {c for c in self.watch if self.cells[c][0] is None}
            caches = tuple(self.machs[i]['cache'] is not None for i in (self.C, self.A, self.B, self.K))
            kc = self.machs[self.K]['cache']
            kwait = kc is not None and kc[2] <= self.t
            self.log.append((self.t, frozenset(self.any_empty), frozenset(after), dict(self.takes), caches, kwait))


def build(rng, edge):
    Q = rng.choice([1, 2, 3, 5, 7, 12])
    net = Unit(Q, rng)
    plant = rng.choice(list(PLANTS))
    seed, powder, k = PLANTS[plant]
    C = net.mach('C', '采种机')
    A = net.mach('A', '种植机')
    B = net.mach('B', '种植机')
    K = net.mach('K', '粉碎机')
    net.C, net.A, net.B, net.K, net.k = C, A, B, K, k
    L = [rng.randint(1, 4) for _ in range(4)]
    net.CA = net.line(('m', C), ('m', A), L[0])
    net.CB = net.line(('m', C), ('m', B), L[1])
    net.AC = net.line(('m', A), ('m', C), L[2])
    net.BK = net.line(('m', B), ('m', K), L[3])
    nexit = rng.randint(1, 4)
    net.sinkids = []
    net.exitlines = []
    for _ in range(nexit):
        s = net.sink('下游')
        net.sinkids.append(s)
        net.exitlines.append(net.line(('m', K), ('s', s), rng.randint(1, 3)))
    net.watch = [ln[0] for ln in net.exitlines]
    net.watchset = set(net.watch)
    # 起态
    def fill(cells, item, p):
        for c in cells:
            if rng.random() < p:
                net.cells[c][0] = item
                net.cells[c][1] = -rng.randint(0, 2 * Q)
    if edge:
        # 贴着阈值：只在 CA 上和 A 存货物品格放种子，C 取货物品格空，别处空，缓存格空
        S = len(net.CA) + len(net.AC) + 2
        target = S + rng.choice([-1, 0, 1, 1, 1, 2])
        fill(net.CA, seed, 0.5)
        have = sum(1 for c in net.CA if net.cells[c][0])
        net.machs[A]['store'] = {seed: max(0, min(50, target - have))} if target - have > 0 else {}
        fill(net.BK, plant, 0.5)
        fill(net.CB, seed, 0.5)
        for ln in net.exitlines:
            fill(ln, powder, 0.5)
    else:
        p = rng.random()
        fill(net.CA, seed, p)
        fill(net.CB, seed, p)
        fill(net.AC, plant, p)
        fill(net.BK, plant, p)
        for ln in net.exitlines:
            fill(ln, powder, rng.random())
        full = rng.random() < 0.2
        def cnt():
            return 50 if full and rng.random() < 0.7 else rng.randint(0, 50)
        for m, item in ((C, plant), (A, seed), (B, seed), (K, plant)):
            n = cnt()
            if n:
                net.machs[m]['store'] = {item: n}
        for m, item in ((C, seed), (A, plant), (B, plant), (K, powder)):
            n = cnt()
            if n:
                net.machs[m]['pk_item'] = item
                net.machs[m]['pk_n'] = n
        for m, (item, n) in ((C, (seed, 2)), (A, (plant, 1)), (B, (plant, 1)), (K, (powder, k))):
            if rng.random() < 0.6:
                net.machs[m]['cache'] = (item, n, rng.randint(0, Q))
    return net


def run_one(rng, edge):
    net = build(rng, edge)
    Q, k = net.Q, net.k
    net.set_mode(True)
    net.start(0)
    L1, L2 = len(net.CA), len(net.AC)
    S = L1 + L2 + 2
    phi0 = net.phi()
    premise = phi0 >= S + Fraction(1, 2)
    net.phi_bound = min(phi0 - Fraction(1, 2), L1 + L2 + 176)
    # 对手期
    Tadv = rng.randint(30, 300) * Q
    t = 0
    while t < Tadv:
        t2 = t + rng.randint(1, 8 * Q)
        net.advance_to(min(t2, Tadv))
        t = min(t2, Tadv)
        for s in net.sinkids:
            if rng.random() < 0.4:
                net.set_sink(s, rng.random() < 0.6)
        net.poke()
    # 确定期：收货端按固定节奏
    net.set_mode(False)
    pat = []
    for s in net.sinkids:
        if rng.random() < 0.5:
            pat.append(None)          # 一直开
            net.set_sink(s, True)
        else:
            a, b = rng.randint(1, 6), rng.randint(0, 6)
            pat.append((a, b))
    P = 1
    for x in pat:
        if x:
            P = P * (x[0] + x[1]) // __import__('math').gcd(P, x[0] + x[1])
    T0 = t
    seen = {}
    kk = 0
    found = None
    while kk < 20000:
        for s, x in zip(net.sinkids, pat):
            if x:
                net.set_sink(s, (kk % (x[0] + x[1])) < x[0])
        net.poke()
        key = (net.snapshot(), kk % P)
        if key in seen:
            found = (seen[key], kk)
            break
        seen[key] = kk
        net.advance_to(T0 + (kk + 1) * Q)
        kk += 1
    if found is None:
        return dict(cycle=False, premise=premise)
    k1, k2 = found
    per = k2 - k1
    # 再走一个周期，逐事件记录
    net.log = []
    start_t = net.t
    empty0 = frozenset(c for c in net.watch if net.cells[c][0] is None)
    caches0 = tuple(net.machs[i]['cache'] is not None for i in (net.C, net.A, net.B, net.K))
    kc = net.machs[net.K]['cache']
    net.log.append((start_t, empty0, empty0, {}, caches0, kc is not None and kc[2] <= start_t))
    batches = {i: 0 for i in (net.C, net.B, net.K)}
    old_start = net.act_mach
    def counting(i, _o=old_start):
        before = net.machs[i]['cache']
        r = _o(i)
        if r and before is None and net.machs[i]['cache'] is not None and i in batches:
            batches[i] += 1
        return r
    net.act_mach = counting
    snap0 = net.snapshot()
    # 走两个周期：开头那一刻的闭合在记录之前已经做过，区间一律从 start_t 之后起算，两个周期保证每种区间都查到
    for j in range(2 * per):
        kk2 = k2 + j
        if j:
            for s, x in zip(net.sinkids, pat):
                if x:
                    net.set_sink(s, (kk2 % (x[0] + x[1])) < x[0])
            net.poke()
        net.advance_to(start_t + (j + 1) * Q)
        if j == per - 1:
            mid_batches = dict(batches)
    end_t = start_t + 2 * per * Q
    log = [e for e in net.log if e[0] < end_t]
    net.act_mach = old_start
    for s, x in zip(net.sinkids, pat):
        if x:
            net.set_sink(s, ((k2 + 2 * per) % (x[0] + x[1])) < x[0])
    net.poke()
    assert net.snapshot() == snap0, '周期复核失败'
    batches = mid_batches
    res = dict(cycle=True, premise=premise, per=per, Q=Q, k=k, nexit=len(net.watch),
               L=[len(net.CA), len(net.CB), len(net.AC), len(net.BK)], phi0=str(phi0), S=S)
    res['phases'] = len({e[0] % Q for e in log})
    empty_hand = [sum(1 for e in log if not e[4][j]) for j in range(4)]
    res['empty_hand_CABK'] = empty_hand
    # K 出货：对每个起点 θ 把周期切成 [θ+n, θ+n+1)，一次扫过事件记录
    viol_min = viol_each = viol_first = checked = 0
    if premise:
        m = len(net.watch)
        if m <= k:
            viol_first = sum(len(e[2]) for e in log)
        times = [e[0] for e in log]
        for _ in range(6):
            theta = start_t + 1 + rng.randrange(Q)
            idx = 0
            prev_after = empty0
            while idx < len(log) and log[idx][0] < theta:
                prev_after = log[idx][2]
                idx += 1
            a = theta
            while a + Q <= end_t:
                b = a + Q
                ready = set(prev_after)
                sends = {}
                while idx < len(log) and log[idx][0] < b:
                    e = log[idx]
                    ready |= e[1]
                    for c, v in e[3].items():
                        sends[c] = sends.get(c, 0) + v
                    prev_after = e[2]
                    idx += 1
                tot = sum(sends.values())
                checked += 1
                if any(v > 1 for v in sends.values()):
                    viol_each += 1
                if tot < min(len(ready), k):
                    viol_min += 1
                if m <= k and any(sends.get(c, 0) != 1 for c in ready):
                    viol_each += 1
                a = b
    res['intervals'] = checked
    res['viol_min'] = viol_min
    res['viol_each'] = viol_each
    res['viol_first_after_closure'] = viol_first
    kwait = any(e[5] for e in log)
    res['k_waited'] = kwait
    res['batches_CBK'] = [batches[net.C], batches[net.B], batches[net.K]]
    res['viol_rate'] = int(premise and not kwait and res['batches_CBK'] != [per, per, per])
    res['phi_bound_viol'] = net.phi_min_viol
    return res


def main():
    seed = int(sys.argv[1])
    n = int(sys.argv[2])
    edge = len(sys.argv) > 3 and sys.argv[3] == 'edge'
    rng = random.Random(seed)
    tot = dict(runs=0, cycles=0, premise_cycles=0, premise_multi_phase=0, premise_empty_hand=[0, 0, 0, 0],
               control_cycles=0, control_empty_hand_C=0, intervals=0, viol_min=0, viol_each=0,
               viol_first_after_closure=0, never_wait_cycles=0, viol_rate=0, phi_bound_viol=0, no_cycle=0,
               nexit_gt_k_cycles=0)
    for _ in range(n):
        r = run_one(rng, edge)
        tot['runs'] += 1
        if not r['cycle']:
            tot['no_cycle'] += 1
            continue
        tot['cycles'] += 1
        tot['phi_bound_viol'] += r['phi_bound_viol']
        if r['premise']:
            tot['premise_cycles'] += 1
            tot['premise_multi_phase'] += int(r['phases'] > 1)
            for j in range(4):
                tot['premise_empty_hand'][j] += int(r['empty_hand_CABK'][j] > 0)
            for key in ('intervals', 'viol_min', 'viol_each', 'viol_first_after_closure', 'viol_rate'):
                tot[key] += r[key]
            tot['never_wait_cycles'] += int(not r['k_waited'])
            tot['nexit_gt_k_cycles'] += int(r['nexit'] > r['k'])
        else:
            tot['control_cycles'] += 1
            tot['control_empty_hand_C'] += int(r['empty_hand_CABK'][0] > 0)
    print(json.dumps(dict(seed=seed, n=n, edge=edge, **tot), ensure_ascii=False))


if __name__ == '__main__':
    main()
