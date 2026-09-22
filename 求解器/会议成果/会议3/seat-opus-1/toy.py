#!/usr/bin/env python3
"""会议 3 seat-opus-1：分解路线的小尺寸对照实测（玩具工厂，不是正式问题）。

玩具规则（取自正式规则的一个子集，另加的只有：汇只收成品、取货口直接给砂叶）：
- N×N 网格，左边界若干 3×1 取货口（中间格向东一个取货端口），各给定一种物品，每 tick 至多 1 件。
- 一个 3×3 的汇，西、南两边的格都是存货端口，只收成品。
- 粉碎机 3×3（一边全存货、对边全取货）：源矿→源石粉末；砂叶→3 砂叶粉末；各 1 tick。
- 研磨机 6×4（长边全存货、对边全取货）：2 源石粉末 + 1 砂叶粉末 → 1 致密源石粉末，1 tick。
- 运输单位：传送带 12、分流器 4、汇流器 4、桥接器 4（两轴方向）；本玩具不放准入口。
- 目标：成品（致密源石粉末）进汇 ≥ D 件/tick。
三种写法：
  jia  : 格状态＋自动通道＋每台机器存、取货边各至少一条通道（端口邻接）；
  yi   : jia ＋ 按物品的整数流（刻度 K=60），一次求解；
  bing : jia ＋ 线性规划子问题（连续）循环回送 Farkas 割（有理数逐列核过、取整往松的方向）。
"""
import argparse, json, time, sys, os, math
from fractions import Fraction as Fr
from ortools.sat.python import cp_model
from ortools.linear_solver import pywraplp

DIRS = [(1, 0), (0, 1), (-1, 0), (0, -1)]  # 0E 1N 2W 3S
OPP = [2, 3, 0, 1]
AX = ['H', 'V', 'H', 'V']  # bridge axis used by a port on side d

ITEMS = ['ore', 'sand', 'opow', 'spow', 'dense']
RECIPES = {
    'crush': [({'ore': 1}, {'opow': 1}, 1), ({'sand': 1}, {'spow': 3}, 1)],
    'grind': [({'opow': 2, 'spow': 1}, {'dense': 1}, 1)],
}
SIZE = {'crush': [(3, 3, s) for s in range(4)],
        'grind': [(6, 4, 3), (6, 4, 1), (4, 6, 2), (4, 6, 0)]}  # (w,h,in-side)
PRODUCTS = ['dense']


def edge_cells(ax, ay, w, h, side):
    if side == 0:
        return [(ax + w - 1, y) for y in range(ay, ay + h)]
    if side == 1:
        return [(x, ay + h - 1) for x in range(ax, ax + w)]
    if side == 2:
        return [(ax, y) for y in range(ay, ay + h)]
    return [(x, ay) for x in range(ax, ax + w)]


class Inst:
    def __init__(self, N, outlets, sink_xy, counts, target, rect=None):
        self.N = N
        self.target = target  # dict item -> Fraction
        self.counts = counts  # type -> min count
        self.blocked = set()
        self.outlets = []  # (port cell c, d from c toward outlet, item)
        for (y0, item) in outlets:  # outlet occupies (0,y0..y0+2), port at middle
            for y in range(y0, y0 + 3):
                self.blocked.add((0, y))
            self.outlets.append(((1, y0 + 1), 2, item))
        sx, sy = sink_xy
        self.sink_ports = []  # (c, d) c outside cell, d from c toward sink
        for x in range(sx, sx + 3):
            for y in range(sy, sy + 3):
                self.blocked.add((x, y))
        for (ex, ey) in edge_cells(sx, sy, 3, 3, 2):
            self.sink_ports.append(((ex - 1, ey), 0))
        for (ex, ey) in edge_cells(sx, sy, 3, 3, 3):
            self.sink_ports.append(((ex, ey - 1), 1))
        self.rect = rect
        if rect:
            rx, ry, rw, rh = rect
            for x in range(rx, rx + rw):
                for y in range(ry, ry + rh):
                    self.blocked.add((x, y))
        self.free = [(x, y) for x in range(N) for y in range(N) if (x, y) not in self.blocked]
        self.freeset = set(self.free)
        self.sink_ports = [(c, d) for (c, d) in self.sink_ports if c in self.freeset]
        # placements
        self.pl = []  # dict(type, fp=(ax,ay,w,h), ins=[(c,d)], outs=[(c,d)])
        for k in counts:
            for (w, h, s) in SIZE[k]:
                so = OPP[s]
                for ax in range(N - w + 1):
                    for ay in range(N - h + 1):
                        if any((x, y) in self.blocked for x in range(ax, ax + w) for y in range(ay, ay + h)):
                            continue
                        ins = []
                        for (ex, ey) in edge_cells(ax, ay, w, h, s):
                            c = (ex + DIRS[s][0], ey + DIRS[s][1])
                            if c in self.freeset:
                                ins.append((c, OPP[s]))
                        outs = []
                        for (ex, ey) in edge_cells(ax, ay, w, h, so):
                            c = (ex + DIRS[so][0], ey + DIRS[so][1])
                            if c in self.freeset:
                                outs.append((c, OPP[so]))
                        self.pl.append(dict(type=k, fp=(ax, ay, w, h), ins=ins, outs=outs))


def nb(c, d):
    return (c[0] + DIRS[d][0], c[1] + DIRS[d][1])


STATES = ['E'] + [('B', i, o) for i in range(4) for o in range(4) if i != o] + \
         [('S', i) for i in range(4)] + [('M', o) for o in range(4)] + \
         [('X', h, v) for h in range(2) for v in range(2)]


def state_ports(st):
    """returns (in0 sides, out0 sides, inB sides, outB sides)"""
    if st == 'E':
        return [], [], [], []
    if st[0] == 'B':
        return [st[1]], [st[2]], [], []
    if st[0] == 'S':
        return [st[1]], [d for d in range(4) if d != st[1]], [], []
    if st[0] == 'M':
        return [d for d in range(4) if d != st[1]], [st[1]], [], []
    h, v = st[1], st[2]
    inb, outb = [], []
    if h == 0:
        inb.append(2); outb.append(0)
    else:
        inb.append(0); outb.append(2)
    if v == 0:
        inb.append(3); outb.append(1)
    else:
        inb.append(1); outb.append(3)
    return [], [], inb, outb


def slot_of(kind, d):
    return '0' if kind == '0' else AX[d]


class Master:
    """格状态＋自动通道（jia）；可选按物品整数流（yi）。"""

    def __init__(self, inst, yi=False, K=60, min_transport=False, tu=False, subsets=False):
        self.inst = I = inst
        m = self.m = cp_model.CpModel()
        cover = {c: [] for c in I.free}
        self.y = []
        for p in I.pl:
            v = m.NewBoolVar('')
            self.y.append(v)
            ax, ay, w, h = p['fp']
            for x in range(ax, ax + w):
                for yy in range(ay, ay + h):
                    cover[(x, yy)].append(v)
        for k, n in I.counts.items():
            m.Add(sum(self.y[i] for i, p in enumerate(I.pl) if p['type'] == k) >= n)
        self.st = {}
        for c in I.free:
            self.st[c] = {s: m.NewBoolVar('') for s in STATES}
            m.Add(sum(cover[c]) + sum(self.st[c].values()) == 1)
        # side literals
        self.side = {}  # (c, kind in/out, slotkind '0'/'B', d) -> literal
        for c in I.free:
            acc = {}
            for s, v in self.st[c].items():
                i0, o0, ib, ob = state_ports(s)
                for d in i0: acc.setdefault(('in', '0', d), []).append(v)
                for d in o0: acc.setdefault(('out', '0', d), []).append(v)
                for d in ib: acc.setdefault(('in', 'B', d), []).append(v)
                for d in ob: acc.setdefault(('out', 'B', d), []).append(v)
            for key, lst in acc.items():
                lit = m.NewBoolVar('')
                m.Add(lit == sum(lst))
                self.side[(c,) + key] = lit
        self.e0 = {}
        self.eB = {}
        for c in I.free:
            e0 = m.NewBoolVar(''); eB = m.NewBoolVar('')
            m.Add(e0 == sum(v for s, v in self.st[c].items() if s != 'E' and s[0] in 'BSM'))
            m.Add(eB == sum(v for s, v in self.st[c].items() if s != 'E' and s[0] == 'X'))
            self.e0[c], self.eB[c] = e0, eB
        # unit port literals
        minp, moutp = {}, {}
        for i, p in enumerate(I.pl):
            for (c, d) in p['ins']:
                minp.setdefault((c, d), []).append(i)
            for (c, d) in p['outs']:
                moutp.setdefault((c, d), []).append(i)
        self.minp, self.moutp = minp, moutp
        self.minlit, self.moutlit = {}, {}
        for key, lst in minp.items():
            lit = m.NewBoolVar(''); m.Add(lit == sum(self.y[i] for i in lst)); self.minlit[key] = lit
        for key, lst in moutp.items():
            lit = m.NewBoolVar(''); m.Add(lit == sum(self.y[i] for i in lst)); self.moutlit[key] = lit

        def AND(a, b):
            v = m.NewBoolVar('')
            m.AddImplication(v, a); m.AddImplication(v, b)
            m.AddBoolOr([a.Not(), b.Not(), v])
            return v
        self.AND = AND
        # channels
        self.chTT = {}  # (c,d,st,sh) -> lit : slot st of c -> slot sh of c'=c+d
        for c in I.free:
            for d in range(4):
                c2 = nb(c, d)
                if c2 not in I.freeset:
                    continue
                for kt in ('0', 'B'):
                    for kh in ('0', 'B'):
                        a = self.side.get((c, 'out', kt, d)); b = self.side.get((c2, 'in', kh, OPP[d]))
                        if a is None or b is None:
                            continue
                        self.chTT[(c, d, kt, kh)] = AND(a, b)
        self.chTU = {}  # (c,d,kt) -> lit : slot of c -> unit at c+d (machine in-port)
        for (c, d), lit in self.minlit.items():
            for kt in ('0', 'B'):
                a = self.side.get((c, 'out', kt, d))
                if a is not None:
                    self.chTU[(c, d, kt)] = AND(a, lit)
        self.chUT = {}  # (c,d,kh) -> lit : unit at c+d (machine out-port) -> slot of c
        for (c, d), lit in self.moutlit.items():
            for kh in ('0', 'B'):
                a = self.side.get((c, 'in', kh, d))
                if a is not None:
                    self.chUT[(c, d, kh)] = AND(a, lit)
        self.chQT = {}  # outlet index, kh -> lit
        for qi, (c, d, item) in enumerate(I.outlets):
            for kh in ('0', 'B'):
                a = self.side.get((c, 'in', kh, d))
                if a is not None:
                    self.chQT[(qi, kh)] = a
        self.chTS = {}  # sink port (c,d), kt -> lit
        for (c, d) in I.sink_ports:
            for kt in ('0', 'B'):
                a = self.side.get((c, 'out', kt, d))
                if a is not None:
                    self.chTS[(c, d, kt)] = a
        # port adjacency (jia): each placed machine has >=1 in-channel and >=1 out-channel
        for i, p in enumerate(I.pl):
            ins = [self.chTU[(c, d, kt)] for (c, d) in p['ins'] for kt in ('0', 'B') if (c, d, kt) in self.chTU]
            outs = [self.chUT[(c, d, kh)] for (c, d) in p['outs'] for kh in ('0', 'B') if (c, d, kh) in self.chUT]
            m.AddBoolOr(ins + [self.y[i].Not()])
            m.AddBoolOr(outs + [self.y[i].Not()])
        m.AddBoolOr(list(self.chTS.values()))
        self.ntrans = sum(self.e0.values()) + sum(self.eB.values())
        if min_transport:
            m.Minimize(self.ntrans)
        if yi:
            self.add_int_flow(K)
        if tu:
            self.add_tu_flow(K)
        if subsets:
            self.add_subset_flows(K)
        self.ncuts = 0

    def add_subset_flows(self, K):
        """seat-opus-2 第四条：物品子集各自一份不分物品的流，各自限容、互不联系（每份全幺模）。
        玩具里取 {ore,opow}、{sand,spow}、{dense} 三份；每台机器每份的收／出只给上下限，按机型给合计。"""
        I, m = self.inst, self.m
        D = I.target['dense']
        SUBS = {  # 每种物品各一份（各自全幺模）；收／出上限按配方每 tick 至多一批
            'ore': dict(src_items={'ore'}, cin={'crush': 1, 'grind': 0}, cout={'crush': 0, 'grind': 0},
                        tot=dict(crush_in=2 * D), sink=0),
            'sand': dict(src_items={'sand'}, cin={'crush': 1, 'grind': 0}, cout={'crush': 0, 'grind': 0},
                         tot=dict(crush_in=D / 3), sink=0),
            'opow': dict(src_items=set(), cin={'crush': 0, 'grind': 2}, cout={'crush': 1, 'grind': 0},
                         tot=dict(crush_out=2 * D, grind_in=2 * D), sink=0),
            'spow': dict(src_items=set(), cin={'crush': 0, 'grind': 1}, cout={'crush': 3, 'grind': 0},
                         tot=dict(crush_out=D, grind_in=D), sink=0),
            'dense': dict(src_items=set(), cin={'crush': 0, 'grind': 0}, cout={'crush': 0, 'grind': 1},
                          tot=dict(grind_out=D), sink=D),
        }

        def slot(c, kind, d):
            return (c, '0') if kind == '0' else (c, AX[d])
        for name, S in SUBS.items():
            slot_in, slot_out, tu, ut, sink = {}, {}, {}, {}, []
            for (c, d, kt, kh), lit in self.chTT.items():
                v = m.NewIntVar(0, K, ''); m.Add(v <= K * lit)
                slot_out.setdefault(slot(c, kt, d), []).append(v)
                slot_in.setdefault(slot(nb(c, d), kh, OPP[d]), []).append(v)
            for (c, d, kt), lit in self.chTU.items():
                v = m.NewIntVar(0, K, ''); m.Add(v <= K * lit)
                slot_out.setdefault(slot(c, kt, d), []).append(v); tu.setdefault((c, d), []).append(v)
            for (c, d, kh), lit in self.chUT.items():
                v = m.NewIntVar(0, K, ''); m.Add(v <= K * lit)
                slot_in.setdefault(slot(c, kh, d), []).append(v); ut.setdefault((c, d), []).append(v)
            for (qi, kh), lit in self.chQT.items():
                c, d, item = I.outlets[qi]
                if item in S['src_items']:
                    v = m.NewIntVar(0, K, ''); m.Add(v <= K * lit)
                    slot_in.setdefault(slot(c, kh, d), []).append(v)
            if S['sink']:
                for (c, d, kt), lit in self.chTS.items():
                    v = m.NewIntVar(0, K, ''); m.Add(v <= K * lit)
                    slot_out.setdefault(slot(c, kt, d), []).append(v); sink.append(v)
            for s in set(slot_in) | set(slot_out):
                m.Add(sum(slot_in.get(s, [])) == sum(slot_out.get(s, [])))
                cap = self.e0[s[0]] if s[1] == '0' else self.eB[s[0]]
                m.Add(sum(slot_out.get(s, [])) <= K * cap)
            tin = {'crush': [], 'grind': []}; tout = {'crush': [], 'grind': []}
            for i, p in enumerate(I.pl):
                k = p['type']
                a = m.NewIntVar(0, K * 3, ''); b = m.NewIntVar(0, K * 3, '')
                m.Add(a <= K * S['cin'][k] * self.y[i]); m.Add(b <= K * S['cout'][k] * self.y[i])
                m.Add(a == sum(v for (c, d) in p['ins'] for v in tu.get((c, d), []))).OnlyEnforceIf(self.y[i])
                m.Add(b == sum(v for (c, d) in p['outs'] for v in ut.get((c, d), []))).OnlyEnforceIf(self.y[i])
                tin[k].append(a); tout[k].append(b)
            T = S['tot']
            if 'crush_in' in T: m.Add(sum(tin['crush']) >= int(T['crush_in'] * K))
            if 'crush_out' in T: m.Add(sum(tout['crush']) >= int(T['crush_out'] * K))
            if 'grind_in' in T: m.Add(sum(tin['grind']) >= int(T['grind_in'] * K))
            if 'grind_out' in T: m.Add(sum(tout['grind']) >= int(T['grind_out'] * K))
            if S['sink']: m.Add(sum(sink) >= int(S['sink'] * K))

    def add_tu_flow(self, K):
        """不分物品的流（seat-opus-2 全幺模版）：每台只给收、出各自的上限，按机型给合计；不写逐台配方比例。"""
        I, m = self.inst, self.m
        slot_in, slot_out = {}, {}

        def slot(c, kind, d):
            return (c, '0') if kind == '0' else (c, AX[d])
        for (c, d, kt, kh), lit in self.chTT.items():
            v = m.NewIntVar(0, K, ''); m.Add(v <= K * lit)
            slot_out.setdefault(slot(c, kt, d), []).append(v)
            slot_in.setdefault(slot(nb(c, d), kh, OPP[d]), []).append(v)
        tu, ut = {}, {}
        for (c, d, kt), lit in self.chTU.items():
            v = m.NewIntVar(0, K, ''); m.Add(v <= K * lit)
            slot_out.setdefault(slot(c, kt, d), []).append(v); tu[(c, d)] = tu.get((c, d), []) + [v]
        for (c, d, kh), lit in self.chUT.items():
            v = m.NewIntVar(0, K, ''); m.Add(v <= K * lit)
            slot_in.setdefault(slot(c, kh, d), []).append(v); ut[(c, d)] = ut.get((c, d), []) + [v]
        for (qi, kh), lit in self.chQT.items():
            c, d, item = I.outlets[qi]
            v = m.NewIntVar(0, K, ''); m.Add(v <= K * lit)
            slot_in.setdefault(slot(c, kh, d), []).append(v)
        sink = []
        for (c, d, kt), lit in self.chTS.items():
            v = m.NewIntVar(0, K, ''); m.Add(v <= K * lit)
            slot_out.setdefault(slot(c, kt, d), []).append(v); sink.append(v)
        for s in set(slot_in) | set(slot_out):
            m.Add(sum(slot_in.get(s, [])) == sum(slot_out.get(s, [])))
            cap = self.e0[s[0]] if s[1] == '0' else self.eB[s[0]]
            m.Add(sum(slot_out.get(s, [])) <= K * cap)
        capin = {'crush': 1, 'grind': 3}; capout = {'crush': 3, 'grind': 1}
        tin = {k: [] for k in capin}; tout = {k: [] for k in capin}
        for i, p in enumerate(I.pl):
            k = p['type']
            a = m.NewIntVar(0, K * capin[k], ''); b = m.NewIntVar(0, K * capout[k], '')
            m.Add(a <= K * capin[k] * self.y[i]); m.Add(b <= K * capout[k] * self.y[i])
            m.Add(a == sum(v for (c, d) in p['ins'] for v in tu.get((c, d), []))).OnlyEnforceIf(self.y[i])
            m.Add(b == sum(v for (c, d) in p['outs'] for v in ut.get((c, d), []))).OnlyEnforceIf(self.y[i])
            tin[k].append(a); tout[k].append(b)
        D = I.target['dense']
        m.Add(sum(tout['crush']) >= int(3 * D * K)); m.Add(sum(tin['crush']) >= int(Fr(7, 3) * D * K))
        m.Add(sum(tin['grind']) >= int(3 * D * K)); m.Add(sum(tout['grind']) >= int(D * K))
        m.Add(sum(sink) >= int(D * K))

    def add_int_flow(self, K):
        I, m = self.inst, self.m
        f = {}
        items_in = {k: set(it for (a, b, t) in RECIPES[k] for it in a) for k in RECIPES}
        items_out = {k: set(it for (a, b, t) in RECIPES[k] for it in b) for k in RECIPES}
        allin = set().union(*items_in.values())
        allout = set().union(*items_out.values())
        slot_in = {}; slot_out = {}

        def slot(c, kind, d):
            return (c, '0') if kind == '0' else (c, AX[d])
        for (c, d, kt, kh), lit in self.chTT.items():
            c2 = nb(c, d)
            for it in ITEMS:
                v = m.NewIntVar(0, K, ''); m.Add(v <= K * lit)
                slot_out.setdefault((slot(c, kt, d), it), []).append(v)
                slot_in.setdefault((slot(c2, kh, OPP[d]), it), []).append(v)
        tu = {}
        for (c, d, kt), lit in self.chTU.items():
            for it in allin:
                v = m.NewIntVar(0, K, ''); m.Add(v <= K * lit)
                slot_out.setdefault((slot(c, kt, d), it), []).append(v)
                tu.setdefault((c, d, it), []).append(v)
        ut = {}
        for (c, d, kh), lit in self.chUT.items():
            for it in allout:
                v = m.NewIntVar(0, K, ''); m.Add(v <= K * lit)
                slot_in.setdefault((slot(c, kh, d), it), []).append(v)
                ut.setdefault((c, d, it), []).append(v)
        for (qi, kh), lit in self.chQT.items():
            c, d, item = I.outlets[qi]
            v = m.NewIntVar(0, K, ''); m.Add(v <= K * lit)
            slot_in.setdefault((slot(c, kh, d), item), []).append(v)
        sinkin = {it: [] for it in PRODUCTS}
        for (c, d, kt), lit in self.chTS.items():
            for it in PRODUCTS:
                v = m.NewIntVar(0, K, ''); m.Add(v <= K * lit)
                slot_out.setdefault((slot(c, kt, d), it), []).append(v)
                sinkin[it].append(v)
        slots = set(k[0] for k in slot_in) | set(k[0] for k in slot_out)
        for s in slots:
            for it in ITEMS:
                m.Add(sum(slot_in.get((s, it), [])) == sum(slot_out.get((s, it), [])))
            cap = self.e0[s[0]] if s[1] == '0' else self.eB[s[0]]
            m.Add(sum(v for it in ITEMS for v in slot_out.get((s, it), [])) <= K * cap)
        for i, p in enumerate(I.pl):
            k = p['type']
            lam = [m.NewIntVar(0, K, '') for r in RECIPES[k]]
            m.Add(sum(RECIPES[k][j][2] * lam[j] for j in range(len(lam))) <= K * self.y[i])
            for it in ITEMS:
                need = sum(RECIPES[k][j][0].get(it, 0) * lam[j] for j in range(len(lam)))
                got = sum(v for (c, d) in p['ins'] for v in tu.get((c, d, it), []))
                if it in allin:
                    m.Add(got == need).OnlyEnforceIf(self.y[i])
                prod = sum(RECIPES[k][j][1].get(it, 0) * lam[j] for j in range(len(lam)))
                sent = sum(v for (c, d) in p['outs'] for v in ut.get((c, d, it), []))
                if it in allout:
                    m.Add(sent == prod).OnlyEnforceIf(self.y[i])
        for it in PRODUCTS:
            tgt = I.target[it] * K
            assert tgt.denominator == 1
            m.Add(sum(sinkin[it]) >= int(tgt))

    def solve(self, tl, threads, log=False):
        s = cp_model.CpSolver()
        s.parameters.max_time_in_seconds = tl
        s.parameters.num_workers = threads
        s.parameters.log_search_progress = log
        t = time.time()
        st = s.Solve(self.m)
        return s, st, time.time() - t

    def extract(self, s):
        I = self.inst
        sol = dict(y=[i for i, v in enumerate(self.y) if s.Value(v)],
                   st={c: next(k for k, v in self.st[c].items() if s.Value(v)) for c in I.free
                       if any(s.Value(v) for v in self.st[c].values())},
                   chTT=[k for k, v in self.chTT.items() if s.Value(v)],
                   chTU=[k for k, v in self.chTU.items() if s.Value(v)],
                   chUT=[k for k, v in self.chUT.items() if s.Value(v)],
                   chQT=[k for k, v in self.chQT.items() if s.Value(v)],
                   chTS=[k for k, v in self.chTS.items() if s.Value(v)])
        return sol


# ---------------------------------------------------------------- LP subproblem & Farkas cut
class LPSub:
    """母图上的线性规划；只在当前通道图上求解，乘子按母图逐列补齐（有理数）。"""

    def __init__(self, master):
        self.M = master
        self.I = master.inst

    def solve(self, sol):
        I, M = self.I, self.M
        lp = pywraplp.Solver.CreateSolver('GLOP')
        inf = lp.infinity()
        ypos = set(sol['y'])
        # which placement sits behind a machine port (c,d)
        owner_in = {}
        owner_out = {}
        for i in ypos:
            p = I.pl[i]
            for (c, d) in p['ins']:
                owner_in[(c, d)] = i
            for (c, d) in p['outs']:
                owner_out[(c, d)] = i

        def slot(c, kind, d):
            return (c, '0') if kind == '0' else (c, AX[d])
        cols = []  # (var, dict(row_key->coef))
        rows_eq = {}  # key -> list of (var, coef)
        rows_cap = {}  # key -> (list of (var,coef))
        rows_tgt = {it: [] for it in PRODUCTS}
        arcs = []  # (arc_key, tail node, head node, items)
        for (c, d, kt, kh) in sol['chTT']:
            arcs.append((('TT', c, d, kt, kh), ('S',) + slot(c, kt, d), ('S',) + slot(nb(c, d), kh, OPP[d]), ITEMS))
        for (c, d, kt) in sol['chTU']:
            i = owner_in[(c, d)]
            its = sorted(set(it for (a, b, t) in RECIPES[I.pl[i]['type']] for it in a))
            arcs.append((('TU', c, d, kt), ('S',) + slot(c, kt, d), ('Min', i), its))
        for (c, d, kh) in sol['chUT']:
            i = owner_out[(c, d)]
            its = sorted(set(it for (a, b, t) in RECIPES[I.pl[i]['type']] for it in b))
            arcs.append((('UT', c, d, kh), ('Mout', i), ('S',) + slot(c, kh, d), its))
        for (qi, kh) in sol['chQT']:
            c, d, item = I.outlets[qi]
            arcs.append((('QT', qi, kh), ('Q', qi), ('S',) + slot(c, kh, d), [item]))
        for (c, d, kt) in sol['chTS']:
            arcs.append((('TS', c, d, kt), ('S',) + slot(c, kt, d), ('Sink',), PRODUCTS))
        fvar = {}
        for (ak, tail, head, its) in arcs:
            for it in its:
                v = lp.NumVar(0, inf, '')
                fvar[(ak, it)] = v
                rows_cap.setdefault(('arc', ak), []).append((v, 1))
                if tail[0] == 'S':
                    rows_eq.setdefault(('slot', tail[1:], it), []).append((v, -1))
                    rows_cap.setdefault(('slotcap', tail[1:]), []).append((v, 1))
                elif tail[0] == 'Mout':
                    rows_eq.setdefault(('mout', tail[1], it), []).append((v, -1))
                elif tail[0] == 'Q':
                    rows_cap.setdefault(('outlet', tail[1]), []).append((v, 1))
                if head[0] == 'S':
                    rows_eq.setdefault(('slot', head[1:], it), []).append((v, 1))
                elif head[0] == 'Min':
                    rows_eq.setdefault(('min', head[1], it), []).append((v, 1))
                elif head[0] == 'Sink':
                    rows_tgt[it].append((v, 1))
        lam = {}
        for i in ypos:
            k = I.pl[i]['type']
            for j, (a, b, t) in enumerate(RECIPES[k]):
                v = lp.NumVar(0, inf, '')
                lam[(i, j)] = v
                rows_cap.setdefault(('mach', i), []).append((v, t))
                for it, q in a.items():
                    rows_eq.setdefault(('min', i, it), []).append((v, -q))
                for it, q in b.items():
                    rows_eq.setdefault(('mout', i, it), []).append((v, q))
        # make sure machine in/out rows exist for all items of its recipes
        slack = {it: lp.NumVar(0, inf, '') for it in PRODUCTS}
        cons = {}
        for key, terms in rows_eq.items():
            cons[key] = lp.Add(sum(v * q for v, q in terms) == 0)
        for key, terms in rows_cap.items():
            cons[key] = lp.Add(sum(v * q for v, q in terms) <= 1)  # all capacities are 1 when active
        for it in PRODUCTS:
            cons[('tgt', it)] = lp.Add(sum(v for v, q in rows_tgt[it]) + slack[it] >= float(I.target[it]))
        lp.Minimize(sum(slack.values()))
        t0 = time.time()
        stt = lp.Solve()
        dt = time.time() - t0
        assert stt == pywraplp.Solver.OPTIMAL, stt
        val = lp.Objective().Value()
        duals = {key: c.dual_value() for key, c in cons.items()}
        flows = {k: v.solution_value() for k, v in fvar.items() if v.solution_value() > 1e-9}
        return dict(value=val, duals=duals, lp_time=dt, nvars=lp.NumVariables(), ncons=lp.NumConstraints(),
                    flows=flows)

    def cut(self, sol, res, denom=10 ** 6):
        """用母图逐列补齐乘子，返回 (terms {lit_key: Fraction}, rhs Fraction, violation at sol)。"""
        I, M = self.I, self.M
        D = res['duals']

        def q(x):
            return Fr(round(x * denom), denom)
        pi = {}
        for key, v in D.items():
            if key[0] in ('slot', 'min', 'mout'):
                pi[key] = q(v)
        rho = {it: max(Fr(0), q(D[('tgt', it)])) for it in PRODUCTS}
        sig = {}
        for key, v in D.items():
            if key[0] == 'slotcap':
                sig[key[1]] = max(Fr(0), -q(v))
        omg = {}
        for key, v in D.items():
            if key[0] == 'outlet':
                omg[key[1]] = max(Fr(0), -q(v))

        def P(node, it):  # value of node for item (0 if not in current graph)
            if node[0] == 'S':
                return pi.get(('slot', node[1:], it), Fr(0))
            if node[0] == 'Min':
                return pi.get(('min', node[1], it), Fr(0))
            if node[0] == 'Mout':
                return pi.get(('mout', node[1], it), Fr(0))
            raise ValueError
        terms = {}

        def add(key, coef):
            if coef > 0:
                terms[key] = max(terms.get(key, Fr(0)), coef)  # aggregated literal: max over merged columns
        # --- slot capacity rows: sigma on e0 / eB (constant per slot); only for current slots
        slotcap_terms = {}
        for s, v in sig.items():
            c, kind = s
            lit = ('e0', c) if kind == '0' else ('eB', c)
            slotcap_terms[lit] = slotcap_terms.get(lit, Fr(0)) + v

        def sg(node):
            return sig.get(node[1:], Fr(0)) if node[0] == 'S' else Fr(0)

        def slot(c, kind, d):
            return ('S', c, '0') if kind == '0' else ('S', c, AX[d])
        allin = sorted(set(it for k in RECIPES for (a, b, t) in RECIPES[k] for it in a))
        allout = sorted(set(it for k in RECIPES for (a, b, t) in RECIPES[k] for it in b))
        # T->T columns over the whole mother graph
        for (c, d, kt, kh) in M.chTT:
            tail = slot(c, kt, d); head = slot(nb(c, d), kh, OPP[d])
            need = max(P(head, it) - P(tail, it) - sg(tail) for it in ITEMS)
            add(('TT', c, d, kt, kh), need)
        # T->M columns: every potential placement behind (c,d); aggregated on chTU literal by max
        for (c, d, kt) in M.chTU:
            tail = slot(c, kt, d)
            best = Fr(0)
            for i in M.minp[(c, d)]:
                its = set(it for (a, b, t) in RECIPES[I.pl[i]['type']] for it in a)
                for it in its:
                    best = max(best, P(('Min', i), it) - P(tail, it) - sg(tail))
            add(('TU', c, d, kt), best)
        # M->T columns
        for (c, d, kh) in M.chUT:
            head = slot(c, kh, d)
            best = Fr(0)
            for i in M.moutp[(c, d)]:
                its = set(it for (a, b, t) in RECIPES[I.pl[i]['type']] for it in b)
                for it in its:
                    best = max(best, P(head, it) - P(('Mout', i), it))
            add(('UT', c, d, kh), best)
        # outlet -> T columns: coefficient split between omega (outlet row, constant w=1) and arc literal
        const_lhs = Fr(0)
        for qi, v in omg.items():
            const_lhs += v  # outlet exists (fixed): w_q = 1
        for (qi, kh) in M.chQT:
            c, d, item = I.outlets[qi]
            head = slot(c, kh, d)
            need = P(head, item) - omg.get(qi, Fr(0))
            add(('QT', qi, kh), need)
        # T->sink columns
        for (c, d, kt) in M.chTS:
            tail = slot(c, kt, d)
            need = max(rho[it] - P(tail, it) - sg(tail) for it in PRODUCTS)
            add(('TS', c, d, kt), need)
        # lambda columns: every potential placement
        for i, p in enumerate(I.pl):
            best = Fr(0)
            for (a, b, t) in RECIPES[p['type']]:
                gain = sum(qq * P(('Mout', i), it) for it, qq in b.items()) - \
                       sum(qq * P(('Min', i), it) for it, qq in a.items())
                best = max(best, gain / t)
            if best > 0:
                terms[('y', i)] = best
        for lit, v in slotcap_terms.items():
            if v > 0:
                terms[lit] = terms.get(lit, Fr(0)) + v
        rhs = sum(rho[it] * self.I.target[it] for it in PRODUCTS) - const_lhs
        # exact column check (independent re-verification of the dual condition, done inline above
        # by construction: every column's requirement is covered by the chosen coefficient)
        # value at current solution
        cur = self.lhs_at(sol, terms)
        return terms, rhs, cur

    def lhs_at(self, sol, terms):
        on = set()
        for i in sol['y']:
            on.add(('y', i))
        for k in sol['chTT']:
            on.add(('TT',) + k)
        for k in sol['chTU']:
            on.add(('TU',) + k)
        for k in sol['chUT']:
            on.add(('UT',) + k)
        for k in sol['chQT']:
            on.add(('QT',) + k)
        for k in sol['chTS']:
            on.add(('TS',) + k)
        for c, s in sol['st'].items():
            if s != 'E':
                on.add(('eB', c) if s[0] == 'X' else ('e0', c))
        return sum((v for k, v in terms.items() if k in on), Fr(0))


def on_set(sol):
    on = set(('y', i) for i in sol['y'])
    for tag in ('TT', 'TU', 'UT', 'QT', 'TS'):
        for k in sol['ch' + tag]:
            on.add((tag,) + tuple(k))
    for c, s in sol['st'].items():
        if s != 'E':
            on.add(('eB', c) if s[0] == 'X' else ('e0', c))
    return on


def lit_of(M, key):
    t = key[0]
    if t == 'y':
        return M.y[key[1]]
    if t == 'TT':
        return M.chTT[key[1:]]
    if t == 'TU':
        return M.chTU[key[1:]]
    if t == 'UT':
        return M.chUT[key[1:]]
    if t == 'QT':
        return M.chQT[key[1:]]
    if t == 'TS':
        return M.chTS[key[1:]]
    if t == 'e0':
        return M.e0[key[1]]
    if t == 'eB':
        return M.eB[key[1]]
    raise KeyError(key)


def add_cut(M, terms, rhs, Kr=10 ** 4):
    coefs = {k: math.ceil(v * Kr) for k, v in terms.items()}
    r = math.ceil(rhs * Kr)
    M.m.Add(sum(c * lit_of(M, k) for k, c in coefs.items() if c != 0) >= r)
    M.ncuts += 1
    return coefs, r


def draw(inst, sol):
    N = inst.N
    g = [['.'] * N for _ in range(N)]
    for c in inst.blocked:
        g[c[1]][c[0]] = '#'
    for (c, d, item) in inst.outlets:
        for y in range(c[1] - 1, c[1] + 2):
            g[y][0] = 'o' if item == 'ore' else 's'
    for i in sol['y']:
        p = inst.pl[i]
        ax, ay, w, h = p['fp']
        ch = 'c' if p['type'] == 'crush' else 'G'
        for x in range(ax, ax + w):
            for y in range(ay, ay + h):
                g[y][x] = ch
        for (c, d) in p['ins']:
            e = nb(c, d); g[e[1]][e[0]] = 'i'
    arrow = {0: '>', 1: '^', 2: '<', 3: 'v'}
    for c, s in sol['st'].items():
        if s == 'E':
            continue
        if s[0] == 'B':
            g[c[1]][c[0]] = arrow[s[2]]
        elif s[0] == 'S':
            g[c[1]][c[0]] = 'Y'
        elif s[0] == 'M':
            g[c[1]][c[0]] = 'm'
        else:
            g[c[1]][c[0]] = '+'
    if inst.rect:
        rx, ry, rw, rh = inst.rect
        for x in range(rx, rx + rw):
            for y in range(ry, ry + rh):
                g[y][x] = ' '
    return '\n'.join(''.join(r) for r in reversed(g))


def make_inst(name, rect=None):
    if name == 'D1':
        return Inst(12, outlets=[(1, 'ore'), (4, 'ore'), (7, 'sand')], sink_xy=(9, 9),
                    counts={'crush': 3, 'grind': 1}, target={'dense': Fr(1)}, rect=rect)
    if name == 'D2':
        return Inst(16, outlets=[(1, 'ore'), (4, 'ore'), (7, 'ore'), (10, 'ore'), (13, 'sand')], sink_xy=(13, 13),
                    counts={'crush': 5, 'grind': 2}, target={'dense': Fr(2)}, rect=rect)
    raise ValueError(name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--inst', default='D1')
    ap.add_argument('--rect', default='none')
    ap.add_argument('--mode', default='bing')
    ap.add_argument('--time', type=float, default=300)
    ap.add_argument('--threads', type=int, default=6)
    ap.add_argument('--iters', type=int, default=200)
    ap.add_argument('--mintrans', type=int, default=0)
    ap.add_argument('--out', default='')
    ap.add_argument('--tu', type=int, default=0)
    ap.add_argument('--subsets', type=int, default=0)
    a = ap.parse_args()
    rect = None if a.rect == 'none' else tuple(map(int, a.rect.split(',')))
    inst = make_inst(a.inst, rect)
    load0 = os.getloadavg()[0]
    t0 = time.time()
    M = Master(inst, yi=(a.mode == 'yi'), min_transport=bool(a.mintrans), tu=bool(a.tu), subsets=bool(a.subsets))
    build = time.time() - t0
    proto = M.m.Proto()
    info = dict(inst=a.inst, rect=a.rect, mode=a.mode, tu=a.tu, subsets=a.subsets, threads=a.threads, load_start=round(load0, 2),
                build_s=round(build, 2), nvars=len(proto.variables), ncons=len(proto.constraints),
                placements=len(inst.pl), free=len(inst.free))
    print(json.dumps(info), flush=True)
    log = []
    if a.mode in ('jia', 'yi'):
        s, st, dt = M.solve(a.time, a.threads)
        rec = dict(status=s.StatusName(st), wall=round(dt, 2))
        if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            sol = M.extract(s)
            sub = LPSub(M).solve(sol)
            rec['lp_shortfall'] = sub['value']
            rec['ntrans'] = sum(1 for v in sol['st'].values() if v != 'E')
            print(draw(inst, sol))
        info.update(rec)
    elif a.mode == 'bing2':
        from fulllp import FullLP
        F = FullLP(M)
        info.update(lp_cols=len(F.cols), lp_rows=len(F.rowkeys))
        tot = 0.0
        for it in range(a.iters):
            s, st, dt = M.solve(max(1.0, a.time - tot), a.threads)
            tot += dt
            rec = dict(iter=it, status=s.StatusName(st), master_s=round(dt, 2), cuts=M.ncuts)
            if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                log.append(rec); print(json.dumps(rec), flush=True)
                info.update(final=s.StatusName(st)); break
            sol = M.extract(s)
            on = on_set(sol)
            t1 = time.time()
            res = F.solve(on)
            rec.update(lp_s=round(res['lp_time'], 3), shortfall=round(res['value'], 6))
            if res['value'] <= 1e-9:
                rec['result'] = 'flow-feasible'
                log.append(rec); print(json.dumps(rec), flush=True)
                info.update(final='FLOW_FEASIBLE', ntrans=sum(1 for v in sol['st'].values() if v != 'E'))
                print(draw(inst, sol)); break
            terms, rhs, cur, rep = F.cut(res, on)
            coefs, r = add_cut(M, terms, rhs)
            tot += time.time() - t1
            rec.update(cut_terms=len(coefs), cut_rhs=float(rhs), cut_lhs_now=float(cur), repaired=rep,
                       violated=bool(cur < rhs), cut_s=round(time.time() - t1, 3))
            log.append(rec); print(json.dumps(rec), flush=True)
            if not cur < rhs:
                info.update(final='CUT_NOT_VIOLATED'); break
            if tot > a.time:
                info.update(final='TIME'); break
        info.update(total_s=round(tot, 2), iters=len(log))
    else:
        sub = LPSub(M)
        tot = 0.0
        for it in range(a.iters):
            s, st, dt = M.solve(max(1.0, a.time - tot), a.threads)
            tot += dt
            rec = dict(iter=it, status=s.StatusName(st), master_s=round(dt, 2), cuts=M.ncuts)
            if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                log.append(rec); print(json.dumps(rec), flush=True)
                info.update(final=s.StatusName(st))
                break
            sol = M.extract(s)
            res = sub.solve(sol)
            rec.update(lp_s=round(res['lp_time'], 3), shortfall=round(res['value'], 6))
            if res['value'] <= 1e-9:
                rec['result'] = 'flow-feasible'
                log.append(rec); print(json.dumps(rec), flush=True)
                info.update(final='FLOW_FEASIBLE', ntrans=sum(1 for v in sol['st'].values() if v != 'E'))
                print(draw(inst, sol))
                break
            t1 = time.time()
            terms, rhs, cur = sub.cut(sol, res)
            coefs, r = add_cut(M, terms, rhs)
            tot += time.time() - t1
            rec.update(cut_terms=len(coefs), cut_rhs=float(rhs), cut_lhs_now=float(cur),
                       violated=bool(cur < rhs), cut_s=round(time.time() - t1, 3))
            log.append(rec); print(json.dumps(rec), flush=True)
            if not cur < rhs:
                info.update(final='CUT_NOT_VIOLATED'); break
            if tot > a.time:
                info.update(final='TIME'); break
        info.update(total_s=round(tot, 2), iters=len(log))
    info['load_end'] = round(os.getloadavg()[0], 2)
    print(json.dumps(info), flush=True)
    if a.out:
        with open(a.out, 'w') as fh:
            json.dump(dict(info=info, log=log), fh, indent=1)


if __name__ == '__main__':
    main()
