#!/usr/bin/env python3
"""复核停止轴、旧探针及独立逐物种账；不把枚举拒收当作全部运行触发覆盖。"""
from collections import Counter
import json
import subprocess
from audit import HERE, SOLVER, KERNEL, BIN, CONFIG, load, write, digest


def totals(state):
    result = Counter()
    for slot in state['warehouse']['slots']:
        if slot['item'] is not None:
            result[slot['item']] += int(slot['quantity']['value'])
    for slot in state['inventory']:
        for row in slot['contents']:
            result[row['item']] += int(row['quantity']['value'])
    return +result


def main():
    axes = load(CONFIG)['axes']
    stops = []
    for axis, row in axes.items():
        if row['disposition'] != '超出覆盖即停':
            continue
        command = [str(BIN), 'request', axis, '--config', str(CONFIG)]
        process = subprocess.run(command, capture_output=True, text=True, timeout=15)
        record = json.loads(process.stdout)
        assert process.returncode == 2 and axis in record['open_items'][0]
        stops.append({'axis': axis, 'status': record['status'], 'exit_code': process.returncode, 'open_items': record['open_items'], 'coverage': '显式请求接口，非游戏事件触发'})
    assert len(stops) == 18
    replay = []
    for old in load(KERNEL / 'evidence/revision-r1/review-probe-replay.json')['cases']:
        source = __import__('pathlib').Path(old['input'])
        assert digest(source) == old['input_sha256']
        ticks = old['completed_instants'] if old['status'] == 'completed' else 4
        output = HERE / ('replay-' + source.stem + '.json')
        command = [str(BIN), 'run', str(source), '--config', str(CONFIG), '--ticks', str(ticks), '--out', str(output)]
        process = subprocess.run(command, capture_output=True, text=True, timeout=30)
        record = load(output)
        length = len(record['trace']['ticks']) if record['trace'] else 0
        assert (record['status'], process.returncode, length) == (old['status'], old['exit_code'], old['completed_instants'])
        if 'output_blocked' in old:
            assert next(r for r in record['uncovered_axes'] if r['axis'] == 'manufacturing.output_blocked') == old['output_blocked']
        replay.append({'input': str(source), 'command': command, 'status': record['status'], 'exit_code': process.returncode, 'completed_instants': length, 'open_items': record['open_items']})
    # 配方数据只读取正式目录，不调用内核的inventory_totals。
    catalog = load(SOLVER / '数据/正式静态目录.json')
    recipes = {r['id']: r for r in catalog['recipes']}
    invariant = []
    for name in ('混做粉碎机两下游', '分流器三路轮询'):
        record = load(SOLVER / f'数据/样例/{name}-运行记录-kernel.json')
        previous = record['trace']['start_state']
        expected = totals(previous)
        assert expected['源矿'] == expected['蓝铁矿'] == 80000
        for tick in record['trace']['ticks']:
            for event in tick['events']:
                if event['operation'] == 'manufacture_complete':
                    recipe_id = next(p for p in previous['progress'] if p['unit'] == event['target'])['recipe']
                    recipe = recipes[recipe_id]
                    for key, sign in [('inputs', -1), ('outputs', 1)]:
                        for item, quantity in recipe[key].items():
                            expected[item] += sign * int(quantity['value'])
            expected = +expected
            assert totals(tick['state']) == expected
            context = tick['state']['semantic_context']['tick_context']['value']
            # 直接由成功移动事件复算每个端口一次预算。
            ports = Counter()
            for event in tick['events']:
                if event['operation'] == 'move' and event['outcome'] == 'success':
                    _, source, target = event['target'].split('|')
                    ports[source] += 1; ports[target] += 1
            assert all(n <= 1 for n in ports.values())
            invariant.append({'sample': name, 'time': tick['time'], 'species_totals': dict(expected), 'port_usage': dict(ports), 'status': '通过'})
            previous = tick['state']
    write('stops-and-invariants.json', {'request_stops': stops, 'old_probes': replay, 'independent_inventory': invariant})
    print(json.dumps({'request_stops': len(stops), 'old_probes': len(replay), 'independent_inventory_ticks': len(invariant)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
