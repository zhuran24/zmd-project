#!/usr/bin/env python3
"""Input hashes, two independent arithmetic routes, and result aggregation."""
import hashlib
import json
import sys
from collections import Counter
from fractions import Fraction as Q
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROUND = HERE.parent
PROJECT = HERE.parents[3]


def write(name, data):
    (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def main():
    paths = list((ROUND / '前提快照').glob('*.txt')) + [ROUND / '临时规则.md']
    previous = ROUND.parent / '第92-94轮'
    paths += [previous / name for name in ('推导92D.md', '推导92F.md', '复核93D.md', '复核94D.md', '复核93F.md', '复核94F.md')]
    paths += [previous / '推导92D' / name for name in ('factory_check.py', 'symbolic_dense_s09.md', 'plant_proof.md')]
    paths += [previous / '推导92C.md']
    inputs = []
    for path in paths:
        raw = path.read_bytes()
        txt = raw.decode('utf-8')
        inputs.append(dict(path=str(path.relative_to(PROJECT)), sha256=hashlib.sha256(raw).hexdigest(),
                           lines=len(txt.splitlines()), basis_lines=sum(x.lstrip().startswith('据：') for x in txt.splitlines())))
    write('inputs.json', inputs)

    # Route A: eliminate intermediates in conservation equations.
    x, y = Q(18), Q(34)
    b_a = x / 30
    c_a = (y / 2 - 10 * b_a) / 20
    # Route B: compose recipes per finished item, then solve the integer 2x2
    # material matrix by its determinant (rows blue mineral, source mineral).
    blue_per_battery = 10 * 1 * 1 * 2
    ore_per_battery = 15 * 2 * 1
    blue_per_capsule = 10 * 2 * 1 * 2
    ore_per_capsule = 0
    det = blue_per_battery * ore_per_capsule - blue_per_capsule * ore_per_battery
    b_b = Q(34 * ore_per_capsule - blue_per_capsule * 18, det)
    c_b = Q(blue_per_battery * 18 - 34 * ore_per_battery, det)
    assert (b_a, c_a) == (b_b, c_b) == (Q(3, 5), Q(11, 20))
    sand_a = Q(17 + 9) + 10 * c_a
    sand_b = 25 * b_b + 30 * c_b
    flower_a = 2 * 10 * c_a
    flower_b = Q(2) * Q(11, 2)
    assert sand_a == sand_b == Q(63, 2)
    assert flower_a == flower_b == Q(11)

    # Graph construction and closed degree count are separate encodings.
    from factory_probe import setup
    f, _ = setup(9500, 3, 'dense', 'mixed')
    model_types = Counter()
    for u in f.ms:
        ingredients, product, amount, duration = u.recipe
        if product.endswith('种子'):
            kind = '采种机'
        elif product in ('砂叶', '荞花'):
            kind = '种植机'
        elif product in ('蓝铁块', '钢块'):
            kind = '精炼炉'
        elif product in ('致密蓝铁粉末', '致密源石粉末', '细磨荞花粉末'):
            kind = '研磨机'
        elif product == '钢制零件':
            kind = '配件机'
        elif product == '钢质瓶':
            kind = '塑形机'
        elif product == '高容谷地电池':
            kind = '封装机'
        elif product == '精选荞愈胶囊':
            kind = '灌装机'
        else:
            kind = '粉碎机'
        model_types[kind] += 1
    formula_types = {'粉碎机': 34 + 18 + 11 + 6, '精炼炉': 34 + 17,
                     '研磨机': 17 + 9 + 6, '塑形机': 5 + 1, '配件机': 6,
                     '种植机': 2 * (11 + 6), '采种机': 11 + 6, '封装机': 3, '灌装机': 3}
    assert dict(model_types) == formula_types
    degree_routes = 69 + 51 + 32 * 3 + (5 * 2 + 1) + 6 + 34 + 17 + 3 * 5 + 3 * 4 + 6
    assert degree_routes == len(f.rs) == 317
    assert sum(formula_types.values()) == len(f.ms) == 221
    expected_480 = dict(高容谷地电池=int(b_a * 480 / 8), 精选荞愈胶囊=int(c_a * 480 / 8), each_mineral=480 // 8)
    assert expected_480 == dict(高容谷地电池=36, 精选荞愈胶囊=33, each_mineral=60)
    write('numbers.json', dict(machine_counts=dict(model_types), total_machines=len(f.ms),
                              total_routes=degree_routes, mineral_ports=len(f.ore_routes),
                              rates_a=[str(b_a), str(c_a)], rates_b=[str(b_b), str(c_b)],
                              cycle_480=expected_480,
                              head_lock_bound_step=8 + 8 - 1,
                              worst_service_rates={str(n): str(Q(8, 8 + n - 1)) for n in (2, 3, 6)},
                              sand_powder_rates=[str(sand_a), str(sand_b)],
                              flower_powder_rates=[str(flower_a), str(flower_b)],
                              separated_sand_fast_paths=3 * 10, separated_sand_remaining_paths=32 - 3 * 10))

    # Keep the last result for repeated seed/configuration keys. Extended runs
    # replace earlier inconclusive bounds; completed steps are not double-counted
    # in the final case count. Raw logs remain available.
    files = ['factory_dense_cross.json', 'factory_random_long.json', 'factory_low.json',
             'factory_low_extended_9530.json', 'factory_low_extended_9536.json',
             'factory_low_extended_9533_9535.json', 'factory_low_extended_9537.json',
             'factory_core_mixed.json']
    cases = {}
    executed_steps = 0
    for name in files:
        path = HERE / name
        if not path.exists():
            continue
        for r in json.loads(path.read_text()):
            key = (r['seed'], r['maxlen'], r['initial'], r['grouping'], r.get('core_blue_outlets', 6))
            cases[key] = dict(r, result_file=name)
            executed_steps += r['compared_steps']
    final = list(cases.values())
    certified = [r for r in final if r.get('pass_rates') is True]
    unresolved = [r for r in final if 'period_steps' not in r]
    assert all(r['pass_rates'] for r in final if 'period_steps' in r)
    write('factory_summary.json', dict(cases=len(final), full_rate_cycles=len(certified),
                                       inconclusive=len(unresolved),
                                       compared_steps_final_cases=sum(r['compared_steps'] for r in final),
                                       compared_steps_including_initial_bounds=executed_steps,
                                       largest_cycle_start=max(r['cycle_start'] for r in certified),
                                       largest_run_steps=max(r['compared_steps'] for r in final),
                                       periods=sorted({r['period_steps'] for r in certified}), results=final))
    print(json.dumps(dict(input_files=len(inputs), cases=len(final), cycles=len(certified), inconclusive=len(unresolved),
                          compared_steps=sum(r['compared_steps'] for r in final)), ensure_ascii=False))


if __name__ == '__main__':
    main()
