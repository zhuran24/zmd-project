#!/usr/bin/env python3
"""第四轮§4.7：只在 kernel/tests/fixtures 生成独立小布局及长区间输入。"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / '数据/样例'))
import check_examples as checker
from generate_examples import unit
from runtime_example import quantity, time_value, decision
from polling_reference import build_sides

OUT = Path(__file__).parent / 'fixtures'
CATALOG = checker.load_json(ROOT / '数据/正式静态目录.json')
BASE = checker.load_json(ROOT / '数据/样例/混做粉碎机两下游.json')


def set_axis(data, name, value):
    """内核输入§5：轴值和种子当前值同步，不改原始样例。"""
    for group in ('fixed', 'offline_mutable', 'fixedness_unproven'):
        if name in data['parameters'][group]:
            data['parameters'][group][name]['value'] = value


def generate(name, local_units, branches=()):
    """内核输入§2–§6：目录导出全部几何和空种子；运行测试另注入明确有限库存。"""
    data = copy.deepcopy(BASE)
    units = [unit('core', '协议核心', 60, 60)] + local_units
    data['scenario'] = {'name': name, 'recipe_intents': [], 'expected_paths': [], 'assertions': []}
    data['catalog']['path'] = str(ROOT / '数据/正式静态目录.json')
    data['parameters']['axis_registry']['path'] = str(ROOT / '规格/选择点参数轴.md')
    data['layout'].update(units=units, physical_channels=None, buffer_channels=None)
    kinds, by_id, ports, channels, buffers, _ = checker.geometry(data, CATALOG)
    data['layout'].update(physical_channels=channels, buffer_channels=buffers)
    order = [u['id'] for u in units if u['kind'] != '传送带'] + [u['id'] for u in units if u['kind'] == '传送带']
    rank = {u: i for i, u in enumerate(order)}
    moments = [{'unit': uid, 'event': f'build_{i}', 'placement': {k: by_id[uid][k] for k in ('kind', 'origin', 'rotation', 'port_layout', 'occupied_cells')}} for i, uid in enumerate(order)]
    data['construction'].update(selected_order=order, moments=moments)
    events = [{'id': f'build_{i}', 'kind': 'build', 'time': time_value(i-len(order))} for i in range(len(order))]
    events += [{'id': k, 'kind': k, 'time': time_value(0)} for k in ('blueprint_complete', 'debug_end')]
    relations = [{'before': a['id'], 'after': b['id'], 'relation': 'strict' if a['time'] != b['time'] else 'occurs_before', 'basis': ['有限合成建造史']} for a, b in zip(events, events[1:])]
    connections = []
    for i, c in enumerate(channels):
        a, b = [ports[c[k]]['unit'] for k in ('source_port', 'target_port')]
        later = max(rank[a], rank[b])
        events.append({'id': f'connect_{i}', 'kind': 'connection_open', 'time': time_value(later-len(order))})
        connections.append({'event': f'connect_{i}', 'channel': c['id'], 'action': 'open', 'cause': f'build_{later}', 'geometry_snapshot': data['layout']['id'], 'construction_basis': decision({'source_build': f'build_{rank[a]}', 'target_build': f'build_{rank[b]}', 'later_build': f'build_{later}'}, '受限转移§1：明确有限历史')})
    data['timeline'].update(events=events, relations=relations, connection_events=connections)
    data['settings'].update(switches=[{'unit': u['id'], 'function': f, 'enabled': False} for u in units for f in kinds[u['kind']]['powered_functions']], gates=[{'unit': u['id'], 'item': None, 'total_limit': None, 'window_limit': None} for u in units if u['kind'] == '物品准入口'], warehouse_assignments=[{'port': pid, 'slot': 'warehouse_0'} for pid, p in ports.items() if p['role'] == 'output' and by_id[p['unit']]['kind'] == '协议核心'])
    templates = [{'operation': 'move', 'target': c['id']} for c in channels] + [{'operation': f, 'target': u['id']} for u in units for f in kinds[u['kind']]['powered_functions']]
    set_axis(data, 'judgment.order', {'schema': 'event-order-v1', 'scope': 'global', 'template_order': templates, 'repeat_embedding': 'scan_round_then_template', 'instant_overrides': []})
    set_axis(data, 'connection.tie', {'kind': 'explicit_order', 'channels': [c['id'] for c in channels]})
    set_axis(data, 'connection.belt_shape', {'kind': 'layout_build_history', 'values': [{'unit': u['id'], 'build_event': f"build_{rank[u['id']]}", 'shape': {0: 'straight', 1: 'turn_left', 2: 'turn_right'}[u['port_layout']]} for u in units if u['kind'] == '传送带']})
    set_axis(data, 'transfer.phase', {'kind': 'explicit_residuals', 'values': [{'unit': u['id'], 'slot': None, 'remaining': time_value(0)} for u in units if u['kind'] == '协议储存箱']})
    set_axis(data, 'manufacturing.input_slot_selection', {'kind': 'explicit_order', 'slots': []})
    set_axis(data, 'damping.branch', {'schema': 'damping-branch-v1', 'fixedness': 'fixed_for_run', 'choices': list(branches), 'evaluations': [], 'on_missing': 'unresolved'})
    set_axis(data, 'warehouse.external_supply', {'kind': 'explicit_ore_history', 'events': [], 'through': time_value(1000), 'basis': '本有限独立试验无矿源出库；初始库存充足'})
    seed = data['initial_state']['nonwarehouse']['value']
    seed['inventory'] = [{'slot': f"{u['id']}:{r['role']}:{i}", 'contents': []} for u in units for r in kinds[u['kind']]['inventory'] if r['role'] != 'warehouse' for i in range(checker.quantity(r['count']))]
    seed['progress'] = [{'unit': u['id'], 'phase': 'idle', 'recipe': None, 'candidate_recipes': [], 'locked_recipe': None, 'remaining': None, 'cooldowns': [{'slot': None, 'remaining': time_value(0)}] if u['kind'] == '协议储存箱' else []} for u in units if kinds[u['kind']]['powered_functions']]
    memory = build_sides(data, kinds, by_id, ports, channels)
    for side in memory['sides']:
        if not side['graded'] and side['levels']:
            side['current_level'] = side['levels'][0]['id']
    seed['logistics'].update(active_channels=[c['id'] for c in channels], blocked_channels=[], gate_counters=[{'unit': u['id'], 'total_received': quantity(0), 'window_received': quantity(0), 'window_started_at': None, 'blocked_reasons': []} for u in units if u['kind'] == '物品准入口'], poll_memory=decision(memory, '受限转移§3.2：全空起点'))
    seed['semantic_context']['arbitration']['level_order'] = [l['id'] for s in memory['sides'] for l in s['levels']]
    seed['semantic_context']['parameter_values'] = [{'axis': a, 'value': d, 'lifetime': {'fixed': 'F', 'offline_mutable': 'O', 'fixedness_unproven': 'U'}[g]} for g in ('fixed', 'offline_mutable', 'fixedness_unproven') for a, d in data['parameters'][g].items()]
    from migrate_round5 import migrate
    data=migrate(data)
    set_axis(data,'manufacturing.input_slot_selection',{'kind':'explicit_order','slots':[r['slot'] for r in seed['inventory'] if ':input:' in r['slot']]})
    data=migrate(data)
    (OUT / f'{name}.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    return data


def main():
    """第四轮§4.7–§4.8：生成三种独立机制布局和明确延长的1000刻历史。"""
    OUT.mkdir(exist_ok=True)
    generate('bridge', [unit('south_box', '协议储存箱', 10, 7), unit('bridge', '桥接器', 12, 10), unit('north_box', '协议储存箱', 12, 11), unit('west_box', '协议储存箱', 9, 10, 'r270'), unit('east_box', '协议储存箱', 13, 8, 'r270'), unit('power', '供电桩', 16, 10)])
    generate('priority', [unit('source', '协议储存箱', 10, 10), unit('merger', '汇流器', 10, 13), unit('gate', '物品准入口', 10, 14), unit('sink_a', '协议储存箱', 10, 15), unit('sink_b', '协议储存箱', 13, 14), unit('belt_1', '传送带', 12, 13, port_layout=1), unit('belt_2', '传送带', 13, 13, 'r270', 2)])
    generate('core_inbound', [unit('box', '协议储存箱', 50, 46), unit('belt', '传送带', 51, 49)])
    data = copy.deepcopy(BASE)
    data['catalog']['path'] = str(ROOT / '数据/正式静态目录.json')
    data['parameters']['axis_registry']['path'] = str(ROOT / '规格/选择点参数轴.md')
    supply = {'kind': 'explicit_ore_history', 'events': [], 'through': time_value(999), 'basis': '1000时刻至多出1000件源矿，初始80000足够；无自动补仓'}
    set_axis(data, 'warehouse.external_supply', supply)
    for row in data['initial_state']['nonwarehouse']['value']['semantic_context']['parameter_values']:
        if row['axis'] == 'warehouse.external_supply':
            row['value']['value'] = supply
    (OUT / 'benchmark_1000.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
