"""Exact checks of independent subset-flow losses and prior boundary examples.

These are algebraic two-parallel-route examples, not factory witnesses or
CP-SAT performance tests. The general product proof is in the seat position.
"""
from fractions import Fraction
from itertools import product
from pathlib import Path
from time import perf_counter
import hashlib
import json


def main():
    started = perf_counter()
    # Each component is an integral two-parallel-route network of capacities 1.
    routes_one = [p for p in product((0, 1), repeat=2) if sum(p) == 1]
    assert len(routes_one) == 2
    product_pairs = list(product(routes_one, repeat=2))
    inclusion_failures = [(all_flow, subset_flow)
                          for all_flow, subset_flow in product_pairs
                          if any(s > a for a, s in zip(all_flow, subset_flow))]
    assert len(inclusion_failures) == 2

    # Disjoint subsets each carry 1, while the all-items layer carries 2.
    # Each plane is feasible, but this tuple overloads its first route.
    all_flow = (1, 1)
    A = B = (1, 0)
    assert sum(all_flow) == 2 and A in routes_one and B in routes_one
    assert all(a <= t and b <= t for a, b, t in zip(A, B, all_flow))
    assert A[0]+B[0] > all_flow[0]

    # Overlapping subsets AB, BC, B, ABC all have total 1, as when only B exists.
    # Independent choices can fail the atom-level inclusion-exclusion identity.
    AB, BC, inter, union = (1, 0), (1, 0), (0, 1), (1, 0)
    assert all(v in routes_one for v in (AB, BC, inter, union))
    assert AB[0]+BC[0] != inter[0]+union[0]

    # A correct atomic assignment can violate the INCORRECT sum over overlaps.
    actual_all = actual_ore = Fraction(1)
    assert actual_all <= 1 and actual_ore <= actual_all
    assert actual_all+actual_ore > 1

    # Independent checks of codex-4's two boundary examples.
    matrix = ((1, 1, 0), (0, 1, 1), (1, 0, 1))
    a, b, c = matrix
    determinant = (a[0]*(b[1]*c[2]-b[2]*c[1])
                   -a[1]*(b[0]*c[2]-b[2]*c[0])
                   +a[2]*(b[0]*c[1]-b[1]*c[0]))
    half = (Fraction(1, 2),)*3
    assert determinant == 2
    assert all(sum(ai*xi for ai, xi in zip(row, half)) == 1 for row in matrix)
    integral_cross_groups = [x for x in product((0, 1), repeat=3)
                            if all(sum(ai*xi for ai, xi in zip(row, x)) == 1
                                   for row in matrix)]
    integral_positive_support = [x for x in product((0, 1), repeat=2)
                                 if sum(x) == 1 and min(x) > 0]
    assert not integral_cross_groups and not integral_positive_support

    # Updated gate-capacity row and phase-I zero witness, case by case.
    gate_capacities = {}
    for kind in ('non_gate', 'unlimited', 'k1', 'k2', 'k3', 'k4', 'k5'):
        flags = {k: int(kind == f'k{k}') for k in range(1, 5)}
        upper = 1-sum(Fraction(5-k, 5)*flags[k] for k in flags)
        expected = Fraction(int(kind[1:]), 5) if kind.startswith('k') else Fraction(1)
        assert upper == expected and upper >= 0
        gate_capacities[kind] = str(upper)
    rhs = [Fraction(3, 5), Fraction(11, 20), Fraction(1), Fraction(0)]
    assert all(Fraction(0)+max(t, 0) >= t for t in rhs)

    meeting = Path(__file__).resolve().parents[1]
    snapshot = meeting/'seat-codex-4'/'aggflow-audit-70802f19.py'
    live = meeting/'seat-opus-2'/'aggflow.py'
    digests = {str(p.relative_to(meeting)): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in (snapshot, live)}
    assert digests[str(snapshot.relative_to(meeting))] == (
        '70802f199c5a164514bd0d09bf68a16cbb970bdad975e8fafdae18415ec44061')
    result = {
        'scope': 'exact subset-flow and boundary checks only; no factory solve',
        'two_route_product': {'integer_points_per_component': 2,
                              'product_points': len(product_pairs),
                              'inclusion_violations': inclusion_failures},
        'disjoint_capacity_loss': {'all': all_flow, 'A': A, 'B': B},
        'overlap_identity_loss': {'AB': AB, 'BC': BC, 'intersection': inter,
                                 'union': union},
        'overlap_sum_is_not_a_valid_capacity_rule': {'all': '1', 'ore': '1'},
        'cross_group_determinant': determinant,
        'integer_cross_group_solutions': integral_cross_groups,
        'integer_positive_support_solutions': integral_positive_support,
        'gate_capacities': gate_capacities,
        'reviewed_snapshot_and_live_sha256': digests,
        'elapsed_seconds_excluding_imports_and_write': perf_counter()-started,
    }
    Path(__file__).with_name('subset_layers_turn4_result.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
