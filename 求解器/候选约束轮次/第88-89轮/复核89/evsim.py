#!/usr/bin/env python3
"""第 89 轮复核自写的逐事件模拟器（只依据前提快照的规则句）。

时间用整数，单位 1/Q tick，所以任意有理相位（分母整除 Q）都能精确表示；
事件只发生在：运输格里的物品满 1 tick（滞留）、缓存格一批做完、准入口 5 tick 窗口走完、
下游（汇点）开关变化、测量边界。每个事件时刻做「同一时刻的判定做到没有可动为止」：
反复收集当前可成功的动作，按（随机或固定）次序逐个在仍可成功时执行，直到没有可动。
随机次序是全部合法判定次序的超集（不模拟轮询指针），用来找反例；结论要靠解析证明。

规则对应：
  运输格上限 1、至少停 1 tick（滞留）；移动零时（移动）；
  制造单位存货格：每格一种物品、上限 50、一种物品只占一格；存货格无种类限制（存货物品格）；
  缓存格：上一批整批进了取货格、存货够一批才开新批；做完后整批进取货格（取货格一种物品、上限 50）；
  开批即消耗用量，做完无冷却（制造）；
  物品准入口：放行种类、累计上限、每 5 tick 上限，窗口从收下第一件起算（物品准入口）。
"""
import random
import bisect

CAP = 50


class Gate:
    __slots__ = ('fil', 'k5', 'win', 'wcnt', 'cum', 'ccnt')

    def __init__(self, fil=None, k5=None, cum=None):
        self.fil, self.k5, self.cum = fil, k5, cum
        self.win = None      # 窗口开始时刻
        self.wcnt = 0
        self.ccnt = 0

    def ok(self, kind, t, Q):
        if self.fil is not None and kind != self.fil:
            return False
        if self.cum is not None and self.ccnt >= self.cum:
            return False
        if self.k5 is not None and self.win is not None and t < self.win + 5 * Q and self.wcnt >= self.k5:
            return False
        return True

    def take(self, t, Q):
        self.ccnt += 1
        if self.k5 is not None:
            if self.win is None or t >= self.win + 5 * Q:
                self.win, self.wcnt = t, 0
            self.wcnt += 1


class Cell:
    __slots__ = ('kind', 'entry', 'gate', 'name')

    def __init__(self, name='', gate=None):
        self.kind, self.entry, self.gate, self.name = None, None, gate, name


class Source:
    """仓库出口：取货端口连着仓库某物品格，矿石持续可得。"""
    __slots__ = ('kind', 'name')

    def __init__(self, kind, name=''):
        self.kind, self.name = kind, name


class Sink:
    """协议核心存货端口或任意下游：按时刻表收或不收。sched(t)->bool。"""
    __slots__ = ('sched', 'name', 'got', 'toggles')

    def __init__(self, sched=None, name='', toggles=None):
        self.sched = sched or (lambda t: True)
        self.name, self.got = name, 0
        self.toggles = toggles     # 可选：返回 >t 的下一个开关时刻的函数


class Recipe:
    __slots__ = ('ins', 'out', 'n', 'd')

    def __init__(self, ins, out, n, d):
        self.ins, self.out, self.n, self.d = dict(ins), out, n, d


class Machine:
    __slots__ = ('name', 'recipes', 'ngrid', 'grid', 'out', 'cache', 'exits', 'starts', 'clears')

    def __init__(self, name, recipes, ngrid=1):
        self.name, self.recipes, self.ngrid = name, recipes, ngrid
        self.grid = [None] * ngrid          # 每格 [kind, count]
        self.out = None                     # [kind, count]
        self.cache = None                   # [recipe, done_time]
        self.exits = []
        self.starts = 0
        self.clears = 0

    def stock(self, kind):
        for g in self.grid:
            if g is not None and g[0] == kind:
                return g[1]
        return 0

    def can_accept(self, kind):
        for g in self.grid:
            if g is not None and g[0] == kind:
                return g[1] < CAP
        return any(g is None for g in self.grid)

    def accept(self, kind):
        for g in self.grid:
            if g is not None and g[0] == kind:
                g[1] += 1
                return
        for i, g in enumerate(self.grid):
            if g is None:
                self.grid[i] = [kind, 1]
                return
        raise RuntimeError('accept')

    def startable(self):
        if self.cache is not None:
            return None
        for r in self.recipes:
            if all(self.stock(k) >= a for k, a in r.ins.items()):
                return r
        return None

    def do_start(self, r, t, Q):
        for k, a in r.ins.items():
            for i, g in enumerate(self.grid):
                if g is not None and g[0] == k:
                    g[1] -= a
                    if g[1] == 0:
                        self.grid[i] = None
        self.cache = [r, t + r.d * Q]
        self.starts += 1

    def clearable(self, t):
        if self.cache is None or self.cache[1] > t:
            return False
        r = self.cache[0]
        if self.out is None:
            return r.n <= CAP
        return self.out[0] == r.out and self.out[1] + r.n <= CAP

    def do_clear(self):
        r = self.cache[0]
        if self.out is None:
            self.out = [r.out, r.n]
        else:
            self.out[1] += r.n
        self.cache = None
        self.clears += 1


class Line:
    __slots__ = ('src', 'cells', 'dst', 'name', 'moved_in', 'delivered')

    def __init__(self, src, cells, dst, name=''):
        self.src, self.cells, self.dst, self.name = src, cells, dst, name
        self.moved_in = 0      # 从源头进首格的件数
        self.delivered = 0     # 从末格交出的件数
        if isinstance(src, Machine):
            src.exits.append(self)


class World:
    def __init__(self, Q, seed=0):
        self.Q = Q
        self.t = 0
        self.lines = []
        self.machines = []
        self.sinks = []
        self.rng = random.Random(seed)
        self.random_order = True
        self.marks = []          # 额外事件时刻（测量边界）
        self.observers = []      # 每个微步后回调 f(world)
        self.post = []           # 每个时刻闭合后回调

    def add_machine(self, m):
        self.machines.append(m); return m

    def add_line(self, l):
        self.lines.append(l)
        if isinstance(l.dst, Sink) and l.dst not in self.sinks:
            self.sinks.append(l.dst)
        return l

    # ---- 动作 ----
    def _cell_ok(self, c, kind, t):
        return c.kind is None and (c.gate is None or c.gate.ok(kind, t, self.Q))

    def _put(self, c, kind, t):
        c.kind, c.entry = kind, t
        if c.gate is not None:
            c.gate.take(t, self.Q)

    def gather(self):
        t, Q = self.t, self.Q
        acts = []
        for li, l in enumerate(self.lines):
            cs = l.cells
            # 源头 -> 首格
            c0 = cs[0]
            if c0.kind is None:
                s = l.src
                if isinstance(s, Source):
                    if self._cell_ok(c0, s.kind, t):
                        acts.append((0, li))
                elif s.out is not None and self._cell_ok(c0, s.out[0], t):
                    acts.append((0, li))
            # 格 -> 格
            for j in range(len(cs) - 1):
                a, b = cs[j], cs[j + 1]
                if a.kind is not None and a.entry + Q <= t and self._cell_ok(b, a.kind, t):
                    acts.append((1, li, j))
            # 末格 -> 终点
            e = cs[-1]
            if e.kind is not None and e.entry + Q <= t:
                d = l.dst
                if isinstance(d, Sink):
                    if d.sched(t):
                        acts.append((2, li))
                elif d.can_accept(e.kind):
                    acts.append((2, li))
        for mi, m in enumerate(self.machines):
            if m.clearable(t):
                acts.append((3, mi))
            elif m.cache is None and m.startable() is not None:
                acts.append((4, mi))
        return acts

    def enabled(self, a):
        t, Q = self.t, self.Q
        typ = a[0]
        if typ == 0:
            l = self.lines[a[1]]; c0 = l.cells[0]
            if c0.kind is not None:
                return False
            s = l.src
            if isinstance(s, Source):
                return self._cell_ok(c0, s.kind, t)
            return s.out is not None and self._cell_ok(c0, s.out[0], t)
        if typ == 1:
            l = self.lines[a[1]]; x, y = l.cells[a[2]], l.cells[a[2] + 1]
            return x.kind is not None and x.entry + Q <= t and self._cell_ok(y, x.kind, t)
        if typ == 2:
            l = self.lines[a[1]]; e = l.cells[-1]
            if e.kind is None or e.entry + Q > t:
                return False
            d = l.dst
            return d.sched(t) if isinstance(d, Sink) else d.can_accept(e.kind)
        if typ == 3:
            return self.machines[a[1]].clearable(t)
        if typ == 4:
            m = self.machines[a[1]]
            return m.cache is None and m.startable() is not None

    def apply(self, a):
        t, Q = self.t, self.Q
        typ = a[0]
        if typ == 0:
            l = self.lines[a[1]]; s = l.src
            if isinstance(s, Source):
                self._put(l.cells[0], s.kind, t)
            else:
                k = s.out[0]; s.out[1] -= 1
                if s.out[1] == 0:
                    s.out = None
                self._put(l.cells[0], k, t)
            l.moved_in += 1
        elif typ == 1:
            l = self.lines[a[1]]; x, y = l.cells[a[2]], l.cells[a[2] + 1]
            k = x.kind; x.kind = None; x.entry = None
            self._put(y, k, t)
        elif typ == 2:
            l = self.lines[a[1]]; e = l.cells[-1]; k = e.kind
            e.kind = None; e.entry = None
            d = l.dst
            if isinstance(d, Sink):
                d.got += 1
            else:
                d.accept(k)
            l.delivered += 1
        elif typ == 3:
            self.machines[a[1]].do_clear()
        elif typ == 4:
            m = self.machines[a[1]]
            m.do_start(m.startable(), t, Q)
        for f in self.observers:
            f(self, a)

    def closure(self):
        for f in self.observers:
            f(self, None)
        while True:
            acts = self.gather()
            if not acts:
                break
            if self.random_order:
                self.rng.shuffle(acts)
            for a in acts:
                if self.enabled(a):
                    self.apply(a)
        for f in self.post:
            f(self)

    def next_time(self, horizon):
        t, Q = self.t, self.Q
        best = horizon
        for l in self.lines:
            for c in l.cells:
                if c.kind is not None and c.entry + Q > t:
                    best = min(best, c.entry + Q)
                g = c.gate
                if g is not None and g.k5 is not None and g.win is not None and g.win + 5 * Q > t:
                    best = min(best, g.win + 5 * Q)
        for m in self.machines:
            if m.cache is not None and m.cache[1] > t:
                best = min(best, m.cache[1])
        for s in self.sinks:
            if s.toggles is not None:
                nt = s.toggles(t)
                if nt is not None:
                    best = min(best, nt)
        i = bisect.bisect_right(self.marks, t)
        if i < len(self.marks):
            best = min(best, self.marks[i])
        return best

    def run_until(self, T):
        """从当前时刻（已闭合）推进到 T（含 T 的闭合）。"""
        while True:
            nt = self.next_time(T)
            if nt > T:
                return
            self.t = nt
            self.closure()
            if nt == T:
                return

    # ---- 循环检测用的规范状态 ----
    def key(self, extra=()):
        t, Q = self.t, self.Q
        parts = []
        for l in self.lines:
            for c in l.cells:
                if c.kind is None:
                    parts.append(None)
                else:
                    parts.append((c.kind, max(0, c.entry + Q - t)))
                g = c.gate
                if g is not None:
                    if g.k5 is not None and g.win is not None and g.win + 5 * Q > t:
                        parts.append((g.win + 5 * Q - t, g.wcnt, g.ccnt if g.cum is not None else 0))
                    else:
                        parts.append((0, 0, g.ccnt if g.cum is not None else 0))
        for m in self.machines:
            parts.append(tuple(None if g is None else tuple(g) for g in m.grid))
            parts.append(None if m.out is None else tuple(m.out))
            parts.append(None if m.cache is None else (id(m.cache[0]), max(0, m.cache[1] - t)))
        parts.append(tuple(extra))
        return hash(tuple(parts))

    def find_cycle(self, T_max, extra_fn=lambda w: ()):
        """确定次序下推进，直到规范状态重复；返回 (t_first, period) 或 None。"""
        seen = {}
        while self.t <= T_max:
            k = self.key(extra_fn(self))
            if k in seen:
                return seen[k], self.t - seen[k]
            seen[k] = self.t
            nt = self.next_time(T_max + 1)
            if nt > T_max:
                return None
            self.t = nt
            self.closure()
        return None


def recipe_table():
    """快照「配方」一节的 18 个配方，按机型。"""
    R = Recipe
    return {
        '粉碎机': [R({'源矿': 1}, '源石粉末', 1, 1), R({'蓝铁块': 1}, '蓝铁粉末', 1, 1),
                 R({'荞花': 1}, '荞花粉末', 2, 1), R({'砂叶': 1}, '砂叶粉末', 3, 1)],
        '精炼炉': [R({'蓝铁矿': 1}, '蓝铁块', 1, 1), R({'致密蓝铁粉末': 1}, '钢块', 1, 1),
                 R({'蓝铁粉末': 1}, '蓝铁块', 1, 1)],
        '研磨机': [R({'蓝铁粉末': 2, '砂叶粉末': 1}, '致密蓝铁粉末', 1, 1),
                 R({'源石粉末': 2, '砂叶粉末': 1}, '致密源石粉末', 1, 1),
                 R({'荞花粉末': 2, '砂叶粉末': 1}, '细磨荞花粉末', 1, 1)],
        '塑形机': [R({'钢块': 2}, '钢质瓶', 1, 1)],
        '配件机': [R({'钢块': 1}, '钢制零件', 1, 1)],
        '种植机': [R({'荞花种子': 1}, '荞花', 1, 1), R({'砂叶种子': 1}, '砂叶', 1, 1)],
        '采种机': [R({'荞花': 1}, '荞花种子', 2, 1), R({'砂叶': 1}, '砂叶种子', 2, 1)],
        '封装机': [R({'钢制零件': 10, '致密源石粉末': 15}, '高容谷地电池', 1, 5)],
        '灌装机': [R({'钢质瓶': 10, '细磨荞花粉末': 10}, '精选荞愈胶囊', 1, 5)],
    }


NGRID = {'粉碎机': 1, '精炼炉': 1, '配件机': 1, '塑形机': 1, '种植机': 1, '采种机': 1,
         '研磨机': 2, '封装机': 2, '灌装机': 2}


def make_machine(name, typ):
    """按机型给全部配方；纯料专线保证实际只凑得齐一个配方。"""
    return Machine(name, recipe_table()[typ], NGRID[typ])


def periodic_sched(Q, period, on_len, phase):
    """在 [phase + nP, phase + nP + on_len) 收；返回 (sched, toggles)。"""
    def sched(t):
        return ((t - phase) % period) < on_len

    def toggles(t):
        r = (t - phase) % period
        if r < on_len:
            return t + (on_len - r)
        return t + (period - r)
    return sched, toggles
