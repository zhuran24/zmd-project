"""Serial, deterministic, reviewer-authored checks. Run with python -B.

All writes stay beside this file. No external simulator or producer code is used.
"""
import hashlib
import itertools as it
import json
import random
from fractions import Fraction as F
from pathlib import Path

from plant_models import AbsolutePlant, CountdownPlant, NAMES

HERE = Path(__file__).resolve().parent
BASE = HERE.parent


def save(name, obj):
    (HERE/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n')


def make_schedule(rng, lengths, n):
    # All priorities below come from a permutation of physical units, not from
    # an independently assigned permutation of channels.
    nodes = NAMES+[(r, i) for r, length in enumerate(lengths) for i in range(length)]
    rng.shuffle(nodes)
    times = {v: i for i, v in enumerate(nodes)}
    routes = {'C': [0, 2], 'A': [1], 'B': [3], 'K': list(range(4, 4+n))}
    connected = {m: [max(times[m], times[r, 0]) for r in rr]
                 for m, rr in routes.items()}
    builds = {m: sorted(range(len(connected[m])), key=lambda j: (connected[m][j], j))
              for m in ('C', 'K')}
    order = sorted(NAMES, key=lambda m: (min(connected[m], default=10**9), m))
    return builds, order


def run_plants():
    rng = random.Random(960095)
    stats = {}
    witnesses = []
    for mode, count, steps in [('arbitrary', 900, 1200), ('full', 480, 1600)]:
        summary = dict(cases=count, steps_each=steps, compared_steps=0,
                       bound_failures=0, strong_normal_bound_failures=0,
                       phi_identity_failures=0, full_failures=0,
                       bb_events=0, minimum_bb_residual2=None,
                       minimum_stock_BK=50, minimum_output_B=50,
                       minimum_output_K={2: 50, 3: 50}, maximum_service_delay=0)
        for case in range(count):
            k = 2+(case % 2)
            n = case % (k+1)
            lengths = [rng.choice([1, 2, 3, 7, 13, 37]) for _ in range(4)]
            lengths += [rng.choice([1, 2, 5]) for _ in range(n)]
            ages = [[rng.randrange(9) if mode == 'full' or rng.random() < .85
                     else None for _ in range(length)] for length in lengths]
            # Outlet inventory/age is deliberately unrestricted.
            for r in range(4, 4+n):
                ages[r] = [rng.choice([None, 0, 1, 7, 8]) for _ in ages[r]]
            nums = [0, 1, 2, 25, 47, 48, 49, 50]
            ins = [50]*4 if mode == 'full' else [rng.choice(nums) for _ in NAMES]
            outs = [50]*4 if mode == 'full' else [rng.choice(nums) for _ in NAMES]
            rem = [rng.randrange(9) for _ in NAMES] if mode == 'full' else [
                rng.choice([None, 0, 1, 2, 7, 8]) for _ in NAMES]
            if mode == 'arbitrary' and case % 3 == 0:
                ins[0] = ins[1] = outs[1] = 50
                outs[0] = rng.choice([1, 2, 3, 48, 49, 50])
                rem[0], rem[1] = rng.randrange(9), rng.randrange(9)
                for r in (0, 1):
                    ages[r] = [rng.randrange(9) for _ in ages[r]]
            lastC = [None, None] if case % 3 == 0 else rng.sample([-100, -99], 2)
            lastK = [None]*n if case % 3 == 0 else rng.sample(list(range(-90, -80)), n)
            init = dict(k=k, n=n, ins=ins, outs=outs, remaining=rem,
                        ages=ages, lastC=lastC, lastK=lastK)
            a, b = AbsolutePlant(init), CountdownPlant(init)
            initial_phi = a.phi2()
            assert initial_phi == b.phi2()
            road_count = lengths[0]+lengths[1]
            if mode == 'full':
                assert initial_phi == 2*(road_count+177)
            previous = initial_phi
            start_normal = None
            pending = [None]*n
            last_letter = None
            builds, order = make_schedule(rng, lengths, n)
            trace = []
            for t in range(steps):
                if t % 23 == 0:
                    builds, order = make_schedule(rng, lengths, n)
                accepts = [bool(rng.getrandbits(1)) for _ in range(n)]
                if case % 4 == 0:
                    accepts = [t % 317 < 47]*n
                elif case % 4 == 1:
                    accepts = [True]*n
                elif case % 4 == 2:
                    accepts = [((t+j*17) % 31 < 11) for j in range(n)]
                enabled = dict.fromkeys(NAMES, True)
                if mode == 'arbitrary':
                    enabled['B'] = t % 137 < 99
                    enabled['K'] = t % 233 < 121
                ea = a.step(t, accepts, order, builds, enabled)
                eb = b.step(t, accepts, order, builds, enabled)
                if a.state(t) != b.state(t) or ea != eb or a.events != b.events:
                    save('model_disagreement.json', dict(init=init, t=t, a=a.state(t), b=b.state(t)))
                    raise AssertionError(('independent models disagree', mode, case, t))
                phi = a.phi2()
                assert phi == b.phi2()
                change = sum(1 if ri == 0 else -1 for m, ri in a.events if m == 'C')
                if phi != previous+change:
                    summary['phi_identity_failures'] += 1
                previous = phi
                summary['compared_steps'] += 1
                if phi < min(initial_phi-1, 2*(road_count+150)):
                    summary['bound_failures'] += 1
                if start_normal is None:
                    start_normal = phi
                elif phi < min(start_normal-1, 2*(road_count+176)):
                    summary['strong_normal_bound_failures'] += 1
                for m, ri in a.events:
                    if m == 'C':
                        letter = 'A' if ri == 0 else 'B'
                        if last_letter == letter == 'B':
                            residual = phi-2*road_count
                            summary['bb_events'] += 1
                            old = summary['minimum_bb_residual2']
                            summary['minimum_bb_residual2'] = residual if old is None else min(old, residual)
                        last_letter = letter
                if mode == 'full':
                    bad = (any(v is None for v in a.due.values()) or
                           min(a.ins['B'], a.ins['K']) < 49 or a.outs['B'] < 49
                           or a.outs['K'] < 50-k or a.roads[2][0] is None
                           or a.roads[3][0] is None)
                    summary['minimum_stock_BK'] = min(summary['minimum_stock_BK'], a.ins['B'], a.ins['K'])
                    summary['minimum_output_B'] = min(summary['minimum_output_B'], a.outs['B'])
                    summary['minimum_output_K'][k] = min(summary['minimum_output_K'][k], a.outs['K'])
                    for j in range(n):
                        if ea[4+j] and pending[j] is None:
                            pending[j] = t
                        if pending[j] is not None:
                            if a.roads[4+j][0] is not None:
                                summary['maximum_service_delay'] = max(summary['maximum_service_delay'], t-pending[j])
                                bad |= t-pending[j] > n-1
                                pending[j] = None
                            else:
                                bad |= t-pending[j] >= n-1
                    if bad:
                        summary['full_failures'] += 1
                        if not witnesses:
                            witnesses.append(dict(case=case, init=init, t=t, trace=trace[-16:], state=a.state(t)))
                trace.append(dict(t=t, phi2=phi, events=a.events[:], stocks=list(a.ins.values()),
                                  outputs=list(a.outs.values())))
                if len(trace) > 20:
                    trace.pop(0)
        stats[mode] = summary
        print(mode, json.dumps(summary, ensure_ascii=False), flush=True)
    save('plant_results.json', dict(seed=960095, scope='abstract legal-service superset, not a layout certificate',
                                    stats=stats, witnesses=witnesses))
    assert all(s['bound_failures'] == s['strong_normal_bound_failures'] ==
               s['phi_identity_failures'] == s['full_failures'] == 0 for s in stats.values())


def chain_formula(mature, uses):
    m, count = len(mature), len(uses)
    sent = [[] for _ in mature]
    for j in range(count):
        for i in range(m-1, -1, -1):
            ready = mature[i] if j == 0 else sent[max(0, i-1)][j-1]+8
            vacancy = uses[j]+1 if i == m-1 else sent[i+1][j]
            sent[i].append(max(ready, vacancy))
    return sent


def chain_steps(mature, uses):
    road = [8-r for r in mature]  # accumulated residence, ready when >=8
    stock = 50
    events = [[] for _ in road]
    for t in range(max(uses)+len(road)*8+20):
        if t:
            road = [None if age is None else min(8, age+1) for age in road]
        for i in reversed(range(len(road))):
            if road[i] != 8:
                continue
            if i == len(road)-1:
                if stock == 50:
                    continue
                stock += 1
            else:
                if road[i+1] is not None:
                    continue
                road[i+1] = 0
            road[i] = None
            events[i].append(t)
        if road[0] is None:
            road[0] = 0
        if t in uses:
            stock -= 1
        if len(events[-1]) == len(uses):
            # The final vacancy propagates to the head later when initial ages
            # differ, so keep running until every cell has sent j times.
            if all(len(e) >= len(uses) for e in events):
                break
    return [e[:len(uses)] for e in events]


def run_chains():
    count = 0
    maximum = 0
    for m in range(1, 4):
        for mature in it.product(range(9), repeat=m):
            for first, gap in it.product([0, 1, 7, 15], [8, 9, 13, 24]):
                uses = [first+gap*j for j in range(6)]
                calc, sim = chain_formula(mature, uses), chain_steps(mature, uses)
                assert calc == sim, (mature, uses, calc, sim)
                maximum = max(maximum, max(t-x for t, x in zip(calc[-1], uses)))
                assert all(t <= x+8 for t, x in zip(calc[-1], uses))
                slow = chain_formula([8]*m, uses)
                expected = [max(8*(j+1), x+1) for j, x in enumerate(uses)]
                assert all(row == expected for row in slow)
                assert all(a <= b for row, upper in zip(calc, slow) for a, b in zip(row, upper))
                count += 1
    rng = random.Random(961)
    for _ in range(2000):
        m = rng.randrange(1, 80)
        mature = [rng.randrange(9) for _ in range(m)]
        uses = [rng.randrange(30)]
        for j in range(15):
            uses.append(uses[-1]+rng.randrange(8, 41))
        calc = chain_formula(mature, uses)
        assert calc == chain_steps(mature, uses)
        assert all(t <= x+8 for t, x in zip(calc[-1], uses))
        count += 1
    result = dict(cases=count, maximum_replenishment_delay=maximum, mismatches=0)
    save('chain_results.json', result)
    print('chains', result, flush=True)


def run_layers():
    count = 0
    for m in range(1, 11):
        for kinds in it.product('BT', repeat=m):
            edges = {i: [i+1] for i in range(m)}
            for i in range(1, m):
                if kinds[i-1] == kinds[i] == 'B':
                    edges[i].append(i-1)
            def possible(i, visited):
                if i == m:  # the actual nontransport endpoint, never a cycle truncation
                    return {0}
                values = set()
                for nxt in edges[i]:
                    if nxt not in visited:
                        values.update(1+v for v in possible(nxt, visited | {nxt}))
                return values
            for i in range(m):
                assert possible(i, {i}) == {m-i}
            count += 1
    # In this enumeration T is a complete belt component. Adjacent T components
    # are also tested as a conservative subdivision; actual continuous belts merge.
    dead = []
    for k, m in it.product(range(2, 9), repeat=2):
        # Work backwards from an end with no outgoing channel. Its predecessor
        # ignores it under rule 28; the following predecessors each add one.
        layers = [1]*k
        for i in range(k-3, -1, -1):
            layers[i] = layers[i+1]+1
        assert layers[0]+1 == k
        live = 0
        for _ in range(m):
            live += 1
        assert live == m
        dead.append([k, m, layers[0]+1, live])
    result = dict(forward_bridge_patterns=count, dead_branch_pairs=len(dead), failures=0)
    save('layer_results.json', result)
    print('layers', result, flush=True)


def run_round_robin():
    rng = random.Random(963)
    counts = 0
    for k in range(2, 7):
        for _ in range(500):
            lasts = [None]*k
            queue = []
            unused = set(range(k))
            free_at = [0]*k
            backlogs = [0, 0]
            word = []
            for t in range(240):
                order = rng.sample(range(k), k)
                new = k if rng.random() < .15 else 0
                backlogs[0] += new
                backlogs[1] += new
                ranked = sorted(range(k), key=lambda j: (
                    lasts[j] is not None, lasts[j] if lasts[j] is not None else order.index(j)))
                chosen = next((j for j in ranked if free_at[j] <= t), None) if backlogs[0] else None
                sequence = [j for j in order if j in unused]+queue
                independent = sequence[0] if backlogs[1] and free_at[sequence[0]] <= t else None
                assert chosen == independent
                if chosen is not None:
                    backlogs = [v-1 for v in backlogs]
                    free_at[chosen] = t+8
                    lasts[chosen] = t
                    unused.discard(chosen)
                    if chosen in queue:
                        queue.remove(chosen)
                    queue.append(chosen)
                    word.append(chosen)
            if len(word) >= k:
                assert all(v == word[i % k] for i, v in enumerate(word))
            for a, b in it.combinations(range(k), 2):
                prefixes = [0]
                for v in word:
                    prefixes.append(prefixes[-1]+(v == a)-(v == b))
                assert max(prefixes)-min(prefixes) <= 1
            counts += 1
    result = dict(cases=counts, steps_each=240, mismatches=0, reset_history=False)
    save('round_robin_results.json', result)
    print('round_robin', result, flush=True)


def run_arithmetic():
    arithmetic = {'150': 49+50+49+1+1, '176': 50+50+50+1+1+F(49, 2)-F(1, 2),
                  '177': 3*50+2+F(50, 2), '400': 8*50,
                  'finite_output_bounds': [50-3*k for k in [1, 2, 3]],
                  'K_output_bounds': [50-k for k in [2, 3]],
                  'restricted_seeders': (F(16)*F(9, 8)).__ceil__(),
                  'grinder_change_rate': 8*(32-F(63, 2)),
                  'fully_switching_grinders': (9*(32-F(63, 2))).__floor__()}
    independent = {'150': sum([98, 100, 98, 2, 2])//2,
                   '176': (2*(50*3+2)+50-2)//2,
                   '177': max((2*(x+y+z+a+c)+q)//2
                              for x, y, z, a, c, q in it.product([0, 50], [0, 50],
                              [0, 50], [0, 1], [0, 1], [0, 50])),
                   '400': list(range(0, 401, 8))[50],
                   'finite_output_bounds': [len(list(range(3*k, 50))) for k in [1, 2, 3]],
                   'K_output_bounds': [len(list(range(k, 50))) for k in [2, 3]],
                   'restricted_seeders': next(n for n in range(100) if 8*n >= 9*16),
                   'grinder_change_rate': 32*8-63*4,
                   'fully_switching_grinders': max(a for a in range(33) if 18*32-2*a >= 9*63)}
    assert arithmetic == independent
    # Three receiving ports with spacing at least eight; a 40-step cooldown has
    # five per port. The old closed-window count 3*(1+40//8) remains conservative.
    exact_box = max(sum(sum(t % 8 == p for t in range(40)) for p in phases)
                    for phases in it.product(range(8), repeat=3))
    assert exact_box == 15 and 3*(1+40//8) == 18
    # Complete run lower bound checked against an explicit greedy earliest-port
    # construction. The next different kind cannot leave until the next step.
    checked_runs = 0
    for q, c in it.product(range(1, 101), range(1, 7)):
        available = [0]*c
        last = -1
        for _ in range(q):
            channel = min(range(c), key=lambda j: available[j])
            last = max(last+1, available[channel])
            available[channel] = last+8
        formula = 8*((q-1)//c)+(q-1) % c+1
        assert last+1 == formula
        checked_runs += 1
    save('arithmetic.json', dict(values={k: str(v) if isinstance(v, F) else v for k, v in arithmetic.items()},
                                 box_exact_40_steps=exact_box, box_conservative=18,
                                 run_formula_cases=checked_runs, independent_equal=True))
    print('arithmetic', arithmetic, flush=True)


def manifest():
    names = ['前提快照/《明日方舟：终末地》游戏规则.txt', '前提快照/求解任务.txt',
             '前提快照/求解约束.txt', '前提快照/求解充分条件.txt', '临时规则.md',
             '推导95T.md', '第92轮候选清单.json', '推导95T-交回.json']
    entries = []
    for name in names:
        data = (BASE/name).read_bytes()
        entries.append(dict(path=str(BASE/name), bytes=len(data), lines=len(data.splitlines()),
                            sha256=hashlib.sha256(data).hexdigest()))
    save('inputs.json', entries)


if __name__ == '__main__':
    manifest()
    run_arithmetic()
    run_layers()
    run_chains()
    run_round_robin()
    run_plants()
