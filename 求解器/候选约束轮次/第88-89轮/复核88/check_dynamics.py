"""Exact finite probes; does not substitute for the real-time proofs in the report."""
from collections import Counter
from hashlib import sha256
from pathlib import Path
import argparse
import json
import os
import random
import time

from exact_model import Model, plant

HERE = Path(__file__).resolve().parent


def plant_case(case):
    r = random.Random(880000+case)
    q = r.choice([1, 2, 3, 5, 7, 11, 17])
    lengths = tuple(r.randint(1, 5) for _ in range(4))
    k = r.choice([2, 3])
    outlets = r.randint(0, 3)
    m = plant(q, 881000+case, lengths, k, outlets)
    m.randomize('low' if case%3==0 else 'dense')
    # Arbitrary downstream acceptance in a prefix, periodic thereafter.
    prefix = 25*q
    period = r.choice([1, 2, 3, 5])*q
    calendars = [[r.random()<r.choice([.15, .5, .9, 1.]) for _ in range(period)]
                 for _ in range(outlets)]
    prefix_calendar = [[r.random()<.65 for _ in range(prefix+1)] for _ in range(outlets)]
    def sink(j, t):
        if j<4:
            return False
        if t<=prefix:
            return prefix_calendar[j-4][t]
        return calendars[j-4][(t-prefix-1)%period]
    m.sink = sink
    m.close()
    phi0 = m.phi2()
    lower = min(phi0-1, 2*(lengths[0]+lengths[1]+176))
    threshold = 2*(lengths[0]+lengths[1])+5
    records = []
    seen = {}
    violations = []
    blocked = 0
    mixed = set()
    minimum = phi0
    cyc = None
    max_units = 1600*q
    for t in range(1, max_units+1):
        m.t = t
        if t<=prefix and t%max(1, q//2)==0:
            # Over-approximation of offline permutations: also varies judgement
            # order during this test prefix; after the prefix it stays fixed.
            r.shuffle(m.actions)
            for machine in m.machines:
                if machine.outgoing:
                    machine.op = r.randrange(len(machine.outgoing))
        m.close()
        phi = m.phi2()
        minimum = min(minimum, phi)
        if phi<lower:
            violations.append(['population', t, phi, lower])
            break
        if t>=q and m.lines[0].cells[0] is not None and m.lines[0].cells[0]<=t:
            blocked += 1
            assert phi>=2*(lengths[0]+lengths[1])+353, (case, t, phi)
        idle = [i for i in (0, 2, 3) if m.machines[i].due is None]
        records.append((t, idle, phi))
        if t>prefix and t%q==0:
            sig = m.signature(period)
            if sig in seen:
                cyc = (seen[sig], t)
                break
            seen[sig] = t
    result = dict(case=case, q=q, lengths=lengths, k=k, outlets=outlets,
                  phi0_twice=phi0, minimum_twice=minimum, bound_twice=lower,
                  blocked_checks=blocked, closure_checks=len(records),
                  cycle=cyc, threshold_met=phi0>=threshold, violations=violations)
    if cyc:
        a, b = cyc
        idle_count = sum(bool(v) for t, v, _ in records if a<=t<b)
        result['idle_states_in_cycle'] = idle_count
        if phi0>=threshold:
            assert idle_count==0, (case, cyc, idle_count)
        if phi0>=threshold and outlets:
            ready = {(t, j) for t, j in m.empty if j>=4}
            moved = Counter((t, j) for t, j in m.moves if j>=4)
            windows = 0
            for s in range(a, b-q+1):
                counts = [sum(moved.get((t, j), 0) for t in range(s, s+q))
                          for j in range(4, 4+outlets)]
                flags = [any((t, j) in ready for t in range(s, s+q))
                         for j in range(4, 4+outlets)]
                assert all(v<=1 for v in counts)
                assert sum(counts)>=min(sum(flags), k), (case, s, counts, flags)
                if outlets<=k:
                    assert all(n==int(flag) for n, flag in zip(counts, flags)), (case, s)
                windows += 1
            result['unit_windows'] = windows
            mixed = {t%q for t, j in m.moves if a<=t<b}
        result['cycle_event_phases'] = sorted(mixed)
        result['cycle_state_sha256'] = sha256(repr(m.signature(period)).encode()).hexdigest()
    return result


def negative_controls():
    # Legal 5-tick blue-powder/refining loop: source cache stays occupied,
    # but a quota on the incoming dedicated line invalidates the relay premise.
    m = Model(q=3, seed=88881)
    y = m.machine('refine_blue_powder_to_block')
    x = m.machine('crush_block_to_blue_powder')
    first = m.line(y, x, length=1, label='blue_block_quota')
    m.lines[first].gate_every = 5
    m.line(x, y, length=7, label='blue_powder_return')
    m.machines[y].stock = [50]
    m.machines[y].output = 50
    m.machines[y].due = 0
    m.prepare()
    m.close()
    seen, states = {}, []
    for t in range(1, 600):
        m.t = t
        m.close()
        states.append((t, m.machines[y].due is None, m.machines[x].due is None))
        if t%m.q==0:
            sig = m.signature()
            if sig in seen:
                a, b = seen[sig], t
                cycle = [s for s in states if a<=s[0]<b]
                assert b-a==5*m.q
                assert all(not s[1] for s in cycle)
                assert sum(s[2] for s in cycle)==4*m.q
                quota = dict(start_units=a, end_units=b, q=m.q,
                             source_idle=sum(s[1] for s in cycle),
                             recipient_idle=sum(s[2] for s in cycle),
                             certificate=repr(sig))
                break
            seen[sig] = t
    else:
        raise AssertionError('quota control did not cycle')
    # Removing sufficient-channel inequality: a shape recipe 2->1, one input.
    m = Model(q=5, seed=88882)
    x = m.machine('shape', need=(2,))
    m.line(None, x, length=2)
    m.line(x, None, length=1)
    m.prepare()
    m.close()
    idle, starts = 0, []
    for t in range(1, 251):
        m.t = t
        m.close()
        if t>200:
            idle += m.machines[x].due is None
    assert idle==25
    return dict(quota=quota, insufficient_channels=dict(q=5, checked_units=50, idle_units=idle))


def skeleton(q, seed):
    m = Model(q=q, seed=seed)
    r = random.Random(seed+1)
    def link(a, b, slot=0, label=''):
        return m.line(a, b, slot, r.randint(1, 4), label)
    iron_ref = [m.machine(f'iron_ore_refine{i}') for i in range(34)]
    iron_cr = [m.machine(f'iron_crush{i}') for i in range(34)]
    ore_cr = [m.machine(f'originium_crush{i}') for i in range(18)]
    ore_lines = []
    for a, b in zip(iron_ref, iron_cr):
        ore_lines.append(link(None, a, label='iron_ore'))
        link(a, b)
    for a in ore_cr:
        ore_lines.append(link(None, a, label='originium_ore'))
    gi = [m.machine(f'grind_iron{i}', need=(2, 1)) for i in range(17)]
    go = [m.machine(f'grind_originium{i}', need=(2, 1)) for i in range(9)]
    gf = [m.machine(f'grind_flower{i}', need=(2, 1)) for i in range(6)]
    for srcs, dest in [(iron_cr, gi), (ore_cr, go)]:
        for i, g in enumerate(dest):
            link(srcs[2*i], g)
            link(srcs[2*i+1], g)
    plant_units = []
    leaf_k, flower_k = [], []
    for kind, count, k, ks in [('leaf', 11, 3, leaf_k), ('flower', 6, 2, flower_k)]:
        for i in range(count):
            c = m.machine(f'{kind}_C{i}', k=2)
            a = m.machine(f'{kind}_A{i}')
            b = m.machine(f'{kind}_B{i}')
            crusher = m.machine(f'{kind}_K{i}', k=k)
            ca = link(c, a)
            ac = link(a, c)
            link(c, b)
            link(b, crusher)
            plant_units.append((c, a, ca, ac))
            ks.append(crusher)
    for i, g in enumerate(gi+go+gf):
        link(leaf_k[i//3], g, slot=1)
    for k, g in zip(flower_k, gf):
        link(k, g)
        link(k, g)
    steel = [m.machine(f'steel{i}') for i in range(17)]
    for g, s in zip(gi, steel):
        link(g, s)
    parts = [m.machine(f'parts{i}') for i in range(6)]
    bottles = [m.machine(f'bottle{i}', need=(2,)) for i in range(6)]
    for a, b in zip(steel[:6], parts):
        link(a, b)
    for i in range(5):
        link(steel[6+2*i], bottles[i])
        link(steel[7+2*i], bottles[i])
    link(steel[16], bottles[5])
    pack = [m.machine(f'battery{i}', need=(10, 15), d=5) for i in range(3)]
    can = [m.machine(f'capsule{i}', need=(10, 10), d=5) for i in range(3)]
    battery_lines, capsule_lines = [], []
    for i in range(3):
        for src in parts[2*i:2*i+2]:
            link(src, pack[i])
        for src in go[3*i:3*i+3]:
            link(src, pack[i], 1)
        for src in bottles[2*i:2*i+2]:
            link(src, can[i])
        for src in gf[2*i:2*i+2]:
            link(src, can[i], 1)
        battery_lines.append(link(pack[i], None, label='battery'))
        capsule_lines.append(link(can[i], None, label='capsule'))
    assert len(m.machines)==221 and len(m.lines)==317
    m.prepare()
    m.randomize('dense')
    for c, a, ca, ac in plant_units:
        m.machines[c].stock = [50]
        m.machines[a].stock = [50]
    return m, ore_lines, battery_lines, capsule_lines, plant_units


def skeleton_case(q, seed):
    m, ores, batteries, capsules, plants = skeleton(q, seed)
    # Nonintegral stop/resume times when q>1. No inputs or settings change.
    history = [(0, True, True), (200*q+1, False, True),
               (520*q+2, False, False), (1000*q+3, True, False),
               (1250*q+4, True, True)]
    history = [(t, b, c) for t, b, c in history]
    phase = 0
    accept = [True, True]
    m.sink = lambda j, t: accept[0] if j in batteries else accept[1]
    m.close(log=False)
    phi0 = [m.phi2(c, a, ca, ac) for c, a, ca, ac in plants]
    assert all(phi>=2*(len(m.lines[ca].cells)+len(m.lines[ac].cells))+5
               for phi, (c, a, ca, ac) in zip(phi0, plants))
    next_sample = q
    seen = {}
    checks = 0
    event_checks = []
    cycle = None
    while m.t<6500*q:
        next_external = history[phase+1][0] if phase+1<len(history) else 10**12
        m.t = m.future(min(next_sample, next_external))
        if m.t==next_external:
            phase += 1
            accept[:] = history[phase][1:]
        m.close(log=False)
        checks += 1
        event_checks.append((m.t,
            [machine.name for machine in m.machines
             if machine.name not in ('bottle5', 'capsule2') and machine.due is None],
            [j for j, line in enumerate(m.lines)
             if line.source is not None
             and m.machines[line.source].d==1
             and m.machines[line.source].name!='bottle5'
             and line.cells[0] is None]))
        for old, (c, a, ca, ac) in zip(phi0, plants):
            bound = min(old-1, 2*(len(m.lines[ca].cells)+len(m.lines[ac].cells)+176))
            assert m.phi2(c, a, ca, ac)>=bound
        if m.t==next_sample:
            next_sample += q
            if phase==len(history)-1:
                sig = m.signature()
                if sig in seen:
                    t0, counts0, state0 = seen[sig]
                    counts1 = m.counters()
                    delta = {key: [b-a for a, b in zip(counts0[key], counts1[key])]
                             for key in counts0}
                    duration = m.t-t0
                    assert all(delta['accepted'][j]*q==duration for j in ores)
                    bcount = sum(delta['delivered'][j] for j in batteries)
                    ccount = sum(delta['delivered'][j] for j in capsules)
                    assert bcount*q*5==duration*3
                    assert ccount*q*20==duration*11
                    checked = [x for x in event_checks if t0<=x[0]<m.t]
                    assert all(not idle and not empty for _, idle, empty in checked), checked
                    cycle = dict(start_units=t0, end_units=m.t, duration_ticks=duration//q,
                                 battery_deliveries=bcount, capsule_deliveries=ccount,
                                 ore_acceptances=[delta['accepted'][j] for j in ores],
                                 starts_by_machine={machine.name: v for machine, v in
                                                    zip(m.machines, delta['starts'])},
                                 state_at_start=state0, state_at_end=repr(sig),
                                 relay_event_checks=len(checked),
                                 source_future_event_phases=sorted({x%q for line in m.lines
                                     for x in line.cells if x is not None and x>m.t}),
                                 equal_state_sha256=sha256(repr(sig).encode()).hexdigest())
                    break
                seen[sig] = (m.t, m.counters(), repr(sig))
            m.moves.clear()
            m.empty.clear()
    assert cycle is not None, (q, seed, 'no cycle within cutoff')
    return dict(q=q, seed=seed, history=history, machines=len(m.machines), paths=len(m.lines),
                event_closures=checks, plant_initial_phi_twice=phi0, cycle=cycle)


def main():
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['plants', 'factory', 'controls'])
    parser.add_argument('--n', type=int, default=100)
    parser.add_argument('--offset', type=int, default=0)
    args = parser.parse_args()
    start = time.monotonic()
    if args.mode=='plants':
        cases = []
        for i in range(args.offset, args.offset+args.n):
            case = plant_case(i)
            assert not case['violations'], case
            cases.append(case)
            if len(cases)%25==0:
                print(json.dumps(dict(progress=len(cases), seconds=round(time.monotonic()-start, 2))), flush=True)
        summary = dict(cases=len(cases), cycles=sum(x['cycle'] is not None for x in cases),
                       cutoffs=sum(x['cycle'] is None for x in cases),
                       threshold_cycles=sum(x['cycle'] is not None and x['threshold_met'] for x in cases),
                       low_phi_idle_cycles=sum(x.get('idle_states_in_cycle', 0)>0 for x in cases),
                       mixed_cycles=sum(len(x.get('cycle_event_phases', []))>1 for x in cases),
                       closed_states=sum(x['closure_checks'] for x in cases),
                       unit_windows=sum(x.get('unit_windows', 0) for x in cases),
                       mature_block_checks=sum(x['blocked_checks'] for x in cases),
                       violations=0, seconds=round(time.monotonic()-start, 3))
        out = dict(summary=summary, cases=cases)
        filename = f'plants_{args.offset}_{args.n}.json'
    elif args.mode=='factory':
        out = skeleton_case(args.n, 889000+args.offset)
        summary = {k: out[k] for k in ['q', 'seed', 'machines', 'paths', 'event_closures']}
        summary['cycle'] = {k: out['cycle'][k] for k in ['start_units', 'end_units', 'duration_ticks',
                            'battery_deliveries', 'capsule_deliveries', 'equal_state_sha256']}
        filename = f'factory_q{args.n}_{args.offset}.json'
    else:
        out = negative_controls()
        summary = out
        filename = 'controls.json'
    (HERE/filename).write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__=='__main__':
    main()
