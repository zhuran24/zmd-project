#!/usr/bin/env python3
"""复核94C 自写步进模拟器（不导入 sim2 与推导92C 的任何脚本）。

只覆盖本复核要跑的构型：进路是单入单出的链，由若干元件首尾相接；
元件是一段连续传送带（多格）或单格元件（物品准入口不设上限、或桥接器一轴，
后者按“每轴单独收货”的读法；本文件的实验不放桥接器）。
每步：1 结束到时的制造（成品进缓存，能进取货格就整批进）；
      2 元件按层数从小到大、同层按 rank 判定，再判定非运输单位（按 rank）；
      3 开始能开始的制造。
滞留：物品进入运输格的步号 e，到 e+8 步起才能离开。
元件内部前移在“一直尝试移动”下随时发生：每步开头和该元件任一格变动后立刻补。
机器取货侧：先试从未成功的（按接通 rank），再按上次成功从早到晚；每次判定至多送一件。
机器存货侧多条进路：其末元件同属收货组，在组内最先判定者的轮次一起判定，
按接通 rank 循环、从上次成功的下一条开始（规则第 31、32 行）。
"""
from __future__ import annotations
import random

RET = 8  # 滞留步数


class Element:
    def __init__(self, name, ncells, rank=0):
        self.name = name
        self.cells = [None] * ncells  # 每格 None 或 [kind, entered]
        self.rank = rank
        self.dst = None      # 下游：Element 或 Machine 或 Sink
        self.src = None
        self.layer = None

    def settle(self, t):
        # 内部前移：从后往前，成熟且后格空就挪
        changed = True
        while changed:
            changed = False
            for j in range(len(self.cells) - 2, -1, -1):
                it = self.cells[j]
                if it is not None and self.cells[j + 1] is None and t - it[1] >= RET:
                    self.cells[j + 1] = [it[0], t]
                    self.cells[j] = None
                    changed = True

    def head_ready(self, t):
        it = self.cells[-1]
        return it if (it is not None and t - it[1] >= RET) else None

    def first_empty(self):
        return self.cells[0] is None

    def put_first(self, kind, t):
        assert self.cells[0] is None
        self.cells[0] = [kind, t]

    def count(self, kind=None):
        return sum(1 for c in self.cells if c is not None and (kind is None or c[0] == kind))


class Sink:
    """非运输终点：pattern(t)->bool 决定该步能否收。"""
    def __init__(self, name, pattern=None):
        self.name = name
        self.pattern = pattern or (lambda t: True)
        self.got = []
        self.in_routes = []

    def can_accept(self, kind, t):
        return self.pattern(t)

    def accept(self, kind, t):
        self.got.append((t, kind))


class Machine:
    def __init__(self, name, recipes, ncells_in=1, rank=0, on=True):
        # recipes: list of (materials dict, product, qty, duration_steps)
        self.name = name
        self.recipes = recipes
        self.nin = ncells_in
        self.inp = []          # list of [kind, count]
        self.out = None        # [kind, count] or None
        self.cache = None      # ('run', rem, product, qty) | ('done', product, qty)
        self.rank = rank
        self.on = on
        self.out_routes = []   # 首元件列表，按接通 rank 排
        self.out_rank = {}
        self.last_succ = {}    # 首元件 -> 步号；不在表中=从未成功
        self.in_routes = []    # 末元件列表
        self.in_rank = {}
        self.in_cursor = None  # 上次成功的收货 rank 序号
        self.starts = []
        self.sent = []

    # ---- 物品格 ----
    def in_count(self, kind):
        for c in self.inp:
            if c[0] == kind:
                return c[1]
        return 0

    def can_accept(self, kind, t):
        if self.out is not None and self.out[0] == kind and self.out[1] > 0:
            return False  # 同种唯一（规则 13）
        for c in self.inp:
            if c[0] == kind:
                return c[1] < 50
        return len(self.inp) < self.nin

    def accept(self, kind, t):
        for c in self.inp:
            if c[0] == kind:
                c[1] += 1
                return
        self.inp.append([kind, 1])

    def flush(self):
        if self.cache is None or self.cache[0] != 'done':
            return False
        _, p, q = self.cache
        if any(c[0] == p for c in self.inp):
            return False  # 同种唯一
        if self.out is None or self.out[1] == 0:
            self.out = [p, q]
        elif self.out[0] == p and self.out[1] + q <= 50:
            self.out[1] += q
        else:
            return False
        self.cache = None
        return True

    def complete(self):
        if self.cache is not None and self.cache[0] == 'run' and self.on:
            _, rem, p, q = self.cache
            rem -= 1
            if rem == 0:
                self.cache = ('done', p, q)
            else:
                self.cache = ('run', rem, p, q)
        self.flush()

    def try_start(self, t):
        if not self.on or self.cache is not None:
            return False
        for mats, p, q, dur in self.recipes:
            if all(self.in_count(k) >= n for k, n in mats.items()):
                for k, n in mats.items():
                    for c in self.inp:
                        if c[0] == k:
                            c[1] -= n
                self.inp = [c for c in self.inp if c[1] > 0]
                self.cache = ('run', dur, p, q)
                self.starts.append(t)
                return True
        return False

    def out_order(self):
        never = [e for e in self.out_routes if e not in self.last_succ]
        never.sort(key=lambda e: self.out_rank[e])
        done = [e for e in self.out_routes if e in self.last_succ]
        done.sort(key=lambda e: (self.last_succ[e], self.out_rank[e]))
        return never + done

    def judge(self, t):
        if self.out is None or self.out[1] == 0:
            return None
        for e in self.out_order():
            if e.first_empty():
                kind = self.out[0]
                e.put_first(kind, t)
                self.out[1] -= 1
                if self.out[1] == 0:
                    self.out = None
                self.last_succ[e] = t
                self.sent.append((t, e.name))
                self.flush()
                return e
        return None

    def cache_nonempty(self):
        return self.cache is not None


class Source:
    """无限供货的非运输单位（仓库取货口一类），单出口。"""
    def __init__(self, name, kind, rank=0, pattern=None):
        self.name = name
        self.kind = kind
        self.rank = rank
        self.out_routes = []
        self.out_rank = {}
        self.pattern = pattern or (lambda t: True)
        self.sent = []

    def judge(self, t):
        if not self.pattern(t):
            return None
        for e in sorted(self.out_routes, key=lambda e: self.out_rank[e]):
            if e.first_empty():
                e.put_first(self.kind, t)
                self.sent.append(t)
                return e
        return None


class World:
    def __init__(self):
        self.elements = []
        self.nts = []   # 非运输单位（机器、源），判定按 rank
        self.t = 0

    def chain(self, src, dst, lengths, ranks=None, out_rank=0, in_rank=0, name='r'):
        """src -> 元件链 -> dst。lengths 是各元件格数（多格=连续传送带）。"""
        els = []
        for i, L in enumerate(lengths):
            e = Element(f'{name}.{i}', L, rank=(ranks[i] if ranks else 0))
            els.append(e)
        for a, b in zip(els, els[1:]):
            a.dst = b
            b.src = a
        els[-1].dst = dst
        els[0].src = src
        src.out_routes.append(els[0])
        src.out_rank[els[0]] = out_rank
        if isinstance(dst, Machine):
            dst.in_routes.append(els[-1])
            dst.in_rank[els[-1]] = in_rank
        elif isinstance(dst, Sink):
            dst.in_routes.append(els[-1])
        self.elements.extend(els)
        return els

    def finalize(self):
        # 层数：送往非元件=1；否则下游层数+1（链，无分叉）
        for e in self.elements:
            L, x = 1, e
            while isinstance(x.dst, Element):
                L += 1
                x = x.dst
            e.layer = L
        self.el_order = sorted(self.elements, key=lambda e: (e.layer, e.rank))
        self.nt_order = sorted(self.nts, key=lambda u: u.rank)
        self.machines = [u for u in self.nts if isinstance(u, Machine)]

    def deliver(self, e, t):
        """元件 e 判定：把末格成熟物品送往下游。成功返回 True。"""
        it = e.head_ready(t)
        if it is None:
            return False
        d = e.dst
        if isinstance(d, Element):
            if not d.first_empty():
                return False
            d.put_first(it[0], t)
            e.cells[-1] = None
            e.settle(t)
            return True
        if d.can_accept(it[0], t):
            d.accept(it[0], t)
            e.cells[-1] = None
            e.settle(t)
            if isinstance(d, Machine):
                d.in_cursor = d.in_rank[e]
            return True
        return False

    def step(self):
        t = self.t
        for m in self.machines:
            m.complete()
        for e in self.elements:
            e.settle(t)
        judged = set()
        for e in self.el_order:
            if e in judged:
                continue
            d = e.dst
            if isinstance(d, Machine) and len(d.in_routes) > 1:
                # 收货组：机器的全部末元件一起判定，按存货侧轮询顺序
                grp = sorted(d.in_routes, key=lambda x: d.in_rank[x])
                ranks = [d.in_rank[x] for x in grp]
                if d.in_cursor is None:
                    start = 0
                else:
                    pos = ranks.index(d.in_cursor)
                    start = (pos + 1) % len(grp)
                grp = grp[start:] + grp[:start]
                for x in grp:
                    judged.add(x)
                    self.deliver(x, t)
            else:
                judged.add(e)
                self.deliver(e, t)
        for u in self.nt_order:
            u.judge(t)
        for m in self.machines:
            m.try_start(t)
        self.t += 1


def seeds_rng(seed):
    return random.Random(seed)
