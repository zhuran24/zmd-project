#!/usr/bin/env python3
"""采种单元构型生成与 D 组两条修订候选（150 下界、满库存不断料）的随机核对。"""
from __future__ import annotations
import random
from engine import (Belt, Cell, Machine, Sink, Source, World, Item, link, STEP_RES)

SEED, PLANT, POWDER = 'seed', 'plant', 'powder'


def build_path(name, src, dst, segs, cross_after=None):
    """segs: [('belt', L) | ('br', m)]，桥接器链 m≥1 个同轴相邻。返回 (元件表, 格位表)。
    格位表每项 (元件, 格号, 正向来路单位名)。"""
    els, slots = [], []
    prev_el = None
    for si, (kind, x) in enumerate(segs):
        if kind == 'belt':
            e = Belt(f'{name}.b{si}', x)
            els.append(e)
            if prev_el is None:
                link(src, e)
            else:
                link(prev_el, e)
            prev_el = e
        else:
            chain = []
            for j in range(x):
                e = Cell(f'{name}.r{si}_{j}.h', unit=f'{name}.r{si}_{j}')
                els.append(e)
                if prev_el is None:
                    link(src, e)
                else:
                    link(prev_el, e)
                if chain:  # 同轴相邻桥：反向通道
                    link(e, chain[-1]).back = True
                chain.append(e)
                prev_el = e
    link(prev_el, dst)
    # 正向来路
    prev_unit = src.out_unit()
    for e in els:
        if isinstance(e, Belt):
            for j in range(len(e.cells)):
                slots.append((e, j, prev_unit if j == 0 else f'{e.name}#{j-1}'))
            prev_unit = e.out_unit()
        else:
            slots.append((e, 0, prev_unit))
            prev_unit = e.out_unit()
    return els, slots


def put(e, j, item):
    if isinstance(e, Belt):
        e.cells[j] = item
    else:
        e.item = item


def get(e, j):
    return e.cells[j] if isinstance(e, Belt) else e.item


def rand_segs(rng, maxlen=6, allow_bridges=True, max_br=3):
    segs = []
    nseg = rng.randint(1, 4)
    kind = rng.choice(['belt', 'br']) if allow_bridges else 'belt'
    for _ in range(nseg):
        if kind == 'belt':
            segs.append(('belt', rng.randint(1, maxlen)))
        else:
            segs.append(('br', rng.randint(1, max_br)))
        if not allow_bridges:
            break
        kind = 'br' if kind == 'belt' else 'belt'
    return segs


class Unit:
    def __init__(self, rng, k=2, n_out=None, segs=None, allow_bridges=True,
                 cross=False, bridge_unit_reading=False, kout_bridge_cross=False):
        self.rng = rng
        self.k = k
        C = Machine('C', ({PLANT: 1}, SEED, 2, 8))
        A = Machine('A', ({SEED: 1}, PLANT, 1, 8))
        B = Machine('B', ({SEED: 1}, PLANT, 1, 8))
        K = Machine('K', ({PLANT: 1}, POWDER, k, 8))
        self.C, self.A, self.B, self.K = C, A, B, K
        nodes = [C, A, B, K]
        segs = segs or {p: rand_segs(rng, allow_bridges=allow_bridges) for p in ('CA', 'AC', 'CB', 'BK')}
        self.segs = segs
        self.paths = {}
        ends = {'CA': (C, A), 'AC': (A, C), 'CB': (C, B), 'BK': (B, K)}
        for p, (s, d) in ends.items():
            els, slots = build_path(p, s, d, segs[p])
            self.paths[p] = (els, slots)
            nodes += els
        # 交叉桥（另一轴有通道）：在 BK 第一个桥接器的另一轴上放一条通往堵死出口的路 Z
        self.cross_nodes = []
        if cross:
            br = [e for e in self.paths['BK'][0] if isinstance(e, Cell)]
            assert br, 'cross needs a bridge on BK'
            X = br[0]
            Zs = Source('Zs', 'z')
            Zin = Belt('Z.in', 1)
            Xv = Cell(X.unit + '.v', unit=X.unit)
            Zout = Belt('Z.out', 1)
            Zk = Sink('Zk')
            Zk.open = False
            link(Zs, Zin)
            link(Zin, Xv)
            link(Xv, Zout)
            link(Zout, Zk)
            self.cross_nodes = [Zs, Zin, Xv, Zout, Zk]
            nodes += self.cross_nodes
            self.Zk = Zk
        # K 的出口
        if n_out is None:
            n_out = rng.randint(0, k)
        self.kout = []
        self.sinks = []
        for i in range(n_out):
            sk = Sink(f'sink{i}')
            if rng.random() < 0.5:
                e = Belt(f'KO{i}', rng.randint(1, 3))
                link(K, e)
                link(e, sk)
                nodes += [e, sk]
            else:
                e = Cell(f'KO{i}.h', unit=f'KO{i}')
                link(K, e)
                link(e, sk)
                nodes += [e, sk]
                if kout_bridge_cross:
                    # 另一轴有通道：一条外来路穿过该桥另一轴
                    zs = Source(f'KZs{i}', 'z')
                    zi = Belt(f'KZ{i}.in', 1)
                    xv = Cell(f'KO{i}.v', unit=f'KO{i}')
                    zo = Belt(f'KZ{i}.out', 1)
                    zk = Sink(f'KZk{i}')
                    zk.open = rng.random() < 0.5
                    link(zs, zi); link(zi, xv); link(xv, zo); link(zo, zk)
                    nodes += [zs, zi, xv, zo, zk]
            self.kout.append(e)
            self.sinks.append(sk)
        self.nodes = nodes
        self.w = World(nodes, rng, bridge_unit_reading=bridge_unit_reading)
        self.L1 = len(self.paths['CA'][1])
        self.L2 = len(self.paths['AC'][1])

    # ---- 状态 ----
    def path_count(self, p):
        return sum(1 for (e, j, _) in self.paths[p][1] if get(e, j) is not None)

    def phi2(self):
        C, A = self.C, self.A
        return (2 * (self.path_count('CA') + A.inv(SEED) + A.out_n + self.path_count('AC')
                     + C.inv(PLANT) + (1 if A.cache_nonempty() else 0)
                     + (1 if C.cache_nonempty() else 0)) + C.out_n)

    def fill_path(self, p, kind, prob, age_lo=-15):
        for (e, j, pu) in self.paths[p][1]:
            if self.rng.random() < prob:
                put(e, j, Item(kind, self.rng.randint(age_lo, 0), pu))
            else:
                put(e, j, None)

    def rand_machine(self, m, inkind, outkind, full=False):
        rng = self.rng
        if full:
            m.slots[0] = [inkind, 50]
            m.out_kind, m.out_n = outkind, 50
            m.cache = ('run', rng.randint(1, 8)) if rng.random() < 0.7 else ('done',)
            return
        n = rng.choice([0, 0, 1, 2, rng.randint(0, 50), 49, 50])
        m.slots[0] = [inkind if n else None, n]
        o = rng.choice([0, 0, 1, rng.randint(0, 50), 48, 49, 50])
        m.out_kind, m.out_n = (outkind if o else None), o
        r = rng.random()
        m.cache = None if r < 0.35 else (('run', rng.randint(1, 8)) if r < 0.75 else ('done',))

    def first_cell(self, e):
        return e.cells[0] if isinstance(e, Belt) else e.item
