#!/usr/bin/env python3
"""会议 3 seat-opus-1：压 U 侧「粗网格流量」放松在 70×70 上的割循环实测。

主问题（CP-SAT，只放整数）：按 seat-opus-2 aggflow.py 的 E0 写法重写：
  机型×朝向×位置布尔（217 台恰为下限）、核心位置、运输格 t、桥 b≤t、覆盖 ≤1；
  仓库取货口固定一种合法排布（左 x=0 占 y=1..69，下 y=0 占 x=1..69，角格空），46 个端口外侧格必须是运输格；
  每台机器存货边、取货边外侧各 ≥1 运输格；可选：空矩形固定、T≤Tmax、T+b≥306、T≥Tmin。
  不放供电桩（放松）。
子问题（线性规划，连续，母图＝全部 b×b 块＋全部可能机器位置＋全部可能核心位置）：
  块内每种物品守恒；相邻块间两向流量和 ≤ 两侧边界运输格数；进入某块物品格的件数 ≤ 该块 t+b；
  机器按位置记配方（Σ时长×批率≤y），从块 B 收／向块 B 送 ≤ 该块里它端口外侧格的 t 之和、≤ 端口数×y；
  取货口每口恰 1 件矿（满速下界＋上界）；核心取货端口同（带核心位置字面量）；核心存货端口收任何物品；
  成品进核心 ≥0.6、≥0.55。第一阶段对所有「≥」行加松弛。
割：μᵀu(x) ≥ ρᵀt(x)，乘子有理化（整数刻度 SCALE），逐列精确核（不在当前布局的机器／核心位置按 min/max 规则补乘子），
系数向上取整加回。
"""
import argparse, json, os, time, math
from ortools.sat.python import cp_model
from ortools.linear_solver import pywraplp

DIRS = [(1, 0), (0, 1), (-1, 0), (0, -1)]
OPP = [2, 3, 0, 1]
N = 70

TYPES = {'crush': ('S', 68), 'refine': ('S', 51), 'parts': ('S', 6), 'mold': ('S', 6),
         'plant': ('M', 32), 'seed': ('M', 16), 'grind': ('L', 32), 'pack': ('L', 3), 'fill': ('L', 3)}
R = {  # recipes: (inputs, outputs, ticks)
    'crush': [({'ore_s': 1}, {'src_pow': 1}, 1), ({'iron_block': 1}, {'iron_pow': 1}, 1),
              ({'buck': 1}, {'buck_pow': 2}, 1), ({'sand': 1}, {'sand_pow': 3}, 1)],
    'refine': [({'ore_i': 1}, {'iron_block': 1}, 1), ({'dense_iron': 1}, {'steel': 1}, 1),
               ({'iron_pow': 1}, {'iron_block': 1}, 1)],
    'grind': [({'iron_pow': 2, 'sand_pow': 1}, {'dense_iron': 1}, 1),
              ({'src_pow': 2, 'sand_pow': 1}, {'dense_src': 1}, 1),
              ({'buck_pow': 2, 'sand_pow': 1}, {'fine_buck': 1}, 1)],
    'mold': [({'steel': 2}, {'bottle': 1}, 1)],
    'parts': [({'steel': 1}, {'parts': 1}, 1)],
    'plant': [({'sand_seed': 1}, {'sand': 1}, 1), ({'buck_seed': 1}, {'buck': 1}, 1)],
    'seed': [({'buck': 1}, {'buck_seed': 2}, 1), ({'sand': 1}, {'sand_seed': 2}, 1)],
    'pack': [({'parts': 10, 'dense_src': 15}, {'battery': 1}, 5)],
    'fill': [({'bottle': 10, 'fine_buck': 10}, {'capsule': 1}, 5)],
}
ITEMS = sorted({it for k in R for (a, b, t) in R[k] for it in list(a) + list(b)})
ORE = ['ore_i', 'ore_s']
TARGET = {'battery': (3, 5), 'capsule': (11, 20)}  # rationals as (num, den)
TAU_L = 5  # lcm of recipe times


def inb(x, y):
    return 0 <= x < N and 0 <= y < N


def edge_cells(ax, ay, w, h, side):
    if side == 0:
        return [(ax + w - 1, y) for y in range(ay, ay + h)]
    if side == 1:
        return [(x, ay + h - 1) for x in range(ax, ax + w)]
    if side == 2:
        return [(ax, y) for y in range(ay, ay + h)]
    return [(x, ay) for x in range(ax, ax + w)]


def orientations(cls):
    if cls == 'S':
        return [(3, 3, s) for s in range(4)]
    if cls == 'M':
        return [(5, 5, s) for s in range(4)]
    return [(6, 4, 3), (6, 4, 1), (4, 6, 2), (4, 6, 0)]


class Geo:
    def __init__(self, rect, B):
        self.B = B
        self.fixed = set()
        self.ore_cells = []
        for j in range(23):
            for yy in range(1 + 3 * j, 4 + 3 * j):
                self.fixed.add((0, yy))
            self.ore_cells.append((1, 2 + 3 * j))
            for xx in range(1 + 3 * j, 4 + 3 * j):
                self.fixed.add((xx, 0))
            self.ore_cells.append((2 + 3 * j, 1))
        self.fixed.add((0, 0))
        self.rect = set()
        if rect:
            rx, ry, rw, rh = rect
            self.rect = {(x, y) for x in range(rx, rx + rw) for y in range(ry, ry + rh)}
        self.blocked = self.fixed | self.rect
        self.free = [(x, y) for x in range(N) for y in range(N) if (x, y) not in self.blocked]
        self.freeset = set(self.free)
        # placements
        self.pl = []
        for k, (cls, cnt) in TYPES.items():
            for (w, h, s) in orientations(cls):
                so = OPP[s]
                for ax in range(N - w + 1):
                    for ay in range(N - h + 1):
                        if any((x, y) in self.blocked for x in range(ax, ax + w) for y in range(ay, ay + h)):
                            continue
                        ins = [(ex + DIRS[s][0], ey + DIRS[s][1]) for (ex, ey) in edge_cells(ax, ay, w, h, s)]
                        outs = [(ex + DIRS[so][0], ey + DIRS[so][1]) for (ex, ey) in edge_cells(ax, ay, w, h, so)]
                        ins = [c for c in ins if c in self.freeset]
                        outs = [c for c in outs if c in self.freeset]
                        self.pl.append(dict(type=k, fp=(ax, ay, w, h), ins=ins, outs=outs))
        self.core = []
        for ori in range(2):
            for ax in range(N - 8):
                for ay in range(N - 8):
                    if any((x, y) in self.blocked for x in range(ax, ax + 9) for y in range(ay, ay + 9)):
                        continue
                    in_sides = [0, 2] if ori == 0 else [1, 3]
                    out_sides = [1, 3] if ori == 0 else [0, 2]
                    ins, outs = [], []
                    for s in in_sides:
                        ec = edge_cells(ax, ay, 9, 9, s)
                        for i in range(1, 8):
                            c = (ec[i][0] + DIRS[s][0], ec[i][1] + DIRS[s][1])
                            if c in self.freeset:
                                ins.append(c)
                    for s in out_sides:
                        ec = edge_cells(ax, ay, 9, 9, s)
                        for i in (1, 4, 7):
                            c = (ec[i][0] + DIRS[s][0], ec[i][1] + DIRS[s][1])
                            if c in self.freeset:
                                outs.append(c)
                    self.core.append(dict(fp=(ax, ay, 9, 9), ins=ins, outs=outs))

    def blk(self, c):
        return (c[0] // self.B, c[1] // self.B)


class Master:
    def __init__(self, G, tmax=0, tmin=0, tb=0):
        self.G = G
        m = self.m = cp_model.CpModel()
        cover = {c: [] for c in G.free}
        self.y = [m.NewBoolVar('') for _ in G.pl]
        for i, p in enumerate(G.pl):
            ax, ay, w, h = p['fp']
            for x in range(ax, ax + w):
                for yy in range(ay, ay + h):
                    cover[(x, yy)].append(self.y[i])
        for k, (cls, cnt) in TYPES.items():
            m.Add(sum(self.y[i] for i, p in enumerate(G.pl) if p['type'] == k) == cnt)
        self.z = [m.NewBoolVar('') for _ in G.core]
        for j, p in enumerate(G.core):
            ax, ay, w, h = p['fp']
            for x in range(ax, ax + 9):
                for yy in range(ay, ay + 9):
                    cover[(x, yy)].append(self.z[j])
        m.AddExactlyOne(self.z)
        self.t, self.b = {}, {}
        for c in G.free:
            self.t[c] = m.NewBoolVar(''); self.b[c] = m.NewBoolVar('')
            m.AddImplication(self.b[c], self.t[c])
            cover[c].append(self.t[c])
        for c, lst in cover.items():
            if len(lst) > 1:
                m.Add(sum(lst) <= 1)
        for i, p in enumerate(G.pl):
            m.AddBoolOr([self.t[c] for c in p['ins']] + [self.y[i].Not()])
            m.AddBoolOr([self.t[c] for c in p['outs']] + [self.y[i].Not()])
        for c in G.ore_cells:
            m.Add(self.t[c] == 1)
        T = sum(self.t.values()); Bn = sum(self.b.values())
        if tmax:
            m.Add(T <= tmax)
        if tmin:
            m.Add(T >= tmin)
        if tb:
            m.Add(T + Bn >= tb)
        self.ncuts = 0

    def set_hint(self, sol):
        self.m.ClearHints()
        ys = set(sol['y']); zs = set(sol['z'])
        for i, v in enumerate(self.y):
            self.m.AddHint(v, i in ys)
        for j, v in enumerate(self.z):
            self.m.AddHint(v, j in zs)
        for c, v in self.t.items():
            self.m.AddHint(v, c in sol['t'])
        for c, v in self.b.items():
            self.m.AddHint(v, c in sol['b'])

    def solve(self, tl, threads, hint=None):
        s = cp_model.CpSolver()
        s.parameters.max_time_in_seconds = tl
        s.parameters.num_workers = threads
        t0 = time.time()
        st = s.Solve(self.m)
        return s, st, time.time() - t0

    def extract(self, s):
        return dict(y=[i for i, v in enumerate(self.y) if s.Value(v)],
                    z=[j for j, v in enumerate(self.z) if s.Value(v)],
                    t={c for c, v in self.t.items() if s.Value(v)},
                    b={c for c, v in self.b.items() if s.Value(v)})


class Coarse:
    """块级线性规划。行键：('blk',B,k) 守恒；('ent',B) 进入物品格 ≤ Σ(t+b)；('cr',B,B2,side) 跨界 ≤ 边界一侧 Σt；
    机器 ('pin',i,k)/('pout',i,k) 守恒；('pt',i) 时长 ≤ y_i；('pinT',i,B)/('pinN',i,B)、('poutT',i,B)/('poutN',i,B)；
    核心 ('cinT',j,B)/('cinN',j,B)；('cout',j,c) ≤ z_j、('coutL',j,c) ≥ z_j；取货口 ('q',c) ≤1、('qL',c) ≥1；目标 ('tgt',k)。"""

    def __init__(self, G):
        self.G = G
        Bn = G.B
        self.nb = (N + Bn - 1) // Bn
        self.blocks = [(i, j) for i in range(self.nb) for j in range(self.nb)]
        self.bcells = {B: [] for B in self.blocks}
        for c in G.free:
            self.bcells[G.blk(c)].append(c)
        # boundary cells between adjacent blocks: (B,B2) -> (cells on B side, cells on B2 side)
        self.bnd = {}
        for c in G.free:
            for d in (0, 1):
                c2 = (c[0] + DIRS[d][0], c[1] + DIRS[d][1])
                if c2 in G.freeset and G.blk(c) != G.blk(c2):
                    key = (G.blk(c), G.blk(c2))
                    self.bnd.setdefault(key, (set(), set()))
                    self.bnd[key][0].add(c); self.bnd[key][1].add(c2)
        self.pinb = []   # per placement: {B: [cells]} for in-port cells
        self.poutb = []
        for p in G.pl:
            d1, d2 = {}, {}
            for c in p['ins']:
                d1.setdefault(G.blk(c), []).append(c)
            for c in p['outs']:
                d2.setdefault(G.blk(c), []).append(c)
            self.pinb.append(d1); self.poutb.append(d2)
        self.cinb = []
        for p in G.core:
            d1 = {}
            for c in p['ins']:
                d1.setdefault(G.blk(c), []).append(c)
            self.cinb.append(d1)

    def solve(self, sol):
        G = self.G
        lp = pywraplp.Solver.CreateSolver('GLOP')
        inf = lp.infinity()
        rows = {}   # key -> [('kind', rhs), terms list]
        def addterm(key, var, coef):
            rows.setdefault(key, []).append((var, coef))
        cols = 0
        # block arcs
        for (B1, B2) in self.bnd:
            for (a, b_) in ((B1, B2), (B2, B1)):
                for k in ITEMS:
                    v = lp.NumVar(0, inf, ''); cols += 1
                    addterm(('blk', a, k), v, -1); addterm(('blk', b_, k), v, 1)
                    addterm(('ent', b_), v, 1)
                    addterm(('cr', B1, B2, 0), v, 1); addterm(('cr', B1, B2, 1), v, 1)
        # machines
        for i in sol['y']:
            p = G.pl[i]; k = p['type']
            ins = sorted({it for (a, b_, tt) in R[k] for it in a})
            outs = sorted({it for (a, b_, tt) in R[k] for it in b_})
            for B in self.pinb[i]:
                for it in ins:
                    v = lp.NumVar(0, inf, ''); cols += 1
                    addterm(('blk', B, it), v, -1); addterm(('pin', i, it), v, 1)
                    addterm(('pinT', i, B), v, 1); addterm(('pinN', i, B), v, 1)
            for B in self.poutb[i]:
                for it in outs:
                    v = lp.NumVar(0, inf, ''); cols += 1
                    addterm(('pout', i, it), v, -1); addterm(('blk', B, it), v, 1); addterm(('ent', B), v, 1)
                    addterm(('poutT', i, B), v, 1); addterm(('poutN', i, B), v, 1)
            for (a, b_, tt) in R[k]:
                v = lp.NumVar(0, inf, ''); cols += 1
                for it, q in a.items():
                    addterm(('pin', i, it), v, -q)
                for it, q in b_.items():
                    addterm(('pout', i, it), v, q)
                addterm(('pt', i), v, tt)
        # core
        for j in sol['z']:
            p = G.core[j]
            for B in self.cinb[j]:
                for it in ITEMS:
                    v = lp.NumVar(0, inf, ''); cols += 1
                    addterm(('blk', B, it), v, -1); addterm(('cinT', j, B), v, 1); addterm(('cinN', j, B), v, 1)
                    if it in TARGET:
                        addterm(('tgt', it), v, 1)
            for c in p['outs']:
                B = G.blk(c)
                for it in ORE:
                    v = lp.NumVar(0, inf, ''); cols += 1
                    addterm(('blk', B, it), v, 1); addterm(('ent', B), v, 1)
                    addterm(('cout', j, c), v, 1); addterm(('coutL', j, c), v, 1)
        for c in G.ore_cells:
            B = G.blk(c)
            for it in ORE:
                v = lp.NumVar(0, inf, ''); cols += 1
                addterm(('blk', B, it), v, 1); addterm(('ent', B), v, 1)
                addterm(('q', c), v, 1); addterm(('qL', c), v, 1)
        # rhs at current point
        t, b = sol['t'], sol['b']
        def rhs(key):
            tag = key[0]
            if tag in ('blk', 'pin', 'pout'):
                return ('eq', 0)
            if tag == 'ent':
                return ('le', sum((c in t) + (c in b) for c in self.bcells[key[1]]))
            if tag == 'cr':
                cells = self.bnd[(key[1], key[2])][key[3]]
                return ('le', sum(c in t for c in cells))
            if tag == 'pt':
                return ('le', 1)
            if tag == 'pinT':
                return ('le', sum(c in t for c in self.pinb[key[1]][key[2]]))
            if tag == 'pinN':
                return ('le', len(self.pinb[key[1]][key[2]]))
            if tag == 'poutT':
                return ('le', sum(c in t for c in self.poutb[key[1]][key[2]]))
            if tag == 'poutN':
                return ('le', len(self.poutb[key[1]][key[2]]))
            if tag == 'cinT':
                return ('le', sum(c in t for c in self.cinb[key[1]][key[2]]))
            if tag == 'cinN':
                return ('le', len(self.cinb[key[1]][key[2]]))
            if tag == 'cout':
                return ('le', 1)
            if tag == 'coutL':
                return ('ge', 1)
            if tag == 'q':
                return ('le', 1)
            if tag == 'qL':
                return ('ge', 1)
            if tag == 'tgt':
                n, d = TARGET[key[1]]
                return ('ge', n / d)
            raise KeyError(key)
        cons = {}
        slack = []
        for key, terms in rows.items():
            kind, r = rhs(key)
            e = sum(v * q for v, q in terms)
            if kind == 'eq':
                cons[key] = lp.Add(e == 0)
            elif kind == 'le':
                cons[key] = lp.Add(e <= r)
            else:
                s_ = lp.NumVar(0, inf, ''); slack.append(s_)
                cons[key] = lp.Add(e + s_ >= r)
        lp.Minimize(sum(slack))
        t0 = time.time()
        st = lp.Solve()
        dt = time.time() - t0
        assert st == pywraplp.Solver.OPTIMAL, st
        return dict(value=lp.Objective().Value(), duals={k: c.dual_value() for k, c in cons.items()},
                    lp_s=dt, ncols=cols, nrows=len(cons))

    def cut(self, res, sol, SCALE=10 ** 6):
        """整数刻度的精确乘子：y_int = round(dual*SCALE)。返回 (terms {lit: int coef}, rhs int)，对应
        Σ coef·lit ≥ rhs，已乘 SCALE*TAU_L 且全为整数；另返回在当前解处的左边值。"""
        G = self.G
        D = res['duals']
        L = TAU_L
        yv = {}
        for k, v in D.items():
            q = round(v * SCALE)
            if k[0] in ('tgt', 'coutL', 'qL'):
                q = max(0, q)
            elif k[0] not in ('blk', 'pin', 'pout'):
                q = min(0, q)
            yv[k] = q * L   # everything scaled by SCALE*L
        get = lambda k: yv.get(k, 0)
        blkv = lambda B, it: get(('blk', B, it))
        entv = lambda B: get(('ent', B))
        repaired = 0
        # ---- exact column checks over the WHOLE mother graph, repairing mu (le-rows) upward
        # block arcs: col coef: blk(a)-1, blk(b)+1, ent(b)+1, cr0 +1, cr1 +1
        for (B1, B2) in self.bnd:
            for (a, b_) in ((B1, B2), (B2, B1)):
                need = max(-blkv(a, it) + blkv(b_, it) for it in ITEMS) + entv(b_) + get(('cr', B1, B2, 0)) + get(('cr', B1, B2, 1))
                if need > 0:
                    yv[('cr', B1, B2, 0)] = get(('cr', B1, B2, 0)) - need; repaired += 1
        active = set(sol['y'])
        for i, p in enumerate(G.pl):
            k = p['type']
            ins = sorted({it for (a, b_, tt) in R[k] for it in a})
            outs = sorted({it for (a, b_, tt) in R[k] for it in b_})
            if i in active:
                al = {it: get(('pin', i, it)) for it in ins}
                be = {it: get(('pout', i, it)) for it in outs}
            else:
                al = {it: min(blkv(B, it) for B in self.pinb[i]) if self.pinb[i] else 0 for it in ins}
                be = {it: max(blkv(B, it) + entv(B) for B in self.poutb[i]) if self.poutb[i] else 0 for it in outs}
                # fix: machine with no in-port cells in grid: alpha may be anything; use 0 (it then needs mu only via time row)
                for it in ins:
                    yv[('pin', i, it)] = al[it]
                for it in outs:
                    yv[('pout', i, it)] = be[it]
            for B in self.pinb[i]:
                for it in ins:
                    need = -blkv(B, it) + al[it] + get(('pinT', i, B)) + get(('pinN', i, B))
                    if need > 0:
                        yv[('pinN', i, B)] = get(('pinN', i, B)) - need; repaired += 1
            for B in self.poutb[i]:
                for it in outs:
                    need = -be[it] + blkv(B, it) + entv(B) + get(('poutT', i, B)) + get(('poutN', i, B))
                    if need > 0:
                        yv[('poutN', i, B)] = get(('poutN', i, B)) - need; repaired += 1
            for (a, b_, tt) in R[k]:
                gain = sum(q * be[it] for it, q in b_.items()) - sum(q * al[it] for it, q in a.items())
                need = gain + tt * get(('pt', i))
                if need > 0:
                    # need tt*|y_pt| >= gain ; y_pt integer-scaled: choose y_pt = -ceil(gain/tt)
                    yv[('pt', i)] = get(('pt', i)) - (-(-need // tt)); repaired += (i in active)
        activec = set(sol['z'])
        for j, p in enumerate(G.core):
            for B in self.cinb[j]:
                need = max(-blkv(B, it) + (get(('tgt', it)) if it in TARGET else 0) for it in ITEMS) \
                    + get(('cinT', j, B)) + get(('cinN', j, B))
                if need > 0:
                    yv[('cinN', j, B)] = get(('cinN', j, B)) - need; repaired += (j in activec)
            for c in p['outs']:
                B = G.blk(c)
                need = max(blkv(B, it) for it in ORE) + entv(B) + get(('cout', j, c)) + get(('coutL', j, c))
                if need > 0:
                    yv[('cout', j, c)] = get(('cout', j, c)) - need; repaired += (j in activec)
        for c in G.ore_cells:
            B = G.blk(c)
            need = max(blkv(B, it) for it in ORE) + entv(B) + get(('q', c)) + get(('qL', c))
            if need > 0:
                yv[('q', c)] = get(('q', c)) - need; repaired += 1
        # ---- assemble cut: sum over le-rows (-y)*u(x) >= sum over ge-rows y*t(x)
        terms = {}
        const20 = 0
        def addlit(lit, coef):
            if coef:
                terms[lit] = terms.get(lit, 0) + coef
        for key, v in yv.items():
            if v == 0:
                continue
            tag = key[0]
            if tag in ('blk', 'pin', 'pout'):
                continue
            if tag in ('tgt', 'coutL', 'qL'):
                # ge rows: contribute to rhs y*t(x); move to lhs with negative sign
                if tag == 'tgt':
                    n, d = TARGET[key[1]]
                    const20 -= v * n * (20 // d)   # exact: 20/d is an integer for d in {5,20}
                elif tag == 'coutL':
                    addlit(('z', key[1]), -v)
                else:
                    const20 -= 20 * v
                continue
            mu = -v
            if tag == 'ent':
                for c in self.bcells[key[1]]:
                    addlit(('t', c), mu); addlit(('b', c), mu)
            elif tag == 'cr':
                for c in self.bnd[(key[1], key[2])][key[3]]:
                    addlit(('t', c), mu)
            elif tag == 'pt':
                addlit(('y', key[1]), mu)
            elif tag in ('pinT', 'poutT'):
                cells = (self.pinb if tag == 'pinT' else self.poutb)[key[1]][key[2]]
                for c in cells:
                    addlit(('t', c), mu)
            elif tag in ('pinN', 'poutN'):
                n = len((self.pinb if tag == 'pinN' else self.poutb)[key[1]][key[2]])
                addlit(('y', key[1]), mu * n)
            elif tag == 'cinT':
                for c in self.cinb[key[1]][key[2]]:
                    addlit(('t', c), mu)
            elif tag == 'cinN':
                addlit(('z', key[1]), mu * len(self.cinb[key[1]][key[2]]))
            elif tag == 'cout':
                addlit(('z', key[1]), mu)
            elif tag == 'q':
                const20 += 20 * mu
            else:
                raise KeyError(key)
        # cut: sum terms*lit + const >= 0   (const includes -rho*t for targets and outlets)
        # targets have denominators 5 and 20: multiply everything by 20 to stay integral
        terms = {k: 20 * v for k, v in terms.items() if v}
        rhs = -const20
        on = set()
        for i in sol['y']: on.add(('y', i))
        for j in sol['z']: on.add(('z', j))
        for c in sol['t']: on.add(('t', c))
        for c in sol['b']: on.add(('b', c))
        cur = sum(v for k, v in terms.items() if k in on)
        return terms, rhs, cur, repaired


def lit(M, key):
    tag = key[0]
    if tag == 'y':
        return M.y[key[1]]
    if tag == 'z':
        return M.z[key[1]]
    if tag == 't':
        return M.t[key[1]]
    if tag == 'b':
        return M.b[key[1]]
    raise KeyError(key)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rect', default='13,45,53,21')
    ap.add_argument('--B', type=int, default=5)
    ap.add_argument('--tmax', type=int, default=0)
    ap.add_argument('--tmin', type=int, default=0)
    ap.add_argument('--tb', type=int, default=0)
    ap.add_argument('--time', type=float, default=1800)
    ap.add_argument('--iter_time', type=float, default=600)
    ap.add_argument('--threads', type=int, default=6)
    ap.add_argument('--iters', type=int, default=100)
    ap.add_argument('--out', default='')
    ap.add_argument('--hint', type=int, default=1)
    a = ap.parse_args()
    rect = None if a.rect == 'none' else tuple(map(int, a.rect.split(',')))
    t0 = time.time()
    G = Geo(rect, a.B)
    M = Master(G, a.tmax, a.tmin, a.tb)
    C = Coarse(G)
    info = dict(rect=a.rect, B=a.B, tmax=a.tmax, tmin=a.tmin, tb=a.tb, threads=a.threads,
                placements=len(G.pl), core=len(G.core), free=len(G.free), build_s=round(time.time() - t0, 1),
                load_start=round(os.getloadavg()[0], 1))
    print(json.dumps(info), flush=True)
    log = []
    tot = 0.0
    for it in range(a.iters):
        s, st, dt = M.solve(min(a.iter_time, max(1.0, a.time - tot)), a.threads)
        tot += dt
        rec = dict(iter=it, status=s.StatusName(st), master_s=round(dt, 1), cuts=M.ncuts,
                   load=round(os.getloadavg()[0], 1))
        if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            log.append(rec); print(json.dumps(rec), flush=True)
            info['final'] = s.StatusName(st); break
        sol = M.extract(s)
        rec.update(T=len(sol['t']), bridges=len(sol['b']))
        t1 = time.time()
        res = C.solve(sol)
        rec.update(lp_s=round(res['lp_s'], 2), lp_cols=res['ncols'], lp_rows=res['nrows'],
                   shortfall=round(res['value'], 6))
        if res['value'] <= 1e-7:
            rec['result'] = 'coarse-feasible'
            log.append(rec); print(json.dumps(rec), flush=True)
            info['final'] = 'COARSE_FEASIBLE'; break
        terms, rhs, cur, rep = C.cut(res, sol)
        M.m.Add(sum(v * lit(M, k) for k, v in terms.items()) >= rhs)
        M.ncuts += 1
        if a.hint:
            M.set_hint(sol)
        tot += time.time() - t1
        rec.update(cut_terms=len(terms), cut_rhs=rhs, cut_lhs_now=cur, violated=bool(cur < rhs), repaired=rep,
                   cut_s=round(time.time() - t1, 1))
        log.append(rec); print(json.dumps(rec), flush=True)
        if not cur < rhs:
            info['final'] = 'CUT_NOT_VIOLATED'; break
        if tot > a.time:
            info['final'] = 'TIME'; break
    info.update(total_s=round(tot, 1), iters=len(log), load_end=round(os.getloadavg()[0], 1))
    print(json.dumps(info), flush=True)
    if a.out:
        json.dump(dict(info=info, log=log), open(a.out, 'w'), indent=1)


if __name__ == '__main__':
    main()
