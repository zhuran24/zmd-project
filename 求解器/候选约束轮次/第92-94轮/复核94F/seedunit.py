#!/usr/bin/env python3
"""复核 94F：候选二第（4）步（放种）在一个采种单元上的模拟，两套编码。

采种单元：采种机 C（1 植物 -> 2 种子，1 tick）、种植机 A、B（1 种子 -> 1 植物）、粉碎机 K（1 植物 -> 3 粉末）。
进路都是一段传送带：CA（L1 格）、AC（L2 格）、CB、BK；K 有 3 条取货通道，各经一格带进一个收货侧（模拟研磨机砂叶格，
按随机开合表收货，代表下游任意堵与放）。
做法（四种）：
  lit_AC   ：开关一直开着；先在第 g1 步前往 A 放 50 件种子，过 Δ 步再往 C 放植物（C 的存货物品格有货时只能放到满 50）。
  lit_CA   ：同上，先放 C 后放 A。
  fixed    ：A、C 关着时放（先放哪个、隔多久任意），全部放完后一次打开 A、C。
记：第二次放的时候那个存货物品格里已有几件（>0 说明候选原文「放进 50 件」做不到）；此后每步判定全部完成后的回路存量 Φ 的最小值，
与 L1+L2+5/2 比。
Φ = CA 上种子 + A 存货种子 + A 取货与 AC 上植物 + C 存货植物 + [A 缓存格非空] + [C 缓存格非空] + C 取货种子/2。
"""
import json
import random
import sys

from simp import Net, World, rank_orders
from simq import Q


def unit_desc(L1, L2, LB, LK, rng):
    U = {
        'C': {'type': 'mach', 'nslots': 1, 'recipes': [{'in': [['pl', 1]], 'out': 'sd', 'qty': 2, 'dur': 8}]},
        'A': {'type': 'mach', 'nslots': 1, 'recipes': [{'in': [['sd', 1]], 'out': 'pl', 'qty': 1, 'dur': 8}]},
        'B': {'type': 'mach', 'nslots': 1, 'recipes': [{'in': [['sd', 1]], 'out': 'pl', 'qty': 1, 'dur': 8}]},
        'K': {'type': 'mach', 'nslots': 1, 'recipes': [{'in': [['pl', 1]], 'out': 'pw', 'qty': 3, 'dur': 8}]},
        'CA': {'type': 'seg', 'len': L1}, 'AC': {'type': 'seg', 'len': L2},
        'CB': {'type': 'seg', 'len': LB}, 'BK': {'type': 'seg', 'len': LK},
    }
    C = [['C', 'CA'], ['CA', 'A'], ['C', 'CB'], ['CB', 'B'], ['A', 'AC'], ['AC', 'C'], ['B', 'BK'], ['BK', 'K']]
    for j in range(3):
        U[f'k{j}'] = {'type': 'seg', 'len': 1}
        mode = rng.random()
        if mode < 0.15:
            sp = ('never',)          # 例：这条砂叶粉末通道进的是还没有主料的研磨机
        elif mode < 0.3:
            sp = ('always',)
        elif mode < 0.6:
            sp = ('period', rng.randint(2, 400), rng.randint(1, 200))
        else:
            sp = ('window', rng.randint(0, 3000), rng.randint(50, 3000))
        U[f'g{j}'] = {'type': 'sink', 'open': sp}
        C += [['K', f'k{j}'], [f'k{j}', f'g{j}']]
    ranks = list(range(len(C)))
    rng.shuffle(ranks)
    return {'units': U, 'chans': [[a, b, r] for (a, b), r in zip(C, ranks)], 'init': {}}


class AdP:
    """编码丙的读写口。"""
    def __init__(self, desc):
        self.net = Net(desc['units'], desc['chans'])
        self.w = World(self.net, {}, settle='eager')
        self.eo, self.no = rank_orders(self.net)

    def step(self):
        self.w.step(self.eo, self.no)

    def slot_count(self, m):
        return sum(s[1] for s in self.w.slot[m] if s[0] is not None)

    def place(self, m, kind, n):
        s = self.w.slot[m][0]
        assert s[0] in (None, kind)
        room = 50 - s[1]
        k = min(n, room)
        if k > 0:
            s[0] = kind
            s[1] += k
        return k

    def set_on(self, ms, on):
        for m in ms:
            self.w.on[m] = on

    def phi(self):
        w = self.w
        cnt = lambda e, k: sum(1 for x in w.cell[e] if x is not None and x[0] == k)
        sl = lambda m, k: sum(s[1] for s in w.slot[m] if s[0] == k)
        tk = lambda m, k: w.take[m][1] if w.take[m][0] == k else 0
        return (cnt('CA', 'sd') + sl('A', 'sd') + tk('A', 'pl') + cnt('AC', 'pl') + sl('C', 'pl')
                + (1 if w.cache['A'] is not None else 0) + (1 if w.cache['C'] is not None else 0)
                + tk('C', 'sd') / 2)


class AdQ:
    """编码丁的读写口。"""
    def __init__(self, desc):
        self.q = Q(desc, settle='eager')
        net = Net(desc['units'], desc['chans'])
        self.eo, self.no = rank_orders(net)
        self.i = self.q.idx

    def step(self):
        self.q.step(self.eo, self.no)

    def slot_count(self, m):
        return sum(s[1] for s in self.q.slots[self.i[m]])

    def place(self, m, kind, n):
        sl = self.q.slots[self.i[m]]
        if sl:
            assert sl[0][0] == kind
            room = 50 - sl[0][1]
            k = min(n, room)
            sl[0][1] += k
        else:
            k = min(n, 50)
            if k > 0:
                sl.append([kind, k])
        return k

    def set_on(self, ms, on):
        for m in ms:
            self.q.on[self.i[m]] = on

    def phi(self):
        q, i = self.q, self.i
        cnt = lambda e, k: sum(1 for c in q.cells[i[e]] if q.cv[c] is not None and q.cv[c][0] == k)
        sl = lambda m, k: sum(s[1] for s in q.slots[i[m]] if s[0] == k)
        tk = lambda m, k: q.tk[i[m]][1] if (q.tk[i[m]] is not None and q.tk[i[m]][0] == k) else 0
        return (cnt('CA', 'sd') + sl('A', 'sd') + tk('A', 'pl') + cnt('AC', 'pl') + sl('C', 'pl')
                + (1 if q.cache[i['A']] is not None else 0) + (1 if q.cache[i['C']] is not None else 0)
                + tk('C', 'sd') / 2)


def run_case(Ad, desc, mode, g1, delta, horizon):
    ad = Ad(desc)
    if mode == 'fixed':
        ad.set_on(['A', 'C'], False)
    for _ in range(g1):
        ad.step()
    first, second = (('A', 'sd'), ('C', 'pl')) if mode in ('lit_AC', 'fixed') else (('C', 'pl'), ('A', 'sd'))
    put1 = ad.place(first[0], first[1], 50)
    for _ in range(delta):
        ad.step()
    pre2 = ad.slot_count(second[0])
    put2 = ad.place(second[0], second[1], 50)
    if mode == 'fixed':
        ad.set_on(['A', 'C'], True)
    phi0 = ad.phi()
    phis = []
    for _ in range(horizon):
        ad.step()
        phis.append(ad.phi())
    return {'pre_second': pre2, 'put': [put1, put2], 'phi_after_place': phi0, 'phi_min': min(phis),
            'phi_min_step': phis.index(min(phis))}


def main():
    s0, n, horizon, out = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    rows = []
    summary = {}
    for seed in range(s0, s0 + n):
        rng = random.Random(seed)
        L1 = rng.randint(1, 60)
        L2 = rng.choice([97 - L1, rng.randint(1, 60)]) if L1 < 97 else rng.randint(1, 30)
        L2 = max(1, L2)
        LB, LK = rng.randint(1, 6), rng.randint(1, 6)
        desc = unit_desc(L1, L2, LB, LK, rng)
        g1 = rng.randint(0, 40)
        delta = rng.choice([1, 2, 3, 5, 7, 8, 9, 16, 23, 40, 80, 160, 400, 1200, 2400, 4000, rng.randint(1, 6000)])
        for mode in ('lit_AC', 'lit_CA', 'fixed'):
            rp = run_case(AdP, desc, mode, g1, delta, horizon)
            rq = run_case(AdQ, desc, mode, g1, delta, horizon)
            agree = rp == rq
            need = L1 + L2 + 2.5
            row = dict(seed=seed, L1=L1, L2=L2, LB=LB, LK=LK, g1=g1, delta=delta, mode=mode, agree=agree,
                       need=need, **rp)
            rows.append(row)
            s = summary.setdefault(mode, {'runs': 0, 'disagree': 0, 'second_cell_nonempty': 0,
                                          'phi_below_need': 0, 'phi_below_99_5': 0, 'worst_phi_minus_need': None,
                                          'min_phi_drop_from_place': None})
            s['runs'] += 1
            s['disagree'] += (not agree)
            s['second_cell_nonempty'] += rp['pre_second'] > 0
            s['phi_below_need'] += rp['phi_min'] < need
            s['phi_below_99_5'] += rp['phi_min'] < 99.5
            gap = rp['phi_min'] - need
            if s['worst_phi_minus_need'] is None or gap < s['worst_phi_minus_need']:
                s['worst_phi_minus_need'] = gap
            drop = rp['phi_min'] - rp['phi_after_place']
            if s['min_phi_drop_from_place'] is None or drop < s['min_phi_drop_from_place']:
                s['min_phi_drop_from_place'] = drop
    json.dump({'summary': summary, 'rows': rows}, open(out, 'w'), ensure_ascii=False, indent=0)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
