"""Independent rational-time, closed-event model of pure dedicated paths.

Times are exact integers in units of 1/q tick, with no rounding of events.
This is a logical model, NOT a geometric factory certificate.
"""
from dataclasses import dataclass, field
import random


@dataclass
class Machine:
    name: str
    need: tuple
    k: int = 1
    d: int = 1
    stock: list = field(default_factory=list)
    output: int = 0
    due: object = None
    incoming: list = field(default_factory=list)
    outgoing: list = field(default_factory=list)
    ip: int = 0
    op: int = 0
    starts: int = 0
    released: int = 0
    enabled: bool = True
    paused_remaining: object = None


@dataclass
class Line:
    source: object
    target: object
    slot: int
    cells: list
    label: str
    accepted: int = 0
    delivered: int = 0
    gate_every: object = None
    gate_due: int = 0


class Model:
    def __init__(self, q=1, seed=0, capacity=50):
        self.q = q
        self.rng = random.Random(seed)
        self.cap = capacity
        self.machines = []
        self.lines = []
        self.actions = []
        self.t = 0
        self.sink = lambda j, t: True
        self.moves = []
        self.empty = []
        self.closures = 0

    def machine(self, name, need=(1,), k=1, d=1):
        i = len(self.machines)
        self.machines.append(Machine(name, tuple(need), k, d, [0]*len(need)))
        return i

    def line(self, src, dst, slot=0, length=1, label=''):
        assert length>=1
        i = len(self.lines)
        self.lines.append(Line(src, dst, slot, [None]*length, label))
        if src is not None:
            self.machines[src].outgoing.append(i)
        if dst is not None:
            self.machines[dst].incoming.append(i)
        return i

    def prepare(self):
        self.actions = []
        for i, m in enumerate(self.machines):
            self.actions.extend([('make', i), ('in', i), ('out', i)])
        for j, line in enumerate(self.lines):
            if line.source is None:
                self.actions.append(('source', j))
            if line.target is None:
                self.actions.append(('sink', j))
            self.actions += [('hop', j, c) for c in range(len(line.cells)-1)]
        self.rng.shuffle(self.actions)

    def randomize(self, mode='dense'):
        def qty():
            if mode=='low':
                return self.rng.choice([0, 0, 0, 1, 1, 2])
            return self.rng.choice([0, 1, 2, self.cap, self.cap-1,
                                    self.rng.randrange(self.cap+1)])
        for m in self.machines:
            m.stock = [qty() for _ in m.need]
            m.output = qty()
            m.due = self.rng.choice([None, 0, self.rng.randint(1, m.d*self.q)])
            m.ip = self.rng.randrange(len(m.incoming)) if m.incoming else 0
            m.op = self.rng.randrange(len(m.outgoing)) if m.outgoing else 0
        for line in self.lines:
            line.cells = [self.rng.choice([None, None, 0, self.rng.randint(1, self.q)])
                          for _ in line.cells]

    def can_take(self, line):
        return line.cells[0] is None and (line.gate_every is None or self.t>=line.gate_due)

    def pause_unfinished(self, i):
        m = self.machines[i]
        assert m.enabled and m.due is not None and m.due>self.t
        m.enabled = False
        m.paused_remaining = m.due-self.t

    def take(self, j):
        line = self.lines[j]
        assert self.can_take(line)
        line.cells[0] = self.t+self.q
        if line.gate_every is not None:
            line.gate_due = self.t+line.gate_every*self.q
        line.accepted += 1
        self.moves.append((self.t, j))

    def act(self, a):
        kind, i = a[:2]
        t = self.t
        if kind=='make':
            m = self.machines[i]
            if not m.enabled:
                # This branch is used only for the unfinished-cache witness.
                assert m.paused_remaining is not None and m.paused_remaining>0
                return False
            if m.due is not None and m.due<=t and m.output+m.k<=self.cap:
                m.output += m.k
                m.due = None
                m.released += 1
                return True
            if m.due is None and all(n>=v for n, v in zip(m.stock, m.need)):
                m.stock = [n-v for n, v in zip(m.stock, m.need)]
                m.due = t+m.d*self.q
                m.starts += 1
                return True
            return False
        if kind=='in':
            m = self.machines[i]
            for z in range(len(m.incoming)):
                ix = (m.ip+z)%len(m.incoming)
                j = m.incoming[ix]
                line = self.lines[j]
                if line.cells[-1] is not None and line.cells[-1]<=t and m.stock[line.slot]<self.cap:
                    line.cells[-1] = None
                    line.delivered += 1
                    m.stock[line.slot] += 1
                    m.ip = (ix+1)%len(m.incoming)
                    return True
            return False
        if kind=='out':
            m = self.machines[i]
            if not m.output:
                return False
            for z in range(len(m.outgoing)):
                ix = (m.op+z)%len(m.outgoing)
                j = m.outgoing[ix]
                if self.can_take(self.lines[j]):
                    self.take(j)
                    m.output -= 1
                    m.op = (ix+1)%len(m.outgoing)
                    return True
            return False
        line = self.lines[i]
        if kind=='source':
            if self.can_take(line):
                self.take(i)
                return True
        elif kind=='sink':
            if line.cells[-1] is not None and line.cells[-1]<=t and self.sink(i, t):
                line.cells[-1] = None
                line.delivered += 1
                return True
        else:
            c = a[2]
            if line.cells[c] is not None and line.cells[c]<=t and line.cells[c+1] is None:
                line.cells[c] = None
                line.cells[c+1] = t+self.q
                return True
        return False

    def close(self, log=True):
        # A path can be ready within the zero-time closure even if it ends full.
        was_empty = {j for j, x in enumerate(self.lines) if self.can_take(x)}
        changed = True
        sweeps = 0
        while changed:
            changed = False
            for a in self.actions:
                if self.act(a):
                    changed = True
                    if log:
                        was_empty.update(j for j, x in enumerate(self.lines) if self.can_take(x))
            sweeps += 1
            assert sweeps < 5000
        if log:
            self.empty.extend((self.t, j) for j in was_empty)
        self.closures += 1

    def future(self, ceiling):
        times = [ceiling]
        times += [m.due for m in self.machines if m.enabled and m.due is not None and m.due>self.t]
        for line in self.lines:
            times.extend(x for x in line.cells if x is not None and x>self.t)
            if line.gate_every is not None and line.gate_due>self.t:
                times.append(line.gate_due)
        return min(times)

    def signature(self, external_period=1):
        def rem(x):
            return -1 if x is None else max(0, x-self.t)
        return (self.t%external_period,
                tuple((tuple(m.stock), m.output,
                       rem(m.due) if m.enabled else ('paused', m.paused_remaining),
                       m.ip, m.op) for m in self.machines),
                tuple((tuple(rem(x) for x in line.cells),
                       max(0, line.gate_due-self.t) if line.gate_every else -1) for line in self.lines))

    def counters(self):
        return {'starts': [m.starts for m in self.machines],
                'released': [m.released for m in self.machines],
                'accepted': [x.accepted for x in self.lines],
                'delivered': [x.delivered for x in self.lines]}

    def phi2(self, c=0, a=1, ca=0, ac=1):
        cm, am = self.machines[c], self.machines[a]
        integer_part = (sum(x is not None for x in self.lines[ca].cells)+am.stock[0]
                        +int(am.due is not None)+am.output
                        +sum(x is not None for x in self.lines[ac].cells)+cm.stock[0]
                        +int(cm.due is not None))
        return 2*integer_part+cm.output


def plant(q, seed, lengths=(1, 1, 1, 1), k=2, outlets=2, capacity=50):
    m = Model(q, seed, capacity)
    c = m.machine('C', k=2)
    a = m.machine('A')
    b = m.machine('B')
    crusher = m.machine('K', k=k)
    for src, dst, length, label in zip([c, a, c, b], [a, c, b, crusher], lengths,
                                     ['CA', 'AC', 'CB', 'BK']):
        m.line(src, dst, length=length, label=label)
    for i in range(outlets):
        m.line(crusher, None, length=1, label=f'Kout{i}')
    m.prepare()
    return m
