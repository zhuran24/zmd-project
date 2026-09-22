"""复核指定四时刻前缀；不导入被审执行器，不作一般内核。"""
import copy
import hashlib
import json
from fractions import Fraction
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE / '被审快照'
SAMPLES = ROOT / '求解器/数据/样例'


def read(path):
    return json.loads(path.read_text())


def number(value):
    return Fraction(value['value'])


def instant(value):
    return number(value['value'])


def geometry(data, catalog):
    # 各旋转直接用闭式坐标，独立于被审几何函数。
    kinds = {row['id']: row for row in catalog['units']}
    ports, occupied = {}, set()
    normals = {'south': (0, -1), 'north': (0, 1), 'west': (-1, 0), 'east': (1, 0)}
    for unit in data['layout']['units']:
        kind = kinds[unit['kind']]
        width, height = (int(number(kind['dimensions'][key])) for key in ('width', 'height'))
        ox, oy = map(number, unit['origin'])
        turns = int(unit['rotation'][1:]) // 90
        transform = (
            lambda x, y: (x, y), lambda x, y: (height - 1 - y, x),
            lambda x, y: (width - 1 - x, height - 1 - y), lambda x, y: (y, width - 1 - x)
        )[turns]
        cells = {(ox + transform(x, y)[0], oy + transform(x, y)[1]) for x in range(width) for y in range(height)}
        assert not occupied & cells
        assert all(0 <= x < 70 and 0 <= y < 70 for x, y in cells)
        occupied |= cells
        if unit['kind'] == '桥接器':
            edges = {edge['side']: edge for variant in kind['ports']['layouts'] for edge in variant}.values()
        else:
            edges = kind['ports']['layouts'][unit['port_layout']]
        for edge in edges:
            side = edge['side']
            role = edge['role']
            if unit['kind'] == '桥接器':
                axis = unit['bridge_axes'][edge['axis']]
                assert axis['status'] == 'resolved'
                role = 'input' if side == axis['input_side'] else 'output'
            for value in edge['positions']:
                position = int(number(value))
                x, y = {'south': (position, 0), 'north': (position, height - 1),
                        'west': (0, position), 'east': (width - 1, position)}[side]
                x, y = transform(x, y)
                dx, dy = normals[side]
                dx, dy = ((dx, dy), (-dy, dx), (-dx, -dy), (dy, -dx))[turns]
                ports[f"{unit['id']}:{side}:{position}"] = ((ox + x, oy + y), (dx, dy), role, kind['family'])
    channels = set()
    for source, (cell, normal, role, family) in ports.items():
        if role != 'output':
            continue
        face = (cell[0] + normal[0], cell[1] + normal[1])
        for target, (other, inward, other_role, other_family) in ports.items():
            if other == face and inward == (-normal[0], -normal[1]) and other_role == 'input' and 'transport' in (family, other_family):
                channels.add(f'PC|{source}|{target}')
    assert channels == {row['id'] for row in data['layout']['physical_channels']}
    return {'units': len(data['layout']['units']), 'occupied_cells': len(occupied), 'physical_channels': len(channels)}


def verify_prefix(data, output):
    # 以下硬限定为本例：唯一源矿配方，两个下游在区间内均未进料。
    seed = data['initial_state']['nonwarehouse']['value']
    assert all(not row['contents'] for row in seed['inventory'])
    stock = {row['slot']: [] for row in seed['inventory']}
    units = {row['id']: row['kind'] for row in data['layout']['units']}
    channels = {row['id']: row for row in data['layout']['physical_channels']}
    parameters = {key: value['value'] for group in ('fixed', 'offline_mutable', 'fixedness_unproven') for key, value in data['parameters'][group].items()}
    order = parameters['judgment.order']['template_order']
    memory = copy.deepcopy(seed['logistics']['poll_memory']['value'])
    sides = {(row['unit'], row['side']): row for row in memory['sides']}
    assignments = {row['port']: row['slot'] for row in data['settings']['warehouse_assignments']}
    warehouse = {row['slot']: [row['item'], int(number(row['quantity']))] for row in seed['warehouse']['slots']}
    phase, due, completed = 'idle', None, 0
    results = []

    def physical(channel, time, used):
        source, target = channel['source_port'], channel['target_port']
        su, tu = source.split(':')[0], target.split(':')[0]
        if units[su] in ('协议核心', '仓库取货口'):
            slot = assignments[source]
            contents = [[warehouse[slot][0], warehouse[slot][1], None]]
        else:
            slot = su + (':transport:0' if units[su] == '传送带' else ':output:0')
            contents = stock[slot]
        if not contents or contents[0][1] == 0:
            return None
        item, _, entered = contents[0]
        if units[tu] == '传送带':
            destination, capacity = tu + ':transport:0', 1
        else:
            if any(row[0] == item for row in stock[tu + ':output:0']):
                return None
            inputs = [key for key in stock if key.startswith(tu + ':input:')]
            same = [key for key in inputs if stock[key] and stock[key][0][0] == item]
            empty = [key for key in inputs if not stock[key]]
            if not same + empty:
                return None
            destination, capacity = (same + empty)[0], 50
        existing = stock[destination]
        if existing and (existing[0][0] != item or sum(row[1] for row in existing) >= capacity):
            return None
        if units[su] == '传送带' and time - entered < 1:
            return None
        if source in used or target in used:
            return None
        return slot, destination, item

    def refresh(time, used):
        for side in sides.values():
            levels = side['levels']
            assert len(levels) <= 1
            side['current_level'] = levels[0]['id'] if levels and (not side['graded'] or any(physical(channels[c], time, used) for c in levels[0]['members'])) else None

    def permission(side, cid, time, used):
        if side['current_level'] is None:
            return False
        level = side['levels'][0]
        members = level['members']
        index = members.index(level['next_channel'])
        ordered = members[index:] + members[:index]
        if side['graded']:
            ordered = [c for c in ordered if physical(channels[c], time, used)]
        return bool(ordered) and ordered[0] == cid

    def advance(side, cid):
        level = side['levels'][0]
        members = level['members']
        level['next_channel'] = members[(members.index(cid) + 1) % len(members)]

    for time, tick in enumerate(output['trace']['ticks']):
        assert instant(tick['time']) == time
        used, moves, internal = set(), [], []
        events = tick['events']
        if due == time:
            first, events = events[0], events[1:]
            assert first['event'] == f'C|{time}|crusher' and first['operation'] == 'manufacture_complete'
            assert phase == 'working' and stock['crusher:buffer:0'] == [['源矿', 1, time - 1]]
            stock['crusher:buffer:0'] = [['源石粉末', 1, time]]
            phase, due, completed = 'completed', None, completed + 1
        assert len(events) % len(order) == 0
        seen = set()
        for index, event in enumerate(events):
            sweep, rank = divmod(index, len(order))
            if rank == 0:
                refresh(time, used)
                boundary = json.dumps([stock, phase, due, memory, sorted(used)], sort_keys=True, ensure_ascii=False)
                assert boundary not in seen
                seen.add(boundary)
            assert event['event'] == f'J|{time}|{sweep}|{rank}'
            template = order[rank]
            assert (event['operation'], event['target']) == (template['operation'], template['target'])
            if event['operation'] == 'move':
                channel = channels[event['target']]
                refresh(time, used)
                left = sides[channel['source_port'].split(':')[0], 'output']
                right = sides[channel['target_port'].split(':')[0], 'input']
                lp, rp = (permission(side, event['target'], time, used) for side in (left, right))
                route = physical(channel, time, used)
                expected = 'no_request' if not (lp or rp) else 'success' if route and lp and rp else 'failure'
                assert event['outcome'] == expected, event['event']
                if expected == 'success':
                    source, target, item = route
                    if source in warehouse:
                        warehouse[source][1] -= 1
                    else:
                        stock[source][0][1] -= 1
                        if stock[source][0][1] == 0:
                            stock[source] = []
                    if stock[target]:
                        stock[target][0][1] += 1
                    else:
                        stock[target] = [[item, 1, time]]
                    used.update((channel['source_port'], channel['target_port']))
                    moves.append(event['event'])
                if lp:
                    advance(left, event['target'])
                if rp:
                    advance(right, event['target'])
            else:
                assert event['operation'] == 'manufacture'
                if event['target'] != 'crusher':
                    assert not any(contents for slot, contents in stock.items() if slot.startswith(event['target'] + ':'))
                    assert event['outcome'] == 'guard_false'
                    continue
                changed = False
                if phase == 'completed':
                    assert not stock['crusher:output:0']
                    stock['crusher:output:0'] = stock['crusher:buffer:0']
                    stock['crusher:buffer:0'] = []
                    phase, changed = 'idle', True
                    internal.append((event['event'], 'output'))
                if phase == 'idle' and stock['crusher:input:0']:
                    assert stock['crusher:input:0'] == [['源矿', 1, time]]
                    stock['crusher:buffer:0'] = stock['crusher:input:0']
                    stock['crusher:input:0'] = []
                    phase, due, changed = 'working', time + 1, True
                    internal.append((event['event'], 'input'))
                assert event['outcome'] == ('success' if changed else 'guard_false')
        refresh(time, used)
        boundary = json.dumps([stock, phase, due, memory, sorted(used)], sort_keys=True, ensure_ascii=False)
        assert boundary in seen
        assert tick['closure']['scan_rounds'] == len(events) // len(order)
        state = tick['state']
        stored = {row['slot']: [[x['item'], int(number(x['quantity'])), instant(x['entered_at'])] for x in row['contents']] for row in state['inventory']}
        assert stock == stored
        assert {row['slot']: [row['item'], int(number(row['quantity']))] for row in state['warehouse']['slots']} == warehouse
        assert state['logistics']['poll_memory']['value'] == memory
        context = state['semantic_context']['tick_context']['value']
        assert moves == [row['event'] for row in context['movements']]
        assert used == {row['port'] for row in context['port_usage']}
        assert all(number(row['quantity']) == 1 for row in context['port_usage'])
        assert internal == [(row['event'], row['batch'].rsplit('|', 1)[1]) for row in context['internal_passages']]
        crusher = next(row for row in state['progress'] if row['unit'] == 'crusher')
        assert crusher['phase'] == phase and (crusher['remaining'] is None if due is None else instant(crusher['remaining']) == due - time)
        for progress in state['progress']:
            if progress['unit'] != 'crusher':
                assert progress['phase'] == 'idle' and progress['recipe'] is None
        assert int(tick['summary']['completed_batches']) == completed
        assert int(tick['summary']['warehouse_ore']) == 79999 - time
        results.append({'time': time, 'events_verified': len(tick['events']), 'successful_moves': moves, 'internal_passages': internal, 'completed_batches': completed})
    return results


def main():
    catalog = read(ROOT / '求解器/数据/正式静态目录.json')
    samples = {name: read(SAMPLES / (name + '.json')) for name in ('桥接器双通路', '分流器三路轮询', '混做粉碎机两下游')}
    result = {'geometry': {name: geometry(data, catalog) for name, data in samples.items()}}
    result['prefix'] = verify_prefix(samples['混做粉碎机两下游'], read(SAMPLES / '混做粉碎机两下游-运行记录.json'))
    result['status'] = '通过'
    result['scope'] = '独立核指定156条记录的守卫、权限、后效、闭包、库存和端口账；不是通用执行器或全称证明。'
    (BASE / '独立核算结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
