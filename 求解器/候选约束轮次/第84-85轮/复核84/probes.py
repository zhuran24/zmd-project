#!/usr/bin/env python3
"""Independent finite probes and repeat-state witnesses, review 84."""
import json
import os
import random
from pathlib import Path
from fractions import Fraction
from events import Net, plant, phi, skeleton

HERE = Path(__file__).resolve().parent
os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})


def full_stock():
    ans = []
    for q in (1, 2, 3):
        for k in (2, 3):
            for count in (1, 2):
                rnd = random.Random(1000 * q + 100 * k + count)
                n = Net(q)
                for j in range(count):
                    nodes, _ = plant(n, str(j), k, tuple(rnd.randrange(1, 5) for _ in range(4)))
                    for _ in range(k):
                        n.route(nodes[3], 'sink', n.ms[nodes[3]].product, rnd.randrange(1, 5))
                for m in n.ms.values():
                    m.stock = {x: 50 for x in m.inp}
                    m.out = 50 - m.batch
                    m.finish = rnd.choice([None] + list(range(q + 1)))
                for r in n.rs:
                    r.cells = [-q] * len(r.cells)
                n.prepare(rnd.randrange(100000))
                schedule = {}
                for i, r in enumerate(n.rs):
                    if r.dest != 'sink': continue
                    now, ss = 0, set()
                    while now < 800 * q:
                        ss.add(now)
                        now += q + rnd.randrange(4 * q + 1)
                    schedule[i] = ss
                req = lambda t, i: t in schedule.get(i, set())
                failures = []
                for t in range(800 * q):
                    n.settle(t, req)
                    if any(any(m.stock[x] != 50 for x in m.inp) for m in n.ms.values()):
                        failures.append(['stock', t])
                    if any(any(b is None for b in r.cells) for r in n.rs):
                        failures.append(['path', t])
                floors = {m.batch: min(n.output_floor.get(x.name, x.out) for x in n.ms.values() if x.batch == m.batch) for m in n.ms.values()}
                assert all(v >= 50 - 3 * k0 for k0, v in floors.items()), floors
                assert not failures, failures[:2]
                ans.append({'q': q, 'powder_batch': k, 'units': count, 'duration_ticks': 800,
                            'minimum_output_by_batch': floors, 'violations': failures})
    return ans


def plant_probes():
    ans = []
    for case in range(96):
        rnd = random.Random(810084 + case)
        n = Net()
        lengths = tuple(rnd.randrange(1, 5) for _ in range(4))
        nodes, rr = plant(n, 'p', 2 + case % 2, lengths)
        for _ in range(n.ms[nodes[3]].batch):
            n.route(nodes[3], 'sink', 'ppowder', rnd.randrange(1, 4))
        for m in n.ms.values():
            m.stock = {x: rnd.choice((0, 1, 2, 3, 8, 25, 50)) for x in m.inp}
            m.out = rnd.choice((0, 1, 2, 3, 8, 25, 50))
            m.finish = rnd.choice((None, 0, 1))
        for r in n.rs:
            r.cells = [rnd.choice((None, -1, 0)) for _ in r.cells]
        period = rnd.randrange(1, 10)
        patterns = {i: [rnd.choice((True, True, False)) for _ in range(period)]
                    for i, r in enumerate(n.rs) if r.dest == 'sink'}
        req = lambda t, i: patterns[i][t % period]
        n.prepare(case)
        n.settle(0, req)
        initial = phi(n, nodes, rr)
        lower = min(initial - .5, lengths[0] + lengths[1] + 176)
        minphi = initial
        seen, history, cyc = {}, [], None
        for t in range(1, 1801):
            n.settle(t, req)
            p = phi(n, nodes, rr)
            assert p >= lower, (case, initial, p, lower)
            minphi = min(minphi, p)
            key = (n.key(), t % period)
            history.append([n.ms[x].finish is not None for x in (nodes[0], nodes[2], nodes[3])])
            if key in seen:
                old = seen[key]
                hand = all(all(x) for x in history[old:t])
                if initial >= lengths[0] + lengths[1] + 2.5:
                    assert hand, (case, initial, old, t)
                cyc = {'start': old + 1, 'end': t + 1, 'period': t - old,
                       'all_C_B_K_nonempty': hand}
                break
            seen[key] = t
        ans.append({'case': case, 'lengths': lengths, 'phi0': initial, 'minimum_phi': minphi,
                    'bound': lower, 'cycle': cyc, 'cap': 1800})
    return ans


def quota_loop():
    n = Net()
    y = n.machine('Y_refiner', {'powder': 1}, 'block')
    x = n.machine('X_crusher', {'block': 1}, 'powder')
    a = n.route(y, x, 'block', 1, quota=1)
    n.route(x, y, 'powder', 15)
    n.ms[y].stock = {'powder': 50}
    n.ms[y].out = 50
    n.ms[y].finish = 0
    n.prepare(4)
    seen, trace, cycle = {}, [], None
    for t in range(300):
        n.settle(t)
        row = {'t': t, 'X_cache': n.ms[x].finish is not None, 'Y_cache': n.ms[y].finish is not None,
               'X_input': n.ms[x].stock.get('block', 0), 'Y_input': n.ms[y].stock.get('powder', 0),
               'gate': a.cells[0] is not None, 'X_starts': n.ms[x].starts, 'Y_starts': n.ms[y].starts}
        trace.append(row)
        assert row['Y_cache']
        key = n.key()
        if key in seen:
            s = seen[key]
            cycle = {'start': s, 'end': t, 'period': t - s, 'trace': trace[s:t+1],
                     'X_empty_ticks': sum(not v['X_cache'] for v in trace[s:t])}
            break
        seen[key] = t
    assert cycle and cycle['period'] == 5 and cycle['X_empty_ticks'] == 4
    # Explicit non-overlapping local geometry; only the intended routes meet.
    geometry = {'Y_body': [4, 4, 3, 3], 'X_body': [8, 4, 3, 3], 'gate': [7, 5],
                'return_belts': [(11, 5), (11, 6), (11, 7), (11, 8), (10, 8), (9, 8), (8, 8),
                                 (7, 8), (6, 8), (5, 8), (4, 8), (3, 8), (3, 7), (3, 6), (3, 5)],
                'power_pillar': [6, 9, 2, 2]}
    return {'cycle': cycle, 'geometry': geometry}


def merger_witness():
    # An always-powered plant unit is filled and frozen. Its K output is one
    # inlet of merger M. The other inlet is a directly adjacent earlier-priority
    # splitter D. A non-transmitting box Z recirculates the same powder through
    # D -> M -> return route -> Z. All route items have age >=1 at each tick.
    # The box creates storage space and refills D in the same closure. Inventory
    # is constant; D is eligible whenever M opens, so K never wins its inlet.
    box, k_out = 49, 50
    d = m = feed = -1
    returning = [-1] * 10
    trace = []
    for t in range(8):
        assert all(b is not None and b <= t-1 for b in returning + [d, m, feed]) and box == 49
        returning[-1] = None; box += 1
        for j in range(9, 0, -1):
            assert returning[j] is None and returning[j-1] <= t-1
            returning[j], returning[j-1] = t, None
        assert returning[0] is None and m <= t-1
        m, returning[0] = None, t
        m_was_empty = m is None
        # Storage priority: the direct splitter inlet outranks the K inlet.
        assert d is not None and d <= t-1 and m_was_empty
        d, m = None, t
        assert feed <= t-1
        d, feed = t, None
        box -= 1; feed = t
        trace.append({'tick': t, 'M_was_empty': m_was_empty, 'K_taken': 0,
                      'D_taken': 1, 'box': box, 'K_out': k_out})
    geometry = {'K_body': [10, 10, 3, 3], 'merger_M': [13, 11], 'splitter_D': [13, 12],
                'box_Z': [15, 11, 3, 3], 'feed_belt': [14, 12],
                'return_belts': [(13,10),(13,9),(14,9),(15,9),(16,9),(17,9),(18,9),(18,10),(18,11),(18,12)],
                'Z_input_side': 'east', 'Z_output_side': 'west', 'Z_wireless': 'off',
                'M_output_side': 'south', 'D_input_side': 'east', 'D_to_M_priority': 'earlier than K-to-M'}
    return {'period': 1, 'trace': trace, 'geometry': geometry,
            'explanation': 'Every transport moves its old item once and receives a new item. Direct-splitter storage priority excludes K.'}


def raw_cut_witness():
    for seed in range(100):
        n = Net()
        nodes, rr = plant(n)
        n.ms[nodes[0]].out = 2
        rr[0].cells = [0]
        for _ in range(2): n.route(nodes[3], 'sink', 'ppowder')
        n.prepare(seed)
        p0 = phi(n, nodes, rr)
        n.settle(0); p1 = phi(n, nodes, rr)
        n.settle(1); p2 = phi(n, nodes, rr)
        if p2 < p0 - .5:
            return {'seed': seed, 'raw_phi': p0, 'after_closure_phi': p1, 'next_phi': p2,
                    'scope': 'intermediate zero-time cut only; not claimed to be an operational debugging counterexample'}
    return None


def phase_witness():
    n=Net(q=4)
    for name,finish in (('F0',4),('Fhalf',6)):
        n.machine(name,{'ore':1},'block')
        n.ms[name].stock={'ore':49}
        n.ms[name].finish=finish
    n.prepare(0)
    previous={name:0 for name in n.ms}
    times={name:[] for name in n.ms}
    for t in range(3,15):
        n.settle(t)
        for name,m in n.ms.items():
            if m.deposits>previous[name]: times[name].append(str(Fraction(t,4)))
            previous[name]=m.deposits
    assert times=={'F0':['1','2','3'],'Fhalf':['3/2','5/2','7/2']}
    return {'debug_release':'3/4','completion_times':times,'difference_mod_one':'1/2',
            'reason':'recipe durations are exactly one tick, but initial starts had different phases'}


def skeleton_probes():
    ans = []
    for length, limit in ((1, None), (2, None), (1, 1)):
        n, plants = skeleton(length)
        if limit:
            for r in n.rs:
                if r.source in n.ores: r.quota = limit
        n.prepare(100 + length)
        seen, cycle = {}, None
        for t in range(8001):
            n.settle(t)
            key = n.key()
            totals = {p: sum(r.delivered for r in n.rs if r.dest == 'sink' and r.item == p)
                      for p in ('battery', 'capsule')}
            totals.update({p: sum(r.supplied for r in n.rs if r.source == p) for p in ('ore_fe', 'ore_src')})
            if key in seen:
                s, old = seen[key]
                delta = {p: totals[p] - old[p] for p in totals}
                rates = {p: Fraction(v, t - s) for p, v in delta.items()}
                factor = 5 if limit else 1
                assert rates == {'battery': Fraction(3, 5*factor), 'capsule': Fraction(11, 20*factor),
                                 'ore_fe': Fraction(34, factor), 'ore_src': Fraction(18, factor)}, rates
                cycle = {'start': s, 'end': t, 'period': t - s, 'delta': delta, 'rates': rates}
                break
            seen[key] = t, totals
        ans.append({'route_length': length, 'ore_gate_limit_per_5_ticks': limit,
                    'machines': len(n.ms), 'routes': len(n.rs), 'cycle': cycle, 'cap': 8000})
    return ans


def main():
    import sys
    part = sys.argv[1] if len(sys.argv) > 1 else 'local'
    if part == 'local':
        ans = {'A_full_stock': full_stock(), 'D_plant': plant_probes(), 'quota_loop': quota_loop(),
               'merger_counterexample': merger_witness(), 'raw_cut_model': raw_cut_witness(),
               'phase_counterexample': phase_witness()}
    else:
        ans = {'skeleton': skeleton_probes()}
    (HERE / f'{part}_probes.json').write_text(json.dumps(ans, ensure_ascii=False, indent=2, default=str) + '\n')
    if part == 'local':
        plants = ans['D_plant']
        print(json.dumps({'A_cases': len(ans['A_full_stock']), 'D_cases': len(plants),
                          'D_cycles': sum(x['cycle'] is not None for x in plants),
                          'D_truncated': sum(x['cycle'] is None for x in plants),
                          'quota_loop': ans['quota_loop'], 'raw_cut_model': ans['raw_cut_model']}, ensure_ascii=False))
    else:
        print(json.dumps(ans, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
