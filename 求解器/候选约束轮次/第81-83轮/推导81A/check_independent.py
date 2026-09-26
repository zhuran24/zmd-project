#!/usr/bin/env python3
"""独立复算：不导入主程序；公式、逐件扣料与直接状态递推分开实现。"""
import hashlib
import itertools as it
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})


def drain_pair(pair, recipe):
    value = list(pair)
    while all(value[i] >= recipe[i] for i in (0, 1)):
        for i in (0, 1):
            value[i] -= recipe[i]
    return value


def sequence_check(pair, recipe, runs):
    stock = drain_pair(pair, recipe)
    index = 0
    history = [[0, *stock]]
    for kind, count in runs:
        target = 'AB'.index(kind)
        for _ in range(count):
            if stock[target] >= 50:
                return index, index+1, stock, history
            stock[target] += 1
            stock = drain_pair(stock, recipe)
            index += 1
            history.append([index, *stock])
    return index, None, stock, history


def independent_graph(amount, subdivisions):
    # 不逐次结算端口动作：直接计算一时间步内取 j 件后是否容得下整批。
    initial = set()
    for count in range(50-amount, 51):
        for remaining in range(subdivisions+1):
            if remaining == 0 and count <= 50-amount:
                initial.add((count+amount, subdivisions, (0,)*amount))
            else:
                initial.add((count, remaining, (0,)*amount))
    reached = set(initial)
    frontier = initial
    transitions = 0
    bad = 0
    while frontier:
        later = set()
        for old_count, old_phase, old_clocks in frontier:
            phase = max(0, old_phase-1)
            clocks = [max(0, v-1) for v in old_clocks]
            free = sum(v == 0 for v in clocks)
            for sent in range(free+1):
                transfer = phase == 0 and old_count-sent <= 50-amount
                count = old_count-sent+amount*transfer
                if old_count < sent:
                    bad += 1
                    continue
                clock_counts = [0]*(subdivisions+1)
                for value in clocks:
                    clock_counts[value] += 1
                clock_counts[0] -= sent
                clock_counts[subdivisions] += sent
                new_clocks = tuple(v for v, n in enumerate(clock_counts) for _ in range(n))
                state = (count, subdivisions if transfer else phase, new_clocks)
                transitions += 1
                if state not in reached:
                    later.add(state)
        reached |= later
        frontier = later
    serial = [[q, p, list(c)] for q, p, c in sorted(reached)]
    digest = hashlib.sha256(json.dumps(serial, separators=(',', ':')).encode()).hexdigest()
    return dict(states=len(reached), edges=transitions, failed_withdrawals=bad,
                minimum_output=min(v[0] for v in reached), state_sha256=digest,
                state_list=serial)


def main():
    reference = json.loads((HERE/'primary_results.json').read_text())
    assert {(r['machine'],r['a'],r['b']) for r in reference['mixed_block_bounds']} == {
        ('研磨机',2,1),('封装机',10,15),('灌装机',10,10)}
    cert = json.loads((HERE/'buffer_certificate.json').read_text())
    geometry = json.loads((HERE/'finite_mixed_source.json').read_text())
    # 第二种几何编码：用边界线段的中点对接，不使用主程序的占格端口映射。
    ins, outs = [], []
    cells = []
    for unit in geometry['units']:
        x,y,w,h = unit['rect']
        for i in range(w):
            for j in range(h):
                assert (x+i,y+j) not in cells
                cells.append((x+i,y+j))
        for field, bucket in [('incoming',ins),('outgoing',outs)]:
            for side in unit[field]:
                if side in 'WE':
                    points = [(2*(x if side=='W' else x+w), 2*(y+j)+1) for j in range(h)]
                else:
                    points = [(2*(x+i)+1,2*(y if side=='S' else y+h)) for i in range(w)]
                bucket.extend((point,side,unit['id'],unit['kind']) for point in points)
    links = []
    for op, od, oi, ok in outs:
        for ip, idr, ii, ik in ins:
            if op==ip and {od,idr} in [{'E','W'},{'N','S'}]:
                if ok in ['传送带','分流器','汇流器'] or ik in ['传送带','分流器','汇流器']:
                    links.append([oi,ii])
    assert sorted(links) == geometry['channels']
    assert len(links) == 9
    pole = next(u['rect'] for u in geometry['units'] if u['kind']=='供电桩')
    machine = next(u['rect'] for u in geometry['units'] if u['id']=='待检机器')
    cx,cy = pole[0]+pole[2]/2, pole[1]+pole[3]/2
    intersects = (max(cx-6,machine[0]) < min(cx+6,machine[0]+machine[2]) and
                  max(cy-6,machine[1]) < min(cy+6,machine[1]+machine[3]))
    assert intersects and geometry['powered_machine']
    checked = 0
    for recipe in [(2, 1), (10, 15), (10, 10)]:
        a, b = recipe
        for initial in it.product(range(51), repeat=2):
            residual = drain_pair(initial, recipe)
            complete = min(initial[0]//a, initial[1]//b)
            assert residual == [initial[0]-a*complete, initial[1]-b*complete]
            checked += 1
    assert checked == reference['canonical_states_checked']
    for example in reference['exact_fifo_examples']:
        n, block, stock, trace = sequence_check(example['initial'], example['recipe'], example['word_runs'])
        assert (n, block, stock, trace) == (example['accepted'], example['blocked_item'], example['residual'], example['trace'])
        supplies = [v for _,v in example['word_runs']]
        assert 0 <= supplies[0]-1 <= 300 and 0 <= supplies[1]-2 <= 300
        assert min((x+s)//r for x,s,r in zip(example['initial'],supplies,example['recipe'])) <= 300

    bound_records = 0
    for row in reference['mixed_block_bounds']:
        a, b = row['a'], row['b']
        u, v = row['block_items']
        prefixes = {0}
        for positions in it.combinations(range(u+v), u):
            positions = set(positions)
            score = 0
            for j in range(u+v):
                score += b if j in positions else -a
                prefixes.add(score)
            assert score == 0
        one_line = {'完整小段起点': prefixes,
                    '任意小段内部起点': {last-first for first in prefixes for last in prefixes}}
        # 直接枚举两种永久满格缺料状态，求出安全开区间边界。
        bad_a = [50*b-a*other for other in range(b)]
        bad_b = [b*other-50*a for other in range(a)]
        low, high = max(bad_b), min(bad_a)
        assert [low, high] == row['safe_open']
        for cut, scores in one_line.items():
            combined = {0}
            for lanes in range(1, 7):
                combined = {s+t for s in combined for t in scores}
                values = [50*b-50*a+s for s in combined]
                target = next(v for v in row['bounds'] if v['cut']==cut and v['lines']==lanes)
                assert min(values) == target['z_min'] and max(values) == target['z_max']
                assert all(low < value < high for value in values) == target['certified']
                bound_records += 1

    box_cases = 0
    for head in range(1, 51):
        for codes in it.product(range(5), repeat=5):
            slots = [('砂叶', head)]
            for code in codes:
                slots.append((None, 0) if code == 0 else
                             ('高容谷地电池' if code <= 2 else '精选荞愈胶囊',
                              1 if code in (1, 3) else 50))
            room = {'砂叶': 0, '高容谷地电池': 80000, '精选荞愈胶囊': 80000, None: 0}
            output = []
            for item, count in slots:
                sent = min(count, room[item])
                room[item] -= sent
                remain = count-sent
                output.append((item, remain) if remain else (None, 0))
            assert output == [('砂叶', head)]+[(None, 0)]*5
            box_cases += 1
    assert box_cases == reference['box_recovery_states_checked']
    assert reference['normal_box_arrival_bound'] == sum(1 for port in range(3) for tick in range(6))
    safe_q = [q for q in range(51) if all(1 <= q+d <= 50 for d in range(-2, 3))]
    assert [min(safe_q), max(safe_q)] == reference['box_safe_q_with_delta_minus2_plus2']
    prepared = [old+25+delta for old in range(3) for delta in range(-2, 3)]
    assert [min(prepared), max(prepared)] == reference['box_add25_preparation_range']

    graph_summaries = []
    for graph in cert:
        independent = independent_graph(graph['batch'], graph['grid'])
        for key, value in independent.items():
            assert graph[key] == value, (graph['batch'], graph['grid'], key)
        assert independent['minimum_output'] >= 50-3*graph['batch']
        graph_summaries.append(dict(batch=graph['batch'], grid=graph['grid'],
                                    states=independent['states'], minimum_output=independent['minimum_output']))

    main_powders = ['蓝铁粉末','源石粉末','荞花粉末']
    dead_types = [p for p in it.combinations(main_powders, 2)]
    assert len(dead_types) == reference['grinding_double_main_pairs']
    dead_stocks = sum(1 for p in dead_types for x in range(1, 51) for y in range(1, 51))
    assert dead_stocks == reference['grinding_double_main_positive_count_states']
    batches = 17+9+11/2
    required = next(n for n in range(100) if n >= batches)
    assert required == reference['grinding_required_usable']
    counts = {'采种机':0, '种植机':0, '粉碎机':0}
    plant_rows = []
    for plant, full, powder_yield in [('荞花',5,2), ('砂叶',10,3)]:
        removals = []
        for tick in range(20):
            removals.append((full+(tick % 2 == 0))*powder_yield)
        powder = sum(removals)
        crushing = powder//powder_yield
        assert crushing*powder_yield == powder
        original = next(v for v in reference['plant_examples'] if v['plant']==plant)
        assert original['powder_per20']==powder and original['batches_per20']==crushing
        for machine, factor in [('采种机',1), ('种植机',2), ('粉碎机',1)]:
            counts[machine] += (full+1)*factor
        plant_rows.append({'plant':plant,'powder_per20':powder,'crushing_per20':crushing})
    assert counts == reference['plant_machine_counts']
    area = sum({'采种机':25,'种植机':25,'粉碎机':9}[key]*n for key,n in counts.items())
    assert area == reference['plant_manufacture_area']
    storage = sum((100+(2 if key=='采种机' else 1))*counts[key] for key in ['采种机','种植机'])
    assert storage == reference['closed_plant_storage_machine_part']
    assert reference['delivery_inequality_scale'] == 20
    assert reference['delivery_inequality_time_coefficients'] == [18*20//30, 165*20//300]

    output = dict(status='PASS', implementation='不导入主程序；逐批扣料、逐种前缀枚举、闭式状态转移',
                  finite_source_channels_checked=len(links),
                  canonical_states_checked=checked, mixed_bound_records=bound_records,
                  fifo_examples_checked=len(reference['exact_fifo_examples']),
                  box_recovery_states_checked=box_cases, buffer_graphs=graph_summaries,
                  grinding_dead_states=dead_stocks, plant_rows=plant_rows,
                  inputs_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in [HERE/'primary_results.json', HERE/'buffer_certificate.json']})
    (HERE/'independent_results.json').write_text(json.dumps(output, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
