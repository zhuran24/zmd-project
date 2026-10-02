#!/usr/bin/env python3
"""Interpreter of the CURRENT formal rules, 2026-09-30, standard library only.

One project tick is eight steps. A Belt is a whole contiguous belt component;
Gate, Splitter, Merger and each BridgeAxis are separate one-cell components.
Layers use actual outgoing channels, not whether a blocked channel can send.
Dead ends have layer 1 but DO NOT count as a downstream 'still sending' element.
Components judge in layer order; ALL nontransport units judge afterwards.
Each judgement sends at most ONE item. Non-splitter components that share a
receiver judge as a group at the first member's turn (all members are consumed).
There is NO once-per-step item-movement budget: transport residence enforces it
where appropriate, but a Box can receive and forward in the SAME step.
The default eager belt motion ('can move => move') also has a staged comparison
mode implementing the earlier downstream pre-motion / own final-motion text.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import count, permutations, product


_CONNECTIONS = count()


@dataclass(eq=False)
class Item:
    kind: str
    entered: int = -100
    moved: int = -100                 # audit only; not a movement restriction
    previous: str = ""


@dataclass(eq=False)
class Channel:
    src: Unit
    dst: Unit
    connected: int


class UnknownLayer(ValueError):
    pass


class Unit:
    component = False
    belt = False
    splitter = False

    def __init__(self, name):
        self.name = name
        self.outputs, self.inputs = [], []
        self.output_channels, self.input_channels = [], []
        self.output_cursor = self.input_cursor = 0
        self.last_output = {}
        self.sent = []

    def connect(self, other, connected=None):
        # Explicit connection ranks are fixture parameters, not Python object
        # placement times. Defaults keep the old fixture's connection order.
        if connected is None:
            connected = next(_CONNECTIONS)
        c = Channel(self, other, connected)
        self.outputs.append(other)
        self.output_channels.append(c)
        other.inputs.append(self)
        other.input_channels.append(c)
        self.last_output[c] = -1
        return other

    def ready_item(self, w):
        return None

    def pop_item(self, item, w):
        raise NotImplementedError

    def move_inside(self, w):
        pass

    def channels(self, side, w=None, candidates=None):
        arr = self.output_channels if side == 'output' else self.input_channels
        arr = sorted(arr, key=lambda c: c.connected)
        if not arr:
            return []
        if side == 'output' and not self.component:
            # Formal rule 33: mergers individually, all other outlets as ONE
            # grade. In particular that other grade is NOT always lowest.
            ordinary = [c for c in arr if not isinstance(c.dst, Merger)]
            grades = [[c] for c in arr if isinstance(c.dst, Merger)]
            if ordinary:
                grades.append(ordinary)
            grades.sort(key=lambda g: (max(w.layers[c.dst.name] for c in g),
                                       min(c.connected for c in g)))
            ordered = []
            for grade in grades:
                ordered.extend(sorted(grade, key=lambda c: (self.last_output[c],
                                                            c.connected)))
        else:
            cursor = self.output_cursor if side == 'output' else self.input_cursor
            # Splitters/mergers start at SECOND connected channel. A single
            # connected channel naturally remains its own start.
            if cursor is None:
                cursor = 1 if len(arr) > 1 else 0
            ordered = arr[cursor % len(arr):] + arr[:cursor % len(arr)]
        if candidates is not None:
            ordered = [c for c in ordered if c in candidates]
        return ordered

    def successful(self, channel, side, w):
        arr = self.output_channels if side == 'output' else self.input_channels
        arr = sorted(arr, key=lambda c: c.connected)
        if side == 'output':
            self.output_cursor = (arr.index(channel) + 1) % len(arr)
            self.last_output[channel] = w.t
        else:
            self.input_cursor = (arr.index(channel) + 1) % len(arr)

    def pre_motion(self, w):
        for dst in self.outputs:
            if dst.belt:
                dst.move_inside(w)

    def send(self, w):
        # One item at most in a judgement, even for a multi-outlet factory.
        # Failed channels are skipped within this ONE judgement.
        for c in self.channels('output', w):
            if (self.name, c.dst.name) in w.attempted:
                continue
            if self.ready_item(w) is None:
                break
            success = w.transfer(c)
            if success:
                break

    def judge(self, w):
        w.log(self, 'judge', layer=w.layers.get(self.name))
        if w.motion == 'staged':
            self.pre_motion(w)
        self.send(w)
        if self.belt and w.motion == 'staged':
            self.move_inside(w)


class Belt(Unit):
    component = True
    belt = True

    def __init__(self, name, length=1):
        super().__init__(name)
        assert length >= 1
        self.cells = [None] * length

    def fill(self, kind='a', entered=-8):
        self.cells = [Item(kind, entered) for _ in self.cells]
        return self

    def ready_item(self, w):
        i = self.cells[-1]
        return i if i is not None and w.t - i.entered >= 8 else None

    def can_accept(self, item, w):
        return self.cells[0] is None

    def receive(self, item, w):
        assert self.cells[0] is None
        self.cells[0] = item
        w.log(self, 'receive', kind=item.kind)

    def pop_item(self, item, w):
        assert self.cells[-1] is item
        self.cells[-1] = None

    def move_inside(self, w):
        for j in range(len(self.cells) - 2, -1, -1):
            item = self.cells[j]
            if item is not None and self.cells[j+1] is None and w.t-item.entered >= 8:
                w.move(item, self, self, internal=True)
                self.cells[j+1], self.cells[j] = item, None
                w.log(self, 'cell_move', kind=item.kind, cell=j+1)

    def phase(self, t):
        return ['x' if i is None else max(0, 7-(t-i.entered)) for i in self.cells]


class Gate(Belt):
    """An UNCONFIGURED item admission gate (one cell, no identity/quota filter)."""
    belt = False

    def __init__(self, name):
        super().__init__(name)


class BridgeAxis(Gate):
    """One pair of parallel sides; the other axis is a distinct component."""


class Bridge:
    def __init__(self, name):
        self.axes = (BridgeAxis(name+'.horizontal'), BridgeAxis(name+'.vertical'))


class Splitter(Gate):
    splitter = True

    def __init__(self, name):
        super().__init__(name)
        self.output_cursor = None
        self.input_cursor = None


class Merger(Gate):
    def __init__(self, name):
        super().__init__(name)
        self.output_cursor = None
        self.input_cursor = None


class Sink(Unit):
    """An always-available terminal inventory, not a transport component."""
    def __init__(self, name='sink', every=1, opens=0):
        super().__init__(name)
        self.every, self.opens = every, opens
        self.received, self.last = [], -100000

    def can_accept(self, item, w):
        return w.t >= self.opens and w.t-self.last >= self.every

    def receive(self, item, w):
        self.last = w.t
        self.received.append((w.t, item.kind))
        w.log(self, 'receive', kind=item.kind)


class Warehouse(Sink):
    def __init__(self, name='warehouse', limit=80000):
        super().__init__(name)
        self.limit, self.stock = limit, Counter()

    def can_accept(self, item, w):
        return self.stock[item.kind] < self.limit

    def receive(self, item, w):
        assert self.can_accept(item, w)
        self.stock[item.kind] += 1
        self.received.append((w.t, item.kind))
        w.log(self, 'receive', kind=item.kind)


class Source(Unit):
    """Terminal inventory supply. period=None means it never runs out."""
    def __init__(self, name='source', kinds=('a',), period=None, phase=0):
        super().__init__(name)
        self.kinds, self.period = tuple(kinds), period
        self.next_release, self.pending, self.sequence = phase, 0, 0
        self.candidate = None

    def ready_item(self, w):
        return self.candidate

    def pop_item(self, item, w):
        self.candidate = None
        self.sequence += 1
        if self.period is not None:
            self.pending -= 1

    def judge(self, w):
        if self.period is not None:
            while self.next_release <= w.t:
                self.pending += 1
                self.next_release += self.period
        if self.period is None or self.pending:
            self.candidate = Item(self.kinds[self.sequence % len(self.kinds)])
        super().judge(w)


class Storage(Unit):
    def __init__(self, name, slots):
        super().__init__(name)
        self.slots = [[] for _ in range(slots)]
        self.received = []

    def target_slot(self, kind):
        for s in self.slots:
            if len(s) < 50 and (not s or s[0].kind == kind):
                return s
        return None

    def can_accept(self, item, w):
        return self.target_slot(item.kind) is not None

    def receive(self, item, w):
        s = self.target_slot(item.kind)
        assert s is not None
        s.append(item)
        self.received.append((w.t, item.kind))
        w.log(self, 'receive', kind=item.kind)


class Box(Storage):
    def __init__(self, name, full=False, wireless=False, wireless_order='before',
                 cooldown=0, warehouse=None):
        super().__init__(name, 6)
        assert wireless_order in ('before', 'after')
        self.wireless, self.wireless_order = wireless, wireless_order
        self.cooldown, self.warehouse = cooldown, warehouse
        self.transmitted = []
        if full:
            self.slots = [[Item('a') for _ in range(50)] for _ in range(6)]

    def ready_item(self, w):
        return next((s[0] for s in self.slots if s), None)

    def pop_item(self, item, w):
        for s in self.slots:
            if s and s[0] is item:
                s.pop(0)
                return
        raise AssertionError('missing item')

    def transmit(self, w):
        if not self.wireless or self.cooldown > 0:
            return
        taken = []
        for s in self.slots:
            kept = []
            for item in s:
                if self.warehouse is None or self.warehouse.can_accept(item, w):
                    if self.warehouse is not None:
                        self.warehouse.receive(item, w)
                    taken.append(item.kind)
                else:
                    kept.append(item)
            s[:] = kept
        self.transmitted.append((w.t, dict(Counter(taken))))
        w.log(self, 'transmit', quantity=len(taken))
        self.cooldown = 40          # even an empty or warehouse-blocked transfer

    def judge(self, w):
        if self.wireless_order == 'before':
            self.transmit(w)
        super().judge(w)
        if self.wireless_order == 'after':
            self.transmit(w)


@dataclass(frozen=True)
class Recipe:
    name: str
    ingredients: tuple[tuple[str, int], ...]
    product: str
    quantity: int = 1
    duration: int = 8


class Machine(Storage):
    def __init__(self, name='machine', quantity=1, auxiliary=False, duration=8,
                 recipes=None, product_quantity=1):
        super().__init__(name, 2 if auxiliary else 1)
        if recipes is None:
            recipes = [Recipe(k, ((k, quantity),) + ((('sand', 1),) if auxiliary else ()),
                              k.upper(), product_quantity, duration) for k in ('a', 'b')]
        self.recipes = tuple(recipes)
        self.output, self.cache = [], []
        self.running, self.remaining = None, None
        self.powered = self.enabled = True
        self.starts, self.finishes, self.flushed = [], [], []
        if auxiliary:
            self.slots[1] = [Item('sand') for _ in range(50)]

    def target_slot(self, kind):
        same = next((s for s in self.slots if s and s[0].kind == kind), None)
        if same is not None:
            return same if len(same) < 50 else None
        return next((s for s in self.slots if not s), None)

    def ready_item(self, w):
        return self.output[0] if self.output else None

    def pop_item(self, item, w):
        assert self.output[0] is item
        self.output.pop(0)
        self.flush(w)              # immediate, not only at start/end judgement

    def complete(self, w):
        if self.running is None or not (self.powered and self.enabled):
            return
        self.remaining -= 1
        if self.remaining == 0:
            r = self.running
            assert not self.cache
            self.cache = [Item(r.product) for _ in range(r.quantity)]
            self.running, self.remaining = None, None
            self.finishes.append((w.t, r.name))
            w.log(self, 'finish', kind=r.name)
            self.flush(w)

    def flush(self, w):
        if not self.cache or len(self.output)+len(self.cache) > 50:
            return
        if self.output and self.output[0].kind != self.cache[0].kind:
            return
        kind = self.cache[0].kind
        for item in self.cache:
            w.move(item, self, self, internal=True)
        self.output.extend(self.cache)
        self.flushed.append((w.t, kind))
        w.log(self, 'cache_to_output', kind=kind, quantity=len(self.cache))
        self.cache = []

    def start(self, w):
        if not (self.powered and self.enabled) or self.running is not None or self.cache:
            return
        available = {s[0].kind: s for s in self.slots if s}
        for r in self.recipes:
            if not all(len(available.get(k, [])) >= n for k, n in r.ingredients):
                continue
            for k, n in r.ingredients:
                s = available[k]
                for item in s[:n]:
                    w.move(item, self, self, internal=True)
                del s[:n]
            self.running, self.remaining = r, r.duration
            self.starts.append((w.t, r.name))
            w.log(self, 'start', kind=r.name)
            return


def component_choices(nodes):
    """All eligible choices, including equal-layer choices separately."""
    branches = []
    for u in nodes:
        if u.component:
            ds = [d for d in u.outputs if d.component and d.outputs]
            if len(ds) > 1:
                branches.append((u.name, [d.name for d in ds]))
    for values in product(*(opts for _, opts in branches)):
        yield dict(zip((name for name, _ in branches), values))


def layers_for(nodes, choices=None, unknown=None):
    choices, unknown = choices or {}, unknown or {}
    result, visiting = {}, set()

    def visit(u):
        if u.name in result:
            return result[u.name]
        if u.name in unknown:
            assert unknown[u.name] >= 1
            result[u.name] = unknown[u.name]
            return result[u.name]
        if u.name in visiting:
            raise UnknownLayer('cannot count layer through cycle at '+u.name)
        visiting.add(u.name)
        ds = [d for d in u.outputs if d.component and d.outputs]
        if len(ds) > 1:
            chosen = choices.get(u.name)
            if chosen is None:
                raise UnknownLayer('supply branch choice for '+u.name)
            ds = [d for d in ds if d.name == chosen]
            if not ds:
                raise ValueError('ineligible branch for '+u.name)
        layer = visit(ds[0])+1 if ds else 1
        visiting.remove(u.name)
        result[u.name] = layer
        return layer

    for u in nodes:
        if u.component:
            visit(u)
    return result


def schedules(nodes, sources=(), nontransport='all', active=None):
    """Enumerate branch choices, ALL equal-layer orders, then all active NT orders.

    Passive sinks/full disabled leaf boxes have no meaningful judgement. Source
    order relative to unrelated NT units commutes in the fixtures: newly supplied
    transport inventory cannot move again until a subsequent step. Putting sources
    last is an explicit commuting-order quotient, not a rule about sources.
    The nontransport parameter can request one representative order when factories
    have independent always-open product lines (the mining quotient).
    """
    if active is None:
        active = [u for u in nodes if u.component or u.outputs or
                  isinstance(u, Box) and u.wireless]
    active = [u for u in active if u not in sources]
    for choices in component_choices(nodes):
        lev = layers_for(nodes, choices)
        comps = [u for u in active if u.component]
        nts = [u for u in active if not u.component]
        groups = [[u for u in comps if lev[u.name] == l]
                  for l in sorted({lev[u.name] for u in comps})]
        ntorders = list(permutations(nts)) if nontransport == 'all' else [tuple(nts)]
        for gs in product(*(permutations(g) for g in groups)):
            for ns in ntorders:
                order = [u.name for g in gs for u in g]+[u.name for u in ns]
                yield dict(choices=choices, layers={u.name: lev[u.name] for u in comps},
                           nontransport_order=[u.name for u in ns], order=order)


class World:
    def __init__(self, nodes, sources=(), schedule=None, trace=False, motion='eager'):
        assert motion in ('eager', 'staged')
        self.nodes, self.sources = list(nodes), list(sources)
        self.trace, self.motion = trace, motion
        self.events, self.t = [], 0
        self.attempted, self.judged = set(), set()
        self.machines = [u for u in nodes if isinstance(u, Machine)]
        self.boxes = [u for u in nodes if isinstance(u, Box)]
        self.belts = [u for u in nodes if u.belt]
        self.lookup = {u.name: u for u in nodes}
        assert len(self.lookup) == len(nodes)
        schedule = schedule or next(schedules(nodes, sources, nontransport='representative'))
        self.schedule = schedule
        self.layers = layers_for(nodes, schedule.get('choices'), schedule.get('unknown'))
        self.order = [self.lookup[n] for n in schedule['order']]
        comp_layers = [self.layers[u.name] for u in self.order if u.component]
        assert comp_layers == sorted(comp_layers), self.layers
        assert all(u.component for u in self.order[:len(comp_layers)])
        passive = [u for u in nodes if u not in self.order and u not in sources]
        for u in passive:
            assert not u.component and not u.outputs and not (isinstance(u, Box) and u.wireless)
        self.order += passive+list(sources)

    def log(self, unit, event, **data):
        if self.trace:
            self.events.append(dict(t=self.t, unit=unit.name, event=event, **data))

    def move(self, item, src, dst, internal=False):
        if not internal:
            assert item.previous != dst.name, 'return to immediately previous unit'
            item.previous = src.name
        item.moved = self.t
        item.entered = self.t

    def settle(self, units=None):
        if self.motion == 'eager':
            for u in self.belts if units is None else units:
                if u.belt:
                    u.move_inside(self)

    def transfer(self, c):
        key = (c.src.name, c.dst.name)
        if key in self.attempted:
            return False
        self.attempted.add(key)
        item = c.src.ready_item(self)
        if item is None or item.previous == c.dst.name or not c.dst.can_accept(item, self):
            return False
        c.src.pop_item(item, self)
        self.move(item, c.src, c.dst)
        c.dst.receive(item, self)
        c.src.successful(c, 'output', self)
        c.dst.successful(c, 'input', self)
        c.src.sent.append((self.t, item.kind, c.dst.name))
        self.log(c.src, 'send', kind=item.kind, destination=c.dst.name)
        self.settle([c.src, c.dst])
        return True

    def judge_component(self, u):
        if u.name in self.judged:
            return
        # Current rule 31: all NON-SPLITTER component upstreams judge together
        # when the first reaches its turn. Even an empty/blocked group member
        # consumes its judgement and must not retry at its nominal later turn.
        if not u.splitter and u.output_channels:
            assert len(u.output_channels) == 1, 'fixtures use one directed outlet per non-splitter'
            dst = u.output_channels[0].dst
            candidates = {c for c in dst.input_channels if c.src.component and not c.src.splitter}
            channels = dst.channels('input', self, candidates)
            for c in channels:
                assert c.src.name not in self.judged, (self.t, c.src.name)
            for c in channels:
                self.judged.add(c.src.name)
            for c in channels:
                member = c.src
                self.log(member, 'judge', layer=self.layers[member.name], trigger=u.name)
                if self.motion == 'staged':
                    member.pre_motion(self)
                self.transfer(c)
                if member.belt and self.motion == 'staged':
                    member.move_inside(self)
        else:
            self.judged.add(u.name)
            u.judge(self)

    def step(self):
        self.attempted.clear()
        self.judged.clear()
        for b in self.boxes:
            if b.wireless and b.cooldown > 0:
                b.cooldown -= 1
        for m in self.machines:
            m.complete(self)
            m.flush(self)
        self.settle()
        for u in self.order:
            if u.component:
                self.judge_component(u)
            else:
                assert u.name not in self.judged
                self.judged.add(u.name)
                u.judge(self)
        for m in self.machines:
            m.start(self)
        self.t += 1

    def run(self, steps):
        for _ in range(steps):
            self.step()
        return self


def steady_stats(events, warmup=2000):
    times = [x[0] for x in events if x[0] >= warmup]
    gaps = [b-a for a, b in zip(times, times[1:])]
    return dict(count=len(times), span=times[-1]-times[0] if len(times) > 1 else 0,
                normalized_rate=8*len(gaps)/sum(gaps) if gaps else 0,
                gaps=dict(sorted(Counter(gaps).items())))
