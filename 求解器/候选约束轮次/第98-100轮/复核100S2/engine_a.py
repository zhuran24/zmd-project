#!/usr/bin/env python3
"""复核100S2 引擎甲：按快照规则第23—36行与临时规则第1、4条自写的逐步模拟（不导入推导席脚本）。

一步 = 1/8 tick：
  1. 结束到时的制造，已完成的一批在取货格放得下整批时即时进入；
  2. 传送带内成熟（滞留满8步）的货逐格前移（下游先移，一直在尝试移动）；
  3. 元件按送货通道接通先后判定；临时规则第1条：一个单位的元件上游里最先「往它送货」
     （尾格有成熟货）的那个判定时，该单位全部元件上游一起判定，由它按收货轮询收下；
  4. 非运输单位（机器、协议核心、仓库取货口）按送货通道最早接通先后判定，每次至多送一件，
     取货侧按「上次成功最早的先试、从未成功的按接通先后排在最前」；
  5. 开始能开始的制造。
离线（临时规则第4条）：全部物理单位按任意次序重建，物品、货龄、制造进度原样保留，
通道接通时刻取两端建成时刻较晚者（同刻随机定序）；成功记录保留或清空两种都跑。
可选 age_reset：离线时把全部运输货龄清零——这不是推导所用读法，只作敏感性对照。
"""
import random
from net import build, BAT, CAP

NEVER = -10**9


class Mach:
    __slots__ = ('name', 'role', 'inputs', 'product', 'qty', 'dur', 'ncells', 'cells', 'take',
                 'cache', 'outs', 'ins', 'last', 'cursor', 'order_key', 'typ', 'on')


class Src:
    __slots__ = ('name', 'kind', 'outs', 'last', 'order_key', 'sent')


class Belt:
    __slots__ = ('idx', 'kind', 'cells', 'src', 'dst', 'conn_in', 'conn_out', 'tiles', 'rej', 'sent')


class Factory:
    def __init__(self, seed, lengths='rand', maxlen=4, history='clear', check=True):
        self.rng = random.Random(seed)
        self.history = history
        self.check = check
        M, S, P = build()
        self.mach = {}
        for name, d in M.items():
            m = Mach()
            m.name, m.role, m.typ = name, d['role'], d['type']
            m.inputs, m.product, m.qty, m.dur = d['inputs'], d['product'], d['qty'], d['dur']
            m.ncells = 2 if d['type'] in ('研磨机', '封装机', '灌装机') else 1
            m.outs, m.ins, m.last, m.cursor = [], [], {}, None
            m.on = True
            self.mach[name] = m
        self.src = {}
        for name, d in S.items():
            s = Src()
            s.name, s.kind, s.outs, s.last, s.sent = name, d['kind'], [], {}, 0
            self.src[name] = s
        self.belts = []
        for i, p in enumerate(P):
            b = Belt()
            b.idx, b.kind, b.src, b.dst = i, p['kind'], p['src'], p['dst']
            if isinstance(lengths, dict):
                L = lengths.get(i, 1)
            elif lengths == 'rand':
                L = self.rng.randint(1, maxlen)
            else:
                L = int(lengths)
            b.tiles = L
            b.rej = 0
            b.sent = 0
            self.belts.append(b)
            (self.mach.get(p['src']) or self.src[p['src']]).outs.append(b)
            if p['dst'] in self.mach:
                self.mach[p['dst']].ins.append(b)
        self.core_in = [b for b in self.belts if b.dst == '核心']
        self.accept = {BAT: True, CAP: True}
        self.cap_left = {BAT: None, CAP: None}
        self.delivered = {BAT: 0, CAP: 0}
        self.core_cursor = None
        self.violations = []
        self.t = 0
        self.initial_state()
        self.connect(blueprint=True)

    # ---------- 起态 ----------
    def initial_state(self):
        for m in self.mach.values():
            m.cells = [[k, 50] for k in m.inputs] + [[None, 0]] * 0
            while len(m.cells) < m.ncells:
                m.cells.append([None, 0])
            if m.role == 'final':
                m.take, m.cache = 0, None
            else:
                m.take, m.cache = 50, ('done', m.qty)
        for b in self.belts:
            if b.dst == '核心':
                b.cells = [None] * b.tiles
            else:
                b.cells = [-8] * b.tiles  # 都已滞留满 1 tick

    # ---------- 接通先后 ----------
    def connect(self, blueprint=False):
        rng = self.rng
        units = list(self.mach) + list(self.src)
        rng.shuffle(units)
        tile_names = [(b.idx, j) for b in self.belts for j in range(b.tiles)]
        rng.shuffle(tile_names)
        if blueprint:
            order = units + tile_names  # 蓝图：传送带在其余单位之后建造
        else:
            order = units + tile_names
            rng.shuffle(order)  # 离线：任意次序
        when = {u: i for i, u in enumerate(order)}
        for b in self.belts:
            # 通道接通时刻 = 两端较晚建成者；同刻接通的先后随机
            b.conn_in = (max(when[b.src], when[(b.idx, 0)]), rng.random())
            dst_t = when[b.dst] if b.dst in when else when[b.dst]
            b.conn_out = (max(dst_t, when[(b.idx, b.tiles - 1)]), rng.random())
        self.elem_order = sorted(self.belts, key=lambda b: b.conn_out)
        nts = list(self.mach.values()) + list(self.src.values())
        for u in nts:
            u.outs.sort(key=lambda b: b.conn_in)
            u.order_key = min((b.conn_in for b in u.outs), default=(10**9, 0))
        for m in self.mach.values():
            m.ins.sort(key=lambda b: b.conn_out)
        self.core_in.sort(key=lambda b: b.conn_out)
        self.nt_order = sorted([u for u in nts if u.outs], key=lambda u: u.order_key)

    def offline(self, keep, age_reset=False):
        self.connect(blueprint=False)
        if not keep:
            for u in list(self.mach.values()) + list(self.src.values()):
                u.last = {}
            for m in self.mach.values():
                m.cursor = None
            self.core_cursor = None
        if age_reset:
            for b in self.belts:
                b.cells = [None if c is None else self.t for c in b.cells]

    # ---------- 机器 ----------
    @staticmethod
    def room(m, kind):
        for c in m.cells:
            if c[0] == kind:
                return c[1] < 50
        for c in m.cells:
            if c[1] == 0:
                return True
        return False

    @staticmethod
    def put(m, kind):
        for c in m.cells:
            if c[0] == kind:
                c[1] += 1
                return
        for c in m.cells:
            if c[1] == 0:
                c[0], c[1] = kind, 1
                return
        raise AssertionError('no room')

    @staticmethod
    def flush(m):
        if m.cache is not None and m.cache[0] == 'done' and m.take + m.cache[1] <= 50:
            m.take += m.cache[1]
            m.cache = None

    # ---------- 传送带 ----------
    def settle(self, b):
        cells, t = b.cells, self.t
        for j in range(len(cells) - 2, -1, -1):
            e = cells[j]
            if e is not None and cells[j + 1] is None and t - e >= 8:
                cells[j + 1] = t
                cells[j] = None

    def ready(self, b):
        e = b.cells[-1]
        return e is not None and self.t - e >= 8

    def core_room(self, kind):
        if not self.accept[kind]:
            return False
        left = self.cap_left[kind]
        return left is None or left > 0

    def receive_group(self, dst):
        """临时规则第1条：dst 的全部元件上游一起判定，按收货轮询收下。"""
        if dst == '核心':
            ins, cur = self.core_in, getattr(self, 'core_cursor', None)
        else:
            m = self.mach[dst]
            ins, cur = m.ins, m.cursor
        n = len(ins)
        start = 0
        if cur is not None and cur in ins:
            start = (ins.index(cur) + 1) % n
        for k in range(n):
            b = ins[(start + k) % n]
            self.judged.add(b.idx)
            if not self.ready(b):
                continue
            if dst == '核心':
                if not self.core_room(b.kind):
                    continue
                self.delivered[b.kind] += 1
                if self.cap_left[b.kind] is not None:
                    self.cap_left[b.kind] -= 1
                self.core_cursor = b
            else:
                if not self.room(m, b.kind):
                    continue
                self.put(m, b.kind)
                m.cursor = b
            b.cells[-1] = None
            self.settle(b)

    def step(self):
        t = self.t
        # 1. 结束到时的制造
        for m in self.mach.values():
            if not m.on and m.cache is not None and m.cache[0] == 'run':
                m.cache = ('run', m.cache[1] + 1)  # 关着：进度保留（调试用，默认全开不触发）
                continue
            if m.cache is not None and m.cache[0] == 'run' and m.cache[1] == t:
                m.cache = ('done', m.qty)
                self.flush(m)
        # 2. 带内前移
        for b in self.belts:
            if len(b.cells) > 1:
                self.settle(b)
        # 3. 元件判定
        self.judged = set()
        for b in self.elem_order:
            if b.idx in self.judged:
                continue
            if self.ready(b):
                self.receive_group(b.dst)
            else:
                self.judged.add(b.idx)
        # 拒收计数：判定后尾格仍有成熟货
        for b in self.belts:
            if self.ready(b):
                b.rej += 1
        # 4. 非运输单位判定
        for u in self.nt_order:
            if isinstance(u, Mach):
                if u.take <= 0:
                    continue
            order = sorted(u.outs, key=lambda b: (u.last.get(b.idx, NEVER), b.conn_in))
            for b in order:
                if b.cells[0] is None:
                    b.cells[0] = t
                    b.sent += 1
                    u.last[b.idx] = t
                    if isinstance(u, Mach):
                        u.take -= 1
                        self.flush(u)
                    else:
                        u.sent += 1
                    break
        # 5. 开始能开始的制造
        for m in self.mach.values():
            if m.cache is None and m.on:
                ok = True
                for k, a in m.inputs.items():
                    cnt = 0
                    for c in m.cells:
                        if c[0] == k:
                            cnt = c[1]
                    if cnt < a:
                        ok = False
                        break
                if ok:
                    for k, a in m.inputs.items():
                        for c in m.cells:
                            if c[0] == k:
                                c[1] -= a
                                if c[1] == 0:
                                    c[0] = None
                    m.cache = ('run', t + m.dur)
        if self.check:
            self.invariants()
        self.t += 1

    def invariants(self):
        bad = []
        for m in self.mach.values():
            if m.role in ('contract', 'C', 'A', 'B', 'K'):
                if m.cache is None:
                    bad.append((m.name, 'cache_empty'))
            if m.role == 'contract':
                if m.take != 50:
                    bad.append((m.name, 'take', m.take))
                for k, a in m.inputs.items():
                    cnt = sum(c[1] for c in m.cells if c[0] == k)
                    if cnt < 50 - a:
                        bad.append((m.name, 'stock', k, cnt))
            if m.role == 'K' and m.take < 50 - m.qty:
                bad.append((m.name, 'Ktake', m.take))
            if m.role in ('B', 'K'):
                for k, a in m.inputs.items():
                    cnt = sum(c[1] for c in m.cells if c[0] == k)
                    if cnt < 49:
                        bad.append((m.name, 'stock', k, cnt))
            if m.role == 'B' and m.take < 49:
                bad.append((m.name, 'Btake', m.take))
        if bad:
            self.violations.extend((self.t, x) for x in bad[:5])

    # ---------- 状态 ----------
    def state(self):
        t = self.t
        out = []
        for m in self.mach.values():
            c = m.cache
            if c is None:
                cs = 0
            elif c[0] == 'run':
                cs = 1000 + (c[1] - t)
            else:
                cs = -c[1]
            out.append((tuple((x[0], x[1]) for x in m.cells), m.take, cs))
        for b in self.belts:
            out.append(tuple(-1 if e is None else min(8, t - e) for e in b.cells))
        for u in list(self.mach.values()) + list(self.src.values()):
            if len(u.outs) > 1:
                out.append(tuple(b.idx for b in sorted(u.outs, key=lambda b: (u.last.get(b.idx, NEVER), b.conn_in))))
        for m in self.mach.values():
            if len(m.ins) > 1:
                out.append(None if m.cursor is None else m.cursor.idx)
        cc = getattr(self, 'core_cursor', None)
        out.append(None if cc is None else cc.idx)
        return tuple(out)

    def snapshot_counts(self):
        return (self.delivered[BAT], self.delivered[CAP],
                tuple(b.sent for b in self.belts),
                tuple(b.rej for b in self.belts))


def run_case(seed, lengths='rand', maxlen=4, history='clear', disturb=True, age_reset=False,
             max_steps=200000, check=True, extra_offline=8, stops=6):
    f = Factory(seed, lengths=lengths, maxlen=maxlen, history=history, check=check)
    f.violations = []
    rng = random.Random(seed * 7919 + 1)
    events = []
    t_end_disturb = 0
    if disturb:
        # 随机安排离线与仓库停收、部分收货
        t = 0
        for _ in range(extra_offline + stops):
            t += rng.randint(50, 3000)
            kind = rng.choice(['off', 'off', 'stopB', 'stopC', 'stopBoth', 'capB', 'capC'])
            events.append((t, kind, rng.randint(1, 4000)))
        t_end_disturb = max(e[0] + e[2] for e in events) + 10
    ev = sorted(events)
    pending_reopen = []
    ei = 0
    while f.t < t_end_disturb:
        while ei < len(ev) and ev[ei][0] == f.t:
            _, kind, dur = ev[ei]
            if kind == 'off':
                keep = history == 'keep' or (history == 'mix' and rng.random() < 0.5)
                f.offline(keep, age_reset=age_reset)
            elif kind.startswith('stop'):
                ks = {'stopB': [BAT], 'stopC': [CAP], 'stopBoth': [BAT, CAP]}[kind]
                for k in ks:
                    f.accept[k] = False
                pending_reopen.append((f.t + dur, ks))
            elif kind.startswith('cap'):
                k = BAT if kind == 'capB' else CAP
                f.cap_left[k] = rng.randint(0, 3)
                pending_reopen.append((f.t + dur, [k]))
            ei += 1
        for (tt, ks) in list(pending_reopen):
            if tt == f.t:
                for k in ks:
                    f.accept[k] = True
                    if f.cap_left[k] is not None and rng.random() < 0.5:
                        f.cap_left[k] = rng.randint(0, 5)  # 玩家拿走少量，仍近满
                    else:
                        f.cap_left[k] = None
                pending_reopen.remove((tt, ks))
        f.step()
    for k in (BAT, CAP):
        f.accept[k] = True
        f.cap_left[k] = None
    # 之后协议核心一直收得下：找循环
    seen = {}
    while f.t < t_end_disturb + max_steps:
        h = hash(f.state())
        if h in seen:
            t1 = seen[h]
            p = f.t - t1
            s0 = f.state()
            c0 = f.snapshot_counts()
            for _ in range(p):
                f.step()
            if f.state() == s0:
                c1 = f.snapshot_counts()
                return dict(seed=seed, history=history, age_reset=age_reset, maxlen=maxlen,
                            cycle_start=f.t - p, period=p,
                            battery=c1[0] - c0[0], capsule=c1[1] - c0[1],
                            ore=[c1[2][i] - c0[2][i] for i in range(len(c0[2]))],
                            rej=[c1[3][i] - c0[3][i] for i in range(len(c0[3]))],
                            violations=f.violations[:20], nviol=len(f.violations),
                            events=len(events), f=f)
            seen = {}
        seen[h] = f.t
        f.step()
    return dict(seed=seed, period=None, violations=f.violations[:20], nviol=len(f.violations))
