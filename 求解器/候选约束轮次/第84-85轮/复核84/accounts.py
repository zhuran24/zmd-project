#!/usr/bin/env python3
"""Independent exact arithmetic for review 84. Python standard library only."""
import hashlib
import itertools as it
import json
import math
import os
import re
from collections import Counter
from fractions import Fraction as F
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})


def parse_recipes():
    rows = (BASE / '前提快照/《明日方舟：终末地》游戏规则.txt').read_text().split('配方\n', 1)[1]
    ans = []
    machine = None
    for s in rows.splitlines():
        s = s.strip()
        if not s:
            continue
        if '→' not in s:
            machine = s
            continue
        left, right = s.split('→')
        product, duration = right.split('，')
        def items(x):
            return {name.strip(): int(n) for n, name in re.findall(r'(\d+)\s+([^＋]+)', x)}
        ans.append((machine, items(left), items(product), int(duration.split()[0])))
    return ans


def stocks(kinds, slots):
    yield {}
    for n in range(1, slots + 1):
        for kk in it.combinations(kinds, n):
            for qq in it.product(range(1, 51), repeat=n):
                yield dict(zip(kk, qq))


def accepts(s, x, slots):
    return s.get(x, 0) < 50 and (x in s or len(s) < slots)


def can_start(s, recipes):
    return any(all(s.get(x, 0) >= n for x, n in inp.items()) for _, inp, _, _ in recipes)


def dead_counts(recipes):
    out = {}
    for m in ('研磨机', '封装机', '灌装机', '塑形机'):
        rr = [r for r in recipes if r[0] == m]
        kinds = sorted(set().union(*(set(r[1]) for r in rr)))
        slots = 1 if m == '塑形机' else 2
        counts = [0, 0]
        pure_clause_failures = 0
        for s in stocks(kinds, slots):
            if m == '研磨机' and len(s) == 2 and '砂叶粉末' not in s:
                continue
            if can_start(s, rr):
                continue
            for j, candidates in enumerate((kinds, kinds + ['误料'])):
                rejected = [x for x in candidates if not accepts(s, x, slots)]
                counts[j] += 2 ** len(rejected) - 1
            for r in rr:
                if set(s) <= set(r[1]) and all(not accepts(s, x, slots) for x in r[1]):
                    pure_clause_failures += 1
        out[m] = {'legal_heads': counts[0], 'plus_one_error_kind': counts[1],
                  'difference': counts[1] - counts[0], 'pure_clause_failures': pure_clause_failures}
    grinder = [r for r in recipes if r[0] == '研磨机']
    kinds = sorted(set().union(*(set(r[1]) for r in grinder))) + ['误料']
    def bad(s):
        return '误料' in s or (len(s) == 2 and '砂叶粉末' not in s)
    transitions = Counter()
    total_states = 0
    for s in stocks(kinds, 2):
        total_states += 1
        if bad(s):
            continue
        for x in kinds:
            if accepts(s, x, 2):
                nxt = dict(s)
                nxt[x] = nxt.get(x, 0) + 1
                if bad(nxt):
                    transitions['wrong' if x == '误料' else 'two_main'] += 1
    old = {'源石粉末': 1, '砂叶粉末': 50}
    heads = ['蓝铁粉末', '砂叶粉末']
    out['old_main_counterexample'] = {
        'stock': old, 'heads': heads, 'can_start': can_start(old, grinder),
        'accepts': [accepts(old, x, 2) for x in heads]}
    prior = {'源石粉末': 1}
    assert accepts(prior, '蓝铁粉末', 2)
    out['old_main_two_main_entry'] = {'before': prior, 'arriving': '蓝铁粉末',
                                     'after': {'源石粉末': 1, '蓝铁粉末': 1},
                                     'can_start_after': can_start({'源石粉末': 1, '蓝铁粉末': 1}, grinder)}
    out['grinder_all_states'] = total_states
    out['first_bad_entries'] = dict(transitions)
    return out


def rref(a, b):
    mat = [[F(x) for x in row] + [F(y)] for row, y in zip(a, b)]
    n, rank, pivots = len(a[0]), 0, []
    for j in range(n):
        p = next((i for i in range(rank, len(mat)) if mat[i][j]), None)
        if p is None:
            continue
        mat[rank], mat[p] = mat[p], mat[rank]
        q = mat[rank][j]
        mat[rank] = [v / q for v in mat[rank]]
        for i in range(len(mat)):
            if i != rank and mat[i][j]:
                q = mat[i][j]
                mat[i] = [x - q * y for x, y in zip(mat[i], mat[rank])]
        pivots.append(j)
        rank += 1
    assert all(any(row[:n]) or not row[n] for row in mat)
    free = [j for j in range(n) if j not in pivots]
    return mat, pivots, free


def rates(recipes):
    species = sorted(set().union(*(set(r[1]) | set(r[2]) for r in recipes)))
    net = {'蓝铁矿': -34, '源矿': -18, '高容谷地电池': F(3, 5), '精选荞愈胶囊': F(11, 20)}
    a = [[r[2].get(x, 0) - r[1].get(x, 0) for r in recipes] for x in species]
    mat, pivots, free = rref(a, [net.get(x, 0) for x in species])
    assert len(free) == 1
    f = free[0]
    solution = [(F(0), F(0)) for _ in recipes]
    solution[f] = (F(0), F(1))
    for i, j in enumerate(pivots):
        solution[j] = (mat[i][-1], -mat[i][f])
    group = {}
    for (m, _, _, d), (v, slope) in zip(recipes, solution):
        group.setdefault(m, [F(0), F(0)])
        group[m][0] += d * v
        group[m][1] += d * slope
    minimum = {m: math.ceil(v[0]) for m, v in group.items()}
    size = {m: (25 if m in ('种植机', '采种机') else 24 if m in ('研磨机', '封装机', '灌装机') else 9) for m in group}
    source = F(52) + sum(sum(r[2].values()) * v[0] for r, v in zip(recipes, solution))
    return {'recipe_count': len(recipes), 'species_count': len(species), 'rank': len(pivots),
            'free_recipe': recipes[f], 'per_machine_work': group, 'machine_lower_bounds': minimum,
            'minimum_total': sum(minimum.values()), 'minimum_body_area': sum(size[m] * c for m, c in minimum.items()),
            'physical_source_rate_r0': source,
            'recipe_rates': [{'machine': r[0], 'input': r[1], 'output': r[2], 'rate': v} for r, v in zip(recipes, solution)]}


def freeze(recipes):
    def solve(rejected, no_store):
        stopped = set()
        finite_items = set(rejected)
        plant_joins = []
        while True:
            before = (len(stopped), len(finite_items))
            for j, (_, inp, prod, _) in enumerate(recipes):
                if any(x in finite_items for x in prod):
                    stopped.add(j)
            for x in no_store:
                users = {j for j, r in enumerate(recipes) if x in r[1]}
                if users <= stopped:
                    finite_items.add(x)
            for p in ('荞花', '砂叶'):
                crush = next(j for j, r in enumerate(recipes) if r[0] == '粉碎机' and p in r[1])
                seed = next(j for j, r in enumerate(recipes) if r[0] == '采种机' and p in r[1])
                grow = next(j for j, r in enumerate(recipes) if r[0] == '种植机' and p + '种子' in r[1])
                if crush in stopped:
                    if seed not in stopped:
                        plant_joins.append(p)
                    stopped.update((seed, grow))
            iron = {'蓝铁矿', '蓝铁块', '蓝铁粉末'}
            leaving = {j for j, r in enumerate(recipes) if set(r[1]) & iron and not set(r[2]) <= iron}
            if iron <= no_store and leaving <= stopped:
                # Internal block/powder conversions preserve the family count;
                # finite capacity bounds new ore, then bounds ore refinement.
                stopped.add(next(j for j, r in enumerate(recipes) if '蓝铁矿' in r[1]))
            if before == (len(stopped), len(finite_items)):
                break
        return {'count': len(stopped), 'stopped': [recipes[j][1] for j in sorted(stopped)],
                'plant_family_arguments': plant_joins}
    all_species = set().union(*(set(r[1]) | set(r[2]) for r in recipes))
    return {
        'battery': solve({'高容谷地电池'}, {'源矿', '源石粉末', '致密源石粉末', '钢制零件'}),
        'capsule': solve({'精选荞愈胶囊'}, {'钢质瓶', '细磨荞花粉末', '荞花粉末'}),
        'both': solve({'高容谷地电池', '精选荞愈胶囊'}, all_species)}


def arithmetic_checks():
    violations = []
    n = 0
    for den in range(1, 38):
        for num in range(0, 200 * den + 1):
            t = F(num, den)
            e = max(0, math.ceil(t) - 1) - (math.floor(t) + 1)
            n += 1
            if e < -2:
                violations.append(str(t))
    counts = {'粉碎机': 69, '精炼炉': 51, '研磨机': 32, '塑形机': 6, '配件机': 6,
              '种植机': 34, '采种机': 17, '封装机': 3, '灌装机': 3}
    inlet = [69, 51, 96, 11, 6, 34, 17, 15, 12]
    outlet = [96, 51, 32, 6, 6, 34, 34, 3, 3]
    area = 9 * (69 + 51 + 6 + 6) + 25 * (34 + 17) + 24 * (32 + 3 + 3)
    return {'A_real_interval_checks': n, 'A_violations': violations, 'A_output_lower_bounds': [47, 44, 41],
            'D_block_threshold': F(50 + 1 + 50 + 50 + 1) + F(49, 2),
            'D_after_one_half_loss': F(50 + 1 + 50 + 50 + 1) + F(49, 2) - F(1, 2),
            'skeleton': {'counts': counts, 'total': sum(counts.values()), 'body_area': area,
                         'machine_input_channels': sum(inlet), 'machine_output_channels': sum(outlet),
                         'all_logical_paths': sum(outlet) + 52, 'all_destinations': sum(inlet) + 6,
                         'battery': 3 * F(1, 5), 'capsule': 2 * F(1, 5) + F(3, 20),
                         'iron_ore': 2 * (6 + 10 + 1), 'source_ore': 3 * 3 * 2,
                         'sand_powder': 17 + 9 + F(11, 2)}}


def main():
    rr = parse_recipes()
    ans = {'snapshot_hashes': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in (BASE / '前提快照').glob('*.txt') if p.name != '来源提交.txt'},
           'candidate_hash': hashlib.sha256((BASE / '修正版清单.json').read_bytes()).hexdigest(),
           'dead': dead_counts(rr), 'rates': rates(rr), 'freeze': freeze(rr), 'checks': arithmetic_checks()}
    assert [ans['dead'][m]['legal_heads'] for m in ('研磨机', '封装机', '灌装机')] == [466, 25, 20]
    assert [ans['dead'][m]['plus_one_error_kind'] for m in ('研磨机', '封装机', '灌装机')] == [1078, 1072, 857]
    assert [ans['freeze'][m]['count'] for m in ('battery', 'capsule', 'both')] == [4, 6, 16]
    (HERE / 'accounts.json').write_text(json.dumps(ans, ensure_ascii=False, indent=2, default=str) + '\n')
    print(json.dumps(ans, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
