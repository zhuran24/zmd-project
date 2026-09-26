#!/usr/bin/env python3
"""随机相位模拟：专用进路下缓存格不空的传递（任意相位版）的三审核对。

逐事件模拟，时间用有理数精确表示（fractions），各单位的物品进格、开批、准入口窗口、
下游停收与恢复的时刻落在各不相同的相位上（分母取 2、3、5、7、11、13、17、101 等）。
- 同一时刻：按一个固定的判定先后反复扫，做到一整遍没有可动为止（闭合）；
  制造单位的多条取货通道、多条存货通道按接通先后轮询（指针随成功的移动前进）。
- 过渡期：下游收货端随机停收与恢复，随机时刻离线（重排判定先后与各单位通道的接通先后）。
- 之后判定先后固定、下游按一个任意相位的周期停收与恢复（玩家按时拿取），跑到状态重复，
  再逐事件记两个周期，核：
  前提（起点制造单位每个时刻闭合后缓存格不空、一直开着）成立时，X 每个时刻闭合后缓存格不空；
  起点满足前提的进路每格闭合后不空；起点的首格闭合后不空；
  末句适用时，X 的首格闭合后不空，任取 θ，[θ+n, θ+n+1) 里每条通道至多收 1 件、就绪（某个时点为空）则恰收 1 件。
配方从正式规则现读。只用标准库，单线程。
用法：python3 phase_sim.py <种子> <次数> [normal|extra|off|few|lim]
"""
import json
import math
import random
import re
import sys
from fractions import Fraction as F
from pathlib import Path

RULES = Path(__file__).resolve().parents[3] / '《明日方舟：终末地》游戏规则.txt'
SLOTS = {'粉碎机': 1, '精炼炉': 1, '配件机': 1, '塑形机': 1, '采种机': 1, '种植机': 1,
         '研磨机': 2, '封装机': 2, '灌装机': 2}
CAP = 50
DENS = [1, 2, 3, 5, 7, 11, 13, 17, 101]


def read_recipes():
    text = RULES.read_text(encoding='utf-8')
    body = text.split('\n配方\n', 1)[1]
    recs, mach = [], None
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        if line in SLOTS:
            mach = line
            continue
        m = re.fullmatch(r'(.+?)\s*→\s*(\d+)\s*(\S+?)，(\d+)\s*tick', line)
        assert m, line
        ins = {}
        for part in re.split(r'\s*＋\s*', m.group(1)):
            a, it = part.split()
            ins[it] = int(a)
        recs.append(dict(mach=mach, ins=ins, k=int(m.group(2)), prod=m.group(3), d=int(m.group(4))))
    assert len(recs) == 18, len(recs)
    return recs


RECIPES = read_recipes()


def rnd_frac(rng, lo, hi):
    q = rng.choice(DENS)
    return F(rng.randrange(math.ceil(lo * q), math.floor(hi * q) + 1), q)


class Sim:
    """一张局部接法。"""

    def __init__(self):
        self.cells = {}      # 名 -> dict(item, tin, gate)
        self.machs = {}      # 名 -> dict(rec, store, cache, pick, on, pch, sch, pp, sp)
        self.sinks = {}      # 名 -> 收货端
        self.chans = []      # (src, dst)：src=('W',物品)|('cell',名)|('mach',名)；dst=('cell',名)|('store',名)|('sink',名)
        self.now = F(0)

    # ---------- 接法 ----------
    def add_cell(self, name, gate=None):
        self.cells[name] = dict(item=None, tin=None, gate=gate)   # gate: dict(allow, lim, ws, cnt)

    def add_mach(self, name, rec):
        self.machs[name] = dict(rec=rec, store={}, cache=None, pick=None, pickn=0, on=True,
                                pch=[], sch=[], pp=0, sp=0)

    def connect(self, src, dst):
        ci = len(self.chans)
        self.chans.append((src, dst))
        if src[0] == 'mach':
            self.machs[src[1]]['pch'].append(ci)
        if dst[0] == 'store':
            self.machs[dst[1]]['sch'].append(ci)
        return ci

    # ---------- 规则 ----------
    def gate_refresh(self, g):
        if g['ws'] is not None and self.now >= g['ws'] + 5:
            g['ws'], g['cnt'] = None, 0

    def src_item(self, src):
        if src[0] == 'W':
            return src[1]
        if src[0] == 'cell':
            c = self.cells[src[1]]
            if c['item'] is not None and self.now >= c['tin'] + 1:
                return c['item']
            return None
        m = self.machs[src[1]]
        return m['pick'] if m['pickn'] > 0 else None

    def dst_ok(self, dst, item):
        if dst[0] == 'cell':
            c = self.cells[dst[1]]
            if c['item'] is not None:
                return False
            g = c['gate']
            if g is not None:
                self.gate_refresh(g)
                if g['allow'] is not None and g['allow'] != item:
                    return False
                if g['lim'] is not None and g['ws'] is not None and g['cnt'] >= g['lim']:
                    return False
            return True
        if dst[0] == 'store':
            m = self.machs[dst[1]]
            n = m['store'].get(item, 0)
            if n >= CAP:
                return False
            if n == 0 and sum(1 for v in m['store'].values() if v > 0) >= SLOTS[m['rec']['mach']]:
                return False
            return True
        return self.sinks[dst[1]].open(self.now)

    def do_move(self, ci):
        src, dst = self.chans[ci]
        item = self.src_item(src)
        if item is None or not self.dst_ok(dst, item):
            return False
        if src[0] == 'cell':
            c = self.cells[src[1]]
            c['item'] = None
            self.log('left', src[1])
        elif src[0] == 'mach':
            m = self.machs[src[1]]
            m['pickn'] -= 1
            if m['pickn'] == 0:
                m['pick'] = None
        if dst[0] == 'cell':
            c = self.cells[dst[1]]
            c['item'], c['tin'] = item, self.now
            g = c['gate']
            if g is not None and g['lim'] is not None:
                if g['ws'] is None:
                    g['ws'], g['cnt'] = self.now, 1
                else:
                    g['cnt'] += 1
            self.log('in', dst[1])
        elif dst[0] == 'store':
            m = self.machs[dst[1]]
            m['store'][item] = m['store'].get(item, 0) + 1
        return True

    def poll(self, lst, ptr_owner, key):
        n = len(lst)
        if n == 0:
            return False
        p = ptr_owner[key] % n
        for j in range(n):
            ci = lst[(p + j) % n]
            if self.do_move(ci):
                ptr_owner[key] = (p + j + 1) % n
                return True
        return False

    def try_load(self, m):
        if m['cache'] is not None:
            return False
        rec = m['rec']
        if all(m['store'].get(i, 0) >= a for i, a in rec['ins'].items()):
            for i, a in rec['ins'].items():
                m['store'][i] -= a
            m['cache'] = F(rec['d'])        # 剩余进度
            return True
        return False

    def try_out(self, m):
        rec = m['rec']
        if m['cache'] != 0:
            return False
        if m['pickn'] > 0 and m['pick'] != rec['prod']:
            return False
        if m['pickn'] + rec['k'] > CAP:
            return False
        m['pick'] = rec['prod']
        m['pickn'] += rec['k']
        m['cache'] = None
        return True

    def build_groups(self, rng):
        groups = []
        for ci, (src, dst) in enumerate(self.chans):
            if src[0] != 'mach' and dst[0] != 'store':
                groups.append(('ch', ci))
        for name in self.machs:
            groups += [('pick', name), ('store', name), ('load', name), ('out', name)]
        rng.shuffle(groups)
        self.groups = groups

    def offline(self, rng):
        """离线：任意两条通道的接通先后可能改变。这里重排判定先后与各单位通道的接通先后。"""
        self.build_groups(rng)
        for m in self.machs.values():
            rng.shuffle(m['pch'])
            rng.shuffle(m['sch'])
            m['pp'] = rng.randrange(max(1, len(m['pch'])))
            m['sp'] = rng.randrange(max(1, len(m['sch'])))

    def closure(self):
        while True:
            any_ = False
            for kind, x in self.groups:
                if kind == 'ch':
                    ok = self.do_move(x)
                elif kind == 'pick':
                    m = self.machs[x]
                    ok = self.poll(m['pch'], m, 'pp')
                elif kind == 'store':
                    m = self.machs[x]
                    ok = self.poll(m['sch'], m, 'sp')
                elif kind == 'load':
                    ok = self.try_load(self.machs[x])
                else:
                    ok = self.try_out(self.machs[x])
                any_ = any_ or ok
            if not any_:
                return

    # ---------- 时间 ----------
    def next_event(self, extra):
        cand = list(extra)
        for c in self.cells.values():
            if c['item'] is not None and c['tin'] + 1 > self.now:
                cand.append(c['tin'] + 1)
            g = c['gate']
            if g is not None and g['ws'] is not None and g['ws'] + 5 > self.now:
                cand.append(g['ws'] + 5)
        for m in self.machs.values():
            if m['on'] and m['cache'] is not None and m['cache'] > 0:
                cand.append(self.now + m['cache'])
        for s in self.sinks.values():
            cand.append(s.next_toggle(self.now))
        return min(t for t in cand if t > self.now)

    def advance_to(self, t):
        dt = t - self.now
        for m in self.machs.values():
            if m['on'] and m['cache'] is not None and m['cache'] > 0:
                m['cache'] = max(F(0), m['cache'] - dt)
        self.now = t

    # ---------- 记录 ----------
    def log(self, kind, cell):
        if self.logging is not None and cell in self.watch:
            self.logging.append((self.now, kind, cell))

    def signature(self, phase):
        cs = []
        for name in sorted(self.cells):
            c = self.cells[name]
            rem = None if c['item'] is None else max(F(0), c['tin'] + 1 - self.now)
            g = c['gate']
            gs = None
            if g is not None and g['ws'] is not None:
                gs = (g['ws'] + 5 - self.now, g['cnt']) if g['ws'] + 5 > self.now else None
            cs.append((c['item'], rem, gs))
        ms = []
        for name in sorted(self.machs):
            m = self.machs[name]
            ms.append((tuple(sorted((k, v) for k, v in m['store'].items() if v)), m['cache'], m['pick'], m['pickn'],
                       m['on'], m['pp'], m['sp']))
        return (phase, tuple(cs), tuple(ms))


class Sink:
    """下游收货端：过渡期随机停收与恢复；之后按周期 P、相位 φ、收货占比 f 停收与恢复。"""

    def __init__(self, rng, t_trans, P):
        self.toggles = sorted(rnd_frac(rng, 0, t_trans) for _ in range(rng.randrange(0, 7)))
        self.init_open = rng.random() < 0.7
        self.t_trans = t_trans
        self.P = P
        self.always = rng.random() < 0.4
        self.phi = rnd_frac(rng, 0, float(P))
        self.f = F(rng.randrange(1, 10), 10)

    def open(self, t):
        if t < self.t_trans:
            k = sum(1 for x in self.toggles if x <= t)
            return self.init_open ^ (k % 2 == 1)
        if self.always:
            return True
        r = (t - self.phi) % self.P
        return r < self.f * self.P

    def next_toggle(self, t):
        if t < self.t_trans:
            for x in self.toggles:
                if x > t:
                    return x
            return self.t_trans
        if self.always:
            return t + 10 ** 6
        r = (t - self.phi) % self.P
        base = t - r
        for x in (base + self.f * self.P, base + self.P, base + self.P + self.f * self.P):
            if x > t:
                return x
        raise AssertionError


def producers(item):
    return [r for r in RECIPES if r['d'] == 1 and r['prod'] == item]


def gen_case(rng, mode):
    sim = Sim()
    xrec = rng.choice(RECIPES)
    sim.add_mach('X', xrec)
    t_trans = F(rng.randrange(20, 160))
    P = rng.choice([F(1), F(2), F(3, 2), F(5, 2), F(7, 3), F(4), F(5), F(10, 3), F(12), F(20, 7)])
    ys = []          # 起点制造单位：dict(name, budget)
    cnt = [0]

    def newname(p):
        cnt[0] += 1
        return f'{p}{cnt[0]}'

    def add_line(src, item, dst, lim_gate=False):
        L = rng.randint(1, 4)
        names = []
        for j in range(L):
            nm = newname('c')
            gate = None
            if j == 0 and lim_gate:
                gate = dict(allow=item, lim=rng.randint(1, 3), ws=None, cnt=0)
            elif rng.random() < 0.1:
                gate = dict(allow=rng.choice([item, None]), lim=None, ws=None, cnt=0)   # 不设上限的物品准入口
            sim.add_cell(nm, gate)
            names.append(nm)
        sim.connect(src, ('cell', names[0]))
        for a, b in zip(names, names[1:]):
            sim.connect(('cell', a), ('cell', b))
        sim.connect(('cell', names[-1]), dst)
        return names

    def source(item, depth):
        """返回 (src, 起点名或 None)。"""
        prods = producers(item)
        if depth < 2 and prods and rng.random() < 0.65:
            spare = [y for y in ys if y['rec']['prod'] == item and y['budget'] > y['used']]
            if spare and rng.random() < 0.5:
                y = rng.choice(spare)
            else:
                rec = rng.choice(prods)
                name = newname('Y')
                sim.add_mach(name, rec)
                y = dict(name=name, rec=rec, budget=rec['k'], used=0, depth=depth)
                ys.append(y)
                for j, a in rec['ins'].items():
                    for _ in range(a + (1 if rng.random() < 0.3 else 0)):
                        s2, _ = source(j, depth + 1)
                        add_line(s2, j, ('store', name))
            y['used'] += 1
            return ('mach', y['name']), y['name']
        return ('W', item), None

    xlines = []          # (起点名或 None, 格名列表)
    few_item = rng.choice(list(xrec['ins'])) if mode == 'few' else None
    lim_line = None
    for i, a in xrec['ins'].items():
        c = -(-a // xrec['d'])
        if i == few_item:
            c -= 1
        elif rng.random() < 0.3:
            c += 1
        for _ in range(c):
            src, yname = source(i, 0)
            lim = mode == 'lim' and lim_line is None
            names = add_line(src, i, ('store', 'X'), lim_gate=lim)
            if lim:
                lim_line = names
            xlines.append((yname, names))
    if mode == 'extra':
        if not ys:
            return None
        ys[0]['budget'] += 1
    if mode == 'off' and not ys:
        return None
    # 起点的其余取货通道：到下游任意，可经每 5 tick 限量的物品准入口
    sideinfo = {}
    for y in ys:
        firsts = []
        extra_needed = mode == 'extra' and y is ys[0]
        while y['used'] < y['budget'] and (extra_needed or rng.random() < 0.6):
            extra_needed = False
            nm = newname('s')
            gate = None
            if rng.random() < 0.4:
                gate = dict(allow=y['rec']['prod'], lim=rng.randint(1, 5), ws=None, cnt=0)
            sim.add_cell(nm, gate)
            sim.connect(('mach', y['name']), ('cell', nm))
            prev = nm
            for _ in range(rng.randint(0, 2)):
                n2 = newname('s')
                sim.add_cell(n2)
                sim.connect(('cell', prev), ('cell', n2))
                prev = n2
            sk = newname('K')
            sim.sinks[sk] = Sink(rng, t_trans, P)
            sim.connect(('cell', prev), ('sink', sk))
            y['used'] += 1
            firsts.append((nm, gate is None))
        sideinfo[y['name']] = firsts
    # X 的取货通道
    kx = xrec['k']
    nout = rng.randint(1, kx) if rng.random() < 0.8 else kx + 1
    xfirst, xfirst_clean = [], True
    for _ in range(nout):
        nm = newname('o')
        gate = None
        if rng.random() < 0.1:
            gate = dict(allow=xrec['prod'], lim=rng.randint(1, 5), ws=None, cnt=0)
            xfirst_clean = False
        sim.add_cell(nm, gate)
        sim.connect(('mach', 'X'), ('cell', nm))
        prev = nm
        for _ in range(rng.randint(0, 2)):
            n2 = newname('o')
            sim.add_cell(n2)
            sim.connect(('cell', prev), ('cell', n2))
            prev = n2
        sk = newname('K')
        sim.sinks[sk] = Sink(rng, t_trans, P)
        sim.connect(('cell', prev), ('sink', sk))
        xfirst.append(nm)
    info = dict(xrec=xrec, xlines=xlines, ys=ys, sideinfo=sideinfo, xfirst=xfirst,
                mojv=(xrec['d'] == 1 and nout <= kx and xfirst_clean), t_trans=t_trans, P=P, mode=mode)
    return sim, info


def random_start(sim, rng):
    """调试期结束时的任意合法起态：各格只有本线物品，已停留时间、剩余进度的相位任意。"""
    # 每格的本线物品：从通道往前追到来源
    feed = {}
    for src, dst in sim.chans:
        if dst[0] == 'cell':
            feed[dst[1]] = src

    def item_for(cell):
        s = feed[cell]
        if s[0] == 'W':
            return s[1]
        if s[0] == 'cell':
            return item_for(s[1])
        return sim.machs[s[1]]['rec']['prod']
    for name, c in sim.cells.items():
        if rng.random() < 0.6:
            c['item'] = item_for(name)
            c['tin'] = -rnd_frac(rng, 0, 1.2)
    for m in sim.machs.values():
        rec = m['rec']
        for i in rec['ins']:
            if rng.random() < 0.7:
                m['store'][i] = rng.randint(0, CAP)
        if rng.random() < 0.5:
            m['pick'] = rec['prod']
            m['pickn'] = rng.randint(1, CAP)
        r = rng.random()
        if r < 0.3:
            m['cache'] = None
        elif r < 0.5:
            m['cache'] = F(0)
        else:
            m['cache'] = rnd_frac(rng, 0.01, rec['d'])
            if m['cache'] <= 0:
                m['cache'] = F(1, 101)


def run_case(seed, mode):
    rng = random.Random(seed)
    g = None
    while g is None:
        g = gen_case(rng, mode)
    sim, info = g
    random_start(sim, rng)
    sim.offline(rng)
    sim.logging = None
    sim.watch = set()
    t_trans, P = info['t_trans'], info['P']
    off_events = sorted(rnd_frac(rng, 1, float(t_trans)) for _ in range(rng.randint(0, 2)))
    t_off = rnd_frac(rng, 2, float(t_trans)) if mode == 'off' else None
    y_off = info['ys'][0]['name'] if mode == 'off' else None
    sim.closure()
    seen = {}
    limit = t_trans + 4000
    period = None
    while sim.now < limit:
        extra = [t for t in off_events if t > sim.now] + [t_trans]
        if sim.now >= t_trans:
            extra.append(t_trans + (math.floor((sim.now - t_trans) / P) + 1) * P)   # 每周期采一次样，静止态也能认出循环
        if t_off is not None and t_off > sim.now:
            extra.append(t_off)
        t = sim.next_event([x for x in extra if x > sim.now] or [sim.now + 10 ** 6])
        sim.advance_to(t)
        if t in off_events:
            sim.offline(rng)
        if t_off is not None and t == t_off:
            sim.machs[y_off]['on'] = False
        sim.closure()
        if sim.now >= t_trans:
            sig = sim.signature((sim.now - t_trans) % P)
            if sig in seen:
                period = sim.now - seen[sig]
                break
            seen[sig] = sim.now
    if period is None:
        return dict(seed=seed, mode=mode, cycle=False)
    # 再走两个周期，逐事件记录
    t0 = sim.now
    watch = set(info['xfirst'])
    for y in info['ys']:
        watch |= {nm for nm, _ in info['sideinfo'][y['name']]}
    for _, names in info['xlines']:
        watch.add(names[0])
    sim.watch = watch
    sim.logging = []
    snaps = []   # (时刻, 闭合后状态摘要)

    def snap():
        snaps.append((sim.now,
                      {n: m['cache'] is not None for n, m in sim.machs.items()},
                      {n: m['on'] for n, m in sim.machs.items()},
                      {n: c['item'] is not None for n, c in sim.cells.items()},
                      max(sim.machs['X']['store'].values(), default=0)))
    snap()
    while sim.now < t0 + 2 * period:
        t = sim.next_event([sim.now + 10 ** 6])
        sim.advance_to(t)
        sim.closure()
        snap()
    ev_log = sim.logging
    # ---- 核 ----
    res = dict(seed=seed, mode=mode, cycle=True, period=str(period), X=f"{info['xrec']['mach']}:{info['xrec']['prod']}",
               d=info['xrec']['d'], n_Y=len(info['ys']))
    phases = {t % 1 for t, *_ in snaps}
    res['phases'] = len(phases)
    ok_y = {}
    for y in info['ys']:
        n = y['name']
        ok_y[n] = all(c[n] for _, c, _, _, _ in snaps) and all(o[n] for _, _, o, _, _ in snaps)
    if mode == 'off':
        ok_y_cache = {y['name']: all(c[y['name']] for _, c, _, _, _ in snaps) for y in info['ys']}
        res['off_premise_cache_only'] = all(ok_y_cache.values())
    premise = all(ok_y.values())
    res['premise'] = premise
    res['x_empty'] = sum(1 for _, c, _, _, _ in snaps if not c['X'])
    good_lines = [names for yname, names in info['xlines'] if yname is None or ok_y.get(yname)]
    res['line_empty'] = sum(1 for *_, cells, _ in snaps for names in good_lines for nm in names if not cells[nm])
    yf = []
    for y in info['ys']:
        if ok_y[y['name']]:
            yf += [names[0] for yname, names in info['xlines'] if yname == y['name']]
            yf += [nm for nm, clean in info['sideinfo'][y['name']] if clean]   # 经限量物品准入口的首格不在引理乙的范围
    res['yfirst_empty'] = sum(1 for *_, cells, _ in snaps for nm in yf if not cells[nm])
    res['max_input'] = max(x for *_, x in snaps)
    # 末句：X 的首格
    res['mojv'] = info['mojv'] and premise and mode == 'normal'
    windows = viol_w = 0
    if res['mojv']:
        res['xfirst_empty'] = sum(1 for *_, cells, _ in snaps for nm in info['xfirst'] if not cells[nm])
        t_end = t0 + 2 * period
        for _ in range(8):
            theta = t0 + rnd_frac(rng, 0, float(period))
            n = 0
            while theta + n + 1 <= t_end:
                a, b = theta + n, theta + n + 1
                for nm in info['xfirst']:
                    ins = sum(1 for t, k, c in ev_log if c == nm and k == 'in' and a <= t < b)
                    ready = any(c == nm and k == 'left' and a <= t < b for t, k, c in ev_log)
                    windows += 1
                    if ins > 1 or (ready and ins != 1) or (not ready and ins != 0):
                        viol_w += 1
                n += 1
    else:
        res['xfirst_empty'] = None
    res['windows'] = windows
    res['window_viol'] = viol_w
    return res


def main():
    seed0, n = int(sys.argv[1]), int(sys.argv[2])
    mode = sys.argv[3] if len(sys.argv) > 3 else 'normal'
    out = []
    for s in range(seed0, seed0 + n):
        out.append(run_case(s, mode))
    cyc = [r for r in out if r['cycle']]
    prem = [r for r in cyc if r['premise']]
    summ = dict(
        mode=mode, seed0=seed0, runs=n, cycles=len(cyc), premise_cycles=len(prem),
        multi_phase=sum(1 for r in prem if r['phases'] > 1),
        five_tick=sum(1 for r in prem if r['d'] == 5),
        with_Y=sum(1 for r in prem if r['n_Y'] > 0),
        input_full=sum(1 for r in prem if r['max_input'] >= CAP),
        x_empty_cycles=sum(1 for r in prem if r['x_empty'] > 0),
        line_empty_cycles=sum(1 for r in prem if r['line_empty'] > 0),
        yfirst_empty_cycles=sum(1 for r in prem if r['yfirst_empty'] > 0),
        mojv_cycles=sum(1 for r in prem if r['mojv']),
        xfirst_empty_cycles=sum(1 for r in prem if r['mojv'] and r['xfirst_empty']),
        windows=sum(r['windows'] for r in prem), window_viol=sum(r['window_viol'] for r in prem),
    )
    if mode != 'normal':
        # 对照组：前提（按条文）不成立的循环里 X 空手的有多少
        np_ = [r for r in cyc if not r['premise'] or mode in ('few', 'lim')]
        summ['control_cycles'] = len(np_)
        summ['control_x_empty'] = sum(1 for r in np_ if r['x_empty'] > 0)
        if mode == 'off':
            summ['off_cache_nonempty_cycles'] = sum(1 for r in cyc if r.get('off_premise_cache_only'))
            summ['off_cache_nonempty_x_empty'] = sum(1 for r in cyc if r.get('off_premise_cache_only') and r['x_empty'] > 0)
        if mode == 'extra':
            summ['extra_cache_nonempty_x_or_line_empty'] = sum(
                1 for r in cyc if r['premise'] and (r['x_empty'] or r['line_empty'] or r['yfirst_empty']))
    bad = [r for r in prem if mode == 'normal' and (r['x_empty'] or r['line_empty'] or r['yfirst_empty']
                                                    or (r['mojv'] and (r['xfirst_empty'] or r['window_viol'])))]
    summ['violating_seeds'] = [r['seed'] for r in bad][:20]
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == '__main__':
    main()
