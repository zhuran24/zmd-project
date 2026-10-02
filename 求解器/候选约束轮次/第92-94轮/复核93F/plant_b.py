#!/usr/bin/env python3
"""Independent implementation B: arrays of ages and remaining work.

This file does not import implementation A or any other project code. Array
ages, rather than entry timestamps, determine transport eligibility; machine
work is a countdown, rather than a scheduled completion time. The two K
routes share a 50-piece receiver with no second ingredient.
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent


def fresh(lengths, limit=50):
    return {'clock': 0, 'machines': [[0, 0, -1] for _ in range(4)],
            'ages': [[-1] * length for length in lengths], 'picked': [-1] * 6,
            'departures': [0] * 6, 'deliveries': [0] * 6, 'sink': 0,
            'limit': limit, 'cursor': 4, 'starts': [0] * 4, 'finishes': [0] * 4,
            'priority': list(range(6)), 'enabled': [True]*4}


def tick(s, machines=(0, 1, 2, 3), components=(0, 1, 2, 3, 4, 5)):
    m, roads = s['machines'], s['ages']
    quantity = (1, 1, 2, 2)
    source = (2, 2, 0, 1, 3, 3)
    target = (0, 1, 2, 3, 4, 4)

    def release(j):
        if m[j][2] == 0 and m[j][1] <= 50 - quantity[j]:
            m[j][1] += quantity[j]
            m[j][2] = -1

    def advance(line):
        for q in reversed(range(1, len(line))):
            if line[q] < 0 and line[q-1] >= 8:
                line[q-1], line[q] = -1, 0

    for j in range(4):
        if m[j][2] > 0 and s['enabled'][j]:
            m[j][2] -= 1
            if m[j][2] == 0:
                s['finishes'][j] += 1
        release(j)
    for line in roads:
        for j in range(len(line)):
            if line[j] >= 0:
                line[j] += 1
        advance(line)
    seen = set()
    for c in components:
        if c in seen:
            continue
        batch = (s['cursor'], 9-s['cursor']) if target[c] == 4 else (c,)
        for e in batch:
            seen.add(e)
            if roads[e][-1] < 8:
                continue
            destination = target[e]
            if destination == 4:
                if s['sink'] == s['limit']:
                    continue
                s['sink'] += 1
                s['cursor'] = 9-e
            else:
                if m[destination][0] == 50:
                    continue
                m[destination][0] += 1
            s['deliveries'][e] += 1
            roads[e][-1] = -1
            advance(roads[e])
    for j in machines:
        if m[j][1] == 0:
            continue
        outlet = sorted((e for e in range(6) if source[e] == j),
                        key=lambda e: (s['picked'][e], s['priority'][e]))
        for e in outlet:
            if roads[e][0] < 0:
                roads[e][0] = 0
                s['picked'][e] = s['clock']
                s['departures'][e] += 1
                m[j][1] -= 1
                release(j)
                break
    for j in range(4):
        if s['enabled'][j] and m[j][2] == -1 and m[j][0] > 0:
            m[j][0] -= 1
            m[j][2] = 8
            s['starts'][j] += 1
    s['clock'] += 1


def phi2(s):
    a, b, c, k = s['machines']
    counts = [sum(v >= 0 for v in road) for road in s['ages']]
    return 2*(counts[0] + a[0] + a[1] + counts[2] + c[0] + (a[2] >= 0) + (c[2] >= 0)) + c[1]


def describe(s):
    labels, paths = 'ABCK', ('CA','CB','AC','BK','K0','K1')
    def batch(j):
        remaining = s['machines'][j][2]
        if remaining < 0:
            return None
        if remaining == 0:
            return ('ready', (1,1,2,2)[j])
        return ('running', s['clock'] + remaining - 1)
    return {'step': s['clock'], 'phi2': phi2(s),
            'stock': {x: s['machines'][j][0] for j, x in enumerate(labels)},
            'output': {x: s['machines'][j][1] for j, x in enumerate(labels)},
            'batch': {x: batch(j) for j, x in enumerate(labels)},
            'enabled': dict(zip(labels,s['enabled'])),
            'route_counts': {x: sum(a >= 0 for a in s['ages'][j]) for j, x in enumerate(paths)},
            'sink': s['sink'], 'sent': dict(zip(paths,s['departures'])),
            'arrivals': dict(zip(paths,s['deliveries']))}


def experiment(lengths, delayed, horizon):
    s = fresh(lengths, 50 if delayed else 10**9)
    s['machines'][0][0] = 50
    if not delayed:
        s['machines'][2][0] = 50
    initial, first, full = describe(s), None, None
    minimum = phi2(s)
    for _ in range(horizon):
        tick(s)
        minimum = min(minimum, phi2(s))
        if delayed and s['machines'][2][0] > 0 and first is None:
            first = describe(s)
        if delayed and s['machines'][2][0] == 50:
            full = describe(s)
            break
    if delayed:
        assert full is not None
        accepted = s['machines'][2][0] + 50 <= 50
        return dict(lengths=lengths, initial=initial, first_nonempty=first,
                    first_full=full, second_50_accepted=accepted, minimum_phi2=minimum)
    return dict(lengths=lengths, minimum_phi2=minimum, end=describe(s))


def main():
    lengths = ((7,13,31,5,5,5), (48,7,49,5,3,3), (49,7,49,5,3,3))
    result = {'implementation': 'B', 'delayed': experiment(lengths[0], True, 30000),
              'joint': [experiment(z, False, 10000) for z in lengths]}
    (OUT/'plant_b.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'delayed_step': result['delayed']['first_full']['step'],
                      'first_nonempty_step': result['delayed']['first_nonempty']['step'],
                      'joint_minimum_phi2': [z['minimum_phi2'] for z in result['joint']]}))


if __name__ == '__main__':
    main()
