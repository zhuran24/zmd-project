"""Exact small checks of network expansion, lower-bound cuts, and floor slack.

Not a factory, geometry, scheduling, or 70x70 performance experiment.
No floating-point solver is used.
"""
from collections import deque
from fractions import Fraction
from itertools import product
from pathlib import Path
from time import perf_counter
import json


def circulation(nodes, arcs):
    residual = {v: {} for v in nodes + ['SS', 'TT']}
    balance = dict.fromkeys(nodes, 0)
    def add(a, b, capacity):
        residual[a][b] = residual[a].get(b, 0) + capacity
        residual[b].setdefault(a, 0)
    for a, b, lower, upper in arcs:
        assert 0 <= lower <= upper
        add(a, b, upper-lower)
        balance[a] -= lower
        balance[b] += lower
    target = 0
    for v, amount in balance.items():
        if amount > 0:
            add('SS', v, amount)
            target += amount
        elif amount < 0:
            add(v, 'TT', -amount)
    value = 0
    while True:
        parent = {'SS': None}
        queue = deque(['SS'])
        while queue and 'TT' not in parent:
            a = queue.popleft()
            for b, capacity in residual[a].items():
                if capacity > 0 and b not in parent:
                    parent[b] = a
                    queue.append(b)
        if 'TT' not in parent:
            break
        amount, b = target-value, 'TT'
        while parent[b] is not None:
            a = parent[b]
            amount = min(amount, residual[a][b])
            b = a
        b = 'TT'
        while parent[b] is not None:
            a = parent[b]
            residual[a][b] -= amount
            residual[b][a] += amount
            b = a
        value += amount
    return {'feasible': value == target, 'maxflow': value, 'required': target}


def hoffman_all_subsets(nodes, arcs):
    violations = []
    for mask in range(1 << len(nodes)):
        S = {v for i, v in enumerate(nodes) if mask & (1 << i)}
        lower_out = sum(l for a,b,l,u in arcs if a in S and b not in S)
        upper_in = sum(u for a,b,l,u in arcs if a not in S and b in S)
        if lower_out > upper_in:
            violations.append({'S': sorted(S), 'lower_out': lower_out,
                               'upper_in': upper_in})
    return {'feasible': not violations, 'subsets_checked': 1 << len(nodes),
            'violation_count': len(violations),
            'first_violation': violations[0] if violations else None}


def main():
    started = perf_counter()
    nodes = ['S','OG','O1','O2','VI','VO','I1','I2','IG','T']
    results = []
    for capacity in (0, 1, 2):
        arcs = [('S','OG',2,2), ('OG','O1',0,1), ('OG','O2',0,1),
                ('O1','VI',0,1), ('O2','VI',0,1), ('VI','VO',0,capacity),
                ('VO','I1',0,1), ('VO','I2',0,1), ('I1','IG',0,1),
                ('I2','IG',0,1), ('IG','T',2,2), ('T','S',0,2)]
        direct = [x for x in product((0,1), repeat=4)
                  if x[0]+x[1] == 2 and x[2]+x[3] == 2
                  and x[0]+x[1] == x[2]+x[3]
                  and x[0]+x[1] <= capacity]
        flow = circulation(nodes, arcs)
        cuts = hoffman_all_subsets(nodes, arcs)
        assert flow['feasible'] == cuts['feasible'] == bool(direct)
        results.append({'internal_capacity': capacity, 'nodes': len(nodes),
                        'arcs': len(arcs), 'direct_assignments_checked': 16,
                        'direct_solutions': direct, 'maxflow_check': flow,
                        'all_cuts_check': cuts})

    # Lower bounds cannot be discarded from the cut condition.
    bad_arcs = [('a','b',1,1), ('b','a',0,0)]
    lower_example = hoffman_all_subsets(['a','b'], bad_arcs)
    assert not lower_example['feasible']
    assert not circulation(['a','b'], bad_arcs)['feasible']

    # The two recipe examples are related by introducing/eliminating u=r.
    rates = [Fraction(0), Fraction(1,3), Fraction(2,3), Fraction(1)]
    pairs = {(r, v) for r, v in product(rates, repeat=2)
             if 3*r == v and v == 1}
    projected_triples = {(r, v) for u, r, v in product(rates, repeat=3)
                         if u == r and v == 3*r and v == 1}
    assert pairs == projected_triples == {(Fraction(1,3), Fraction(1))}
    assert not any(3*r == 20 for r in range(21))

    # Broadening every conservation row permits accumulation of rounding slack.
    # Original: x0=0, x_i=x_(i-1), x20=1 -- infeasible.
    # K=20 floor-row relaxation: q0=0, |q_i-q_(i-1)|<=1, q20=20.
    K = 20
    q = list(range(K+1))
    assert q[0] == 0 and q[-1] == K
    assert all(0 <= x <= K for x in q)
    assert all(-1 <= q[i]-q[i-1] <= 1 for i in range(1,K+1))

    result = {
        'scope': 'exact algebraic/network fixtures only; not a factory witness',
        'algorithm': 'integer augmenting paths plus exhaustive cut enumeration',
        'network_cases': results,
        'lower_bound_counterexample': lower_example,
        'recipe_examples_equivalent_under_u_equals_r': True,
        'floor_conservation_slack_example': {
            'K': K, 'conservation_rows': K,
            'source': 0, 'claimed_output_items_per_tick': 1,
            'original_equalities_feasible': False,
            'relaxed_integer_rows_feasible': True,
        },
        'elapsed_seconds_excluding_imports_and_write': perf_counter()-started,
    }
    Path(__file__).with_name('network_turn3_result.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
