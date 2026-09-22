"""Exact arithmetic checks for round 2; no factory or solver performance claim."""
from fractions import Fraction
from itertools import product
from math import lcm
from pathlib import Path
import json


def det(a):
    if len(a) == 1:
        return a[0][0]
    return sum((-1) ** j * a[0][j] * det([r[:j] + r[j+1:] for r in a[1:]]) for j in range(len(a)))

K = 20
split_basis = [[1,1,1], [1,-1,0], [0,1,-1]]
assert abs(det(split_basis)) == 3
real_flow = [Fraction(1,3)] * 3
assert sum(real_flow) == 1
assert all((K*f).denominator != 1 for f in real_flow)
integer_split_solutions = [x for x in product(range(K+1), repeat=3)
                          if sum(x)==K and x[0]==x[1]==x[2]]
assert integer_split_solutions == []
substitute_flow = [Fraction(7,20), Fraction(7,20), Fraction(6,20)]
assert sum(substitute_flow) == 1
assert all(0 <= f <= 1 for f in substitute_flow)
assert all((K*f).denominator == 1 for f in substitute_flow)
assert 3*Fraction(1,3) == 1
assert all(3*q != K for q in range(K+1))
assert 3*1 == 3  # A non-TU coefficient does not rule out integer feasibility.

# Test the proved floor-mapping row bound on a finite exact sample only.
# Proof, rather than this finite sample, establishes general coverage.
rows = [[1,-1,0], [3,-1,0], [2,1,-3], [-2,-1,3]]
values = [Fraction(0), Fraction(1,60), Fraction(1,3), Fraction(2,5), Fraction(1)]
checked = 0
for row in rows:
    p = sum(max(a,0) for a in row)
    n = sum(max(-a,0) for a in row)
    for x in product(values, repeat=3):
        b = sum(a*v for a,v in zip(row,x))
        q = [(K*v).__floor__() for v in x]
        aq = sum(a*v for a,v in zip(row,q))
        assert K*b-p <= aq <= K*b+n
        checked += 1

assert 1 + (-1) == 0  # Dual row sum for y<=x and -y<=-1.
assert 0-1 < 0 and 1-1 == 0

result = {
    'scope': 'exact algebraic toy checks; no achieved factory layout, no CP-SAT run',
    'K': K,
    'equal_split_basis_determinant': det(split_basis),
    'equal_split_real_solution': [str(f) for f in real_flow],
    'equal_split_integer_solutions': len(integer_split_solutions),
    'without_equalities_integer_substitute': [str(f) for f in substitute_flow],
    'recipe_toy': {'equations': ['3*r=o', 'o=1'], 'r':'1/3', 'integer_grid_feasible':False},
    'non_tu_integer_feasible_example': '3*r=3 admits r=1',
    'denominator_bound_is_not_grid_denominator': {'denominator_bound':3, 'K_equal_bound':3, 'missed_fraction':'1/2', 'safe_lcm':lcm(1,2,3)},
    'floor_row_bound_finite_samples_checked': checked,
    'parametric_farkas_toy': {'constraints':['y<=x', '-y<=-1', 'y>=0'], 'master_domain':[0,1], 'dual':[1,1], 'valid_cut':'x-1>=0', 'warning':'a fixed-x contradiction is not a global constant cut'},
}
Path(__file__).with_name('integer-flow-check.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(result, ensure_ascii=False, indent=2))
