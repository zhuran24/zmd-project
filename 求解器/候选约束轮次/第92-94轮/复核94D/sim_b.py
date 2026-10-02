# 编码乙：对象式、计数器递减、显式轮询队列、通用通道图与第 31 行「一起判定」。
# 复核94D 自写，与编码甲不共享代码，不导入推导席脚本与 sim2。
# 运输格：item（物品名或 None）、age（已停留步数，每步开头 +1，>=8 才能离开）、frm（上一单位名）。
# 机器：inp、out、busy（剩余步数，None 表示无进行中）、done（已完成未进取货格的件数）。
# 第 31 行两种读法：
#   cur：一个单位的非分流器元件上游，在其中最先判定者判定时一起判定；
#   new：在其中最先「往它送货」者判定时一起判定（手里没有能送往它的物品不算）。
# 元件判定次序由调用方给出（层数从小到大；无法确定时由调用方挑一种合法次序）。

class Cell:
    def __init__(self, name, unit=None, gate=None):
        self.name = name
        self.unit = unit or name      # 所属单位名（桥接器两轴同属一个单位）
        self.item = None
        self.age = 0
        self.frm = None
        self.outs = []                # 通往的目标（Cell / Machine / Sink）
        self.gate = gate              # None 或 dict(limit5=..)
        self.win_start = None
        self.win_count = 0

    def can_take(self, item, t, frm_unit):
        if self.item is not None:
            return False
        if self.gate is not None:
            g = self.gate
            if self.win_start is not None and t >= self.win_start + 40:
                self.win_start = None
                self.win_count = 0
            if self.win_start is not None and self.win_count >= g['limit5']:
                return False
        return True

    def take(self, item, t, frm_unit):
        self.item = item
        self.age = 0
        self.frm = frm_unit
        if self.gate is not None:
            if self.win_start is None:
                self.win_start = t
                self.win_count = 0
            self.win_count += 1


class Sink:
    def __init__(self, name, rule):
        self.name = name
        self.unit = name
        self.rule = rule   # rule(t) -> bool
        self.got = 0

    def can_take(self, item, t, frm_unit):
        return self.rule(t)

    def take(self, item, t, frm_unit):
        self.got += 1


class Machine:
    def __init__(self, name, item_in, item_out, batch, cap=50):
        self.name = name
        self.unit = name
        self.item_in = item_in
        self.item_out = item_out
        self.batch = batch
        self.cap = cap
        self.inp = 0
        self.out = 0
        self.busy = None
        self.done = 0
        self.outs = []      # 取货通道首格（Cell）列表
        self.queue = []     # 轮询队列：队首先试
        self.never = set()

    def can_start(self):
        return self.inp >= 1

    def do_start(self):
        self.inp -= 1

    def cache_nonempty(self):
        return self.busy is not None or self.done > 0

    def can_take(self, item, t, frm_unit):
        return item == self.item_in and self.inp < self.cap

    def take(self, item, t, frm_unit):
        self.inp += 1

    def flow(self):
        if self.done > 0 and self.out + self.done <= self.cap:
            self.out += self.done
            self.done = 0


class Net:
    def __init__(self, reading='cur'):
        self.cells = []
        self.machines = []
        self.order = None
        self.reading = reading
        self.t = 0
        self.log = []

    def upstream_groups(self):
        g = {}
        for c in self.cells:
            for o in c.outs:
                g.setdefault(id(o), []).append(c)
        return g

    def set_poll(self, m, queue):
        m.queue = list(queue)
        m.never = set(id(c) for c in queue)

    def offline(self, m, rnd):
        nev = [c for c in m.queue if id(c) in m.never]
        rest = [c for c in m.queue if id(c) not in m.never]
        rnd.shuffle(nev)
        m.queue = nev + rest

    def try_send(self, c, t):
        """元件 c 的一次判定。"""
        if c.item is None or c.age < 8:
            return False
        for o in c.outs:
            if o.unit == c.frm:
                continue
            if o.can_take(c.item, t, c.unit):
                o.take(c.item, t, c.unit)
                c.item = None
                return True
        return False

    def wants(self, c, o):
        return c.item is not None and c.age >= 8 and o.unit != c.frm

    def step(self, ext=None):
        self.t += 1
        t = self.t
        # 开头：运输格停留 +1
        for c in self.cells:
            if c.item is not None:
                c.age += 1
        # 1 结束到时的制造
        for m in self.machines:
            if m.busy is not None:
                m.busy -= 1
                if m.busy == 0:
                    m.busy = None
                    m.done = m.batch
            m.flow()
        if ext is not None:
            ext(self, t)
        # 2 元件判定
        groups = self.upstream_groups()
        judged = set()
        for c in self.order:
            if id(c) in judged:
                continue
            pulled = []
            for o in c.outs:
                if self.reading == 'cur' or self.wants(c, o):
                    for u in groups.get(id(o), []):
                        if u is not c and id(u) not in judged:
                            pulled.append(u)
            judged.add(id(c))
            self.try_send(c, t)
            for u in pulled:
                if id(u) in judged:
                    continue
                judged.add(id(u))
                self.try_send(u, t)
        # 3 非运输单位判定
        for m in self.machines:
            if m.out <= 0 or not m.queue:
                continue
            for c in list(m.queue):
                if c.can_take(m.item_out, t, m.unit):
                    c.take(m.item_out, t, m.unit)
                    m.out -= 1
                    m.queue.remove(c)
                    m.queue.append(c)
                    m.never.discard(id(c))
                    m.flow()
                    break
        # 4 开始制造
        for m in self.machines:
            if m.busy is None and m.done == 0 and m.can_start():
                m.do_start()
                m.busy = 8


def path(net, name, n, src, dst, unit_prefix=None):
    cs = [Cell(f'{name}{i}') for i in range(n)]
    for i in range(n - 1):
        cs[i].outs = [cs[i + 1]]
    cs[-1].outs = [dst]
    net.cells += cs
    src.outs.append(cs[0])
    if isinstance(src, Machine):
        src.queue.append(cs[0])
        src.never.add(id(cs[0]))
    return cs


def chain_order(paths):
    """多条纯链：各链下游先（层数=到链尾的格数）。"""
    order = []
    mx = max(len(p) for p in paths)
    for lay in range(mx):
        for p in paths:
            if lay < len(p):
                order.append(p[len(p) - 1 - lay])
    return order


def plant_unit(L1, L2, L3, L4, k, kpaths, reading='cur'):
    """建一个采种单元。kpaths: K 的取货通道，每项 (格数, 末端 Sink)。"""
    net = Net(reading)
    C = Machine('C', 'plant', 'seed', 2)
    A = Machine('A', 'seed', 'plant', 1)
    B = Machine('B', 'seed', 'plant', 1)
    K = Machine('K', 'plant', 'powder', k)
    net.machines = [A, B, C, K]
    CA = path(net, 'CA', L1, C, A)
    CB = path(net, 'CB', L3, C, B)
    AC = path(net, 'AC', L2, A, C)
    BK = path(net, 'BK', L4, B, K)
    KP = []
    for i, (n, sink) in enumerate(kpaths):
        KP.append(path(net, f'K{i}_', n, K, sink))
    net.order = chain_order([CA, CB, AC, BK] + KP)
    net.C, net.A, net.B, net.K = C, A, B, K
    net.CA, net.CB, net.AC, net.BK, net.KP = CA, CB, AC, BK, KP
    return net


def phi2(net):
    v = 2 * sum(c.item is not None for c in net.CA) + 2 * net.A.inp + 2 * net.A.out
    v += 2 * sum(c.item is not None for c in net.AC) + 2 * net.C.inp
    v += 2 * net.A.cache_nonempty() + 2 * net.C.cache_nonempty() + net.C.out
    return v
