"""Direct port-vector enumeration and array convolution; no A imports."""
import itertools
import json
import math
from fractions import Fraction
from pathlib import Path

OUT = Path(__file__).resolve().parent


def direct_group(size, maximum, count, total):
    costs = [10**6]*(maximum+1)
    for vector in itertools.product((0, 1, 2), repeat=size):
        demand = sum(vector)
        if demand > maximum:
            continue
        active = [i for i, value in enumerate(vector) if value]
        value = 0
        for i, j in zip(active, active[1:]):
            if j-i < 4:
                value += vector[i]+vector[j]
        costs[demand] = min(costs[demand], value)
    before = [0]+[10**9]*total
    for machine in range(count):
        after = [10**9]*(total+1)
        for amount in range(min(total, (machine+1)*maximum)+1):
            after[amount] = min(before[amount-use]+costs[use]
                                for use in range(min(amount, maximum)+1))
        before = after
    return before[total]


def main():
    # All recipe quantities below are for a 20 tick cycle: 12 batteries,
    # 11 capsules. This route does not use A's nine input/output totals.
    battery, capsule = 12, 11
    steel_parts, bottles = 10*battery, 10*capsule
    steel = steel_parts+2*bottles
    dense_ore, dense_iron, flower_powder = 15*battery, steel, 10*capsule
    ground_batches = dense_ore+dense_iron+flower_powder
    sand_crush = ground_batches//3
    flower_crush = 2*flower_powder//2
    planted = 2*(sand_crush+flower_crush)
    seed_batches = planted//2
    raw_iron, raw_ore = 2*dense_iron, 2*dense_ore
    pulverize = raw_iron+raw_ore+sand_crush+flower_crush
    refine = raw_iron+dense_iron
    time_ticks = [pulverize, refine, ground_batches, bottles, steel_parts,
                  planted, seed_batches, 5*battery, 5*capsule]
    counts = [(v+19)//20 for v in time_ticks]
    manufacturing_area = (counts[0]+counts[1]+counts[3]+counts[4])*3*3 \
        + (counts[5]+counts[6])*5*5 + (counts[2]+counts[7]+counts[8])*6*4
    input_totals = [pulverize, refine, 3*ground_batches, 2*bottles,
                    steel_parts, planted, seed_batches, 25*battery, 20*capsule]
    output_totals = [raw_iron+raw_ore+3*sand_crush+2*flower_crush, refine,
                     ground_batches, bottles, steel_parts, planted, 2*seed_batches,
                     battery, capsule]
    input_ports = sum((v+19)//20 for v in input_totals)
    output_ports = sum(max((v+19)//20, c) for v, c in zip(output_totals, counts))
    source_ports = (raw_iron+raw_ore)//20
    interfaces = input_ports+output_ports+source_ports+2
    weights = {name: direct_group(size, maximum, count, total) for name, size, maximum, count, total in [
        ('研磨机', 6, 6, counts[2], 3*ground_batches//10), ('塑形机', 3, 4, counts[3], 2*bottles//10),
        ('封装机', 6, 10, counts[7], 25*battery//10), ('灌装机', 6, 8, counts[8], 20*capsule//10)]}
    tables = {}
    net_steps = {}
    for name, ports, limit, initial, stop, target, body_area in [
        ('研磨机', 6, 6, counts[2], 48, 3*ground_batches//10, 6*4),
        ('塑形机', 3, 4, counts[3], 11, 2*bottles//10, 3*3),
        ('封装机', 6, 10, counts[7], 8, 25*battery//10, 6*4),
        ('灌装机', 6, 8, counts[8], 6, 20*capsule//10, 6*4)]:
        table = [[n, direct_group(ports, limit, n, target)] for n in range(initial, stop+1)]
        assert table[-1][1] == 0
        tables[name] = table
        steps = []
        for row, nxt in zip(table, table[1:]):
            old = 8*(row[0]-initial)*body_area+row[1]
            new = 8*(nxt[0]-initial)*body_area+nxt[1]
            steps.append(Fraction(new-old, 2))
        net_steps[name] = {'first': str(steps[0]), 'minimum': str(min(steps))}
    band = {(1, y) for y in range(1, 70)} | {(x, 1) for x in range(1, 70)}
    direction_twice = 2*interfaces+2*(4*46-91)+16+sum(weights.values())+2*(len(band)-46-3)+8
    area_residual = 4900-manufacturing_area-81-23*3*2
    factor_pairs = {}
    for w in range(6, 69):
        for h in range(w, 69):
            if 1107 <= w*h <= 1113:
                factor_pairs.setdefault(w*h, []).append([w, h])
    dims = {i: factor_pairs.get(i, []) for i in range(1107, 1114)}
    # Direct integer search, independent of A's ceiling formula.
    cases = []
    for occupied in [0, 1]:
        for original_z in range(411):
            for lhs in range(0, 2000, 2):
                if 2*lhs >= direction_twice+2*original_z-4*occupied:
                    break
            expected = 921+original_z-occupied
            assert lhs >= expected
            cases.append([occupied, original_z, lhs, expected])
    all_costs = []
    for p in range(1, 348):
        for j in range(p+1):
            if 23*p-10*j >= sum(counts) and 54*p-25*j >= 520:
                all_costs.append(16*p-2*j)
    minimum_power = min(all_costs)
    at_1110 = {str(p): [] for p in range(10, 14)}
    remainder = [[], []]
    for p in range(10, 348):
        for j in range(p+1):
            if 54*p-25*j < 520 or 23*p-10*j < 217:
                continue
            cost = 16*p-2*j
            remainder[0 if p == 10 else 1].append(4751-4440-cost)
            if 4440+cost <= 4639:
                assert p <= 13
                at_1110[str(p)].append(j)
    # Search the inequality after multiplying by 8, independently of A's Fraction expression.
    maximum_extra_area_eighths = max(a8 for a8 in range(40000)
                                    if 4*a8+8*minimum_power+4*287 <= 8*4751)
    outer = []
    for label, removed, pieces, extras in [('two', 30+37, 2, 1), ('one', 37, 3, 2), ('none', 0, 2, 2)]:
        length = 2*69-removed
        low = []
        for t in (0, extras):
            low.append(next(x for x in range(139) if 6*x+14+8*t+5*pieces >= length))
        outer.append([label, length, pieces, extras, *low])
    result = {'machine_count': sum(counts), 'manufacturing_area': manufacturing_area,
              'input_interfaces': input_ports, 'output_interfaces': output_ports,
              'interfaces': interfaces, 'weights_twice': weights, 'weight_twice': sum(weights.values()),
              'weight_tables_twice': tables, 'net_area_steps': net_steps,
              'direction_lower_twice': direction_twice, 'area_residual': area_residual,
              'transport_lower_twice': 2*interfaces+2*(184-91)+16+sum(weights.values()),
              'old_area_constant': 4*area_residual-921,
              'integer_corrected_constant': math.floor(4*area_residual-direction_twice/2),
              'minimum_idle_corner_excess_area': 3*3,
              'corner_area_upper_with_one_small_idle': math.floor(4*area_residual-direction_twice/2-4*3*3+2),
              'minimum_power_cost': minimum_power,
              'at_1110_pj': at_1110, 'at_1110_remaining_4E_omega': [max(v) for v in remainder],
              'extra_area_limit_fraction': str(Fraction(maximum_extra_area_eighths, 8)), 'outer_bounds': outer,
              'legal_dimensions': dims, 'integer_implications_checked': len(cases),
              'rounding_cases': cases}
    (OUT/'arithmetic_b.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'rounding_cases'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
