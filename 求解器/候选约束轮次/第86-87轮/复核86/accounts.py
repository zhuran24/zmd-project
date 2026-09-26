"""Round 86: exact accounts, inventory enumeration; independently written.
Only reads the three designated snapshots. Standard library, one CPU.
"""
import hashlib
import itertools
import json
import math
import os
import re
from fractions import Fraction as F
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})


def recipes():
    lines = (BASE / '前提快照/《明日方舟：终末地》游戏规则.txt').read_text().splitlines()
    active = False
    machine = ''
    out = []
    for line in lines:
        line = line.strip()
        if line == '配方':
            active = True
        if not active or not line:
            continue
        if '→' not in line:
            machine = line
            continue
        left, right = line.split('→')
        product, duration = right.split('，')
        ins = {}
        for term in left.split('＋'):
            n, name = term.strip().split(' ', 1)
            ins[name] = int(n)
        n, name = product.strip().split(' ', 1)
        out.append(dict(machine=machine, inputs=ins, product=name,
                        quantity=int(n), duration=int(duration.split()[0])))
    return out


def solve(rows, rhs, n):
    a = [[F(x) for x in row] + [F(b)] for row, b in zip(rows, rhs)]
    pivots = []
    k = 0
    for col in range(n):
        pivot = next((i for i in range(k, len(a)) if a[i][col]), None)
        if pivot is None:
            continue
        a[k], a[pivot] = a[pivot], a[k]
        q = a[k][col]
        a[k] = [v/q for v in a[k]]
        for i in range(len(a)):
            if i != k and a[i][col]:
                q = a[i][col]
                a[i] = [v-q*w for v, w in zip(a[i], a[k])]
        pivots.append(col)
        k += 1
    assert all(any(row[:-1]) or not row[-1] for row in a)
    assert len(pivots) == n, (len(pivots), n)
    x = [F(0)]*n
    for i, p in enumerate(pivots):
        x[p] = a[i][-1]
    assert all(sum(F(z)*v for z, v in zip(row, x)) == b for row, b in zip(rows, rhs))
    return x


def stock_states(kinds, slots):
    yield {}
    for n in range(1, slots+1):
        for names in itertools.combinations(kinds, n):
            for counts in itertools.product(range(1, 51), repeat=n):
                yield dict(zip(names, counts))


def run():
    rec = recipes()
    items = sorted(set().union(*(set(r['inputs']) | {r['product']} for r in rec)))
    ores = ['蓝铁矿', '源矿']
    n = len(rec)+len(ores)
    rows, rhs = [], []
    for item in items:
        rows.append([r['quantity']*(r['product'] == item)-r['inputs'].get(item, 0)
                     for r in rec]+[int(item == ore) for ore in ores])
        rhs.append({'高容谷地电池': F(3, 5), '精选荞愈胶囊': F(11, 20)}.get(item, F(0)))
    recycle = next(i for i, r in enumerate(rec)
                   if r['machine'] == '精炼炉' and r['inputs'] == {'蓝铁粉末': 1})
    row = [0]*n
    row[recycle] = 1
    zero = solve(rows+[row], rhs+[0], n)
    one = solve(rows+[row], rhs+[1], n)
    machines = ['粉碎机', '精炼炉', '研磨机', '塑形机', '配件机', '种植机', '采种机', '封装机', '灌装机']
    work, increment = {}, {}
    for machine in machines:
        work[machine] = sum((zero[i]*r['duration'] for i, r in enumerate(rec) if r['machine'] == machine), F(0))
        increment[machine] = sum(((one[i]-zero[i])*r['duration'] for i, r in enumerate(rec) if r['machine'] == machine), F(0))
    counts = {m: math.ceil(work[m]) for m in machines}
    assert list(counts.values()) == [68,51,32,6,6,32,16,3,3]
    assert sum(counts.values()) == 217
    # Enumerate the fixed two-material sufficient condition, all legal stocks.
    pure = []
    for r in rec:
        if len(r['inputs']) != 2:
            continue
        checked = bad = 0
        for stock in stock_states(sorted(r['inputs']), 2):
            checked += 1
            refused = all(stock.get(i, 0) == 50 for i in r['inputs'])
            runnable = all(stock.get(i, 0) >= need for i, need in r['inputs'].items())
            bad += refused and not runnable
        pure.append(dict(machine=r['machine'], product=r['product'], states=checked, violations=bad))
        assert not bad
    # Entering two different primary powders from an unlocked legal stock.
    primaries = ['蓝铁粉末', '源石粉末', '荞花粉末']
    entered = []
    for first, second in itertools.permutations(primaries, 2):
        for q in range(1, 51):
            entered.append(dict(before={first:q}, incoming=second, after={first:q,second:1}))
    assert len(entered) == 300
    # Full skeleton account constructed from component families.
    skeleton = dict(zip(machines, [34+18+11+6,34+17,17+9+6,5+1,6,2*(11+6),11+6,3,3]))
    size = {m: 9 if m in machines[:2]+machines[3:5] else 25 if m in machines[5:7] else 24 for m in machines}
    body = sum(skeleton[m]*size[m] for m in machines)
    machine_inputs = sum([69,51,96,11,6,34,17,15,12])
    machine_outputs = sum([96,51,32,6,6,34,34,3,3])
    assert sum(skeleton.values()) == 221 and body == 3375
    assert machine_inputs+6 == machine_outputs+52 == 317
    files = ['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt']
    result = dict(
        hashes={f: hashlib.sha256((BASE/'前提快照'/f).read_bytes()).hexdigest() for f in files},
        candidate_sha256=hashlib.sha256((BASE/'修正版清单.json').read_bytes()).hexdigest(),
        recipes=rec, items=items,
        reaction_rates_at_r0=[str(v) for v in zero[:len(rec)]],
        rate_increment_per_r=[str(one[i]-zero[i]) for i in range(len(rec))],
        ore_rates=dict(zip(ores,map(str,zero[-2:]))),
        machine_work_at_r0={m:str(v) for m,v in work.items()},
        machine_work_increment={m:str(v) for m,v in increment.items()},
        machine_lower_bounds=counts, pure_inventory_checks=pure,
        two_primary_entry_count=len(entered),
        constants={'blocked_phi_extra':str(F(50+1+50+50+1)+F(49,2)),
                   'phi_lower_extra':str(F(50+1+50+50+1)+F(49,2)-F(1,2))},
        skeleton=dict(machines=skeleton,total_machines=sum(skeleton.values()),body_area=body,
                      input_ports=machine_inputs,output_ports=machine_outputs,paths=317,
                      battery_rate=str(F(3,5)),capsule_rate=str(F(2,5)+F(3,20))),
        cpu_affinity=sorted(os.sched_getaffinity(0)))
    (HERE/'accounts.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['machine_lower_bounds','pure_inventory_checks','constants','skeleton']},ensure_ascii=False))


if __name__ == '__main__':
    run()
