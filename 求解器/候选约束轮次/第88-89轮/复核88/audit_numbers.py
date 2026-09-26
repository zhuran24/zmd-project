"""Independent exact arithmetic for review 88. Standard library only."""
from collections import Counter
from fractions import Fraction as F
from hashlib import sha256
from pathlib import Path
import json
import math
import os
import re

HERE = Path(__file__).resolve().parent
BASE = HERE.parent


def solve(rows, n):
    a = [[F(x) for x in row] for row in rows]
    rank = 0
    pivots = []
    for col in range(n):
        pivot = next((j for j in range(rank, len(a)) if a[j][col]), None)
        if pivot is None:
            continue
        a[rank], a[pivot] = a[pivot], a[rank]
        div = a[rank][col]
        a[rank] = [x / div for x in a[rank]]
        for j in range(len(a)):
            if j != rank and a[j][col]:
                v = a[j][col]
                a[j] = [x-v*y for x, y in zip(a[j], a[rank])]
        pivots.append(col)
        rank += 1
    assert all(any(row[:n]) or not row[n] for row in a)
    assert rank == n
    out = [F(0)] * n
    for row, col in zip(a, pivots):
        out[col] = row[n]
    assert all(sum(F(x)*y for x, y in zip(row[:n], out)) == row[n]
               for row in rows)
    return out


def main():
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    rules = (BASE/'前提快照/《明日方舟：终末地》游戏规则.txt').read_text()
    names = ['粉碎机', '精炼炉', '研磨机', '塑形机', '配件机',
             '种植机', '采种机', '封装机', '灌装机']
    recipes = []
    machine = None
    for line in rules.split('配方\n', 1)[1].splitlines():
        line = line.strip()
        if line in names:
            machine = line
        if '→' not in line:
            continue
        left, right = line.split('→')
        prod, dur = right.split('，')
        inputs = {n.strip(): int(v) for v, n in
                  (part.strip().split(' ', 1) for part in left.split('＋'))}
        k, item = prod.strip().split(' ', 1)
        recipes.append(dict(machine=machine, inputs=inputs, output=item.strip(),
                            k=int(k), d=int(dur.strip().split()[0])))
    assert len(recipes) == 18
    all_items = sorted(set(x for r in recipes for x in r['inputs']) |
                       {r['output'] for r in recipes})
    assert len(all_items) == 19
    n = len(recipes)
    back = next(i for i, r in enumerate(recipes)
                if r['machine']=='精炼炉' and r['inputs']=={'蓝铁粉末': 1})
    def flows(rval):
        rows = []
        for item in all_items:
            if item in ('源矿', '蓝铁矿'):
                continue
            rhs = {'高容谷地电池': F(3, 5), '精选荞愈胶囊': F(11, 20)}.get(item, F(0))
            row = [(r['k'] if r['output']==item else 0)-r['inputs'].get(item, 0)
                   for r in recipes]
            rows.append(row+[rhs])
        rows.append([int(i==back) for i in range(n)]+[rval])
        return solve(rows, n)
    f0, f1 = flows(F(0)), flows(F(1))
    affine = [(a, b-a) for a, b in zip(f0, f1)]
    loads = {m: [sum(f0[i]*r['d'] for i, r in enumerate(recipes) if r['machine']==m),
                 sum((f1[i]-f0[i])*r['d'] for i, r in enumerate(recipes) if r['machine']==m)]
             for m in names}
    lower = [math.ceil(loads[m][0]) for m in names]
    assert lower == [68, 51, 32, 6, 6, 32, 16, 3, 3]
    sizes = {m: 9 if m in names[:2]+names[3:5] else 25 if m in names[5:7] else 24
             for m in names}
    # Canonical two-slot grinder inventory: item identity determines a unique slot.
    materials = ('蓝铁粉末', '源石粉末', '荞花粉末', '砂叶粉末')
    states = [dict()]
    for a in materials:
        states += [{a: i} for i in range(1, 51)]
    for u, a in enumerate(materials):
        for b in materials[u+1:]:
            states += [{a: i, b: j} for i in range(1, 51) for j in range(1, 51)]
    def double_main(s):
        return len(s)==2 and all(x in materials[:3] for x in s)
    entry, start_entry = [], 0
    for state in states:
        if double_main(state):
            continue
        for item in materials:
            if state.get(item, 0)==50 or item not in state and len(state)==2:
                continue
            nxt = dict(state)
            nxt[item] = nxt.get(item, 0)+1
            if double_main(nxt):
                assert len(state)==1 and item not in state
                entry.append([state, item, nxt])
        for item in materials[:3]:
            if state.get(item, 0)>=2 and state.get('砂叶粉末', 0)>=1:
                nxt = {a: v-({'砂叶粉末': 1, item: 2}.get(a, 0)) for a, v in state.items()}
                nxt = {a: v for a, v in nxt.items() if v}
                start_entry += double_main(nxt)
    assert len(states)==15201 and len(entry)==300 and start_entry==0
    # Construct the topology from the candidate text, counting logical paths separately.
    counts = dict(zip(names, [34+18+11+6, 34+17, 17+9+6, 5+1, 6, 2*(11+6), 11+6, 3, 3]))
    ins = dict(zip(names, [69, 51, 32*3, 5*2+1, 6, 34, 17, 3*5, 3*4]))
    outs = dict(zip(names, [34+18+32+6*2, 51, 32, 6, 6, 34, 17*2, 3, 3]))
    assert sum(ins.values())+6 == sum(outs.values())+52 == 317
    final = dict(
        premises={str(p.relative_to(BASE)): sha256(p.read_bytes()).hexdigest()
                  for p in [BASE/'前提快照'/x for x in
                            ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt']]
                  + [BASE/'修正版清单.json']},
        recipe_count=n, item_count=len(all_items),
        recipe_rates=[dict(**r, rate_at_r0=str(affine[i][0]), coefficient_r=str(affine[i][1]))
                      for i, r in enumerate(recipes)],
        workloads={m: [str(x) for x in v] for m, v in loads.items()},
        lower_counts=lower, lower_total=sum(lower),
        lower_area=sum(sizes[m]*c for m, c in zip(names, lower)),
        grinder=dict(states=len(states), incoming_double_main=len(entry),
                     start_double_main=start_entry, example=entry[0]),
        population=dict(blocked_excess=str(3*F(50)+2+F(49, 2)),
                        retained_excess=str(3*F(50)+2+F(49, 2)-F(1, 2))),
        skeleton=dict(counts=counts, machines=sum(counts.values()),
                      area=sum(counts[m]*sizes[m] for m in names),
                      inputs=sum(ins.values()), outputs=sum(outs.values()), paths=317,
                      battery=str(3*F(1, 5)), capsule=str(2*F(1, 5)+(1+F(1, 2))/10)))
    (HERE/'numbers.json').write_text(json.dumps(final, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: final[k] for k in ['recipe_count', 'item_count', 'workloads',
                     'lower_counts', 'lower_total', 'lower_area', 'grinder', 'population', 'skeleton']},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
