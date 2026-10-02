#!/usr/bin/env python3
"""Finite audits and exact arithmetic. No author scripts are imported."""
from collections import Counter
from fractions import Fraction as Q
from itertools import combinations, permutations, product
from pathlib import Path
import json
import random

OUT = Path(__file__).resolve().parent
GOODS = ('源矿','蓝铁矿','砂叶粉末')


def receive_by_slots(initial, words, blocked_kind):
    bins = [list(x) for x in initial]
    accepted = 0
    for word in words:
        if word == blocked_kind:
            continue
        same = [i for i,b in enumerate(bins) if b[0] == word]
        empty = [i for i,b in enumerate(bins) if b[0] is None]
        available = same or empty
        if not available:
            continue
        j = available[0]
        if bins[j][1] == 50:
            continue
        bins[j] = [word,bins[j][1]+1]
        accepted += 1
    return accepted, {k:n for k,n in bins if k is not None}


def can_receive_by_counts(initial, words, blocked_kind):
    before = Counter({k:n for k,n in initial if k is not None})
    incoming = Counter(words)
    result = before + incoming
    okay = (blocked_kind not in incoming and len(result) <= len(initial)
            and all(n <= 50 for n in result.values()))
    return okay, dict(result)


def audit_reception():
    cases, orders, all_fit = 0, 0, 0
    for slot_count in (1,2):
        for types in range(slot_count+1):
            for kinds in combinations(GOODS,types):
                for quantities in product((1,49,50),repeat=types):
                    initial = list(zip(kinds,quantities))+[(None,0)]*(slot_count-types)
                    for blocked in (None,)+tuple(k for k in GOODS if k not in kinds):
                        for count in range(5):
                            for word in product(GOODS,repeat=count):
                                okay,total = can_receive_by_counts(initial,word,blocked)
                                for perm in set(permutations(word)):
                                    received,actual = receive_by_slots(initial,perm,blocked)
                                    assert (received == count) == okay
                                    if okay:
                                        assert actual == total
                                    orders += 1
                                cases += 1
                                all_fit += okay
    return dict(cases=cases,orders=orders,all_fit_cases=all_fit,differences=0)


def layers_recursive(out):
    cache = {}
    def visit(v):
        if v in cache:
            return cache[v]
        target = out[v]
        cache[v] = visit(target)+1 if target in out and out[target] is not None else 1
        return cache[v]
    return {v: visit(v) for v in out}


def layers_iteration(out):
    answer = {v:1 for v in out}
    for _ in range(len(out)):
        newer = {}
        for v,target in out.items():
            newer[v] = 1 if target not in out or out[target] is None else 1+answer[target]
        if newer == answer:
            return answer
        answer = newer
    raise AssertionError('non-DAG')


def audit_layers():
    rng = random.Random(930092)
    count, dead_ends = 0, 0
    for _ in range(5000):
        n = rng.randrange(1,10)
        out = {i:rng.choice([None,-1,-2]+list(range(i+1,n))) for i in range(n)}
        incoming = Counter(t for t in out.values() if t is not None)
        if any(k >= 0 and v > 3 for k,v in incoming.items()):
            continue
        a,b = layers_recursive(out),layers_iteration(out)
        assert a == b
        for target in incoming:
            assert len({a[v] for v in out if out[v] == target}) == 1
        dead_ends += any(target in out and out[target] is None for target in out.values())
        count += 1
    return dict(dags=count,including_dead_end_examples=dead_ends,differences=0,
                scope='抽象元件有向无环图；不声称这些图是可摆放的布局')


def gaussian(rows, rhs, size):
    a = [[Q(x) for x in row]+[Q(y)] for row,y in zip(rows,rhs)]
    pivot_row, pivot_cols = 0, []
    for col in range(size):
        chosen = next((i for i in range(pivot_row,len(a)) if a[i][col]),None)
        if chosen is None:
            continue
        a[pivot_row],a[chosen] = a[chosen],a[pivot_row]
        denominator = a[pivot_row][col]
        a[pivot_row] = [v/denominator for v in a[pivot_row]]
        for j in range(len(a)):
            if j != pivot_row:
                q = a[j][col]
                a[j] = [u-q*v for u,v in zip(a[j],a[pivot_row])]
        pivot_cols.append(col)
        pivot_row += 1
    assert len(pivot_cols) == size
    for row in a[pivot_row:]:
        assert all(v == 0 for v in row)
    answer = [Q(0)]*size
    for i,c in enumerate(pivot_cols):
        answer[c] = a[i][-1]
    return answer


def arithmetic():
    # Encoding A: backward substitution using the displayed recipes.
    battery,capsule = Q(3,5),Q(11,20)
    parts,bottles,fine,source_dense = battery*10,capsule*10,capsule*10,battery*15
    steel=parts+2*bottles
    blue=2*steel
    source=2*source_dense
    sand_powder=steel+source_dense+fine
    sand_crush=sand_powder/3
    buck_crush=fine
    a=[source,blue,buck_crush,sand_crush,blue,steel,Q(0),steel,source_dense,fine,
       bottles,parts,2*buck_crush,2*sand_crush,buck_crush,sand_crush,battery,capsule]
    # Encoding B: independent stoichiometric matrix + exact elimination.
    # Recipes follow rule snapshot order, including the recycling recipe.
    rec=[({'源矿':1},{'源石粉末':1}),({'蓝铁块':1},{'蓝铁粉末':1}),
         ({'荞花':1},{'荞花粉末':2}),({'砂叶':1},{'砂叶粉末':3}),
         ({'蓝铁矿':1},{'蓝铁块':1}),({'致密蓝铁粉末':1},{'钢块':1}),
         ({'蓝铁粉末':1},{'蓝铁块':1}),
         ({'蓝铁粉末':2,'砂叶粉末':1},{'致密蓝铁粉末':1}),
         ({'源石粉末':2,'砂叶粉末':1},{'致密源石粉末':1}),
         ({'荞花粉末':2,'砂叶粉末':1},{'细磨荞花粉末':1}),
         ({'钢块':2},{'钢质瓶':1}),({'钢块':1},{'钢制零件':1}),
         ({'荞花种子':1},{'荞花':1}),({'砂叶种子':1},{'砂叶':1}),
         ({'荞花':1},{'荞花种子':2}),({'砂叶':1},{'砂叶种子':2}),
         ({'钢制零件':10,'致密源石粉末':15},{'高容谷地电池':1}),
         ({'钢质瓶':10,'细磨荞花粉末':10},{'精选荞愈胶囊':1})]
    species=set().union(*(set(i)|set(o) for i,o in rec))-{'源矿','蓝铁矿'}
    rows,rhs=[],[]
    demand={'高容谷地电池':Q(3,5),'精选荞愈胶囊':Q(11,20)}
    for item in sorted(species):
        rows.append([o.get(item,0)-i.get(item,0) for i,o in rec])
        rhs.append(demand.get(item,0))
    rows.append([int(j==6) for j in range(len(rec))]); rhs.append(0)
    b=gaussian(rows,rhs,18)
    assert a == b
    rates={'粉碎机':sum(a[:4]),'精炼炉':sum(a[4:7]),'研磨机':sum(a[7:10]),
           '塑形机':a[10],'配件机':a[11],'种植机':sum(a[12:14]),'采种机':sum(a[14:16]),
           '封装机':5*a[16],'灌装机':5*a[17]}
    minimum={k:(v.numerator+v.denominator-1)//v.denominator for k,v in rates.items()}
    dedicated={'粉碎机':69,'精炼炉':51,'研磨机':32,'塑形机':6,'配件机':6,
               '种植机':34,'采种机':17,'封装机':3,'灌装机':3}
    minimum_area=sum(minimum[k]*(25 if k in ('种植机','采种机') else 24 if k in ('研磨机','封装机','灌装机') else 9)
                     for k in minimum)
    dedicated_area=sum(dedicated[k]*(25 if k in ('种植机','采种机') else 24 if k in ('研磨机','封装机','灌装机') else 9)
                       for k in dedicated)
    threshold_a=(Q(100)-Q(1,2)-Q(5,2)).numerator
    threshold_b=max(l for l in range(4901) if 200-1 >= 2*l+5)
    assert threshold_a == threshold_b == 97
    remaining_a=51+52+34+6+1
    remaining_b=sum(dedicated.values())-(17+17+32+5+3+3)
    assert remaining_a == remaining_b == 144
    # Before any planting, all sand production units are empty; the steel
    # chain cannot run. Wrongly sourced initial plants can only occupy the
    # first 52 mineral machines, the 18 source-ore crushers, the nine source
    # grinding machines and three packagers, plus transportation cells.
    # Every listed item represents at most one initial plant of either fixed
    # species. Ready/running batches are bounded by three input/output pieces.
    withdrawn_bound_a=52*50+18*(50+3)+9*(100+50+3)+3*100+2*70*70
    inventories=([50]*52+[53]*18+[153]*9+[100]*3+[2 for _ in range(4900)])
    withdrawn_bound_b=sum(inventories)
    assert withdrawn_bound_a == withdrawn_bound_b == 15031
    return dict(recipe_rates=[str(v) for v in b],blue_ore=str(blue),source_ore=str(source),
                total_ore=str(blue+source),minimum_machine_counts=minimum,
                minimum_machines=sum(minimum.values()),minimum_area=minimum_area,
                dedicated_machines=sum(dedicated.values()),dedicated_area=dedicated_area,
                remaining_machines=remaining_a,threshold_97_both_encodings=threshold_b,
                seeds_or_plants_for_sand_units=50*11,seeds_or_plants_for_buckwheat_units=50*6,
                max_initial_plant_or_seed_withdrawal_before_correction=withdrawn_bound_a,
                warehouse_stock_at_least=80000-withdrawn_bound_b,
                max_per_kind_startup_requirement_with_long_routes=50*11+2*70*70,
                counterexample_steps=3249,counterexample_ticks=str(Q(3249,8)),
                caveat='流量代数不是现行步进规则下的达标证明；97代数不证明存量引理')


def main():
    result={'receipt':audit_reception(),'layers':audit_layers(),'arithmetic':arithmetic()}
    (OUT/'lemmas_and_counts.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'receipt':result['receipt'],'layers':result['layers'],
                      'numbers':{k:result['arithmetic'][k] for k in ('total_ore','dedicated_machines','remaining_machines','threshold_97_both_encodings')}},ensure_ascii=False))


if __name__ == '__main__':
    main()
