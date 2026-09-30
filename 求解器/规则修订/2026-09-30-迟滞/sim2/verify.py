#!/usr/bin/env python3
"""Independent 7..0 phase interpreter, rule unit tests, and motion equivalence.

No external implementation is imported or executed. The independent phase
interpreter does not use Item/entered timestamps or World's transfer routine.
"""
import itertools as it
import json
import random
from collections import Counter
from fractions import Fraction
from pathlib import Path

from run_checks import (branch_builder, build_world, image_insertion_builder,
                        image_insertion_schedules, image_overflow_builder, lag_builder,
                        machine_builder, mining_builder, mining_schedule, overflow_builder,
                        overflow_schedules, protected_inputs, stats)
from simulator import (Belt, Box, Bridge, Gate, Item, Machine, Merger, Sink,
                       Source, Splitter, UnknownLayer, World, layers_for, schedules)

HERE = Path(__file__).resolve().parent


def phase_run(n, schedule, dead_count=2, following=1, steps=160):
    # A position is [remaining phase, last transition step]. Age advancement
    # uses no entered timestamps. A phase becoming 0 cannot send until next step.
    cells = {'X': [[0, -1]], 'S': [[0, -1] for _ in range(n)]}
    for j in range(dead_count):
        cells['D'+str(j+1)] = [[0, -1]]
    for j in range(following):
        cells['G'+str(j+1)] = [[0, -1]]
    downstream = {'X': ['S', 'D1'], 'S': ['G1'] if following else ['sink']}
    for j in range(dead_count):
        downstream['D'+str(j+1)] = ['D'+str(j+2)] if j+1 < dead_count else []
    for j in range(following):
        downstream['G'+str(j+1)] = ['G'+str(j+2)] if j+1 < following else ['sink']
    sent, sink, states, micro = [], [], [], []

    def state(t):
        return dict(t=t, X=['x' if p is None else p[0] for p in cells['X']],
                    S=['x' if p is None else p[0] for p in cells['S']])

    def move(name, t):
        arr = cells[name]
        for j in range(len(arr)-2, -1, -1):
            p = arr[j]
            if p is not None and p[0] == 0 and p[1] != t and arr[j+1] is None:
                arr[j], arr[j+1] = None, [7, t]

    def transfer(name, dest, t):
        p = cells[name][-1]
        if p is None or p[0] != 0 or p[1] == t:
            return False
        if dest != 'sink' and cells[dest][0] is not None:
            return False
        cells[name][-1] = None
        if dest == 'sink':
            sink.append(t)
        else:
            cells[dest][0] = [7, t]
        if name == 'S':
            sent.append(t)
        move(name, t)
        if dest != 'sink':
            move(dest, t)
        return True

    for t in range(steps):
        for arr in cells.values():
            for p in arr:
                if p is not None and p[0] > 0:
                    p[0] -= 1
                    p[1] = t
        for name in cells:
            move(name, t)
        for name in schedule['order']:
            if name not in cells:
                continue
            micro.append(dict(stage=name+':判定前', **state(t)))
            # Dead branch stays full, so splitter cursor cannot affect it.
            for dest in downstream[name]:
                if transfer(name, dest, t):
                    break
            micro.append(dict(stage=name+':判定后', **state(t)))
        if cells['X'][0] is None:
            cells['X'][0] = [7, t]
        states.append(state(t))
    return sent, sink, states, micro


def state_of(w):
    result = {}
    for u in w.nodes:
        data = {}
        if hasattr(u, 'cells'):
            data['cells'] = [None if x is None else (x.kind, x.entered, x.previous) for x in u.cells]
        if hasattr(u, 'slots'):
            data['slots'] = [[(x.kind, x.previous) for x in s] for s in u.slots]
        if isinstance(u, Machine):
            data.update(output=[(x.kind, x.previous) for x in u.output],
                        cache=[(x.kind, x.previous) for x in u.cache],
                        running=u.running.name if u.running else None, remaining=u.remaining,
                        starts=u.starts, finishes=u.finishes, flushed=u.flushed)
        data['sent'] = list(u.sent)
        if hasattr(u, 'received'):
            data['received'] = list(u.received)
        data['input_cursor'] = u.input_cursor
        data['output_cursor'] = u.output_cursor
        data['last_output'] = [(c.dst.name, u.last_output[c]) for c in u.output_channels]
        result[u.name] = data
    return result


def assert_invariants(w):
    seen = set()
    for u in w.nodes:
        arrays = []
        if hasattr(u, 'cells'):
            arrays.append([x for x in u.cells if x is not None])
        if hasattr(u, 'slots'):
            arrays.extend(u.slots)
            assert all(len(s) <= 50 and len({x.kind for x in s}) <= 1 for s in u.slots)
            if isinstance(u, Machine):
                kinds = [s[0].kind for s in u.slots if s]
                assert len(kinds) == len(set(kinds))
        if isinstance(u, Machine):
            arrays.extend([u.cache, u.output])
            assert len(u.output) <= 50 and len({x.kind for x in u.output}) <= 1
        for arr in arrays:
            for x in arr:
                assert id(x) not in seen, 'duplicate item'
                seen.add(id(x))
                assert x.moved < w.t
        sent = Counter(t for t, _, _ in u.sent)
        assert not sent or max(sent.values()) <= 1, (u.name, sent)
    assert len(w.judged) == len(w.nodes), (w.t, w.judged)


def layer_and_polling_checks():
    tests = []
    # A dead end does not count as 'still sending'. Its predecessor is ALSO 1.
    x, d1, d2, s, sink = Splitter('X'), Gate('D1'), Gate('D2'), Belt('S'), Sink()
    x.connect(d1)
    d1.connect(d2)
    x.connect(s).connect(sink)
    lev = layers_for([x, d1, d2, s, sink], {'X': 'D1'})
    assert lev == {'D2': 1, 'D1': 1, 'X': 2, 'S': 1}, lev
    tests.append('dead tail layer rule')
    # Uncountable layers are NOT silently filled in by graph construction order.
    a, b = Gate('A'), Gate('B')
    a.connect(b).connect(a)
    try:
        layers_for([a, b])
        raise AssertionError('cycle must require explicit unknown layer')
    except UnknownLayer:
        pass
    assert layers_for([a, b], unknown={'A': 3, 'B': 1}) == {'A': 3, 'B': 1}
    tests.append('unknown cycle is explicit parameter')
    # Group members consume their judgement even when the first has no cargo.
    a, b, m, sink = Belt('A'), Belt('B').fill('b'), Merger('M'), Sink()
    a.connect(m, connected=0)
    b.connect(m, connected=1)
    m.connect(sink)
    nodes = [m, a, b, sink]
    sch = next(s for s in schedules(nodes) if s['order'].index('A') < s['order'].index('B'))
    w = World(nodes, schedule=sch, trace=True).run(1)
    assert m.cells[0].kind == 'b'
    assert [e for e in w.events if e['event'] == 'judge' and e['unit'] == 'B'][0]['trigger'] == 'A'
    assert_invariants(w)
    tests.append('empty first group member recruits ready peer')
    # The group is tried once, not again at a peer's nominal later turn.
    a, b, m, sink = Belt('A').fill(), Belt('B').fill('b'), Merger('M').fill('old'), Sink(opens=1)
    a.connect(m, connected=0)
    b.connect(m, connected=1)
    m.connect(sink)
    w = World([m, a, b, sink], trace=True).run(2)
    counts = Counter((e['t'], e['unit']) for e in w.events if e['event'] == 'judge')
    assert all(v == 1 for v in counts.values())
    assert not any(t == 0 for t, _, _ in a.sent+b.sent)
    assert sum(t == 1 for t, _, _ in a.sent+b.sent) == 1
    tests.append('grouped failed judgement never retries')
    # Splitter starts on second connected output; normal NT starts on first.
    x, a, b = Splitter('X').fill(), Sink('A'), Sink('B')
    x.connect(a, connected=0)
    x.connect(b, connected=1)
    w = World([x, a, b]).run(1)
    assert x.sent == [(0, 'a', 'B')]
    tests.append('splitter initial second channel')
    # Three outputs: only ONE success per NT judgement. Oldest unsuccessful
    # outlet is tried first at the next judgement, not a rotating failed cursor.
    m = Machine('M')
    m.output = [Item('A') for _ in range(10)]
    outs, sinks = [Belt('O'+str(j)) for j in range(3)], [Sink('S'+str(j)) for j in range(3)]
    for j in range(3):
        m.connect(outs[j], connected=j).connect(sinks[j])
    w = World([m, *outs, *sinks]).run(3)
    assert [t for t, _, _ in m.sent] == [0, 1, 2]
    assert [d for _, _, d in m.sent] == ['O0', 'O1', 'O2']
    assert_invariants(w)
    tests.append('NT one item; oldest outlet first')
    # Bridge axes are two independent components, not one shared judgement.
    bridge = Bridge('bridge')
    sinks = [Sink('H_sink'), Sink('V_sink')]
    for axis, sink in zip(bridge.axes, sinks):
        axis.fill()
        axis.connect(sink)
    w = World([*bridge.axes, *sinks], trace=True).run(1)
    assert sum(len(a.sent) for a in bridge.axes) == 2
    assert_invariants(w)
    tests.append('bridge independent axis judgements')
    # Manufacturing pauses preserve progress. Ready cached output still flushes
    # immediately, independent of whether the next manufacturing batch can run.
    m = Machine()
    m.slots[0] = [Item('a')]
    w = World([m]).run(3)
    before = m.remaining
    m.powered = False
    w.run(5)
    assert m.remaining == before
    m.powered = True
    w.run(6)
    assert m.finishes == [(13, 'a')]
    tests.append('powered manufacturing elapsed steps')
    # Rule 33's non-merger grade is the MAX of its member outlet layers.
    b, short, long, gate, merge, tail, sink = Box('B'), Belt('short'), Belt('long'), Gate('gate'), Merger('merge'), Belt('tail'), Sink()
    b.connect(short, connected=0)
    b.connect(long, connected=1)
    b.connect(merge, connected=2)
    short.connect(sink)
    long.connect(gate).connect(sink)
    merge.connect(tail).connect(sink)
    nodes = [b, short, long, gate, merge, tail, sink]
    w = World(nodes)
    # non-merger group level=2, merger level=2 => group's earlier connection wins
    assert [c.dst.name for c in b.channels('output', w)] == ['short', 'long', 'merge']
    tests.append('ordinary outlet group maximum and connection tie')
    return tests


def motion_equivalence():
    count, steps = 0, 0
    for n, dc, following in it.product((1, 2, 3, 6), (1, 2, 3), (0, 1, 2)):
        builder = lambda: lag_builder(n, dead_count=dc, following=following)
        nodes, sources, _ = builder()
        for sch in schedules(nodes, sources):
            a, _ = build_world(builder, sch, motion='eager')
            b, _ = build_world(builder, sch, motion='staged')
            for _ in range(100):
                a.step()
                b.step()
                assert state_of(a) == state_of(b), (n, dc, following, sch, a.t)
                steps += 1
            count += 1
    # Random valid-capacity initial states test empty middle cells, different
    # item phases and input/output backpressure, beyond synchronized full belts.
    for seed in range(160):
        def builder():
            nodes, sources, obj = branch_builder(1+seed % 2, seed % 3, 1+seed % 5, 'long')
            rng = random.Random(seed)
            for u in nodes:
                if hasattr(u, 'cells'):
                    u.cells = [None if rng.randrange(4) == 0 else Item('a', -rng.randrange(19))
                               for _ in u.cells]
            return nodes, sources, obj
        nodes, sources, _ = builder()
        opts = list(schedules(nodes, sources))
        sch = opts[seed % len(opts)]
        a, _ = build_world(builder, sch, motion='eager')
        b, _ = build_world(builder, sch, motion='staged')
        for _ in range(120):
            a.step()
            b.step()
            assert state_of(a) == state_of(b), ('random', seed, sch, a.t)
            steps += 1
        count += 1
    return dict(cases=count, compared_steps=steps, status='PASS')


def check_order_quotients():
    count = 0
    builders = [(lambda dc=dc, lg=lg: overflow_builder(dc, lg), overflow_schedules, ('X', 'S'))
                for dc, lg in it.product((1, 2), (0, 1, 2, 3))]
    builders.extend([(image_overflow_builder, overflow_schedules, ('X', 'S')),
                     (image_insertion_builder, image_insertion_schedules, ('Y', 'blue'))])
    for builder, quotient, pair in builders:
        nodes, sources, _ = builder()
        reps = list(quotient(nodes, sources))
        for seed in range(12):
            rng = random.Random(seed)
            ref = reps[seed % len(reps)]
            base_nodes, _, _ = builder()
            comp = [u for u in base_nodes if u.component]
            order = []
            for l in sorted(set(ref['layers'].values())):
                group = [u.name for u in comp if ref['layers'][u.name] == l]
                rng.shuffle(group)
                order.extend(group)
            target = next(r for r in reps if r['choices'] == ref['choices'] and
                          (r['order'].index(pair[0]) < r['order'].index(pair[1])) ==
                          (order.index(pair[0]) < order.index(pair[1])))
            sch = dict(target, order=order+target['nontransport_order'])
            a, _ = build_world(builder, target)
            b, _ = build_world(builder, sch)
            for _ in range(160):
                a.step()
                b.step()
                assert state_of(a) == state_of(b), (builder, seed, target, sch, a.t)
            count += 1
    return dict(cases=count, steps_per_case=160, status='PASS')


def check_evidence(result):
    for r in result['a']:
        assert r['rate_fraction'] == '1'
    for label in ('old_abbreviated', 'community_complete'):
        for r in result['b'][label]:
            expected = Fraction(8*r['n'], 8*r['n']+1) if r.get('X_before_S') else Fraction(1)
            assert Fraction(r['rate_fraction']) == expected, r
    for r in result['c']['cases']:
        assert r['AB_period'] == [18 if r['case'] == 3 else 16]
    for r in result['d']['examples']:
        assert r['upstream_first'] == r['k']
    for r in result['e']:
        assert r['rate_fraction'] == '1'
    for r in result['equal_branches']:
        expected = Fraction(8*r['n'], 8*r['n']+1) if r['X_before_open'] else Fraction(1)
        assert Fraction(r['rate_fraction']) == expected
        assert Fraction(r['machine']['rate_fraction']) == expected
    for r in result['mining']['cases']:
        assert all(Fraction(x['rate_fraction']) == Fraction(1, r['k']) for x in r['starts'].values())
    for r in result['container_merger']:
        assert not r['container_first']
        assert r['container_rate']['rate_fraction'] == '0'
        assert r['pass_rate']['rate_fraction'] == '1'
    for r in result['priority_three_upstreams']:
        assert r['rate_fraction'] == '1' and len(r['stream']['cycle_counts']) == 1
    for r in result['f_insert']:
        counts = r['stream']['cycle_counts']
        if not r['ore_first']:
            assert counts == {'blue': 1}, r
        elif r['lagged']:
            assert counts == {'ore': r['n']+1, 'blue': 1}, r
        else:
            assert counts == {'ore': 1}, r
    for r in result['f_overflow']:
        lev = r['schedule']['layers']
        top = (lev['top'], r['connections'].index('top'))
        lower = (lev['lower'], r['connections'].index('lower'))
        expected = ('0', '1') if lower < top else ('3/4', '1/4') if r['lagged'] else ('1', '0')
        assert (r['top']['rate_fraction'], r['lower']['rate_fraction']) == expected, r
    for r in result['f_images']['insertion']:
        sch = r['schedule']
        early = sch['order'].index('Y') < sch['order'].index('blue')
        lagged = sch['order'].index('X') < sch['order'].index('S')
        expected = {'blue': 1} if not early else {'ore': r['n']+1, 'blue': 1} if lagged else {'ore': 1}
        assert r['stream']['cycle_counts'] == expected, r
    for r in result['f_images']['overflow']:
        lagged = r['schedule']['order'].index('X') < r['schedule']['order'].index('S')
        expected = ('3/4', '1/4') if lagged else ('1', '0')
        assert (r['top']['rate_fraction'], r['lower']['rate_fraction']) == expected, r
    return True


def main():
    result = json.loads((HERE/'results.json').read_text())
    tests = layer_and_polling_checks()
    phase_cases, phase_steps = 0, 0
    for n, dc, following in it.product((1, 2, 3, 6), (1, 2, 3), (0, 1, 2)):
        builder = lambda: lag_builder(n, dead_count=dc, following=following)
        nodes, sources, _ = builder()
        for sch in schedules(nodes, sources):
            w, obj = build_world(builder, sch)
            states = []
            for _ in range(160):
                w.step()
                states.append(dict(t=w.t-1, X=obj['X'].phase(w.t-1), S=obj['S'].phase(w.t-1)))
            deliveries, sink, independent_states, micro = phase_run(n, sch, dc, following)
            assert [t for t, _, _ in obj['S'].sent] == deliveries, (n, dc, following, sch)
            assert [t for t, _ in obj['sink'].received] == sink, (n, dc, following, sch)
            assert states == independent_states, (n, dc, following, sch)
            phase_cases += 1
            phase_steps += 160
    _, _, states, micro = phase_run(2, result['b']['phase_schedule'], steps=45)
    assert states == result['b']['phase_trace_n2']
    (HERE/'b_n2_microphase.json').write_text(json.dumps(micro, ensure_ascii=False, indent=2)+'\n')
    invariant_steps = 0
    for case in (1, 2, 3):
        builder = lambda: machine_builder(case)
        w, _ = build_world(builder)
        for _ in range(1200):
            w.step()
            assert_invariants(w)
            invariant_steps += 1
    motion = motion_equivalence()
    quotients = check_order_quotients()
    check_evidence(result)
    count = protected_inputs()
    evidence = dict(rule_snapshot='ba3d767', phase_comparison_cases=phase_cases,
                    phase_comparison_steps=phase_steps, rule_unit_tests=tests,
                    invariant_steps=invariant_steps, motion_equivalence=motion,
                    order_quotient_checks=quotients,
                    protected_input_count=count, input_hashes_unchanged=True, status='PASS')
    (HERE/'verification.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(evidence, ensure_ascii=False))


if __name__ == '__main__':
    main()
