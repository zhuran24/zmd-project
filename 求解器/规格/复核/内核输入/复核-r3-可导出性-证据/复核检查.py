#!/usr/bin/env python3
"""可导出性复核：只读取被审快照，只在本证据目录写入。"""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
from unittest.mock import patch

BASE = Path(__file__).resolve().parent
SNAPSHOT = BASE / '被审快照'
EXAMPLES = SNAPSHOT / '求解器/数据/样例'
sys.dont_write_bytecode = True
sys.path.insert(0, str(EXAMPLES))
import check_examples as checker
import check_golden_trace as golden
import test_runtime_input as regression


def save(name, value):
    path = BASE / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    return path


def independent_geometry(data, catalog):
    """独立按目录旋转端口，不调用被审几何函数。"""
    kinds = {row['id']: row for row in catalog['units']}
    directions = {'south': (0, -1), 'east': (1, 0), 'north': (0, 1), 'west': (-1, 0)}
    occupied = set()
    ports = {}
    for unit in data['layout']['units']:
        kind = kinds[unit['kind']]
        width, height = [int(kind['dimensions'][key]['value']) for key in ('width', 'height')]
        ox, oy = [int(q['value']) for q in unit['origin']]
        turns = int(unit['rotation'][1:]) // 90

        def rotate(x, y):
            w, h = width, height
            for _ in range(turns):
                x, y, w, h = h - 1 - y, x, h, w
            return ox + x, oy + y

        cells = {rotate(x, y) for x in range(width) for y in range(height)}
        assert not occupied.intersection(cells)
        assert all(0 <= x < 70 and 0 <= y < 70 for x, y in cells)
        occupied.update(cells)
        if unit['kind'] == '桥接器':
            edges = {edge['side']: copy.deepcopy(edge) for variant in kind['ports']['layouts'] for edge in variant}
            for edge in edges.values():
                axis = 'vertical' if edge['side'] in ('south', 'north') else 'horizontal'
                edge['role'] = 'input' if edge['side'] == unit['bridge_axes'][axis]['input_side'] else 'output'
            edges = list(edges.values())
        else:
            edges = kind['ports']['layouts'][unit['port_layout']]
        for edge in edges:
            side = edge['side']
            for position in edge['positions']:
                p = int(position['value'])
                x, y = {'south': (p, 0), 'north': (p, height - 1), 'west': (0, p), 'east': (width - 1, p)}[side]
                dx, dy = directions[side]
                for _ in range(turns):
                    dx, dy = -dy, dx
                ports[f"{unit['id']}:{side}:{p}"] = (rotate(x, y), (dx, dy), edge['role'], kind['family'])
    channels = set()
    for left, ((x, y), (dx, dy), role, family) in ports.items():
        if role != 'output':
            continue
        for right, (cell, normal, target_role, target_family) in ports.items():
            if cell == (x + dx, y + dy) and normal == (-dx, -dy) and target_role == 'input' and 'transport' in (family, target_family):
                channels.add(f'PC|{left}|{right}')
    assert channels == {row['id'] for row in data['layout']['physical_channels']}
    return {'units': len(data['layout']['units']), 'occupied_cells': len(occupied), 'physical_channels': len(channels)}


def inspect_trace(output):
    """逐项核查手算成功事件、整格库存、制造进度、物料账和端口额度。"""
    expected_success = [
        ['J|0|0|0'],
        ['J|1|0|1', 'J|1|0|11', 'J|1|1|0'],
        ['C|2|crusher', 'J|2|0|1', 'J|2|0|11', 'J|2|1|0', 'J|2|1|2'],
        ['C|3|crusher', 'J|3|0|1', 'J|3|0|4', 'J|3|0|11', 'J|3|1|0', 'J|3|1|3'],
    ]
    expected_powder = [[], [], ['belt_a0:transport:0'], ['belt_a1:transport:0', 'belt_b0:transport:0']]
    result = []
    for t, tick in enumerate(output['trace']['ticks']):
        state = tick['state']
        assert [event['event'] for event in tick['events'] if event['outcome'] == 'success'] == expected_success[t]
        expected = {'feed_belt:transport:0': ('源矿', 1, t)}
        if t:
            expected['crusher:buffer:0'] = ('源矿', 1, t)
        expected.update({slot: ('源石粉末', 1, t) for slot in expected_powder[t]})
        actual = {}
        for row in state['inventory']:
            if row['contents']:
                assert len(row['contents']) == 1
                content = row['contents'][0]
                actual[row['slot']] = (content['item'], int(content['quantity']['value']), int(content['entered_at']['value']['value']))
        assert actual == expected
        ore = next(slot for slot in state['warehouse']['slots'] if slot['item'] == '源矿')
        assert int(ore['quantity']['value']) == 79999 - t
        assert sum(count for _, count, _ in actual.values()) == t + 1
        assert all(int(slot['quantity']['value']) == 80000 for slot in state['warehouse']['slots'] if slot['item'] != '源矿')
        for progress in state['progress']:
            if progress['unit'] != 'crusher' or t == 0:
                assert progress['phase'] == 'idle' and progress['remaining'] is None
            else:
                assert progress['phase'] == 'working' and progress['recipe'] == '粉碎-源矿'
                assert progress['remaining']['value']['value'] == '1'
        context = state['semantic_context']['tick_context']['value']
        counts = {}
        for movement in context['movements']:
            assert movement['event'] in expected_success[t]
            assert movement['quantity']['value'] == '1'
            for port in movement['channel'].split('|')[1:]:
                counts[port] = counts.get(port, 0) + 1
        assert max(counts.values()) == 1
        assert counts == {r['port']: int(r['quantity']['value']) for r in context['port_usage']}
        assert tick['closure']['scan_rounds'] == (2 if t == 0 else 3)
        result.append({'tick': t, 'success_events': expected_success[t], 'inventory_and_balance': '通过', 'port_budget': '通过'})
    return result


def run_regression(label, output):
    path = save('反例/' + label + '.json', output)
    regression.OUTPUT = path
    saved_write = Path.write_text

    def redirect_write(target, content, *args, **kwargs):
        # 被审回归固定写其原报告位置；在此只把报告重定向进复核证据。
        if target == SNAPSHOT / '求解器/规格/内核输入修订验证-r3/运行回归结果.json':
            target = BASE / ('日志/' + label + '-回归报告.json')
        assert target.is_relative_to(BASE) and not target.is_relative_to(SNAPSHOT), str(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        return saved_write(target, content, *args, **kwargs)

    stdout = io.StringIO()
    try:
        with patch.object(Path, 'write_text', redirect_write), contextlib.redirect_stdout(stdout):
            regression.main()
    except Exception as error:
        result = {'status': '拒绝', 'error': type(error).__name__ + ': ' + str(error)}
    else:
        result = {'status': '通过'}
    (BASE / '日志').mkdir(exist_ok=True)
    (BASE / ('日志/' + label + '.log')).write_text(stdout.getvalue() + json.dumps(result, ensure_ascii=False) + '\n')
    return result


def main():
    data = checker.load_json(golden.INPUT)
    catalog = checker.load_json(EXAMPLES.parent / '正式静态目录.json')
    documents = [checker.load_json(EXAMPLES / name) for name in checker.NAMES]
    original = checker.load_json(EXAMPLES / '混做粉碎机两下游-运行记录.json')
    result = {'geometry': {name: independent_geometry(doc, catalog) for name, doc in zip(checker.NAMES, documents)}}
    result['existing_negative_tests'] = checker.negative_tests(documents)
    result['existing_representation_tests'] = checker.representation_tests(documents)
    result['input_checks'] = [checker.check(doc, EXAMPLES / name) for doc, name in zip(documents, checker.NAMES)]
    ticks = golden.run(data)
    result['recomputed_full_ticks_equal_archived_record'] = ticks == original['trace']['ticks']
    assert result['recomputed_full_ticks_equal_archived_record']
    result['independent_trace_checks'] = inspect_trace(original)
    # 只在证据目录重新生成一份一致的运行记录，不更新被审原件或快照。
    golden.OUTPUT = BASE / '参考重算记录.json'
    with contextlib.redirect_stdout(io.StringIO()):
        golden.main()
    regenerated = checker.load_json(golden.OUTPUT)
    result['coherent_baseline'] = run_regression('正常重算记录', regenerated)
    assert result['coherent_baseline']['status'] == '通过'

    bad = copy.deepcopy(regenerated)
    next(r for r in bad['trace']['ticks'][0]['state']['inventory'] if r['slot'] == 'feed_belt:transport:0')['contents'][0]['quantity']['value'] = '2'
    result['over_capacity_trace'] = run_regression('运输格两件仍绿', bad)

    bad = copy.deepcopy(regenerated)
    bad['parameter_assignment']['fixedness_unproven']['time.domain']['value'] = 'invented_domain'
    result['wrong_record_assignment'] = run_regression('记录参数与输入不符仍绿', bad)

    bad = copy.deepcopy(regenerated)
    bad['trace']['ticks'][3]['events'] = []
    result['missing_actual_events'] = run_regression('末刻无事件仍绿', bad)

    assignment = checker.load_json(EXAMPLES / 'kernel_profile_v1参数赋值.json')
    source = (EXAMPLES / assignment['profile_source']['path']).resolve()
    result['stale_assignment_source'] = {'recorded': assignment['profile_source']['sha256'], 'actual': hashlib.sha256(source.read_bytes()).hexdigest(), 'accepted_in_coherent_baseline': result['coherent_baseline']['status'] == '通过'}
    dependencies = {str((EXAMPLES / name).resolve()) for name in ('check_examples.py', 'kernel_profile_v1参数赋值.json')}
    fingerprinted = {row['path'] for row in regenerated['fingerprints']}
    result['unfingerprinted_actual_dependencies'] = sorted(dependencies - fingerprinted)
    result['coverage_examples'] = [row for row in regenerated['uncovered_axes'] if row['axis'] in ('time.domain', 'polling.level_tie', 'transfer.cooldown_scope', 'damping.belt_component_rule')]
    result['schema_parsed'] = True
    result['axis_count'] = len(checker.axis_registry())
    save('复核结果.json', result)
    print(json.dumps({key: value for key, value in result.items() if key not in ('input_checks', 'existing_negative_tests', 'existing_representation_tests', 'independent_trace_checks')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
