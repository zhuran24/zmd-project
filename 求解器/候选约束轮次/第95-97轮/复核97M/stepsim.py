"""复核97M 本席独立步进模拟器（不导入 sim2 或推导席脚本）。
按快照规则第 23—33 行加临时规则第 1、2 条：
  * 每步：结束到时制造 -> 判定（元件按层数、同层按送货通道最早接通；再非运输单位）-> 开始制造；
  * 元件内物品“一直尝试移动”：步首与每次移出后，成熟（同格停留>=8 步）且前格空即前移；
  * 收货（临时 1）：非分流器元件轮到时，若手里有成熟、可送往其收货单位 R 的物品，则 R 的全部尚未判定的
    非分流器元件上游一起判定，R 按收货游标轮询收下；否则只本元件判定；非运输单位不被带动；
  * 收货单位 R 的身份：桥接器按轴（unit_mode='axis'）或按整个桥接器（unit_mode='unit'）；
  * 不移回刚离开的单位（按单位，不按元件）。
"""
from dataclasses import dataclass, field
import itertools

@dataclass(eq=False)
class Item:
    kind: str
    entered: int
    prev: object = None   # 刚离开的“单位”键

class Elem:
    """元件：cells 为物品格列表（传送带多格，其他一格）；unit 为所属单位键。"""
    transport = True
    def __init__(self, name, n=1, splitter=False, unit=None):
        self.name = name; self.cells = [None]*n; self.splitter = splitter
        self.unit = unit if unit is not None else name
        self.outs = []; self.ins = []      # 通道 (src, dst, conn)
        self.out_cursor = None; self.in_cursor = 0
    def head_free(self): return self.cells[0] is None
    def ready(self, t):
        it = self.cells[-1]
        return it if it is not None and t - it.entered >= 8 else None
    def accept(self, item, t):
        return self.cells[0] is None
    def put(self, item, t):
        self.cells[0] = item
    def pop(self):
        self.cells[-1] = None
    def settle(self, t):
        for j in range(len(self.cells)-2, -1, -1):
            it = self.cells[j]
            if it is not None and self.cells[j+1] is None and t - it.entered >= 8:
                self.cells[j+1], self.cells[j] = it, None
                it.entered = t
    def state(self):
        return tuple(None if c is None else (c.kind, c.entered, c.prev) for c in self.cells)

class NT:
    transport = False
    def __init__(self, name):
        self.name = name; self.unit = name; self.outs = []; self.ins = []; self.in_cursor = 0; self.out_cursor = 0

class Source(NT):
    def __init__(self, name, kind): super().__init__(name); self.kind = kind
    def ready(self, t): return Item(self.kind, t)
    def pop(self): pass
    def state(self): return (self.out_cursor,)

class Sink(NT):
    def __init__(self, name, pattern=lambda t: True):
        super().__init__(name); self.pattern = pattern; self.got = []
    def accept(self, item, t): return self.pattern(t)
    def put(self, item, t): self.got.append((t, item.kind))
    def ready(self, t): return None
    def state(self): return (len(self.got),)

class Machine(NT):
    """recipes: [(dict 原料->件数, 产物, 件数, 时长步)]；slots 个存货物品格。"""
    def __init__(self, name, recipes, slots=1, on=True):
        super().__init__(name); self.recipes = recipes; self.slots = [[] for _ in range(slots)]
        self.out = []; self.cache = []; self.running = None; self.remain = 0; self.on = on
        self.starts = []; self.cache_empty_steps = []
    def accept(self, item, t):
        for s in self.slots:
            if s and s[0] == item.kind: return len(s) < 50
        return any(not s for s in self.slots)
    def put(self, item, t):
        for s in self.slots:
            if s and s[0] == item.kind: s.append(item.kind); return
        for s in self.slots:
            if not s: s.append(item.kind); return
        raise AssertionError
    def ready(self, t): return Item(self.out[0], t) if self.out else None
    def pop(self):
        self.out.pop(0); self.flush()
    def flush(self):
        if self.cache and self.running is None:
            k = self.cache[0]
            if len(self.out) + len(self.cache) <= 50 and (not self.out or self.out[0] == k):
                self.out.extend(self.cache); self.cache = []
    def complete(self, t):
        if self.running is not None and self.on:
            self.remain -= 1
            if self.remain == 0:
                _, prod, q, _ = self.running
                self.cache = [prod]*q; self.running = None
                self.flush()
    def start(self, t):
        if not self.on or self.running is not None or self.cache: return
        have = {s[0]: len(s) for s in self.slots if s}
        for r in self.recipes:
            ing, prod, q, dur = r
            if all(have.get(k, 0) >= n for k, n in ing.items()):
                for k, n in ing.items():
                    for s in self.slots:
                        if s and s[0] == k: del s[:n]
                self.running = r; self.remain = dur; self.cache = ['@']*1  # 缓存非空标记：在制一批
                self.cache_running = True
                self.starts.append((t, prod))
                return
    def cache_nonempty(self):
        return self.running is not None or bool(self.cache)
    def state(self):
        return (tuple(tuple(s) for s in self.slots), tuple(self.out), tuple(self.cache), None if self.running is None else (self.running[1], self.remain))

class World:
    def __init__(self, units, unit_mode='axis'):
        self.units = units; self.t = 0; self.unit_mode = unit_mode; self.conn = itertools.count()
        self.elems = [u for u in units if u.transport]
        self.nts = [u for u in units if not u.transport]
        self.order = None
        self.cursors = {}
    def connect(self, src, dst, conn=None):
        c = (src, dst, next(self.conn) if conn is None else conn)
        src.outs.append(c); dst.ins.append(c); return c
    def rkey(self, dst):
        """收货单位键：按轴时为元件本身，按单位时为所属单位。"""
        if not dst.transport: return dst
        return dst if self.unit_mode == 'axis' else dst.unit
    def layers(self):
        L = {}
        def lay(e, seen):
            if e in L: return L[e]
            # 合资格下游：还有向外通道的运输元件，不绕回自己
            ds = [d for (_, d, _) in e.outs if d.transport and d.outs and d not in seen]
            if not ds: v = 1
            else:
                assert len({id(d) for d in ds}) == 1 or e.splitter, e.name
                v = 1 + min(lay(d, seen | {e}) for d in ds)  # 本模拟只用无分叉或固定选支
            L[e] = v; return v
        for e in self.elems: lay(e, frozenset())
        return L
    def default_order(self):
        L = self.layers()
        es = sorted(self.elems, key=lambda e: (L[e], min((c[2] for c in e.outs), default=10**9)))
        ns = sorted(self.nts, key=lambda u: min((c[2] for c in u.outs), default=10**9))
        return es + ns
    # ---- 移动 ----
    def try_send(self, c):
        src, dst, _ = c
        it = src.ready(self.t)
        if it is None: return False
        if it.prev is not None and it.prev == dst.unit: return False
        if not dst.accept(it, self.t): return False
        src.pop()
        if src.transport: src.settle(self.t)
        if not src.transport:
            it = Item(it.kind, self.t)
        it.prev = src.unit; it.entered = self.t
        dst.put(it, self.t)
        return True
    nt_rule = 'earliest'
    trigger_capacity = False   # True：“往它送货”另要求收货格此刻收得下（另一读法）
    def sendable_to(self, e, R):
        it = e.ready(self.t)
        if it is None: return False
        if it.prev is not None and it.prev == (R.unit if hasattr(R, 'unit') else R): return False
        return R.accept(it, self.t) if self.trigger_capacity else True
    def step(self, order=None):
        order = order or self.order or self.default_order()
        t = self.t
        for m in self.nts:
            if isinstance(m, Machine): m.complete(t)
        for e in self.elems: e.settle(t)
        judged = set()
        for u in order:
            if u in judged: continue
            if u.transport and not u.splitter and u.outs:
                (_, dst, _), = u.outs
                R = self.rkey(dst)
                if self.sendable_to(u, dst):
                    allc = sorted([c2 for x in self.units for c2 in x.ins if self.rkey(x) == R], key=lambda c2: c2[2])
                    k = getattr(R, 'in_cursor', 0) if not isinstance(R, str) else self.cursors.setdefault(R, 0)
                    k = k % len(allc)
                    rot = allc[k:] + allc[:k]
                    # 被带动的只有尚未判定的非分流器元件上游；按收货单位的轮询次序尝试
                    group = [c for c in rot if c[0].transport and not c[0].splitter and c[0] not in judged]
                    for c in group: judged.add(c[0])
                    for c in group:
                        if self.try_send(c):
                            allc = sorted([c2 for x in self.units for c2 in x.ins if self.rkey(x) == R], key=lambda c2: c2[2])
                            nk = (allc.index(c) + 1) % len(allc)
                            if isinstance(R, str): self.cursors[R] = nk
                            else: R.in_cursor = nk
                else:
                    judged.add(u)
            elif u.transport and u.splitter:
                judged.add(u)
                outs = sorted(u.outs, key=lambda c: c[2])
                cur = u.out_cursor if u.out_cursor is not None else (1 if len(outs) > 1 else 0)
                for j in range(len(outs)):
                    c = outs[(cur+j) % len(outs)]
                    if self.try_send(c):
                        u.out_cursor = (cur+j+1) % len(outs); break
            elif u.transport:
                judged.add(u)
            else:
                judged.add(u)
                outs = sorted(u.outs, key=lambda c: c[2])
                if outs and self.nt_rule == 'earliest':
                    # 规则第 32 行：非运输单位取货侧先试上次成功最早的，从未成功的按接通先后排最前
                    last = getattr(u, 'last_ok', None)
                    if last is None: last = u.last_ok = {}
                    for c in sorted(outs, key=lambda c: (last.get(c, -10**9), c[2])):
                        if self.try_send(c):
                            last[c] = self.t; break
                elif outs:
                    cur = u.out_cursor % len(outs)
                    for j in range(len(outs)):
                        c = outs[(cur+j) % len(outs)]
                        if self.try_send(c):
                            u.out_cursor = (cur+j+1) % len(outs); break
        for m in self.nts:
            if isinstance(m, Machine): m.start(t)
            if isinstance(m, Machine): m.cache_empty_steps.append(not m.cache_nonempty())
        self.t += 1
    def snapshot(self):
        return tuple((u.name, u.state(), getattr(u, 'in_cursor', None), getattr(u, 'out_cursor', None)) for u in self.units) + (tuple(sorted(self.cursors.items())),)
