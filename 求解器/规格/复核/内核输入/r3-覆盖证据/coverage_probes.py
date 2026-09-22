#!/usr/bin/env python3
"""独立几何复算与真实参考执行中途状态取证；不修改原产物。"""
import copy
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
EXAMPLES = ROOT / '求解器/数据/样例'
sys.dont_write_bytecode = True
sys.path.insert(0, str(EXAMPLES))
import check_golden_trace as golden


def load(path):
    return json.loads(path.read_text())


def geometry(data, catalog):
    kinds = {u['id']: u for u in catalog['units']}
    occupied, ports, internal = set(), {}, set()
    for unit in data['layout']['units']:
        kind = kinds[unit['kind']]
        uid = unit['id']
        w, h = (int(kind['dimensions'][k]['value']) for k in ('width', 'height'))
        ox, oy = (int(q['value']) for q in unit['origin'])
        turn = ('r0', 'r90', 'r180', 'r270').index(unit['rotation'])
        def rotate(x, y):
            return [(x, y), (h-1-y, x), (w-1-x, h-1-y), (y, w-1-x)][turn]
        cells = {(ox+rotate(x, y)[0], oy+rotate(x, y)[1]) for x in range(w) for y in range(h)}
        assert not occupied & cells
        assert all(0 <= x < 70 and 0 <= y < 70 for x, y in cells)
        occupied |= cells
        if unit['kind'] == '桥接器':
            edges = {e['side']: copy.deepcopy(e) for layout in kind['ports']['layouts'] for e in layout}
            for side, edge in edges.items():
                axis = 'vertical' if side in ('south', 'north') else 'horizontal'
                state = unit['bridge_axes'][axis]
                assert state['status'] == 'resolved'
                edge['role'] = 'input' if side == state['input_side'] else 'output'
            edges = list(edges.values())
        else:
            edges = kind['ports']['layouts'][unit['port_layout']]
        for edge in edges:
            side = edge['side']
            dx, dy = {'south': (0, -1), 'north': (0, 1), 'west': (-1, 0), 'east': (1, 0)}[side]
            normal = [(dx, dy), (-dy, dx), (-dx, -dy), (dy, -dx)][turn]
            for quantity in edge['positions']:
                p = int(quantity['value'])
                x, y = {'south': (p, 0), 'north': (p, h-1), 'west': (0, p), 'east': (w-1, p)}[side]
                x, y = rotate(x, y)
                ports[f'{uid}:{side}:{p}'] = (ox+x, oy+y, *normal, edge['role'], kind['family'])
        if kind['family'] == 'manufacturing':
            for row in kind['inventory']:
                if row['role'] not in ('input', 'output'):
                    continue
                for i in range(int(row['count']['value'])):
                    slot, buffer = f"{uid}:{row['role']}:{i}", f'{uid}:buffer:0'
                    a, b = (slot, buffer) if row['role'] == 'input' else (buffer, slot)
                    internal.add(f'BC|{a}|{b}')
    external = set()
    for source, a in ports.items():
        for target, b in ports.items():
            if a[4] == 'output' and b[4] == 'input' and 'transport' in (a[5], b[5]) and (a[0]+a[2], a[1]+a[3]) == b[:2] and (a[2], a[3]) == (-b[2], -b[3]):
                external.add(f'PC|{source}|{target}')
    assert external == {c['id'] for c in data['layout']['physical_channels']}
    assert internal == {c['id'] for c in data['layout']['buffer_channels']}
    return {'name': data['scenario']['name'], 'units': len(data['layout']['units']), 'occupied_cells': len(occupied), 'ports': len(ports), 'PC': len(external), 'BC': len(internal)}


def main():
    catalog = load(EXAMPLES.parent / '正式静态目录.json')
    names = ['桥接器双通路', '分流器三路轮询', '混做粉碎机两下游']
    geometries = [geometry(load(EXAMPLES / (name + '.json')), catalog) for name in names]
    source = Path(golden.__file__).resolve()
    line = next(i for i, text in enumerate(source.read_text().splitlines(), 1) if "records.append({'event':event,'operation':operation" in text)
    captured = []
    def trace(frame, event, arg):
        if event == 'line' and Path(frame.f_code.co_filename).resolve() == source and frame.f_lineno == line:
            values = frame.f_locals
            if values.get('event') == 'J|2|0|1':
                captured.append(copy.deepcopy({
                    'event': values['event'], 'outcome': values['outcome'],
                    'time': values['t'], 'round': values['rounds'], 'next_template': values['i']+1,
                    'inventory': values['state']['inventory'], 'progress': values['state']['progress'],
                    'poll_memory': values['state']['logistics']['poll_memory'],
                    'movements': values['movements'], 'port_usage': values['usage'],
                    'completed_events': values['records'],
                }))
        return trace
    try:
        sys.settrace(trace)
        golden.run(load(golden.INPUT))
    finally:
        sys.settrace(None)
    assert len(captured) == 1
    snap = captured[0]
    p = next(row for row in snap['progress'] if row['unit'] == 'crusher')
    assert p['phase'] == 'completed'
    assert next(row for row in snap['inventory'] if row['slot'] == 'crusher:input:0')['contents'][0]['item'] == '源矿'
    assert next(row for row in snap['inventory'] if row['slot'] == 'crusher:buffer:0')['contents'][0]['item'] == '源石粉末'
    result = {
        'independent_geometry': geometries,
        'mid_closure': snap,
        'mid_closure_scope': '原参考执行的实际瞬时物理投影；把空调试期结束标签移至此处是报告中的另一历史条件，不是玩家精确控制策略，也不是完整新输入文件。',
        'source': {'path': str(source), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'capture_line': line},
        'event_order_periodic_witness': {
            'rule': '两个互不相连的空箱每5 tick各做一次单位传输判定；时刻5k，偶数k先A后B，奇数k先B后A。',
            'prefix': [{'time': 5*k, 'order': ['A', 'B'] if k % 2 == 0 else ['B', 'A']} for k in range(8)],
            'scope': '有限前缀可列instant_overrides；完整周期函数在event-order-v1中无编码，未声称该布局达标。'
        }
    }
    (HERE / '覆盖反例证据.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'geometry': geometries, 'captured': snap['event'], 'phase': p['phase']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
