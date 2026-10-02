"""Support-set costs and dictionary dynamic programming, exact half-units."""
import itertools
import json
from fractions import Fraction
from math import ceil as math_ceil
from pathlib import Path

OUT = Path(__file__).resolve().parent


def machine_table(width, cap):
    best = {d: 10**6 for d in range(2*cap+1)}
    best[0] = 0
    for mask in range(1, 1 << width):
        support = [i for i in range(width) if mask & (1 << i)]
        coefficients = {i: 0 for i in support}
        for lo, hi in zip(support, support[1:]):
            if hi-lo <= 3:
                coefficients[lo] += 1
                coefficients[hi] += 1
        # Integer flow units are halves of one item/tick; each port holds two.
        unit_costs = sorted(c for c in coefficients.values() for _ in range(2))
        for demand in range(min(2*cap, len(unit_costs))+1):
            best[demand] = min(best[demand], sum(unit_costs[:demand]))
    return best


def group(width, cap, n, demand):
    local = machine_table(width, cap)
    dp = {0: 0}
    for _ in range(n):
        nxt = {}
        for old, cost in dp.items():
            for add, extra in local.items():
                if old+add <= demand:
                    nxt[old+add] = min(nxt.get(old+add, 10**9), cost+extra)
        dp = nxt
    return dp[demand]


def main():
    minimum = [68, 51, 32, 6, 6, 32, 16, 3, 3]
    area = [9, 9, 24, 9, 9, 25, 25, 24, 24]
    inputs = [68, 51, 95, 11, 6, 32, 16, 15, 11]
    outputs = [95, 51, 32, 6, 6, 32, 32, 3, 3]
    interfaces = sum(inputs)+sum(outputs)+46+6+2
    weights = {name: group(width, cap, n, demand) for name, width, cap, n, demand in [
        ('研磨机', 6, 3, 32, 189), ('塑形机', 3, 2, 6, 22),
        ('封装机', 6, 5, 3, 30), ('灌装机', 6, 4, 3, 22)]}
    double_weight = sum(weights.values())
    tables = {}
    net_steps = {}
    for name, width, cap, start, end, demand, size in [
        ('研磨机', 6, 3, 32, 48, 189, 24), ('塑形机', 3, 2, 6, 11, 22, 9),
        ('封装机', 6, 5, 3, 8, 30, 24), ('灌装机', 6, 4, 3, 6, 22, 24)]:
        values = [group(width, cap, n, demand) for n in range(start, end+1)]
        assert values[-1] == 0
        tables[name] = [[start+i, v] for i, v in enumerate(values)]
        increments = [4*size+Fraction(new-old, 2) for old, new in zip(values, values[1:])]
        net_steps[name] = {'first': str(increments[0]), 'minimum': str(min(increments))}
    direction_twice = 2*(interfaces+46*4+8+(137-46-3)+4-91)+double_weight
    residual_area = 70*70-sum(n*s for n, s in zip(minimum, area))-9*9-46*3
    legal_dimensions = {a: [(w, a//w) for w in range(6, 69) if a % w == 0 and w <= a//w <= 68]
                        for a in range(1107, 1114)}
    cases = []
    for corner in [0, 1]:
        for z in range(411):
            # z uses the original X, including its two corner charges.
            lower_twice = direction_twice+2*z-4*corner
            smallest_even_lhs = 2*((lower_twice+3)//4)
            target = 921+z-corner
            assert smallest_even_lhs >= target
            if corner == 0 or z % 2:
                assert smallest_even_lhs >= 921+z
            cases.append([corner, z, smallest_even_lhs, target])
    pj = [(p, j, 16*p-2*j) for p in range(10, residual_area//4+1)
          for j in range(p+1) if 23*p-10*j >= 217 and 54*p-25*j >= 520]
    min_power_cost = min(row[2] for row in pj)
    at_1110 = {str(p): sorted({j for pp, j, cost in pj if pp == p and cost <= 4639-4*1110})
               for p in range(10, 14)}
    remaining_omega = [4751-4*1110-min(cost for p, j, cost in pj if p == 10),
                       4751-4*1110-min(cost for p, j, cost in pj if p >= 11)]
    assert max(p for p, j, cost in pj if cost <= 4639-4*1110) == 13
    area_extra_limit = Fraction(4751-min_power_cost, 4)-Fraction(287, 8)
    outer = []
    for label, length, pieces, extra_segments in [('two', 71, 2, 1), ('one', 101, 3, 2), ('none', 138, 2, 2)]:
        no_extra = math_ceil(Fraction(length-14-5*pieces, 6))
        one_extra = math_ceil(Fraction(length-14-8*extra_segments-5*pieces, 6))
        outer.append([label, length, pieces, extra_segments, no_extra, one_extra])
    result = {'machine_count': sum(minimum), 'manufacturing_area': sum(n*s for n, s in zip(minimum, area)),
              'input_interfaces': sum(inputs), 'output_interfaces': sum(outputs),
              'interfaces': interfaces, 'weights_twice': weights, 'weight_twice': double_weight,
              'weight_tables_twice': tables, 'net_area_steps': net_steps,
              'direction_lower_twice': direction_twice, 'area_residual': residual_area,
              'transport_lower_twice': direction_twice-2*(88+4),
              'old_area_constant': 4*residual_area-921,
              'integer_corrected_constant': 4*residual_area-(direction_twice+1)//2,
              'minimum_idle_corner_excess_area': min(area),
              'corner_area_upper_with_one_small_idle': 4*residual_area-(direction_twice+1)//2+2-4*min(area),
              'minimum_power_cost': min_power_cost,
              'at_1110_pj': at_1110, 'at_1110_remaining_4E_omega': remaining_omega,
              'extra_area_limit_fraction': str(area_extra_limit), 'outer_bounds': outer,
              'legal_dimensions': legal_dimensions, 'integer_implications_checked': len(cases),
              'rounding_cases': cases}
    (OUT/'arithmetic_a.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'rounding_cases'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
