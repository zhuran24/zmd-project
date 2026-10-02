#!/usr/bin/env python3
"""编码甲：按现行规则（第 23-33 行）自写的步进模拟器，只用标准库。

不导入 sim2。只覆盖本报告引理的前提所允许的单位：
  非运输单位：src（仓库取货口/协议核心取货端口，设一种或按序几种物品，货源不断）、
             mach（制造单位，1 或 2 个存货物品格，取货物品格、缓存格、配方）、
             sink（协议核心收货侧，按给定的开合表收货）。
  元件：belt（一段连续传送带，L 格）、gate（物品准入口，可设放行种类、每 5 tick 上限）、
        baxis（桥接器的一轴）、merger（汇流器）。
没有分流器、协议储存箱。每个运输物品格至多一条送货通道（规则推出：传送带、准入口、汇流器只有一条取货边；
桥接器一轴只在不与另一桥接器相邻时成立，由网络生成器保证）。

一步：结束到时的制造 -> 逐个判定（元件按层数，再非运输单位）-> 开始能开始的制造。
时间以步计，1 tick = 8 步。
"""
from __future__ import annotations

import random

TICK = 8


class Net:
    """静态结构：单位与通道。channels: list of (src, dst, rank)。rank 小的先接通。"""

    def __init__(self, units, channels, strict=True):
        self.units = units                  # id -> dict(type=..., ...)
        self.channels = sorted(channels, key=lambda c: c[2])
        self.out = {u: [] for u in units}
        self.inp = {u: [] for u in units}
        for c in self.channels:
            self.out[c[0]].append(c)
            self.inp[c[1]].append(c)
        self.elements = [u for u, d in units.items() if d['type'] in ('belt', 'gate', 'baxis', 'merger')]
        self.nontransport = [u for u, d in units.items() if d['type'] in ('src', 'mach', 'sink')]
        for e in self.elements:
            assert len(self.out[e]) <= 1, ('前提：元件至多一条送货通道', e)
            nt_in = [c for c in self.inp[e] if units[c[0]]['type'] in ('src', 'mach', 'sink')]
            assert len(nt_in) <= 1 or not strict, ('前提：至多一个非运输单位往它送货', e)
            if units[e]['type'] != 'merger':
                assert len(self.inp[e]) <= 1, e
            else:
                assert len(self.inp[e]) <= 3, e
        self.layer = self._layers()

    def is_element(self, u):
        return u in self.layer or self.units[u]['type'] in ('belt', 'gate', 'baxis', 'merger')

    def _layers(self):
        # 规则第 28 行：送往的单位里若有还往下送货的元件，层数比它大 1，否则为 1。
        lay, visiting = {}, set()

        def visit(e):
            if e in lay:
                return lay[e]
            assert e not in visiting, ('前提：没有只由运输单位组成的环', e)
            visiting.add(e)
            nxt = [c[1] for c in self.out[e]
                   if self.units[c[1]]['type'] in ('belt', 'gate', 'baxis', 'merger') and self.out[c[1]]]
            lay[e] = visit(nxt[0]) + 1 if nxt else 1
            visiting.discard(e)
            return lay[e]

        for e in self.elements:
            visit(e)
        return lay


class Item:
    __slots__ = ('kind', 'entered', 'prev')

    def __init__(self, kind, entered=-100, prev=None):
        self.kind, self.entered, self.prev = kind, entered, prev


class Sim:
    def __init__(self, net: Net, init: dict, order_seed=None, order=None):
        self.net, self.t = net, 0
        U = net.units
        self.cells = {}       # 元件 -> list of Item|None（下标 0 是收货端，末尾是送货端）
        self.gate = {}        # gate -> [window_start, count]
        self.slots = {}       # mach -> list of [kind|None, count]
        self.outslot = {}     # mach -> [kind|None, count]
        self.cache = {}       # mach -> (kind, qty) | None
        self.run = {}         # mach -> [recipe_index, remaining] | None
        self.src_seq = {}     # src -> index
        self.cursor = {}      # 收货侧轮询：unit -> 下一个先试的下标（按接通先后排的数组）
        self.last = {}        # 非运输单位送货：channel -> 上次成功的步（从未成功为 -1）
        self.sink_got = {}
        self.chan_count = {}
        self.stat = dict(moves=0, groups_multi_ready=0, groups_contended=0, nt_sends=0, nt_skipped_full=0, starts=0)
        for u, d in U.items():
            ty = d['type']
            if ty == 'belt':
                self.cells[u] = [None] * d['length']
            elif ty in ('gate', 'baxis', 'merger'):
                self.cells[u] = [None]
            if ty == 'gate':
                self.gate[u] = [None, 0]
            if ty == 'mach':
                self.slots[u] = [[None, 0] for _ in range(d['nslots'])]
                self.outslot[u] = [None, 0]
                self.cache[u] = None
                self.run[u] = None
            if ty == 'src':
                self.src_seq[u] = 0
            if ty == 'sink':
                self.sink_got[u] = []
            # 汇流器第一次从第二条接通的通道开始（规则第 32 行）；其余从第一条
            self.cursor[u] = 1 if (ty == 'merger' and len(net.inp[u]) > 1) else 0
        for c in net.channels:
            self.last[c] = -1
        # 初态
        for u, lst in init.get('cells', {}).items():
            for j, it in enumerate(lst):
                if it is not None:
                    self.cells[u][j] = Item(it[0], it[1], None)
        for u, lst in init.get('slots', {}).items():
            for j, (k, n) in enumerate(lst):
                self.slots[u][j] = [k, n]
        for u, (k, n) in init.get('outslot', {}).items():
            self.outslot[u] = [k, n]
        for u, v in init.get('cache', {}).items():
            self.cache[u] = tuple(v) if v else None
        for u, v in init.get('run', {}).items():
            self.run[u] = list(v) if v else None
        for u, v in init.get('cursor', {}).items():
            self.cursor[u] = v
        for u, v in init.get('gate', {}).items():
            self.gate[u] = list(v)
        # 判定先后：同层元件之间、非运输单位之间的次序（可任意给）
        rng = random.Random(order_seed)
        if order is None:
            layers = sorted(set(net.layer.values()))
            order = []
            for L in layers:
                grp = [e for e in net.elements if net.layer[e] == L]
                rng.shuffle(grp)
                order += grp
            nts = list(net.nontransport)
            rng.shuffle(nts)
            order += nts
        self.order = order
        lays = [net.layer[e] for e in order if e in net.layer]
        assert lays == sorted(lays)

    # ---------- 物品格操作 ----------
    def settle(self, e):
        cs = self.cells[e]
        for j in range(len(cs) - 2, -1, -1):
            it = cs[j]
            if it is not None and cs[j + 1] is None and self.t - it.entered >= TICK:
                it.entered, it.prev = self.t, (e, j)       # 刚离开的单位：第 j 格
                cs[j + 1], cs[j] = it, None

    def accepts(self, u, kind):
        d = self.net.units[u]
        ty = d['type']
        if ty in ('belt', 'baxis', 'merger'):
            return self.cells[u][0] is None
        if ty == 'gate':
            if self.cells[u][0] is not None:
                return False
            if d.get('allow') is not None and d['allow'] != kind:
                return False
            k = d.get('quota')
            if k is not None:
                ws, cnt = self.gate[u]
                if ws is not None and self.t < ws + 5 * TICK and cnt >= k:
                    return False
            return True
        if ty == 'mach':
            same = [s for s in self.slots[u] if s[0] == kind]
            if same:
                return same[0][1] < 50
            return any(s[0] is None for s in self.slots[u])
        if ty == 'sink':
            return d['open'](self.t)
        return False

    def receive(self, u, item, src):
        ty = self.net.units[u]['type']
        if ty in ('belt', 'gate', 'baxis', 'merger'):
            item.entered, item.prev = self.t, src
            self.cells[u][0] = item
            if ty == 'gate' and self.net.units[u].get('quota') is not None:
                ws, cnt = self.gate[u]
                if ws is None or self.t >= ws + 5 * TICK:
                    self.gate[u] = [self.t, 1]
                else:
                    self.gate[u] = [ws, cnt + 1]
        elif ty == 'mach':
            same = [s for s in self.slots[u] if s[0] == item.kind]
            s = same[0] if same else next(s for s in self.slots[u] if s[0] is None)
            s[0] = item.kind
            s[1] += 1
        elif ty == 'sink':
            self.sink_got[u].append((self.t, item.kind))

    def head_item(self, u, c=None):
        ty = self.net.units[u]['type']
        if ty in ('belt', 'gate', 'baxis', 'merger'):
            it = self.cells[u][-1]
            if it is not None and self.t - it.entered >= TICK:
                return it
            return None
        if ty == 'mach':
            k, n = self.outslot[u]
            return Item(k, None, u) if n > 0 else None
        if ty == 'src':
            pk = self.net.units[u].get('port_kinds')
            if pk is not None:          # 协议核心的几个取货端口：每个端口各连仓库的某一物品格
                return Item(pk[c[1]], None, u) if c is not None else Item(None, None, u)
            ks = self.net.units[u]['kinds']
            return Item(ks[self.src_seq[u] % len(ks)], None, u)
        return None

    def pop(self, u):
        ty = self.net.units[u]['type']
        if ty in ('belt', 'gate', 'baxis', 'merger'):
            self.cells[u][-1] = None
            if ty == 'belt':
                self.settle(u)
        elif ty == 'mach':
            o = self.outslot[u]
            o[1] -= 1
            if o[1] == 0:
                o[0] = None
            self.flush(u)
        elif ty == 'src':
            self.src_seq[u] += 1

    def flush(self, m):
        c = self.cache[m]
        if c is None:
            return
        o = self.outslot[m]
        if (o[0] is None or o[0] == c[0]) and o[1] + c[1] <= 50:
            o[0] = c[0]
            o[1] += c[1]
            self.cache[m] = None

    # ---------- 一步 ----------
    def step(self):
        net, t = self.net, self.t
        U = net.units
        # 一、结束到时的制造
        for m in self.slots:
            r = self.run[m]
            if r is not None:
                r[1] -= 1
                if r[1] == 0:
                    rec = U[m]['recipes'][r[0]]
                    assert self.cache[m] is None
                    self.cache[m] = (rec['out'], rec['qty'])
                    self.run[m] = None
            self.flush(m)
        for e in net.elements:
            if U[e]['type'] == 'belt':
                self.settle(e)
        # 二、逐个判定
        judged = set()
        for u in self.order:
            if u in judged:
                continue
            if u in net.layer:              # 元件
                outs = net.out[u]
                if not outs:
                    judged.add(u)
                    continue
                dst = outs[0][1]
                arr = net.inp[dst]          # 按接通先后排好
                n = len(arr)
                cur = self.cursor[dst] % n
                ordered = arr[cur:] + arr[:cur]
                group = [c for c in ordered if c[0] in net.layer]   # 非分流器元件上游，一起判定
                for c in group:
                    assert c[0] not in judged, ('同组成员应同层', c)
                    judged.add(c[0])
                ready = [c for c in group if self.head_item(c[0]) is not None]
                if len(ready) >= 2:
                    self.stat['groups_multi_ready'] += 1
                got = 0
                for c in group:
                    it = self.head_item(c[0])
                    if it is None or it.prev == self.entry_id(dst) or not self.accepts(dst, it.kind):
                        continue
                    got += 1
                    self.stat['moves'] += 1
                    self.pop(c[0])
                    self.receive(dst, it, (c[0], len(self.cells[c[0]]) - 1))
                    self.cursor[dst] = (arr.index(c) + 1) % n
                if len(ready) >= 2 and 0 < got < len(ready):
                    self.stat['groups_contended'] += 1
            else:                            # 非运输单位
                judged.add(u)
                if U[u]['type'] == 'sink':
                    continue
                for c in self.out_order(u):
                    it = self.head_item(u, c)
                    if it is None:
                        break
                    if not self.accepts(c[1], it.kind):
                        self.stat['nt_skipped_full'] += 1
                        continue
                    self.stat['nt_sends'] += 1
                    self.pop(u)
                    self.receive(c[1], it, u)
                    self.last[c] = t
                    self.chan_count[(c[0], c[1])] = self.chan_count.get((c[0], c[1]), 0) + 1
                    arr = net.inp[c[1]]
                    self.cursor[c[1]] = (arr.index(c) + 1) % len(arr)
                    break
        # 三、开始能开始的制造
        for m in self.slots:
            if self.run[m] is not None or self.cache[m] is not None:
                continue
            for ri, rec in enumerate(U[m]['recipes']):
                have = {s[0]: s for s in self.slots[m] if s[0] is not None}
                if all(k in have and have[k][1] >= n for k, n in rec['in']):
                    for k, n in rec['in']:
                        s = have[k]
                        s[1] -= n
                        if s[1] == 0:
                            s[0] = None
                    self.run[m] = [ri, rec['dur']]
                    self.stat['starts'] += 1
                    break
        self.t += 1

    def entry_id(self, u):
        """物品进入单位 u 时进的那个物理单位：元件是它的第 0 格，非运输单位是它自己。"""
        return (u, 0) if u in self.cells else u

    def out_order(self, u):
        """非运输单位取货侧：取货优先级分级（第 33 行），级内先试上次成功最早的、从未成功的按接通先后（第 32 行）。"""
        net = self.net
        arr = net.out[u]
        if not arr:
            return []
        mer = [c for c in arr if net.units[c[1]]['type'] == 'merger']
        rest = [c for c in arr if net.units[c[1]]['type'] != 'merger']
        grades = [[c] for c in mer] + ([rest] if rest else [])

        def glayer(g):
            return max(net.layer.get(c[1], 1) for c in g)

        grades.sort(key=lambda g: (glayer(g), min(c[2] for c in g)))
        res = []
        for g in grades:
            res += sorted(g, key=lambda c: (self.last[c], c[2]))
        return res

    def snapshot(self):
        cells = tuple((e, tuple(None if i is None else (i.kind, i.entered, i.prev) for i in self.cells[e]))
                      for e in sorted(self.cells))
        return (self.t, cells,
                tuple(sorted((m, tuple(tuple(s) for s in self.slots[m])) for m in self.slots)),
                tuple(sorted((m, tuple(self.outslot[m])) for m in self.outslot)),
                tuple(sorted((m, self.cache[m]) for m in self.cache)),
                tuple(sorted((m, None if self.run[m] is None else tuple(self.run[m])) for m in self.run)),
                tuple(sorted(self.src_seq.items())),
                tuple(sorted(self.cursor.items())),
                tuple(sorted(((c[0], c[1], c[2]), v) for c, v in self.last.items())),
                tuple(sorted((g, tuple(v)) for g, v in self.gate.items())),
                tuple(sorted((s, len(v)) for s, v in self.sink_got.items())))
