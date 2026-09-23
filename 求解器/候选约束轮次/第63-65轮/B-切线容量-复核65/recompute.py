#!/usr/bin/env python3
"""第65轮独立复算。从正式规则重建模型，对照第63轮 JSON 数据，不导入其代码。

python -B 求解器/候选约束轮次/第63-65轮/B-切线容量-复核65/recompute.py
输出只落在本脚本目录。--verify-only 仅用标准库重建模型并核验存档证书。
"""
import argparse
from collections import Counter
from fractions import Fraction as F
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SOURCE = HERE.parent / 'B-切线容量'
FORMAL = ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt']
KINDS = ['粉碎机', '精炼炉', '配件机', '塑形机', '种植机', '采种机']
EQ_KINDS = [k for k in KINDS if k != '塑形机']
MINERAL = {'蓝铁矿', '源矿', '蓝铁块', '蓝铁粉末', '源石粉末'}


def write(name, obj):
    (HERE / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2,
                                      default=str) + '\n')


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def parse_recipes():
    body = (ROOT / FORMAL[0]).read_text().split('\n配方\n', 1)[1]
    recipes = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        if '→' not in line:
            kind = line
            continue
        left, right = line.split('→')
        right, ticks = right.split('，')
        def side(s):
            return {name: int(n) for n, name in re.findall(r'(\d+)\s+([^＋]+?)(?=\s*＋|$)', s.strip())}
        recipes.append(dict(kind=kind, inputs=side(left), outputs=side(right),
                            ticks=int(ticks.split()[0])))
    assert len(recipes) == 18
    return recipes


def solve_exact(rows, rhs, width):
    """独立有理数消元，接受冗余等式，要求唯一解。"""
    mat = [[F(x) for x in row] + [F(b)] for row, b in zip(rows, rhs)]
    pivots = []
    for col in range(width):
        pivot = next((r for r in range(len(pivots), len(mat)) if mat[r][col]), None)
        if pivot is None:
            continue
        pos = len(pivots)
        mat[pos], mat[pivot] = mat[pivot], mat[pos]
        divisor = mat[pos][col]
        mat[pos] = [x / divisor for x in mat[pos]]
        for r in range(len(mat)):
            if r != pos and mat[r][col]:
                factor = mat[r][col]
                mat[r] = [x - factor*y for x, y in zip(mat[r], mat[pos])]
        pivots.append(col)
    assert all(any(row[:-1]) or row[-1] == 0 for row in mat)
    assert len(pivots) == width
    answer = [F(0)] * width
    for r, col in enumerate(pivots):
        answer[col] = mat[r][-1]
    return answer


def global_accounting(recipes, items, net):
    # 目标固定、非成品零入库。蓝铁粉末回炼为0：最低34+17批已占满51台精炼炉。
    final = {'高容谷地电池': F(3, 5), '精选荞愈胶囊': F(11, 20)}
    rows, rhs = [], []
    for item in items:
        if item not in {'蓝铁矿', '源矿'}:
            rows.append(net[item])
            rhs.append(final.get(item, F(0)))
    recycle = next(j for j, r in enumerate(recipes)
                   if r['kind'] == '精炼炉' and '蓝铁粉末' in r['inputs'])
    rows.append([int(j == recycle) for j in range(len(recipes))])
    rhs.append(0)
    rates = solve_exact(rows, rhs, len(recipes))
    assert all(x >= 0 for x in rates)
    raw = {i: -sum(a*b for a, b in zip(net[i], rates)) for i in ['蓝铁矿', '源矿']}
    assert raw == {'蓝铁矿': F(34), '源矿': F(18)}
    loads = {}
    for r, q in zip(recipes, rates):
        loads[r['kind']] = loads.get(r['kind'], F(0)) + q*r['ticks']
    minima = {k: -(-q.numerator // q.denominator) for k, q in loads.items()}
    assert sum(minima.values()) == 217
    area = sum(n*(9 if k in KINDS[:4] else 25 if k in KINDS[4:] else 24)
               for k, n in minima.items())
    assert area == 3291
    single_min = {k: (loads[k] - (minima[k]-1))/next(r['ticks'] for r in recipes if r['kind'] == k)
                  for k in ['研磨机', '封装机', '灌装机']}
    assert single_min == {'研磨机': F(1, 2), '封装机': F(1, 5), '灌装机': F(3, 20)}
    recipe_checks = []
    for r, q in zip(recipes, rates):
        ki = sum(n for i, n in r['inputs'].items() if i in MINERAL)
        ko = sum(n for i, n in r['outputs'].items() if i in MINERAL)
        recipe_checks.append(dict(**r, rate=q, mineral_in=ki, mineral_out=ko,
                                  mineral_decrease=ki-ko))
        assert ki-ko == (2 if r['kind'] == '研磨机' and ki else 0)
    kappa = {k: max(F(r['mineral_in'], r['ticks']) for r in recipe_checks if r['kind'] == k)
             for k in loads}
    assert kappa == {k: F(1) if k in ['粉碎机', '精炼炉'] else F(2) if k == '研磨机' else F(0)
                     for k in loads}
    return rates, dict(raw=raw, loads=loads, minima=minima, machine_area=area,
                       single_large_minimum=single_min, mineral_receive_bounds=kappa,
                       recipes=recipe_checks)


def boundary(g):
    # 在唯一空格两侧分别从头铺长3的取货口。
    starts = list(range(0, g, 3)) + list(range(g+1, 70, 3))
    assert len(starts) == 23 and all(s+2 < 70 for s in starts)
    return [s+1 for s in starts]


def cells(x, y, w, h):
    return {(a, b) for a in range(x, x+w) for b in range(y, y+h)}


def orientations(kind):
    w, h = (3, 3) if kind in KINDS[:4] else (5, 5) if kind in KINDS[4:] else (6, 4)
    if w == h:
        return [(w, h, d) for d in ['N', 'S', 'E', 'W']]
    return [(6, 4, 'N'), (6, 4, 'S'), (4, 6, 'E'), (4, 6, 'W')]


def port_neighbors(x, y, w, h, direction):
    if direction == 'N':
        return [(a, y+h) for a in range(x, x+w)]
    if direction == 'S':
        return [(a, y-1) for a in range(x, x+w)]
    if direction == 'E':
        return [(x+w, b) for b in range(y, y+h)]
    return [(x-1, b) for b in range(y, y+h)]


def geometry():
    pairs = [(gleft, gdown) for gleft in range(0, 70, 3) for gdown in range(0, 70, 3)
             if gleft == 0 or gdown == 0]
    assert len(pairs) == 47
    summaries, b7_cases = [], []
    for b in [6, 7, 9, 17]:
        for gl, gd in pairs:
            ports = boundary(gd)
            count = sum(x >= 49 for x in ports)
            assert count == 7
            forced = {(x, 1) for x in ports} | {(1, y) for y in boundary(gl)}
            candidates = {}
            for kind, min_in, min_out in [('研磨机', F(3, 2), F(1, 2)),
                                         ('封装机', F(5), F(1, 5)),
                                         ('灌装机', F(3), F(3, 20))]:
                accepted = []
                for w, h, out in orientations(kind):
                    inp = dict(N='S', S='N', E='W', W='E')[out]
                    for x in range(49, 71-w):
                        for y in range(1, b-h+1):
                            occupied = cells(x, y, w, h)
                            if occupied & forced:
                                continue
                            def free(p):
                                # 第0行全是无可用存货口的取货口或单出口死端空格。
                                a, c = p
                                return 0 <= a < 70 and c >= 1 and c < b
                            ni = sum(free(p) for p in port_neighbors(x, y, w, h, inp))
                            no = sum(free(p) for p in port_neighbors(x, y, w, h, out))
                            if ni < min_in or no < min_out:
                                continue
                            if y == 2 and h == 4:
                                m = sum(x <= a < x+w for a in ports)
                                demand = min_out if out == 'S' else min_in
                                if F(m) + demand > 2:
                                    continue
                            accepted.append([x, y, w, h, out])
                candidates[kind] = accepted
            if b == 6:
                assert all(not a for a in candidates.values())
            if b == 7:
                for kind, placements in candidates.items():
                    assert all(y == 2 and w == 6 and h == 4 and out == 'S'
                               for x, y, w, h, out in placements)
                    for first, second in product(placements, repeat=2):
                        assert cells(*first[:4]) & cells(*second[:4])
                for placement in candidates['研磨机']:
                    gx, gy, gw, gh, _ = placement
                    block = cells(gx, gy, gw, gh)
                    assert gd-1 >= gx and gd+1 < gx+gw
                    # 容纳每一种其他机型、每一朝向；甚至不要求端口畅通，仍须过第4行。
                    other_domains = {}
                    for kind in KINDS:
                        found = set()
                        for w, h, _ in orientations(kind):
                            for x in range(49, 71-w):
                                for y in range(1, b-h+1):
                                    box = cells(x, y, w, h)
                                    if not box & (forced | block):
                                        assert y <= 4 < y+h
                                        found.add((x, y, w, h))
                        other_domains[kind] = len(found)
                    b7_cases.append(dict(left_gap=gl, bottom_gap=gd,
                                         grinder=placement, other_domain_counts=other_domains))
            summaries.append(dict(b=b, left_gap=gl, bottom_gap=gd,
                                  raw_ports=count, large_domains=candidates))
    assert len(b7_cases) == 10
    assert sorted({d['bottom_gap'] for d in b7_cases}) == [51, 54, 57, 60, 63, 66]
    penalties = []
    for kind in KINDS + ['研磨机', '封装机', '灌装机', '协议核心', '供电桩']:
        hs = [9] if kind == '协议核心' else [2] if kind == '供电桩' else sorted({h for _, h, _ in orientations(kind)})
        kappa = 1 if kind in ['粉碎机', '精炼炉'] else 2 if kind == '研磨机' else 0
        for h in hs:
            assert h-kappa >= 2
            penalties.append(dict(kind=kind, h=h, kappa=kappa, penalty=h-kappa))
    # 原D漏掉纵坐标限定：此桩跨48/49列，却完全不碰b=9的下侧切线。
    pole = cells(48, 63, 2, 2)
    hole = cells(49, 9, 21, 53)
    lower_cut_rows = set(range(1, 9))
    assert not pole & hole and not ({y for _, y in pole} & lower_cut_rows)
    return dict(boundary_pair_count=len(pairs), enumerations=summaries,
                b7_cases=b7_cases, crossing_penalties=penalties,
                scope_example=dict(b=9, pole=[48, 63, 2, 2],
                                   literal_D_contribution=2, lower_D_contribution=0,
                                   status='局部占格来源；不是达标全厂反例'))


def model(recipes, items, net, rates):
    nr, ns = len(recipes), len(items)
    nv = nr+1+ns
    blank = lambda: [F(0)] * nv
    def kindrow(kind):
        return [F(int(j < nr and recipes[j]['kind'] == kind)) for j in range(nv)]
    A, rhs = [], []
    def add(row, b):
        A.append(row)
        rhs.append(F(b))
    grind = kindrow('研磨机')
    add(grind, 1)
    add([-a for a in grind], F(-1, 2))
    minerals = blank()
    for j, r in enumerate(recipes):
        if r['kind'] == '研磨机' and any(i in MINERAL for i in r['inputs']):
            minerals[j] = -1
    add(minerals, F(-1, 2))
    shape = kindrow('塑形机')
    add(shape, 0)
    add([-a for a in shape], 0)
    for i, item in enumerate(items):
        v = [F(a) for a in net[item]] + [F(int(item == '蓝铁矿') - int(item == '源矿'))] + [F(0)]*ns
        const = 7 if item == '源矿' else 0
        for sign in [1, -1]:
            row = [sign*a for a in v]
            row[nr+1+i] = -1
            add(row, -sign*const)
    E = [kindrow(k) for k in EQ_KINDS]
    upper = [F(0) if r['kind'] in ['封装机', '灌装机'] else q for r, q in zip(recipes, rates)] + [F(7)] + [None]*ns
    c = [F(0)]*(nr+1) + [F(1)]*ns
    return dict(A=A, rhs=rhs, E=E, upper=upper, objective=c)


def branches():
    return [small+medium for small in product(range(6), repeat=4)
            for medium in product(range(4), repeat=2)
            if 3*sum(small)+5*sum(medium) <= 15]


def branch_rhs(base, counts):
    b = base['rhs'].copy()
    mapping = dict(zip(KINDS, counts))
    b[3] = F(mapping['塑形机'])
    b[4] = F(1, 2)-mapping['塑形机']
    d = [F(mapping[k]) for k in EQ_KINDS]
    return b, d


def dot(a, b):
    return sum((x*y for x, y in zip(a, b)), F(0))


def check_cert(base, cert):
    A, E, upper, c = [base[k] for k in ['A', 'E', 'upper', 'objective']]
    b, d = branch_rhs(base, cert['counts'])
    y, e, lo, hi, x = [[F(v) for v in cert[k]] for k in ['y', 'e', 'lower', 'upper', 'primal']]
    assert [len(y), len(e), len(lo), len(hi), len(x)] == [len(A), len(E), len(c), len(c), len(c)]
    assert all(v <= 0 for v in y+hi) and all(v >= 0 for v in lo+x)
    assert all(dot(row, x) <= bound for row, bound in zip(A, b))
    assert all(dot(row, x) == bound for row, bound in zip(E, d))
    for j, cap in enumerate(upper):
        if cap is None:
            assert hi[j] == 0
        else:
            assert x[j] <= cap
        assert c[j] == sum(A[i][j]*y[i] for i in range(len(A))) + sum(E[i][j]*e[i] for i in range(len(E))) + lo[j]+hi[j]
    bound = dot(b, y)+dot(d, e)+sum(cap*v for cap, v in zip(upper, hi) if cap is not None)
    assert bound == dot(c, x) == F(cert['bound'])
    assert bound >= F(19, 3)
    return bound


def certificate_audit(base, expected, path):
    certificates = json.loads(path.read_text())
    counts = [tuple(c['counts']) for c in certificates]
    assert len(counts) == len(set(counts)) == len(expected) == 215
    assert set(counts) == set(expected)
    values = [check_cert(base, c) for c in certificates]
    return dict(branch_count=len(values), minimum=min(values),
                maximum=max(values), bound_histogram=dict(Counter(map(str, values))),
                minimum_counts=[c['counts'] for c, v in zip(certificates, values) if v == min(values)],
                all_exact=True)


def regenerate(base, expected):
    import numpy as np
    from scipy.optimize import linprog
    A, E, upper, c = [base[k] for k in ['A', 'E', 'upper', 'objective']]
    arr = lambda a: np.array(a, dtype=float)
    def rational(values):
        return [str(F(float(v)).limit_denominator(1000000)) for v in values]
    certificates = []
    for counts in expected:
        b, d = branch_rhs(base, counts)
        result = linprog(arr(c), A_ub=arr(A), b_ub=arr(b), A_eq=arr(E), b_eq=arr(d),
                         bounds=[(0, None if cap is None else float(cap)) for cap in upper], method='highs')
        assert result.success, (counts, result.message)
        cert = dict(counts=list(counts), y=rational(result.ineqlin.marginals),
                    e=rational(result.eqlin.marginals), lower=rational(result.lower.marginals),
                    upper=rational(result.upper.marginals), primal=rational(result.x),
                    bound=str(F(float(result.fun)).limit_denominator(1000000)))
        check_cert(base, cert)  # 浮点只用来找证书；通过分数恒等式才接受。
        certificates.append(cert)
    write('independent_certificates.json', certificates)
    return certificate_audit(base, expected, HERE / 'independent_certificates.json')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    input_paths = [ROOT / name for name in FORMAL] + [ROOT / '候选约束.txt',
                   HERE.parent / 'B-切线容量-推导.md',
                   SOURCE / 'b7_lp_model.json', SOURCE / 'b7_rational_certificates.json']
    before = {str(p.relative_to(ROOT)): digest(p) for p in input_paths}
    recipes = parse_recipes()
    items = sorted({i for r in recipes for side in ['inputs', 'outputs'] for i in r[side]})
    assert len(items) == 19
    net = {i: [r['outputs'].get(i, 0)-r['inputs'].get(i, 0) for r in recipes] for i in items}
    rates, accounting = global_accounting(recipes, items, net)
    geo = geometry()
    base = model(recipes, items, net, rates)
    expected = branches()
    assert len(expected) == len(set(expected)) == 215
    # 原模型只能在独立重建之后作比较，不作为输入矩阵使用。
    old = json.loads((SOURCE / 'b7_lp_model.json').read_text())
    assert items == old['items'] and KINDS == old['kinds'] and EQ_KINDS == old['eq_kinds']
    def normalized(v):
        if isinstance(v, list):
            return [normalized(x) for x in v]
        return None if v is None else F(v)
    for key in base:
        assert normalized(base[key]) == normalized(old[key]), key
    original = certificate_audit(base, expected, SOURCE / 'b7_rational_certificates.json')
    independent = (certificate_audit(base, expected, HERE / 'independent_certificates.json')
                   if args.verify_only else regenerate(base, expected))
    positions = []
    for b in [6, 7, 9, 17]:
        for transpose in [False, True]:
            for poles in [10, 11, 12]:
                positions.append(dict(position=[b, 49] if transpose else [49, b], P=poles,
                                      excluded=b in [6, 7],
                                      deficit='2' if b == 6 else '1/3' if b == 7 else None,
                                      remaining_slack=f'{b-8}+2G-D_lower' if b >= 9 else None))
    areas = sorted({w*h for w in range(6, 69) for h in range(w, 69) if w*h < 1113})
    assert areas[-1] == 1110
    assert before == {str(p.relative_to(ROOT)): digest(p) for p in input_paths}
    write('accounting.json', accounting)
    write('geometry.json', geo)
    write('rebuilt_model.json', dict(**base, items=items, recipes=recipes, count_order=KINDS,
                                    equality_order=EQ_KINDS, integer_branches=expected))
    summary = dict(status='PASS', formal_hashes={n: before[n] for n in FORMAL},
                   input_hashes_unchanged=True, source_model_matches=True,
                   boundary_pairs=47, b7_layout_cases=10,
                   original_certificates=original, independent_certificates=independent,
                   position_P_branches=positions, next_integer_area=areas[-1],
                   first_candidate='修正：D只统计行1…b−1内的跨线单位',
                   second_candidate='未否证：四位置各P=10、11、12排除')
    write('results.json', summary)
    write('input_manifest.json', before)
    print(json.dumps(dict(status='PASS', branches=215, minimum=str(independent['minimum']),
                          boundary_pairs=47, b7_layout_cases=10,
                          excluded_position_P_branches=sum(p['excluded'] for p in positions),
                          unchanged_inputs=True), ensure_ascii=False))


if __name__ == '__main__':
    main()
