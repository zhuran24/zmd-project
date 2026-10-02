#!/usr/bin/env python3
"""第97轮 T 组复核自写步进模拟器（不导入 sim2、不导入推导席脚本）。

按前提快照规则第23—33行加临时规则第1、2、4条：
- 每步：结束到时制造（并整批入取货格）→ 元件按层数、同层按最早送货通道接通先后判定 → 非运输单位判定 → 开始制造。
- 传送带连续段是一个元件；带内成熟物品只要下一格空就前移（随时），每进一格重新等 8 步。
- 收货（临时第1条）：非分流器元件真正把物品送往某单位时，触发该单位其他尚未判定的非分流器元件上游一起判定；
  被带动者做它自己的完整判定。机器、来源等非运输单位不被带动、在全部元件之后判定。
- 桥接器：每轴一个元件；“单位”按 bridge_unit_reading 选：False=按轴（每轴自成收货单位），True=按整台。
- 层数（临时第2条）：数层数不绕回自己；一个下游元件若除了送回来路外没有别的去向，不算“还往下送货”。
- 离线（临时第4条）：任意次序重建全部单位，接通时刻 = 两端建造时刻较大者，同刻随机打破；
  默认物品（含来源、货龄）、轮询记录、制造进度都保留；可选清空轮询记录 reset_poll、清空来源 reset_prev。
"""
from __future__ import annotations
import random

STEP_RES = 8  # 滞留 1 tick = 8 步


class Item:
    __slots__ = ('kind', 'entered', 'prev')

    def __init__(self, kind, entered, prev):
        self.kind, self.entered, self.prev = kind, entered, prev


class Chan:
    __slots__ = ('src', 'dst', 'conn', 'idx', 'back')

    def __init__(self, src, dst):
        self.src, self.dst, self.conn, self.idx, self.back = src, dst, None, None, False


class Node:
    is_element = False
    is_splitter = False
    is_belt = False

    def __init__(self, name):
        self.name = name
        self.outs = []      # Chan
        self.ins = []       # Chan
        self.cursor = None  # 元件：上次成功通道（Chan）
        self.in_cursor = None

    # 建造单位（用于接通时刻）：送出端、接收端各一个
    def out_unit(self):
        return self.name

    def in_unit(self):
        return self.name

    # 接收单位标识（来源记录 / 收货单位）
    def recv_unit(self):
        return self.name


class Belt(Node):
    is_element = True
    is_belt = True

    def __init__(self, name, n):
        super().__init__(name)
        self.cells = [None] * n

    def out_unit(self):
        return f'{self.name}#{len(self.cells)-1}'

    def in_unit(self):
        return f'{self.name}#0'

    def recv_unit(self):
        return f'{self.name}#0'

    def head(self):
        return self.cells[-1]

    def can_accept(self, item, w):
        return self.cells[0] is None

    def accept(self, item, w, src_unit):
        item.prev, item.entered = src_unit, w.t
        self.cells[0] = item
        w.settle(self)

    def pop(self, w):
        it = self.cells[-1]
        self.cells[-1] = None
        w.settle(self)
        return it

    def settle(self, t):
        c = self.cells
        for j in range(len(c) - 2, -1, -1):
            it = c[j]
            if it is not None and c[j + 1] is None and t - it.entered >= STEP_RES:
                it.prev, it.entered = f'{self.name}#{j}', t
                c[j + 1], c[j] = it, None


class Cell(Node):
    """单格特别运输单位的一个元件：桥接器一轴、准入口、分流器、汇流器。"""
    is_element = True

    def __init__(self, name, unit=None):
        super().__init__(name)
        self.item = None
        self.unit = unit or name   # 建造/来源用的单位名（桥接器两轴同名）

    def out_unit(self):
        return self.unit

    def in_unit(self):
        return self.unit

    def recv_unit(self):
        return self.unit

    def head(self):
        return self.item

    def can_accept(self, item, w):
        return self.item is None

    def accept(self, item, w, src_unit):
        item.prev, item.entered = src_unit, w.t
        self.item = item

    def pop(self, w):
        it, self.item = self.item, None
        return it


class Splitter(Cell):
    is_splitter = True


class Merger(Cell):
    pass


class Gate(Cell):
    """物品准入口：kind=None 不设放行种类；per5=每 5 tick 上限（None 不设）。"""

    def __init__(self, name, kind=None, per5=None):
        super().__init__(name)
        self.kind, self.per5 = kind, per5
        self.win_start, self.win_count = None, 0

    def can_accept(self, item, w):
        if self.item is not None:
            return False
        if self.kind is not None and item.kind != self.kind:
            return False
        if self.per5 is not None:
            if self.win_start is not None and w.t - self.win_start < 40 and self.win_count >= self.per5:
                return False
        return True

    def accept(self, item, w, src_unit):
        if self.per5 is not None:
            if self.win_start is None or w.t - self.win_start >= 40:
                self.win_start, self.win_count = w.t, 0
            self.win_count += 1
        super().accept(item, w, src_unit)


class Source(Node):
    def __init__(self, name, kind):
        super().__init__(name)
        self.kind = kind
        self.last_success = {}

    def ready(self):
        return True

    def take(self, w):
        return Item(self.kind, w.t, self.name)


class Sink(Node):
    def __init__(self, name):
        super().__init__(name)
        self.open = True
        self.got = 0

    def can_accept(self, item, w):
        return self.open

    def accept(self, item, w, src_unit):
        self.got += 1


class Machine(Node):
    """制造单位。recipe: ({kind: n}, product, qty, dur_steps)。nslots: 存货物品格数。"""

    def __init__(self, name, recipe, nslots=1):
        super().__init__(name)
        self.ing, self.prod, self.qty, self.dur = recipe
        self.slots = [[None, 0] for _ in range(nslots)]
        self.out_kind, self.out_n = None, 0
        self.cache = None            # None / ('run', remaining) / ('done',)
        self.powered = True
        self.last_success = {}       # Chan -> 上次成功的步
        self.starts = []

    def slot_for(self, kind):
        for s in self.slots:
            if s[0] == kind and s[1] > 0:
                return s if s[1] < 50 else None
        for s in self.slots:
            if s[1] == 0:
                return s
        return None

    def inv(self, kind):
        for s in self.slots:
            if s[0] == kind and s[1] > 0:
                return s[1]
        return 0

    def can_accept(self, item, w):
        return self.slot_for(item.kind) is not None

    def accept(self, item, w, src_unit):
        s = self.slot_for(item.kind)
        s[0] = item.kind
        s[1] += 1

    def ready(self):
        return self.out_n > 0

    def take(self, w):
        assert self.out_n > 0
        self.out_n -= 1
        it = Item(self.out_kind, w.t, self.name)
        if self.out_n == 0:
            self.out_kind = None
        self.flush()
        return it

    def flush(self):
        if self.cache == ('done',) and self.out_n + self.qty <= 50 and self.out_kind in (None, self.prod):
            self.out_kind = self.prod
            self.out_n += self.qty
            self.cache = None

    def complete(self, w):
        if self.cache is not None and self.cache[0] == 'run' and self.powered:
            r = self.cache[1] - 1
            self.cache = ('done',) if r == 0 else ('run', r)
        self.flush()

    def start(self, w):
        if not self.powered or self.cache is not None:
            return
        if all(self.inv(k) >= n for k, n in self.ing.items()):
            for k, n in self.ing.items():
                for s in self.slots:
                    if s[0] == k and s[1] > 0:
                        s[1] -= n
                        if s[1] == 0:
                            s[0] = None
                        break
            self.cache = ('run', self.dur)
            self.starts.append(w.t)

    def cache_nonempty(self):
        return self.cache is not None


class World:
    def __init__(self, nodes, rng, bridge_unit_reading=False, layers=None):
        self.nodes = list(nodes)
        self.by = {n.name: n for n in self.nodes}
        self.t = 0
        self.rng = rng
        self.bridge_unit_reading = bridge_unit_reading
        self.elements = [n for n in self.nodes if n.is_element]
        self.nontransport = [n for n in self.nodes if not n.is_element]
        self.machines = [n for n in self.nodes if isinstance(n, Machine)]
        self.belts = [n for n in self.nodes if n.is_belt]
        self.chans = [c for n in self.nodes for c in n.outs]
        self.layers = layers or compute_layers(self.elements)
        self.judged = set()
        self.log_out_of_order = 0
        self.hooks_after_element = []
        self.offline_build()

    # ---------- 建造与接通 ----------
    def build_units(self):
        us = []
        for n in self.nodes:
            if n.is_belt:
                us += [f'{n.name}#{j}' for j in range(len(n.cells))]
            elif isinstance(n, Cell):
                us.append(n.unit)
            else:
                us.append(n.name)
        return sorted(set(us))

    def offline_build(self, order=None, reset_poll=False, reset_prev=False):
        units = self.build_units()
        if order is None:
            order = units[:]
            self.rng.shuffle(order)
        b = {u: i for i, u in enumerate(order)}
        for c in self.chans:
            c.conn = (max(b[c.src.out_unit()], b[c.dst.in_unit()]), self.rng.random())
        for n in self.nodes:
            n.outs.sort(key=lambda c: c.conn)
            n.ins.sort(key=lambda c: c.conn)
        if reset_poll:
            for n in self.nodes:
                n.cursor = None
                n.in_cursor = None
                if hasattr(n, 'last_success'):
                    n.last_success = {}
        if reset_prev:
            for n in self.nodes:
                for it in self.items_of(n):
                    it.prev = None
        def first_send(n):
            return min((c.conn for c in n.outs), default=(10**9, 0))
        self.order_el = sorted(self.elements, key=lambda n: (self.layers[n.name], first_send(n)))
        self.order_nt = sorted(self.nontransport, key=first_send)

    def items_of(self, n):
        if n.is_belt:
            return [x for x in n.cells if x is not None]
        if isinstance(n, Cell):
            return [n.item] if n.item is not None else []
        return []

    def settle(self, belt):
        belt.settle(self.t)

    # ---------- 收货单位与上游 ----------
    def recv_key(self, n):
        if isinstance(n, Cell) and self.bridge_unit_reading:
            return n.unit
        return n.name

    def upstream_group(self, dst):
        key = self.recv_key(dst)
        mem = []
        for n in self.elements:
            if n.is_splitter:
                continue
            for c in n.outs:
                if self.recv_key(c.dst) == key:
                    mem.append(n)
                    break
        return mem

    # ---------- 判定 ----------
    def out_order(self, n):
        outs = n.outs
        if not outs:
            return []
        if n.cursor is None:
            start = 1 if (n.is_splitter or isinstance(n, Merger)) and len(outs) > 1 else 0
        else:
            start = (outs.index(n.cursor) + 1) % len(outs)
        return outs[start:] + outs[:start]

    def judge_element(self, n, joint=False):
        if n.name in self.judged:
            return
        self.judged.add(n.name)
        it = n.head()
        if it is None or self.t - it.entered < STEP_RES:
            return
        for c in self.out_order(n):
            dst = c.dst
            if it.prev == dst.recv_unit():
                continue  # 不能移回刚离开的单位：不算往它送货
            # 真正往 dst 送货：带动 dst 其余尚未判定的非分流器元件上游
            if not n.is_splitter:
                for m in self.upstream_group(dst):
                    if m.name not in self.judged:
                        if joint:
                            pass
                        mh = m.head()
                        if mh is not None and self.t - mh.entered >= STEP_RES:
                            # 记录被提前带动且手里有成熟货的情形
                            self.log_out_of_order += 1
                        self.judge_element(m, joint=True)
            if dst.can_accept(it, self):
                n.pop(self)
                dst.accept(it, self, n.out_unit())
                n.cursor = c
                return
        return

    def judge_nt(self, n):
        if isinstance(n, Sink) or not n.outs:
            return
        if not n.ready():
            return
        # 非运输单位取货侧：先试上次成功最早的；从未成功的按接通先后排最前
        outs = sorted(n.outs, key=lambda c: (n.last_success.get(c, -10**9), c.conn))
        for c in outs:
            probe = Item(getattr(n, 'out_kind', None) or getattr(n, 'kind', None), self.t, n.name)
            if c.dst.can_accept(probe, self):
                it = n.take(self)
                c.dst.accept(it, self, n.out_unit())
                n.last_success[c] = self.t
                return

    def step(self):
        self.judged = set()
        for m in self.machines:
            m.complete(self)
        for b in self.belts:
            b.settle(self.t)
        for n in self.order_el:
            self.judge_element(n)
            for h in self.hooks_after_element:
                h(self, n)
        for n in self.order_nt:
            self.judge_nt(n)
        for m in self.machines:
            m.start(self)
        self.t += 1


def link(a, b):
    c = Chan(a, b)
    a.outs.append(c)
    b.ins.append(c)
    return c


def compute_layers(elements):
    """临时第2条：同轴相邻桥之间来回的反向通道不参与数层数（不算成环）；
    其余数法不绕回已经过的元件；有“还往下送货”的下游元件但全部数法都绕回时该数法不可用。"""
    def fwd(u):
        return [c for c in u.outs if not getattr(c, 'back', False)]

    def count(u, visited):
        opts = []
        has_sending = False
        for c in fwd(u):
            v = c.dst
            if not v.is_element or not fwd(v):
                continue
            has_sending = True
            if v.name in visited or v is u:
                continue
            r = count(v, visited | {u.name})
            if r is not None:
                opts.append(r + 1)
        if opts:
            assert len(set(opts)) == 1, (u.name, opts)
            return opts[0]
        return None if has_sending else 1

    out = {}
    for n in elements:
        r = count(n, frozenset())
        assert r is not None, ('层数无法确定', n.name)
        out[n.name] = r
    return out
