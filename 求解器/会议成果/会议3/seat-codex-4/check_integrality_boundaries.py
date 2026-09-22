"""Exact arithmetic examples of two limits of a network integrality proof.

These are abstract linear systems, not counterexamples to the factory task
or to the disjoint machine-type group construction.
"""
from fractions import Fraction
from itertools import product
import json

matrix = [[1, 1, 0], [0, 1, 1], [1, 0, 1]]
a, b, c = matrix
det = (a[0] * (b[1] * c[2] - b[2] * c[1])
       - a[1] * (b[0] * c[2] - b[2] * c[0])
       + a[2] * (b[0] * c[1] - b[1] * c[0]))
half = [Fraction(1, 2)] * 3
rhs = [sum(u * v for u, v in zip(row, half)) for row in matrix]
integer_group_solutions = [
    x for x in product((0, 1), repeat=3)
    if all(sum(u * v for u, v in zip(row, x)) == 1 for row in matrix)
]
integer_support_solutions = [
    x for x in product((0, 1), repeat=2) if sum(x) == 1 and min(x) > 0
]
assert det == 2 and rhs == [1, 1, 1] and not integer_group_solutions
assert not integer_support_solutions
print(json.dumps({
    'overlapping_groups': {
        'matrix': matrix, 'determinant': det,
        'fractional_witness': [str(x) for x in half],
        'rhs': [str(x) for x in rhs],
        'nonnegative_integer_solutions': integer_group_solutions,
    },
    'positive_support': {
        'equation': 'x+y=1; x>0; y>0',
        'fractional_witness': ['1/2', '1/2'],
        'nonnegative_integer_solutions': integer_support_solutions,
    },
    'scope': 'Abstract exact-arithmetic boundary examples; not a factory solve.',
}, indent=2))
