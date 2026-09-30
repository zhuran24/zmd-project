#!/usr/bin/env python3
"""Formal-rule simulations and local-only evidence; stdlib, no external code.

Outputs are confined to this directory. Use --groups to rerun selected groups.
Schedules enumerate structural layers before judgement orders, unlike sim/.
"""
import argparse
import csv
import hashlib
import itertools as it
import json
from collections import Counter
from fractions import Fraction
from math import factorial
from pathlib import Path

from simulator import (Belt, Box, BridgeAxis, Gate, Item, Machine, Merger,
                       Recipe, Sink, Source, Splitter, Warehouse, World,
                       component_choices, layers_for, schedules, steady_stats)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STEPS = 12000


def protected_inputs():
    saved = json.loads((HERE/'inputs.sha256.json').read_text())
    changed = [p for p, h in saved.items()
               if hashlib.sha256((ROOT/p).read_bytes()).hexdigest() != h]
    assert not changed, changed
    return len(saved)


def stats(events, warmup=2000):
    r = steady_stats(events, warmup)
    times = [x[0] for x in events if x[0] >= warmup]
    gaps = [b-a for a, b in zip(times, times[1:])]
    r['rate_fraction'] = '0' if not gaps else None
    # Exact observed repeating gap pattern; do not round a finite-window rate.
    for p in range(1, min(len(gaps)//10, 800)+1):
        tail = gaps[-10*p:]
        if all(tail[j] == tail[j % p] for j in range(len(tail))):
            r.update(gap_period=tail[:p], period_steps=sum(tail[:p]),
                     rate_fraction=str(Fraction(8*p, sum(tail[:p]))))
            break
    return r


def stream(events, warmup=2000, kind_index=1):
    seq = [x[kind_index] for x in events if x[0] >= warmup]
    result = dict(counts=dict(Counter(seq)), first=seq[:32])
    for p in range(1, min(len(seq)//10, 256)+1):
        tail = seq[-10*p:]
        if all(tail[j] == tail[j % p] for j in range(len(tail))):
            result['cycle'] = tail[:p]
            result['cycle_counts'] = dict(Counter(tail[:p]))
            break
    return result


def trace_csv(name, events):
    fields = ['t', 'unit', 'event', 'kind', 'destination', 'quantity', 'cell', 'layer', 'trigger']
    with (HERE/name).open('w') as f:
        writer = csv.DictWriter(f, fields)
        writer.writeheader()
        writer.writerows(events)


def build_world(builder, schedule=None, trace=False, motion='eager'):
    nodes, sources, obj = builder()
    w = World(nodes, sources, schedule, trace, motion)
    return w, obj


def enum_runs(builder, steps=STEPS, nontransport='all', trace_first=None):
    nodes, sources, _ = builder()
    for i, sch in enumerate(schedules(nodes, sources, nontransport)):
        w, obj = build_world(builder, sch, trace=trace_first is not None and i == 0)
        if w.trace:
            w.run(min(60, steps))
            trace_csv(trace_first, w.events)
            w.trace = False
            w.run(max(0, steps-60))
        else:
            w.run(steps)
        yield sch, w, obj


def machine_tail(line, nodes, name='machine', duration=8):
    m = Machine(name, duration=duration)
    out, sink = Belt(name+'_output'), Sink(name+'_sink')
    line.connect(m).connect(out).connect(sink)
    nodes.extend([m, out, sink])
    return m, sink


def pure_builder(n):
    src, line, out, m, sink = Source(), Belt('input', n), Belt('output'), Machine(), Sink()
    src.connect(line).connect(m).connect(out).connect(sink)
    return [src, line, m, out, sink], [src], dict(machine=m, sink=sink)


def pure_chain():
    rows = []
    for n in (1, 2, 3, 4, 8, 16, 64):
        for sch, w, obj in enum_runs(lambda: pure_builder(n), 8*n+4000):
            r = dict(n=n, schedule=sch, **stats(obj['machine'].starts, 8*n+100))
            assert r['rate_fraction'] == '1', r
            rows.append(r)
    return rows


def lag_builder(n, blocked='tail', dead_count=1, following=0, initial='full'):
    src, x, s, sink = Source(), Splitter('X'), Belt('S', n), Sink()
    nodes = [src, x, s, sink]
    src.connect(x)
    x.connect(s)
    last = s
    for j in range(following):
        g = Gate('G'+str(j+1))
        last.connect(g)
        nodes.append(g)
        if initial == 'full':
            g.fill()
        last = g
    last.connect(sink)
    ds = []
    if blocked == 'direct_box':
        d = Box('B', full=True)
        x.connect(d)
        nodes.append(d)
    else:
        last = x
        for j in range(dead_count):
            d = BridgeAxis('D'+str(j+1))
            last.connect(d)
            nodes.append(d)
            d.fill()
            ds.append(d)
            last = d
        if blocked == 'box':
            b = Box('B', full=True)
            last.connect(b)
            nodes.append(b)
    if initial == 'full':
        x.fill()
        s.fill()
    return nodes, [src], dict(X=x, S=s, sink=sink, dead=ds)


def lag():
    rows = []
    for blocked, n, initial in it.product(('tail', 'box', 'direct_box'), range(1, 5), ('full', 'empty')):
        builder = lambda: lag_builder(n, blocked=blocked, initial=initial)
        for sch, w, obj in enum_runs(builder):
            r = dict(n=n, blocked=blocked, initial=initial, schedule=sch,
                     **stats(obj['S'].sent))
            # Old abbreviated graph now has X=2, S=1: impossible to put X first.
            assert r['rate_fraction'] == '1', r
            rows.append(r)
    complete = []
    for n, blocked, initial in it.product(range(1, 7), ('tail', 'box', 'direct_box'), ('full', 'empty')):
        dc = 2 if blocked == 'tail' else 1
        builder = lambda: lag_builder(n, blocked=blocked, dead_count=dc, following=1, initial=initial)
        for sch, w, obj in enum_runs(builder):
            before = sch['order'].index('X') < sch['order'].index('S')
            expected = str(Fraction(8*n, 8*n+1)) if before else '1'
            r = dict(n=n, blocked=blocked, initial=initial, X_before_S=before,
                     schedule=sch, **stats(obj['S'].sent))
            assert r['rate_fraction'] == expected, r
            complete.append(r)
    # Concrete complete graph with the same local X/S state as the old trace.
    nodes, srcs, _ = lag_builder(2, dead_count=2, following=1)
    sch = next(s for s in schedules(nodes, srcs) if s['choices'].get('X') == 'D1'
               and s['order'].index('X') < s['order'].index('S'))
    w, obj = build_world(lambda: lag_builder(2, dead_count=2, following=1), sch, trace=True)
    phase_trace = []
    for _ in range(45):
        w.step()
        phase_trace.append(dict(t=w.t-1, X=obj['X'].phase(w.t-1), S=obj['S'].phase(w.t-1)))
    trace_csv('b_n2_trace.csv', w.events)
    return dict(old_abbreviated=rows, community_complete=complete,
                phase_schedule=sch, phase_trace_n2=phase_trace)


def machine_builder(case, connection_order=None):
    m = Machine(quantity=2 if case == 3 else 1, auxiliary=case == 3)
    out, sink = Belt('output'), Sink()
    m.connect(out).connect(sink)
    nodes, sources, belts = [m, out, sink], [], {}
    if case == 2:
        a, src = Belt('ab'), Source('ab_source', ('b', 'a'))
        a.cells[0] = Item('a', -7)
        src.connect(a)
        belts['ab'] = a
        nodes.extend([a, src])
        sources.append(src)
    else:
        for kind in ('a', 'b'):
            line, src = Belt(kind).fill(kind, -7), Source(kind+'_source', (kind,))
            src.connect(line)
            belts[kind] = line
            nodes.extend([line, src])
            sources.append(src)
    if case == 3:
        line, src = Belt('sand'), Source('sand_source', ('sand',))
        src.connect(line)
        belts['sand'] = line
        nodes.extend([line, src])
        sources.append(src)
    for j, name in enumerate(connection_order or belts):
        belts[name].connect(m, connected=j)
    return nodes, sources, dict(machine=m, sink=sink)


def machines():
    rows = []
    for case in (1, 2, 3):
        names = ['ab'] if case == 2 else ['a', 'b'] if case == 1 else ['a', 'b', 'sand']
        for connections in it.permutations(names):
            builder = lambda: machine_builder(case, connections)
            nodes, sources, _ = builder()
            for i, sch in enumerate(schedules(nodes, sources)):
                w, obj = build_world(builder, sch, trace=i == 0)
                w.t = 1
                w.run(60)
                if w.trace:
                    trace_csv('c'+str(case)+'_'+''.join(connections)+'.csv', w.events)
                w.trace = False
                w.run(STEPS-60)
                m = obj['machine']
                periods = sorted({m.starts[j+2][0]-m.starts[j][0] for j in range(len(m.starts)-2)
                                  if m.starts[j][0] >= 2000})
                r = dict(case=case, connections=connections, schedule=sch,
                         **stats(m.starts), AB_period=periods,
                         first_starts=m.starts[:7], first_finishes=m.finishes[:6],
                         first_cache_to_output=m.flushed[:6], first_sends=m.sent[:6],
                         first_receives=m.received[:16])
                assert periods == [18 if case == 3 else 16], r
                assert all(m.starts[j][1] != m.starts[j+1][1] for j in range(len(m.starts)-1)), r
                rows.append(r)
    blocked = []
    for quantity in (1, 2):
        m, out, sink = Machine(), Belt('output'), Sink()
        m.output = [Item('A') for _ in range(50)]
        m.cache = [Item('A') for _ in range(quantity)]
        m.slots[0] = [Item('a')]
        m.connect(out).connect(sink)
        w = World([m, out, sink], trace=True).run(12)
        r = dict(batch_quantity=quantity, first_start=m.starts[0][0],
                 first_flush=m.flushed[0][0], first_send=m.sent[0][0])
        assert r['first_flush'] == r['first_start'] == (0 if quantity == 1 else 8), r
        blocked.append(r)
        trace_csv('c_cache_batch'+str(quantity)+'.csv', w.events)
    return dict(cases=rows, blocked_output=blocked)


def box_builder(k):
    belts = [Belt('L'+str(i)).fill() for i in range(k+1)]
    boxes = [Box('B'+str(i+1), full=True) for i in range(k)]
    source, sink = Source(), Sink(opens=0)
    source.connect(belts[0])
    for j, b in enumerate(boxes):
        belts[j].connect(b).connect(belts[j+1])
    belts[-1].connect(sink)
    return [*belts, *boxes, source, sink], [source], dict(belts=belts, boxes=boxes)


def boxes():
    rows, exhaustive = [], []
    for k in range(1, 7):
        builder = lambda: box_builder(k)
        nodes, sources, _ = builder()
        sch = next(schedules(nodes, sources))
        w, obj = build_world(builder, sch, trace=k == 3)
        w.run(k+12)
        r = dict(k=k, schedule=sch,
                 box_first_outputs={b.name: b.sent[0][0] for b in obj['boxes']},
                 box_first_inputs={b.name: b.received[0][0] for b in obj['boxes']},
                 upstream_first=obj['belts'][0].sent[0][0])
        assert r['upstream_first'] == k, r
        rows.append(r)
        if k == 3:
            trace_csv('d_boxes3.csv', w.events)
        if k <= 3:
            first, count = set(), 0
            for es, ew, eo in enum_runs(builder, k+12):
                count += 1
                first.add(eo['belts'][0].sent[0][0])
            exhaustive.append(dict(k=k, orders=count, upstream_first=sorted(first)))
    return dict(examples=rows, all_orders=exhaustive,
                quotient_argument='all belts are layer 1, all boxes at least layer 2; '
                                  'box order cannot reuse a belt that already failed')


def merger_builder(phase=0, connections=('full', 'sparse')):
    a, b, m, sink = Belt('full'), Belt('sparse'), Merger('merge'), Sink()
    sa, sb = Source('full_source'), Source('sparse_source', ('b',), period=40, phase=phase)
    sa.connect(a)
    sb.connect(b)
    for j, name in enumerate(connections):
        {'full': a, 'sparse': b}[name].connect(m, connected=j)
    m.connect(sink)
    return [a, b, m, sink, sa, sb], [sa, sb], dict(sink=sink)


def mergers():
    rows = []
    for connections, phase in it.product((('full', 'sparse'), ('sparse', 'full')), range(40)):
        for sch, w, obj in enum_runs(lambda: merger_builder(phase, connections)):
            r = dict(connections=connections, phase=phase, schedule=sch,
                     **stats(obj['sink'].received), stream=stream(obj['sink'].received))
            assert r['rate_fraction'] == '1', r
            sparse = [(t, kind) for t, kind in obj['sink'].received if kind == 'b']
            assert stats(sparse)['rate_fraction'] == '1/5', r
            rows.append(r)
    return rows


def insertion_builder(n=1, dead_count=1):
    ore, blue = Source('ore_source', ('ore',)), Source('blue_source', ('blue',))
    x, s, y, m = Splitter('X'), Belt('S', n), Splitter('Y'), Merger('M')
    t, sink = Belt('blue'), Sink()
    ore.connect(x)
    x.connect(s).connect(y).connect(m).connect(sink)
    blue.connect(t).connect(m)
    ds, last = [], x
    for j in range(dead_count):
        d = BridgeAxis('D'+str(j+1)).fill('ore')
        last.connect(d)
        ds.append(d)
        last = d
    return [ore, blue, x, s, y, m, t, sink, *ds], [ore, blue], dict(sink=sink)


def priority_insertion():
    rows = []
    for n, dead_count in it.product((1, 2, 3), (1, 2)):
        for sch, w, obj in enum_runs(lambda: insertion_builder(n, dead_count)):
            ore_first = sch['order'].index('Y') < sch['order'].index('blue')
            lagged = sch['order'].index('X') < sch['order'].index('S')
            events = obj['sink'].received
            r = dict(n=n, dead_count=dead_count, ore_first=ore_first,
                     lagged=lagged, schedule=sch, **stats(events), stream=stream(events))
            rows.append(r)
    return rows


def overflow_builder(dead_count=1, lower_gates=3, connections=('top', 'lower')):
    src, feed, box = Source(), Belt('feed'), Box('factory')
    top, x, s, gate = Belt('top'), Splitter('X'), Belt('S'), Gate('top_gate')
    lower, lowline = Merger('lower'), Belt('lower_line', 5)
    ts, ls = Sink('top_sink'), Sink('lower_sink')
    src.connect(feed).connect(box)
    for j, name in enumerate(connections):
        box.connect(top if name == 'top' else lower, connected=j)
    top.connect(x).connect(s).connect(gate).connect(ts)
    ds, last = [], x
    for j in range(dead_count):
        d = BridgeAxis('D'+str(j+1)).fill()
        last.connect(d)
        ds.append(d)
        last = d
    lower.connect(lowline)
    lg, last = [], lowline
    for j in range(lower_gates):
        g = Gate('lower_gate'+str(j))
        last.connect(g)
        lg.append(g)
        last = g
    last.connect(ls)
    return [src, feed, box, top, x, s, gate, lower, lowline, ts, ls, *ds, *lg], [src], \
           dict(box=box, top_sink=ts, lower_sink=ls)


def overflow_schedules(nodes, sources):
    """EXACT commuting-order quotient of all equal-layer permutations.

    This graph has no receiver shared by two component upstreams. Equal-layer
    judgements touch disjoint cells except X/S when their layers coincide; all
    other adjacent component pairs have strictly different layers. Therefore
    the only material same-layer ordering is X before/after S. The quotient
    retains BOTH, and counts the concrete fixed orders represented by each.
    """
    comps = [u for u in nodes if u.component]
    nts = [u for u in nodes if not u.component and u.outputs and u not in sources]
    assert len(nts) == 1
    for choices in component_choices(nodes):
        lev = layers_for(nodes, choices)
        base = sorted(comps, key=lambda u: (lev[u.name], u.name))
        total = 1
        for layer in set(lev.values()):
            total *= factorial(sum(lev[u.name] == layer for u in comps))
        tied = lev['X'] == lev['S']
        for before in (False, True) if tied else (None,):
            order = list(base)
            if before is not None:
                ix = next(j for j, u in enumerate(order) if u.name == 'X')
                iy = next(j for j, u in enumerate(order) if u.name == 'S')
                if (ix < iy) != before:
                    order[ix], order[iy] = order[iy], order[ix]
            yield dict(choices=choices, layers={u.name: lev[u.name] for u in comps},
                       nontransport_order=[u.name for u in nts],
                       order=[u.name for u in order+nts],
                       represented_fixed_orders=total//2 if tied else total)


def overflow():
    rows = []
    for dc, lower_gates, connections in it.product((1, 2), (0, 1, 2, 3),
                                                   (('top', 'lower'), ('lower', 'top'))):
        builder = lambda: overflow_builder(dc, lower_gates, connections)
        nodes, sources, _ = builder()
        for sch in overflow_schedules(nodes, sources):
            w, obj = build_world(builder, sch)
            w.run(STEPS)
            choices = obj['box'].sent
            r = dict(dead_count=dc, lower_gates=lower_gates, connections=connections,
                     lagged=sch['order'].index('X') < sch['order'].index('S'),
                     schedule=sch, branch_choices=stream(choices, kind_index=2),
                     top=stats(obj['top_sink'].received), lower=stats(obj['lower_sink'].received))
            rows.append(r)
    return rows


def branch_builder(short_count=1, difference=0, n=1, open_branch='long'):
    src, x, box = Source(), Splitter('X'), Box('blocked_box', full=True)
    src.connect(x)
    nodes, heads = [src, x, box], {}
    for name, count in (('short', short_count), ('long', short_count+difference)):
        head = Belt(name+'1', n)
        head.fill()
        x.connect(head)
        nodes.append(head)
        heads[name] = head
        last = head
        for j in range(2, count+1):
            g = Gate(name+str(j)).fill()
            last.connect(g)
            nodes.append(g)
            last = g
        if name == open_branch:
            machine, sink = machine_tail(last, nodes, 'consumer')
        else:
            last.connect(box)
    x.fill()
    return nodes, [src], dict(head=heads[open_branch], machine=machine, sink=sink)


def equal_branches():
    rows = []
    for short, diff, n, opened in it.product((1, 2), (0, 1, 2), (1, 2, 4), ('long', 'short')):
        for sch, w, obj in enum_runs(lambda: branch_builder(short, diff, n, opened), 6000):
            before = sch['order'].index('X') < sch['order'].index(obj['head'].name)
            expected = str(Fraction(8*n, 8*n+1)) if before else '1'
            r = dict(short_count=short, difference=diff, n=n, open_branch=opened,
                     X_before_open=before, schedule=sch, **stats(obj['head'].sent, 1000),
                     machine=stats(obj['machine'].starts, 1000))
            assert r['rate_fraction'] == expected, r
            rows.append(r)
    return rows


def tail_trigger():
    rows = []
    # 'following=0' is the question's direct-to-machine topology. The community
    # explicitly requires ANOTHER element AFTER S; following=1 restores it.
    for dc, n, following in it.product((1, 2, 3), (1, 2, 3, 6), (0, 1, 2)):
        for sch, w, obj in enum_runs(lambda: lag_builder(n, dead_count=dc, following=following)):
            before = sch['order'].index('X') < sch['order'].index('S')
            expected = str(Fraction(8*n, 8*n+1)) if before else '1'
            r = dict(dead_count=dc, n=n, following=following, X_before_S=before,
                     schedule=sch, **stats(obj['S'].sent))
            assert r['rate_fraction'] == expected, r
            rows.append(r)
    return rows


def mining_builder(k=3, n=1, mask=0, phase=0):
    src = Source(phase=phase, period=8)
    splitters = [Splitter('X'+str(j+1)) for j in range(k-1)]
    belts = [Belt('C'+str(j+1), n) for j in range(k-1)]
    machines = [Machine('M'+str(j+1), duration=8*k) for j in range(k)]
    outlets = [Belt('O'+str(j+1)) for j in range(k)]
    sinks = [Sink('S'+str(j+1)) for j in range(k)]
    src.connect(splitters[0])
    for j, x in enumerate(splitters):
        if mask & (1 << j):
            x.connect(belts[j], connected=0)
            x.connect(machines[j], connected=1)
        else:
            x.connect(machines[j], connected=0)
            x.connect(belts[j], connected=1)
        belts[j].connect(splitters[j+1] if j+1 < k-1 else machines[-1])
    for j, m in enumerate(machines):
        m.connect(outlets[j]).connect(sinks[j])
    return [src, *splitters, *belts, *machines, *outlets, *sinks], [src], \
           dict(machines=machines, splitters=splitters, belts=belts, outlets=outlets)


def mining_schedule(builder, late=False, reverse_outlets=False):
    nodes, sources, _ = builder()
    lev = layers_for(nodes)
    # The feed network has no same-layer competition. Product belts have open
    # sinks and factory judgements have independent product outlets; these
    # permutations commute with feed judgements. Test opposite representatives.
    comps = [u for u in nodes if u.component]
    comps.sort(key=lambda u: (lev[u.name],
               -int(u.name[1:]) if reverse_outlets and u.name.startswith('O') else 0, u.name))
    machines = [u for u in nodes if isinstance(u, Machine)]
    if late:
        machines.reverse()
    return dict(choices={}, layers={u.name: lev[u.name] for u in comps},
                nontransport_order=[u.name for u in machines],
                order=[u.name for u in comps+machines])


def mining():
    rows = []
    jobs = list(it.product((2, 3, 4, 5), (1, 3), (0, 7), (False, True)))
    jobs.extend([(8, 1, 0, False), (8, 3, 7, True)])
    for k, n, phase, late in jobs:
        for mask in range(2**(k-1)):
            builder = lambda: mining_builder(k, n, mask, phase)
            sch = mining_schedule(builder, late, reverse_outlets=late)
            w, obj = build_world(builder, sch)
            w.run(30000)
            rates = {m.name: stats(m.starts, 16000) for m in obj['machines']}
            received = {m.name: stats(m.received, 16000) for m in obj['machines']}
            r = dict(k=k, belt_length=n, phase=phase, connection_mask=mask,
                     late_machines=late, schedule=sch, starts=rates, receives=received,
                     max_input_stock={m.name: len(m.slots[0]) for m in obj['machines']})
            assert all(v['rate_fraction'] == str(Fraction(1, k)) for v in rates.values()), r
            rows.append(r)
    return dict(cases=rows, commuting_order_quotient=True)


def container_merger_builder(container='machine', phase=0, connection_reverse=False, k=1):
    feed, passing, merge, sink = Belt('feed').fill(), Belt('passing').fill('b', -8+phase), Merger('merge'), Sink()
    sa, sb = Source('factory_source'), Source('passing_source', ('b',))
    sa.connect(feed)
    sb.connect(passing)
    if container == 'machine':
        u = Machine('container', duration=8*k)
        u.output = [Item('A') for _ in range(50)]
    else:
        u = Box('container', full=True)
    feed.connect(u)
    if connection_reverse:
        passing.connect(merge, connected=0)
        u.connect(merge, connected=1)
    else:
        u.connect(merge, connected=0)
        passing.connect(merge, connected=1)
    merge.connect(sink)
    return [feed, passing, merge, sink, sa, sb, u], [sa, sb], dict(container=u, passing=passing, sink=sink)


def container_merger():
    rows = []
    for container, phase, rev, k in it.product(('machine', 'box'), range(8), (False, True), (1, 5)):
        if container == 'box' and k != 1:
            continue
        for sch, w, obj in enum_runs(lambda: container_merger_builder(container, phase, rev, k)):
            early = sch['order'].index('container') < sch['order'].index('passing')
            r = dict(container=container, phase=phase, connection_reverse=rev,
                     machine_recipe_ticks=k, container_first=early, schedule=sch,
                     container_rate=stats(obj['container'].sent), pass_rate=stats(obj['passing'].sent),
                     total=stats(obj['sink'].received), stream=stream(obj['sink'].received))
            rows.append(r)
    return rows


def protocol_box():
    rows = []
    # Empty box: the same item can enter and leave at t=0. Retains OLD sim's
    # no-immediate-return constraint but removes its artificial move budget.
    b, incoming, outgoing, sink = Box('B'), Belt('in').fill(), Belt('out'), Sink()
    incoming.connect(b).connect(outgoing).connect(sink)
    w = World([b, incoming, outgoing, sink], trace=True).run(10)
    r = dict(case='empty_receive_then_send', first_input=b.received[0][0],
             first_output=b.sent[0][0], delivered=sink.received[:2], schedule=w.schedule)
    assert r['first_input'] == r['first_output'] == 0, r
    rows.append(r)
    trace_csv('protocol_receive_send.csv', w.events)
    # Lowest-numbered slot, not global FIFO: an older b in slot 2 is bypassed
    # by a newly received a in the now-empty slot 1.
    b, incoming, outgoing, sink = Box('B'), Belt('in').fill('a'), Belt('out'), Sink()
    b.slots[1] = [Item('b')]
    incoming.connect(b).connect(outgoing).connect(sink)
    w = World([b, incoming, outgoing, sink], trace=True).run(10)
    rows.append(dict(case='numbered_slots_not_FIFO', sent=b.sent[:2],
                     first_input=b.received[0], schedule=w.schedule))
    assert [x[1] for x in b.sent[:2]] == ['a', 'b']
    trace_csv('protocol_numbered_slots.csv', w.events)
    # Wireless order in a judgement is genuinely not determined by the rule.
    for order in ('before', 'after'):
        b, incoming, outgoing, sink, wh = Box('B', wireless=True, wireless_order=order), \
                                         Belt('in').fill(), Belt('out'), Sink(), Warehouse()
        b.warehouse = wh
        incoming.connect(b).connect(outgoing).connect(sink)
        w = World([b, incoming, outgoing, sink, wh], trace=True).run(85)
        rows.append(dict(case='wireless_empty', order=order, sent=b.sent,
                         transmitted=b.transmitted, warehouse_stock=dict(wh.stock), schedule=w.schedule))
        trace_csv('protocol_wireless_'+order+'.csv', w.events)
    # Full warehouse still consumes the 40-step cooldown. Partial capacity
    # transfers as much as fits, preserving everything else in the box.
    for capacity in (0, 2):
        wh = Warehouse(limit=capacity)
        b = Box('B', wireless=True, warehouse=wh)
        b.slots[0] = [Item('a') for _ in range(3)]
        w = World([b, wh], trace=True).run(85)
        rows.append(dict(case='wireless_warehouse_capacity', capacity=capacity,
                         transmitted=b.transmitted, remaining=len(b.slots[0]),
                         warehouse_stock=dict(wh.stock)))
        assert [t for t, _ in b.transmitted] == [0, 40, 80]
    # No outlet gives only a vacuous nontransport layer bound. Enumerate whether
    # a wireless-only box runs BEFORE or AFTER its layer-1 inlet.
    for order in ('before', 'after'):
        def builder():
            b, line, wh = Box('B', full=True, wireless=True, wireless_order=order), Belt('in').fill(), Warehouse()
            b.warehouse = wh
            line.connect(b)
            return [b, line, wh], [], dict(box=b, warehouse=wh)
        for sch, w, obj in enum_runs(builder, 3):
            rows.append(dict(case='wireless_full_no_outlet', order=order, schedule=sch,
                             first_input=obj['box'].received[0][0], transmitted=obj['box'].transmitted,
                             warehouse_stock=dict(obj['warehouse'].stock)))
    return rows


def image_insertion_builder(n=1):
    # The community image has two real dead-side components, an inlet belt,
    # and an outlet belt AFTER M. None is dropped from the layer calculation.
    ore, blue = Source('ore_source', ('ore',)), Source('blue_source', ('blue',))
    inlet, x, s, y, m = Belt('ore_in'), Splitter('X'), Belt('S', n), Splitter('Y'), Merger('M')
    t, out, sink = Belt('blue'), Belt('out', 8), Sink()
    d1, d2 = Belt('D1').fill('ore'), BridgeAxis('D2').fill('ore')
    ore.connect(inlet).connect(x)
    x.connect(s).connect(y).connect(m).connect(out).connect(sink)
    x.connect(d1).connect(d2)
    blue.connect(t).connect(m)
    return [ore, blue, inlet, x, s, y, m, t, out, sink, d1, d2], [ore, blue], dict(sink=sink)


def image_overflow_builder():
    src, feed, box = Source(), Belt('feed'), Box('factory')
    top, x, s, gate, tail = Belt('top'), Splitter('X'), Belt('S'), Gate('top_gate'), Belt('top_tail', 8)
    d1, d2 = Belt('D1', 2).fill(), BridgeAxis('D2').fill()
    lower, lowline = Merger('lower'), Belt('lower_line', 5)
    lg = [Gate('lower_gate'+str(j)) for j in range(3)]
    ts, ls = Sink('top_sink'), Sink('lower_sink')
    src.connect(feed).connect(box)
    box.connect(top, connected=0).connect(x).connect(s).connect(gate).connect(tail).connect(ts)
    x.connect(d1).connect(d2)
    box.connect(lower, connected=1).connect(lowline)
    last = lowline
    for g in lg:
        last.connect(g)
        last = g
    last.connect(ls)
    return [src, feed, box, top, x, s, gate, tail, d1, d2, lower, lowline, *lg, ts, ls], [src], \
           dict(box=box, top_sink=ts, lower_sink=ls)


def image_insertion_schedules(nodes, sources):
    comps = [u for u in nodes if u.component]
    for choices in component_choices(nodes):
        lev = layers_for(nodes, choices)
        base = sorted(comps, key=lambda u: (lev[u.name], u.name))
        total = 1
        for layer in set(lev.values()):
            total *= factorial(sum(lev[u.name] == layer for u in comps))
        assert lev['Y'] == lev['blue']
        for ore_first in (False, True):
            order = list(base)
            ix = next(j for j, u in enumerate(order) if u.name == 'Y')
            iy = next(j for j, u in enumerate(order) if u.name == 'blue')
            if (ix < iy) != ore_first:
                order[ix], order[iy] = order[iy], order[ix]
            yield dict(choices=choices, layers=lev, nontransport_order=[],
                       order=[u.name for u in order], represented_fixed_orders=total//2)


def image_cases():
    insertion, overflow_rows = [], []
    for n in (1, 2, 3):
        builder = lambda: image_insertion_builder(n)
        nodes, sources, _ = builder()
        for sch in image_insertion_schedules(nodes, sources):
            w, obj = build_world(builder, sch)
            w.run(STEPS)
            insertion.append(dict(n=n, schedule=sch, **stats(obj['sink'].received),
                                  stream=stream(obj['sink'].received)))
    builder = image_overflow_builder
    nodes, sources, _ = builder()
    for sch in overflow_schedules(nodes, sources):
        w, obj = build_world(builder, sch)
        w.run(STEPS)
        overflow_rows.append(dict(schedule=sch, top=stats(obj['top_sink'].received),
                                  lower=stats(obj['lower_sink'].received),
                                  branch_choices=stream(obj['box'].sent, kind_index=2)))
    return dict(insertion=insertion, overflow=overflow_rows,
                picture_sources=['AgAABT6CrK1dyb6LQXZIVpkdV2fRpIiI.png',
                                 'AgAABT6CrK1xkhqlmQZI04bcURiLhB_H.png'])


def priority_three_builder(n=1, initial='full', connections=('left', 'belt', 'right')):
    left, center, right, merge, sink = Splitter('left'), Belt('belt', n), Splitter('right'), Merger('merge'), Sink()
    obj = {'left': left, 'belt': center, 'right': right}
    sources = []
    for name, u in obj.items():
        src = Source(name+'_source', (name,))
        src.connect(u)
        sources.append(src)
        if initial == 'full':
            u.fill(name)
    for j, name in enumerate(connections):
        obj[name].connect(merge, connected=j)
    merge.connect(sink)
    return [left, center, right, merge, sink, *sources], sources, dict(sink=sink)


def priority_three_upstreams():
    rows = []
    for n, initial, connections in it.product((1, 3), ('full', 'empty'),
                                              it.permutations(('left', 'belt', 'right'))):
        for sch, w, obj in enum_runs(lambda: priority_three_builder(n, initial, connections)):
            r = dict(belt_length=n, initial=initial, connections=connections, schedule=sch,
                     **stats(obj['sink'].received), stream=stream(obj['sink'].received))
            assert r['rate_fraction'] == '1', r
            assert len(r['stream']['cycle_counts']) == 1, r
            first = next(name for name in sch['order'] if name in ('left', 'belt', 'right'))
            assert r['stream']['cycle'] == [first], r
            rows.append(r)
    return rows


GROUPS = [('a', pure_chain), ('b', lag), ('c', machines), ('d', boxes), ('e', mergers),
          ('f_insert', priority_insertion), ('f_overflow', overflow),
          ('equal_branches', equal_branches), ('mining', mining),
          ('tail_trigger', tail_trigger), ('container_merger', container_merger),
          ('protocol_box', protocol_box), ('priority_three_upstreams', priority_three_upstreams),
          ('f_images', image_cases)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--groups', nargs='*', choices=[n for n, _ in GROUPS])
    args = parser.parse_args()
    protected_inputs()
    path = HERE/'results.json'
    result = json.loads(path.read_text()) if args.groups and path.exists() else {}
    versions = result.setdefault('group_versions', {n: '94c5e00; equivalent to ba3d767'
                               for n, _ in GROUPS if n in result})
    result['metadata'] = dict(rule='formal 2026-09-30', step='1/8 project tick',
                             steps=STEPS, warmup=2000,
                             rule_snapshot='ba3d767', multi_outlet_quantity='one item per judgement', motion='eager',
                             fixed_order_source='规则第27行，固定未知次序（本次规则修订解释）')
    for name, fn in GROUPS:
        if args.groups is not None and name not in args.groups:
            continue
        result[name] = fn()
        versions[name] = 'ba3d767'
        # Checkpoint each finished group; all evidence remains beneath sim2.
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
        print(name, 'done', flush=True)
    result['protected_input_count'] = protected_inputs()
    result['input_hashes_unchanged'] = True
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print('results.json written', flush=True)


if __name__ == '__main__':
    main()
