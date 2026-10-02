#!/usr/bin/env python3
"""复核 94F：候选二第（3）步（取出不属本线的物品，缓存格里错的一批等它进了取货物品格再取出）会不会做不完。

「全厂专用进路接法达标」的一段：源矿研磨机 Gs 收两台源矿粉碎机 CrX、CrY 的源石粉末；另一台源矿研磨机 G2 收 CrA、CrB；
Gs、G2 的致密源石粉末各经一条进路进封装机 P。第（4）步之前采种单元是空的，没有砂叶粉末从粉碎机 K 来，配件机也没有钢制零件，
所以 P 在第（4）步前不开工。
蓝图建成时取货端口设定：PX=荞花、PY=砂叶、PB=砂叶（设错），PA=源矿（设对）。开关建成时就开着（情形 on）或第（2）步才开（情形 off）。
第（2）步在第 g_set 步前把三个设错的端口改成源矿（情形 off 同时打开全部开关）。
第（3）步：从第 T_rm 步起每隔 R 步做一轮「取出全部不属本线的物品」（运输物品格、存货物品格、取货物品格；缓存格里的不动，按候选原文等它进格）。
找这样的走法：某台机器缓存格里有一批不属本线的产物，取货物品格里是本线产物、永远腾不空，这批永远进不了格，第（3）步做不完。
两套编码各跑一遍、逐步比对。
"""
import json
import random
import sys

from simp import Net, World, rank_orders
from simq import Q, canon_p

CR = [{'in': [['ys', 1]], 'out': 'ysf', 'qty': 1, 'dur': 8},
      {'in': [['sy', 1]], 'out': 'syf', 'qty': 3, 'dur': 8},
      {'in': [['qh', 1]], 'out': 'qhf', 'qty': 2, 'dur': 8}]
GR = [{'in': [['ysf', 2], ['syf', 1]], 'out': 'mys', 'qty': 1, 'dur': 8},
      {'in': [['qhf', 2], ['syf', 1]], 'out': 'mqh', 'qty': 1, 'dur': 8}]
PK = [{'in': [['lpart', 10], ['mys', 15]], 'out': 'bat', 'qty': 1, 'dur': 40}]

OWN_ROUTE = {'rPX': 'ys', 'rPY': 'ys', 'rPA': 'ys', 'rPB': 'ys', 'rX': 'ysf', 'rY': 'ysf', 'rA': 'ysf', 'rB': 'ysf',
             'rGs': 'mys', 'rG2': 'mys'}
OWN_MACH = {m: ({'ys'}, 'ysf') for m in ('CrX', 'CrY', 'CrA', 'CrB')}
OWN_MACH.update({m: ({'ysf', 'syf'}, 'mys') for m in ('Gs', 'G2')})
OWN_MACH['P'] = ({'lpart', 'mys'}, 'bat')


def desc(par, switches_on):
    U = {}
    for p, k in (('PX', 'qh'), ('PY', 'sy'), ('PA', 'ys'), ('PB', 'sy')):
        U[p] = {'type': 'src', 'kinds': [k]}
    for m in ('CrX', 'CrY', 'CrA', 'CrB'):
        U[m] = {'type': 'mach', 'nslots': 1, 'recipes': CR, 'on': switches_on}
    for m in ('Gs', 'G2'):
        U[m] = {'type': 'mach', 'nslots': 2, 'recipes': GR, 'on': switches_on}
    U['P'] = {'type': 'mach', 'nslots': 2, 'recipes': PK, 'on': switches_on}
    C = []
    for r, a, b in (('rPX', 'PX', 'CrX'), ('rPY', 'PY', 'CrY'), ('rPA', 'PA', 'CrA'), ('rPB', 'PB', 'CrB'),
                    ('rX', 'CrX', 'Gs'), ('rY', 'CrY', 'Gs'), ('rA', 'CrA', 'G2'), ('rB', 'CrB', 'G2'),
                    ('rGs', 'Gs', 'P'), ('rG2', 'G2', 'P')):
        U[r] = {'type': 'seg', 'len': par['len'][r]}
        C += [[a, r], [r, b]]
    ranks = par['ranks']
    return {'units': U, 'chans': [[a, b, ranks[i]] for i, (a, b) in enumerate(C)], 'init': {}}


class P_:
    def __init__(self, d):
        self.net = Net(d['units'], d['chans'])
        self.w = World(self.net, {}, settle='eager')
        self.eo, self.no = rank_orders(self.net)

    def step(self):
        self.w.step(self.eo, self.no)

    def set_port(self, p, k):
        i = self.net.outs[p][0]
        self.w.chan_kind[i] = k

    def set_on(self, on):
        for m in self.w.on:
            self.w.on[m] = on

    def remove_wrong(self, fix=False):
        w, n = self.w, 0
        if fix:
            for m, (raw, prod) in OWN_MACH.items():
                c = w.cache[m]
                if c is not None and c[0] != prod and w.run[m] is None and w.take[m][1] > 0:
                    n += w.take[m][1]
                    w.take[m] = [None, 0]
                    w.flush(m)
        for r, k in OWN_ROUTE.items():
            for j, x in enumerate(w.cell[r]):
                if x is not None and x[0] != k:
                    w.cell[r][j] = None
                    n += 1
        for m, (raw, prod) in OWN_MACH.items():
            for s in w.slot[m]:
                if s[0] is not None and s[0] not in raw:
                    n += s[1]
                    s[0], s[1] = None, 0
            if w.take[m][0] is not None and w.take[m][0] != prod:
                n += w.take[m][1]
                w.take[m] = [None, 0]
        return n

    def count_wrong(self):
        w, n = self.w, 0
        for r, k in OWN_ROUTE.items():
            n += sum(1 for x in w.cell[r] if x is not None and x[0] != k)
        for m, (raw, prod) in OWN_MACH.items():
            n += sum(s[1] for s in w.slot[m] if s[0] is not None and s[0] not in raw)
            n += w.take[m][1] if (w.take[m][0] is not None and w.take[m][0] != prod) else 0
            n += 1 if (w.cache[m] is not None and w.cache[m][0] != prod) else 0
        return n

    def wrong_in_cache(self):
        w = self.w
        return sorted(m for m, (raw, prod) in OWN_MACH.items() if w.cache[m] is not None and w.cache[m][0] != prod)

    def take_of(self, m):
        return tuple(self.w.take[m])

    def canon(self):
        return canon_p(self.w)


class Q_:
    def __init__(self, d):
        self.q = Q(d, settle='eager')
        net = Net(d['units'], d['chans'])
        self.eo, self.no = rank_orders(net)
        self.i = self.q.idx

    def step(self):
        self.q.step(self.eo, self.no)

    def set_port(self, p, k):
        u = self.i[p]
        self.q.kind_of[self.q.out[u][0]] = k

    def set_on(self, on):
        for m in self.q.on:
            self.q.on[m] = on

    def remove_wrong(self, fix=False):
        q, n = self.q, 0
        if fix:
            for m, (raw, prod) in OWN_MACH.items():
                u = self.i[m]
                c = q.cache[u]
                if c is not None and c[0] != prod and q.left[u] == 0 and q.tk[u] is not None:
                    n += q.tk[u][1]
                    q.tk[u] = None
                    q.try_flush(u)
        for r, k in OWN_ROUTE.items():
            for c in q.cells[self.i[r]]:
                if q.cv[c] is not None and q.cv[c][0] != k:
                    q.cv[c] = None
                    n += 1
        for m, (raw, prod) in OWN_MACH.items():
            u = self.i[m]
            n += sum(s[1] for s in q.slots[u] if s[0] not in raw)
            q.slots[u] = [s for s in q.slots[u] if s[0] in raw]
            if q.tk[u] is not None and q.tk[u][0] != prod:
                n += q.tk[u][1]
                q.tk[u] = None
        return n

    def count_wrong(self):
        q, n = self.q, 0
        for r, k in OWN_ROUTE.items():
            n += sum(1 for c in q.cells[self.i[r]] if q.cv[c] is not None and q.cv[c][0] != k)
        for m, (raw, prod) in OWN_MACH.items():
            u = self.i[m]
            n += sum(s[1] for s in q.slots[u] if s[0] not in raw)
            n += q.tk[u][1] if (q.tk[u] is not None and q.tk[u][0] != prod) else 0
            n += 1 if (q.cache[u] is not None and q.cache[u][0] != prod) else 0
        return n

    def wrong_in_cache(self):
        q = self.q
        return sorted(m for m, (raw, prod) in OWN_MACH.items()
                      if q.cache[self.i[m]] is not None and q.cache[self.i[m]][0] != prod)

    def canon(self):
        return self.q.canon()


def run(Ad, par, horizon, fix=False):
    d = desc(par, par['switches_on'])
    ad = Ad(d)
    t = 0
    removed = 0
    log = []
    stuck_since = None
    while t < horizon:
        for p in ('PX', 'PY', 'PB'):
            if t == par['g_set'][p]:
                ad.set_port(p, 'ys')
        if t == max(par['g_set'].values()) and not par['switches_on']:
            ad.set_on(True)
        if t >= par['T_rm'] and (t - par['T_rm']) % par['R'] == 0:
            removed += ad.remove_wrong(fix)
        ad.step()
        t += 1
        wc = ad.wrong_in_cache()
        if wc:
            stuck_since = t if stuck_since is None else stuck_since
        else:
            stuck_since = None
        if t % 400 == 0:
            log.append(ad.canon())
    return {'wrong_in_cache_at_end': ad.wrong_in_cache(), 'wrong_items_at_end': ad.count_wrong(),
            'stuck_steps': (t - stuck_since) if stuck_since else 0,
            'removed': removed, 'final': ad.canon(), 'log': log}


def main():
    s0, n, horizon, out = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    found = []
    tried = 0
    fixed_clean, fixed_bad = 0, []
    for seed in range(s0, s0 + n):
        rng = random.Random(seed)
        lens = {r: rng.randint(1, 5) for r in OWN_ROUTE}
        lens['rX'] = rng.randint(1, 60)
        lens['rY'] = rng.randint(1, 6)
        lens['rPX'] = rng.randint(1, 120)
        lens['rPY'] = rng.randint(1, 120)
        # 第（2）步的几次设定各落在哪两步之间不由玩家定：各端口改对的时刻分开取
        par = {'len': lens, 'ranks': rng.sample(range(20), 20), 'switches_on': True,
               'g_set': {'PX': 8 * rng.randint(1, 30), 'PY': 8 * rng.randint(1, 30), 'PB': 8 * rng.randint(20, 200)}}
        par['T_rm'] = max(par['g_set'].values()) + 8 * rng.choice([0, 1, 5, 20, 50, 100, 200, 400, rng.randint(0, 600)])
        par['R'] = rng.choice([1, 8, 80, 800])
        tried += 1
        rf = run(P_, par, horizon, fix=True)
        fixed_clean += (rf['wrong_items_at_end'] == 0)
        if rf['wrong_items_at_end'] != 0:
            fixed_bad.append(seed)
        rp = run(P_, par, horizon)
        if rp['wrong_in_cache_at_end'] and rp['stuck_steps'] >= horizon // 2:
            rq = run(Q_, par, horizon)
            agree = (rq['final'] == rp['final'] and rq['log'] == rp['log']
                     and rq['wrong_in_cache_at_end'] == rp['wrong_in_cache_at_end'])
            found.append({'seed': seed, 'par': par, 'wrong_in_cache': rp['wrong_in_cache_at_end'],
                          'stuck_steps': rp['stuck_steps'], 'removed': rp['removed'], 'two_codings_agree': agree,
                          'final_state': repr(rp['final'])})
    res = {'tried': tried, 'horizon_steps': horizon, 'stuck': len(found),
           'fixed_procedure_clean_at_end': fixed_clean, 'fixed_procedure_not_clean': fixed_bad, 'cases': found}
    json.dump(res, open(out, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({'tried': tried, 'stuck': len(found), 'fixed_clean': fixed_clean, 'fixed_bad': fixed_bad,
                      'first': found[:3] and [{k: v for k, v in f.items() if k != 'final_state'} for f in found[:3]]},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
