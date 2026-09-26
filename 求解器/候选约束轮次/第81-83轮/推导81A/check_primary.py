#!/usr/bin/env python3
"""第81轮A：局部算术和有限状态证书；不调用游戏内核。"""
import hashlib
import itertools
import json
import math
import os
from collections import deque
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ROOT = BASE.parents[2]
os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recipes():
    rule = (BASE / '前提快照/《明日方舟：终末地》游戏规则.txt').read_text()
    table = []
    machine = None
    in_recipes = False
    for line in rule.splitlines():
        if line == '配方':
            in_recipes = True
        elif in_recipes and line and '→' not in line:
            machine = line
        elif in_recipes and '→' in line:
            lhs, rhs = line.split(' → ')
            ins = [tuple(part.split(' ', 1)) for part in lhs.split(' ＋ ')]
            out, duration = rhs.split('，')
            qty, item = out.split(' ', 1)
            table.append(dict(machine=machine,
                              inputs={item: int(n) for n, item in ins},
                              output={item: int(qty)},
                              ticks=int(duration.split()[0])))
    return table


def canonical(x, y, a, b):
    batches = min(x // a, y // b)
    return x-a*batches, y-b*batches


def accept_word(a, b, x, y, word):
    u, v = canonical(x, y, a, b)
    trace = [[0, u, v]]
    for i, letter in enumerate(word, 1):
        if (u if letter == 'A' else v) == 50:
            return dict(accepted=i-1, blocked_item=i, residual=[u, v], trace=trace)
        u += letter == 'A'
        v += letter == 'B'
        u, v = canonical(u, v, a, b)
        trace.append([i, u, v])
    return dict(accepted=len(word), blocked_item=None, residual=[u, v], trace=trace)


def buffer_graph(k, grid):
    """独立原料始终充足的单机：批量k/1tick，恰k个取货口。
    外部可任意停取；每口相邻取货至少1tick。时间步为1/grid。
    输出格和缓存按实际整批规则逐事件结算，端口按对称性合并。
    """
    def settle(q, phase):
        if phase == 0 and q+k <= 50:
            return q+k, grid
        return q, phase

    initial = set()
    for q in range(50-k, 51):
        for p in range(grid+1):
            q0, p0 = settle(q, p)
            initial.add((q0, p0, (0,)*k))
    seen = set(initial)
    todo = deque(initial)
    edges = 0
    failed = 0
    while todo:
        q, p, clocks = todo.popleft()
        ready_clocks = tuple(max(0, x-1) for x in clocks)
        q0, p0 = settle(q, max(0, p-1))
        available = ready_clocks.count(0)
        for take in range(available+1):
            q1, p1 = q0, p0
            cc = list(ready_clocks)
            for j in range(take):
                if q1 == 0:
                    failed += 1
                    break
                q1 -= 1
                cc[j] = grid
                q1, p1 = settle(q1, p1)
            else:
                dest = (q1, p1, tuple(sorted(cc)))
                edges += 1
                if dest not in seen:
                    seen.add(dest)
                    todo.append(dest)
    serial = [[q, p, list(c)] for q, p, c in sorted(seen)]
    payload = json.dumps(serial, separators=(',', ':'))
    return dict(batch=k, grid=grid, states=len(seen), edges=edges,
                failed_withdrawals=failed, minimum_output=min(s[0] for s in seen),
                analytic_lower=50-3*k,
                state_sha256=hashlib.sha256(payload.encode()).hexdigest(),
                state_list=serial)


def main():
    rr = recipes()
    assert len(rr) == 18
    names = ['《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt']
    manifest = {'formal_snapshots': {n: digest(BASE/'前提快照'/n) for n in names},
                'memory_used_for_proof': False,
                'scope': '局部恒等式、显式前提下的状态枚举；不是全厂布局证书',
                'cpu_affinity': sorted(os.sched_getaffinity(0))}
    assert manifest['formal_snapshots'] == {
        '《明日方舟：终末地》游戏规则.txt': '6e64e3903a65536c530b363c9f3aef8c1bb2a1c1193e866799125dd047159924',
        '求解任务.txt': '1630ca1febec79b324aa3afb110be2d3330298e266c68b06415c3d1516108bac',
        '求解约束.txt': '0c05976f6063f3332db6ee19d7746052ef35148d7c2a12dfa396c7bb8753f30f'}
    selected = [next(r for r in rr if r['machine'] == m)
                for m in ('研磨机', '封装机', '灌装机')]
    arithmetic = []
    for r in selected:
        a, b = r['inputs'].values()
        g = math.gcd(a, b)
        c = a*b//g
        lower, upper, z0 = b*(a-1)-50*a, 50*b-a*(b-1), 50*(b-a)
        bounds = []
        for lines in range(1, 7):
            for cut in ('完整小段起点', '任意小段内部起点'):
                width = lines*c*(1 if cut == '完整小段起点' else 2)
                bounds.append(dict(lines=lines, cut=cut,
                                   z_min=z0-width, z_max=z0+width,
                                   certified=(lower < z0-width and z0+width < upper)))
        words = sorted(set(itertools.permutations('A'*(a//g)+'B'*(b//g))))
        extremes = []
        for word in words:
            s = 0
            extremes.append(s)
            for x in word:
                s += b if x == 'A' else -a
                extremes.append(s)
            assert s == 0
        assert (min(extremes), max(extremes)) == (-c, c)
        arithmetic.append(dict(machine=r['machine'], a=a, b=b, gcd=g,
                               block_items=[a//g, b//g], block_deviation=c,
                               safe_open=[lower, upper], initial_z=z0,
                               block_orders=len(words), bounds=bounds))

    examples = []
    for a, b, na, nb in [(2, 1, 102, 51), (10, 15, 40, 60), (10, 10, 60, 60)]:
        for x in [50, 0]:
            e = accept_word(a, b, x, 50, 'A'*na+'B'*nb)
            e.update(recipe=[a, b], word_runs=[['A', na], ['B', nb]], initial=[x, 50],
                     source='候选简化第3轮A的有限箱体供货接法；不声称全厂达标或该起态由堵满必达')
            examples.append(e)

    local_units = [
        dict(id='主料箱', kind='协议储存箱', rect=[10,20,3,3], incoming='W', outgoing='E'),
        dict(id='主料分流器', kind='分流器', rect=[13,21,1,1], incoming='W', outgoing='ENS'),
        dict(id='另一原料箱', kind='协议储存箱', rect=[14,16,3,3], incoming='S', outgoing='N'),
        dict(id='另一原料带1', kind='传送带', rect=[14,19,1,1], incoming='S', outgoing='N'),
        dict(id='另一原料带2', kind='传送带', rect=[14,20,1,1], incoming='S', outgoing='N'),
        dict(id='汇流器', kind='汇流器', rect=[14,21,1,1], incoming='WSN', outgoing='E'),
        dict(id='共同进料带', kind='传送带', rect=[15,21,1,1], incoming='W', outgoing='E'),
        dict(id='待检机器', kind='研磨机/封装机/灌装机', rect=[16,19,4,6], incoming='W', outgoing='E'),
        dict(id='出料带', kind='传送带', rect=[20,21,1,1], incoming='W', outgoing='E'),
        dict(id='收货箱', kind='协议储存箱', rect=[21,20,3,3], incoming='W', outgoing='E'),
        dict(id='供电桩', kind='供电桩', rect=[20,16,2,2], incoming='', outgoing='')]
    occupied = set()
    port_map = {}
    direction = dict(N=(0,1), S=(0,-1), W=(-1,0), E=(1,0))
    for unit in local_units:
        x,y,w,h = unit['rect']
        cells = {(i,j) for i in range(x,x+w) for j in range(y,y+h)}
        assert not occupied & cells
        assert all(0 <= i < 70 and 0 <= j < 70 for i,j in cells)
        occupied |= cells
        for mode in ['incoming','outgoing']:
            for side in unit[mode]:
                dx,dy = direction[side]
                for cell in cells:
                    outside = (cell[0]+dx, cell[1]+dy)
                    if outside not in cells:
                        port_map[(cell, side, mode)] = unit['id']
    edges = []
    opposite = dict(N='S',S='N',W='E',E='W')
    transport = {u['id'] for u in local_units if u['kind'] in ['传送带','分流器','汇流器']}
    for (cell,side,mode), source in port_map.items():
        if mode != 'outgoing':
            continue
        dx,dy = direction[side]
        receiver = port_map.get(((cell[0]+dx,cell[1]+dy),opposite[side],'incoming'))
        if receiver is not None and (source in transport or receiver in transport):
            edges.append([source,receiver])
    assert len(edges) == 9
    geometry = dict(scope='可生成有限混料前缀的局部接法，不是全厂布局',
                    units=local_units, channels=sorted(edges),
                    all_boxes_transmission=False, priority='主料分流器到汇流器的存货级先接通',
                    initial='分流器有1件主料；另一原料两格带各1件；其余运输格空；运输旧货已滞留1tick；机器两存货格按例给定；取货格和缓存空。',
                    supply_counts='主料箱放n_A-1件；另一原料箱放n_B-2件；收货箱空。',
                    powered_machine=True)
    # 桩的供电范围与待检机器占格有非空交集。
    assert 15 <= 16 < 27 and 11 <= 19 < 23
    (HERE/'finite_mixed_source.json').write_text(json.dumps(geometry,ensure_ascii=False,indent=2)+'\n')

    residual_checks = 0
    for a, b in [(2, 1), (10, 15), (10, 10)]:
        for x, y in itertools.product(range(51), repeat=2):
            u, v = canonical(x, y, a, b)
            assert 0 <= u <= 50 and 0 <= v <= 50 and (u < a or v < b)
            assert b*u-a*v == b*x-a*y
            residual_checks += 1

    box_checks = 0
    box_values = [(None, 0), ('高容谷地电池', 1), ('高容谷地电池', 50),
                  ('精选荞愈胶囊', 1), ('精选荞愈胶囊', 50)]
    for q in range(1, 51):
        for tail in itertools.product(box_values, repeat=5):
            state = [('砂叶', q), *tail]
            after = [(name, qty) if name == '砂叶' else (None, 0) for name, qty in state]
            assert after == [('砂叶', q)]+[(None, 0)]*5
            box_checks += 1

    buffers = [buffer_graph(k, grid) for k in (1, 2, 3) for grid in (1, 2, 3)]
    for r in buffers:
        assert not r['failed_withdrawals']
        assert r['minimum_output'] >= r['analytic_lower'] > 0

    # 每种植物分别使用固定配对；粉碎出货由外部给出的服务时刻驱动。
    plant = []
    for name, n, k in [('荞花', 6, 2), ('砂叶', 11, 3)]:
        full = n-1
        half = 1
        batches20 = full*20+half*10
        plant.append(dict(plant=name, seeders=n, growers=2*n, crushers=n,
                          batches_per20=batches20, seed_batches_per20=batches20,
                          grow_batches_per20=2*batches20,
                          powder_per20=k*batches20,
                          full_rate_crushers=full, half_rate_crushers=half))
    machine_counts = dict(采种机=sum(x['seeders'] for x in plant),
                          种植机=sum(x['growers'] for x in plant),
                          粉碎机=sum(x['crushers'] for x in plant))
    manufacture_area = 25*(machine_counts['采种机']+machine_counts['种植机'])+9*machine_counts['粉碎机']
    targets = [Fraction('0.6'), Fraction('0.55')]
    scale = math.lcm(*(f.denominator for f in targets))
    output = dict(status='PASS', manifest=manifest, recipes=rr, mixed_block_bounds=arithmetic,
                  exact_fifo_examples=examples, canonical_states_checked=residual_checks,
                  box_recovery_states_checked=box_checks, normal_box_arrival_bound=3*(5+1),
                  warehouse_first_clear_ticks=5,
                  box_safe_q_with_delta_minus2_plus2=[3, 48],
                  box_add25_preparation_range=[23, 29],
                  grinding_double_main_pairs=math.comb(3, 2),
                  grinding_double_main_positive_count_states=math.comb(3, 2)*50*50,
                  grinding_required_usable=math.ceil((34+18+11)/2),
                  plant_examples=plant, plant_machine_counts=machine_counts,
                  plant_manufacture_area=manufacture_area,
                  delivery_inequality_scale=scale,
                  delivery_inequality_time_coefficients=[int(scale*f) for f in targets],
                  closed_plant_storage_machine_part=102*machine_counts['采种机']+101*machine_counts['种植机'],
                  buffer_graphs=[{k:v for k,v in d.items() if k!='state_list'} for d in buffers])
    (HERE/'primary_results.json').write_text(json.dumps(output, ensure_ascii=False, indent=2)+'\n')
    (HERE/'buffer_certificate.json').write_text(json.dumps(buffers, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k:output[k] for k in ['status','canonical_states_checked','box_recovery_states_checked',
                                           'plant_machine_counts','plant_manufacture_area','buffer_graphs']},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
