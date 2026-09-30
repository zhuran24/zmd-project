#!/usr/bin/env python3
"""Small event-by-step interpreter of the 2026-09-30 draft (standard library only).

One time step = 1/8 project tick. Contiguous belts are ONE component.
`entered` implements >= 8 steps per cell; aging is not a channel movement.
Only `move_inside` is called during downstream pre-motion: no recursive sends.
Factory internal channel moves can share or not share the logistics move budget.
No ordering is inferred from object construction: each run supplies an order.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import Counter


@dataclass(eq=False)
class Item:
    kind: str
    entered: int = -100
    moved: int = -100
    previous: str = ""


class World:
    def __init__(self, order, sources=(), scope="logistics", trace=False):
        assert scope in ("all_channels", "logistics")
        self.order, self.sources, self.scope = list(order), list(sources), scope
        self.t = 0
        self.events = []
        self.trace = trace
        self.machines = [x for x in order if isinstance(x, Machine)]
        self.snapshots = []

    def log(self, unit, event, **data):
        if self.trace:
            self.events.append(dict(t=self.t, unit=unit.name, event=event, **data))

    def move(self, item, sender, receiver, internal=False):
        if not internal or self.scope == "all_channels":
            assert item.moved != self.t, (self.t, sender.name, receiver.name)
            item.moved = self.t
        if not internal:
            assert item.previous != receiver.name, "immediate return to previous unit"
            item.previous = sender.name
        item.entered = self.t

    def step(self):
        for m in self.machines:
            m.complete(self)
        for u in self.order:
            u.judge(self)
        for s in self.sources:
            s.judge(self)
        for m in self.machines:
            m.start(self)
        self.t += 1

    def run(self, steps):
        for _ in range(steps):
            self.step()
        return self


class Unit:
    def __init__(self, name):
        self.name, self.outputs, self.inputs = name, [], []
        self.sent = []

    def connect(self, other):
        self.outputs.append(other)
        other.inputs.append(self)
        return other

    def ready_item(self, w):
        return None

    def move_inside(self, w):
        pass

    def judge(self, w):
        pass

    def dispatch(self, dst, w):
        # Non-splitter upstreams jointly arbitrate a merger at the first trigger.
        if isinstance(dst, Merger) and not isinstance(self, Splitter):
            return dst.arbitrate(w, self)
        if isinstance(dst, Machine) and not isinstance(self, Splitter) and dst.input_policy != "sequential":
            return dst.arbitrate(w, self)
        return self.transfer(dst, w)

    def transfer(self, dst, w):
        item = self.ready_item(w)
        if item is None or item.previous == dst.name or not dst.can_accept(item, w):
            return False
        self.pop_item(item)
        w.move(item, self, dst)
        dst.receive(item, w)
        self.sent.append((w.t, item.kind, dst.name))
        w.log(self, "send", kind=item.kind, destination=dst.name)
        return True


class Belt(Unit):
    def __init__(self, name, length=1):
        super().__init__(name)
        assert length >= 1
        self.cells = [None] * length

    def fill(self, kind="a", entered=-8):
        self.cells = [Item(kind, entered) for _ in self.cells]
        return self

    def ready_item(self, w):
        i = self.cells[-1]
        return i if i and i.moved != w.t and w.t - i.entered >= 8 else None

    def can_accept(self, item, w):
        return self.cells[0] is None

    def receive(self, item, w):
        assert self.cells[0] is None
        self.cells[0] = item
        w.log(self, "receive", kind=item.kind)

    def pop_item(self, item):
        assert self.cells[-1] is item
        self.cells[-1] = None

    def move_inside(self, w):
        for index in range(len(self.cells)-2, -1, -1):
            item = self.cells[index]
            if (item and self.cells[index+1] is None and item.moved != w.t
                    and w.t-item.entered >= 8):
                w.move(item, self, self, internal=True)
                # Belt internal movement ALWAYS consumes the logistics budget.
                item.moved = w.t
                self.cells[index+1], self.cells[index] = item, None
                w.log(self, "cell_move", kind=item.kind, cell=index+1)

    def judge(self, w):
        for dst in self.outputs:
            dst.move_inside(w)
        if self.outputs:
            self.dispatch(self.outputs[0], w)
        self.move_inside(w)

    def phase(self, t):
        # End-of-step labels used in the community trace (7 at entry, 0 at exit).
        return ["x" if i is None else max(0, 7-(t-i.entered)) for i in self.cells]


class Splitter(Belt):
    def __init__(self, name, polling="skip", cursor=1):
        super().__init__(name)
        self.polling, self.cursor = polling, cursor

    def judge(self, w):
        for dst in self.outputs:
            dst.move_inside(w)
        if not self.outputs or self.ready_item(w) is None:
            return
        n = len(self.outputs)
        indices = [(self.cursor+j) % n for j in range(n if self.polling == "skip" else 1)]
        for j in indices:
            success = self.transfer(self.outputs[j], w)
            if success or self.polling != "hold":
                self.cursor = (j+1) % n
            if success:
                break


class Merger(Belt):
    def __init__(self, name, polling="skip", cursor=1):
        super().__init__(name)
        self.polling, self.cursor, self.polled = polling, cursor, -1

    def arbitrate(self, w, trigger):
        if self.polled == w.t:
            return False
        self.polled = w.t
        candidates = [u for u in self.inputs if not isinstance(u, Splitter)]
        if not candidates:
            return False
        n = len(candidates)
        # rotate_busy is deliberately another plausible but unfair reading:
        # it rotates even if the destination is occupied.
        if self.cells[0] is not None:
            if self.polling == "rotate_busy":
                self.cursor = (self.cursor+1) % n
            return False
        indices = [(self.cursor+j) % n for j in range(n if self.polling == "skip" else 1)]
        for j in indices:
            success = candidates[j].transfer(self, w)
            if success or self.polling != "hold":
                self.cursor = (j+1) % n
            if success:
                return True
        return False


class Sink(Unit):
    def __init__(self, name="sink", every=1, opens=0):
        super().__init__(name)
        self.every, self.opens, self.received = every, opens, []
        self.last = -100000

    def can_accept(self, item, w):
        return w.t >= self.opens and w.t-self.last >= self.every

    def receive(self, item, w):
        self.last = w.t
        self.received.append((w.t, item.kind))
        w.log(self, "receive", kind=item.kind)


class Source(Unit):
    def __init__(self, name="source", kinds=("a",), period=None, phase=0):
        super().__init__(name)
        self.kinds, self.period, self.next_release = tuple(kinds), period, phase
        self.sequence = 0
        self.pending = 0
        self.candidate = None

    def ready_item(self, w):
        return self.candidate

    def pop_item(self, item):
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
            self.dispatch(self.outputs[0], w)


class Storage(Unit):
    def __init__(self, name, slots):
        super().__init__(name)
        self.slots = [[] for _ in range(slots)]
        self.received = []

    def target_slot(self, kind):
        for slot in self.slots:
            if len(slot) < 50 and (not slot or slot[0].kind == kind):
                return slot
        return None

    def can_accept(self, item, w):
        return self.target_slot(item.kind) is not None

    def receive(self, item, w):
        slot = self.target_slot(item.kind)
        assert slot is not None
        slot.append(item)
        self.received.append((w.t, item.kind))
        w.log(self, "receive", kind=item.kind)


class Box(Storage):
    """Wireless transmission is disabled in the blocking experiments."""
    def __init__(self, name, full=False, priority=False):
        super().__init__(name, 6)
        self.priority, self.cursor = priority, 0
        self.last_output = [-1]*3
        if full:
            self.slots = [[Item("a") for _ in range(50)] for _ in range(6)]

    def ready_item(self, w):
        for slot in self.slots:
            if slot:
                return next((x for x in slot if x.moved != w.t), None)
        return None

    def pop_item(self, item):
        for slot in self.slots:
            if any(x is item for x in slot):
                slot.remove(item)
                return
        raise AssertionError("missing item")

    def judge(self, w):
        if self.priority:
            order = range(len(self.outputs))
        else:
            order = sorted(range(len(self.outputs)), key=lambda j: (self.last_output[j],j))
        for j in order:
            if self.dispatch(self.outputs[j], w):
                self.last_output[j] = w.t
                break


class Machine(Storage):
    def __init__(self, name="machine", quantity=1, auxiliary=False, inner_order="flush_send", input_policy="skip"):
        super().__init__(name, 2 if auxiliary else 1)
        self.quantity, self.auxiliary, self.inner_order = quantity, auxiliary, inner_order
        self.input_policy, self.input_cursor, self.input_polled = input_policy, 0, -1
        self.output = []
        self.cache = []
        self.running = None
        self.finishes_at = None
        self.starts, self.finishes, self.flushed = [], [], []
        if auxiliary:
            self.slots[1] = [Item("sand") for _ in range(50)]

    def arbitrate(self, w, trigger):
        if self.input_polled == w.t:
            return False
        self.input_polled = w.t
        candidates = [u for u in self.inputs if not isinstance(u,Splitter)]
        n=len(candidates)
        indices=[(self.input_cursor+offset)%n for offset in range(n)]
        any_success=False
        for j in indices:
            if candidates[j].transfer(self,w):
                self.input_cursor=(j+1)%n
                any_success=True
                if self.input_policy == "skip_one":
                    break
        return any_success

    def target_slot(self, kind):
        # Formal rule: a kind occupies at most one input slot per machine.
        same = next((s for s in self.slots if s and s[0].kind == kind), None)
        if same is not None:
            return same if len(same)<50 else None
        return next((s for s in self.slots if not s), None)

    def ready_item(self, w):
        return next((x for x in self.output if x.moved != w.t), None)

    def pop_item(self, item):
        self.output.remove(item)

    def complete(self, w):
        if self.finishes_at == w.t:
            kind = self.running
            self.cache = [Item(kind.upper())]
            self.running, self.finishes_at = None, None
            self.finishes.append((w.t,kind))
            w.log(self,"finish",kind=kind)

    def flush(self, w):
        if self.cache and len(self.output)+len(self.cache)<=50:
            if self.output and self.output[0].kind != self.cache[0].kind:
                return
            for item in self.cache:
                w.move(item, self, self, internal=True)
            self.output.extend(self.cache)
            self.flushed.append((w.t,self.cache[0].kind))
            w.log(self,"cache_to_output",kind=self.cache[0].kind,quantity=len(self.cache))
            self.cache = []

    def judge(self, w):
        if self.inner_order == "flush_send":
            self.flush(w)
        if self.outputs:
            self.dispatch(self.outputs[0], w)
        if self.inner_order == "send_flush":
            self.flush(w)

    def start(self, w):
        if self.running is not None or self.cache:
            return
        for slot in self.slots:
            if not slot or slot[0].kind not in ("a","b"):
                continue
            available = [x for x in slot if w.scope != "all_channels" or x.moved != w.t]
            sand = next((s for s in self.slots if s and s[0].kind=="sand"),[]) if self.auxiliary else []
            usable_sand = [x for x in sand if w.scope != "all_channels" or x.moved != w.t]
            if len(available)<self.quantity or (self.auxiliary and not usable_sand):
                continue
            kind=slot[0].kind
            for x in available[:self.quantity]:
                w.move(x,self,self,internal=True)
                slot.remove(x)
            if self.auxiliary:
                x=usable_sand[0]
                w.move(x,self,self,internal=True)
                sand.remove(x)
            self.running, self.finishes_at = kind, w.t+8
            self.starts.append((w.t,kind))
            w.log(self,"start",kind=kind)
            return


def steady_stats(events, warmup=2000):
    """Use inter-departure spans, not a finite-window count biased by endpoints."""
    times = [x[0] for x in events if x[0]>=warmup]
    gaps = [b-a for a,b in zip(times,times[1:])]
    return dict(count=len(times),span=times[-1]-times[0] if len(times)>1 else 0,
                normalized_rate=8*len(gaps)/sum(gaps) if gaps else 0,
                gaps=dict(sorted(Counter(gaps).items())))
