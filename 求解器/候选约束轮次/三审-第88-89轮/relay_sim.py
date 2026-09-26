#!/usr/bin/env python3
"""传递一步的随机相位核对（三审自写）：报告第 5 节的两步在一般接法下的核对，不只全厂那张接法。

用法：python3 -B relay_sim.py 种子 次数 [few_lines|extra_exit]

对照 few_lines：某种原料少给一条进路（d·c_i<a_i）；extra_exit：起点制造单位的取货通道多于每批件数。两种对照都应查出空手。

每次随机取一台制造单位 X（九种机型里取一个配方），它的每种原料 i 经 c_i 条专用进路进来，c_i 取满足 d·c_i≥a_i 的最小值再随机加 0—1；
每条进路的起点随机取「一直有货的来源」（仿仓库取货口）或一台起点制造单位 Y：Y 只做一个产物就是原料 i 的 1 tick 配方，
它自己的原料由一直有货的来源经专用进路供给（Y 的原料每批几件就给几条），Y 另有 0—(k_Y−1) 条通往随机开关收货端的取货通道（与 X 争货），
全部取货通道不多于每批件数 k_Y。X 的取货通道 1—2 条，通往随机开关的收货端（回压）。
对手期判定先后随机、收货端随机开关；确定期判定先后固定、收货端按整数 tick 的固定节奏开关，跑到状态重复，再走一个周期核：
X 在每个时刻闭合后缓存格不空；每条通往 X 的进路每格在每个时刻闭合后都有物品；X 是 1 tick 配方、取货通道不多于每批件数、
下游一直收时，X 的取货通道首格在每个时刻闭合后都有物品。
"""
import json
import math
import random
import sys

from engine import Net, RECIPES


class Relay(Net):
    def __init__(self, Q, rng):
        super().__init__(Q, rng)
        self.checking = False
        self.claim_m = set()
        self.claim_c = set()
        self.viol_m = self.viol_c = 0
        self.xf = set()
        self.vac = set()
        self.on_leave = lambda c: self.vac.add(c) if self.checking and c in self.claim_c else None
        self.phases = set()

    def act_mach(self, i):
        before = self.machs[i]['cache']
        r = super().act_mach(i)
        if r and self.checking and before is not None and self.machs[i]['cache'] is None:
            self.xf.add(i)
        return r

    def pre_closure(self):
        self.xf = set()
        self.vac = set()

    def post_closure(self):
        if not self.checking:
            return
        self.phases.add(self.t % self.Q)
        for i in self.xf:
            if i in self.claim_m and self.machs[i]['cache'] is None:
                self.viol_m += 1
        for c in self.vac:
            if self.cells[c][0] is None:
                self.viol_c += 1


def producers():
    """产物 → [(机型, 配方下标)]，只取 1 tick 配方。"""
    out = {}
    for typ, rs in RECIPES.items():
        for j, (ins, prod, n, d) in enumerate(rs):
            if d == 1:
                out.setdefault(prod, []).append((typ, j))
    return out


PROD = producers()


def build(rng, control=None):
    Q = rng.choice([1, 2, 3, 5, 7, 12])
    net = Relay(Q, rng)
    L = lambda: rng.randint(1, 3)
    typ = rng.choice(list(RECIPES))
    j = rng.randrange(len(RECIPES[typ]))
    ins, prod, n, d = RECIPES[typ][j]
    X = net.mach('X', typ, j)
    lines = []
    _line = net.line

    def line(src, dst, n_, item):
        cs = _line(src, dst, n_)
        lines.append((cs, item))
        return cs
    sinks = []
    pat = []
    net.claim_m = {X}
    ysrc = []
    few = None
    if control == 'few_lines':
        cand = [it for it, a in ins.items() if math.ceil(a / d) >= 2]
        if not cand:
            return None
        few = rng.choice(cand)
    for item, a in ins.items():
        c = math.ceil(a / d) + rng.randint(0, 1)
        if item == few:
            c = math.ceil(a / d) - 1
        for _ in range(c):
            if item in PROD and (control == 'extra_exit' or rng.random() < 0.7):
                ytyp, yj = rng.choice(PROD[item])
                yins, _, k, _ = RECIPES[ytyp][yj]
                Y = net.mach('Y', ytyp, yj)
                ysrc.append(Y)
                for it2, a2 in yins.items():
                    for _ in range(a2):
                        o = net.ore(it2)
                        line(('o', o), ('m', Y), L(), it2)
                cs = line(('m', Y), ('m', X), L(), item)
                net.claim_c.update(cs)
                for _ in range(k if control == 'extra_exit' else rng.randint(0, k - 1)):
                    s = net.sink('争货')
                    sinks.append(s)
                    line(('m', Y), ('s', s), L(), item)
                net.claim_m.add(Y)
            else:
                o = net.ore(item)
                cs = line(('o', o), ('m', X), L(), item)
                net.claim_c.update(cs)
    nx = rng.randint(1, 2)
    xsinks = []
    for _ in range(nx):
        s = net.sink('下游')
        sinks.append(s)
        xsinks.append(s)
        line(('m', X), ('s', s), L(), prod)
    # 起态：路上随机放本线物品，机器存货随机、缓存随机
    p = rng.random()
    for cs, item in lines:
        for c in cs:
            if rng.random() < p:
                net.cells[c][0] = item
                net.cells[c][1] = -rng.randint(0, 2 * Q)
    for m in net.machs:
        rec = m['rec'][0]
        for it in rec[0]:
            v = rng.randint(0, 50)
            if v:
                m['store'][it] = v
        v = rng.randint(0, 50)
        if v:
            m['pk_item'], m['pk_n'] = rec[1], v
        if rng.random() < 0.6:
            m['cache'] = (rec[1], rec[2], rng.randint(0, rec[3] * Q))
    return net, X, sinks, xsinks, (typ, prod, n, d, nx)


def run_one(rng, control=None):
    b = build(rng, control)
    if b is None:
        return None
    net, X, sinks, xsinks, info = b
    Q = net.Q
    # 路上起态：按每条进路的物品放货
    net.set_mode(True)
    net.start(0)
    Tadv = rng.randint(50, 300) * Q
    t = 0
    while t < Tadv:
        t2 = min(Tadv, t + rng.randint(1, 10 * Q))
        net.advance_to(t2)
        t = t2
        for s in sinks:
            if rng.random() < 0.5:
                net.set_sink(s, rng.random() < 0.5)
        net.poke()
    net.set_mode(False)
    open_all = rng.random() < 0.4
    pat = {}
    for s in sinks:
        if open_all or rng.random() < 0.4:
            pat[s] = None
            net.set_sink(s, True)
        else:
            pat[s] = (rng.randint(1, 5), rng.randint(1, 5))
    P = 1
    for x in pat.values():
        if x:
            P = P * sum(x) // math.gcd(P, sum(x))
    T0 = net.t
    seen = {}
    kk = 0
    found = None

    def setp(k):
        for s, x in pat.items():
            if x:
                net.set_sink(s, (k % sum(x)) < x[0])
        net.poke()
    while kk < 20000:
        setp(kk)
        key = (net.snapshot(), kk % P)
        if key in seen:
            found = (seen[key], kk)
            break
        seen[key] = kk
        net.advance_to(T0 + (kk + 1) * Q)
        kk += 1
    if found is None:
        return None
    per = found[1] - found[0]
    snap0 = net.snapshot()
    start = net.t
    typ, prod, n, d, nx = info
    xfirst = [net.machs[X]['exits'][e] for e in range(nx)]
    check_xfirst = d == 1 and nx <= n and all(pat[s] is None for s in xsinks)
    if check_xfirst:
        net.claim_c.update(xfirst)
    net.checking = True
    v0 = sum(1 for i in net.claim_m if net.machs[i]['cache'] is None) + sum(1 for c in net.claim_c if net.cells[c][0] is None)
    for j in range(per):
        if j:
            setp(found[1] + j)
        net.advance_to(start + (j + 1) * Q)
    net.checking = False
    setp(found[1] + per)
    assert net.snapshot() == snap0
    x_waited = False
    return dict(typ=typ, d=d, per=per, Q=Q, phases=len(net.phases), viol=net.viol_m + net.viol_c + v0,
                check_xfirst=check_xfirst, backpressure=any(pat[s] for s in xsinks) or not open_all)


def main():
    seed, n = int(sys.argv[1]), int(sys.argv[2])
    control = sys.argv[3] if len(sys.argv) > 3 else None
    rng = random.Random(seed)
    tot = dict(control=control, runs_with_viol=0, runs=0, cycles=0, viol=0, d5=0, multi_phase=0, xfirst_checked=0, backpressure=0, types={})
    for _ in range(n):
        r = run_one(rng, control)
        tot['runs'] += 1
        if r is None:
            continue
        tot['cycles'] += 1
        tot['viol'] += r['viol']
        tot['runs_with_viol'] += int(r['viol'] > 0)
        tot['d5'] += int(r['d'] == 5)
        tot['multi_phase'] += int(r['phases'] > 1)
        tot['xfirst_checked'] += int(r['check_xfirst'])
        tot['backpressure'] += int(r['backpressure'])
        tot['types'][r['typ']] = tot['types'].get(r['typ'], 0) + 1
    print(json.dumps(dict(seed=seed, **tot), ensure_ascii=False))


if __name__ == '__main__':
    main()
