"""Exact arithmetic check of a recipe-flow block, not a factory witness.

Recipe: one sand leaf -> three sand-leaf powder, one tick.
Boundary condition chosen for this block: powder output = 1 item/tick.
Variables: input flow u, recipe rate r, output flow v.
Equations: u=r, v=3*r, v=1. Bounds: 0<=u,r,v<=1.
No geometry, startup, scheduling, or complete task feasibility is checked.
"""

from fractions import Fraction
from pathlib import Path
from time import perf_counter
import json


def main():
    started = perf_counter()
    u = r = Fraction(1, 3)
    v = Fraction(1)
    assert u == r and v == 3*r and v == 1
    assert all(0 <= x <= 1 for x in (u, r, v))

    grids = {}
    for scale in (20, 60):
        # Eliminating U=R and V=scale leaves 3*R=scale.
        solutions = [[R, R, scale] for R in range(scale + 1)
                     if 3*R == scale]
        grids[str(scale)] = {
            "integer_candidates_checked": scale + 1,
            "solutions_scaled_U_R_V": solutions,
        }
    assert grids["20"]["solutions_scaled_U_R_V"] == []
    assert grids["60"]["solutions_scaled_U_R_V"] == [[20, 20, 60]]

    # The 1x1 minor [-3] in v-3*r=0 disproves TU for this matrix.
    # Non-TU alone does not disprove integrality for a particular RHS:
    # 2*x=2, x>=0 has the unique integral point x=1.
    assert Fraction(2, 2) == 1

    result = {
        "scope": "3-variable recipe-flow block; exact arithmetic only",
        "rule_file": "《明日方舟：终末地》游戏规则.txt",
        "rule_line": 84,
        "boundary_condition": "powder output v=1 item/tick",
        "continuous_solution_u_r_v": [str(x) for x in (u, r, v)],
        "grid_checks": grids,
        "non_TU_minor_determinant": -3,
        "non_TU_with_integral_feasible_set_example": "2*x=2, x>=0 -> x=1",
        "solver": "none; Python fractions and complete one-dimensional enumeration",
        "elapsed_seconds": perf_counter() - started,
        "not_established": [
            "a complete target-achieving 70x70 layout",
            "a grid-20 counterexample at the full task's fixed demands",
            "an adequate universal scale of 60",
            "CP-SAT or LP solver performance",
        ],
    }
    output = Path(__file__).with_name("rate_grid_turn2_result.json")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
